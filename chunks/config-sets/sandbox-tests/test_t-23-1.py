"""Generated SANDBOX test t-23-1 - Sets full CRUD + member-management round-trip (issue #23).

Maps to:
  - AC #23.2: integration test against SANDBOX
  - AC #23.7: member-management endpoint uses correct `op` query parameter
    (`add_members` / `delete_members`)
  - AC #23.8: documented round-trip flow
    (create -> update -> add members -> remove members -> delete)

Drives the full set CRUD + member-management round-trip end-to-end against live
SANDBOX. Creates a fresh ITEMIZED BIB_MMS set with a UUID-suffixed name (so
concurrent runs do not collide), updates its description (PUT), adds an existing
SANDBOX bib MMS as a member (POST with op=add_members), confirms the member
count rose, removes the member (POST with op=delete_members), confirms the
count fell, then deletes the set (DELETE). Reads the surviving set with the
existing Admin.get_set_info helper between mutations to assert each step landed.

The fixture (existing_bib_mms_id) is loaded at runtime from
chunks/config-sets/test-data.json so that no operator-supplied identifier is
committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
chunks/config-sets/test-recommendation.json.
"""
from __future__ import annotations

import json
import pathlib
import uuid

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.admin import Admin

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())
EXISTING_BIB_MMS_ID = _TEST_DATA["existing_bib_mms_id"]


def _extract_member_count(set_info):
    """Return the integer member count from an Admin.get_set_info summary dict.

    ``Admin.get_set_info`` returns a normalised summary, not the raw Alma
    response: the count lives at ``total_members`` (already unwrapped from
    Alma's ``number_of_members.value`` shape). Coerce to int and default to
    0 if absent or unparseable.
    """
    if not isinstance(set_info, dict):
        return 0
    return int(set_info.get("total_members", 0) or 0)


def test_t_23_1():
    client = AlmaAPIClient(environment="SANDBOX")
    admin = Admin(client)

    set_name = f"almaapitk-chunk23-{uuid.uuid4().hex[:8]}"
    create_payload = {
        "name": set_name,
        "description": "almaapitk chunk-23 round-trip set (auto-cleanup)",
        "type": {"value": "ITEMIZED"},
        "content": {"value": "BIB_MMS"},
        "private": {"value": "false"},
        "status": {"value": "ACTIVE"},
    }

    created_set_id = None
    try:
        # --- create ---------------------------------------------------------
        create_response = admin.create_set(create_payload)
        assert create_response is not None
        assert getattr(create_response, "success", False) is True
        created_set_id = create_response.data.get("id") if hasattr(create_response, "data") else None
        assert isinstance(created_set_id, str) and len(created_set_id) > 0

        # --- update ---------------------------------------------------------
        update_payload = dict(create_payload)
        update_payload["description"] = "almaapitk chunk-23 round-trip set (updated)"
        update_payload["id"] = created_set_id
        update_response = admin.update_set(created_set_id, update_payload)
        assert getattr(update_response, "success", False) is True

        post_update_info = admin.get_set_info(created_set_id)
        assert isinstance(post_update_info, dict)
        post_update_description = post_update_info.get("description", "")
        assert (
            post_update_description == "almaapitk chunk-23 round-trip set (updated)"
            or "updated" in str(post_update_description).lower()
        )

        # --- add members ----------------------------------------------------
        add_response = admin.add_members_to_set(created_set_id, [EXISTING_BIB_MMS_ID])
        assert getattr(add_response, "success", False) is True

        post_add_info = admin.get_set_info(created_set_id)
        post_add_member_count = _extract_member_count(post_add_info)
        assert post_add_member_count >= 1

        # --- remove members -------------------------------------------------
        remove_response = admin.remove_members_from_set(created_set_id, [EXISTING_BIB_MMS_ID])
        assert getattr(remove_response, "success", False) is True

        post_remove_info = admin.get_set_info(created_set_id)
        post_remove_member_count = _extract_member_count(post_remove_info)
        assert post_remove_member_count == 0

        # --- delete ---------------------------------------------------------
        delete_response = admin.delete_set(created_set_id)
        assert getattr(delete_response, "success", False) is True

        # The set should no longer be retrievable; any read attempt should
        # raise (Alma typically returns 400/404 for an unknown set id).
        post_delete_error = None
        try:
            admin.get_set_info(created_set_id)
        except Exception as exc:  # noqa: BLE001 - any error proves the set is gone
            post_delete_error = exc
        assert post_delete_error is not None

        # The happy path successfully deleted the set, so the cleanup branch
        # below has nothing to do.
        created_set_id = None

    finally:
        if created_set_id:
            try:
                admin.delete_set(created_set_id)
            except AlmaAPIError:
                # Set already gone (e.g., happy-path delete succeeded but a
                # later assertion failed) -- safe to ignore.
                pass
