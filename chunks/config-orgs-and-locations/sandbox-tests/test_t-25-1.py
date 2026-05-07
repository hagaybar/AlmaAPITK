"""Generated SANDBOX test t-25-1 - Configuration locations CRUD round-trip
(issue #25).

Maps to AC #25:
  - Each new CRUD method exercised against live SANDBOX
    (create_location / get_location / list_locations / update_location /
    delete_location).
  - "Errors raise ``AlmaValidationError`` (input) or ``AlmaAPIError`` /
    subclass (API)." -- the API-error half (post-delete get_location
    raises ``AlmaAPIError``).
  - Round-trip flow: create -> get -> list -> update -> get -> delete ->
    confirm gone.

Drives the full locations CRUD round-trip end-to-end against live
SANDBOX. Generates a UUID-suffixed location code so concurrent runs do
not collide, creates a location inside ``target_library_code`` with a
minimal valid payload, reads it back, lists and confirms the new code
is present, mutates the name and pushes via update_location, reads
again to confirm the rename landed, then deletes and confirms a
follow-up get_location raises AlmaAPIError. Cleanup runs delete_location
in a try/finally so a partially-created location is always torn down
even on assertion failure.

Configuration.get_location returns the unwrapped Alma response dict
directly (raw ``code`` / ``name`` keys). ``create_location`` /
``update_location`` / ``delete_location`` each return an
``AlmaResponse`` whose ``.success`` flag is asserted below.

Fixture (target_library_code) is loaded at runtime from
chunks/config-orgs-and-locations/test-data.json so that no
operator-supplied identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
chunks/config-orgs-and-locations/test-recommendation.json.
"""
from __future__ import annotations

import json
import pathlib
import uuid

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.configuration import Configuration

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def _code_matches(record, expected_code):
    """Return True if ``record['code']`` matches ``expected_code``.

    Alma returns ``code`` either as a bare string or as
    ``{"value": "...", "desc": "..."}``; accept both shapes.
    """
    if not isinstance(record, dict):
        return False
    raw = record.get("code")
    if raw == expected_code:
        return True
    if isinstance(raw, dict) and raw.get("value") == expected_code:
        return True
    return False


def _listing_contains_code(listing, expected_code):
    """Return True if any entry in ``listing`` has the given code."""
    if not isinstance(listing, list):
        return False
    for loc in listing:
        if not isinstance(loc, dict):
            continue
        raw = loc.get("code")
        if isinstance(raw, dict):
            raw = raw.get("value")
        if isinstance(raw, str) and raw == expected_code:
            return True
    return False


def test_t_25_1():
    target_library_code = _TEST_DATA["target_library_code"]

    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # Generate a fresh location code at runtime so concurrent runs do
    # not collide.
    new_location_code = f"TKLOC{uuid.uuid4().hex[:8].upper()}"
    create_payload = {
        "code": new_location_code,
        "name": f"almaapitk chunk-25 round-trip location {new_location_code}",
        "type": {"value": "OPEN"},
        "external_name": f"almaapitk chunk-25 location {new_location_code}",
        "description": "almaapitk chunk-25 round-trip location (auto-cleanup)",
    }

    # Track whether the happy-path delete already removed the location.
    location_exists = False

    try:
        # --- create -------------------------------------------------------
        create_response = config.create_location(target_library_code, create_payload)
        assert create_response is not None
        assert getattr(create_response, "success", False) is True
        location_exists = True

        # --- get (post-create) -------------------------------------------
        post_create_get = config.get_location(target_library_code, new_location_code)
        assert isinstance(post_create_get, dict) and len(post_create_get) > 0
        assert _code_matches(post_create_get, new_location_code)

        # --- list (post-create) ------------------------------------------
        post_create_listing = config.list_locations(target_library_code)
        assert isinstance(post_create_listing, list)
        assert _listing_contains_code(post_create_listing, new_location_code) is True

        # --- update (rename) ---------------------------------------------
        # Use the original create_payload as the basis, NOT post_create_get.
        # Alma's GET response echoes some fields (e.g. accession_placement)
        # as {"value": "...", "desc": "..."} dicts, but PUT's validator
        # rejects that shape and demands a bare string. Building the update
        # off create_payload (which Alma accepted on POST) avoids the
        # GET-to-PUT asymmetry entirely.
        update_payload = dict(create_payload)
        update_payload["name"] = (
            f"almaapitk chunk-25 location {new_location_code} (renamed)"
        )
        update_response = config.update_location(
            target_library_code, new_location_code, update_payload
        )
        assert getattr(update_response, "success", False) is True

        # --- get (post-update) -------------------------------------------
        post_update_get = config.get_location(target_library_code, new_location_code)
        post_update_name = (
            post_update_get.get("name") if isinstance(post_update_get, dict) else None
        )
        assert isinstance(post_update_name, str) and "renamed" in post_update_name.lower()

        # --- delete -------------------------------------------------------
        delete_response = config.delete_location(target_library_code, new_location_code)
        assert getattr(delete_response, "success", False) is True
        # Happy path deleted the location; cleanup branch becomes a no-op.
        location_exists = False

        # --- get (post-delete) -- must raise AlmaAPIError ----------------
        post_delete_error = None
        try:
            config.get_location(target_library_code, new_location_code)
        except AlmaAPIError as e:
            post_delete_error = e
        assert post_delete_error is not None
        assert isinstance(post_delete_error, AlmaAPIError)

    finally:
        # Mandatory cleanup: if anything above failed after create, tear
        # down the residual location. Re-raise unexpected cleanup errors
        # so a true cleanup failure surfaces as a test failure; ignore
        # the "already deleted" / "never created" 4xx (per the
        # recommendation's cleanup block).
        if location_exists:
            try:
                config.delete_location(target_library_code, new_location_code)
            except AlmaAPIError:
                # Location already deleted by the happy path or never
                # successfully created -- safe to ignore.
                pass
