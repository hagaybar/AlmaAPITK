"""
Unit tests for the Users domain class — issue #36 / #39 / #40 / #44 / #45
coverage:

- ``Users.list_users`` — list/search via ``GET /almaws/v1/users``
- ``Users.search_users`` — convenience wrapper requiring ``q``
- ``Users.get_user_personal_data`` — GDPR export via
  ``GET /almaws/v1/users/{user_id}/personal-data``
- ``Users.list_user_attachments`` — list attachments via
  ``GET /almaws/v1/users/{user_id}/attachments`` (issue #39)
- ``Users.get_user_attachment`` — retrieve a single attachment via
  ``GET /almaws/v1/users/{user_id}/attachments/{attachment_id}``
  (issue #39)
- ``Users.upload_user_attachment`` — upload an attachment via
  ``POST /almaws/v1/users/{user_id}/attachments`` (issue #39)
- ``Users.{list,create,get}_user_fee`` and op-driven posts
  (``pay_all_user_fees`` / ``pay_user_fee`` / ``waive_user_fee`` /
  ``dispute_user_fee`` / ``restore_user_fee``) — fines/fees coverage
  (issue #44)
- ``Users.{list,create,get}_user_deposit`` and
  ``perform_user_deposit_action`` — deposits coverage (issue #45)
- ``Users.{list,create,get}_user_loan`` plus ``renew_user_loan`` /
  ``update_user_loan`` — loans coverage (issue #40)

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
        self.post_response: MockAlmaResponse = MockAlmaResponse()
        self.put_response: MockAlmaResponse = MockAlmaResponse()
        self.delete_response: MockAlmaResponse = MockAlmaResponse()
        self.next_exception: Optional[Exception] = None
        self.calls = {"get": [], "post": [], "put": [], "delete": []}

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

    def post(
        self,
        endpoint: str,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        self.calls["post"].append(
            {
                "endpoint": endpoint,
                "data": data,
                "params": params,
                "content_type": content_type,
            }
        )
        if self.next_exception is not None:
            exc, self.next_exception = self.next_exception, None
            raise exc
        return self.post_response

    def put(
        self,
        endpoint: str,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        self.calls["put"].append(
            {
                "endpoint": endpoint,
                "data": data,
                "params": params,
                "content_type": content_type,
            }
        )
        if self.next_exception is not None:
            exc, self.next_exception = self.next_exception, None
            raise exc
        return self.put_response

    def delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        self.calls["delete"].append(
            {"endpoint": endpoint, "params": params}
        )
        if self.next_exception is not None:
            exc, self.next_exception = self.next_exception, None
            raise exc
        return self.delete_response


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
# list_user_attachments  (issue #39)
# ---------------------------------------------------------------------------


class TestListUserAttachments:
    """Tests for ``Users.list_user_attachments`` (issue #39)."""

    def test_list_user_attachments_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_attachment": [
                    {"id": "att-1", "file_name": "a.pdf"},
                    {"id": "att-2", "file_name": "b.pdf"},
                ],
                "total_record_count": 2,
            }
        )
        users = Users(mock_client)

        result = users.list_user_attachments("u1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/attachments"
        # No params on the list endpoint.
        assert call["params"] is None
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "att-1"

    def test_list_user_attachments_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user_attachment": []}
        )
        users = Users(mock_client)

        users.list_user_attachments("  u1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/attachments"

    def test_list_user_attachments_falls_back_to_attachment_key(self):
        """Defensive: handle the legacy ``attachment`` envelope key."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"attachment": [{"id": "att-1"}]}
        )
        users = Users(mock_client)

        result = users.list_user_attachments("u1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "att-1"

    def test_list_user_attachments_returns_empty_list_on_missing_key(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        users = Users(mock_client)

        result = users.list_user_attachments("u1")

        assert result == []

    def test_list_user_attachments_handles_single_dict_response(self):
        """A single attachment as dict (not list) is normalised."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user_attachment": {"id": "only-att"}}
        )
        users = Users(mock_client)

        result = users.list_user_attachments("u1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "only-att"

    def test_list_user_attachments_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_attachments("")

    def test_list_user_attachments_raises_on_non_string_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_attachments(None)  # type: ignore[arg-type]

    def test_list_user_attachments_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=500)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.list_user_attachments("u1")


# ---------------------------------------------------------------------------
# get_user_attachment  (issue #39)
# ---------------------------------------------------------------------------


class TestGetUserAttachment:
    """Tests for ``Users.get_user_attachment`` (issue #39)."""

    def test_get_user_attachment_without_expand(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "id": "att-1",
                "file_name": "a.pdf",
                "type": "GENERAL",
                "size": 1024,
            }
        )
        users = Users(mock_client)

        result = users.get_user_attachment("u1", "att-1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/users/u1/attachments/att-1"
        )
        # No ``expand`` supplied → params is None (not {"expand": None}).
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["id"] == "att-1"
        assert result["file_name"] == "a.pdf"

    def test_get_user_attachment_with_expand_content(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "id": "att-1",
                "file_name": "a.pdf",
                # Pretend Alma echoes the base64 payload back here.
                "content": "aGVsbG8=",
            }
        )
        users = Users(mock_client)

        result = users.get_user_attachment(
            "u1", "att-1", expand="content"
        )

        call = mock_client.calls["get"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/users/u1/attachments/att-1"
        )
        assert call["params"] == {"expand": "content"}
        # The method must NOT base64-decode for the caller — leave it
        # as-is so callers control decoding.
        assert result["content"] == "aGVsbG8="

    def test_get_user_attachment_with_expand_content_no_encoding(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"id": "att-1"}
        )
        users = Users(mock_client)

        users.get_user_attachment(
            "u1", "att-1", expand="content_no_encoding"
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {"expand": "content_no_encoding"}

    def test_get_user_attachment_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"id": "att-1"})
        users = Users(mock_client)

        users.get_user_attachment("  u1  ", "  att-1  ")

        call = mock_client.calls["get"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/users/u1/attachments/att-1"
        )

    def test_get_user_attachment_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_attachment("", "att-1")

    def test_get_user_attachment_raises_on_empty_attachment_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_attachment("u1", "")

    def test_get_user_attachment_raises_on_non_string_attachment_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_attachment("u1", None)  # type: ignore[arg-type]

    def test_get_user_attachment_returns_empty_dict_on_empty_body(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        result = users.get_user_attachment("u1", "att-1")

        assert result == {}

    def test_get_user_attachment_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Not found", status_code=404
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.get_user_attachment("u1", "missing-att")


# ---------------------------------------------------------------------------
# upload_user_attachment  (issue #39)
# ---------------------------------------------------------------------------


class TestUploadUserAttachment:
    """Tests for ``Users.upload_user_attachment`` (issue #39)."""

    def test_upload_user_attachment_happy_path(self, tmp_path):
        """Upload posts JSON+base64 with the verified body shape."""
        import base64

        from almaapitk.domains.users import Users

        # Create a small file with deterministic bytes.
        file_bytes = b"hello world"
        file_path = tmp_path / "hello.txt"
        file_path.write_bytes(file_bytes)

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={
                "id": "12345",
                "type": "GENERAL",
                "size": len(file_bytes),
                "file_name": "hello.txt",
            }
        )
        users = Users(mock_client)

        response = users.upload_user_attachment("u1", str(file_path))

        # One POST to the correct endpoint.
        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/attachments"
        # JSON body, NOT multipart — content_type must be the default.
        assert call["content_type"] is None

        body = call["data"]
        assert isinstance(body, dict)
        # ``type`` is a plain string, NOT a {"value": "..."} wrapper.
        assert body["type"] == "GENERAL"
        assert body["file_name"] == "hello.txt"
        # ``content`` is base64-encoded file bytes.
        assert body["content"] == base64.b64encode(file_bytes).decode("ascii")

        # Returned AlmaResponse exposes the new attachment's id.
        assert response.data["id"] == "12345"

    def test_upload_user_attachment_uses_supplied_attachment_data(
        self, tmp_path
    ):
        """Caller-supplied attachment_data overrides defaults except content."""
        import base64

        from almaapitk.domains.users import Users

        file_bytes = b"abc123"
        file_path = tmp_path / "doc.pdf"
        file_path.write_bytes(file_bytes)

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "att-1"})
        users = Users(mock_client)

        users.upload_user_attachment(
            "u1",
            str(file_path),
            attachment_data={
                "type": "GENERAL",
                "note": "Operator-supplied note",
                # A stale ``content`` value MUST be overridden by the
                # freshly-encoded file bytes.
                "content": "STALE_BASE64",
            },
        )

        call = mock_client.calls["post"][0]
        body = call["data"]
        assert body["type"] == "GENERAL"
        assert body["note"] == "Operator-supplied note"
        assert body["file_name"] == "doc.pdf"
        # Content is the live encoding of the file, NOT the stale value.
        assert body["content"] == base64.b64encode(file_bytes).decode("ascii")
        assert body["content"] != "STALE_BASE64"

    def test_upload_user_attachment_does_not_mutate_caller_dict(
        self, tmp_path
    ):
        """``attachment_data`` must be shallow-copied, not mutated in place."""
        from almaapitk.domains.users import Users

        file_bytes = b"x"
        file_path = tmp_path / "x.bin"
        file_path.write_bytes(file_bytes)

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "x"})
        users = Users(mock_client)

        caller_data = {"type": "GENERAL", "note": "n"}
        snapshot = dict(caller_data)
        users.upload_user_attachment(
            "u1", str(file_path), attachment_data=caller_data
        )

        # Caller's dict must remain untouched (no ``content`` /
        # ``file_name`` injected).
        assert caller_data == snapshot

    def test_upload_user_attachment_defaults_type_to_general(self, tmp_path):
        from almaapitk.domains.users import Users

        file_path = tmp_path / "f.txt"
        file_path.write_bytes(b"abc")

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "x"})
        users = Users(mock_client)

        users.upload_user_attachment("u1", str(file_path))

        body = mock_client.calls["post"][0]["data"]
        assert body["type"] == "GENERAL"

    def test_upload_user_attachment_raises_on_missing_file(self, tmp_path):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        missing_path = tmp_path / "does_not_exist.bin"

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.upload_user_attachment("u1", str(missing_path))
        # No HTTP call should have been issued.
        assert mock_client.calls["post"] == []

    def test_upload_user_attachment_raises_on_directory_path(self, tmp_path):
        """A directory is not a file — must raise validation error."""
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.upload_user_attachment("u1", str(tmp_path))

    def test_upload_user_attachment_raises_on_empty_file_path(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.upload_user_attachment("u1", "")

    def test_upload_user_attachment_raises_on_non_string_file_path(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.upload_user_attachment(
                "u1", None  # type: ignore[arg-type]
            )

    def test_upload_user_attachment_raises_on_empty_user_id(self, tmp_path):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        file_path = tmp_path / "f.txt"
        file_path.write_bytes(b"abc")

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.upload_user_attachment("", str(file_path))

    def test_upload_user_attachment_propagates_api_error(self, tmp_path):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        file_path = tmp_path / "f.txt"
        file_path.write_bytes(b"abc")

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=500)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.upload_user_attachment("u1", str(file_path))

    def test_upload_user_attachment_does_not_log_file_body_or_base64(
        self, tmp_path
    ):
        """File contents and base64 payload must never appear in logs."""
        import base64

        from almaapitk.domains.users import Users

        # Use a recognisable byte sequence that we can grep for in logs.
        file_bytes = b"SUPER_SECRET_FILE_CONTENT_MARKER"
        file_path = tmp_path / "secret.bin"
        file_path.write_bytes(file_bytes)
        encoded = base64.b64encode(file_bytes).decode("ascii")

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "x"})
        users = Users(mock_client)

        with _captured_logs("Users_SANDBOX") as records:
            users.upload_user_attachment("u1", str(file_path))

        sensitive_strings = (
            file_bytes.decode("ascii"),  # raw content
            encoded,                     # base64 payload
        )
        for rec in records:
            msg = rec.getMessage()
            for needle in sensitive_strings:
                assert needle not in msg, (
                    f"Sensitive value leaked into log: {msg!r}"
                )


# ---------------------------------------------------------------------------
# list_user_fees  (issue #44)
# ---------------------------------------------------------------------------


class TestListUserFees:
    """Tests for ``Users.list_user_fees`` (issue #44)."""

    def test_list_user_fees_calls_correct_endpoint_no_status(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "fee": [
                    {"id": "fee-1", "type": {"value": "OVERDUEFINEFEE"}},
                    {"id": "fee-2", "type": {"value": "LOSTITEMREPLACEMENTFEE"}},
                ],
                "total_record_count": 2,
            }
        )
        users = Users(mock_client)

        result = users.list_user_fees("u1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees"
        # No status filter → params should be None (not empty dict).
        assert call["params"] is None
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "fee-1"

    def test_list_user_fees_forwards_status_filter(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"fee": [{"id": "fee-1"}], "total_record_count": 1}
        )
        users = Users(mock_client)

        users.list_user_fees("u1", status="ACTIVE")

        call = mock_client.calls["get"][0]
        assert call["params"] == {"status": "ACTIVE"}

    def test_list_user_fees_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"fee": []})
        users = Users(mock_client)

        users.list_user_fees("  u1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees"

    def test_list_user_fees_returns_empty_list_on_missing_key(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        users = Users(mock_client)

        result = users.list_user_fees("u1")

        assert result == []

    def test_list_user_fees_handles_single_dict_response(self):
        """A single fee returned as dict (not list) is normalised."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"fee": {"id": "only-fee"}, "total_record_count": 1}
        )
        users = Users(mock_client)

        result = users.list_user_fees("u1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "only-fee"

    def test_list_user_fees_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_fees("")

    def test_list_user_fees_raises_on_non_string_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_fees(None)  # type: ignore[arg-type]

    def test_list_user_fees_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=500)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.list_user_fees("u1")


# ---------------------------------------------------------------------------
# create_user_fee  (issue #44)
# ---------------------------------------------------------------------------


class TestCreateUserFee:
    """Tests for ``Users.create_user_fee`` (issue #44)."""

    def test_create_user_fee_posts_body_verbatim(self):
        from almaapitk.domains.users import Users

        fee_body = {
            "type": {"value": "CREDIT"},
            "original_amount": "10.00",
            "balance": "10.00",
            "owner": {"value": "MAIN"},
        }

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"id": "fee-99", "type": {"value": "CREDIT"}}
        )
        users = Users(mock_client)

        response = users.create_user_fee("u1", fee_body)

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees"
        # JSON body, not multipart.
        assert call["content_type"] is None
        # Body is the operator-supplied dict verbatim.
        assert call["data"] == fee_body
        # No query params on creation.
        assert call["params"] is None
        assert response.data["id"] == "fee-99"

    def test_create_user_fee_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_fee("", {"type": "X"})

    def test_create_user_fee_raises_on_empty_fee_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_fee("u1", {})

    def test_create_user_fee_raises_on_non_dict_fee_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_fee("u1", "not-a-dict")  # type: ignore[arg-type]

    def test_create_user_fee_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "User fine/fee type is required.", status_code=400
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.create_user_fee("u1", {"original_amount": "5.00"})


# ---------------------------------------------------------------------------
# get_user_fee  (issue #44)
# ---------------------------------------------------------------------------


class TestGetUserFee:
    """Tests for ``Users.get_user_fee`` (issue #44)."""

    def test_get_user_fee_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "id": "fee-1",
                "type": {"value": "OVERDUEFINEFEE"},
                "original_amount": "5.00",
                "balance": "5.00",
            }
        )
        users = Users(mock_client)

        result = users.get_user_fee("u1", "fee-1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees/fee-1"
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["id"] == "fee-1"

    def test_get_user_fee_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"id": "fee-1"})
        users = Users(mock_client)

        users.get_user_fee("  u1  ", "  fee-1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees/fee-1"

    def test_get_user_fee_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_fee("", "fee-1")

    def test_get_user_fee_raises_on_empty_fee_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_fee("u1", "")

    def test_get_user_fee_returns_empty_dict_on_empty_body(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        result = users.get_user_fee("u1", "fee-1")

        assert result == {}

    def test_get_user_fee_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Not found", status_code=404
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.get_user_fee("u1", "missing-fee")


# ---------------------------------------------------------------------------
# pay_all_user_fees  (issue #44)
# ---------------------------------------------------------------------------


class TestPayAllUserFees:
    """Tests for ``Users.pay_all_user_fees`` (issue #44)."""

    def test_pay_all_user_fees_defaults_send_op_amount_method_as_params(self):
        """Default call: op=pay, amount=ALL, method=CASH as query params."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.pay_all_user_fees("u1")

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees/all"
        # No body — all transport is via query params.
        assert call["data"] is None
        assert call["params"] == {
            "op": "pay",
            "amount": "ALL",
            "method": "CASH",
        }

    def test_pay_all_user_fees_forwards_numeric_amount_and_method(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.pay_all_user_fees("u1", amount="12.50", method="CREDIT")

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "pay",
            "amount": "12.50",
            "method": "CREDIT",
        }

    def test_pay_all_user_fees_forwards_external_transaction_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.pay_all_user_fees(
            "u1",
            amount="ALL",
            method="ONLINE",
            external_transaction_id="txn-abc",
        )

        call = mock_client.calls["post"][0]
        assert call["params"]["external_transaction_id"] == "txn-abc"

    def test_pay_all_user_fees_omits_external_transaction_id_when_none(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.pay_all_user_fees("u1")

        call = mock_client.calls["post"][0]
        assert "external_transaction_id" not in call["params"]

    def test_pay_all_user_fees_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.pay_all_user_fees("")
        # No HTTP call on failed validation.
        assert mock_client.calls["post"] == []

    def test_pay_all_user_fees_rejects_non_numeric_non_all_amount(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.pay_all_user_fees("u1", amount="not-a-number")
        assert mock_client.calls["post"] == []

    def test_pay_all_user_fees_rejects_amount_with_two_decimals(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.pay_all_user_fees("u1", amount="1.2.3")

    def test_pay_all_user_fees_rejects_empty_amount(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.pay_all_user_fees("u1", amount="")

    def test_pay_all_user_fees_rejects_empty_method(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.pay_all_user_fees("u1", method="")

    def test_pay_all_user_fees_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=400)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.pay_all_user_fees("u1")


# ---------------------------------------------------------------------------
# pay_user_fee  (issue #44)
# ---------------------------------------------------------------------------


class TestPayUserFee:
    """Tests for ``Users.pay_user_fee`` (issue #44)."""

    def test_pay_user_fee_sends_op_amount_method_as_params(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.pay_user_fee("u1", "fee-1", amount="5.00")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees/fee-1"
        assert call["data"] is None
        assert call["params"] == {
            "op": "pay",
            "amount": "5.00",
            "method": "CASH",
        }

    def test_pay_user_fee_accepts_amount_all_sentinel(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.pay_user_fee("u1", "fee-1", amount="ALL", method="CREDIT")

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "pay",
            "amount": "ALL",
            "method": "CREDIT",
        }

    def test_pay_user_fee_forwards_external_transaction_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.pay_user_fee(
            "u1",
            "fee-1",
            amount="3.00",
            external_transaction_id="ext-xyz",
        )

        call = mock_client.calls["post"][0]
        assert call["params"]["external_transaction_id"] == "ext-xyz"

    def test_pay_user_fee_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.pay_user_fee("", "fee-1", amount="1.00")

    def test_pay_user_fee_raises_on_empty_fee_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.pay_user_fee("u1", "", amount="1.00")

    def test_pay_user_fee_rejects_bad_amount(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.pay_user_fee("u1", "fee-1", amount="abc")

    def test_pay_user_fee_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "The fee is API Restricted by library.", status_code=400
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.pay_user_fee("u1", "fee-1", amount="5.00")


# ---------------------------------------------------------------------------
# waive_user_fee  (issue #44)
# ---------------------------------------------------------------------------


class TestWaiveUserFee:
    """Tests for ``Users.waive_user_fee`` (issue #44)."""

    def test_waive_user_fee_required_reason_sent_as_param(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.waive_user_fee("u1", "fee-1", reason="GOODWILL")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees/fee-1"
        assert call["data"] is None
        assert call["params"] == {"op": "waive", "reason": "GOODWILL"}
        # method must NOT be sent on waive.
        assert "method" not in call["params"]

    def test_waive_user_fee_with_partial_amount_and_comment(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.waive_user_fee(
            "u1",
            "fee-1",
            reason="GOODWILL",
            amount="2.50",
            comment="Partial waive per supervisor",
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "waive",
            "reason": "GOODWILL",
            "amount": "2.50",
            "comment": "Partial waive per supervisor",
        }

    def test_waive_user_fee_strips_reason_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.waive_user_fee("u1", "fee-1", reason="  GOODWILL  ")

        call = mock_client.calls["post"][0]
        assert call["params"]["reason"] == "GOODWILL"

    def test_waive_user_fee_raises_on_missing_reason(self):
        """Reason is REQUIRED for op=waive."""
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.waive_user_fee("u1", "fee-1", reason="")
        assert mock_client.calls["post"] == []

    def test_waive_user_fee_raises_on_whitespace_reason(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.waive_user_fee("u1", "fee-1", reason="   ")

    def test_waive_user_fee_raises_on_non_string_reason(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.waive_user_fee(
                "u1", "fee-1", reason=None  # type: ignore[arg-type]
            )

    def test_waive_user_fee_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.waive_user_fee("", "fee-1", reason="GOODWILL")

    def test_waive_user_fee_raises_on_empty_fee_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.waive_user_fee("u1", "", reason="GOODWILL")

    def test_waive_user_fee_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=400)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.waive_user_fee("u1", "fee-1", reason="GOODWILL")


# ---------------------------------------------------------------------------
# dispute_user_fee  (issue #44)
# ---------------------------------------------------------------------------


class TestDisputeUserFee:
    """Tests for ``Users.dispute_user_fee`` (issue #44).

    Audit fix #2: ``reason`` is OPTIONAL on dispute (not required).
    """

    def test_dispute_user_fee_minimal_no_reason_no_comment(self):
        """Dispute with just user_id + fee_id sends only op=dispute."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.dispute_user_fee("u1", "fee-1")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees/fee-1"
        assert call["data"] is None
        assert call["params"] == {"op": "dispute"}
        # reason MUST be absent when not provided (audit fix).
        assert "reason" not in call["params"]
        # method MUST NOT be sent on dispute.
        assert "method" not in call["params"]
        # comment MUST be absent when not provided.
        assert "comment" not in call["params"]

    def test_dispute_user_fee_with_reason(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.dispute_user_fee("u1", "fee-1", reason="LOST_RECEIPT")

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "dispute",
            "reason": "LOST_RECEIPT",
        }

    def test_dispute_user_fee_with_comment_only(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.dispute_user_fee(
            "u1", "fee-1", comment="Patron filed a written objection"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "dispute",
            "comment": "Patron filed a written objection",
        }
        assert "reason" not in call["params"]

    def test_dispute_user_fee_with_reason_and_comment(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.dispute_user_fee(
            "u1", "fee-1", reason="LOST_RECEIPT", comment="See ticket #123"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "dispute",
            "reason": "LOST_RECEIPT",
            "comment": "See ticket #123",
        }

    def test_dispute_user_fee_drops_empty_reason_string(self):
        """An empty/whitespace reason string is dropped (treated as None)."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.dispute_user_fee("u1", "fee-1", reason="   ")

        call = mock_client.calls["post"][0]
        assert "reason" not in call["params"]

    def test_dispute_user_fee_does_not_require_reason(self):
        """Regression: the audit-fixed signature must NOT raise on no reason."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        # Should not raise.
        users.dispute_user_fee("u1", "fee-1")
        assert len(mock_client.calls["post"]) == 1

    def test_dispute_user_fee_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.dispute_user_fee("", "fee-1")

    def test_dispute_user_fee_raises_on_empty_fee_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.dispute_user_fee("u1", "")

    def test_dispute_user_fee_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=500)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.dispute_user_fee("u1", "fee-1")


# ---------------------------------------------------------------------------
# restore_user_fee  (issue #44)
# ---------------------------------------------------------------------------


class TestRestoreUserFee:
    """Tests for ``Users.restore_user_fee`` (issue #44)."""

    def test_restore_user_fee_sends_only_op(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.restore_user_fee("u1", "fee-1")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees/fee-1"
        assert call["data"] is None
        assert call["params"] == {"op": "restore"}
        # No reason/amount/method on restore.
        assert "reason" not in call["params"]
        assert "amount" not in call["params"]
        assert "method" not in call["params"]

    def test_restore_user_fee_with_comment(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.restore_user_fee(
            "u1", "fee-1", comment="Dispute resolved against patron"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "restore",
            "comment": "Dispute resolved against patron",
        }

    def test_restore_user_fee_strips_whitespace_in_ids(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.restore_user_fee("  u1  ", "  fee-1  ")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/fees/fee-1"

    def test_restore_user_fee_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.restore_user_fee("", "fee-1")

    def test_restore_user_fee_raises_on_empty_fee_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.restore_user_fee("u1", "")

    def test_restore_user_fee_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=400)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.restore_user_fee("u1", "fee-1")


# ---------------------------------------------------------------------------
# list_user_deposits  (issue #45)
# ---------------------------------------------------------------------------


class TestListUserDeposits:
    """Tests for ``Users.list_user_deposits`` (issue #45)."""

    def test_list_user_deposits_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "deposit": [
                    {"id": "dep-1", "amount": "10.00"},
                    {"id": "dep-2", "amount": "20.00"},
                ],
                "total_record_count": 2,
            }
        )
        users = Users(mock_client)

        result = users.list_user_deposits("u1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/deposits"
        # No params expected for list.
        assert call["params"] is None
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "dep-1"

    def test_list_user_deposits_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"deposit": []})
        users = Users(mock_client)

        users.list_user_deposits("  u1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/deposits"

    def test_list_user_deposits_returns_empty_list_on_missing_key(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        users = Users(mock_client)

        result = users.list_user_deposits("u1")

        assert result == []

    def test_list_user_deposits_handles_single_dict_response(self):
        """A single deposit returned as dict (not list) is normalised."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"deposit": {"id": "only-dep"}, "total_record_count": 1}
        )
        users = Users(mock_client)

        result = users.list_user_deposits("u1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "only-dep"

    def test_list_user_deposits_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_deposits("")

    def test_list_user_deposits_raises_on_non_string_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_deposits(None)  # type: ignore[arg-type]

    def test_list_user_deposits_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Failed to get deposits.", status_code=400
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.list_user_deposits("u1")


# ---------------------------------------------------------------------------
# create_user_deposit  (issue #45)
# ---------------------------------------------------------------------------


class TestCreateUserDeposit:
    """Tests for ``Users.create_user_deposit`` (issue #45)."""

    def test_create_user_deposit_posts_body_verbatim(self):
        from almaapitk.domains.users import Users

        deposit_body = {
            "amount": "50.00",
            "currency": {"value": "USD"},
            "type": {"value": "CASH"},
        }

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"id": "dep-99", "amount": "50.00"}
        )
        users = Users(mock_client)

        response = users.create_user_deposit("u1", deposit_body)

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/deposits"
        # JSON body, not multipart.
        assert call["content_type"] is None
        # Body is the operator-supplied dict verbatim.
        assert call["data"] == deposit_body
        # No query params on creation.
        assert call["params"] is None
        assert response.data["id"] == "dep-99"

    def test_create_user_deposit_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "dep-1"})
        users = Users(mock_client)

        users.create_user_deposit("  u1  ", {"amount": "5.00"})

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/deposits"

    def test_create_user_deposit_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_deposit("", {"amount": "5.00"})

    def test_create_user_deposit_raises_on_empty_deposit_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_deposit("u1", {})

    def test_create_user_deposit_raises_on_non_dict_deposit_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_deposit("u1", "not-a-dict")  # type: ignore[arg-type]

    def test_create_user_deposit_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "X parameter is not valid.", status_code=400
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.create_user_deposit("u1", {"amount": "5.00"})


# ---------------------------------------------------------------------------
# get_user_deposit  (issue #45)
# ---------------------------------------------------------------------------


class TestGetUserDeposit:
    """Tests for ``Users.get_user_deposit`` (issue #45)."""

    def test_get_user_deposit_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "id": "dep-1",
                "amount": "25.00",
                "currency": {"value": "USD"},
            }
        )
        users = Users(mock_client)

        result = users.get_user_deposit("u1", "dep-1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/deposits/dep-1"
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["id"] == "dep-1"

    def test_get_user_deposit_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"id": "dep-1"})
        users = Users(mock_client)

        users.get_user_deposit("  u1  ", "  dep-1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/deposits/dep-1"

    def test_get_user_deposit_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_deposit("", "dep-1")

    def test_get_user_deposit_raises_on_empty_deposit_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_deposit("u1", "")

    def test_get_user_deposit_raises_on_non_string_ids(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_deposit(None, "dep-1")  # type: ignore[arg-type]
        with pytest.raises(AlmaValidationError):
            users.get_user_deposit("u1", None)  # type: ignore[arg-type]

    def test_get_user_deposit_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Failed to get deposit.", status_code=400
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.get_user_deposit("u1", "dep-1")


# ---------------------------------------------------------------------------
# perform_user_deposit_action  (issue #45)
# ---------------------------------------------------------------------------


class TestPerformUserDepositAction:
    """Tests for ``Users.perform_user_deposit_action`` (issue #45)."""

    def test_perform_user_deposit_action_sends_op_as_param(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        response = users.perform_user_deposit_action("u1", "dep-1", "pay")

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/deposits/dep-1"
        # op travels as query param, body is empty.
        assert call["data"] is None
        assert call["params"] == {"op": "pay"}
        assert response.data == {"status": "ok"}

    def test_perform_user_deposit_action_accepts_arbitrary_op(self):
        """Wrapper does NOT restrict op values; arbitrary strings reach Alma."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        # Use an op that's neither pay/refund/dispute/restore — wrapper
        # should still forward it.
        users.perform_user_deposit_action("u1", "dep-1", "future_op_x")

        call = mock_client.calls["post"][0]
        assert call["params"] == {"op": "future_op_x"}

    def test_perform_user_deposit_action_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"status": "ok"})
        users = Users(mock_client)

        users.perform_user_deposit_action("  u1  ", "  dep-1  ", "  refund  ")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/deposits/dep-1"
        assert call["params"] == {"op": "refund"}

    def test_perform_user_deposit_action_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_deposit_action("", "dep-1", "pay")

    def test_perform_user_deposit_action_raises_on_empty_deposit_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_deposit_action("u1", "", "pay")

    def test_perform_user_deposit_action_raises_on_empty_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_deposit_action("u1", "dep-1", "")

    def test_perform_user_deposit_action_raises_on_whitespace_only_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_deposit_action("u1", "dep-1", "   ")

    def test_perform_user_deposit_action_raises_on_non_string_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_deposit_action("u1", "dep-1", None)  # type: ignore[arg-type]

    def test_perform_user_deposit_action_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "General Error - An error has occurred while updating the deposit.",
            status_code=400,
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.perform_user_deposit_action("u1", "dep-1", "pay")


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


# ---------------------------------------------------------------------------
# create_user  (issue #37)
# ---------------------------------------------------------------------------


class TestCreateUser:
    """Tests for ``Users.create_user`` (issue #37)."""

    def _valid_user_data(self) -> Dict[str, Any]:
        """Return a fully-populated, Alma-valid user payload (synthetic IDs).

        Uses the ``{"value": ...}`` wrapper shape Alma returns on reads
        — exercising the round-trip path callers will most often use.
        """
        return {
            "primary_id": "tau000000",
            "account_type": {"value": "INTERNAL"},
            "status": {"value": "ACTIVE"},
            "user_group": {"value": "STAFF"},
            "first_name": "Synthetic",
            "last_name": "User",
        }

    def test_create_user_posts_body_verbatim(self):
        from almaapitk.domains.users import Users

        body = self._valid_user_data()
        # Add a non-required extra key to confirm the body passes through
        # verbatim (the issue's AC is explicit about not stripping fields).
        body["contact_info"] = {
            "email": [
                {
                    "email_address": "synthetic@example.com",
                    "preferred": True,
                }
            ]
        }

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"primary_id": "tau000000", "first_name": "Synthetic"}
        )
        users = Users(mock_client)

        response = users.create_user(body)

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users"
        # JSON body, not multipart.
        assert call["content_type"] is None
        # Body forwarded verbatim — including the extra non-required key.
        assert call["data"] == body
        # No query params on creation.
        assert call["params"] is None
        assert response.data["primary_id"] == "tau000000"

    def test_create_user_accepts_plain_string_account_type(self):
        """Bare strings for ``account_type`` / ``status`` / ``user_group``
        must be accepted (mirrors ``Admin.create_set`` behaviour)."""
        from almaapitk.domains.users import Users

        body = {
            "primary_id": "tau000000",
            "account_type": "INTERNAL",
            "status": "ACTIVE",
            "user_group": "STAFF",
        }
        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"primary_id": "tau000000"}
        )
        users = Users(mock_client)

        response = users.create_user(body)

        # Validation accepted bare strings; body forwarded verbatim.
        assert mock_client.calls["post"][0]["data"] == body
        assert response.data["primary_id"] == "tau000000"

    def test_create_user_accepts_value_dict_account_type(self):
        """The canonical ``{"value": "..."}`` wrapper shape must be
        accepted (the shape Alma returns on reads)."""
        from almaapitk.domains.users import Users

        body = self._valid_user_data()  # uses {"value": ...} dicts
        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"primary_id": "tau000000"}
        )
        users = Users(mock_client)

        response = users.create_user(body)

        # The body is forwarded as-is; Alma owns server-side semantics.
        sent = mock_client.calls["post"][0]["data"]
        assert sent["account_type"] == {"value": "INTERNAL"}
        assert sent["status"] == {"value": "ACTIVE"}
        assert sent["user_group"] == {"value": "STAFF"}
        assert response.data["primary_id"] == "tau000000"

    def test_create_user_raises_on_empty_dict(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user({})

    def test_create_user_raises_on_non_dict(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user("not-a-dict")  # type: ignore[arg-type]

    def test_create_user_raises_on_missing_primary_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        body = self._valid_user_data()
        body.pop("primary_id")

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user(body)

    def test_create_user_raises_on_empty_primary_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        body = self._valid_user_data()
        body["primary_id"] = "   "

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user(body)

    def test_create_user_raises_on_missing_account_type(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        body = self._valid_user_data()
        body.pop("account_type")

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user(body)

    def test_create_user_raises_on_missing_status(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        body = self._valid_user_data()
        body.pop("status")

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user(body)

    def test_create_user_raises_on_missing_user_group(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        body = self._valid_user_data()
        body.pop("user_group")

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user(body)

    def test_create_user_raises_on_empty_value_in_wrapper(self):
        """The ``{"value": ""}`` shape must fail validation, not
        silently pass through."""
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        body = self._valid_user_data()
        body["account_type"] = {"value": ""}

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user(body)

    def test_create_user_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Primary identifier already exists",
            status_code=400,
            alma_code="401873",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.create_user(self._valid_user_data())


# ---------------------------------------------------------------------------
# delete_user  (issue #37)
# ---------------------------------------------------------------------------


class TestDeleteUser:
    """Tests for ``Users.delete_user`` (issue #37)."""

    def test_delete_user_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        # Alma typically echoes the deleted user's payload — we can
        # exercise the audit path by returning a stub.
        mock_client.delete_response = MockAlmaResponse(
            body={"primary_id": "tau000000", "status": {"value": "ACTIVE"}}
        )
        users = Users(mock_client)

        response = users.delete_user("tau000000")

        assert len(mock_client.calls["delete"]) == 1
        call = mock_client.calls["delete"][0]
        assert call["endpoint"] == "almaws/v1/users/tau000000"
        # Should not pass any query params.
        assert call["params"] is None
        # Response is returned for audit, including the echoed body.
        assert response.data["primary_id"] == "tau000000"

    def test_delete_user_strips_id_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.delete_user("  tau000000  ")

        # Whitespace stripped from the endpoint URL.
        assert (
            mock_client.calls["delete"][0]["endpoint"]
            == "almaws/v1/users/tau000000"
        )

    def test_delete_user_raises_on_empty_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.delete_user("")

    def test_delete_user_raises_on_whitespace_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.delete_user("   ")

    def test_delete_user_raises_on_non_string_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.delete_user(None)  # type: ignore[arg-type]

    def test_delete_user_propagates_api_error(self):
        """When Alma rejects (e.g. user has active loans/fees), the
        AlmaAPIError must propagate so callers can dispatch on
        alma_code / tracking_id."""
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "User has active loans/fees",
            status_code=400,
            alma_code="401890",
            tracking_id="tracking-abc-123",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.delete_user("tau000000")

        # The exception still carries the diagnostic fields callers need.
        assert exc_info.value.alma_code == "401890"
        assert exc_info.value.tracking_id == "tracking-abc-123"


# ---------------------------------------------------------------------------
# list_user_loans  (issue #40)
# ---------------------------------------------------------------------------


class TestListUserLoans:
    """Tests for ``Users.list_user_loans`` (issue #40)."""

    def test_list_user_loans_calls_correct_endpoint_with_defaults(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "item_loan": [
                    {"loan_id": "loan-1", "item_barcode": "B1"},
                    {"loan_id": "loan-2", "item_barcode": "B2"},
                ],
                "total_record_count": 2,
            }
        )
        users = Users(mock_client)

        result = users.list_user_loans("u1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans"
        # Default limit/offset are forwarded; expand/order_by absent.
        assert call["params"] == {"limit": 10, "offset": 0}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["loan_id"] == "loan-1"

    def test_list_user_loans_forwards_limit_offset(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"item_loan": [], "total_record_count": 0}
        )
        users = Users(mock_client)

        users.list_user_loans("u1", limit=50, offset=100)

        call = mock_client.calls["get"][0]
        assert call["params"] == {"limit": 50, "offset": 100}

    def test_list_user_loans_forwards_expand(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"item_loan": []})
        users = Users(mock_client)

        users.list_user_loans("u1", expand="renewable")

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 10,
            "offset": 0,
            "expand": "renewable",
        }

    def test_list_user_loans_forwards_order_by(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"item_loan": []})
        users = Users(mock_client)

        users.list_user_loans("u1", order_by="due_date")

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 10,
            "offset": 0,
            "order_by": "due_date",
        }

    def test_list_user_loans_forwards_all_optional_params(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"item_loan": []})
        users = Users(mock_client)

        users.list_user_loans(
            "u1", limit=25, offset=50, expand="renewable", order_by="barcode"
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 25,
            "offset": 50,
            "expand": "renewable",
            "order_by": "barcode",
        }

    def test_list_user_loans_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"item_loan": []})
        users = Users(mock_client)

        users.list_user_loans("  u1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans"

    def test_list_user_loans_returns_empty_list_on_missing_key(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        users = Users(mock_client)

        result = users.list_user_loans("u1")

        assert result == []

    def test_list_user_loans_handles_single_dict_response(self):
        """A single loan returned as dict (not list) is normalised."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "item_loan": {"loan_id": "only-loan"},
                "total_record_count": 1,
            }
        )
        users = Users(mock_client)

        result = users.list_user_loans("u1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["loan_id"] == "only-loan"

    def test_list_user_loans_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_loans("")

    def test_list_user_loans_raises_on_whitespace_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_loans("   ")

    def test_list_user_loans_raises_on_non_string_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_loans(None)  # type: ignore[arg-type]

    def test_list_user_loans_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=500)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.list_user_loans("u1")


# ---------------------------------------------------------------------------
# create_user_loan  (issue #40)
# ---------------------------------------------------------------------------


class TestCreateUserLoan:
    """Tests for ``Users.create_user_loan`` (issue #40)."""

    def test_create_user_loan_with_item_barcode_only(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"loan_id": "loan-99", "item_barcode": "B1"}
        )
        users = Users(mock_client)

        response = users.create_user_loan("u1", item_barcode="B1")

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans"
        # item_barcode is a query param, NOT a body field.
        assert call["params"] == {"item_barcode": "B1"}
        # No body when loan_data is None.
        assert call["data"] is None
        assert response.data["loan_id"] == "loan-99"

    def test_create_user_loan_with_item_pid_only(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"loan_id": "loan-99"}
        )
        users = Users(mock_client)

        users.create_user_loan("u1", item_pid="23123456")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans"
        assert call["params"] == {"item_pid": "23123456"}
        assert call["data"] is None

    def test_create_user_loan_forwards_user_id_type(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"loan_id": "loan-99"}
        )
        users = Users(mock_client)

        users.create_user_loan(
            "u1", item_barcode="B1", user_id_type="all_unique"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "item_barcode": "B1",
            "user_id_type": "all_unique",
        }

    def test_create_user_loan_forwards_loan_data_as_body(self):
        from almaapitk.domains.users import Users

        loan_body = {
            "circ_desk": {"value": "DEFAULT_CIRC_DESK"},
            "library": {"value": "MAIN"},
        }

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"loan_id": "loan-99"}
        )
        users = Users(mock_client)

        users.create_user_loan(
            "u1", item_barcode="B1", loan_data=loan_body
        )

        call = mock_client.calls["post"][0]
        # loan_data forwarded verbatim as body.
        assert call["data"] == loan_body
        # Identifier still in query params.
        assert call["params"] == {"item_barcode": "B1"}

    def test_create_user_loan_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"loan_id": "loan-99"}
        )
        users = Users(mock_client)

        users.create_user_loan("  u1  ", item_barcode="B1")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans"

    def test_create_user_loan_raises_when_both_item_identifiers_supplied(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_loan(
                "u1", item_barcode="B1", item_pid="23123456"
            )
        # No HTTP call should be made on validation failure.
        assert mock_client.calls["post"] == []

    def test_create_user_loan_raises_when_neither_item_identifier_supplied(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_loan("u1")
        assert mock_client.calls["post"] == []

    def test_create_user_loan_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_loan("", item_barcode="B1")

    def test_create_user_loan_raises_on_whitespace_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_loan("   ", item_barcode="B1")

    def test_create_user_loan_raises_on_non_dict_loan_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_loan(
                "u1",
                item_barcode="B1",
                loan_data="not-a-dict",  # type: ignore[arg-type]
            )

    def test_create_user_loan_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Item is not loanable",
            status_code=400,
            alma_code="401651",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.create_user_loan("u1", item_barcode="B1")

        assert exc_info.value.alma_code == "401651"


# ---------------------------------------------------------------------------
# get_user_loan  (issue #40)
# ---------------------------------------------------------------------------


class TestGetUserLoan:
    """Tests for ``Users.get_user_loan`` (issue #40)."""

    def test_get_user_loan_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "loan_id": "loan-1",
                "item_barcode": "B1",
                "due_date": "2026-06-01Z",
            }
        )
        users = Users(mock_client)

        result = users.get_user_loan("u1", "loan-1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans/loan-1"
        # No params on a plain GET.
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["loan_id"] == "loan-1"

    def test_get_user_loan_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"loan_id": "loan-1"})
        users = Users(mock_client)

        users.get_user_loan("  u1  ", "  loan-1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans/loan-1"

    def test_get_user_loan_returns_empty_dict_on_empty_body(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        result = users.get_user_loan("u1", "loan-1")

        assert result == {}

    def test_get_user_loan_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_loan("", "loan-1")

    def test_get_user_loan_raises_on_empty_loan_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_loan("u1", "")

    def test_get_user_loan_raises_on_non_string_loan_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_loan("u1", None)  # type: ignore[arg-type]

    def test_get_user_loan_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Loan ID does not exist", status_code=400, alma_code="401823"
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.get_user_loan("u1", "loan-1")

        assert exc_info.value.alma_code == "401823"


# ---------------------------------------------------------------------------
# renew_user_loan  (issue #40)
# ---------------------------------------------------------------------------


class TestRenewUserLoan:
    """Tests for ``Users.renew_user_loan`` (issue #40)."""

    def test_renew_user_loan_sends_op_renew_with_empty_body(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"loan_id": "loan-1", "due_date": "2026-07-01Z"}
        )
        users = Users(mock_client)

        response = users.renew_user_loan("u1", "loan-1")

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans/loan-1"
        assert call["params"] == {"op": "renew"}
        # Empty body — renewal is op-driven, not body-driven.
        assert call["data"] is None
        assert response.data["loan_id"] == "loan-1"

    def test_renew_user_loan_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"loan_id": "loan-1"})
        users = Users(mock_client)

        users.renew_user_loan("  u1  ", "  loan-1  ")

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans/loan-1"

    def test_renew_user_loan_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.renew_user_loan("", "loan-1")

    def test_renew_user_loan_raises_on_empty_loan_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.renew_user_loan("u1", "")

    def test_renew_user_loan_raises_on_non_string_ids(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.renew_user_loan(None, "loan-1")  # type: ignore[arg-type]
        with pytest.raises(AlmaValidationError):
            users.renew_user_loan("u1", None)  # type: ignore[arg-type]

    def test_renew_user_loan_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Cannot renew loan", status_code=400, alma_code="401822"
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.renew_user_loan("u1", "loan-1")

        assert exc_info.value.alma_code == "401822"


# ---------------------------------------------------------------------------
# update_user_loan  (issue #40)
# ---------------------------------------------------------------------------


class TestUpdateUserLoan:
    """Tests for ``Users.update_user_loan`` (issue #40)."""

    def test_update_user_loan_puts_body_verbatim(self):
        from almaapitk.domains.users import Users

        loan_body = {
            "loan_id": "loan-1",
            "due_date": "2026-08-01Z",
        }

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={"loan_id": "loan-1", "due_date": "2026-08-01Z"}
        )
        users = Users(mock_client)

        response = users.update_user_loan("u1", "loan-1", loan_body)

        assert len(mock_client.calls["put"]) == 1
        call = mock_client.calls["put"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans/loan-1"
        # Body is the operator-supplied dict verbatim.
        assert call["data"] == loan_body
        # No query params (notify_user is not exposed by the wrapper).
        assert call["params"] is None
        assert response.data["due_date"] == "2026-08-01Z"

    def test_update_user_loan_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(body={"loan_id": "loan-1"})
        users = Users(mock_client)

        users.update_user_loan(
            "  u1  ", "  loan-1  ", {"due_date": "2026-08-01Z"}
        )

        call = mock_client.calls["put"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/loans/loan-1"

    def test_update_user_loan_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.update_user_loan("", "loan-1", {"due_date": "2026-08-01Z"})

    def test_update_user_loan_raises_on_empty_loan_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.update_user_loan("u1", "", {"due_date": "2026-08-01Z"})

    def test_update_user_loan_raises_on_empty_loan_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.update_user_loan("u1", "loan-1", {})

    def test_update_user_loan_raises_on_non_dict_loan_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.update_user_loan(
                "u1", "loan-1", "not-a-dict"  # type: ignore[arg-type]
            )

    def test_update_user_loan_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Due date cannot be in the past",
            status_code=400,
            alma_code="401681",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.update_user_loan(
                "u1", "loan-1", {"due_date": "2020-01-01Z"}
            )

        assert exc_info.value.alma_code == "401681"


# ---------------------------------------------------------------------------
# list_user_requests  (issue #41)
# ---------------------------------------------------------------------------


class TestListUserRequests:
    """Tests for ``Users.list_user_requests`` (issue #41)."""

    def test_list_user_requests_calls_correct_endpoint_with_defaults(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_request": [
                    {"request_id": "req-1", "request_type": "HOLD"},
                    {"request_id": "req-2", "request_type": "BOOKING"},
                ],
                "total_record_count": 2,
            }
        )
        users = Users(mock_client)

        result = users.list_user_requests("u1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests"
        # Default limit/offset are forwarded; request_type / status absent.
        assert call["params"] == {"limit": 10, "offset": 0}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["request_id"] == "req-1"

    def test_list_user_requests_forwards_request_type(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"user_request": []})
        users = Users(mock_client)

        users.list_user_requests("u1", request_type="HOLD")

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 10,
            "offset": 0,
            "request_type": "HOLD",
        }

    def test_list_user_requests_forwards_status(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"user_request": []})
        users = Users(mock_client)

        users.list_user_requests("u1", status="history")

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 10,
            "offset": 0,
            "status": "history",
        }

    def test_list_user_requests_forwards_limit_offset(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"user_request": []})
        users = Users(mock_client)

        users.list_user_requests("u1", limit=50, offset=100)

        call = mock_client.calls["get"][0]
        assert call["params"] == {"limit": 50, "offset": 100}

    def test_list_user_requests_forwards_all_filters(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"user_request": []})
        users = Users(mock_client)

        users.list_user_requests(
            "u1",
            request_type="DIGITIZATION",
            status="active",
            limit=25,
            offset=50,
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 25,
            "offset": 50,
            "request_type": "DIGITIZATION",
            "status": "active",
        }

    def test_list_user_requests_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"user_request": []})
        users = Users(mock_client)

        users.list_user_requests("  u1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests"

    def test_list_user_requests_returns_empty_list_on_missing_key(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        users = Users(mock_client)

        result = users.list_user_requests("u1")

        assert result == []

    def test_list_user_requests_handles_single_dict_response(self):
        """A single request returned as dict (not list) is normalised."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_request": {"request_id": "only-req"},
                "total_record_count": 1,
            }
        )
        users = Users(mock_client)

        result = users.list_user_requests("u1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["request_id"] == "only-req"

    def test_list_user_requests_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_requests("")

    def test_list_user_requests_raises_on_whitespace_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_requests("   ")

    def test_list_user_requests_raises_on_non_string_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_requests(None)  # type: ignore[arg-type]

    def test_list_user_requests_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError("boom", status_code=500)
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError):
            users.list_user_requests("u1")


# ---------------------------------------------------------------------------
# create_user_request  (issue #41)
# ---------------------------------------------------------------------------


class TestCreateUserRequest:
    """Tests for ``Users.create_user_request`` (issue #41)."""

    def test_create_user_request_with_mms_id_only(self):
        from almaapitk.domains.users import Users

        body = {
            "request_type": "HOLD",
            "pickup_location_type": "LIBRARY",
            "pickup_location_library": "MAIN",
        }

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "req-99", "request_type": "HOLD"}
        )
        users = Users(mock_client)

        response = users.create_user_request(
            "u1", request_data=body, mms_id="9981234567"
        )

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests"
        assert call["params"] == {"mms_id": "9981234567"}
        # request_data forwarded verbatim as body.
        assert call["data"] == body
        assert response.data["request_id"] == "req-99"

    def test_create_user_request_with_item_pid_only(self):
        from almaapitk.domains.users import Users

        body = {"request_type": "BOOKING"}

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "req-99"}
        )
        users = Users(mock_client)

        users.create_user_request(
            "u1", request_data=body, item_pid="23123456"
        )

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests"
        assert call["params"] == {"item_pid": "23123456"}
        assert call["data"] == body

    def test_create_user_request_with_holding_id_only(self):
        from almaapitk.domains.users import Users

        body = {"request_type": "HOLD"}

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "req-99"}
        )
        users = Users(mock_client)

        users.create_user_request(
            "u1", request_data=body, holding_id="hol-1"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {"holding_id": "hol-1"}
        assert call["data"] == body

    def test_create_user_request_with_mms_and_item_pid(self):
        from almaapitk.domains.users import Users

        body = {"request_type": "HOLD"}

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "req-99"}
        )
        users = Users(mock_client)

        # The wrapper does NOT enforce title-vs-item exclusivity; both
        # are forwarded so Alma can apply the institution-specific
        # rules. Cf. create_user_loan, which DOES enforce one-of for
        # item_barcode/item_pid — but the request endpoint takes a
        # different shape per swagger.
        users.create_user_request(
            "u1",
            request_data=body,
            mms_id="9981234567",
            item_pid="23123456",
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "mms_id": "9981234567",
            "item_pid": "23123456",
        }

    def test_create_user_request_forwards_user_id_type(self):
        from almaapitk.domains.users import Users

        body = {"request_type": "HOLD"}

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "req-99"}
        )
        users = Users(mock_client)

        users.create_user_request(
            "u1",
            request_data=body,
            mms_id="9981234567",
            user_id_type="all_unique",
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "mms_id": "9981234567",
            "user_id_type": "all_unique",
        }

    def test_create_user_request_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "req-99"}
        )
        users = Users(mock_client)

        users.create_user_request(
            "  u1  ",
            request_data={"request_type": "HOLD"},
            mms_id="9981234567",
        )

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests"

    def test_create_user_request_raises_when_no_resource_identifier_supplied(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_request(
                "u1", request_data={"request_type": "HOLD"}
            )
        # No HTTP call should be made on validation failure.
        assert mock_client.calls["post"] == []

    def test_create_user_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_request(
                "",
                request_data={"request_type": "HOLD"},
                mms_id="9981234567",
            )

    def test_create_user_request_raises_on_whitespace_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_request(
                "   ",
                request_data={"request_type": "HOLD"},
                mms_id="9981234567",
            )

    def test_create_user_request_raises_on_empty_request_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_request(
                "u1", request_data={}, mms_id="9981234567"
            )

    def test_create_user_request_raises_on_non_dict_request_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_request(
                "u1",
                request_data="not-a-dict",  # type: ignore[arg-type]
                mms_id="9981234567",
            )

    def test_create_user_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "No items can fulfill the submitted request",
            status_code=400,
            alma_code="401129",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.create_user_request(
                "u1",
                request_data={"request_type": "HOLD"},
                mms_id="9981234567",
            )

        assert exc_info.value.alma_code == "401129"


# ---------------------------------------------------------------------------
# get_user_request  (issue #41)
# ---------------------------------------------------------------------------


class TestGetUserRequest:
    """Tests for ``Users.get_user_request`` (issue #41)."""

    def test_get_user_request_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "request_id": "req-1",
                "request_type": "HOLD",
                "request_status": "ACTIVE",
            }
        )
        users = Users(mock_client)

        result = users.get_user_request("u1", "req-1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests/req-1"
        # No params on a plain GET.
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["request_id"] == "req-1"

    def test_get_user_request_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"request_id": "req-1"}
        )
        users = Users(mock_client)

        users.get_user_request("  u1  ", "  req-1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests/req-1"

    def test_get_user_request_returns_empty_dict_on_empty_body(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        result = users.get_user_request("u1", "req-1")

        assert result == {}

    def test_get_user_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_request("", "req-1")

    def test_get_user_request_raises_on_empty_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_request("u1", "")

    def test_get_user_request_raises_on_non_string_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_request("u1", None)  # type: ignore[arg-type]

    def test_get_user_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Request Identifier not found",
            status_code=400,
            alma_code="401694",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.get_user_request("u1", "req-1")

        assert exc_info.value.alma_code == "401694"


# ---------------------------------------------------------------------------
# cancel_user_request  (issue #41)
# ---------------------------------------------------------------------------


class TestCancelUserRequest:
    """Tests for ``Users.cancel_user_request`` (issue #41)."""

    def test_cancel_user_request_with_reason_only(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        # Swagger says 204 No Content — body is empty.
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        response = users.cancel_user_request(
            "u1", "req-1", reason="CancelledAtPatronRequest"
        )

        assert len(mock_client.calls["delete"]) == 1
        call = mock_client.calls["delete"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests/req-1"
        # Reason is forwarded as a QUERY param on DELETE.
        assert call["params"] == {"reason": "CancelledAtPatronRequest"}
        # Empty body for 204 response — wrapper still returns it.
        assert response.data == {}

    def test_cancel_user_request_with_reason_and_note(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.cancel_user_request(
            "u1",
            "req-1",
            reason="CancelledAtPatronRequest",
            note="Patron called and asked to cancel",
        )

        call = mock_client.calls["delete"][0]
        assert call["params"] == {
            "reason": "CancelledAtPatronRequest",
            "note": "Patron called and asked to cancel",
        }

    def test_cancel_user_request_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.cancel_user_request(
            "  u1  ",
            "  req-1  ",
            reason="  CancelledAtPatronRequest  ",
        )

        call = mock_client.calls["delete"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests/req-1"
        # Reason whitespace is stripped.
        assert call["params"] == {"reason": "CancelledAtPatronRequest"}

    def test_cancel_user_request_raises_on_empty_reason(self):
        """Reason is REQUIRED per the swagger."""
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.cancel_user_request("u1", "req-1", reason="")
        # No HTTP call on validation failure.
        assert mock_client.calls["delete"] == []

    def test_cancel_user_request_raises_on_whitespace_reason(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.cancel_user_request("u1", "req-1", reason="   ")

    def test_cancel_user_request_raises_on_non_string_reason(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.cancel_user_request(
                "u1", "req-1", reason=None  # type: ignore[arg-type]
            )

    def test_cancel_user_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.cancel_user_request(
                "", "req-1", reason="CancelledAtPatronRequest"
            )

    def test_cancel_user_request_raises_on_empty_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.cancel_user_request(
                "u1", "", reason="CancelledAtPatronRequest"
            )

    def test_cancel_user_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Request Identifier not found",
            status_code=400,
            alma_code="401694",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.cancel_user_request(
                "u1", "req-1", reason="CancelledAtPatronRequest"
            )

        assert exc_info.value.alma_code == "401694"


# ---------------------------------------------------------------------------
# perform_user_request_action  (issue #41)
# ---------------------------------------------------------------------------


class TestPerformUserRequestAction:
    """Tests for ``Users.perform_user_request_action`` (issue #41)."""

    def test_perform_user_request_action_sends_op_as_param(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "req-1", "request_status": "IN_PROCESS"}
        )
        users = Users(mock_client)

        response = users.perform_user_request_action(
            "u1", "req-1", op="next_step"
        )

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests/req-1"
        assert call["params"] == {"op": "next_step"}
        # Empty body — action is op-driven, not body-driven.
        assert call["data"] is None
        assert response.data["request_id"] == "req-1"

    def test_perform_user_request_action_accepts_arbitrary_op(self):
        """Wrapper does not enumerate ops; Alma rejects invalid ones."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_request_action(
            "u1", "req-1", op="some_future_op"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {"op": "some_future_op"}

    def test_perform_user_request_action_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_request_action(
            "  u1  ", "  req-1  ", op="  next_step  "
        )

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests/req-1"
        assert call["params"] == {"op": "next_step"}

    def test_perform_user_request_action_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_request_action("", "req-1", op="next_step")

    def test_perform_user_request_action_raises_on_empty_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_request_action("u1", "", op="next_step")

    def test_perform_user_request_action_raises_on_empty_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_request_action("u1", "req-1", op="")

    def test_perform_user_request_action_raises_on_whitespace_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_request_action("u1", "req-1", op="   ")

    def test_perform_user_request_action_raises_on_non_string_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_request_action(
                "u1", "req-1", op=None  # type: ignore[arg-type]
            )

    def test_perform_user_request_action_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Failed to find a request for the given request ID",
            status_code=400,
            alma_code="401907",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.perform_user_request_action(
                "u1", "req-1", op="next_step"
            )

        assert exc_info.value.alma_code == "401907"


# ---------------------------------------------------------------------------
# update_user_request  (issue #41)
# ---------------------------------------------------------------------------


class TestUpdateUserRequest:
    """Tests for ``Users.update_user_request`` (issue #41)."""

    def test_update_user_request_puts_body_verbatim(self):
        from almaapitk.domains.users import Users

        body = {
            "request_type": "HOLD",
            "pickup_location_library": "OTHER_LIB",
        }

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={"request_id": "req-1", "pickup_location_library": "OTHER_LIB"}
        )
        users = Users(mock_client)

        response = users.update_user_request("u1", "req-1", body)

        assert len(mock_client.calls["put"]) == 1
        call = mock_client.calls["put"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests/req-1"
        # Body forwarded verbatim.
        assert call["data"] == body
        # No query params on update.
        assert call["params"] is None
        assert response.data["request_id"] == "req-1"

    def test_update_user_request_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={"request_id": "req-1"}
        )
        users = Users(mock_client)

        users.update_user_request(
            "  u1  ", "  req-1  ", {"request_type": "HOLD"}
        )

        call = mock_client.calls["put"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/requests/req-1"

    def test_update_user_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.update_user_request("", "req-1", {"request_type": "HOLD"})

    def test_update_user_request_raises_on_empty_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.update_user_request("u1", "", {"request_type": "HOLD"})

    def test_update_user_request_raises_on_empty_request_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.update_user_request("u1", "req-1", {})

    def test_update_user_request_raises_on_non_dict_request_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.update_user_request(
                "u1", "req-1", "not-a-dict"  # type: ignore[arg-type]
            )

    def test_update_user_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Invalid partial digitization volume or issue",
            status_code=400,
            alma_code="60330",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.update_user_request(
                "u1", "req-1", {"request_type": "DIGITIZATION"}
            )

        assert exc_info.value.alma_code == "60330"


# ---------------------------------------------------------------------------
# User-note helpers (issue #119)
# ---------------------------------------------------------------------------


class TestListUserNotes:
    """Tests for ``Users.list_user_notes`` (issue #119)."""

    def test_list_user_notes_returns_notes_from_wrapped_list(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "primary_id": "u1",
                "user_note": {
                    "user_note": [
                        {
                            "note_type": {"value": "CIRCULATION"},
                            "note_text": "Returned damaged book",
                        },
                        {
                            "note_type": {"value": "OTHER"},
                            "note_text": "VIP patron",
                        },
                    ]
                },
            }
        )
        users = Users(mock_client)

        notes = users.list_user_notes("u1")

        assert len(notes) == 2
        assert notes[0]["note_text"] == "Returned damaged book"
        assert notes[1]["note_type"]["value"] == "OTHER"
        # Read-only: exactly one GET, zero PUTs.
        assert len(mock_client.calls["get"]) == 1
        assert mock_client.calls["get"][0]["endpoint"] == "almaws/v1/users/u1"
        assert mock_client.calls["put"] == []

    def test_list_user_notes_normalizes_single_dict_to_list(self):
        from almaapitk.domains.users import Users

        # Alma quirk: single-note arrays sometimes serialize as a bare dict.
        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_note": {
                    "user_note": {
                        "note_type": {"value": "CIRCULATION"},
                        "note_text": "Only note",
                    }
                }
            }
        )
        users = Users(mock_client)

        notes = users.list_user_notes("u1")

        assert isinstance(notes, list)
        assert len(notes) == 1
        assert notes[0]["note_text"] == "Only note"

    def test_list_user_notes_returns_empty_when_wrapper_missing(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"primary_id": "u1"})
        users = Users(mock_client)

        assert users.list_user_notes("u1") == []

    def test_list_user_notes_returns_empty_when_inner_missing(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user_note": {}}
        )
        users = Users(mock_client)

        assert users.list_user_notes("u1") == []

    def test_list_user_notes_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_notes("")
        with pytest.raises(AlmaValidationError):
            users.list_user_notes("   ")

    def test_list_user_notes_raises_on_non_string_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_notes(123)  # type: ignore[arg-type]


class TestAddUserNote:
    """Tests for ``Users.add_user_note`` (issue #119)."""

    def test_add_user_note_appends_to_existing_list(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "primary_id": "u1",
                "user_note": {
                    "user_note": [
                        {
                            "note_type": {"value": "OTHER"},
                            "note_text": "Existing",
                        }
                    ]
                },
            }
        )
        mock_client.put_response = MockAlmaResponse(body={"primary_id": "u1"})
        users = Users(mock_client)

        response = users.add_user_note(
            "u1",
            "Returned damaged book on 2026-05-08",
            note_type="CIRCULATION",
        )

        # Two HTTP requests: one GET (read), one PUT (write).
        assert len(mock_client.calls["get"]) == 1
        assert len(mock_client.calls["put"]) == 1
        put_call = mock_client.calls["put"][0]
        assert put_call["endpoint"] == "almaws/v1/users/u1"

        sent_notes = put_call["data"]["user_note"]
        assert len(sent_notes) == 2
        # The existing note is preserved.
        assert sent_notes[0]["note_text"] == "Existing"
        # The new note carries the value-wrapped note_type idiom.
        new_note = sent_notes[1]
        assert new_note["note_type"] == {"value": "CIRCULATION"}
        assert new_note["note_text"] == "Returned damaged book on 2026-05-08"
        assert new_note["user_viewable"] is False
        assert new_note["popup_note"] is False
        assert response.data == {"primary_id": "u1"}

    def test_add_user_note_creates_flat_list_when_field_missing(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"primary_id": "u1"})
        mock_client.put_response = MockAlmaResponse(body={"primary_id": "u1"})
        users = Users(mock_client)

        users.add_user_note("u1", "First note", note_type="OTHER")

        # Per Alma's JSON schema, user_note is a flat List<UserNote>.
        # See issue #119 R10 regression for the wrapped-shape rejection.
        sent = mock_client.calls["put"][0]["data"]
        assert sent["user_note"] == [
            {
                "note_type": {"value": "OTHER"},
                "note_text": "First note",
                "user_viewable": False,
                "popup_note": False,
            }
        ]

    def test_add_user_note_normalizes_single_dict_to_list_before_append(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_note": {
                    "user_note": {
                        "note_type": {"value": "OTHER"},
                        "note_text": "Pre-existing single note",
                    }
                }
            }
        )
        mock_client.put_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.add_user_note("u1", "Brand new note")

        sent_notes = mock_client.calls["put"][0]["data"]["user_note"]
        assert len(sent_notes) == 2
        assert sent_notes[0]["note_text"] == "Pre-existing single note"
        assert sent_notes[1]["note_text"] == "Brand new note"

    def test_add_user_note_honours_visibility_flags(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"primary_id": "u1"})
        mock_client.put_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.add_user_note(
            "u1",
            "Public reminder",
            note_type="OTHER",
            user_viewable=True,
            popup_note=True,
        )

        appended = mock_client.calls["put"][0]["data"]["user_note"][0]
        assert appended["user_viewable"] is True
        assert appended["popup_note"] is True

    def test_add_user_note_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.add_user_note("", "text")

    def test_add_user_note_raises_on_empty_note_text(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.add_user_note("u1", "")
        with pytest.raises(AlmaValidationError):
            users.add_user_note("u1", "   ")

    def test_add_user_note_raises_on_non_string_note_text(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.add_user_note("u1", None)  # type: ignore[arg-type]

    def test_add_user_note_raises_on_empty_note_type(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.add_user_note("u1", "text", note_type="")


class TestRemoveUserNotes:
    """Tests for ``Users.remove_user_notes`` (issue #119)."""

    def test_remove_user_notes_filters_by_predicate(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "primary_id": "u1",
                "user_note": {
                    "user_note": [
                        {
                            "note_type": {"value": "CIRCULATION"},
                            "note_text": "Stale circulation note",
                        },
                        {
                            "note_type": {"value": "OTHER"},
                            "note_text": "Keep me",
                        },
                        {
                            "note_type": {"value": "CIRCULATION"},
                            "note_text": "Another stale circ note",
                        },
                    ]
                },
            }
        )
        mock_client.put_response = MockAlmaResponse(body={"primary_id": "u1"})
        users = Users(mock_client)

        response = users.remove_user_notes(
            "u1",
            predicate=lambda n: n.get("note_type", {}).get("value") == "CIRCULATION",
        )

        # GET + PUT, in that order.
        assert len(mock_client.calls["get"]) == 1
        assert len(mock_client.calls["put"]) == 1
        put_call = mock_client.calls["put"][0]
        kept = put_call["data"]["user_note"]
        assert len(kept) == 1
        assert kept[0]["note_text"] == "Keep me"
        assert response.data == {"primary_id": "u1"}

    def test_remove_user_notes_handles_single_dict_form(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_note": {
                    "user_note": {
                        "note_type": {"value": "OTHER"},
                        "note_text": "delete me",
                    }
                }
            }
        )
        mock_client.put_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.remove_user_notes("u1", predicate=lambda n: True)

        kept = mock_client.calls["put"][0]["data"]["user_note"]
        assert kept == []

    def test_remove_user_notes_with_no_existing_notes_puts_empty_list(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"primary_id": "u1"})
        mock_client.put_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.remove_user_notes("u1", predicate=lambda n: True)

        sent = mock_client.calls["put"][0]["data"]
        assert sent["user_note"] == []

    def test_remove_user_notes_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.remove_user_notes("", predicate=lambda n: True)

    def test_remove_user_notes_raises_on_non_callable_predicate(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.remove_user_notes("u1", predicate="not callable")  # type: ignore[arg-type]

    def test_remove_user_notes_propagates_predicate_exception(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_note": {
                    "user_note": [{"note_text": "x"}]
                }
            }
        )
        users = Users(mock_client)

        def broken(_note):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            users.remove_user_notes("u1", predicate=broken)
        # PUT must not be issued when predicate explodes.
        assert mock_client.calls["put"] == []


# ---------------------------------------------------------------------------
# create_user_rs_request  (issue #42)
# ---------------------------------------------------------------------------


class TestCreateUserRsRequest:
    """Tests for ``Users.create_user_rs_request`` (issue #42)."""

    def test_create_user_rs_request_posts_body_verbatim(self):
        from almaapitk.domains.users import Users

        body = {
            "citation_type": "BK",
            "format": "PHYSICAL",
            "title": "Sample title",
            "owner": {"value": "ILL"},
        }

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "rs-42", "external_id": "ext-1"}
        )
        users = Users(mock_client)

        response = users.create_user_rs_request("u1", request_data=body)

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests"
        )
        # No optional kwargs => no query params forwarded.
        assert call["params"] is None
        # Body forwarded verbatim.
        assert call["data"] == body
        assert response.data["request_id"] == "rs-42"

    def test_create_user_rs_request_forwards_user_id_type(self):
        from almaapitk.domains.users import Users

        body = {"citation_type": "BK", "title": "Sample"}

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "rs-42"}
        )
        users = Users(mock_client)

        users.create_user_rs_request(
            "u1", request_data=body, user_id_type="all_unique"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {"user_id_type": "all_unique"}

    def test_create_user_rs_request_forwards_override_blocks_true(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "rs-42"}
        )
        users = Users(mock_client)

        users.create_user_rs_request(
            "u1",
            request_data={"citation_type": "BK"},
            override_blocks=True,
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {"override_blocks": "true"}

    def test_create_user_rs_request_forwards_override_blocks_false(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "rs-42"}
        )
        users = Users(mock_client)

        users.create_user_rs_request(
            "u1",
            request_data={"citation_type": "BK"},
            override_blocks=False,
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {"override_blocks": "false"}

    def test_create_user_rs_request_forwards_all_query_params(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "rs-42"}
        )
        users = Users(mock_client)

        users.create_user_rs_request(
            "u1",
            request_data={"citation_type": "BK"},
            user_id_type="all_unique",
            override_blocks=True,
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "user_id_type": "all_unique",
            "override_blocks": "true",
        }

    def test_create_user_rs_request_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "rs-42"}
        )
        users = Users(mock_client)

        users.create_user_rs_request(
            "  u1  ", request_data={"citation_type": "BK"}
        )

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests"
        )

    def test_create_user_rs_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_rs_request(
                "", request_data={"citation_type": "BK"}
            )
        assert mock_client.calls["post"] == []

    def test_create_user_rs_request_raises_on_whitespace_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_rs_request(
                "   ", request_data={"citation_type": "BK"}
            )

    def test_create_user_rs_request_raises_on_empty_request_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_rs_request("u1", request_data={})

    def test_create_user_rs_request_raises_on_non_dict_request_data(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_rs_request(
                "u1", request_data="not-a-dict"  # type: ignore[arg-type]
            )

    def test_create_user_rs_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Patron is not affiliated with a resource sharing library",
            status_code=400,
            alma_code="401768",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.create_user_rs_request(
                "u1", request_data={"citation_type": "BK"}
            )

        assert exc_info.value.alma_code == "401768"


# ---------------------------------------------------------------------------
# get_user_rs_request  (issue #42)
# ---------------------------------------------------------------------------


class TestGetUserRsRequest:
    """Tests for ``Users.get_user_rs_request`` (issue #42)."""

    def test_get_user_rs_request_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "request_id": "rs-1",
                "request_status": "REQUEST_CREATED_BOR",
            }
        )
        users = Users(mock_client)

        result = users.get_user_rs_request("u1", "rs-1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests/rs-1"
        )
        # No optional kwargs => no query params.
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["request_id"] == "rs-1"

    def test_get_user_rs_request_forwards_request_id_type(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"request_id": "rs-1"}
        )
        users = Users(mock_client)

        users.get_user_rs_request(
            "u1", "rs-ext-1", request_id_type="external"
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {"request_id_type": "external"}

    def test_get_user_rs_request_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"request_id": "rs-1"}
        )
        users = Users(mock_client)

        users.get_user_rs_request("  u1  ", "  rs-1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests/rs-1"
        )

    def test_get_user_rs_request_returns_empty_dict_on_empty_body(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        result = users.get_user_rs_request("u1", "rs-1")

        assert result == {}

    def test_get_user_rs_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_rs_request("", "rs-1")

    def test_get_user_rs_request_raises_on_empty_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_rs_request("u1", "")

    def test_get_user_rs_request_raises_on_non_string_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_rs_request(
                "u1", None  # type: ignore[arg-type]
            )

    def test_get_user_rs_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "No result found for given parameters",
            status_code=400,
            alma_code="40166450",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.get_user_rs_request("u1", "rs-1")

        assert exc_info.value.alma_code == "40166450"


# ---------------------------------------------------------------------------
# cancel_user_rs_request  (issue #42)
# ---------------------------------------------------------------------------


class TestCancelUserRsRequest:
    """Tests for ``Users.cancel_user_rs_request`` (issue #42)."""

    def test_cancel_user_rs_request_no_kwargs(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        # Swagger says 204 No Content — body is empty.
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        response = users.cancel_user_rs_request("u1", "rs-1")

        assert len(mock_client.calls["delete"]) == 1
        call = mock_client.calls["delete"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests/rs-1"
        )
        # No optional kwargs => no query params (reason is OPTIONAL on
        # the RS DELETE endpoint per swagger, unlike the regular
        # cancel_user_request).
        assert call["params"] is None
        # Empty body for 204 response — wrapper still returns it.
        assert response.data == {}

    def test_cancel_user_rs_request_with_reason(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.cancel_user_rs_request(
            "u1", "rs-1", reason="CancelledAtPatronRequest"
        )

        call = mock_client.calls["delete"][0]
        assert call["params"] == {"reason": "CancelledAtPatronRequest"}

    def test_cancel_user_rs_request_with_all_kwargs(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.cancel_user_rs_request(
            "u1",
            "rs-1",
            reason="CancelledAtPatronRequest",
            note="Patron asked to cancel",
            remove_request=True,
            notify_user=False,
        )

        call = mock_client.calls["delete"][0]
        assert call["params"] == {
            "reason": "CancelledAtPatronRequest",
            "note": "Patron asked to cancel",
            "remove_request": "true",
            "notify_user": "false",
        }

    def test_cancel_user_rs_request_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.cancel_user_rs_request(
            "  u1  ",
            "  rs-1  ",
            reason="  CancelledAtPatronRequest  ",
        )

        call = mock_client.calls["delete"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests/rs-1"
        )
        # Reason whitespace is stripped.
        assert call["params"] == {"reason": "CancelledAtPatronRequest"}

    def test_cancel_user_rs_request_remove_request_false_flag(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.cancel_user_rs_request(
            "u1", "rs-1", remove_request=False, notify_user=True
        )

        call = mock_client.calls["delete"][0]
        assert call["params"] == {
            "remove_request": "false",
            "notify_user": "true",
        }

    def test_cancel_user_rs_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.cancel_user_rs_request("", "rs-1")
        assert mock_client.calls["delete"] == []

    def test_cancel_user_rs_request_raises_on_empty_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.cancel_user_rs_request("u1", "")

    def test_cancel_user_rs_request_raises_on_non_string_reason(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.cancel_user_rs_request(
                "u1", "rs-1", reason=123  # type: ignore[arg-type]
            )

    def test_cancel_user_rs_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Request Identifier not found",
            status_code=400,
            alma_code="401694",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.cancel_user_rs_request("u1", "rs-1")

        assert exc_info.value.alma_code == "401694"


# ---------------------------------------------------------------------------
# perform_user_rs_request_action  (issue #42)
# ---------------------------------------------------------------------------


class TestPerformUserRsRequestAction:
    """Tests for ``Users.perform_user_rs_request_action`` (issue #42)."""

    def test_perform_user_rs_request_action_sends_op_as_param(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "rs-1", "shipping_cost": "12.50"}
        )
        users = Users(mock_client)

        response = users.perform_user_rs_request_action(
            "u1", "rs-1", op="update_shipping"
        )

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests/rs-1"
        )
        assert call["params"] == {"op": "update_shipping"}
        # Empty body — action is op-driven, not body-driven.
        assert call["data"] is None
        assert response.data["request_id"] == "rs-1"

    def test_perform_user_rs_request_action_forwards_shipping_cost(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_rs_request_action(
            "u1", "rs-1", op="update_shipping", shipping_cost="12.50"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "update_shipping",
            "shipping_cost": "12.50",
        }

    def test_perform_user_rs_request_action_forwards_fund_code(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_rs_request_action(
            "u1", "rs-1", op="update_shipping", fund_code="FUND-001"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "update_shipping",
            "fund_code": "FUND-001",
        }

    def test_perform_user_rs_request_action_forwards_all_query_params(
        self,
    ):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_rs_request_action(
            "u1",
            "rs-1",
            op="update_shipping",
            shipping_cost="12.50",
            fund_code="FUND-001",
            request_id_type="external",
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {
            "op": "update_shipping",
            "shipping_cost": "12.50",
            "fund_code": "FUND-001",
            "request_id_type": "external",
        }

    def test_perform_user_rs_request_action_accepts_arbitrary_op(self):
        """Wrapper does not enumerate ops; Alma rejects invalid ones."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_rs_request_action(
            "u1", "rs-1", op="some_future_op"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {"op": "some_future_op"}

    def test_perform_user_rs_request_action_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_rs_request_action(
            "  u1  ", "  rs-1  ", op="  update_shipping  "
        )

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests/rs-1"
        )
        assert call["params"] == {"op": "update_shipping"}

    def test_perform_user_rs_request_action_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_rs_request_action(
                "", "rs-1", op="update_shipping"
            )

    def test_perform_user_rs_request_action_raises_on_empty_request_id(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_rs_request_action(
                "u1", "", op="update_shipping"
            )

    def test_perform_user_rs_request_action_raises_on_empty_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_rs_request_action("u1", "rs-1", op="")

    def test_perform_user_rs_request_action_raises_on_whitespace_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_rs_request_action(
                "u1", "rs-1", op="   "
            )

    def test_perform_user_rs_request_action_raises_on_non_string_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_rs_request_action(
                "u1", "rs-1", op=None  # type: ignore[arg-type]
            )

    def test_perform_user_rs_request_action_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Shipping cost cannot be lower than 0",
            status_code=400,
            alma_code="40166425",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.perform_user_rs_request_action(
                "u1", "rs-1", op="update_shipping", shipping_cost="-1"
            )

        assert exc_info.value.alma_code == "40166425"


# ---------------------------------------------------------------------------
# list_user_purchase_requests  (issue #43)
# ---------------------------------------------------------------------------


class TestListUserPurchaseRequests:
    """Tests for ``Users.list_user_purchase_requests`` (issue #43)."""

    def test_list_user_purchase_requests_defaults(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_request": [
                    {"id": "pr-1", "status": "INREVIEW"},
                    {"id": "pr-2", "status": "APPROVED"},
                ],
                "total_record_count": 2,
            }
        )
        users = Users(mock_client)

        result = users.list_user_purchase_requests("u1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/purchase-requests"
        # Default limit/offset are forwarded; status / user_id_type absent.
        assert call["params"] == {"limit": 10, "offset": 0}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "pr-1"

    def test_list_user_purchase_requests_forwards_status(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user_request": []}
        )
        users = Users(mock_client)

        users.list_user_purchase_requests("u1", status="INREVIEW")

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 10,
            "offset": 0,
            "status": "INREVIEW",
        }

    def test_list_user_purchase_requests_forwards_user_id_type(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user_request": []}
        )
        users = Users(mock_client)

        users.list_user_purchase_requests("u1", user_id_type="all_unique")

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 10,
            "offset": 0,
            "user_id_type": "all_unique",
        }

    def test_list_user_purchase_requests_forwards_limit_offset(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user_request": []}
        )
        users = Users(mock_client)

        users.list_user_purchase_requests("u1", limit=50, offset=100)

        call = mock_client.calls["get"][0]
        assert call["params"] == {"limit": 50, "offset": 100}

    def test_list_user_purchase_requests_forwards_all_filters(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user_request": []}
        )
        users = Users(mock_client)

        users.list_user_purchase_requests(
            "u1",
            status="APPROVED",
            user_id_type="all_unique",
            limit=25,
            offset=50,
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "limit": 25,
            "offset": 50,
            "status": "APPROVED",
            "user_id_type": "all_unique",
        }

    def test_list_user_purchase_requests_strips_whitespace_in_user_id(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"user_request": []}
        )
        users = Users(mock_client)

        users.list_user_purchase_requests("  u1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/users/u1/purchase-requests"

    def test_list_user_purchase_requests_returns_empty_list_on_missing_key(
        self,
    ):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        users = Users(mock_client)

        result = users.list_user_purchase_requests("u1")

        assert result == []

    def test_list_user_purchase_requests_handles_single_dict_response(self):
        """A single record returned as dict (not list) is normalised."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "user_request": {"id": "only-pr"},
                "total_record_count": 1,
            }
        )
        users = Users(mock_client)

        result = users.list_user_purchase_requests("u1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "only-pr"

    def test_list_user_purchase_requests_falls_back_to_purchase_request_key(
        self,
    ):
        """If Alma returns the singular-form key, the wrapper still
        unwraps it."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "purchase_request": [
                    {"id": "pr-1"},
                ],
                "total_record_count": 1,
            }
        )
        users = Users(mock_client)

        result = users.list_user_purchase_requests("u1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "pr-1"

    def test_list_user_purchase_requests_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_purchase_requests("")
        assert mock_client.calls["get"] == []

    def test_list_user_purchase_requests_raises_on_whitespace_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_purchase_requests("   ")

    def test_list_user_purchase_requests_raises_on_non_string_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.list_user_purchase_requests(
                None  # type: ignore[arg-type]
            )

    def test_list_user_purchase_requests_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Purchase request status is not valid",
            status_code=400,
            alma_code="60275",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.list_user_purchase_requests("u1", status="BOGUS")

        assert exc_info.value.alma_code == "60275"


# ---------------------------------------------------------------------------
# create_user_purchase_request  (issue #43)
# ---------------------------------------------------------------------------


class TestCreateUserPurchaseRequest:
    """Tests for ``Users.create_user_purchase_request`` (issue #43)."""

    def test_create_user_purchase_request_posts_body_verbatim(self):
        from almaapitk.domains.users import Users

        body = {
            "resource_metadata": {
                "title": "Sample title",
                "author": "Ada Lovelace",
                "isbn": "9780000000000",
            },
            "format": {"value": "PHYSICAL"},
            "library": {"value": "MAIN"},
        }

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"id": "pr-42", "status": "INREVIEW"}
        )
        users = Users(mock_client)

        response = users.create_user_purchase_request(
            "u1", purchase_request_data=body
        )

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/purchase-requests"
        )
        # No optional kwargs => no query params forwarded.
        assert call["params"] is None
        # Body forwarded verbatim.
        assert call["data"] == body
        assert response.data["id"] == "pr-42"

    def test_create_user_purchase_request_forwards_user_id_type(self):
        from almaapitk.domains.users import Users

        body = {"resource_metadata": {"title": "Sample"}}

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "pr-42"})
        users = Users(mock_client)

        users.create_user_purchase_request(
            "u1", purchase_request_data=body, user_id_type="all_unique"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {"user_id_type": "all_unique"}

    def test_create_user_purchase_request_strips_whitespace_in_user_id(
        self,
    ):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "pr-42"})
        users = Users(mock_client)

        users.create_user_purchase_request(
            "  u1  ",
            purchase_request_data={"resource_metadata": {"title": "x"}},
        )

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/purchase-requests"
        )

    def test_create_user_purchase_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_purchase_request(
                "",
                purchase_request_data={
                    "resource_metadata": {"title": "x"}
                },
            )
        assert mock_client.calls["post"] == []

    def test_create_user_purchase_request_raises_on_whitespace_user_id(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_purchase_request(
                "   ",
                purchase_request_data={
                    "resource_metadata": {"title": "x"}
                },
            )

    def test_create_user_purchase_request_raises_on_empty_request_data(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_purchase_request(
                "u1", purchase_request_data={}
            )

    def test_create_user_purchase_request_raises_on_non_dict_request_data(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.create_user_purchase_request(
                "u1",
                purchase_request_data="not-a-dict",  # type: ignore[arg-type]
            )

    def test_create_user_purchase_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Title is missing",
            status_code=400,
            alma_code="60273",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.create_user_purchase_request(
                "u1",
                purchase_request_data={
                    "resource_metadata": {"author": "Anon"}
                },
            )

        assert exc_info.value.alma_code == "60273"


# ---------------------------------------------------------------------------
# get_user_purchase_request  (issue #43)
# ---------------------------------------------------------------------------


class TestGetUserPurchaseRequest:
    """Tests for ``Users.get_user_purchase_request`` (issue #43)."""

    def test_get_user_purchase_request_calls_correct_endpoint(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"id": "pr-1", "status": "INREVIEW"}
        )
        users = Users(mock_client)

        result = users.get_user_purchase_request("u1", "pr-1")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/purchase-requests/pr-1"
        )
        # No optional kwargs => no query params.
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["id"] == "pr-1"

    def test_get_user_purchase_request_forwards_user_id_type(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"id": "pr-1"})
        users = Users(mock_client)

        users.get_user_purchase_request(
            "u1", "pr-1", user_id_type="all_unique"
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {"user_id_type": "all_unique"}

    def test_get_user_purchase_request_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"id": "pr-1"})
        users = Users(mock_client)

        users.get_user_purchase_request("  u1  ", "  pr-1  ")

        call = mock_client.calls["get"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/purchase-requests/pr-1"
        )

    def test_get_user_purchase_request_returns_empty_dict_on_empty_body(
        self,
    ):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        result = users.get_user_purchase_request("u1", "pr-1")

        assert result == {}

    def test_get_user_purchase_request_raises_on_empty_user_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_purchase_request("", "pr-1")

    def test_get_user_purchase_request_raises_on_empty_request_id(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_purchase_request("u1", "")

    def test_get_user_purchase_request_raises_on_non_string_request_id(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.get_user_purchase_request(
                "u1", None  # type: ignore[arg-type]
            )

    def test_get_user_purchase_request_propagates_api_error(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "The purchase request identifier is not valid",
            status_code=400,
            alma_code="60276",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.get_user_purchase_request("u1", "pr-bogus")

        assert exc_info.value.alma_code == "60276"


# ---------------------------------------------------------------------------
# perform_user_purchase_request_action  (issue #43)
# ---------------------------------------------------------------------------


class TestPerformUserPurchaseRequestAction:
    """Tests for ``Users.perform_user_purchase_request_action`` (issue #43)."""

    def test_perform_user_purchase_request_action_sends_op_as_param(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        response = users.perform_user_purchase_request_action(
            "u1", "pr-1", op="cancel"
        )

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/purchase-requests/pr-1"
        )
        assert call["params"] == {"op": "cancel"}
        # Empty body — action is op-driven, not body-driven.
        assert call["data"] is None
        assert response.data == {}

    def test_perform_user_purchase_request_action_accepts_arbitrary_op(
        self,
    ):
        """Wrapper does not enumerate ops; Alma rejects invalid ones."""
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_purchase_request_action(
            "u1", "pr-1", op="some_future_op"
        )

        call = mock_client.calls["post"][0]
        assert call["params"] == {"op": "some_future_op"}

    def test_perform_user_purchase_request_action_strips_whitespace(self):
        from almaapitk.domains.users import Users

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        users = Users(mock_client)

        users.perform_user_purchase_request_action(
            "  u1  ", "  pr-1  ", op="  cancel  "
        )

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/purchase-requests/pr-1"
        )
        assert call["params"] == {"op": "cancel"}

    def test_perform_user_purchase_request_action_raises_on_empty_user_id(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_purchase_request_action(
                "", "pr-1", op="cancel"
            )

    def test_perform_user_purchase_request_action_raises_on_empty_request_id(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_purchase_request_action(
                "u1", "", op="cancel"
            )

    def test_perform_user_purchase_request_action_raises_on_empty_op(self):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_purchase_request_action(
                "u1", "pr-1", op=""
            )

    def test_perform_user_purchase_request_action_raises_on_whitespace_op(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_purchase_request_action(
                "u1", "pr-1", op="   "
            )

    def test_perform_user_purchase_request_action_raises_on_non_string_op(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient()
        users = Users(mock_client)

        with pytest.raises(AlmaValidationError):
            users.perform_user_purchase_request_action(
                "u1", "pr-1", op=None  # type: ignore[arg-type]
            )

    def test_perform_user_purchase_request_action_propagates_api_error(
        self,
    ):
        from almaapitk.domains.users import Users
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "The operation is not supported",
            status_code=400,
            alma_code="401873",
        )
        users = Users(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            users.perform_user_purchase_request_action(
                "u1", "pr-1", op="approve"
            )

        assert exc_info.value.alma_code == "401873"


# ---------------------------------------------------------------------------
# build_user_rs_request  (issue #197)
# ---------------------------------------------------------------------------


class TestBuildUserRsRequest:
    """Tests for ``almaapitk.domains.users.build_user_rs_request``.

    Pure builder — no HTTP is involved except in the round-trip test, which
    uses the same ``MockAlmaAPIClient`` stand-in as the rest of this module.
    """

    def test_builds_minimal_body_with_correct_wrapping(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            owner="RS_LIB",
            format="DIGITAL",
            citation_type="CR",
        )

        assert body == {
            # owner is a PLAIN string — the Alma quirk (issue #197).
            "owner": "RS_LIB",
            "format": {"value": "DIGITAL"},
            "citation_type": {"value": "CR"},
            "agree_to_copyright_terms": True,
        }

    def test_builds_full_body(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            owner="RS_LIB",
            format="PHYSICAL",
            citation_type="BK",
            title="Sample title",
            journal_title="Sample journal",
            author="Sample, Author",
            year="2009",
            pickup_location="PICKUP_LIB",
            pickup_location_type="LIBRARY",
            external_id="caller-app:42",
        )

        assert body == {
            "owner": "RS_LIB",
            "format": {"value": "PHYSICAL"},
            "citation_type": {"value": "BK"},
            "external_id": "caller-app:42",
            # pickup_location_type is plain, pickup_location is wrapped.
            "pickup_location_type": "LIBRARY",
            "title": "Sample title",
            "author": "Sample, Author",
            "journal_title": "Sample journal",
            "year": "2009",
            "pickup_location": {"value": "PICKUP_LIB"},
            "agree_to_copyright_terms": True,
        }

    def test_omits_optional_fields_that_are_none(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request("RS_LIB", "DIGITAL", "CR")

        for field in (
            "title",
            "journal_title",
            "author",
            "year",
            "pickup_location",
            "pickup_location_type",
            "external_id",
        ):
            assert field not in body

    def test_agree_to_copyright_terms_none_omits_field(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            "RS_LIB", "DIGITAL", "CR", agree_to_copyright_terms=None
        )

        assert "agree_to_copyright_terms" not in body

    def test_agree_to_copyright_terms_false_is_kept(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            "RS_LIB", "DIGITAL", "CR", agree_to_copyright_terms=False
        )

        assert body["agree_to_copyright_terms"] is False

    def test_year_accepts_int(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request("RS_LIB", "PHYSICAL", "BK", year=2009)

        assert body["year"] == "2009"

    def test_strips_surrounding_whitespace(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            "  RS_LIB  ",
            "  DIGITAL ",
            " CR ",
            title="  Sample title  ",
            pickup_location=" PICKUP_LIB ",
        )

        assert body["owner"] == "RS_LIB"
        assert body["format"] == {"value": "DIGITAL"}
        assert body["citation_type"] == {"value": "CR"}
        assert body["title"] == "Sample title"
        assert body["pickup_location"] == {"value": "PICKUP_LIB"}

    def test_extra_wraps_known_code_table_fields(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            "RS_LIB",
            "DIGITAL",
            "CR",
            extra={"level_of_service": "REGULAR", "partner": "PARTNER_CODE"},
        )

        assert body["level_of_service"] == {"value": "REGULAR"}
        assert body["partner"] == {"value": "PARTNER_CODE"}

    def test_extra_passes_plain_fields_through_unwrapped(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            "RS_LIB",
            "PHYSICAL",
            "BK",
            extra={
                "mms_id": "99123456789",
                "note": "Automated request",
                "allow_other_formats": True,
                "maximum_fee": 12.5,
            },
        )

        assert body["mms_id"] == "99123456789"
        assert body["note"] == "Automated request"
        assert body["allow_other_formats"] is True
        assert body["maximum_fee"] == 12.5

    def test_extra_does_not_double_wrap_already_wrapped_values(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            "RS_LIB",
            "DIGITAL",
            "CR",
            extra={"level_of_service": {"value": "EXPEDITED"}},
        )

        assert body["level_of_service"] == {"value": "EXPEDITED"}

    def test_extra_overrides_explicit_arguments(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            "RS_LIB",
            "DIGITAL",
            "CR",
            title="Sample title",
            extra={"title": "Override title"},
        )

        assert body["title"] == "Override title"

    def test_extra_supports_unknown_fields_verbatim(self):
        from almaapitk.domains.users import build_user_rs_request

        body = build_user_rs_request(
            "RS_LIB", "DIGITAL", "CR", extra={"future_field": "abc"}
        )

        assert body["future_field"] == "abc"

    def test_result_round_trips_through_create_user_rs_request(self):
        from almaapitk.domains.users import Users, build_user_rs_request

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"request_id": "rs-197"}
        )
        users = Users(mock_client)

        body = build_user_rs_request(
            "RS_LIB", "DIGITAL", "CR", title="Sample title"
        )
        response = users.create_user_rs_request("u1", request_data=body)

        call = mock_client.calls["post"][0]
        assert call["endpoint"] == (
            "almaws/v1/users/u1/resource-sharing-requests"
        )
        # The builder output is forwarded verbatim — no re-shaping.
        assert call["data"] == body
        assert response.data["request_id"] == "rs-197"

    @pytest.mark.parametrize(
        "kwargs,field",
        [
            ({"owner": ""}, "owner"),
            ({"owner": "   "}, "owner"),
            ({"owner": None}, "owner"),
            ({"format": ""}, "format"),
            ({"format": 5}, "format"),
            ({"citation_type": ""}, "citation_type"),
            ({"citation_type": None}, "citation_type"),
        ],
    )
    def test_raises_on_missing_required_field(self, kwargs, field):
        from almaapitk.domains.users import build_user_rs_request
        from almaapitk import AlmaValidationError

        call_kwargs = {
            "owner": "RS_LIB",
            "format": "DIGITAL",
            "citation_type": "CR",
        }
        call_kwargs.update(kwargs)

        with pytest.raises(AlmaValidationError) as exc_info:
            build_user_rs_request(**call_kwargs)  # type: ignore[arg-type]

        assert field in str(exc_info.value)

    @pytest.mark.parametrize(
        "field",
        [
            "title",
            "journal_title",
            "author",
            "pickup_location",
            "pickup_location_type",
            "external_id",
        ],
    )
    def test_raises_on_empty_optional_text_field(self, field):
        from almaapitk.domains.users import build_user_rs_request
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError) as exc_info:
            build_user_rs_request(
                "RS_LIB", "DIGITAL", "CR", **{field: "  "}
            )

        assert field in str(exc_info.value)

    def test_raises_on_non_string_year(self):
        from almaapitk.domains.users import build_user_rs_request
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError) as exc_info:
            build_user_rs_request(
                "RS_LIB", "PHYSICAL", "BK", year=[2009]  # type: ignore[arg-type]
            )

        assert "year" in str(exc_info.value)

    def test_raises_on_non_bool_agree_to_copyright_terms(self):
        from almaapitk.domains.users import build_user_rs_request
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError) as exc_info:
            build_user_rs_request(
                "RS_LIB",
                "DIGITAL",
                "CR",
                agree_to_copyright_terms="yes",  # type: ignore[arg-type]
            )

        assert "agree_to_copyright_terms" in str(exc_info.value)

    def test_raises_on_non_dict_extra(self):
        from almaapitk.domains.users import build_user_rs_request
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError) as exc_info:
            build_user_rs_request(
                "RS_LIB", "DIGITAL", "CR", extra=["note"]  # type: ignore[arg-type]
            )

        assert "extra" in str(exc_info.value)

    def test_raises_on_empty_extra_key(self):
        from almaapitk.domains.users import build_user_rs_request
        from almaapitk import AlmaValidationError

        with pytest.raises(AlmaValidationError) as exc_info:
            build_user_rs_request(
                "RS_LIB", "DIGITAL", "CR", extra={"   ": "value"}
            )

        assert "extra" in str(exc_info.value)

    def test_exported_from_package_root(self):
        import almaapitk

        assert "build_user_rs_request" in almaapitk.__all__
        assert callable(almaapitk.build_user_rs_request)
