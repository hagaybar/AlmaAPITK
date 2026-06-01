"""R10 hardening test for issue #144 — validate the `expand` param on get_user.

`Users.get_user(user_id, expand=...)` forwarded any string straight to Alma,
which rejects unknown values with HTTP 400 (alma_code 401666) only after the
round-trip — and the failing field never appears in the call, so it's opaque to
debug. The committed swagger (`users.json`, GET /users/{user_id}) declares the
expand options as exactly `loans`, `requests`, `fees` (comma-separated; default
`none`). A consumer who trusted the (wrong) skill note and passed `user_blocks`
got the opaque 400.

These tests pin client-side validation: known tokens pass through, unknown
tokens raise AlmaValidationError *before* any request.
"""
import pytest

from unittest.mock import MagicMock

from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users


def _users():
    client = MagicMock()
    client.get_environment.return_value = "SANDBOX"
    return Users(client), client


def test_get_user_rejects_invalid_expand_before_request():
    users, client = _users()

    with pytest.raises(AlmaValidationError):
        users.get_user("tau000000", expand="user_blocks")

    client.get.assert_not_called()  # rejected client-side, no wasted round-trip


def test_get_user_accepts_valid_expand_tokens():
    users, client = _users()
    client.get.return_value = MagicMock()

    for value in ("none", "loans", "requests", "fees", "loans,fees", "loans, requests, fees"):
        users.get_user("tau000000", expand=value)  # must not raise


def test_get_user_rejects_mixed_valid_and_invalid_expand():
    users, client = _users()

    with pytest.raises(AlmaValidationError):
        users.get_user("tau000000", expand="loans,user_blocks")
