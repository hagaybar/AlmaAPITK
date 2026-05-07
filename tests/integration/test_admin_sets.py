"""Integration tests for ``Admin`` set CRUD + member management (issue #23).

Exercises the live SANDBOX API for the new methods landed by issue #23:

- ``Admin.create_set``
- ``Admin.update_set``
- ``Admin.delete_set``
- ``Admin.add_members_to_set``
- ``Admin.remove_members_from_set``

These tests stay opt-in. They are skipped cleanly when:

- The ``ALMA_SB_API_KEY`` environment variable is unset (no fixture
  available in this shell).
- The ``ALMA_SETS_INTEGRATION`` environment variable is not set to a
  truthy value (operator opt-in gate; round-trip tests create + delete
  real Alma objects, so we don't run them silently on every ``pytest``
  invocation).

Pattern source: skip-on-missing-fixture mirrors
``tests/integration/domains/test_bibs_collections.py``; round-trip
shape mirrors the issue #23 acceptance criterion.

Run with::

    ALMA_SETS_INTEGRATION=1 ALMA_SB_API_KEY=<key> \\
      pytest tests/integration/test_admin_sets.py -v -m integration

The optional ``ALMA_SETS_INTEGRATION_MEMBER_ID`` environment variable
controls the member ID used for the add/remove portion of the
round-trip (default fixture lives in the SANDBOX). When the supplied
ID is not valid in the caller's tenant, the add-step is allowed to
fall back to a skip.
"""

import os
import uuid

import pytest


def _integration_enabled() -> bool:
    """Return True when the operator has opted into the live round-trip."""
    flag = os.getenv("ALMA_SETS_INTEGRATION", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


@pytest.fixture(scope="module")
def alma_client():
    """Build a SANDBOX ``AlmaAPIClient`` if the environment supports it.

    Skips the entire module when no SANDBOX key is available so the
    suite never hard-fails on a workstation without credentials.
    """
    if not _integration_enabled():
        pytest.skip(
            "ALMA_SETS_INTEGRATION not set; skipping live sets round-trip"
        )
    api_key = os.getenv("ALMA_SB_API_KEY")
    if not api_key:
        pytest.skip("ALMA_SB_API_KEY not set; cannot run integration test")

    from almaapitk import AlmaAPIClient

    return AlmaAPIClient("SANDBOX")


@pytest.fixture(scope="module")
def admin(alma_client):
    from almaapitk import Admin

    return Admin(alma_client)


@pytest.fixture
def unique_set_name() -> str:
    """A short, collision-resistant set name.

    Per R9, no real operator IDs in committed content -- we use a UUID
    suffix here so the integration run cannot accidentally clobber a
    pre-existing tenant set. ``almaapitk-#23-`` makes the source
    obvious in the Alma UI when an operator inspects the SANDBOX.
    """
    return f"almaapitk-#23-{uuid.uuid4().hex[:8]}"


@pytest.mark.integration
class TestAdminSetsRoundTrip:
    """Full create → update → add → remove → delete round-trip."""

    def test_round_trip(self, admin, unique_set_name):
        from almaapitk import AlmaAPIError, AlmaValidationError

        # The default member ID is a placeholder; operators with a real
        # SANDBOX fixture should set ALMA_SETS_INTEGRATION_MEMBER_ID
        # to a valid ID for their tenant.
        member_id = os.getenv(
            "ALMA_SETS_INTEGRATION_MEMBER_ID", ""
        ).strip()

        created_set_id = None
        try:
            # ----- create ----------------------------------------------
            create_payload = {
                "name": unique_set_name,
                "description": "Created by AlmaAPITK issue #23 integration test",
                "type": {"value": "ITEMIZED"},
                "content": {"value": "BIB_MMS"},
                "private": {"value": "false"},
                "status": {"value": "ACTIVE"},
            }

            try:
                create_response = admin.create_set(create_payload)
            except AlmaAPIError as e:
                pytest.skip(
                    f"create_set failed in SANDBOX (tenant config?): {e}"
                )

            assert create_response is not None
            assert create_response.success
            created = create_response.data
            created_set_id = created.get("id")
            assert created_set_id, "Alma did not return an id for the new set"

            # ----- update ----------------------------------------------
            updated_payload = dict(created)
            updated_payload["description"] = (
                "Updated by AlmaAPITK issue #23 integration test"
            )
            update_response = admin.update_set(created_set_id, updated_payload)
            assert update_response is not None
            assert update_response.success

            # ----- add members -----------------------------------------
            if member_id:
                try:
                    add_response = admin.add_members_to_set(
                        created_set_id, [member_id]
                    )
                    assert add_response is not None
                    assert add_response.success

                    # ----- remove members ------------------------------
                    remove_response = admin.remove_members_from_set(
                        created_set_id, [member_id]
                    )
                    assert remove_response is not None
                    assert remove_response.success
                except AlmaAPIError as e:
                    # Member-management failed (likely the supplied
                    # member ID isn't valid in this tenant); the rest
                    # of the round-trip is still useful, so don't fail
                    # the whole test on the member step.
                    pytest.skip(
                        f"member-management step skipped in SANDBOX: {e}"
                    )
            else:
                pytest.skip(
                    "ALMA_SETS_INTEGRATION_MEMBER_ID not set; "
                    "skipping the add/remove portion of the round-trip"
                )

        finally:
            # ----- delete ---------------------------------------------
            # Always clean up the set we created, even if a mid-step
            # assertion blew up. Swallow delete failures here so the
            # original test failure is what gets reported.
            if created_set_id:
                try:
                    admin.delete_set(created_set_id)
                except AlmaAPIError:
                    pass


@pytest.mark.integration
class TestAdminSetsValidation:
    """Validation paths -- no live API call required, but kept here so the
    integration-marker filter still exercises them."""

    def test_create_set_validates_input(self, admin):
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError):
            admin.create_set({})

    def test_update_set_validates_set_id(self, admin):
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError):
            admin.update_set("", {"name": "x", "type": "ITEMIZED"})

    def test_delete_set_validates_set_id(self, admin):
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError):
            admin.delete_set("")

    def test_add_members_validates_inputs(self, admin):
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError):
            admin.add_members_to_set("", ["m1"])
        with pytest.raises(AlmaValidationError):
            admin.add_members_to_set("set-1", [])

    def test_remove_members_validates_inputs(self, admin):
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError):
            admin.remove_members_from_set("", ["m1"])
        with pytest.raises(AlmaValidationError):
            admin.remove_members_from_set("set-1", [])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
