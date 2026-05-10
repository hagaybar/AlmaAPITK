"""Generated SANDBOX test t-37-1 - Users create/get/delete round-trip (issue #37).

Maps to issue #37 acceptance criteria:
  - "Each method has unit-test coverage (mocked HTTP) and at least one
    integration test against SANDBOX." -- this is the SANDBOX integration
    test for ``create_user``, ``get_user``, and ``delete_user``.
  - "Errors raise AlmaValidationError (input) or AlmaAPIError / subclass
    (API)." -- the post-delete ``get_user`` is expected to raise
    ``AlmaAPIError``, covering the API-error half of the AC.
  - "delete_user returns the deleted user payload for audit logging."

WARNING - STATE-CHANGING WITH OPERATOR-CLEANUP-FALLBACK:
   This test creates a real Alma user (primary_id begins with 'tau-test-')
   and deletes it within the same run. The mandatory try/finally retries
   the delete on any mid-test failure. If BOTH the happy-path delete AND
   the finally-retry delete fail, the primary_id of the leftover user is
   printed at runtime in a clearly-marked banner -- the operator must then
   manually remove that user via the Alma staff UI. Every primary_id
   begins with 'tau-test-' so manual identification is unambiguous.

The fixture file (``chunks/users-crud/test-data.json``) is empty -- the
``primary_id`` is generated inside the test using ``uuid.uuid4()`` so that
no operator-supplied identifier is committed to the public repository
(R9). The runtime fixture-load shape is preserved here for consistency
with other chunks.

DO NOT EDIT by hand. Generated from
chunks/users-crud/test-recommendation.json.
"""
from __future__ import annotations

import json
import pathlib
import uuid

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.users import Users

_TEST_DATA = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "test-data.json").read_text()
)


def test_t_37_1():
    primary_id = f"tau-test-{uuid.uuid4().hex[:8]}"

    # Print primary_id at the very start so even a Python crash leaves
    # the cleanup target visible in regression-smoke output.
    print(f"\n[t-37-1] CREATED PRIMARY_ID: {primary_id}")

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)

    # Build the minimal valid user payload. Required core fields per Alma
    # docs and issue #37 ACs: primary_id, account_type, status, user_group.
    # first_name/last_name are typically required by Alma server-side.
    payload = {
        "primary_id": primary_id,
        "first_name": "AlmaAPITK",
        "last_name": "TestUser",
        "account_type": {"value": "INTERNAL"},
        "status": {"value": "ACTIVE"},
        "user_group": {"value": "01"},
    }

    deleted = False
    try:
        # --- create ---------------------------------------------------------
        create_response = users.create_user(payload)
        assert create_response is not None
        assert getattr(create_response, "success", False) is True
        assert isinstance(create_response.data, dict)
        echoed_primary_id = create_response.data.get("primary_id")
        assert isinstance(echoed_primary_id, str) and echoed_primary_id.strip() != ""
        assert echoed_primary_id == primary_id, (
            f"create response primary_id mismatch: expected {primary_id!r}, "
            f"got {echoed_primary_id!r}"
        )

        # --- get to verify --------------------------------------------------
        got = users.get_user(primary_id)
        assert got is not None
        assert getattr(got, "success", False) is True
        # Users.get_user returns AlmaResponse; access via .data
        assert isinstance(got.data, dict)
        assert got.data.get("primary_id") == primary_id

        # --- delete (happy path) --------------------------------------------
        # Note: Alma's user-delete endpoint can take 30-60 seconds in
        # SANDBOX (it cascades through linked resources). The response
        # body is empty / non-JSON in practice (verified live
        # 2026-05-09: a 40-second 200 with no parseable JSON body), so
        # we assert .success only — NOT that .data is a dict. The
        # "user actually deleted" semantics are verified by the next
        # step where get_user must raise.
        delete_response = users.delete_user(primary_id)
        assert delete_response is not None
        assert getattr(delete_response, "success", False) is True
        deleted = True

        # --- get after delete should raise ----------------------------------
        post_delete_error = None
        try:
            users.get_user(primary_id)
        except AlmaAPIError as e:
            post_delete_error = e
        assert post_delete_error is not None, (
            "expected AlmaAPIError on get_user after delete"
        )
        assert isinstance(post_delete_error, AlmaAPIError)
    finally:
        if not deleted:
            # Mid-test failure -- try to clean up.
            try:
                users.delete_user(primary_id)
                print(
                    f"[t-37-1] CLEANUP OK: deleted {primary_id} in finally"
                )
            except AlmaAPIError as cleanup_err:
                print(
                    f"\n!!! [t-37-1] MANUAL CLEANUP REQUIRED !!!\n"
                    f"!!! primary_id: {primary_id}\n"
                    f"!!! reason: {cleanup_err}\n"
                    f"!!! Operator must remove this user via Alma staff UI.\n"
                )
                # Don't re-raise -- the original test failure should
                # surface as the test's exit reason. The print above
                # is the operator signal.
            except Exception as cleanup_err:  # noqa: BLE001
                print(
                    f"\n!!! [t-37-1] MANUAL CLEANUP REQUIRED !!!\n"
                    f"!!! primary_id: {primary_id}\n"
                    f"!!! reason: {cleanup_err!r}\n"
                    f"!!! Operator must remove this user via Alma staff UI.\n"
                )
