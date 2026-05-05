"""Generated SANDBOX test t-13-2 - close() idempotency + raise-on-use-after-close (issue #13).

Maps to:
  - AC #13.2: `alma.close()` is callable directly and is idempotent
  - AC #13.3: calling any HTTP method after `close()` raises a clear error

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
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())
USER_ID = _TEST_DATA["existing_user_primary_id"]


def test_t_13_2():
    client = AlmaAPIClient(environment='SANDBOX')
    users = Users(client)
    pre_close_response = users.get_user(USER_ID)
    client.close()
    second_close_raised = None
    try:
        client.close()
    except Exception as e:
        second_close_raised = e
    post_close_error = None
    try:
        users.get_user(USER_ID)
    except AlmaAPIError as e:
        post_close_error = e

    assert pre_close_response is not None
    assert pre_close_response.success is True
    assert second_close_raised is None
    assert getattr(client, '_session', 'missing-attr') is None
    assert post_close_error is not None
    assert isinstance(post_close_error, AlmaAPIError) is True
    assert 'closed' in str(post_close_error).lower()
