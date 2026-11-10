"""Expectations: simple checks on what a call returned.

Forms: ``status == 200``, ``<path> exists``, ``<path> == <value>``,
``<path> contains <text>``. Targets: ``status`` (last request), ``error``
(exception class name), ``http[N].status`` / ``http[N].body.<path>`` (the N-th
raw response), otherwise a path into the method's normalised return value.
"""
from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from typing import Any, Literal, Optional

from almaapitk.lab.capture import CapturedRequest
from almaapitk.lab.normalize import resolve

Op = Literal["==", "exists", "contains"]
USAGE = 'use "status == 200", "<path> exists", "<path> == <value>" or "<path> contains <text>"'
_HTTP = re.compile(r"^http\[(-?\d+)\]\.(status|body)(?:\.(.+))?$")


@dataclass(frozen=True)
class Expectation:
    text: str
    target: str
    op: Op
    value: Optional[str]


def parse_expectation(text: str) -> Expectation:
    try:
        parts = shlex.split(text)
    except ValueError as exc:
        raise ValueError(f"cannot read expectation {text!r} ({exc}); {USAGE}") from None
    if len(parts) == 2 and parts[1] == "exists":
        return Expectation(text, parts[0], "exists", None)
    if len(parts) >= 3 and parts[1] in ("==", "contains"):
        return Expectation(text, parts[0], parts[1], " ".join(parts[2:]))  # type: ignore[arg-type]
    raise ValueError(f"cannot read expectation {text!r}; {USAGE}")


def evaluate(
    exp: Expectation,
    *,
    result: Any,
    requests: list[CapturedRequest],
    error: Optional[str],
) -> dict:
    """``{"text", "outcome": "passed"|"failed"|"error", "actual"}``."""
    try:
        actual = _target_value(exp.target, result, requests, error)
    except KeyError as exc:
        return {"text": exp.text, "outcome": "failed", "actual": f"missing: {exc.args[0]}"}
    except Exception as exc:  # a malformed body or path: report, never crash the run
        return {"text": exp.text, "outcome": "error", "actual": f"{type(exc).__name__}: {exc}"}
    return {"text": exp.text, "outcome": "passed" if _check(exp, actual) else "failed", "actual": actual}


def _target_value(target: str, result: Any, requests: list[CapturedRequest], error: Optional[str]) -> Any:
    sent = [r for r in requests if r.sent]
    if target == "status":
        if not sent:
            raise KeyError("status (no request was sent)")
        return sent[-1].status
    if target == "error":
        return error
    match = _HTTP.match(target)
    if match:
        index, part, path = int(match.group(1)), match.group(2), match.group(3)
        try:
            req = sent[index]
        except IndexError:
            raise KeyError(f"http[{index}] (only {len(sent)} requests were sent)") from None
        if part == "status":
            return req.status
        body = _parse_body(req.response_body or "")
        return resolve(body, path) if path else body
    return resolve(result, target)


def _parse_body(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return text  # XML is parsed by resolve()


def _check(exp: Expectation, actual: Any) -> bool:
    if exp.op == "exists":
        return actual not in (None, "", [], {})
    if exp.op == "contains":
        haystack = actual if isinstance(actual, str) else json.dumps(actual, ensure_ascii=False)
        return str(exp.value) in haystack
    return _equal(actual, str(exp.value))


def _equal(actual: Any, wanted: str) -> bool:
    if isinstance(actual, bool):
        return str(actual).lower() == wanted.lower()
    try:
        return float(actual) == float(wanted)
    except (TypeError, ValueError):
        return str(actual) == wanted
