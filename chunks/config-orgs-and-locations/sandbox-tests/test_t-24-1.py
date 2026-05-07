"""Generated SANDBOX test t-24-1 - Configuration org-units read smoke (issue #24).

Maps to AC #24 facets:
  - Each new method exercised against live SANDBOX
    (list_libraries / get_library / list_departments /
    list_circ_desks / get_circ_desk).
  - Happy-path AlmaAPIError propagation (no error raised).

Calls every read-only org-unit method shipped in issue #24 against live
SANDBOX. Confirms list_libraries() and list_departments() return list
envelopes, that get_library round-trips a known library code, that
list_circ_desks returns a list scoped to the target library, and that
get_circ_desk round-trips a known per-library/per-desk lookup. No state
is mutated and no new entities are created -- pure read smoke.

Configuration.get_library and Configuration.get_circ_desk return the
unwrapped Alma response dict directly (see
``src/almaapitk/domains/configuration.py``), so the raw Alma keys
(``code``) are the right names. The ``code`` field can come back as a
bare string OR as a ``{"value": "...", "desc": "..."}`` dict shape;
both are accepted below to mirror Alma's response asymmetry.

Fixtures (existing_library_code, target_library_code,
existing_circ_desk_code) are loaded at runtime from
chunks/config-orgs-and-locations/test-data.json so that no
operator-supplied identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
chunks/config-orgs-and-locations/test-recommendation.json.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def _code_matches(record, expected_code):
    """Return True if ``record['code']`` matches ``expected_code``.

    Alma sometimes returns ``code`` as a bare string and sometimes as
    ``{"value": "...", "desc": "..."}``; accept either shape (and a
    final fallback that scans string-valued fields, mirroring the
    pythonCalls passCriteria in the recommendation).
    """
    if not isinstance(record, dict):
        return False
    raw = record.get("code")
    if raw == expected_code:
        return True
    if isinstance(raw, dict) and raw.get("value") == expected_code:
        return True
    return any(
        isinstance(v, str) and v == expected_code
        for v in record.values()
    )


def test_t_24_1():
    existing_library_code = _TEST_DATA["existing_library_code"]
    target_library_code = _TEST_DATA["target_library_code"]
    existing_circ_desk_code = _TEST_DATA["existing_circ_desk_code"]

    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # --- list_libraries ---------------------------------------------------
    libraries = config.list_libraries()
    assert isinstance(libraries, list)

    # --- list_departments -------------------------------------------------
    departments = config.list_departments()
    assert isinstance(departments, list)

    # --- get_library (round-trip on existing_library_code) ----------------
    library = config.get_library(existing_library_code)
    assert isinstance(library, dict) and len(library) > 0
    assert _code_matches(library, existing_library_code)

    # --- list_circ_desks --------------------------------------------------
    circ_desks = config.list_circ_desks(target_library_code)
    assert isinstance(circ_desks, list)

    # --- get_circ_desk (round-trip on existing_circ_desk_code) ------------
    circ_desk = config.get_circ_desk(target_library_code, existing_circ_desk_code)
    assert isinstance(circ_desk, dict) and len(circ_desk) > 0
    assert _code_matches(circ_desk, existing_circ_desk_code)
