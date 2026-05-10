"""Generated SANDBOX test t-41-2 - Users requests validation smoke (issue #41).

Maps to AC #41:
  - "Errors raise ``AlmaValidationError`` (input)" -- input-validation
    half, exercised through the live ``Users`` object so the guards
    are proven wired in the build the operator will actually ship.
  - "``cancel_user_request(reason)`` requires ``reason`` (non-empty
    validation)" -- the codex-direct audit finding that promoted
    ``reason`` from optional to required.

Confirms every input-validation guard added in issue #41 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises:

  - ``list_user_requests``           on empty / None / non-string user_id.
  - ``get_user_request``             on empty / None user_id and
                                     request_id.
  - ``create_user_request``          on empty / None user_id, on empty /
                                     None / non-dict request_data, and
                                     on the at-least-one-resource-
                                     identifier guard (mms_id /
                                     item_pid / holding_id all None must
                                     raise).
  - ``cancel_user_request``          on empty / None user_id, empty /
                                     None request_id, AND the audit-
                                     corrected MUST guard -- empty /
                                     None / non-string ``reason`` must
                                     raise.
  - ``perform_user_request_action``  on empty / None user_id, empty /
                                     None request_id, and empty / None /
                                     non-string ``op``.
  - ``update_user_request``          on empty / None user_id, empty /
                                     None request_id, empty-dict
                                     ``request_data``, and non-dict
                                     ``request_data``.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
``chunks/users-requests/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users


def test_t_41_2():
    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)
    errors = {}

    # ---- list_user_requests guards ------------------------------------
    try:
        users.list_user_requests("")
    except AlmaValidationError as e:
        errors["list_requests_empty"] = e

    try:
        users.list_user_requests(None)
    except AlmaValidationError as e:
        errors["list_requests_none"] = e

    try:
        users.list_user_requests(123)
    except AlmaValidationError as e:
        errors["list_requests_nonstring"] = e

    # ---- get_user_request guards --------------------------------------
    try:
        users.get_user_request("", "R")
    except AlmaValidationError as e:
        errors["get_request_empty_user"] = e

    try:
        users.get_user_request("U", "")
    except AlmaValidationError as e:
        errors["get_request_empty_id"] = e

    try:
        users.get_user_request(None, "R")
    except AlmaValidationError as e:
        errors["get_request_none_user"] = e

    try:
        users.get_user_request("U", None)
    except AlmaValidationError as e:
        errors["get_request_none_id"] = e

    # ---- create_user_request guards -----------------------------------
    try:
        users.create_user_request("", {"request_type": "HOLD"}, mms_id="9911")
    except AlmaValidationError as e:
        errors["create_request_empty_user"] = e

    try:
        users.create_user_request(None, {"request_type": "HOLD"}, mms_id="9911")
    except AlmaValidationError as e:
        errors["create_request_none_user"] = e

    try:
        users.create_user_request("U", {}, mms_id="9911")
    except AlmaValidationError as e:
        errors["create_request_empty_body"] = e

    try:
        users.create_user_request("U", "not-a-dict", mms_id="9911")
    except AlmaValidationError as e:
        errors["create_request_nondict_body"] = e

    try:
        users.create_user_request("U", {"request_type": "HOLD"})
    except AlmaValidationError as e:
        errors["create_request_no_resource"] = e

    # ---- cancel_user_request guards -----------------------------------
    try:
        users.cancel_user_request("", "R", reason="X")
    except AlmaValidationError as e:
        errors["cancel_empty_user"] = e

    try:
        users.cancel_user_request(None, "R", reason="X")
    except AlmaValidationError as e:
        errors["cancel_none_user"] = e

    try:
        users.cancel_user_request("U", "", reason="X")
    except AlmaValidationError as e:
        errors["cancel_empty_id"] = e

    try:
        users.cancel_user_request("U", None, reason="X")
    except AlmaValidationError as e:
        errors["cancel_none_id"] = e

    try:
        users.cancel_user_request("U", "R", reason="")
    except AlmaValidationError as e:
        errors["cancel_empty_reason"] = e

    try:
        users.cancel_user_request("U", "R", reason=None)
    except AlmaValidationError as e:
        errors["cancel_none_reason"] = e

    try:
        users.cancel_user_request("U", "R", reason=123)
    except AlmaValidationError as e:
        errors["cancel_nonstring_reason"] = e

    # ---- perform_user_request_action guards ---------------------------
    try:
        users.perform_user_request_action("", "R", op="next_step")
    except AlmaValidationError as e:
        errors["action_empty_user"] = e

    try:
        users.perform_user_request_action("U", "", op="next_step")
    except AlmaValidationError as e:
        errors["action_empty_id"] = e

    try:
        users.perform_user_request_action("U", "R", op="")
    except AlmaValidationError as e:
        errors["action_empty_op"] = e

    # ---- update_user_request guards -----------------------------------
    try:
        users.update_user_request("", "R", {"pickup_location_library": "MAIN"})
    except AlmaValidationError as e:
        errors["update_empty_user"] = e

    try:
        users.update_user_request("U", "", {"pickup_location_library": "MAIN"})
    except AlmaValidationError as e:
        errors["update_empty_id"] = e

    try:
        users.update_user_request("U", "R", {})
    except AlmaValidationError as e:
        errors["update_empty_body"] = e

    try:
        users.update_user_request("U", "R", "not-a-dict")
    except AlmaValidationError as e:
        errors["update_nondict_body"] = e

    # ---- pass-criteria assertions -------------------------------------
    assert "list_requests_empty" in errors and isinstance(
        errors["list_requests_empty"], AlmaValidationError
    )
    assert "list_requests_none" in errors and isinstance(
        errors["list_requests_none"], AlmaValidationError
    )
    assert "list_requests_nonstring" in errors and isinstance(
        errors["list_requests_nonstring"], AlmaValidationError
    )
    assert "get_request_empty_user" in errors and isinstance(
        errors["get_request_empty_user"], AlmaValidationError
    )
    assert "get_request_empty_id" in errors and isinstance(
        errors["get_request_empty_id"], AlmaValidationError
    )
    assert "get_request_none_user" in errors and isinstance(
        errors["get_request_none_user"], AlmaValidationError
    )
    assert "get_request_none_id" in errors and isinstance(
        errors["get_request_none_id"], AlmaValidationError
    )
    assert "create_request_empty_user" in errors and isinstance(
        errors["create_request_empty_user"], AlmaValidationError
    )
    assert "create_request_none_user" in errors and isinstance(
        errors["create_request_none_user"], AlmaValidationError
    )
    assert "create_request_empty_body" in errors and isinstance(
        errors["create_request_empty_body"], AlmaValidationError
    )
    assert "create_request_nondict_body" in errors and isinstance(
        errors["create_request_nondict_body"], AlmaValidationError
    )
    assert "create_request_no_resource" in errors and isinstance(
        errors["create_request_no_resource"], AlmaValidationError
    )
    assert "cancel_empty_user" in errors and isinstance(
        errors["cancel_empty_user"], AlmaValidationError
    )
    assert "cancel_none_user" in errors and isinstance(
        errors["cancel_none_user"], AlmaValidationError
    )
    assert "cancel_empty_id" in errors and isinstance(
        errors["cancel_empty_id"], AlmaValidationError
    )
    assert "cancel_none_id" in errors and isinstance(
        errors["cancel_none_id"], AlmaValidationError
    )
    assert "cancel_empty_reason" in errors and isinstance(
        errors["cancel_empty_reason"], AlmaValidationError
    )
    assert "cancel_none_reason" in errors and isinstance(
        errors["cancel_none_reason"], AlmaValidationError
    )
    assert "cancel_nonstring_reason" in errors and isinstance(
        errors["cancel_nonstring_reason"], AlmaValidationError
    )
    assert "action_empty_user" in errors and isinstance(
        errors["action_empty_user"], AlmaValidationError
    )
    assert "action_empty_id" in errors and isinstance(
        errors["action_empty_id"], AlmaValidationError
    )
    assert "action_empty_op" in errors and isinstance(
        errors["action_empty_op"], AlmaValidationError
    )
    assert "update_empty_user" in errors and isinstance(
        errors["update_empty_user"], AlmaValidationError
    )
    assert "update_empty_id" in errors and isinstance(
        errors["update_empty_id"], AlmaValidationError
    )
    assert "update_empty_body" in errors and isinstance(
        errors["update_empty_body"], AlmaValidationError
    )
    assert "update_nondict_body" in errors and isinstance(
        errors["update_nondict_body"], AlmaValidationError
    )
