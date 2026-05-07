"""Generated SANDBOX test t-30-2 - Configuration deposit + import profiles
validation smoke (issue #30).

Maps to AC #30:
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- input-validation half.

Confirms every input-validation guard added in issue #30 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises
``Configuration._validate_code`` through ``get_deposit_profile`` and
``get_import_profile`` (empty, whitespace, ``None``, non-string).
``list_deposit_profiles`` / ``list_import_profiles`` take no arguments
so have no validation surface and are not exercised here.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
``chunks/config-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.configuration import Configuration


def test_t_30_2():
    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)
    errors = {}

    try:
        config.get_deposit_profile("")
    except AlmaValidationError as e:
        errors["get_deposit_empty"] = e

    try:
        config.get_deposit_profile("   ")
    except AlmaValidationError as e:
        errors["get_deposit_whitespace"] = e

    try:
        config.get_deposit_profile(None)
    except AlmaValidationError as e:
        errors["get_deposit_none"] = e

    try:
        config.get_deposit_profile(123)
    except AlmaValidationError as e:
        errors["get_deposit_nonstring"] = e

    try:
        config.get_import_profile("")
    except AlmaValidationError as e:
        errors["get_import_empty"] = e

    try:
        config.get_import_profile("   ")
    except AlmaValidationError as e:
        errors["get_import_whitespace"] = e

    try:
        config.get_import_profile(None)
    except AlmaValidationError as e:
        errors["get_import_none"] = e

    try:
        config.get_import_profile(123)
    except AlmaValidationError as e:
        errors["get_import_nonstring"] = e

    assert "get_deposit_empty" in errors and isinstance(
        errors["get_deposit_empty"], AlmaValidationError
    )
    assert "get_deposit_whitespace" in errors and isinstance(
        errors["get_deposit_whitespace"], AlmaValidationError
    )
    assert "get_deposit_none" in errors and isinstance(
        errors["get_deposit_none"], AlmaValidationError
    )
    assert "get_deposit_nonstring" in errors and isinstance(
        errors["get_deposit_nonstring"], AlmaValidationError
    )
    assert "get_import_empty" in errors and isinstance(
        errors["get_import_empty"], AlmaValidationError
    )
    assert "get_import_whitespace" in errors and isinstance(
        errors["get_import_whitespace"], AlmaValidationError
    )
    assert "get_import_none" in errors and isinstance(
        errors["get_import_none"], AlmaValidationError
    )
    assert "get_import_nonstring" in errors and isinstance(
        errors["get_import_nonstring"], AlmaValidationError
    )
