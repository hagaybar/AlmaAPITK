"""Generated SANDBOX test t-30-1 - Configuration deposit + import profiles
read smoke (issue #30).

Maps to AC #30 facets:
  - Each new read method exercised against live SANDBOX
    (``list_deposit_profiles`` / ``list_import_profiles`` /
    ``get_import_profile``).
  - Happy-path AlmaAPIError propagation (no error raised).

Calls the read-only profile methods shipped in issue #30 that have an
operator-supplied fixture available. Confirms ``list_deposit_profiles()``
and ``list_import_profiles()`` return ``List[Dict]`` envelopes
(successfully unwrapped from Alma's response shape) and
``get_import_profile(<existing_import_profile_id>)`` round-trips a known
import-profile id with a non-empty dict.

NOTE: ``get_deposit_profile()`` is intentionally NOT exercised against
SANDBOX here — the operator deferred deposit-profile fixture to a later
run. ``list_deposit_profiles()`` is still called to confirm the list
endpoint at least responds. No state is mutated.

Fixture (``existing_import_profile_id``) is loaded at runtime from
``chunks/config-grab-bag-1/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/config-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_30_1():
    existing_import_profile_id = _TEST_DATA["existing_import_profile_id"]

    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # --- list_deposit_profiles -------------------------------------------
    deposit_profiles = config.list_deposit_profiles()
    assert isinstance(deposit_profiles, list)

    # --- list_import_profiles --------------------------------------------
    import_profiles = config.list_import_profiles()
    assert isinstance(import_profiles, list)

    # --- get_import_profile (round-trip on existing id) -------------------
    import_profile = config.get_import_profile(existing_import_profile_id)
    assert isinstance(import_profile, dict)
    assert len(import_profile) > 0
