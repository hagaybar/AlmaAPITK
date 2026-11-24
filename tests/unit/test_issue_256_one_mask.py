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
    """No handler at all (console and file off): Python's lastResort prints."""
    buf = io.StringIO()
    monkeypatch.setattr(logging, "lastResort", logging.StreamHandler(buf))
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


# --- lab CLI terminal output ----------------------------------------------

def test_lab_cli_terminal_output_is_masked(capsys):
    from almaapitk.lab import cli

    cli._out(json.dumps(fake_user(), indent=2))
    cli._err(f"error: GET almaws/v1/users/{PRIMARY_ID} -> 404 for {EMAIL}")
    out, err = capsys.readouterr()
    assert_clean(out)
    assert_clean(err)
    assert json.loads(out)["comment"] == PATRON_COMMENT  # still valid JSON
