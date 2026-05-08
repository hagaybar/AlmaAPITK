"""
Unit tests for the Users domain class — issue #36 / #39 / #44 / #45 coverage:

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
        self.next_exception: Optional[Exception] = None
        self.calls = {"get": [], "post": []}

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
