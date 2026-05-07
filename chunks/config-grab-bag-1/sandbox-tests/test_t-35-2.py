"""Generated SANDBOX test t-35-2 - Configuration run_workflow validation
smoke (issue #35).

Maps to AC #35:
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- input-validation half.

Confirms every input-validation guard added in issue #35 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises
``Configuration._validate_code`` through ``run_workflow`` with empty,
whitespace-only, ``None``, and non-string ``workflow_id`` values.

``get_general_configuration`` and ``get_fee_transactions_report`` take
no required arguments so have no validation surface and are not
exercised here.

Pure runtime guard exercise; no SANDBOX state is read or mutated and
NO workflows are executed (the validation guards reject every input
before any POST is dispatched).

DO NOT EDIT by hand. Generated from
``chunks/config-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.configuration import Configuration


def test_t_35_2():
    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)
    errors = {}

    try:
        config.run_workflow("")
    except AlmaValidationError as e:
        errors["run_workflow_empty"] = e

    try:
        config.run_workflow("   ")
    except AlmaValidationError as e:
        errors["run_workflow_whitespace"] = e

    try:
        config.run_workflow(None)
    except AlmaValidationError as e:
        errors["run_workflow_none"] = e

    try:
        config.run_workflow(123)
    except AlmaValidationError as e:
        errors["run_workflow_nonstring"] = e

    assert "run_workflow_empty" in errors and isinstance(
        errors["run_workflow_empty"], AlmaValidationError
    )
    assert "run_workflow_whitespace" in errors and isinstance(
        errors["run_workflow_whitespace"], AlmaValidationError
    )
    assert "run_workflow_none" in errors and isinstance(
        errors["run_workflow_none"], AlmaValidationError
    )
    assert "run_workflow_nonstring" in errors and isinstance(
        errors["run_workflow_nonstring"], AlmaValidationError
    )
