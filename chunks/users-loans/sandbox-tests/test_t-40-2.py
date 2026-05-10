"""Generated SANDBOX test t-40-2 - Users loans validation smoke (issue #40).

Maps to AC #40:
  - "Unit tests cover: missing/both ``item_barcode`` + ``item_pid``
    raises ``AlmaValidationError``; missing body fields raise
    ``AlmaValidationError``" -- input-validation half, exercised through
    the live ``Users`` object so that the guards are proven wired in
    the build the operator will actually ship.

Confirms every input-validation guard added in issue #40 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises:

  - ``list_user_loans``    on empty / None / non-string user_id.
  - ``get_user_loan``      on empty / None user_id and loan_id.
  - ``create_user_loan``   on empty / None user_id, on BOTH
    ``item_barcode`` AND ``item_pid`` supplied (exclusivity guard),
    on NEITHER ``item_barcode`` NOR ``item_pid`` supplied
    (at-least-one guard), and on non-dict ``loan_data`` when
    ``item_barcode`` is supplied.
  - ``renew_user_loan``    on empty / None user_id and loan_id.
  - ``update_user_loan``   on empty / None user_id and loan_id, on
    empty-dict ``loan_data``, and on non-dict ``loan_data``.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
``chunks/users-loans/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users


def test_t_40_2():
    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)
    errors = {}

    # ---- list_user_loans guards ---------------------------------------
    try:
        users.list_user_loans("")
    except AlmaValidationError as e:
        errors["list_loans_empty"] = e

    try:
        users.list_user_loans(None)
    except AlmaValidationError as e:
        errors["list_loans_none"] = e

    try:
        users.list_user_loans(123)
    except AlmaValidationError as e:
        errors["list_loans_nonstring"] = e

    # ---- get_user_loan guards -----------------------------------------
    try:
        users.get_user_loan("", "L")
    except AlmaValidationError as e:
        errors["get_loan_empty_user"] = e

    try:
        users.get_user_loan("U", "")
    except AlmaValidationError as e:
        errors["get_loan_empty_id"] = e

    try:
        users.get_user_loan(None, "L")
    except AlmaValidationError as e:
        errors["get_loan_none_user"] = e

    try:
        users.get_user_loan("U", None)
    except AlmaValidationError as e:
        errors["get_loan_none_id"] = e

    # ---- create_user_loan guards --------------------------------------
    try:
        users.create_user_loan("", item_barcode="BC1")
    except AlmaValidationError as e:
        errors["create_loan_empty_user"] = e

    try:
        users.create_user_loan(None, item_barcode="BC1")
    except AlmaValidationError as e:
        errors["create_loan_none_user"] = e

    try:
        users.create_user_loan("U", item_barcode="BC1", item_pid="PID1")
    except AlmaValidationError as e:
        errors["create_loan_both_ids"] = e

    try:
        users.create_user_loan("U")
    except AlmaValidationError as e:
        errors["create_loan_neither_id"] = e

    try:
        users.create_user_loan("U", item_barcode="BC1", loan_data="not-a-dict")
    except AlmaValidationError as e:
        errors["create_loan_nondict_body"] = e

    # ---- renew_user_loan guards ---------------------------------------
    try:
        users.renew_user_loan("", "L")
    except AlmaValidationError as e:
        errors["renew_empty_user"] = e

    try:
        users.renew_user_loan("U", "")
    except AlmaValidationError as e:
        errors["renew_empty_id"] = e

    try:
        users.renew_user_loan(None, "L")
    except AlmaValidationError as e:
        errors["renew_none_user"] = e

    try:
        users.renew_user_loan("U", None)
    except AlmaValidationError as e:
        errors["renew_none_id"] = e

    # ---- update_user_loan guards --------------------------------------
    try:
        users.update_user_loan("", "L", {"due_date": "2026-12-31Z"})
    except AlmaValidationError as e:
        errors["update_empty_user"] = e

    try:
        users.update_user_loan("U", "", {"due_date": "2026-12-31Z"})
    except AlmaValidationError as e:
        errors["update_empty_id"] = e

    try:
        users.update_user_loan(None, "L", {"due_date": "2026-12-31Z"})
    except AlmaValidationError as e:
        errors["update_none_user"] = e

    try:
        users.update_user_loan("U", None, {"due_date": "2026-12-31Z"})
    except AlmaValidationError as e:
        errors["update_none_id"] = e

    try:
        users.update_user_loan("U", "L", {})
    except AlmaValidationError as e:
        errors["update_empty_body"] = e

    try:
        users.update_user_loan("U", "L", "not-a-dict")
    except AlmaValidationError as e:
        errors["update_nondict_body"] = e

    # ---- pass-criteria assertions --------------------------------------
    assert "list_loans_empty" in errors and isinstance(
        errors["list_loans_empty"], AlmaValidationError
    )
    assert "list_loans_none" in errors and isinstance(
        errors["list_loans_none"], AlmaValidationError
    )
    assert "list_loans_nonstring" in errors and isinstance(
        errors["list_loans_nonstring"], AlmaValidationError
    )
    assert "get_loan_empty_user" in errors and isinstance(
        errors["get_loan_empty_user"], AlmaValidationError
    )
    assert "get_loan_empty_id" in errors and isinstance(
        errors["get_loan_empty_id"], AlmaValidationError
    )
    assert "get_loan_none_user" in errors and isinstance(
        errors["get_loan_none_user"], AlmaValidationError
    )
    assert "get_loan_none_id" in errors and isinstance(
        errors["get_loan_none_id"], AlmaValidationError
    )
    assert "create_loan_empty_user" in errors and isinstance(
        errors["create_loan_empty_user"], AlmaValidationError
    )
    assert "create_loan_none_user" in errors and isinstance(
        errors["create_loan_none_user"], AlmaValidationError
    )
    assert "create_loan_both_ids" in errors and isinstance(
        errors["create_loan_both_ids"], AlmaValidationError
    )
    assert "create_loan_neither_id" in errors and isinstance(
        errors["create_loan_neither_id"], AlmaValidationError
    )
    assert "create_loan_nondict_body" in errors and isinstance(
        errors["create_loan_nondict_body"], AlmaValidationError
    )
    assert "renew_empty_user" in errors and isinstance(
        errors["renew_empty_user"], AlmaValidationError
    )
    assert "renew_empty_id" in errors and isinstance(
        errors["renew_empty_id"], AlmaValidationError
    )
    assert "renew_none_user" in errors and isinstance(
        errors["renew_none_user"], AlmaValidationError
    )
    assert "renew_none_id" in errors and isinstance(
        errors["renew_none_id"], AlmaValidationError
    )
    assert "update_empty_user" in errors and isinstance(
        errors["update_empty_user"], AlmaValidationError
    )
    assert "update_empty_id" in errors and isinstance(
        errors["update_empty_id"], AlmaValidationError
    )
    assert "update_none_user" in errors and isinstance(
        errors["update_none_user"], AlmaValidationError
    )
    assert "update_none_id" in errors and isinstance(
        errors["update_none_id"], AlmaValidationError
    )
    assert "update_empty_body" in errors and isinstance(
        errors["update_empty_body"], AlmaValidationError
    )
    assert "update_nondict_body" in errors and isinstance(
        errors["update_nondict_body"], AlmaValidationError
    )
