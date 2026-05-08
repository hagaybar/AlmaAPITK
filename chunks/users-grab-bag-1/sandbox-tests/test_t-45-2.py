"""Generated SANDBOX test t-45-2 - Users deposits validation smoke
(issue #45).

Maps to AC #45:
  - "Errors raise ``AlmaValidationError`` (input)..." -- input-
    validation half across list / create / get / perform-action.

Confirms every input-validation guard added in issue #45 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises:

  - ``list_user_deposits``         on empty / None / non-string user_id.
  - ``create_user_deposit``        on empty / None user_id and on
    missing / non-dict deposit_data.
  - ``get_user_deposit``           on empty / None user_id and
    deposit_id.
  - ``perform_user_deposit_action`` on empty / None user_id, deposit_id,
    and op.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
``chunks/users-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users


def test_t_45_2():
    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)
    errors = {}

    # ---- list_user_deposits guards ------------------------------------
    try:
        users.list_user_deposits("")
    except AlmaValidationError as e:
        errors["list_deposits_empty"] = e

    try:
        users.list_user_deposits(None)
    except AlmaValidationError as e:
        errors["list_deposits_none"] = e

    try:
        users.list_user_deposits(123)
    except AlmaValidationError as e:
        errors["list_deposits_nonstring"] = e

    # ---- create_user_deposit guards -----------------------------------
    try:
        users.create_user_deposit("", {"amount": "1.00"})
    except AlmaValidationError as e:
        errors["create_deposit_empty_user"] = e

    try:
        users.create_user_deposit(None, {"amount": "1.00"})
    except AlmaValidationError as e:
        errors["create_deposit_none_user"] = e

    try:
        users.create_user_deposit("U", None)
    except AlmaValidationError as e:
        errors["create_deposit_none_body"] = e

    try:
        users.create_user_deposit("U", "not-a-dict")
    except AlmaValidationError as e:
        errors["create_deposit_nondict_body"] = e

    # ---- get_user_deposit guards --------------------------------------
    try:
        users.get_user_deposit("", "D")
    except AlmaValidationError as e:
        errors["get_deposit_empty_user"] = e

    try:
        users.get_user_deposit("U", "")
    except AlmaValidationError as e:
        errors["get_deposit_empty_id"] = e

    try:
        users.get_user_deposit(None, "D")
    except AlmaValidationError as e:
        errors["get_deposit_none_user"] = e

    try:
        users.get_user_deposit("U", None)
    except AlmaValidationError as e:
        errors["get_deposit_none_id"] = e

    # ---- perform_user_deposit_action guards ---------------------------
    try:
        users.perform_user_deposit_action("", "D", "pay")
    except AlmaValidationError as e:
        errors["action_empty_user"] = e

    try:
        users.perform_user_deposit_action("U", "", "pay")
    except AlmaValidationError as e:
        errors["action_empty_id"] = e

    try:
        users.perform_user_deposit_action("U", "D", "")
    except AlmaValidationError as e:
        errors["action_empty_op"] = e

    try:
        users.perform_user_deposit_action(None, "D", "pay")
    except AlmaValidationError as e:
        errors["action_none_user"] = e

    try:
        users.perform_user_deposit_action("U", None, "pay")
    except AlmaValidationError as e:
        errors["action_none_id"] = e

    try:
        users.perform_user_deposit_action("U", "D", None)
    except AlmaValidationError as e:
        errors["action_none_op"] = e

    # ---- pass-criteria assertions --------------------------------------
    assert "list_deposits_empty" in errors and isinstance(
        errors["list_deposits_empty"], AlmaValidationError
    )
    assert "list_deposits_none" in errors and isinstance(
        errors["list_deposits_none"], AlmaValidationError
    )
    assert "list_deposits_nonstring" in errors and isinstance(
        errors["list_deposits_nonstring"], AlmaValidationError
    )
    assert "create_deposit_empty_user" in errors and isinstance(
        errors["create_deposit_empty_user"], AlmaValidationError
    )
    assert "create_deposit_none_user" in errors and isinstance(
        errors["create_deposit_none_user"], AlmaValidationError
    )
    assert "create_deposit_none_body" in errors and isinstance(
        errors["create_deposit_none_body"], AlmaValidationError
    )
    assert "create_deposit_nondict_body" in errors and isinstance(
        errors["create_deposit_nondict_body"], AlmaValidationError
    )
    assert "get_deposit_empty_user" in errors and isinstance(
        errors["get_deposit_empty_user"], AlmaValidationError
    )
    assert "get_deposit_empty_id" in errors and isinstance(
        errors["get_deposit_empty_id"], AlmaValidationError
    )
    assert "get_deposit_none_user" in errors and isinstance(
        errors["get_deposit_none_user"], AlmaValidationError
    )
    assert "get_deposit_none_id" in errors and isinstance(
        errors["get_deposit_none_id"], AlmaValidationError
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
    assert "action_none_user" in errors and isinstance(
        errors["action_none_user"], AlmaValidationError
    )
    assert "action_none_id" in errors and isinstance(
        errors["action_none_id"], AlmaValidationError
    )
    assert "action_none_op" in errors and isinstance(
        errors["action_none_op"], AlmaValidationError
    )
