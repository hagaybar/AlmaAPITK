"""Generated SANDBOX test t-33-1 - Configuration letters + printers read
smoke (issue #33).

Maps to AC #33 facets:
  - Each new read method exercised against live SANDBOX
    (``list_letters`` / ``get_letter`` / ``list_printers``).
  - Happy-path AlmaAPIError propagation (no error raised).

Calls the read-only letter and printer methods shipped in issue #33 that
have an operator-supplied fixture available. Confirms ``list_letters()``
and ``list_printers()`` return ``List[Dict]`` envelopes (successfully
unwrapped from Alma's response shape) and
``get_letter(<disabled_letter_code>)`` round-trips a known letter code
on the operator-designated DISABLED letter (the same fixture used by
t-33-3 for its round-trip mutation) returning a non-empty dict.

NOTE: ``get_printer()`` is intentionally NOT exercised against SANDBOX
here — the operator deferred printer fixture to a later run.
``list_printers()`` is still called to confirm the list endpoint at
least responds. The PUT path (``update_letter``) is exercised
end-to-end by t-33-3.

Fixture (``disabled_letter_code``) is loaded at runtime from
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


def test_t_33_1():
    disabled_letter_code = _TEST_DATA["disabled_letter_code"]

    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # --- list_letters -----------------------------------------------------
    letters = config.list_letters()
    assert isinstance(letters, list)

    # --- get_letter (round-trip on disabled letter code) ------------------
    letter = config.get_letter(disabled_letter_code)
    assert isinstance(letter, dict)
    assert len(letter) > 0

    # --- list_printers ----------------------------------------------------
    printers = config.list_printers()
    assert isinstance(printers, list)
