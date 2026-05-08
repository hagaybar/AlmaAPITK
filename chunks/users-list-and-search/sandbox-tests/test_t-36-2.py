"""Generated SANDBOX test t-36-2 - Users list & search validation smoke
(issue #36).

Maps to AC #36:
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- input-validation half.
  - "missing ``user_id`` raises ``AlmaValidationError``" facet of the
    unit-test AC, exercised here at runtime (the fully-mocked unit
    coverage lives in ``tests/unit/domains/test_users.py``).

Confirms every input-validation guard added in issue #36 raises
``AlmaValidationError`` BEFORE any HTTP call is issued:

  - ``search_users`` ``q`` guard: empty string, whitespace-only, ``None``,
    non-string -- all four must raise.
  - ``get_user_personal_data`` ``user_id`` guard: empty string,
    whitespace-only, ``None``, non-string -- all four must raise.

``list_users`` has no required string parameter so no validation
surface is exercised here.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
``chunks/users-list-and-search/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users


def test_t_36_2():
    client = AlmaAPIClient(environment="SANDBOX")
    users_domain = Users(client)
    errors = {}

    # --- search_users q guard --------------------------------------------
    try:
        users_domain.search_users("")
    except AlmaValidationError as e:
        errors["search_empty"] = e

    try:
        users_domain.search_users("   ")
    except AlmaValidationError as e:
        errors["search_whitespace"] = e

    try:
        users_domain.search_users(None)
    except AlmaValidationError as e:
        errors["search_none"] = e

    try:
        users_domain.search_users(123)
    except AlmaValidationError as e:
        errors["search_nonstring"] = e

    # --- get_user_personal_data user_id guard ----------------------------
    try:
        users_domain.get_user_personal_data("")
    except AlmaValidationError as e:
        errors["personal_empty"] = e

    try:
        users_domain.get_user_personal_data("   ")
    except AlmaValidationError as e:
        errors["personal_whitespace"] = e

    try:
        users_domain.get_user_personal_data(None)
    except AlmaValidationError as e:
        errors["personal_none"] = e

    try:
        users_domain.get_user_personal_data(123)
    except AlmaValidationError as e:
        errors["personal_nonstring"] = e

    # --- assert every guard fired ----------------------------------------
    assert "search_empty" in errors and isinstance(
        errors["search_empty"], AlmaValidationError
    )
    assert "search_whitespace" in errors and isinstance(
        errors["search_whitespace"], AlmaValidationError
    )
    assert "search_none" in errors and isinstance(
        errors["search_none"], AlmaValidationError
    )
    assert "search_nonstring" in errors and isinstance(
        errors["search_nonstring"], AlmaValidationError
    )
    assert "personal_empty" in errors and isinstance(
        errors["personal_empty"], AlmaValidationError
    )
    assert "personal_whitespace" in errors and isinstance(
        errors["personal_whitespace"], AlmaValidationError
    )
    assert "personal_none" in errors and isinstance(
        errors["personal_none"], AlmaValidationError
    )
    assert "personal_nonstring" in errors and isinstance(
        errors["personal_nonstring"], AlmaValidationError
    )
