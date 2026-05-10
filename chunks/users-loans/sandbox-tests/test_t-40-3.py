"""Generated SANDBOX test t-40-3 - Users loans live round-trip with
in-band scan-in cleanup (issue #40). STATE-CHANGING -- operator-
authorized.

Maps to AC #40 facets:
  - ``create_user_loan`` exercised end-to-end against live SANDBOX
    (POST /users/{user_id}/loans) with ``library`` + ``circ_desk`` in
    the loan body and ``item_pid`` on the query string.
  - ``get_user_loan`` round-trips the freshly-created loan and the
    response echoes the captured ``loan_id``.
  - ``renew_user_loan`` exercises the ``op=renew`` query-string variant
    (POST /users/{user_id}/loans/{loan_id}?op=renew with no body).
  - ``BibliographicRecords.scan_in_item`` returns the item via a
    circ-desk scan, completing the loan in-band so net state stays
    clean. The same Alma endpoint that places work-orders also performs
    circulation returns when called with ``circ_desk`` and no
    ``work_order_type``.

Sequence:
  1. ``create_user_loan`` with ``library`` + ``circ_desk`` in
     ``loan_data``.
  2. ``get_user_loan`` to verify the captured ``loan_id``.
  3. ``renew_user_loan`` to exercise ``op=renew``.
  4. ``bibs.scan_in_item`` with ``circ_desk`` to RETURN the item
     (completes the loan).

Cleanup discipline (mandatory ``try/finally``):
  - Happy path scan-in handles the return.
  - ``finally`` retries scan-in if the happy path failed mid-test.
  - If the in-finally scan-in also fails, prints a HUGE manual-cleanup
    banner with ``loan_id``, ``user_id``, ``item_pid`` so the operator
    can clear the leftover loan via the Alma staff UI.

The chunk's loans surface uses ``Users`` for create/get/renew and the
existing ``BibliographicRecords`` domain for the return.

WARNING -- STATE-CHANGING:
   This test creates a real loan on a real SANDBOX user and a real
   SANDBOX item. The happy path returns the item via scan-in, leaving
   net state clean. If any step fails after create succeeds, the
   ``finally`` block retries the scan-in. If that also fails, the
   operator must manually return the item via the Alma staff UI.

Fixtures are loaded at runtime from
``chunks/users-loans/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/users-loans/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.bibs import BibliographicRecords
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_40_3():
    user_id = _TEST_DATA["existing_user_primary_id"]
    item_pid = _TEST_DATA["existing_item_pid"]
    holding_id = _TEST_DATA["existing_holding_id"]
    mms_id = _TEST_DATA["existing_mms_id"]
    library = _TEST_DATA["target_library_code"]
    circ_desk = _TEST_DATA["existing_circ_desk_code"]

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)
    bibs = BibliographicRecords(client)

    print(
        f"\n[t-40-3] live create->renew->return on user {user_id}, "
        f"item {item_pid} at library {library} / circ_desk {circ_desk}"
    )

    loan_id = None
    scan_in_succeeded = False
    try:
        # --- Step 1: create the loan -------------------------------------
        create_response = users.create_user_loan(
            user_id,
            item_pid=item_pid,
            loan_data={
                "circ_desk": {"value": circ_desk},
                "library": {"value": library},
            },
        )
        assert create_response is not None
        assert getattr(create_response, "success", False) is True
        create_data = create_response.data
        assert isinstance(create_data, dict)
        assert "loan_id" in create_data
        loan_id = create_data.get("loan_id")
        assert loan_id, "expected a loan_id in create_user_loan response"
        print(f"[t-40-3] loan created: loan_id={loan_id!r}")

        # --- Step 2: get_user_loan to verify -----------------------------
        get_response = users.get_user_loan(user_id, str(loan_id))
        assert isinstance(get_response, dict)
        echoed_loan_id = get_response.get("loan_id")
        assert str(echoed_loan_id) == str(loan_id), (
            f"get_user_loan loan_id mismatch: expected {loan_id!r}, "
            f"got {echoed_loan_id!r}"
        )

        # --- Step 3: renew -----------------------------------------------
        renew_response = users.renew_user_loan(user_id, str(loan_id))
        assert renew_response is not None
        assert getattr(renew_response, "success", False) is True
        print(f"[t-40-3] loan renewed: loan_id={loan_id!r}")

        # --- Step 4: in-band cleanup -- scan-in returns the item ---------
        scan_in_response = bibs.scan_in_item(
            mms_id=mms_id,
            holding_id=holding_id,
            item_pid=item_pid,
            library=library,
            circ_desk=circ_desk,
        )
        assert scan_in_response is not None
        assert getattr(scan_in_response, "success", False) is True
        scan_in_succeeded = True
        print(
            f"[t-40-3] item returned via scan-in: status="
            f"{scan_in_response.status_code} success={scan_in_response.success}"
        )

    finally:
        # Belt-and-braces: if the happy-path scan-in did not run or
        # failed (e.g. an earlier assertion raised, or the scan-in
        # itself errored), retry once. If it still fails, print a
        # loud manual-cleanup banner so the operator can clear the
        # leftover loan via the Alma staff UI. Never re-raise from
        # finally -- the original test failure (if any) should
        # surface as the test's exit reason.
        if loan_id and not scan_in_succeeded:
            try:
                bibs.scan_in_item(
                    mms_id=mms_id,
                    holding_id=holding_id,
                    item_pid=item_pid,
                    library=library,
                    circ_desk=circ_desk,
                )
                print(
                    "[t-40-3 cleanup] in-finally scan-in returned the item OK"
                )
            except AlmaAPIError as cleanup_err:
                print(
                    f"\n!!! [t-40-3] MANUAL CLEANUP REQUIRED !!!\n"
                    f"!!! loan_id: {loan_id!r}\n"
                    f"!!! user_id: {user_id}\n"
                    f"!!! item_pid: {item_pid}\n"
                    f"!!! reason: {cleanup_err}\n"
                    f"!!! Operator must return the item via the Alma "
                    f"staff UI.\n"
                )
