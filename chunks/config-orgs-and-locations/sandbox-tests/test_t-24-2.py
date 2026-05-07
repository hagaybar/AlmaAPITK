"""Generated SANDBOX test t-24-2 - Configuration org-units validation smoke
(issue #24).

Maps to AC #24:
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- input-validation half.

Confirms every input-validation guard added in issue #24 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises
``Configuration._validate_code`` through every public entry point that
takes a path-parameter code: ``get_library``, ``list_circ_desks``,
``get_circ_desk``. ``list_libraries`` and ``list_departments`` take no
arguments so have no validation surface and are not exercised here.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
chunks/config-orgs-and-locations/test-recommendation.json.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.configuration import Configuration


def test_t_24_2():
    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)
    errors = {}

    try:
        config.get_library("")
    except AlmaValidationError as e:
        errors["get_library_empty"] = e

    try:
        config.get_library("   ")
    except AlmaValidationError as e:
        errors["get_library_whitespace"] = e

    try:
        config.get_library(None)
    except AlmaValidationError as e:
        errors["get_library_none"] = e

    try:
        config.get_library(123)
    except AlmaValidationError as e:
        errors["get_library_nonstring"] = e

    try:
        config.list_circ_desks("")
    except AlmaValidationError as e:
        errors["list_circ_desks_empty"] = e

    try:
        config.list_circ_desks(None)
    except AlmaValidationError as e:
        errors["list_circ_desks_none"] = e

    try:
        config.get_circ_desk("", "x")
    except AlmaValidationError as e:
        errors["get_circ_desk_empty_lib"] = e

    try:
        config.get_circ_desk("LIB", "")
    except AlmaValidationError as e:
        errors["get_circ_desk_empty_desk"] = e

    try:
        config.get_circ_desk(None, None)
    except AlmaValidationError as e:
        errors["get_circ_desk_both_none"] = e

    assert "get_library_empty" in errors and isinstance(
        errors["get_library_empty"], AlmaValidationError
    )
    assert "get_library_whitespace" in errors and isinstance(
        errors["get_library_whitespace"], AlmaValidationError
    )
    assert "get_library_none" in errors and isinstance(
        errors["get_library_none"], AlmaValidationError
    )
    assert "get_library_nonstring" in errors and isinstance(
        errors["get_library_nonstring"], AlmaValidationError
    )
    assert "list_circ_desks_empty" in errors and isinstance(
        errors["list_circ_desks_empty"], AlmaValidationError
    )
    assert "list_circ_desks_none" in errors and isinstance(
        errors["list_circ_desks_none"], AlmaValidationError
    )
    assert "get_circ_desk_empty_lib" in errors and isinstance(
        errors["get_circ_desk_empty_lib"], AlmaValidationError
    )
    assert "get_circ_desk_empty_desk" in errors and isinstance(
        errors["get_circ_desk_empty_desk"], AlmaValidationError
    )
    assert "get_circ_desk_both_none" in errors and isinstance(
        errors["get_circ_desk_both_none"], AlmaValidationError
    )
