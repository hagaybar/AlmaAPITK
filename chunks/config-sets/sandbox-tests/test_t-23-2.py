"""Generated SANDBOX test t-23-2 - Sets write-method input-validation smoke (issue #23).

Maps to:
  - AC #23.3: input-validation errors raise AlmaValidationError

Confirms the new write methods raise AlmaValidationError on malformed inputs
BEFORE any HTTP call is issued. Exercises the input-validation guards added
in this chunk:

  * create_set rejects an empty/non-dict payload and a payload missing
    'name' or 'type'
  * update_set rejects an empty set_id and an empty body
  * delete_set rejects an empty set_id
  * add_members_to_set / remove_members_from_set reject an empty
    member_ids list, blank entries, and an empty set_id

These are pure Python guards, but exercising them through the live
AlmaAPIClient/Admin objects proves the guards are wired in the build the
operator will actually use. No SANDBOX state is mutated.

DO NOT EDIT by hand. Generated from
chunks/config-sets/test-recommendation.json.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.admin import Admin

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
# test-data.json is loaded for parity with the other generated tests; this
# smoke does not consume any fixture values because no HTTP call is issued.
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_23_2():
    client = AlmaAPIClient(environment="SANDBOX")
    admin = Admin(client)

    errors = {}

    # --- create_set guards --------------------------------------------------
    try:
        admin.create_set({})
    except AlmaValidationError as exc:
        errors["create_empty"] = exc

    try:
        admin.create_set({"type": {"value": "ITEMIZED"}})
    except AlmaValidationError as exc:
        errors["create_no_name"] = exc

    try:
        admin.create_set({"name": "x"})
    except AlmaValidationError as exc:
        errors["create_no_type"] = exc

    # --- update_set guards --------------------------------------------------
    try:
        admin.update_set("", {"name": "x"})
    except AlmaValidationError as exc:
        errors["update_empty_id"] = exc

    try:
        admin.update_set("abc", {})
    except AlmaValidationError as exc:
        errors["update_empty_body"] = exc

    # --- delete_set guards --------------------------------------------------
    try:
        admin.delete_set("")
    except AlmaValidationError as exc:
        errors["delete_empty_id"] = exc

    # --- add_members_to_set guards -----------------------------------------
    try:
        admin.add_members_to_set("abc", [])
    except AlmaValidationError as exc:
        errors["add_empty_members"] = exc

    try:
        admin.add_members_to_set("abc", [""])
    except AlmaValidationError as exc:
        errors["add_blank_member"] = exc

    # --- remove_members_from_set guards ------------------------------------
    try:
        admin.remove_members_from_set("abc", [])
    except AlmaValidationError as exc:
        errors["remove_empty_members"] = exc

    try:
        admin.remove_members_from_set("", ["9911"])
    except AlmaValidationError as exc:
        errors["remove_empty_id"] = exc

    # --- assertions ---------------------------------------------------------
    assert "create_empty" in errors and isinstance(errors["create_empty"], AlmaValidationError)
    assert "create_no_name" in errors and isinstance(errors["create_no_name"], AlmaValidationError)
    assert "create_no_type" in errors and isinstance(errors["create_no_type"], AlmaValidationError)
    assert "update_empty_id" in errors and isinstance(errors["update_empty_id"], AlmaValidationError)
    assert "update_empty_body" in errors and isinstance(errors["update_empty_body"], AlmaValidationError)
    assert "delete_empty_id" in errors and isinstance(errors["delete_empty_id"], AlmaValidationError)
    assert "add_empty_members" in errors and isinstance(errors["add_empty_members"], AlmaValidationError)
    assert "add_blank_member" in errors and isinstance(errors["add_blank_member"], AlmaValidationError)
    assert "remove_empty_members" in errors and isinstance(errors["remove_empty_members"], AlmaValidationError)
    assert "remove_empty_id" in errors and isinstance(errors["remove_empty_id"], AlmaValidationError)
