"""Generated SANDBOX test t-36-1 - Users list & search read smoke
(issue #36).

Maps to AC #36 facets:
  - ``list_users`` exposes ``limit`` (and other) kwargs and forwards
    them only when provided -- ``limit=5`` passthrough is observable
    here.
  - ``search_users(query, limit)`` is a thin wrapper over ``list_users``
    and returns just the ``user`` array -- echo-back via
    ``primary_id~<value>`` confirms the supplied user is in the result.
  - ``get_user_personal_data(user_id)`` calls
    ``GET /almaws/v1/users/{user_id}/personal-data`` and returns the
    body -- non-empty dict assertion locks the response shape.
  - "At least one SANDBOX integration test for ``list_users`` and one
    for ``get_user_personal_data``." -- both exercised here.

Calls every read-only method shipped in issue #36 against live SANDBOX:

  1. ``list_users(limit=5)`` -- the Alma envelope
     ``{"user": [...], "total_record_count": N}`` is unwrapped by the
     domain helper, so we assert a non-empty ``List[Dict]`` directly. A
     real Alma tenant always has at least a few users, so non-empty is
     a safe assertion.

  2. ``search_users(q="primary_id~<existing_user>", limit=5)`` -- thin
     wrapper over ``list_users``; assert the supplied user appears in
     the result (echo-back). Alma's user response shape uses
     ``primary_id`` as a top-level string key, but we also tolerate the
     ``{"value": "..."}`` dict shape Alma sometimes returns for
     identifier fields.

  3. ``get_user_personal_data(user_id)`` -- raw ``AlmaResponse.data``
     dict (the GDPR export payload); assert non-empty dict.

No state is mutated -- pure read smoke.

Fixtures (``existing_user_primary_id``) are loaded at runtime from
``chunks/users-list-and-search/test-data.json`` so that no
operator-supplied identifier is committed to the public repository
(R9).

DO NOT EDIT by hand. Generated from
``chunks/users-list-and-search/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def _primary_id_matches(record, expected_user_id):
    """Return True if ``record['primary_id']`` matches the expected id.

    Alma occasionally returns identifier fields as bare strings and
    occasionally as ``{"value": "...", "desc": "..."}`` dicts; tolerate
    both shapes (mirrors the passCriteria from the recommendation).
    """
    if not isinstance(record, dict):
        return False
    raw = record.get("primary_id")
    if raw == expected_user_id:
        return True
    if isinstance(raw, dict) and raw.get("value") == expected_user_id:
        return True
    return False


def test_t_36_1():
    existing_user_primary_id = _TEST_DATA["existing_user_primary_id"]

    client = AlmaAPIClient(environment="SANDBOX")
    users_domain = Users(client)

    # --- list_users(limit=5) ---------------------------------------------
    users_list = users_domain.list_users(limit=5)
    assert isinstance(users_list, list)
    assert len(users_list) > 0
    assert all(isinstance(u, dict) for u in users_list)

    # --- search_users (echo-back via primary_id~<value>) -----------------
    search_results = users_domain.search_users(
        q=f"primary_id~{existing_user_primary_id}", limit=5
    )
    assert isinstance(search_results, list)
    assert any(
        _primary_id_matches(u, existing_user_primary_id) for u in search_results
    )

    # --- get_user_personal_data (GDPR export) ----------------------------
    personal_data = users_domain.get_user_personal_data(existing_user_primary_id)
    assert isinstance(personal_data, dict)
    assert len(personal_data) > 0
