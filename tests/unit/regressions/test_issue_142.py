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
from io import StringIO

from almaapitk.alma_logging.config import LoggingConfig
from almaapitk.alma_logging.formatters import (
    JSONFormatter,
    TextFormatter,
    redact_sensitive_data,
)
from almaapitk.alma_logging.logger import AlmaLogger


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


# --- PII redaction (issue #142 expansion, 2026-05-25) ---------------------
# Personal data must be scrubbed from logs by default, regardless of log
# level. User identifiers keep only their last three characters
# (123456789 -> <...>789) so operators can still correlate a record in a
# support context; names/emails/addresses/phones are blanked entirely.
# Bibliographic identifiers (mms_id) are NOT personal and must stay
# visible — see test_text_formatter_keeps_non_secret_fields_visible above.

# Synthetic, clearly-fake user id (R9: never a real tenant identifier).
# Last three characters are distinctive so the partial-redaction format
# is easy to assert.
SYNTH_USER_ID = "550000000123"
SYNTH_USER_ID_REDACTED = "<...>123"


def test_redactor_partial_redacts_user_id_field():
    """A ``user_id`` field keeps only its last three characters."""
    out = redact_sensitive_data({"user_id": SYNTH_USER_ID})
    assert out["user_id"] == SYNTH_USER_ID_REDACTED


def test_redactor_partial_redacts_primary_id_field():
    """The Alma user ``primary_id`` field is partially redacted too."""
    out = redact_sensitive_data({"primary_id": SYNTH_USER_ID})
    assert out["primary_id"] == SYNTH_USER_ID_REDACTED


def test_redactor_short_user_id_is_fully_hidden():
    """An id of three characters or fewer must not reveal the whole
    value — keeping 'last 3' of a 3-char id would leak all of it."""
    out = redact_sensitive_data({"user_id": "12"})
    assert "12" not in out["user_id"]
    assert out["user_id"] == "<...>"


def test_redactor_full_redacts_personal_name_and_contact_fields():
    """Names, emails, addresses and phone numbers have no safe partial
    form, so they are blanked entirely."""
    out = redact_sensitive_data(
        {
            "first_name": "Jane",
            "last_name": "Patron",
            "email_address": "jane.patron@example.org",
            "phone_number": "555-0100",
        }
    )
    blob = str(out)
    assert "Jane" not in blob
    assert "Patron" not in blob
    assert "jane.patron@example.org" not in blob
    assert "555-0100" not in blob


def test_redactor_does_not_over_redact_non_personal_names():
    """Vendor/fund names are not personal data and must stay readable so
    the redactor doesn't gut operationally-useful logs."""
    out = redact_sensitive_data({"vendor_name": "ACME Books", "fund_name": "GEN"})
    assert out["vendor_name"] == "ACME Books"
    assert out["fund_name"] == "GEN"


def test_text_formatter_redacts_user_id_in_message():
    """The user id frequently rides inside the request URL, which lands
    in the log *message* (not a labeled field). It must be redacted
    there too."""
    record = logging.LogRecord(
        name="almapi.api_client",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg=f"API Request: GET almaws/v1/users/{SYNTH_USER_ID}",
        args=(),
        exc_info=None,
    )
    out = TextFormatter(use_colors=False).format(record)
    assert SYNTH_USER_ID not in out, "user id leaked in message. Output:\n" + out
    assert SYNTH_USER_ID_REDACTED in out


def test_text_formatter_redacts_user_id_in_endpoint_field():
    """A user id inside a string field value (e.g. ``endpoint``) is also
    redacted."""
    record = _make_record(
        {"method": "GET", "endpoint": f"almaws/v1/users/{SYNTH_USER_ID}"}
    )
    out = TextFormatter(use_colors=False).format(record)
    assert SYNTH_USER_ID not in out, "user id leaked in endpoint field. Output:\n" + out
    assert SYNTH_USER_ID_REDACTED in out


def test_json_formatter_redacts_user_id_in_message():
    """JSON formatter must redact the user id in the message too."""
    record = logging.LogRecord(
        name="almapi.api_client",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg=f"API Request: GET almaws/v1/users/{SYNTH_USER_ID}",
        args=(),
        exc_info=None,
    )
    out = JSONFormatter().format(record)
    assert SYNTH_USER_ID not in out, "user id leaked in JSON message. Output:\n" + out
    assert SYNTH_USER_ID_REDACTED in out


def test_bib_mms_id_is_not_treated_as_personal():
    """Guard: bibliographic identifiers are not PII and stay fully
    visible, so the user-id redactor must not touch ``bibs/`` paths."""
    bib_endpoint = "almaws/v1/bibs/990000000000000000"
    record = _make_record({"endpoint": bib_endpoint})
    out = TextFormatter(use_colors=False).format(record)
    assert bib_endpoint in out


# --- bodies off by default (issue #142 expansion, 2026-05-25) -------------
# Full request/response bodies are the single largest PII source (a user
# lookup returns the entire patron record). They must NOT be logged unless
# a consumer explicitly opts in via the ``log_bodies`` config flag — the
# always-on redactor is the belt, bodies-off is the braces.

SENTINEL_BODY = {"note_text": "SENTINEL_BODY_VALUE_DO_NOT_LOG"}


def _capturing_body_logger(domain_suffix: str, log_bodies: bool):
    """Build an ``AlmaLogger`` on a private domain with a single
    in-memory capture handler and a controllable ``log_bodies`` setting.
    No console/file handlers so the test leaves no artifacts."""
    cfg = LoggingConfig()
    cfg.output = {"console": False, "file": False}
    cfg.config["log_bodies"] = log_bodies
    alma_logger = AlmaLogger(
        f"test_issue_142_{domain_suffix}", environment="SANDBOX", config=cfg
    )
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(TextFormatter(use_colors=False))
    alma_logger.logger.handlers = [handler]
    alma_logger.logger.setLevel(logging.DEBUG)
    return alma_logger, buf


def test_default_config_disables_body_logging():
    """Out of the box, body logging is off."""
    assert LoggingConfig().get_log_bodies() is False


def test_request_body_not_logged_by_default():
    """``log_request`` must drop the body when bodies are disabled."""
    alma_logger, buf = _capturing_body_logger("req_off", log_bodies=False)
    alma_logger.log_request(
        "POST", "almaws/v1/bibs/990000000000000000", body=SENTINEL_BODY
    )
    assert "SENTINEL_BODY_VALUE_DO_NOT_LOG" not in buf.getvalue()


def test_request_body_logged_when_explicitly_enabled():
    """With ``log_bodies`` on, the body is logged (opt-in works)."""
    alma_logger, buf = _capturing_body_logger("req_on", log_bodies=True)
    alma_logger.log_request(
        "POST", "almaws/v1/bibs/990000000000000000", body=SENTINEL_BODY
    )
    assert "SENTINEL_BODY_VALUE_DO_NOT_LOG" in buf.getvalue()


def test_log_request_body_helper_is_noop_by_default():
    """The dedicated request-body trace helper emits nothing by default."""
    alma_logger, buf = _capturing_body_logger("rbody_off", log_bodies=False)
    alma_logger.log_request_body("POST", "almaws/v1/bibs/x", SENTINEL_BODY)
    assert buf.getvalue() == ""


def test_log_response_body_helper_logs_when_enabled():
    """The response-body trace helper emits when explicitly enabled."""
    alma_logger, buf = _capturing_body_logger("respbody_on", log_bodies=True)
    alma_logger.log_response_body(
        "GET", "almaws/v1/bibs/x", 200, {"k": "SENTINEL_RESP_XYZ"}
    )
    assert "SENTINEL_RESP_XYZ" in buf.getvalue()


# --- safe defaults + one-line opt-out (issue #142 expansion, 2026-05-25) --
# A consumer who configures nothing should get quiet, file-free logging
# they can silence with a single call.


def test_default_domain_levels_are_info():
    """Verbosity is opt-in: no domain ships at DEBUG by default, so a
    bare ``get_logger`` call never dumps request/response detail."""
    cfg = LoggingConfig()
    assert cfg.get_domain_level("api_client") == "INFO"
    assert cfg.get_domain_level("acquisitions") == "INFO"


def test_default_config_disables_file_output():
    """No surprise logfile under the consumer's CWD: file output is
    opt-in."""
    assert LoggingConfig().output.get("file") is False


def test_get_logger_attaches_no_file_handler_by_default():
    """A bare ``get_logger`` must not wire up a rotating file handler
    (which would create ``logs/api_requests/<date>/<domain>.log`` under
    the consumer's working directory)."""
    from almaapitk.alma_logging import get_logger
    from almaapitk.alma_logging.handlers import AlmaRotatingFileHandler

    alma_logger = get_logger("test_issue_142_nofile", environment="SANDBOX")
    file_handlers = [
        h for h in alma_logger.logger.handlers
        if isinstance(h, AlmaRotatingFileHandler)
    ]
    assert file_handlers == []


def test_parent_logger_setlevel_silences_domain_loggers():
    """The whole toolkit can be quieted with one line:
    ``logging.getLogger("almapi").setLevel(logging.WARNING)``. This works
    only if domain loggers leave their level unset and defer to the
    shared ``almapi`` parent."""
    from almaapitk.alma_logging import get_logger

    alma_logger = get_logger("test_issue_142_optout", environment="SANDBOX")
    child = alma_logger.logger
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(TextFormatter(use_colors=False))
    # Replace the framework's console/file handlers with our capture
    # handler, but do NOT touch the child's level — the whole point is
    # that it inherits from the parent.
    child.handlers = [handler]

    parent = logging.getLogger("almapi")
    previous = parent.level
    try:
        parent.setLevel(logging.WARNING)
        alma_logger.info("info noise", endpoint="almaws/v1/bibs/x")
        assert buf.getvalue() == "", (
            "Setting almapi -> WARNING did not silence a domain INFO log; "
            "the child logger is pinning its own level. Output:\n"
            + buf.getvalue()
        )
        alma_logger.warning("audible warning")
        assert "audible warning" in buf.getvalue()
    finally:
        parent.setLevel(previous)
