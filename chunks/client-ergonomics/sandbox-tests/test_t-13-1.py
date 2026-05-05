"""Generated SANDBOX test t-13-1 - context-manager happy path (issue #13).

Maps to:
  - AC #13.1: `with AlmaAPIClient(...) as alma:` works
  - AC #13.4: test exercising the with-statement path

The fixture (existing_user_primary_id) is loaded at runtime from
chunks/client-ergonomics/test-data.json so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
chunks/client-ergonomics/test-recommendation.json.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())
USER_ID = _TEST_DATA["existing_user_primary_id"]


def test_t_13_1():
    captured_client = None
    captured_response = None
    with AlmaAPIClient(environment='SANDBOX') as alma:
        captured_client = alma
        users = Users(alma)
        captured_response = users.get_user(USER_ID)
    session_after_exit = getattr(captured_client, '_session', 'missing-attr')

    assert captured_response is not None
    assert captured_response.success is True
    assert captured_response.status_code == 200
    assert session_after_exit is None
