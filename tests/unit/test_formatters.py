"""Unit tests for almaapitk.alma_logging.formatters.

Regression coverage for issue #2: stray `(taskName=None)` on every log line
under Python 3.12+. Python 3.12 added `taskName` as a built-in LogRecord
attribute; both formatters must treat it as standard so it does not bleed
into custom-context output.
"""

from __future__ import annotations

import json
import logging

import pytest

from almaapitk.alma_logging.formatters import JSONFormatter, TextFormatter


def _make_record(extra: dict | None = None) -> logging.LogRecord:
    record = logging.LogRecord(
        name="almaapitk.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=None,
        exc_info=None,
    )
    record.taskName = None  # what Python 3.12+ injects for sync code
    if extra:
        for key, value in extra.items():
            setattr(record, key, value)
    return record


class TestTaskNameNotLeaked:
    """Issue #2: `taskName` from Python 3.12+ must not appear in formatted output."""

    def test_text_formatter_omits_taskname(self) -> None:
        record = _make_record()
        formatted = TextFormatter(use_colors=False).format(record)
        assert "taskName" not in formatted

    def test_text_formatter_keeps_real_custom_fields(self) -> None:
        record = _make_record(extra={"invoice_id": "INV-1"})
        formatted = TextFormatter(use_colors=False).format(record)
        assert "invoice_id=INV-1" in formatted
        assert "taskName" not in formatted

    def test_json_formatter_omits_taskname(self) -> None:
        record = _make_record()
        payload = json.loads(JSONFormatter().format(record))
        assert "taskName" not in payload.get("context", {})
        assert "taskName" not in payload

    def test_json_formatter_keeps_real_custom_fields(self) -> None:
        record = _make_record(extra={"invoice_id": "INV-1"})
        payload = json.loads(JSONFormatter().format(record))
        assert payload["context"] == {"invoice_id": "INV-1"}


@pytest.mark.parametrize(
    "attr",
    [
        "taskName",  # added in Python 3.12 (issue #2)
    ],
)
def test_python_312_logrecord_attrs_are_treated_as_standard(attr: str) -> None:
    """Guard against future drift: any attribute Python's logging module sets
    automatically on LogRecord must not appear in the custom-context tail.
    """
    record = _make_record(extra={attr: None})
    text_out = TextFormatter(use_colors=False).format(record)
    json_out = json.loads(JSONFormatter().format(record))
    assert attr not in text_out
    assert attr not in json_out.get("context", {})
