"""Run one operation and produce its evidence record.

Both front ends (headless command and app) call ``Session.run``. Input
problems raise ``InputError`` before anything is sent; anything that goes
wrong once the method runs is recorded in the evidence, never raised.
"""
from __future__ import annotations

import difflib
import json
import re
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Optional
from urllib.parse import quote, urlsplit

from almaapitk.alma_logging import get_logger
from almaapitk.lab import catalog
from almaapitk.lab.capture import Recorder, WriteCancelled, WriteGate, make_lab_client
from almaapitk.lab.catalog import Operation, find_operation
from almaapitk.lab.endpoints import Endpoint, custom_endpoint, get_twin, match, wrapped_by
from almaapitk.lab.evidence import (
    DEFAULT_EVIDENCE_DIR,
    EvidenceError,
    EvidenceRecord,
    new_record,
    write_record,
)
from almaapitk.lab.expect import evaluate, parse_expectation
from almaapitk.lab.hints import HINTS
from almaapitk.lab.normalize import normalize_result

_TRUE = {"true", "yes", "y", "1", "on"}
_FALSE = {"false", "no", "n", "0", "off"}


class InputError(ValueError):
    """An input cannot be used; ``field`` names it (or ``expect``)."""

    def __init__(self, field: str, message: str):
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


def coerce_inputs(op: Operation, raw: dict[str, Any]) -> dict[str, Any]:
    """Typed keyword arguments for ``op`` from text (or already-typed) values."""
    params = {p.name: p for p in op.params}
    for name in raw:
        if name not in params:
            raise InputError(name, f"not a parameter of {op.qualname}")
    out: dict[str, Any] = {}
    for p in op.params:
        value = raw.get(p.name)
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == "":
            if p.required:
                raise InputError(p.name, "is required")
            continue
        out[p.name] = _coerce(p, value)
    return out


def _coerce(p: catalog.Param, value: Any) -> Any:
    if not isinstance(value, str):
        if p.kind == "unsupported":
            raise InputError(p.name, "cannot be set in the lab")
        return value
    try:
        if p.kind == "int":
            return int(value)
        if p.kind == "float":
            return float(value)
        if p.kind == "bool":
            low = value.lower()
            if low in _TRUE or low in _FALSE:
                return low in _TRUE
            raise ValueError("expected true or false")
        if p.kind == "json":
            return json.loads(value)
    except ValueError as exc:
        raise InputError(p.name, f"{_kind_word(p.kind)} expected ({exc})") from None
    if p.kind == "choice" and p.choices and value not in p.choices:
        raise InputError(p.name, f"must be one of: {', '.join(p.choices)}")
    if p.kind == "unsupported":
        raise InputError(p.name, "cannot be set in the lab")
    return value


def _kind_word(kind: str) -> str:
    return {"int": "a whole number", "float": "a number", "bool": "true or false",
            "json": "JSON"}.get(kind, kind)


# --- raw calls ----------------------------------------------------------------

_PLACEHOLDER = re.compile(r"\{([^}]+)\}")


@dataclass
class RawRequest:
    """One raw call as the front ends describe it (text values, not yet checked)."""

    endpoint: Endpoint
    path_params: dict[str, str]
    query: dict[str, str]
    body: Optional[str] = None
    fmt: Literal["json", "xml"] = "json"
    baseline_query: dict[str, str] = field(default_factory=dict)


def resolve_path(endpoint: Endpoint, path_params: dict[str, str]) -> str:
    """The concrete path for ``raw_request`` (no leading ``/``), each value URL-quoted."""
    def fill(m: re.Match) -> str:
        value = _clean(path_params.get(m.group(1)))
        if value == "":
            raise InputError(m.group(1), "is required")
        return quote(str(value), safe="")

    return _PLACEHOLDER.sub(fill, endpoint.path).lstrip("/")


def _path_values(endpoint: Endpoint, path_params: dict[str, str]) -> dict[str, str]:
    """The path values the template uses, stripped (as recorded in ``inputs``)."""
    resolve_path(endpoint, path_params)  # raises for a missing one
    return {name: str(_clean(path_params[name])) for name in _PLACEHOLDER.findall(endpoint.path)}


def coerce_query(endpoint: Endpoint, query: dict[str, Any]) -> dict[str, Any]:
    """Typed query parameters: blanks dropped, integers and booleans checked."""
    known = {p.name: p for p in endpoint.query_params}
    out: dict[str, Any] = {}
    for name, value in query.items():
        value = _clean(value)
        if value == "":
            continue
        param = known.get(name)
        if param is None and not endpoint.custom:
            raise InputError(name, f"not a query parameter of {endpoint.key}")
        out[name] = _coerce_query_value(param.type if param else "string", name, value)
    return out


def _coerce_query_value(kind: str, name: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if kind == "integer":
        try:
            return int(value)
        except ValueError:
            raise InputError(name, f"a whole number expected, not {value!r}") from None
    if kind == "boolean":
        low = value.lower()
        if low in _TRUE or low in _FALSE:
            return low in _TRUE
        raise InputError(name, "true or false expected")
    return value


def _clean(value: Any) -> Any:
    if value is None:
        return ""
    return value.strip() if isinstance(value, str) else value


def normalise_body(text: str, fmt: str) -> str:
    """JSON pretty-printed with sorted keys; XML (or anything unparsable) as text,
    trailing whitespace stripped per line. Used for both the diff and the stale check."""
    if fmt == "json":
        try:
            return json.dumps(json.loads(text), sort_keys=True, indent=2, ensure_ascii=False)
        except ValueError:
            pass
    return "\n".join(line.rstrip() for line in text.splitlines())


def body_diff(before: str, after: str, fmt: str) -> str:
    """Unified diff of the baseline body → the sent body, after normalising both."""
    lines = difflib.unified_diff(normalise_body(before, fmt).splitlines(),
                                 normalise_body(after, fmt).splitlines(),
                                 fromfile="baseline", tofile="sent", lineterm="")
    return "\n".join(lines)


def _response_body(record: EvidenceRecord) -> str:
    sent = [r for r in record.requests if r.sent]
    return (sent[-1].response_body or "") if sent else ""


class Session:
    """One environment, one client, one evidence folder."""

    def __init__(
        self,
        environment: str = "SANDBOX",
        evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
        gate: Optional[WriteGate] = None,
        source: str = "app",
        command: Optional[str] = None,
    ):
        self.environment = environment.upper()
        self.evidence_dir = Path(evidence_dir)
        self.gate = gate
        self.source = source
        self.command = command
        self.logger = get_logger("lab", environment=self.environment)
        self._client = None
        self._recorder: Optional[Recorder] = None
        self._domains: dict[str, Any] = {}
        self.last_path: Optional[Path] = None
        self._lock = threading.Lock()

    @property
    def client(self):
        if self._client is None:
            self._client = make_lab_client(self.environment)
            self._recorder = Recorder(self._client, gate=self._gate)
            self._recorder.install()
        return self._client

    def _gate(self, method: str, url: str, body: Optional[str]) -> bool:
        return bool(self.gate and self.gate(method, url, body))

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def run(self, op: Operation, raw_inputs: dict[str, Any],
            expectations: Iterable[str] = ()) -> EvidenceRecord:
        """Run ``op`` once. One call at a time per session: the recording is shared."""
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("a call is already running in this session; wait for it to finish")
        try:
            return self._run(op, raw_inputs, expectations)
        finally:
            self._lock.release()

    def _run(self, op: Operation, raw_inputs: dict[str, Any],
             expectations: Iterable[str]) -> EvidenceRecord:
        kwargs = coerce_inputs(op, raw_inputs)
        parsed = self._parse_expectations(expectations)
        self._check_writable()  # before anything is sent: never lose a write's evidence
        record = self._new_record(op.qualname, kwargs)
        reason = HINTS.get(op.qualname, {}).get("incomplete_reason")
        record.incomplete, record.incomplete_reason = bool(reason), reason
        self._recorder.start()
        self.logger.info("Lab call", operation=op.qualname, environment=self.environment)
        value, error = None, None
        try:
            value = getattr(self._domain(op.domain), op.name)(**kwargs)
        except Exception as exc:  # recorded, not raised: the evidence is the output
            error = f"{type(exc).__name__}: {exc}"
        return self._finish(record, value, error, parsed)

    def _finish(self, record: EvidenceRecord, value: Any, error: Optional[str],
                parsed: list) -> EvidenceRecord:
        """Collect requests, normalise the result, check expectations, write the record."""
        record.error = error
        record.requests = list(self._recorder.requests)
        record.cancelled_writes = [{"method": r.method, "url": r.url} for r in record.requests if not r.sent]
        record.result, record.capped = normalize_result(value)
        error_class = record.error.split(":", 1)[0] if record.error else None
        record.expectations = [evaluate(e, result=record.result, requests=record.requests,
                                        error=error_class) for e in parsed]
        try:
            self.last_path = write_record(record, self.evidence_dir)
        except EvidenceError as exc:
            exc.record = record  # the call happened: let the front end still show it
            raise
        self.logger.info("Lab call recorded", operation=record.operation, evidence=record.id,
                         status=record.last_status, error=error_class, refused=record.refused)
        return record

    @staticmethod
    def _parse_expectations(expectations: Iterable[str]) -> list:
        try:
            return [parse_expectation(e) for e in expectations]
        except ValueError as exc:
            raise InputError("expect", str(exc)) from None

    def _new_record(self, operation: str, inputs: dict) -> EvidenceRecord:
        return new_record(operation=operation, inputs=inputs, environment=self.environment,
                          base_url_host=urlsplit(self.client.base_url).netloc,
                          source=self.source, command=self.command)

    # --- raw calls ------------------------------------------------------------

    def run_raw(self, req: RawRequest, expectations: Iterable[str] = (),
                baseline: Optional[EvidenceRecord] = None) -> EvidenceRecord:
        """Send one raw call. Input problems raise ``InputError`` before anything is sent."""
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("a call is already running in this session; wait for it to finish")
        try:
            return self._run_raw(req, expectations, baseline)
        finally:
            self._lock.release()

    def fetch_baseline(self, req: RawRequest) -> EvidenceRecord:
        """GET the record an update will start from; a normal raw record."""
        ep = req.endpoint
        twin = custom_endpoint("GET", ep.path) if ep.custom else get_twin(ep)
        if twin is None:
            raise InputError("baseline", f"no GET for {ep.short_path}")
        return self.run_raw(RawRequest(endpoint=twin, path_params=dict(req.path_params),
                                       query=dict(req.baseline_query), fmt=req.fmt))

    def _run_raw(self, req: RawRequest, expectations: Iterable[str],
                 baseline: Optional[EvidenceRecord]) -> EvidenceRecord:
        ep, method = req.endpoint, req.endpoint.method
        path = resolve_path(ep, req.path_params)
        path_values = _path_values(ep, req.path_params)
        query = coerce_query(ep, req.query)
        body_text, data = self._raw_body(req)
        parsed = self._parse_expectations(expectations)
        twin = None if ep.custom or method != "PUT" else get_twin(ep)
        twin_path, twin_query = None, None
        if twin is not None:
            twin_path, twin_query = resolve_path(twin, req.path_params), coerce_query(twin, req.baseline_query)
            self._check_baseline(baseline, twin, path_values, twin_query, req.fmt)
        self._check_writable()  # before anything is sent: never lose a write's evidence
        record = self._new_record(f"raw {method} {ep.path}", {
            "path": path_values, "query": query, "format": req.fmt, "body": body_text})
        record.raw, record.slug = True, ep.slug
        record.endpoint = {"method": method, "path": ep.path, "area": ep.area,
                           "source_fetched": ep.source_fetched, "custom": ep.custom}
        record.wrapped_by = list(wrapped_by(ep))
        if baseline is not None:
            base_body = _response_body(baseline)
            record.baseline = {"evidence_id": baseline.id, "body": base_body}
            record.body_diff = body_diff(base_body, body_text or "", req.fmt)
        accept = {"Accept": "application/xml"} if req.fmt == "xml" else None
        self._recorder.start()
        self.logger.info("Lab raw call", operation=record.operation, environment=self.environment)
        value, error = None, None
        try:
            if twin is not None:
                current = self.client.raw_request("GET", twin_path, params=twin_query,
                                                  custom_headers=accept)
                if normalise_body(current.text(), req.fmt) != normalise_body(
                        record.baseline["body"], req.fmt):
                    record.refused = "baseline changed"
            if record.refused is None:
                value = self._send_raw(method, path, query, data, req.fmt, accept)
        except Exception as exc:  # recorded, not raised: the evidence is the output
            error = f"{type(exc).__name__}: {exc}"
            if twin is not None and not any(r.method == method for r in self._recorder.requests):
                record.refused = "baseline could not be checked"
        return self._finish(record, value, error, parsed)

    def _send_raw(self, method: str, path: str, query: dict, data: Any, fmt: str,
                  accept: Optional[dict]) -> Any:
        return self.client.raw_request(
            method, path, params=query, data=data,
            content_type="application/xml" if fmt == "xml" and data is not None else None,
            custom_headers=accept)

    @staticmethod
    def _raw_body(req: RawRequest) -> tuple[Optional[str], Any]:
        """``(body text as recorded, data for raw_request)``; checks JSON and required bodies."""
        ep = req.endpoint
        if req.fmt not in ("json", "xml"):
            raise InputError("format", "must be json or xml")
        text = req.body if req.body is not None and req.body.strip() else None
        if text is None:
            if ep.method in ("POST", "PUT") and ep.body_formats and not ep.custom:
                raise InputError("body", "is required")
            return None, None
        if ep.body_formats and req.fmt not in ep.body_formats:
            raise InputError("format", f"{ep.key} accepts {' or '.join(ep.body_formats)}")
        if req.fmt == "xml":
            return text, text
        try:
            parsed = json.loads(text)
        except ValueError as exc:
            raise InputError("body", f"JSON expected ({exc})") from None
        # a dict goes as JSON; anything else is sent as JSON text
        return text, parsed if isinstance(parsed, dict) else json.dumps(parsed)

    @staticmethod
    def _check_baseline(baseline: Optional[EvidenceRecord], twin: Endpoint,
                        path_values: dict[str, str], twin_query: dict[str, Any], fmt: str) -> None:
        message = "load the current record first"
        if baseline is None:
            raise InputError("baseline", message)
        status = baseline.last_status
        ok = (baseline.raw and baseline.error is None and baseline.refused is None
              and status is not None and 200 <= status < 300
              and (baseline.endpoint or {}).get("method") == "GET"
              and (baseline.endpoint or {}).get("path") == twin.path
              and baseline.inputs.get("path") == path_values
              and baseline.inputs.get("query") == twin_query
              and baseline.inputs.get("format") == fmt)
        if not ok:
            raise InputError("baseline", message)

    def _check_writable(self) -> None:
        try:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=self.evidence_dir):
                pass
        except OSError as exc:
            raise EvidenceError(f"cannot write evidence under {self.evidence_dir}: {exc}; "
                                "nothing was sent") from exc

    def rerun(self, record: EvidenceRecord) -> EvidenceRecord:
        expectations = [e["text"] for e in record.expectations]
        if record.raw:
            return self.run_raw(_raw_request_from(record), expectations)
        return self.run(find_operation(record.operation), dict(record.inputs), expectations)

    def _domain(self, name: str) -> Any:
        if name not in self._domains:
            self._domains[name] = catalog.DOMAINS[name](self.client)
        return self._domains[name]


def _raw_request_from(record: EvidenceRecord) -> RawRequest:
    """Rebuild the request of a raw record (for rerun)."""
    info, inputs = record.endpoint or {}, record.inputs
    method, template = info.get("method", ""), info.get("path", "")
    values = {k: str(v) for k, v in (inputs.get("path") or {}).items()}
    ep = None
    if not info.get("custom"):
        concrete = _PLACEHOLDER.sub(lambda m: quote(values.get(m.group(1), ""), safe=""), template)
        found = match(method, concrete)
        if found is not None:
            ep, values = found
    if ep is None:
        ep = custom_endpoint(method, template)
    if ep.method == "PUT" and not ep.custom and get_twin(ep) is not None:
        raise InputError("baseline", "load the current record again before resending an update")
    query = {k: (str(v).lower() if isinstance(v, bool) else str(v))
             for k, v in (inputs.get("query") or {}).items()}
    return RawRequest(endpoint=ep, path_params=values, query=query, body=inputs.get("body"),
                      fmt=inputs.get("format") or "json")


__all__ = ["InputError", "RawRequest", "Session", "WriteCancelled", "body_diff", "coerce_inputs",
           "coerce_query", "normalise_body", "resolve_path"]
