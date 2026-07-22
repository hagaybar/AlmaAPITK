"""t-194-1: network-free smoke — opt-in soft validation (issue #194 opt. 2).

Proves the validate=True pre-flight check on Users.create_user_rs_request
fires BEFORE any HTTP request in the shipped build: a wrong-table format
code ('P', the purchase-request code from the issue's reproduction)
raises AlmaValidationError NAMING the field; same for
pickup_location_type and citation_type. Also pins: the deliberate
permissiveness on citation_type (BK/CR/BOOK/JOURNAL all pass); both
encodings accepted ({'value': ...} wrapper and bare string); non-string
values skipped rather than rejected; only the three code-table fields
inspected; validate keyword-only defaulting False; and the docstring
cheat sheet (issue #194 option 3).

The user id used is the literal placeholder '<user_primary_id>' which
does not exist in SANDBOX — deliberate: if validation ever FAILED to
short-circuit, the leaked network request would surface as an
AlmaAPIError (not caught below) and the test would fail loudly. That is
what makes 'before the network call' observable without a fixture.

No SANDBOX state is read or mutated. The pass-direction assertions call
the module-level pure helper _validate_rs_borrowing_codes directly,
because driving them through the public method with a valid body would
issue a real POST.

R9: only synthetic placeholder values appear below; no operator-supplied
fixture values are needed or used.
"""

from __future__ import annotations

import inspect
import json
import os
import pathlib

import pytest

# Fixtures are loaded at RUNTIME from the gitignored test-data.json —
# never inlined at generation time (R9). This test is fixture-free
# (deliberately, per its scope); the loader is tolerant so the smoke
# stays runnable when the operator-filled file is absent.
_TEST_DATA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
)
_TEST_DATA = (
    json.loads(_TEST_DATA_PATH.read_text()) if _TEST_DATA_PATH.exists() else {}
)

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users, _validate_rs_borrowing_codes

TEST_NAME = "t-194-1"


def test_t_194_1() -> None:
    if "ALMA_SB_API_KEY" not in os.environ:
        pytest.skip("ALMA_SB_API_KEY not set (needed to construct the client)")

    # Constructing the client performs no HTTP; SANDBOX only, never PROD.
    client = AlmaAPIClient("SANDBOX")
    users = Users(client)

    base_body = {
        "owner": "<RS_LIB>",
        "format": {"value": "PHYSICAL"},
        "citation_type": {"value": "BOOK"},
        "title": "AlmaAPITK chunk-test validation probe (issue 194)",
        "pickup_location_type": "LIBRARY",
        "pickup_location": {"value": "<PICKUP_LIB>"},
        "agree_to_copyright_terms": True,
    }

    # --- wrong-table format code: the issue's reproduction case --------
    format_error = None
    try:
        users.create_user_rs_request(
            "<user_primary_id>",
            {**base_body, "format": {"value": "P"}},
            validate=True,
        )
    except AlmaValidationError as e:
        format_error = str(e)

    # --- wrong pickup_location_type ------------------------------------
    pickup_type_error = None
    try:
        users.create_user_rs_request(
            "<user_primary_id>",
            {**base_body, "pickup_location_type": "BRANCH"},
            validate=True,
        )
    except AlmaValidationError as e:
        pickup_type_error = str(e)

    # --- wrong citation_type -------------------------------------------
    citation_error = None
    try:
        users.create_user_rs_request(
            "<user_primary_id>",
            {**base_body, "citation_type": {"value": "NOT_A_CODE"}},
            validate=True,
        )
    except AlmaValidationError as e:
        citation_error = str(e)

    # An AlmaValidationError (not an AlmaAPIError) proves the check ran
    # before any HTTP request left the process.
    assert format_error is not None
    assert "format" in format_error and "'P'" in format_error
    assert "PHYSICAL" in format_error and "DIGITAL" in format_error
    assert pickup_type_error is not None
    assert "pickup_location_type" in pickup_type_error
    assert citation_error is not None
    assert "citation_type" in citation_error

    # --- deliberate permissiveness on citation_type --------------------
    permissive_ok = True
    for code in ("BK", "CR", "BOOK", "JOURNAL"):
        try:
            _validate_rs_borrowing_codes(
                {
                    "format": {"value": "DIGITAL"},
                    "citation_type": {"value": code},
                    "pickup_location_type": "LIBRARY",
                }
            )
        except AlmaValidationError:
            permissive_ok = False
    assert permissive_ok is True

    # --- both encodings understood (wrapper and bare string) -----------
    bare_string_ok = True
    try:
        _validate_rs_borrowing_codes({"format": "DIGITAL", "citation_type": "BK"})
    except AlmaValidationError:
        bare_string_ok = False

    bare_string_rejects_bad_code = False
    try:
        _validate_rs_borrowing_codes({"format": "P"})
    except AlmaValidationError:
        bare_string_rejects_bad_code = True

    assert bare_string_ok is True
    assert bare_string_rejects_bad_code is True

    # --- non-string values are skipped, not rejected -------------------
    skip_nonstring_ok = True
    try:
        _validate_rs_borrowing_codes({"format": {"value": {"nested": "object"}}})
    except AlmaValidationError:
        skip_nonstring_ok = False
    assert skip_nonstring_ok is True

    # --- only the three code-table fields are inspected ----------------
    unchecked_fields_ok = True
    try:
        _validate_rs_borrowing_codes(
            {"owner": "ANYTHING", "title": "anything at all"}
        )
    except AlmaValidationError:
        unchecked_fields_ok = False
    assert unchecked_fields_ok is True

    # --- validate is keyword-only, off by default ----------------------
    sig = inspect.signature(Users.create_user_rs_request)
    validate_default_off = (
        sig.parameters["validate"].default is False
        and sig.parameters["validate"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    assert validate_default_off is True

    # --- docstring cheat sheet (issue #194 option 3) -------------------
    doc = Users.create_user_rs_request.__doc__ or ""
    cheatsheet_ok = (
        "PHYSICAL" in doc
        and "DIGITAL" in doc
        and "purchase" in doc.lower()
        and "lending" in doc.lower()
    )
    assert cheatsheet_ok is True

    print(
        f"[{TEST_NAME}] format_error_raised={format_error is not None} "
        f"pickup_type_error_raised={pickup_type_error is not None} "
        f"citation_error_raised={citation_error is not None} "
        f"validate_default_off={validate_default_off}"
    )
