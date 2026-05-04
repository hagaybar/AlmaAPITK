"""t-6-1: 60s default timeout doesn't break a normal SANDBOX GET (issue #6).

Maps to:
  - AC-1: Default lowered to 60s
  - AC-3: Per-call override path exists (default flows through)
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users


def test_default_timeout_60_allows_user_get(test_user_id, sandbox_key_present):
    client = AlmaAPIClient(environment="SANDBOX")
    assert client.timeout == 60, (
        f"AC-1: expected default timeout 60s, got {client.timeout}"
    )
    users = Users(client)
    response = users.get_user(test_user_id)
    assert response.success is True, "GET /users/{id} did not report success"
    assert isinstance(response.data, dict) and response.data, (
        "response.data should be a non-empty dict"
    )
