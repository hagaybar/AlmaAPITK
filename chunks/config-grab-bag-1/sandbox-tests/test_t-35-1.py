"""Generated SANDBOX test t-35-1 - Configuration workflows runner +
utilities read smoke (issue #35).

Maps to AC #35 facets:
  - Each new read method exercised against live SANDBOX
    (``get_general_configuration`` / ``get_fee_transactions_report``).
  - Happy-path AlmaAPIError propagation (no error raised).

Calls the read-only utility methods shipped in issue #35 against live
SANDBOX. ``get_general_configuration()`` (no params) confirms the
``GET /almaws/v1/conf/general`` endpoint round-trips and returns a
non-empty ``Dict[str, Any]`` of institution settings;
``get_fee_transactions_report()`` (no kwargs) confirms
``GET /almaws/v1/conf/utilities/fee-transactions`` round-trips and
returns a ``List[Dict]`` envelope (successfully unwrapped from Alma's
response shape).

No state is mutated and no workflows are executed — this is a pure read
smoke. The POST path (``run_workflow``) is intentionally NOT exercised
here; live workflow execution against SANDBOX was not authorized by the
operator (no known-safe ``workflow_id`` designated). ``run_workflow``
validation guards are exercised by t-35-2.

DO NOT EDIT by hand. Generated from
``chunks/config-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration


def test_t_35_1():
    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # --- get_general_configuration ---------------------------------------
    general_config = config.get_general_configuration()
    assert isinstance(general_config, dict)
    assert len(general_config) > 0

    # --- get_fee_transactions_report (no filters) ------------------------
    fee_transactions = config.get_fee_transactions_report()
    assert isinstance(fee_transactions, list)
