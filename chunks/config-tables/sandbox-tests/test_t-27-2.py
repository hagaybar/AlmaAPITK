"""Generated SANDBOX test t-27-2 - Configuration mapping-tables validation
smoke (issue #27).

Maps to AC #27:
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- input-validation half.

Confirms every input-validation guard added in issue #27 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises
``Configuration._validate_code`` through ``get_mapping_table`` (empty,
whitespace, ``None``, non-string) and the ``update_mapping_table``
guards (name guard via empty / ``None``; body guard via ``None`` /
empty dict / non-dict). ``list_mapping_tables`` takes no arguments so
has no validation surface and is not exercised here.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
``chunks/config-tables/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.configuration import Configuration


def test_t_27_2():
    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)
    errors = {}

    try:
        config.get_mapping_table("")
    except AlmaValidationError as e:
        errors["get_empty"] = e

    try:
        config.get_mapping_table("   ")
    except AlmaValidationError as e:
        errors["get_whitespace"] = e

    try:
        config.get_mapping_table(None)
    except AlmaValidationError as e:
        errors["get_none"] = e

    try:
        config.get_mapping_table(123)
    except AlmaValidationError as e:
        errors["get_nonstring"] = e

    try:
        config.update_mapping_table("", {"name": "X"})
    except AlmaValidationError as e:
        errors["update_empty_name"] = e

    try:
        config.update_mapping_table(None, {"name": "X"})
    except AlmaValidationError as e:
        errors["update_none_name"] = e

    try:
        config.update_mapping_table("NAME", None)
    except AlmaValidationError as e:
        errors["update_none_body"] = e

    try:
        config.update_mapping_table("NAME", {})
    except AlmaValidationError as e:
        errors["update_empty_body"] = e

    try:
        config.update_mapping_table("NAME", "not-a-dict")
    except AlmaValidationError as e:
        errors["update_nondict_body"] = e

    assert "get_empty" in errors and isinstance(
        errors["get_empty"], AlmaValidationError
    )
    assert "get_whitespace" in errors and isinstance(
        errors["get_whitespace"], AlmaValidationError
    )
    assert "get_none" in errors and isinstance(
        errors["get_none"], AlmaValidationError
    )
    assert "get_nonstring" in errors and isinstance(
        errors["get_nonstring"], AlmaValidationError
    )
    assert "update_empty_name" in errors and isinstance(
        errors["update_empty_name"], AlmaValidationError
    )
    assert "update_none_name" in errors and isinstance(
        errors["update_none_name"], AlmaValidationError
    )
    assert "update_none_body" in errors and isinstance(
        errors["update_none_body"], AlmaValidationError
    )
    assert "update_empty_body" in errors and isinstance(
        errors["update_empty_body"], AlmaValidationError
    )
    assert "update_nondict_body" in errors and isinstance(
        errors["update_nondict_body"], AlmaValidationError
    )
