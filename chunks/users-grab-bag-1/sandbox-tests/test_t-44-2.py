"""Generated SANDBOX test t-44-2 - Users fees validation smoke (issue #44).

Maps to AC #44 facets:
  - "Errors raise ``AlmaValidationError`` (input)..." -- input-
    validation half across list / get / create / pay_all / pay / waive /
    dispute / restore.
  - Audit-corrected guards:
       * ``pay_all_user_fees`` rejects non-numeric, non-``ALL`` amount
         strings.
       * ``waive_user_fee`` requires non-empty ``reason``.
       * ``dispute_user_fee`` does NOT require ``reason``.

Confirms every input-validation guard added in issue #44 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Pure runtime
guard exercise; no SANDBOX state is read or mutated.

Note on the ``dispute`` assertion: dispute does NOT require a reason,
so passing a missing reason MUST NOT raise on the reason guard.
However, ``dispute_user_fee('', 'F')`` MUST still raise because the
empty user_id guard fires. We therefore exercise the empty-user_id
form to prove the dispute guards are wired correctly while still
honouring the audit-corrected "reason is optional" contract.

DO NOT EDIT by hand. Generated from
``chunks/users-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users


def test_t_44_2():
    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)
    errors = {}

    # ---- list_user_fees guards ----------------------------------------
    try:
        users.list_user_fees("")
    except AlmaValidationError as e:
        errors["list_fees_empty"] = e

    try:
        users.list_user_fees(None)
    except AlmaValidationError as e:
        errors["list_fees_none"] = e

    # ---- get_user_fee guards ------------------------------------------
    try:
        users.get_user_fee("", "F")
    except AlmaValidationError as e:
        errors["get_fee_empty_user"] = e

    try:
        users.get_user_fee("U", "")
    except AlmaValidationError as e:
        errors["get_fee_empty_id"] = e

    try:
        users.get_user_fee(None, "F")
    except AlmaValidationError as e:
        errors["get_fee_none_user"] = e

    try:
        users.get_user_fee("U", None)
    except AlmaValidationError as e:
        errors["get_fee_none_id"] = e

    # ---- create_user_fee guards ---------------------------------------
    try:
        users.create_user_fee("", {"type": {"value": "OTHER"}, "amount": "1.00"})
    except AlmaValidationError as e:
        errors["create_fee_empty_user"] = e

    try:
        users.create_user_fee(
            None, {"type": {"value": "OTHER"}, "amount": "1.00"}
        )
    except AlmaValidationError as e:
        errors["create_fee_none_user"] = e

    try:
        users.create_user_fee("U", None)
    except AlmaValidationError as e:
        errors["create_fee_none_body"] = e

    try:
        users.create_user_fee("U", "not-a-dict")
    except AlmaValidationError as e:
        errors["create_fee_nondict_body"] = e

    # ---- pay_all_user_fees guards -------------------------------------
    try:
        users.pay_all_user_fees("")
    except AlmaValidationError as e:
        errors["pay_all_empty_user"] = e

    try:
        users.pay_all_user_fees(None)
    except AlmaValidationError as e:
        errors["pay_all_none_user"] = e

    # Audit-flagged: pay_all rejects non-numeric, non-'ALL' amount.
    try:
        users.pay_all_user_fees("U", amount="abc")
    except AlmaValidationError as e:
        errors["pay_all_bad_amount"] = e

    # ---- pay_user_fee guards ------------------------------------------
    try:
        users.pay_user_fee("", "F", amount="1.00")
    except AlmaValidationError as e:
        errors["pay_empty_user"] = e

    try:
        users.pay_user_fee("U", "", amount="1.00")
    except AlmaValidationError as e:
        errors["pay_empty_id"] = e

    try:
        users.pay_user_fee(None, "F", amount="1.00")
    except AlmaValidationError as e:
        errors["pay_none_user"] = e

    try:
        users.pay_user_fee("U", None, amount="1.00")
    except AlmaValidationError as e:
        errors["pay_none_id"] = e

    # ---- waive_user_fee guards (audit-flagged: reason REQUIRED) -------
    try:
        users.waive_user_fee("U", "F", reason="")
    except AlmaValidationError as e:
        errors["waive_empty_reason"] = e

    try:
        users.waive_user_fee("U", "F", reason=None)
    except AlmaValidationError as e:
        errors["waive_none_reason"] = e

    # ---- dispute_user_fee guards (audit-corrected: reason OPTIONAL) ---
    # Confirm the dispute guards still fire on bad user_id even when no
    # reason is supplied — proves the wrapper validates user_id without
    # erroneously requiring a reason.
    dispute_no_reason_validation_raised = False
    try:
        users.dispute_user_fee("", "F")
    except AlmaValidationError:
        dispute_no_reason_validation_raised = True
    except Exception:
        # Anything other than AlmaValidationError on bad user_id
        # indicates the guard is not wired correctly.
        dispute_no_reason_validation_raised = False

    # ---- restore_user_fee guards --------------------------------------
    try:
        users.restore_user_fee("", "F")
    except AlmaValidationError as e:
        errors["restore_empty_user"] = e

    try:
        users.restore_user_fee("U", "")
    except AlmaValidationError as e:
        errors["restore_empty_id"] = e

    # ---- pass-criteria assertions --------------------------------------
    assert "list_fees_empty" in errors and isinstance(
        errors["list_fees_empty"], AlmaValidationError
    )
    assert "list_fees_none" in errors and isinstance(
        errors["list_fees_none"], AlmaValidationError
    )
    assert "get_fee_empty_user" in errors and isinstance(
        errors["get_fee_empty_user"], AlmaValidationError
    )
    assert "get_fee_empty_id" in errors and isinstance(
        errors["get_fee_empty_id"], AlmaValidationError
    )
    assert "get_fee_none_user" in errors and isinstance(
        errors["get_fee_none_user"], AlmaValidationError
    )
    assert "get_fee_none_id" in errors and isinstance(
        errors["get_fee_none_id"], AlmaValidationError
    )
    assert "create_fee_empty_user" in errors and isinstance(
        errors["create_fee_empty_user"], AlmaValidationError
    )
    assert "create_fee_none_user" in errors and isinstance(
        errors["create_fee_none_user"], AlmaValidationError
    )
    assert "create_fee_none_body" in errors and isinstance(
        errors["create_fee_none_body"], AlmaValidationError
    )
    assert "create_fee_nondict_body" in errors and isinstance(
        errors["create_fee_nondict_body"], AlmaValidationError
    )
    assert "pay_all_empty_user" in errors and isinstance(
        errors["pay_all_empty_user"], AlmaValidationError
    )
    assert "pay_all_none_user" in errors and isinstance(
        errors["pay_all_none_user"], AlmaValidationError
    )
    assert "pay_all_bad_amount" in errors and isinstance(
        errors["pay_all_bad_amount"], AlmaValidationError
    )
    assert "pay_empty_user" in errors and isinstance(
        errors["pay_empty_user"], AlmaValidationError
    )
    assert "pay_empty_id" in errors and isinstance(
        errors["pay_empty_id"], AlmaValidationError
    )
    assert "pay_none_user" in errors and isinstance(
        errors["pay_none_user"], AlmaValidationError
    )
    assert "pay_none_id" in errors and isinstance(
        errors["pay_none_id"], AlmaValidationError
    )
    assert "waive_empty_reason" in errors and isinstance(
        errors["waive_empty_reason"], AlmaValidationError
    )
    assert "waive_none_reason" in errors and isinstance(
        errors["waive_none_reason"], AlmaValidationError
    )
    assert dispute_no_reason_validation_raised is True, (
        "dispute_user_fee('', 'F') must raise AlmaValidationError on the "
        "empty user_id guard (audit-corrected: reason is optional, but "
        "user_id is still required)"
    )
    assert "restore_empty_user" in errors and isinstance(
        errors["restore_empty_user"], AlmaValidationError
    )
    assert "restore_empty_id" in errors and isinstance(
        errors["restore_empty_id"], AlmaValidationError
    )
