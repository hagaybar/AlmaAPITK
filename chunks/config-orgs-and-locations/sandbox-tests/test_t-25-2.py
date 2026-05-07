"""Generated SANDBOX test t-25-2 - Configuration locations CRUD validation
smoke (issue #25).

Maps to AC #25:
  - "Location creation validates required fields (code, name, type)
    before sending to API."
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- input-validation half.

Confirms every input-validation guard added in issue #25 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises:
  - ``Configuration._validate_code`` on every CRUD path-parameter entry
    point (``list_locations`` / ``get_location`` / ``create_location`` /
    ``update_location`` / ``delete_location``).
  - ``Configuration._validate_location_data_for_create`` on the
    ``create_location`` payload (None / empty / missing code / missing
    name / missing type / empty type.value / empty code / empty name).
  - ``update_location``'s body guard (empty / None body).

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
chunks/config-orgs-and-locations/test-recommendation.json.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.configuration import Configuration


def test_t_25_2():
    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)
    errors = {}

    try:
        config.list_locations("")
    except AlmaValidationError as e:
        errors["list_empty_lib"] = e

    try:
        config.get_location("", "X")
    except AlmaValidationError as e:
        errors["get_empty_lib"] = e

    try:
        config.get_location("LIB", "")
    except AlmaValidationError as e:
        errors["get_empty_loc"] = e

    try:
        config.create_location("", {"code": "X", "name": "Y", "type": {"value": "OPEN"}})
    except AlmaValidationError as e:
        errors["create_empty_lib"] = e

    try:
        config.create_location("LIB", None)
    except AlmaValidationError as e:
        errors["create_none_payload"] = e

    try:
        config.create_location("LIB", {})
    except AlmaValidationError as e:
        errors["create_empty_payload"] = e

    try:
        config.create_location("LIB", {"name": "Y", "type": {"value": "OPEN"}})
    except AlmaValidationError as e:
        errors["create_no_code"] = e

    try:
        config.create_location("LIB", {"code": "X", "type": {"value": "OPEN"}})
    except AlmaValidationError as e:
        errors["create_no_name"] = e

    try:
        config.create_location("LIB", {"code": "X", "name": "Y"})
    except AlmaValidationError as e:
        errors["create_no_type"] = e

    try:
        config.create_location("LIB", {"code": "X", "name": "Y", "type": {"value": ""}})
    except AlmaValidationError as e:
        errors["create_empty_type_value"] = e

    try:
        config.create_location("LIB", {"code": "", "name": "Y", "type": {"value": "OPEN"}})
    except AlmaValidationError as e:
        errors["create_empty_code"] = e

    try:
        config.create_location("LIB", {"code": "X", "name": "", "type": {"value": "OPEN"}})
    except AlmaValidationError as e:
        errors["create_empty_name"] = e

    try:
        config.update_location("", "X", {"name": "Y"})
    except AlmaValidationError as e:
        errors["update_empty_lib"] = e

    try:
        config.update_location("LIB", "", {"name": "Y"})
    except AlmaValidationError as e:
        errors["update_empty_loc"] = e

    try:
        config.update_location("LIB", "X", {})
    except AlmaValidationError as e:
        errors["update_empty_body"] = e

    try:
        config.update_location("LIB", "X", None)
    except AlmaValidationError as e:
        errors["update_none_body"] = e

    try:
        config.delete_location("", "X")
    except AlmaValidationError as e:
        errors["delete_empty_lib"] = e

    try:
        config.delete_location("LIB", "")
    except AlmaValidationError as e:
        errors["delete_empty_loc"] = e

    assert "list_empty_lib" in errors and isinstance(
        errors["list_empty_lib"], AlmaValidationError
    )
    assert "get_empty_lib" in errors and isinstance(
        errors["get_empty_lib"], AlmaValidationError
    )
    assert "get_empty_loc" in errors and isinstance(
        errors["get_empty_loc"], AlmaValidationError
    )
    assert "create_empty_lib" in errors and isinstance(
        errors["create_empty_lib"], AlmaValidationError
    )
    assert "create_none_payload" in errors and isinstance(
        errors["create_none_payload"], AlmaValidationError
    )
    assert "create_empty_payload" in errors and isinstance(
        errors["create_empty_payload"], AlmaValidationError
    )
    assert "create_no_code" in errors and isinstance(
        errors["create_no_code"], AlmaValidationError
    )
    assert "create_no_name" in errors and isinstance(
        errors["create_no_name"], AlmaValidationError
    )
    assert "create_no_type" in errors and isinstance(
        errors["create_no_type"], AlmaValidationError
    )
    assert "create_empty_type_value" in errors and isinstance(
        errors["create_empty_type_value"], AlmaValidationError
    )
    assert "create_empty_code" in errors and isinstance(
        errors["create_empty_code"], AlmaValidationError
    )
    assert "create_empty_name" in errors and isinstance(
        errors["create_empty_name"], AlmaValidationError
    )
    assert "update_empty_lib" in errors and isinstance(
        errors["update_empty_lib"], AlmaValidationError
    )
    assert "update_empty_loc" in errors and isinstance(
        errors["update_empty_loc"], AlmaValidationError
    )
    assert "update_empty_body" in errors and isinstance(
        errors["update_empty_body"], AlmaValidationError
    )
    assert "update_none_body" in errors and isinstance(
        errors["update_none_body"], AlmaValidationError
    )
    assert "delete_empty_lib" in errors and isinstance(
        errors["delete_empty_lib"], AlmaValidationError
    )
    assert "delete_empty_loc" in errors and isinstance(
        errors["delete_empty_loc"], AlmaValidationError
    )
