"""Generated SANDBOX test t-26-1 - Configuration code-tables read smoke
(issue #26).

Maps to AC #26 facets:
  - Each new read method exercised against live SANDBOX
    (``list_code_tables`` / ``get_code_table``).
  - ``list_code_tables()`` takes no ``scope`` parameter (or any other
    undocumented filter) — observed at runtime by calling it with no
    arguments.
  - Happy-path AlmaAPIError propagation (no error raised).

Calls every read-only code-table method shipped in issue #26 against
live SANDBOX. Confirms ``list_code_tables()`` returns a list (the Alma
envelope ``{"code_table": [...], "total_record_count": N}`` is
unwrapped) and that ``get_code_table`` round-trips a known
institution-wide code-table name. No state is mutated and no tables are
created -- pure read smoke. The PUT path (``update_code_table``) is
intentionally NOT exercised here (institutional config; not safe to
mutate in shared SANDBOX).

``Configuration.get_code_table`` returns the unwrapped Alma response
dict directly (see ``src/almaapitk/domains/configuration.py``). The
table's individual entries live at the top-level ``row`` key (singular)
-- NOT wrapped in ``rows.row`` -- so we additionally assert ``"row"``
exists and is a list to lock that response shape.

The ``name`` field can come back as a bare string OR as a
``{"value": "...", "desc": "..."}`` dict shape; both are accepted below
to mirror Alma's response asymmetry.

Fixtures (``existing_code_table_name``) are loaded at runtime from
``chunks/config-tables/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/config-tables/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def _name_matches(record, expected_name):
    """Return True if ``record['name']`` matches ``expected_name``.

    Alma sometimes returns ``name`` as a bare string and sometimes as
    ``{"value": "...", "desc": "..."}``; accept either shape (and a
    final fallback that scans string-valued fields, mirroring the
    pythonCalls passCriteria in the recommendation).
    """
    if not isinstance(record, dict):
        return False
    raw = record.get("name")
    if raw == expected_name:
        return True
    if isinstance(raw, dict) and raw.get("value") == expected_name:
        return True
    return any(
        isinstance(v, str) and v == expected_name
        for v in record.values()
    )


def test_t_26_1():
    existing_code_table_name = _TEST_DATA["existing_code_table_name"]

    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # --- list_code_tables -------------------------------------------------
    # Implicit invariant: the call signature exposes no ``scope`` arg.
    code_tables = config.list_code_tables()
    assert isinstance(code_tables, list)

    # --- get_code_table (round-trip on existing_code_table_name) ----------
    code_table = config.get_code_table(existing_code_table_name)
    assert isinstance(code_table, dict) and len(code_table) > 0
    assert _name_matches(code_table, existing_code_table_name)

    # Lock the response shape: entries live at top-level ``row`` (singular),
    # NOT wrapped in ``rows.row``. See get_code_table docstring.
    assert "row" in code_table
    assert isinstance(code_table["row"], list)
