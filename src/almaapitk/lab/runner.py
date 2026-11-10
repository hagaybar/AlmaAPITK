"""Run one operation and produce its evidence record.

Both front ends (headless command and app) call ``Session.run``. Input
problems raise ``InputError`` before anything is sent; anything that goes
wrong once the method runs is recorded in the evidence, never raised.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlsplit

from almaapitk.alma_logging import get_logger
from almaapitk.lab import catalog
from almaapitk.lab.capture import Recorder, WriteCancelled, WriteGate, make_lab_client
from almaapitk.lab.catalog import Operation, find_operation
from almaapitk.lab.evidence import DEFAULT_EVIDENCE_DIR, EvidenceRecord, new_record, write_record
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
        kwargs = coerce_inputs(op, raw_inputs)
        try:
            parsed = [parse_expectation(e) for e in expectations]
        except ValueError as exc:
            raise InputError("expect", str(exc)) from None
        client = self.client
        record = new_record(operation=op.qualname, inputs=kwargs, environment=self.environment,
                            base_url_host=urlsplit(client.base_url).netloc, source=self.source,
                            command=self.command)
        reason = HINTS.get(op.qualname, {}).get("incomplete_reason")
        record.incomplete, record.incomplete_reason = bool(reason), reason
        self._recorder.start()
        self.logger.info("Lab call", operation=op.qualname, environment=self.environment)
        value = None
        try:
            value = getattr(self._domain(op.domain), op.name)(**kwargs)
        except Exception as exc:  # recorded, not raised: the evidence is the output
            record.error = f"{type(exc).__name__}: {exc}"
        record.requests = list(self._recorder.requests)
        record.cancelled_writes = [{"method": r.method, "url": r.url} for r in record.requests if not r.sent]
        record.result, record.capped = normalize_result(value)
        error_class = record.error.split(":", 1)[0] if record.error else None
        record.expectations = [evaluate(e, result=record.result, requests=record.requests,
                                        error=error_class) for e in parsed]
        write_record(record, self.evidence_dir)
        self.logger.info("Lab call recorded", operation=op.qualname, evidence=record.id,
                         status=record.last_status, error=error_class)
        return record

    def rerun(self, record: EvidenceRecord) -> EvidenceRecord:
        expectations = [e["text"] for e in record.expectations]
        return self.run(find_operation(record.operation), dict(record.inputs), expectations)

    def _domain(self, name: str) -> Any:
        if name not in self._domains:
            self._domains[name] = catalog.DOMAINS[name](self.client)
        return self._domains[name]


__all__ = ["InputError", "Session", "WriteCancelled", "coerce_inputs"]
