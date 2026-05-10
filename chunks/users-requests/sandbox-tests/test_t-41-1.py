"""Generated SANDBOX test t-41-1 - Users requests read smoke (issue #41).

Maps to AC #41 facets:
  - ``list_user_requests`` exercised against live SANDBOX, returns a
    List[Dict] envelope (Alma's ``user_request`` wrapper unwrapped per
    the chunk's audit-corrected signature).
  - ``get_user_request`` exercised against live SANDBOX when the user
    has at least one request, returns a non-empty Dict[str, Any].
  - Methods exist on the existing ``Users`` class (importable / bound).

Calls the read-only request methods shipped in issue #41 against live
SANDBOX. Confirms ``list_user_requests`` returns a list and, if the
list is non-empty, that ``get_user_request`` round-trips the first
request's ``request_id`` and returns a non-empty Dict[str, Any]. If
the list is empty (the SANDBOX user has no active requests), the
get-step is skipped and only the list-shape assertion is verified --
the test is still considered pass because the list endpoint itself
responded correctly.

No state is mutated. The create/get/cancel live cycle is exercised
by t-41-3.

Fixture (``existing_user_primary_id``) is loaded at runtime from
``chunks/users-requests/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/users-requests/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_41_1():
    existing_user_primary_id = _TEST_DATA["existing_user_primary_id"]

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)

    # --- list_user_requests --------------------------------------------
    requests_list = users.list_user_requests(existing_user_primary_id)
    assert isinstance(requests_list, list)

    # --- get_user_request (only when the list is non-empty) ------------
    first_request = None
    request_detail = None
    if len(requests_list) > 0:
        first_request = requests_list[0]
        request_id = (
            first_request.get("request_id")
            if isinstance(first_request, dict)
            else None
        )
        if request_id:
            request_detail = users.get_user_request(
                existing_user_primary_id, str(request_id)
            )

    # --- pass criteria --------------------------------------------------
    assert isinstance(requests_list, list)
    assert first_request is None or (
        isinstance(request_detail, dict) and len(request_detail) > 0
    )
