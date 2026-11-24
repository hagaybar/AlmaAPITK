"""Issue #256: one personal-data mask, used by every output path.

A fake user record (no real data, R9) goes through each place the library
writes or shows data -- the public mask, logging (toolkit formatters, a
consumer's own handler, Python's last-resort handler), error ``str`` /
``repr`` / tracebacks, object ``repr``s, the Alma Lab CLI and the testing
transport -- and no personal value may appear. The in-memory record must
come out unchanged, so chained calls keep working.
"""
from __future__ import annotations

import copy
import io
import json
import logging
import traceback

import pytest

import almaapitk
from almaapitk import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaResourceNotFoundError,
    AlmaResponse,
    AlmaValidationError,
    redact,
    redact_text,
)
from almaapitk.alma_logging.formatters import JSONFormatter, TextFormatter
from almaapitk.alma_logging.logger import AlmaLogger, MaskingFilter
from tests.unit.lab.conftest import (  # noqa: F401 -- fixtures
    _restore_almapi_log_level,
    lab_client,
)

# --- the fake record -------------------------------------------------------

PRIMARY_ID = "FAKEPID0000123"
BARCODE = "FAKEBC99887766"
FIRST, LAST = "Fakefirstname", "Fakelastname"
EMAIL = "fake.patron@example.org"
PHONE = "+972-3-555-0100"
STREET = "1 Fakestreet Road"
USER_NOTE = "FAKE NOTE patron prefers mornings"
STAFF = "FAKE_STAFF_OPERATOR"
RECEIVING_NOTE = "FAKE RECEIVING NOTE box damaged"
PATRON_COMMENT = "Please send the second edition"

PERSONAL_VALUES = [PRIMARY_ID, BARCODE, FIRST, LAST, EMAIL, PHONE, STREET,
                   USER_NOTE, STAFF, RECEIVING_NOTE]


def fake_user() -> dict:
    return {
        "primary_id": PRIMARY_ID,
        "first_name": FIRST,
        "last_name": LAST,
        "full_name": f"{FIRST} {LAST}",
        "user_group": {"value": "FAKEGROUP", "desc": "Fake group"},
        "expiry_date": "2030-01-01Z",
        "user_identifier": [{
            "id_type": {"value": "BARCODE", "desc": "Barcode"},
            "value": BARCODE,
            "status": "ACTIVE",
        }],
        "contact_info": {
            "email": [{"email_address": EMAIL, "preferred": True,
                       "email_type": [{"value": "personal"}]}],
            "phone": [{"phone_number": PHONE, "preferred": True}],
            "address": [{"line1": STREET, "city": "Faketown",
                         "address_type": [{"value": "home"}]}],
        },
        "user_note": [{
            "note_text": USER_NOTE,
            "note_type": {"value": "OTHER"},
            "popup_note": False,
            "created_by": STAFF,
            "created_date": "2026-01-01Z",
        }],
        "receiving_note": RECEIVING_NOTE,
        "comment": PATRON_COMMENT,
        "mms_id": "990000000000000001",
    }


def assert_clean(text: str) -> None:
    for value in PERSONAL_VALUES:
        assert value not in text, f"{value!r} leaked:\n{text}"


# --- the public mask -------------------------------------------------------

def test_public_api_exports_the_mask():
    assert "redact" in almaapitk.__all__ and "redact_text" in almaapitk.__all__


def test_redact_masks_every_personal_field_and_keeps_the_rest():
    user = fake_user()
    out = redact(user)
    assert_clean(json.dumps(out))
    assert out["primary_id"] == "<...>123"
    assert out["user_identifier"][0]["value"] == "<...>766"
    assert out["user_note"][0]["created_by"] == "<redacted>"
    assert out["user_note"][0]["popup_note"] is False
    assert out["user_note"][0]["note_type"] == {"value": "OTHER"}
    # visible: patron-typed text, codes, dates, record ids
    assert out["comment"] == PATRON_COMMENT
    assert out["user_group"] == {"value": "FAKEGROUP", "desc": "Fake group"}
    assert out["mms_id"] == "990000000000000001"
    assert out["contact_info"]["email"][0]["preferred"] is True


def test_redact_returns_a_copy_and_never_changes_the_record():
    user = fake_user()
    before = copy.deepcopy(user)
    redact(user)
    redact_text(json.dumps(user))
    assert user == before


@pytest.mark.parametrize("text", [
    json.dumps(fake_user()),
    json.dumps(fake_user(), indent=2),
    repr(fake_user()),
    f"<user><primary_id>{PRIMARY_ID}</primary_id><email_address>{EMAIL}"
    f"</email_address><created_by>{STAFF}</created_by></user>",
    f"GET almaws/v1/users/{PRIMARY_ID}/loans failed for {EMAIL}",
    f"User with identifier {BARCODE} of type all_unique was not found",
    f"Creating user: {PRIMARY_ID} (operator={STAFF}, receiving_note={RECEIVING_NOTE})",
])
def test_redact_text_masks_each_text_shape(text):
    assert_clean(redact_text(text))


def test_redact_text_leaves_plain_text_alone():
    text = 'GET almaws/v1/bibs/990000000000000001 -> {"total_record_count": 3}'
    assert redact_text(text) == text
    assert redact_text(None) is None


# --- logging ---------------------------------------------------------------

@pytest.fixture
def fresh_logger():
    name = "test_issue_256"
    logger = AlmaLogger(name)
    py_logger = logger.logger
    saved = list(py_logger.handlers)
    for h in saved:
        py_logger.removeHandler(h)
    yield logger
    for h in list(py_logger.handlers):
        py_logger.removeHandler(h)
    for h in saved:
        py_logger.addHandler(h)


def _log_everything(logger: AlmaLogger, user: dict) -> None:
    logger.info(f"Fetched user {PRIMARY_ID} ({EMAIL})", user=user, endpoint=f"almaws/v1/users/{PRIMARY_ID}")
    try:
        raise AlmaAPIError(f"GET almaws/v1/users/{PRIMARY_ID} failed: {EMAIL}", 400)
    except AlmaAPIError as exc:
        logger.log_error(exc, user_primary_id=PRIMARY_ID)
        logger.exception("lookup failed", user=user)


@pytest.mark.parametrize("formatter", [
    TextFormatter(use_colors=False),
    JSONFormatter(),
    logging.Formatter("%(message)s %(user)s"),  # a consumer's own handler
], ids=["text", "json", "consumer-handler"])
def test_logging_masks_message_fields_and_traceback(fresh_logger, formatter):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(formatter)
    fresh_logger.logger.addHandler(handler)
    user = fake_user()
    before = copy.deepcopy(user)

    _log_everything(fresh_logger, user)

    assert buf.getvalue().strip()
    assert_clean(buf.getvalue())
    assert user == before  # the caller's object is not changed by the filter


def test_logging_last_resort_handler_is_masked(fresh_logger, monkeypatch):
    """No handler at all (console and file off): Python's lastResort prints.

    pytest's logging plugin adds capture handlers to the root logger and
    (pytest 9) to the test's logger; an empty handler list and
    ``propagate=False`` make lastResort the only output whatever the pytest
    version (review finding 5).
    """
    buf = io.StringIO()
    monkeypatch.setattr(logging, "lastResort", logging.StreamHandler(buf))
    monkeypatch.setattr(fresh_logger.logger, "handlers", [])
    monkeypatch.setattr(fresh_logger.logger, "propagate", False)
    fresh_logger.warning(f"user {PRIMARY_ID} has no email, was {EMAIL}")
    assert "has no email" in buf.getvalue()
    assert_clean(buf.getvalue())


def test_masking_filter_is_installed_once(fresh_logger):
    AlmaLogger("test_issue_256")
    assert sum(isinstance(f, MaskingFilter) for f in fresh_logger.logger.filters) == 1


# --- errors ----------------------------------------------------------------

@pytest.mark.parametrize("exc", [
    AlmaAPIError(f"GET almaws/v1/users/{PRIMARY_ID} failed for {EMAIL}", 400),
    AlmaResourceNotFoundError(f"User with identifier {BARCODE} of type all_unique was not found", 404),
    AlmaValidationError(f"Generated email is invalid: {EMAIL}"),
], ids=["base", "subclass", "validation"])
def test_error_str_repr_and_traceback_are_masked(exc):
    raw = exc.args[0]
    assert_clean(str(exc))
    assert_clean(repr(exc))
    try:
        raise exc
    except Exception as caught:  # noqa: BLE001 -- we render whatever was raised
        assert_clean("".join(traceback.format_exception(caught)))
    assert exc.args[0] == raw  # in memory: raw, so code can still use it


class _FakeHTTPResponse:
    """A minimal ``requests.Response`` double for ``_handle_response``."""

    status_code = 404
    headers = {"content-type": "application/json"}
    url = f"https://api-eu.hosted.exlibrisgroup.com/almaws/v1/users/{PRIMARY_ID}"
    text = ""

    def json(self):
        return {"errorsExist": True, "errorList": {"error": [{
            "errorCode": "401861",
            "errorMessage": f"User with identifier {PRIMARY_ID} of type all_unique was not found.",
            "trackingId": "E01-0000000000-FAKE",
        }]}}


def test_error_raised_from_an_alma_response_is_masked(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", "<fake_sandbox_key>")
    client = AlmaAPIClient("SANDBOX")
    with pytest.raises(AlmaAPIError) as info:
        client._handle_response(_FakeHTTPResponse())
    assert_clean(str(info.value))
    assert_clean(repr(info.value))
    assert PRIMARY_ID in info.value.args[0]
    assert info.value.tracking_id == "E01-0000000000-FAKE"


# --- object reprs ----------------------------------------------------------

class _OkResponse:
    status_code = 200
    headers = {"content-type": "application/json"}

    def json(self):
        return fake_user()


def test_response_repr_shows_status_only_and_data_stays_raw():
    response = AlmaResponse(_OkResponse())
    assert repr(response) == "AlmaResponse(status_code=200, success=True)"
    assert response.data == fake_user()  # chained calls get the raw record


def test_client_repr_shows_environment_only(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", "<fake_sandbox_key>")
    client = AlmaAPIClient("SANDBOX")
    assert repr(client) == "AlmaAPIClient(environment='SANDBOX')"


def test_testing_transport_recorded_call_repr_is_masked():
    from almaapitk.testing.transport import RecordedCall

    call = RecordedCall("POST", f"https://h/almaws/v1/users/{PRIMARY_ID}", body=fake_user())
    assert_clean(repr(call))
    assert call.body == fake_user()


def test_lab_dataclass_reprs_are_masked():
    from almaapitk.lab.capture import CapturedRequest
    from almaapitk.lab.evidence import new_record

    captured = CapturedRequest("GET", f"https://h/almaws/v1/users/{PRIMARY_ID}", {},
                               None, 200, response_body=json.dumps(fake_user()))
    record = new_record(operation="Users.get_user", inputs={"user_id": PRIMARY_ID},
                        environment="SANDBOX", base_url_host="h", source="cli")
    record.requests.append(captured)
    record.result = fake_user()
    assert_clean(repr(captured))
    assert_clean(repr(record))
    assert record.result == fake_user()


# --- Alma Lab: screen raw, saved files masked (owner's answer 1) ---------

USER_PATH = "almaws/v1/users/<user_id>"


@pytest.fixture
def lab_cli(lab_client, monkeypatch, tmp_path):
    """``main`` with each call's client on the shared scripted HTTP layer."""
    from tests.unit.lab.conftest import TEST_KEY

    def fresh(env):
        client = AlmaAPIClient(lab_client.environment, api_key=TEST_KEY)
        client._session.request = lab_client.http
        return client

    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", fresh)
    monkeypatch.chdir(tmp_path)
    return lab_client


def _saved_files(folder) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(folder.rglob("*")) if p.is_file())


def test_lab_cli_terminal_output_stays_raw(capsys):
    from almaapitk.lab import cli

    cli._out(json.dumps(fake_user(), indent=2))
    cli._err(f"error: GET almaws/v1/users/{PRIMARY_ID} -> 404 for {EMAIL}")
    out, err = capsys.readouterr()
    assert PRIMARY_ID in out and EMAIL in err  # the owner sees real data on screen
    assert json.loads(out) == fake_user()


def test_lab_evidence_file_is_masked_and_screen_raw(lab_cli, capsys, tmp_path):
    from almaapitk.lab.cli import main

    lab_cli.http.answers = [{"body": fake_user()}]
    code = main(["raw", "GET", f"almaws/v1/users/{PRIMARY_ID}", "--json",
                 "--evidence-dir", str(tmp_path / "ev")])
    assert code == 0
    assert PRIMARY_ID in capsys.readouterr().out  # screen: raw
    saved = _saved_files(tmp_path / "ev")
    assert saved
    assert_clean(saved)  # disk: masked
    assert PATRON_COMMENT in saved


def test_lab_baseline_file_is_masked_and_cannot_be_sent_back(lab_cli, capsys, tmp_path):
    """A masked baseline must never reach Alma: it would overwrite the
    record's personal fields with placeholders."""
    from almaapitk.lab.cli import main

    lab_cli.http.answers = [{"body": fake_user()}]
    base = tmp_path / "current.json"
    assert main(["raw", "PUT", f"almaws/v1/users/{PRIMARY_ID}", "--baseline-out", str(base),
                 "--evidence-dir", str(tmp_path / "ev")]) == 0
    assert_clean(base.read_text(encoding="utf-8"))
    assert_clean(_saved_files(tmp_path / "ev"))
    capsys.readouterr()

    edited = tmp_path / "edited.json"
    edited.write_text(base.read_text(encoding="utf-8").replace("FAKEGROUP", "OTHER"), "utf-8")
    sent_before = len(lab_cli.http.calls)
    code = main(["raw", "PUT", f"almaws/v1/users/{PRIMARY_ID}", "--body-file", str(edited),
                 "--baseline", str(base), "--allow-writes", "--evidence-dir", str(tmp_path / "ev")])
    assert code == 2
    assert "masked" in capsys.readouterr().err
    assert len(lab_cli.http.calls) == sent_before  # nothing was sent


def test_lab_session_refuses_masked_inputs(lab_client, tmp_path, monkeypatch):
    from almaapitk.lab import catalog
    from almaapitk.lab.runner import InputError, Session

    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    session = Session("SANDBOX", evidence_dir=tmp_path)
    op = next(o for o in catalog.discover_operations() if o.qualname == "Users.get_user")
    with pytest.raises(InputError, match="masked"):
        session.run(op, {"user_id": "<...>123"})
    assert lab_client.http.calls == []


# --- field list checked against Ex Libris' schemas (2026-11-24) -----------

@pytest.mark.parametrize("field, value, expected", [
    ("approved_by", "FAKE_STAFF_APPROVER", "<redacted>"),
    ("note_text", "FAKE NOTE", "<redacted>"),
    ("renewal_note", "FAKE RENEWAL NOTE", "<redacted>"),
    ("cancellation_restriction_note", "FAKE CANCEL NOTE", "<redacted>"),
    ("user_primary_id", PRIMARY_ID, "<...>123"),
    ("requester", {"value": PRIMARY_ID, "desc": f"{FIRST} {LAST}"},
     {"value": "<...>123", "desc": "<redacted>"}),
    ("text_email", EMAIL, "<redacted>"),
    ("text_postal_1", STREET, "<redacted>"),
    ("text_postal_2", "FAKE LINE 2", "<redacted>"),
    ("text_postal_3", "FAKE LINE 3", "<redacted>"),
    ("text_postal_4", "FAKE LINE 4", "<redacted>"),
    ("comment", PATRON_COMMENT, PATRON_COMMENT),  # owner: request comment stays
    ("assigned_to", "FAKE_VALUE", "FAKE_VALUE"),  # not in Alma's schemas: dropped
])
def test_schema_checked_fields(field, value, expected):
    assert redact({field: value}) == {field: expected}


def test_schema_checked_fields_are_named_in_the_list():
    from almaapitk import redaction

    assert "assigned_to" not in redaction.STAFF_NAME_FIELDS
    assert "approved_by" in redaction.STAFF_NAME_FIELDS
    assert {"note_text", "renewal_note", "cancellation_restriction_note"} <= redaction.NOTE_FIELDS
    assert {"text_email", "text_postal_1", "text_postal_2", "text_postal_3",
            "text_postal_4"} <= redaction.CONTACT_FIELDS
    assert {"user_primary_id", "requester"} <= set(redaction.USER_ID_PATTERNS)


# --- review finding 3: no over-masking --------------------------------------

@pytest.mark.parametrize("text", [
    "Bib with identifier 990000000000000001 was not found",
    "Processed users: 1500",
    "Requester 2024-11-01 cancelled",
    "Requesters: 1500",
])
def test_free_text_counts_dates_and_record_identifiers_stay_visible(text):
    assert redact_text(text) == text


def test_free_text_user_ids_still_masked():
    assert redact_text("user 123456789 not found") == "user <...>789 not found"
    assert redact_text(f"Requester {PRIMARY_ID}") == "Requester <...>123"
    assert_clean(redact_text(f"User with identifier {BARCODE} of type all_unique was not found"))


def test_standard_number_identifier_stays_visible():
    issn = {"id_type": {"value": "ISSN", "desc": "ISSN"}, "value": "0000-0019"}
    assert redact(issn) == issn
    assert redact_text(repr(issn)) == repr(issn)
    # a user identifier met on its own is still masked
    alone = {"id_type": {"value": "BARCODE"}, "value": BARCODE, "segment_type": "Internal"}
    assert redact(alone)["value"] == "<...>766"
    assert_clean(redact_text(repr(alone)))


@pytest.mark.parametrize("field", ["ip_address", "email_template", "email_sent",
                                   "address_type"])
def test_fields_merely_containing_address_or_email_stay_visible(field):
    assert redact({field: "VISIBLE_VALUE"}) == {field: "VISIBLE_VALUE"}


@pytest.mark.parametrize("field", ["email", "email_address", "address", "preferred_email"])
def test_contact_fields_by_exact_name_are_masked(field):
    assert redact({field: "FAKE CONTACT"}) == {field: "<redacted>"}


# --- review finding 1: chained causes in tracebacks -----------------------

def _connection_error():
    import requests
    import urllib3

    try:
        raise urllib3.exceptions.MaxRetryError(None, f"/almaws/v1/users/{PRIMARY_ID}", None)
    except urllib3.exceptions.MaxRetryError as inner:
        try:  # as requests does: raised while handling urllib3's error
            raise requests.exceptions.ConnectionError(inner)
        except requests.exceptions.ConnectionError as outer:
            return outer


def _raised_by_client(monkeypatch, error):
    monkeypatch.setenv("ALMA_SB_API_KEY", "<fake_sandbox_key>")
    client = AlmaAPIClient("SANDBOX")

    def fail(*args, **kwargs):
        raise error

    client._session.request = fail
    with pytest.raises(Exception) as info:
        client.get(f"almaws/v1/users/{PRIMARY_ID}")
    return info.value


def _default_traceback(exc) -> str:
    """What the default excepthook / ``logger.exception`` of a consumer print."""
    return "".join(traceback.format_exception(exc))


def test_chained_retry_error_cause_is_masked(monkeypatch):
    import requests

    from almaapitk import AlmaServerError

    exc = _raised_by_client(monkeypatch, requests.exceptions.RetryError(
        f"Max retries exceeded with url: /almaws/v1/users/{PRIMARY_ID}"))
    assert isinstance(exc, AlmaServerError)
    text = _default_traceback(exc)
    assert "direct cause" in text and "RetryError" in text  # still useful
    assert_clean(text)
    assert isinstance(exc.__cause__, requests.exceptions.RetryError)


def test_chained_timeout_cause_is_masked(monkeypatch):
    import requests

    from almaapitk import AlmaTimeoutError

    exc = _raised_by_client(monkeypatch, requests.exceptions.ConnectTimeout(
        f"timed out: /almaws/v1/users/{PRIMARY_ID}"))
    assert isinstance(exc, AlmaTimeoutError)
    text = _default_traceback(exc)
    assert "ConnectTimeout" in text
    assert_clean(text)


def test_reraised_connection_error_keeps_its_type_and_is_masked(monkeypatch):
    import requests

    original = _connection_error()
    exc = _raised_by_client(monkeypatch, original)
    assert isinstance(exc, requests.exceptions.ConnectionError)  # contract kept
    text = _default_traceback(exc)
    assert "MaxRetryError" in text and "<...>123" in text
    assert_clean(text)
    assert PRIMARY_ID in str(original)  # the original object is unchanged


# --- review finding 4: a malformed log call never crashes the job ---------

def test_malformed_percent_log_call_does_not_raise(fresh_logger, capsys, monkeypatch):
    """Python's normal behaviour: "--- Logging error ---" on stderr, the job
    goes on. Only our handler is attached: pytest's capture handlers re-raise
    logging errors on purpose."""
    buf = io.StringIO()
    monkeypatch.setattr(fresh_logger.logger, "handlers", [logging.StreamHandler(buf)])
    monkeypatch.setattr(fresh_logger.logger, "propagate", False)
    fresh_logger.logger.error("GET %s failed: %s", f"almaws/v1/users/{PRIMARY_ID}")  # no exception
    err = capsys.readouterr().err
    assert "Logging error" in err
    assert_clean(err + buf.getvalue())


def test_masking_filter_passes_a_malformed_record_through_masked():
    record = logging.LogRecord("almapi.x", logging.INFO, __file__, 1,
                               "GET %s for %s: %d loans", (f"almaws/v1/users/{PRIMARY_ID}", EMAIL), None)
    assert MaskingFilter().filter(record) is True  # no exception
    assert record.args == ("almaws/v1/users/<...>123", "<redacted>")  # masked one by one
    assert record.msg == "GET %s for %s: %d loans"  # left unrendered


def test_malformed_call_on_citation_metadata_logger_does_not_raise(capsys, monkeypatch):
    from almaapitk.utils import citation_metadata

    monkeypatch.setattr(citation_metadata.logger, "handlers", [])
    monkeypatch.setattr(citation_metadata.logger, "propagate", False)
    monkeypatch.setattr(logging, "lastResort", logging.StreamHandler())
    citation_metadata.logger.warning("bad %d", "not-a-number")  # no exception
    assert "Logging error" in capsys.readouterr().err
