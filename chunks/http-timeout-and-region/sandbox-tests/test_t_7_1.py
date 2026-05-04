"""t-7-1: default region='EU' preserves backward-compat (issue #7).

Maps to:
  - AC-2: region defaults to EU
  - AC-5: Existing tests pass; public signatures preserved
  - AC-6: client.base_url is public
"""
from __future__ import annotations

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users


def test_default_region_is_eu_and_user_get_succeeds(test_user_id, sandbox_key_present):
    client = AlmaAPIClient(environment="SANDBOX")
    assert client.base_url == "https://api-eu.hosted.exlibrisgroup.com", (
        f"AC-2/AC-6: expected EU base_url, got {client.base_url!r}"
    )
    users = Users(client)
    response = users.get_user(test_user_id)
    assert response.success is True, "GET /users/{id} did not report success"
    assert isinstance(response.data, dict) and response.data, (
        "response.data should be a non-empty dict"
    )
