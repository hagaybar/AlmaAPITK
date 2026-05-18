"""R10 regression test for issue #142 — TextFormatter PII leak.

Bug discovered 2026-05-18 during live SANDBOX testing of the bib-record
roundtrip (``BibliographicRecords.get_record``): the ``api_client``
logger emits a DEBUG record on every request carrying the full
``headers`` dict, including ``Authorization: apikey <real_key>``.

The toolkit ships a ``redact_sensitive_data()`` helper in
``almaapitk.alma_logging.formatters`` whose default patterns include
``'authorization'`` — but the helper is only wired into
``JSONFormatter.format()``. ``TextFormatter.format()`` (the formatter
used on the stderr console handler) writes ``record.__dict__`` entries
straight as ``key=value`` text without ever calling the redactor.
Consequence: every request prints the live API key to stderr.

These tests pin the *symptom* — given a LogRecord that carries a
``headers`` custom field containing an ``Authorization: apikey ...``
value, the formatted output must NOT contain the literal value. The
fix wires ``redact_sensitive_data`` into ``TextFormatter.format()``
the same way ``JSONFormatter`` already does.

Pattern source: ``tests/unit/regressions/test_issue_119_user_note_write_shape.py``.
"""

from __future__ import annotations

import logging

from almaapitk.alma_logging.formatters import (
    JSONFormatter,
    TextFormatter,
    redact_sensitive_data,
)


# A clearly-fake API key string. Synthetic; matches the *shape* of an
# Alma key but the digits are all zero except for a short marker so it
# is easy to grep for in the captured output. Per CLAUDE.md R9 the
# test must never contain a real tenant key.
FAKE_APIKEY_VALUE = "FAKETEST_apikey_value_THAT_MUST_BE_REDACTED_42"
FAKE_AUTHORIZATION = f"apikey {FAKE_APIKEY_VALUE}"


def _make_record(custom_fields: dict) -> logging.LogRecord:
    """Build a LogRecord that mirrors how the toolkit's loggers emit
    request lines — message plus a dict of structured kwargs attached as
    attributes."""
    record = logging.LogRecord(
        name="almapi.api_client",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg="API Request: GET almaws/v1/bibs/<mms_id>",
        args=(),
        exc_info=None,
    )
    for key, value in custom_fields.items():
        setattr(record, key, value)
    return record


# --- TextFormatter redaction (the leak we hit) ----------------------------


def test_text_formatter_redacts_authorization_header_value():
    """The literal ``Authorization`` header value must not appear in
    ``TextFormatter`` output. This is the headline bug from #142."""
    record = _make_record(
        {
            "method": "GET",
            "endpoint": "almaws/v1/bibs/990000000000000000",
            "headers": {"Authorization": FAKE_AUTHORIZATION},
        }
    )
    formatter = TextFormatter(use_colors=False)
    out = formatter.format(record)
    # The fake key must be gone; the structural shell stays so operators
    # can still see *that* an Authorization header was sent.
    assert FAKE_APIKEY_VALUE not in out, (
        "TextFormatter leaked the Authorization header value into the "
        "formatted record. See issue #142. Output was:\n" + out
    )
    assert FAKE_AUTHORIZATION not in out, (
        "TextFormatter leaked the full Authorization header value into the "
        "formatted record. See issue #142. Output was:\n" + out
    )


def test_text_formatter_redacts_apikey_dict_value():
    """A top-level ``apikey`` custom field must also be redacted (mirrors
    the existing JSONFormatter pattern set)."""
    record = _make_record({"apikey": FAKE_APIKEY_VALUE})
    formatter = TextFormatter(use_colors=False)
    out = formatter.format(record)
    assert FAKE_APIKEY_VALUE not in out, (
        "TextFormatter leaked the apikey field value. Output was:\n" + out
    )


def test_text_formatter_redacts_nested_authorization():
    """Nested dicts inside custom fields must also be redacted (the
    request-headers case is exactly this nesting)."""
    record = _make_record(
        {
            "request": {
                "headers": {
                    "Authorization": FAKE_AUTHORIZATION,
                    "Accept": "application/json",
                },
                "method": "GET",
            }
        }
    )
    formatter = TextFormatter(use_colors=False)
    out = formatter.format(record)
    assert FAKE_APIKEY_VALUE not in out, (
        "TextFormatter leaked a nested Authorization value. Output was:\n" + out
    )
    # Non-sensitive nested fields should still be present (the formatter
    # didn't accidentally strip everything).
    assert "Accept" in out, (
        "TextFormatter dropped a non-sensitive nested field while "
        "redacting. Output was:\n" + out
    )


def test_text_formatter_keeps_non_secret_fields_visible():
    """Verify the redactor doesn't over-redact — non-secret fields stay
    visible so the formatter is still useful for operators."""
    record = _make_record(
        {
            "method": "GET",
            "endpoint": "almaws/v1/bibs/990000000000000000",
            "duration_ms": 591.2,
        }
    )
    formatter = TextFormatter(use_colors=False)
    out = formatter.format(record)
    assert "method=GET" in out
    assert "endpoint=almaws/v1/bibs/990000000000000000" in out
    assert "duration_ms=591.2" in out


# --- JSONFormatter parity (regression-guard so the existing path stays --
# fixed even after the TextFormatter change) -----------------------------


def test_json_formatter_redaction_still_works():
    """Pin existing behavior: the JSONFormatter already redacts. This
    test guards against an accidental regression while we're editing the
    formatters module."""
    record = _make_record(
        {"headers": {"Authorization": FAKE_AUTHORIZATION}}
    )
    out = JSONFormatter().format(record)
    assert FAKE_APIKEY_VALUE not in out, (
        "JSONFormatter regression: Authorization value leaked. "
        "Output was:\n" + out
    )


# --- redact_sensitive_data helper (sanity check on the pattern set) -----


def test_redactor_default_patterns_cover_authorization():
    """The default pattern list must include 'authorization' so the
    common case (HTTP Authorization header) is covered without
    consumers having to configure it."""
    result = redact_sensitive_data(
        {"Authorization": FAKE_AUTHORIZATION, "User-Agent": "almaapitk/test"}
    )
    assert result["Authorization"] == "***REDACTED***"
    assert result["User-Agent"] == "almaapitk/test"
