"""t-197-2: operator-authorized live SANDBOX round-trip (issue #197).

The one genuinely live-worthy check for #197: a body produced entirely by
build_user_rs_request is ACCEPTED BY ALMA on a real create. Sequence:
build -> create -> get (confirm request_id round-trips). Code values are
the empirically-passing SANDBOX values from the previous chunk's live
test (format PHYSICAL, citation_type BOOK) so a failure here points at
the builder's SHAPE, not at a code-table guess. This also supplies the
positive half of issue #194's reproduction and the 'no behavior change
to valid calls' evidence: a valid call must succeed with no
'[almaapitk hint:' anywhere.

OPERATOR OVERRIDE (this run only): the created resource-sharing request
is deliberately NOT cancelled or deleted — the operator wants to inspect
it in Alma SANDBOX afterwards. No cleanup code exists in this file; the
DELETE endpoint is never called. After a successful create, the created
request is GET-verified and its id is printed to stdout as
'LEFT-IN-PLACE request_id=<id>'.

Alma's echo of external_id on GET is recorded for information only and
is NOT a pass criterion.

R9: fixtures (user id, library codes) are loaded at RUNTIME from the
gitignored test-data.json — never inlined into this committed file, and
never printed by this test's own output.
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
        "the live SANDBOX round-trip",
        allow_module_level=True,
    )
_TEST_DATA = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent
     / "test-data.json").read_text()
)

from almaapitk import AlmaAPIClient, build_user_rs_request
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.users import Users

TEST_NAME = "t-197-2"
_REQUIRED_KEYS = (
    "existing_user_primary_id",
    "rs_library_code",
    "pickup_library_code",
)


def _usable(key: str) -> bool:
    value = str(_TEST_DATA.get(key, "") or "").strip()
    return bool(value) and not (value.startswith("<") and value.endswith(">"))


def test_t_197_2(capsys) -> None:
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

    # --- BUILD ----------------------------------------------------------
    built_body = build_user_rs_request(
        owner=rs_library_code,
        format="PHYSICAL",
        citation_type="BOOK",
        title="AlmaAPITK chunk-test RS request (issue 197 builder)",
        author="AlmaAPITK",
        pickup_location=pickup_library_code,
        pickup_location_type="LIBRARY",
        agree_to_copyright_terms=True,
        external_id="almaapitk-chunk-test-197",
    )
    # Print structure only (keys / bools / synthetic codes) — the owner and
    # pickup_location VALUES are operator fixtures and are never printed.
    print(
        "[%s] built body: keys=%s owner_is_plain=%s format=%s "
        "pickup_location_type=%s"
        % (
            TEST_NAME,
            sorted(built_body),
            isinstance(built_body["owner"], str),
            built_body["format"],
            built_body["pickup_location_type"],
        )
    )

    # --- CREATE ---------------------------------------------------------
    raised_error: AlmaAPIError | None = None
    create_response = None
    try:
        create_response = users.create_user_rs_request(user_id, built_body)
    except AlmaAPIError as e:
        raised_error = e

    # R9: on failure report only the exception class and numeric Alma code,
    # never the full message (it may embed fixture values).
    assert raised_error is None, (
        "create raised %s (alma_code=%s) — Alma rejected a builder-produced "
        "body; see the detail log under sandbox-test-output/ for the full "
        "error" % (
            type(raised_error).__name__,
            getattr(raised_error, "alma_code", None),
        )
    )
    assert create_response is not None
    assert getattr(create_response, "success", False) is True

    create_data = getattr(create_response, "data", None)
    request_id = None
    if isinstance(create_data, dict):
        request_id = create_data.get("request_id") or create_data.get("id")
    print(f"[{TEST_NAME}] RS request created: request_id={request_id!r}")
    assert isinstance(create_data, dict)
    assert request_id is not None

    try:
        # --- GET (round-trip the request_id) ----------------------------
        get_response = users.get_user_rs_request(user_id, str(request_id))
        get_request_id_echo = None
        external_id_echo = None
        if isinstance(get_response, dict):
            get_request_id_echo = (
                get_response.get("request_id") or get_response.get("id")
            )
            external_id_echo = get_response.get("external_id")
        print(
            f"[{TEST_NAME}] external_id echoed back by Alma: "
            f"{external_id_echo!r} (informational only)"
        )
        assert isinstance(get_response, dict)
        assert str(get_request_id_echo) == str(request_id)

        # --- no-hint check on a valid call (issue #194 evidence) --------
        captured = capsys.readouterr()
        combined_output = captured.out + captured.err
        # Re-emit so the runner still sees the banners after readouterr().
        print(combined_output, end="")
        assert "[almaapitk hint:" not in combined_output
    finally:
        # OPERATOR OVERRIDE (this run only): do NOT cancel/delete the
        # created request. Leave it for inspection in Alma SANDBOX and
        # print the marker line directly to the terminal (bypassing
        # capture) so the operator always sees it.
        with capsys.disabled():
            print(f"LEFT-IN-PLACE request_id={request_id}")

    print(f"[{TEST_NAME}] done: create accepted, round-trip verified")
