"""
Unit tests for the Users domain class — issue #36 coverage:

- ``Users.list_users`` — list/search via ``GET /almaws/v1/users``
- ``Users.search_users`` — convenience wrapper requiring ``q``
- ``Users.get_user_personal_data`` — GDPR export via
  ``GET /almaws/v1/users/{user_id}/personal-data``

Tests use a mocked AlmaAPIClient stand-in (no real HTTP) following the
mock-shape established in ``tests/unit/domains/test_configuration.py``.
"""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest


class MockAlmaResponse:
    """Lightweight stand-in for ``almaapitk.AlmaResponse``.

    Mirrors ``test_configuration.MockAlmaResponse`` — just enough
    surface area for the GET-shaped methods under test.
    """

    def __init__(
        self,
        body: Optional[Dict[str, Any]] = None,
        status_code: int = 200,
        success: bool = True,
    ):
        self._body = body if body is not None else {}
        self.status_code = status_code
        self.success = success

    def json(self) -> Dict[str, Any]:
        return self._body

    @property
    def data(self) -> Dict[str, Any]:
        return self._body


class MockAlmaAPIClient:
    """Mock AlmaAPIClient for testing the Users domain.

    Records GET calls (endpoint + params) and lets each test set the
    next response via ``get_response`` or a one-shot ``next_exception``.
    The Users.__init__ calls ``client.logger`` and
    ``client.get_environment``; both are honoured here.
    """

    def __init__(
        self,
        environment: str = 'SANDBOX',
    ):
        self.environment = environment
        self.logger = MagicMock()
        self.get_response: MockAlmaResponse = MockAlmaResponse()
        self.next_exception: Optional[Exception] = None
        self.calls = {"get": []}

    def get_environment(self) -> str:
        return self.environment

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        self.calls["get"].append(
            {"endpoint": endpoint, "params": params}
        )
        if self.next_exception is not None:
            exc, self.next_exception = self.next_exception, None
            raise exc
        return self.get_response


# ---------------------------------------------------------------------------
# list_users
# ---------------------------------------------------------------------------


class TestListUsers:
    """Tests for ``Users.list_users`` (issue #36)."""

    def test_list_users_calls_correct_endpoint_with_defaults(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user": [
                    {"primary_id": "u1", "first_name": "Ada"},
                    {"primary_id": "u2", "first_name": "Linus"},
                ],
                "total_record_count": 2,
            }
        )
        users = Users(mock_client)

        result = users.list_users()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users"
        # Defaults: limit=10, offset=0; no other filters present.
        assert call["params"] == {"limit": "10", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["primary_id"] == "u1"

    def test_list_users_forwards_q_and_pagination(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user": [{"primary_id": "u1"}],
                "total_record_count": 1,
            }
        )
        users = Users(mock_client)

        result = users.list_users(
            limit=50,
            offset=100,
            q="last_name~Smith",
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": "50",
            "offset": "100",
            "q": "last_name~Smith",
        }
        assert result[0]["primary_id"] == "u1"

    def test_list_users_forwards_all_optional_filters(self):
        """All documented optional filters must be forwarded when set."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user": [], "total_record_count": 0}
        )
        users = Users(mock_client)

        users.list_users(
            limit=25,
            offset=0,
            q="primary_id~ST123",
            order_by="last_name",
            expand="loans",
            source_user_id="src-user-1",
            source_institution_code="INST_A",
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": "25",
            "offset": "0",
            "q": "primary_id~ST123",
            "order_by": "last_name",
            "expand": "loans",
            "source_user_id": "src-user-1",
            "source_institution_code": "INST_A",
        }

    def test_list_users_omits_unset_optional_filters(self):
        """``None`` filters must not appear in the query string."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user": [], "total_record_count": 0}
        )
        users = Users(mock_client)

        users.list_users(limit=5, offset=0)

        call = mock_client.calls["get"][0]
        # Only the two pagination params should be present.
        assert call["params"] == {"limit": "5", "offset": "0"}
        for key in (
            "q",
            "order_by",
            "expand",
            "source_user_id",
            "source_institution_code",
        ):
            assert key not in call["params"]

    def test_list_users_returns_empty_list_on_missing_key(self):
        """Alma envelope without ``user`` key → empty list, not None."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        users = Users(mock_client)

        result = users.list_users()

        assert result == []

    def test_list_users_handles_single_dict_response(self):
        """A single user returned as dict (not list) is normalised."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user": {"primary_id": "only-user"},
                "total_record_count": 1,
            }
        )
        users = Users(mock_client)

        result = users.list_users()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["primary_id"] == "only-user"

    def test_list_users_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=500)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.list_users()


# ---------------------------------------------------------------------------
# search_users
# ---------------------------------------------------------------------------


class TestSearchUsers:
    """Tests for ``Users.search_users`` (issue #36)."""

    def test_search_users_requires_non_empty_q(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.search_users(q="")

    def test_search_users_requires_non_whitespace_q(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.search_users(q="   ")

    def test_search_users_rejects_non_string_q(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.search_users(q=None)  # type: ignore[arg-type]

    def test_search_users_forwards_to_list_users(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user": [{"primary_id": "ada"}],
                "total_record_count": 1,
            }
        )
        users = Users(mock_client)

        result = users.search_users(q="last_name~Lovelace", limit=20)

        # search_users delegates to list_users, which makes one GET.
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users"
        assert call["params"]["q"] == "last_name~Lovelace"
        assert call["params"]["limit"] == "20"
        assert isinstance(result, list)
        assert result[0]["primary_id"] == "ada"

    def test_search_users_strips_q_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user": [], "total_record_count": 0}
        )
        users = Users(mock_client)

        users.search_users(q="  primary_id~ST123  ")

        call = mock_client.calls["get"][0]
        assert call["params"]["q"] == "primary_id~ST123"

    def test_search_users_passes_through_kwargs(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user": [], "total_record_count": 0}
        )
        users = Users(mock_client)

        users.search_users(
            q="last_name~Smith",
            limit=15,
            offset=30,
            order_by="last_name",
            expand="loans",
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": "15",
            "offset": "30",
            "q": "last_name~Smith",
            "order_by": "last_name",
            "expand": "loans",
        }


# ---------------------------------------------------------------------------
# get_user_personal_data
# ---------------------------------------------------------------------------


class TestGetUserPersonalData:
    """Tests for ``Users.get_user_personal_data`` (issue #36)."""

    def test_get_user_personal_data_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "primary_id": "u1",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "contact_info": {"email": []},
            }
        )
        users = Users(mock_client)

        result = users.get_user_personal_data("u1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/personal-data"
        # No params on personal-data endpoint.
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["primary_id"] == "u1"
        assert result["first_name"] == "Ada"

    def test_get_user_personal_data_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"primary_id": "u1"}
        )
        users = Users(mock_client)

        users.get_user_personal_data("  u1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/personal-data"

    def test_get_user_personal_data_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_personal_data("")

    def test_get_user_personal_data_raises_on_whitespace_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_personal_data("   ")

    def test_get_user_personal_data_raises_on_non_string_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_personal_data(None)  # type: ignore[arg-type]

    def test_get_user_personal_data_returns_empty_dict_on_empty_body(self):
        """A ``None`` body normalises to an empty dict."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        # MockAlmaResponse defaults to {} — explicit here for clarity.
        mock_client.get_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        result = users.get_user_personal_data("u1")

        assert result == {}

    def test_get_user_personal_data_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "User not found", status_code=400
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.get_user_personal_data("missing-user")

    def test_get_user_personal_data_does_not_log_body(self):
        """Personal-data body must never appear in log records."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        sensitive = {
            "primary_id": "u1",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "contact_info": {
                "email": [
                    {"email_address": "ada@example.test"},
                ],
                "address": [
                    {"line1": "123 Sensitive St"},
                ],
            },
        }
        mock_client.get_response = MockAlmaResponse(body=sensitive)
        users = Users(mock_client)

        # The Users class swaps ``self.logger`` to a real ``logging``
        # logger in __init__, so capture log output via caplog rather
        # than asserting on the mock_client.logger.
        import logging

        with _captured_logs("Users_SANDBOX") as records:
            users.get_user_personal_data("u1")

        # No log message may contain any sensitive value.
        sensitive_strings = (
            "ada@example.test",
            "Ada",
            "Lovelace",
            "123 Sensitive St",
        )
        for rec in records:
            msg = rec.getMessage()
            for needle in sensitive_strings:
                assert needle not in msg, (
                    f"Sensitive value {needle!r} leaked into log: {msg!r}"
                )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


from contextlib import contextmanager
import logging


@contextmanager
def _captured_logs(logger_name: str):
    """Capture log records emitted by a named logger during a block.

    The Users class builds its own non-propagating logger via
    ``_setup_enhanced_logger``; pytest's ``caplog`` does not see those
    records unless we attach a handler directly.
    """
    logger = logging.getLogger(logger_name)
    records: list = []

    class _ListHandler(logging.Handler):
        def emit(self, record):  # noqa: D401 - simple capture
            records.append(record)

    handler = _ListHandler(level=logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
