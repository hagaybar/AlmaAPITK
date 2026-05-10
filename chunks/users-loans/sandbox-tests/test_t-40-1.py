"""Generated SANDBOX test t-40-1 - Users loans read smoke (issue #40).

Maps to AC #40 facets:
  - ``list_user_loans`` exercised against live SANDBOX, returns a
    List[Dict] envelope (Alma's ``item_loan`` wrapper unwrapped per the
    chunk's audit-corrected signature).
  - ``get_user_loan`` exercised against live SANDBOX when the user has
    at least one loan, returns a Dict[str, Any] containing a ``loan_id``
    key.
  - Methods exist on the existing ``Users`` class (importable / bound).

Calls the read-only loan methods shipped in issue #40 against live
SANDBOX. Confirms ``list_user_loans`` returns a list and, if the list
is non-empty, that ``get_user_loan`` round-trips the first loan's
``loan_id`` and returns a non-empty Dict[str, Any] containing a
``loan_id`` key. If the list is empty (the SANDBOX user has no active
loans), the get-step is skipped and only the list-shape assertion is
verified -- the test is still considered pass because the list endpoint
itself responded correctly.

No state is mutated. The create/renew/return live cycle is exercised
by t-40-3.

Fixture (``existing_user_primary_id``) is loaded at runtime from
``chunks/users-loans/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/users-loans/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_40_1():
    existing_user_primary_id = _TEST_DATA["existing_user_primary_id"]

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)

    # --- list_user_loans ------------------------------------------------
    loans = users.list_user_loans(existing_user_primary_id)
    assert isinstance(loans, list)

    # --- get_user_loan (only when the list is non-empty) ----------------
    if len(loans) > 0:
        first_loan = loans[0]
        assert isinstance(first_loan, dict)
        loan_id = first_loan.get("loan_id")
        if loan_id:
            loan_detail = users.get_user_loan(
                existing_user_primary_id, str(loan_id)
            )
            assert isinstance(loan_detail, dict)
            assert "loan_id" in loan_detail
