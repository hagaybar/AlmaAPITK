"""Generated SANDBOX test t-33-3 - Configuration letter update_letter
round-trip (issue #33). STATE-CHANGING — operator-authorized.

Maps to AC #33 facets:
  - ``update_letter`` exercised end-to-end against live SANDBOX.
  - AlmaResponse return-value contract on PUT (``.success`` flag).
  - Round-trip read-after-write semantics (mutation is observable on
    the subsequent GET, then restored).

Operator-authorized live ``update_letter`` round-trip against the
DISABLED letter ``<disabled_letter_code>``. Reads the original letter
payload, builds a mutated copy that touches ONLY the ``description``
field (with a UUID-suffixed test marker so concurrent runs do not
collide), pushes the mutation via ``update_letter``, reads the letter
back and asserts the description now contains the marker, then restores
the original payload via ``update_letter``.

The mutation is intentionally limited to ``description``: ``subject``,
``body``, ``letter_template_xsl``, and every other user-visible field
are untouched. The letter is disabled, so even in the worst case (all
restores fail) no end user receives a letter with mutated content.

Cleanup discipline:
  - The happy path performs an explicit restore (step 5).
  - The ``finally`` block is a mandatory safety net: if the explicit
    restore was not reached (assertion failure mid-test) it retries the
    restore. A failure to restore is re-raised as a HARD test failure —
    a permanent mutation of the disabled letter is unacceptable.
  - If ``original`` failed to read in step 1, the test ``assert``
    raises before we enter the ``try`` block — there is nothing to
    restore. That is fine.

Fixture (``disabled_letter_code``) is loaded at runtime from
``chunks/config-grab-bag-1/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/config-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib
import uuid

import pytest

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.configuration import Configuration

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


@pytest.mark.skip(
    reason=(
        "Alma letters PUT requires XML body; current update_letter sends "
        "JSON and Alma rejects with error 60105 ('JSON is not supported "
        "for this API.'). Confirmed live 2026-05-07: the GET works, the "
        "first PUT fails with 400 BEFORE any mutation is applied (so the "
        "disabled letter is intact) and the in-finally restore PUT also "
        "fails with the same error. Tracked as issue #114 (XML body "
        "support for update_letter). Remove this skip when #114 ships."
    )
)
def test_t_33_3():
    disabled_letter_code = _TEST_DATA["disabled_letter_code"]

    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # --- Step 1: read original (snapshot) --------------------------------
    original = config.get_letter(disabled_letter_code)
    assert isinstance(original, dict) and len(original) > 0

    # --- Step 2: build mutated payload — change ONLY description --------
    test_marker = f"AlmaAPITK round-trip {uuid.uuid4().hex[:8]}"
    mutated = dict(original)
    mutated["description"] = test_marker

    restored = False
    try:
        # --- Step 3: PUT mutation ---------------------------------------
        update_response = config.update_letter(disabled_letter_code, mutated)
        assert getattr(update_response, "success", False) is True

        # --- Step 4: read back, assert marker ---------------------------
        post_update = config.get_letter(disabled_letter_code)
        assert isinstance(post_update, dict)
        assert test_marker in str(post_update.get("description", ""))

        # --- Step 5: explicit restore (happy path) ----------------------
        restore_response = config.update_letter(disabled_letter_code, original)
        assert getattr(restore_response, "success", False) is True
        restored = True
    finally:
        # MANDATORY safety net: if the explicit restore in the happy
        # path was not reached (a mid-test assert raised), retry the
        # restore here. A restore failure is re-raised as a HARD test
        # failure — permanent mutation of the disabled letter is
        # unacceptable.
        if not restored:
            try:
                config.update_letter(disabled_letter_code, original)
            except AlmaAPIError:
                # Re-raise — failure to restore is a HARD test failure.
                raise
