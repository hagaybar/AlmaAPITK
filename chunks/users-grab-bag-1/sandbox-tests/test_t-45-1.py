"""Generated SANDBOX test t-45-1 - Users deposits read smoke (issue #45).

Maps to AC #45 facets:
  - ``list_user_deposits`` exercised against live SANDBOX, returns a
    List[Dict] envelope (Alma's deposit wrapper unwrapped).
  - ``list_user_deposits`` exists on the existing ``Users`` class
    (importable / bound).

Calls the read-only deposit method shipped in issue #45 against live
SANDBOX. Confirms ``list_user_deposits`` returns a list (the SANDBOX
user is likely to have zero deposits — common case — in which case the
list is empty and that is still a pass for the list-shape assertion).
No conditional get is exercised here because there may be no deposits
to fetch on the SANDBOX user; the get / create / perform-action wire
shapes are covered by mocked-HTTP unit tests in
``tests/unit/domains/test_users.py``.

No state is mutated.

Fixture (``existing_user_primary_id``) is loaded at runtime from
``chunks/users-grab-bag-1/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/users-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_45_1():
    existing_user_primary_id = _TEST_DATA["existing_user_primary_id"]

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)

    # --- list_user_deposits ---------------------------------------------
    deposits = users.list_user_deposits(existing_user_primary_id)
    assert isinstance(deposits, list)
