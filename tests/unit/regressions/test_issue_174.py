"""R10 regression test for issue #174.

``Users.update_user_email`` re-wrapped ``AlmaValidationError`` raised inside
its try block (e.g. by ``get_user`` on a blank user id) as ``AlmaAPIError``,
breaking its documented ``Raises: AlmaValidationError`` contract.
"""
import pytest

from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users


class _StubClient:
    def get_environment(self):
        return "SANDBOX"


def test_blank_user_id_raises_validation_error():
    users = Users(_StubClient())

    with pytest.raises(AlmaValidationError):
        users.update_user_email("   ", "valid@example.com")
