"""t-194-2: operator-authorized live reproduction of issue #194.

Deliberately POSTs a wrong-code-table value to the RS-borrowing endpoint
and confirms the client turns Alma's dead-end error into an actionable
one. The payload is the known-good body from the previous chunk's
passing live test EXCEPT format, set to the purchase-request code 'P'
(the issue's exact reproduction). validate= is deliberately NOT passed:
that proves validation is off by default (the request reaches Alma at
all) and lets the error-hint path run. Expected: HTTP 400, AlmaAPIError,
message carrying an appended '[almaapitk hint: ...]' naming
format/PHYSICAL/DIGITAL and pointing at build_user_rs_request and
validate=True.

IF THE REPRODUCTION NO LONGER REPRODUCES (Alma fixed its message
template upstream), mangled_shape will be False and the client will —
correctly, by design — append no hint. That is an upstream environment
change, not a chunk defect: record it in the results; the hint logic is
pinned unconditionally by t-194-3 and tests/unit/regressions/.

OPERATOR OVERRIDE (this run only): no cleanup/cancel/DELETE code exists
in this file. The create is EXPECTED to be rejected; should Alma
unexpectedly ACCEPT it, the request is left in place for operator
inspection, GET-verified, and its id printed as
'LEFT-IN-PLACE request_id=<id>'.

R9: fixtures are loaded at RUNTIME from the gitignored test-data.json —
never inlined into this committed file. Assertions are on booleans
computed from the error message, so a failure never dumps the raw Alma
message (which could embed fixture values) into pytest output.
"""

from __future__ import annotations

import json
import pathlib

import pytest

_TEST_DATA_FILE = (
    pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
)
if not _TEST_DATA_FILE.exists():
    pytest.skip(
        "test-data.json missing (operator-filled, gitignored) — cannot run "
        "the live wrong-code probe",
        allow_module_level=True,
    )
_TEST_DATA = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent
     / "test-data.json").read_text()
)

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import (
    AlmaAPIError,
    AlmaInvalidPolModeError,
)
from almaapitk.domains.users import Users

TEST_NAME = "t-194-2"
_REQUIRED_KEYS = (
    "existing_user_primary_id",
    "rs_library_code",
    "pickup_library_code",
)


def _usable(key: str) -> bool:
    value = str(_TEST_DATA.get(key, "") or "").strip()
    return bool(value) and not (value.startswith("<") and value.endswith(">"))


def test_t_194_2(capsys) -> None:
    missing = [key for key in _REQUIRED_KEYS if not _usable(key)]
    if missing:
        # Key NAMES only — never values.
        pytest.skip(f"test-data.json lacks usable values for: {missing}")

    user_id = _TEST_DATA["existing_user_primary_id"]
    rs_library_code = _TEST_DATA["rs_library_code"]
    pickup_library_code = _TEST_DATA["pickup_library_code"]

    print(f"[{TEST_NAME}] starting (SANDBOX)")
    client = AlmaAPIClient("SANDBOX")  # reads ALMA_SB_API_KEY — never PROD
    users = Users(client)

    raised: AlmaAPIError | None = None
    unexpected_response = None
    unexpected_request_id = None

    wrong_code_body = {
        "owner": rs_library_code,
        "format": {"value": "P"},
        "citation_type": {"value": "BOOK"},
        "title": "AlmaAPITK chunk-test wrong-code probe (issue 194)",
        "author": "AlmaAPITK",
        "pickup_location_type": "LIBRARY",
        "pickup_location": {"value": pickup_library_code},
        "agree_to_copyright_terms": True,
    }

    print(
        f"[{TEST_NAME}] posting a deliberately wrong format code "
        "(P = purchase-request table) with validate= NOT passed, to provoke "
        "Alma mangled error"
    )
    try:
        unexpected_response = users.create_user_rs_request(
            user_id, wrong_code_body
        )
        _data = getattr(unexpected_response, "data", None)
        if isinstance(_data, dict):
            unexpected_request_id = _data.get("request_id") or _data.get("id")
    except AlmaAPIError as e:
        raised = e

    message = str(raised) if raised is not None else ""
    mangled_shape = "invalid field value" in message.lower()
    hint_present = "[almaapitk hint:" in message
    hint_names_format = "'format'" in message and "PHYSICAL/DIGITAL" in message
    hint_points_at_helpers = (
        "build_user_rs_request" in message and "validate=True" in message
    )
    not_a_pol_error = not isinstance(raised, AlmaInvalidPolModeError)
    raw_dict_reached_alma = raised is not None or unexpected_response is not None
    print(
        f"[{TEST_NAME}] raised="
        f"{type(raised).__name__ if raised is not None else None} "
        f"mangled_shape={mangled_shape} hint_present={hint_present} "
        f"unexpected_request_id={unexpected_request_id!r}"
    )

    # OPERATOR OVERRIDE (this run only): if Alma unexpectedly ACCEPTED the
    # wrong-code body, do NOT cancel it — GET-verify it exists, leave it in
    # place for operator inspection, and print the marker line directly to
    # the terminal (bypassing capture) so the operator always sees it.
    if unexpected_request_id is not None:
        exists = False
        try:
            echo = users.get_user_rs_request(user_id, str(unexpected_request_id))
            exists = isinstance(echo, dict) and bool(echo)
        except AlmaAPIError:
            exists = False
        with capsys.disabled():
            print(f"LEFT-IN-PLACE request_id={unexpected_request_id}")
        print(
            f"[{TEST_NAME}] unexpectedly-created request verified "
            f"exists={exists}; left in place per operator override"
        )

    # --- pass criteria --------------------------------------------------
    assert raised is not None and isinstance(raised, AlmaAPIError), (
        "Alma did not reject the wrong-code body"
    )
    assert unexpected_response is None and unexpected_request_id is None, (
        "a resource-sharing request was unexpectedly created (left in place "
        "per operator override — see the LEFT-IN-PLACE marker above)"
    )
    assert raw_dict_reached_alma is True
    assert mangled_shape is True, (
        "Alma no longer returns the mangled 'Invalid field value' shape — "
        "likely an upstream Alma fix, not a chunk defect; see the scope note "
        "and record in results (hint criteria then not-applicable)"
    )
    assert hint_present is True, (
        "no '[almaapitk hint:' suffix was appended to Alma's message"
    )
    assert hint_names_format is True, (
        "the hint does not name 'format' with its PHYSICAL/DIGITAL values"
    )
    assert hint_points_at_helpers is True, (
        "the hint does not point at build_user_rs_request / validate=True"
    )
    assert not_a_pol_error is True, (
        "the acquisitions meaning of a colliding error code leaked onto the "
        "RS surface (AlmaInvalidPolModeError)"
    )
    assert hasattr(raised, "tracking_id") is True, (
        "exception attributes changed — the hint must be message-only"
    )
    print(f"[{TEST_NAME}] done: rejection surfaced with actionable hint")
