"""Generated SANDBOX test t-37-2 - Users create/delete validation smoke
(issue #37).

Maps to issue #37 acceptance criteria:
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- input-validation half.
  - "``create_user`` validates required fields (primary_id, account_type,
    status, user_group) before sending."

Confirms every input-validation guard added in issue #37 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises:
  - ``create_user`` with empty / ``None`` / non-dict payloads.
  - ``create_user`` with each of the four required core fields missing
    individually (primary_id, account_type, status, user_group).
  - ``create_user`` with empty ``{"value": ""}`` wrappers on the typed
    fields (account_type, status, user_group).
  - ``delete_user`` with empty / ``None`` / whitespace-only / non-string
    user identifiers.

Pure runtime guard exercise; no SANDBOX state is read or mutated. The
fixture file (``chunks/users-crud/test-data.json``) is empty -- the
runtime fixture-load shape is preserved here for consistency with other
chunks.

DO NOT EDIT by hand. Generated from
chunks/users-crud/test-recommendation.json.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users

_TEST_DATA = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "test-data.json").read_text()
)


def test_t_37_2():
    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)
    errors = {}

    # --- create_user: payload-shape guards ---------------------------------
    try:
        users.create_user({})
    except AlmaValidationError as e:
        errors["create_empty"] = e

    try:
        users.create_user(None)
    except (AlmaValidationError, TypeError) as e:
        errors["create_none"] = e

    try:
        users.create_user("not-a-dict")
    except (AlmaValidationError, TypeError) as e:
        errors["create_nondict"] = e

    # --- create_user: missing-required-field guards ------------------------
    try:
        users.create_user(
            {
                "account_type": {"value": "INTERNAL"},
                "status": {"value": "ACTIVE"},
                "user_group": {"value": "01"},
            }
        )
    except AlmaValidationError as e:
        errors["create_no_primary_id"] = e

    try:
        users.create_user(
            {
                "primary_id": "tau-test-placeholder",
                "status": {"value": "ACTIVE"},
                "user_group": {"value": "01"},
            }
        )
    except AlmaValidationError as e:
        errors["create_no_account_type"] = e

    try:
        users.create_user(
            {
                "primary_id": "tau-test-placeholder",
                "account_type": {"value": "INTERNAL"},
                "user_group": {"value": "01"},
            }
        )
    except AlmaValidationError as e:
        errors["create_no_status"] = e

    try:
        users.create_user(
            {
                "primary_id": "tau-test-placeholder",
                "account_type": {"value": "INTERNAL"},
                "status": {"value": "ACTIVE"},
            }
        )
    except AlmaValidationError as e:
        errors["create_no_user_group"] = e

    # --- create_user: empty-value-in-wrapper guards ------------------------
    try:
        users.create_user(
            {
                "primary_id": "tau-test-placeholder",
                "account_type": {"value": ""},
                "status": {"value": "ACTIVE"},
                "user_group": {"value": "01"},
            }
        )
    except AlmaValidationError as e:
        errors["create_empty_account_type_value"] = e

    try:
        users.create_user(
            {
                "primary_id": "tau-test-placeholder",
                "account_type": {"value": "INTERNAL"},
                "status": {"value": ""},
                "user_group": {"value": "01"},
            }
        )
    except AlmaValidationError as e:
        errors["create_empty_status_value"] = e

    try:
        users.create_user(
            {
                "primary_id": "tau-test-placeholder",
                "account_type": {"value": "INTERNAL"},
                "status": {"value": "ACTIVE"},
                "user_group": {"value": ""},
            }
        )
    except AlmaValidationError as e:
        errors["create_empty_user_group_value"] = e

    # --- delete_user: identifier guards ------------------------------------
    try:
        users.delete_user("")
    except AlmaValidationError as e:
        errors["delete_empty"] = e

    try:
        users.delete_user(None)
    except (AlmaValidationError, TypeError) as e:
        errors["delete_none"] = e

    try:
        users.delete_user("   ")
    except AlmaValidationError as e:
        errors["delete_whitespace"] = e

    try:
        users.delete_user(123)
    except (AlmaValidationError, TypeError) as e:
        errors["delete_nonstring"] = e

    # --- assertions --------------------------------------------------------
    assert "create_empty" in errors and isinstance(
        errors["create_empty"], AlmaValidationError
    )
    assert "create_none" in errors
    assert "create_nondict" in errors
    assert "create_no_primary_id" in errors and isinstance(
        errors["create_no_primary_id"], AlmaValidationError
    )
    assert "create_no_account_type" in errors and isinstance(
        errors["create_no_account_type"], AlmaValidationError
    )
    assert "create_no_status" in errors and isinstance(
        errors["create_no_status"], AlmaValidationError
    )
    assert "create_no_user_group" in errors and isinstance(
        errors["create_no_user_group"], AlmaValidationError
    )
    assert "create_empty_account_type_value" in errors and isinstance(
        errors["create_empty_account_type_value"], AlmaValidationError
    )
    assert "create_empty_status_value" in errors and isinstance(
        errors["create_empty_status_value"], AlmaValidationError
    )
    assert "create_empty_user_group_value" in errors and isinstance(
        errors["create_empty_user_group_value"], AlmaValidationError
    )
    assert "delete_empty" in errors and isinstance(
        errors["delete_empty"], AlmaValidationError
    )
    assert "delete_none" in errors
    assert "delete_whitespace" in errors and isinstance(
        errors["delete_whitespace"], AlmaValidationError
    )
    assert "delete_nonstring" in errors
