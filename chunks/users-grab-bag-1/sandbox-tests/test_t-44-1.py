"""Generated SANDBOX test t-44-1 - Users fees read smoke (issue #44).

Maps to AC #44 facets:
  - ``list_user_fees`` exercised against live SANDBOX, returns a
    List[Dict] envelope (per the chunk's audit-corrected signature).
  - ``get_user_fee`` exercised against live SANDBOX when the user has at
    least one fee, returns a Dict[str, Any] containing an ``id`` key.
  - Methods exist on the existing ``Users`` class (importable / bound).

Calls the read-only fee methods shipped in issue #44 against live
SANDBOX. Confirms ``list_user_fees`` returns a list (the SANDBOX user
may have zero fees, in which case the list is empty and that is still a
pass for the list-shape assertion). If the returned list is non-empty,
picks the first fee's id and calls ``get_user_fee`` to confirm the
single-fee GET round-trips and returns a non-empty Dict[str, Any]
containing an ``id`` key.

No state is mutated; all write paths (create / pay_all / pay / waive /
dispute / restore) are deliberately unmappable to live SANDBOX (see
``unmappable[]`` in the recommendation) and are covered by mocked-HTTP
unit tests in ``tests/unit/domains/test_users.py``.

Fixture (``existing_user_primary_id``) is loaded at runtime from
``chunks/users-grab-bag-1/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/users-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_44_1():
    existing_user_primary_id = _TEST_DATA["existing_user_primary_id"]

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)

    # --- list_user_fees -------------------------------------------------
    fees = users.list_user_fees(existing_user_primary_id)
    assert isinstance(fees, list)

    # --- get_user_fee (only when the list is non-empty) -----------------
    if len(fees) > 0:
        first_fee = fees[0]
        assert isinstance(first_fee, dict)
        fee_id = first_fee.get("id")
        if fee_id:
            fee_detail = users.get_user_fee(
                existing_user_primary_id, str(fee_id)
            )
            assert isinstance(fee_detail, dict)
            assert "id" in fee_detail
