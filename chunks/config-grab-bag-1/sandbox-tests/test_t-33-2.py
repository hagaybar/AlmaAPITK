"""Generated SANDBOX test t-33-2 - Configuration letters + printers
validation smoke (issue #33).

Maps to AC #33:
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- input-validation half.

Confirms every input-validation guard added in issue #33 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises:
  - ``Configuration._validate_code`` through ``get_letter`` (empty,
    whitespace, ``None``, non-string).
  - ``update_letter`` path-parameter guard via ``update_letter('', {...})``
    and ``update_letter(None, {...})``.
  - ``update_letter`` body guard via ``update_letter('CODE', None)``,
    ``update_letter('CODE', {})``, and ``update_letter('CODE', 'not-a-dict')``.
  - ``Configuration._validate_code`` through ``get_printer`` (empty,
    whitespace, ``None``, non-string).

``list_letters`` / ``list_printers`` take no arguments so have no
validation surface and are not exercised here.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
``chunks/config-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.configuration import Configuration


def test_t_33_2():
    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)
    errors = {}

    # --- get_letter validation -------------------------------------------
    try:
        config.get_letter("")
    except AlmaValidationError as e:
        errors["get_letter_empty"] = e

    try:
        config.get_letter("   ")
    except AlmaValidationError as e:
        errors["get_letter_whitespace"] = e

    try:
        config.get_letter(None)
    except AlmaValidationError as e:
        errors["get_letter_none"] = e

    try:
        config.get_letter(123)
    except AlmaValidationError as e:
        errors["get_letter_nonstring"] = e

    # --- update_letter path-parameter guard ------------------------------
    try:
        config.update_letter("", {"description": "X"})
    except AlmaValidationError as e:
        errors["update_letter_empty_code"] = e

    try:
        config.update_letter(None, {"description": "X"})
    except AlmaValidationError as e:
        errors["update_letter_none_code"] = e

    # --- update_letter body guard ----------------------------------------
    try:
        config.update_letter("CODE", None)
    except AlmaValidationError as e:
        errors["update_letter_none_body"] = e

    try:
        config.update_letter("CODE", {})
    except AlmaValidationError as e:
        errors["update_letter_empty_body"] = e

    try:
        config.update_letter("CODE", "not-a-dict")
    except AlmaValidationError as e:
        errors["update_letter_nondict_body"] = e

    # --- get_printer validation ------------------------------------------
    try:
        config.get_printer("")
    except AlmaValidationError as e:
        errors["get_printer_empty"] = e

    try:
        config.get_printer("   ")
    except AlmaValidationError as e:
        errors["get_printer_whitespace"] = e

    try:
        config.get_printer(None)
    except AlmaValidationError as e:
        errors["get_printer_none"] = e

    try:
        config.get_printer(123)
    except AlmaValidationError as e:
        errors["get_printer_nonstring"] = e

    # --- assertions ------------------------------------------------------
    assert "get_letter_empty" in errors and isinstance(
        errors["get_letter_empty"], AlmaValidationError
    )
    assert "get_letter_whitespace" in errors and isinstance(
        errors["get_letter_whitespace"], AlmaValidationError
    )
    assert "get_letter_none" in errors and isinstance(
        errors["get_letter_none"], AlmaValidationError
    )
    assert "get_letter_nonstring" in errors and isinstance(
        errors["get_letter_nonstring"], AlmaValidationError
    )
    assert "update_letter_empty_code" in errors and isinstance(
        errors["update_letter_empty_code"], AlmaValidationError
    )
    assert "update_letter_none_code" in errors and isinstance(
        errors["update_letter_none_code"], AlmaValidationError
    )
    assert "update_letter_none_body" in errors and isinstance(
        errors["update_letter_none_body"], AlmaValidationError
    )
    assert "update_letter_empty_body" in errors and isinstance(
        errors["update_letter_empty_body"], AlmaValidationError
    )
    assert "update_letter_nondict_body" in errors and isinstance(
        errors["update_letter_nondict_body"], AlmaValidationError
    )
    assert "get_printer_empty" in errors and isinstance(
        errors["get_printer_empty"], AlmaValidationError
    )
    assert "get_printer_whitespace" in errors and isinstance(
        errors["get_printer_whitespace"], AlmaValidationError
    )
    assert "get_printer_none" in errors and isinstance(
        errors["get_printer_none"], AlmaValidationError
    )
    assert "get_printer_nonstring" in errors and isinstance(
        errors["get_printer_nonstring"], AlmaValidationError
    )
