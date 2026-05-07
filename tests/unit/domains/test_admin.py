"""Unit tests for the Admin domain class — set CRUD + member management (issue #23).

Tests cover the five new methods:

- ``Admin.create_set``
- ``Admin.update_set``
- ``Admin.delete_set``
- ``Admin.add_members_to_set``
- ``Admin.remove_members_from_set``

Pattern source: mirrors ``tests/unit/domains/test_configuration.py`` /
``tests/unit/domains/test_analytics.py`` for the mock-client style
(plain ``MockAlmaAPIClient`` + ``MockAlmaResponse``, no real HTTP).
"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest


class MockAlmaResponse:
    """Lightweight stand-in for ``almaapitk.AlmaResponse``.

    Just enough surface area for the Admin methods under test:
    ``status_code``, ``success``, and a ``.data`` / ``.json()`` pair
    backed by a single dict.
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
    """Mock AlmaAPIClient wired so each verb records the call it received.

    Records the last ``(endpoint, params, data)`` triple per verb so
    tests can assert on URL / query-param / body shape without standing
    up an HTTP layer.
    """

    def __init__(self, environment: str = 'SANDBOX'):
        self.environment = environment
        # The Admin constructor copies ``client.logger`` onto ``self``;
        # MagicMock gives us call-recording for free without asking the
        # alma_logging stack to spin up.
        self.logger = MagicMock()

        # Per-verb response registers; tests set these before they call
        # the Admin method under test.
        self.post_response: MockAlmaResponse = MockAlmaResponse()
        self.put_response: MockAlmaResponse = MockAlmaResponse()
        self.delete_response: MockAlmaResponse = MockAlmaResponse()
        # Optional override: when set to an exception, the next call
        # raises it instead of returning ``*_response``.
        self.next_exception: Optional[Exception] = None

        self.calls: Dict[str, list] = {
            "post": [],
            "put": [],
            "delete": [],
            "get": [],
        }

    def get_environment(self) -> str:
        return self.environment

    def post(
        self,
        endpoint: str,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        self.calls["post"].append(
            {"endpoint": endpoint, "data": data, "params": params}
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
            {"endpoint": endpoint, "data": data, "params": params}
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

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        # Not exercised by the tests below, but several Admin methods
        # call ``client.get`` indirectly through other paths -- keep the
        # surface complete to avoid AttributeError in any future test.
        self.calls["get"].append({"endpoint": endpoint, "params": params})
        return MockAlmaResponse()


# ---------------------------------------------------------------------------
# create_set
# ---------------------------------------------------------------------------


class TestCreateSet:
    """Tests for ``Admin.create_set``."""

    def _valid_payload(self) -> Dict[str, Any]:
        return {
            "name": "My Test Set",
            "type": {"value": "ITEMIZED"},
            "content": {"value": "BIB_MMS"},
            "description": "A test set",
        }

    def test_create_set_posts_to_correct_endpoint(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"id": "1234567890", "name": "My Test Set"}
        )
        admin = Admin(mock_client)

        response = admin.create_set(self._valid_payload())

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/conf/sets"
        # No ``op`` query param on create.
        assert call["params"] is None
        # Body is forwarded verbatim.
        assert call["data"]["name"] == "My Test Set"
        assert call["data"]["type"] == {"value": "ITEMIZED"}
        # Returned response is the mock.
        assert response is mock_client.post_response
        assert response.data["id"] == "1234567890"

    def test_create_set_accepts_string_type(self):
        """Alma accepts ``type`` as a bare string in create payloads."""
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        admin = Admin(mock_client)

        payload = {"name": "S", "type": "ITEMIZED"}
        admin.create_set(payload)

        call = mock_client.calls["post"][0]
        assert call["data"]["type"] == "ITEMIZED"

    def test_create_set_logs_success_with_id(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "9999"})
        admin = Admin(mock_client)

        admin.create_set(self._valid_payload())

        assert mock_client.logger.info.called

    def test_create_set_rejects_empty_dict(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.create_set({})

    def test_create_set_rejects_non_dict(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.create_set("not a dict")  # type: ignore[arg-type]

    def test_create_set_rejects_missing_name(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.create_set({"type": {"value": "ITEMIZED"}})

    def test_create_set_rejects_blank_name(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.create_set(
                {"name": "   ", "type": {"value": "ITEMIZED"}}
            )

    def test_create_set_rejects_missing_type(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.create_set({"name": "S"})

    def test_create_set_rejects_type_dict_without_value(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.create_set({"name": "S", "type": {}})

    def test_create_set_propagates_api_error_with_logging(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "The set name already exists.", status_code=400, alma_code="402263"
        )
        admin = Admin(mock_client)

        with pytest.raises(AlmaAPIError):
            admin.create_set(self._valid_payload())

        assert mock_client.logger.error.called


# ---------------------------------------------------------------------------
# update_set
# ---------------------------------------------------------------------------


class TestUpdateSet:
    """Tests for ``Admin.update_set``."""

    def _valid_payload(self) -> Dict[str, Any]:
        return {
            "id": "1234567890",
            "name": "Updated Set Name",
            "description": "Updated description",
            "type": {"value": "ITEMIZED"},
        }

    def test_update_set_puts_to_correct_endpoint(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(body=self._valid_payload())
        admin = Admin(mock_client)

        response = admin.update_set("1234567890", self._valid_payload())

        assert len(mock_client.calls["put"]) == 1
        call = mock_client.calls["put"][0]
        assert call["endpoint"] == "almaws/v1/conf/sets/1234567890"
        assert call["data"]["name"] == "Updated Set Name"
        assert response is mock_client.put_response

    def test_update_set_rejects_empty_set_id(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.update_set("", self._valid_payload())

    def test_update_set_rejects_empty_payload(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.update_set("1234567890", {})

    def test_update_set_rejects_non_dict_payload(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.update_set("1234567890", "not a dict")  # type: ignore[arg-type]

    def test_update_set_propagates_api_error(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Failed updating set.", status_code=400, alma_code="40166408"
        )
        admin = Admin(mock_client)

        with pytest.raises(AlmaAPIError):
            admin.update_set("1234567890", self._valid_payload())

        assert mock_client.logger.error.called


# ---------------------------------------------------------------------------
# delete_set
# ---------------------------------------------------------------------------


class TestDeleteSet:
    """Tests for ``Admin.delete_set``."""

    def test_delete_set_calls_correct_endpoint(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(
            body={}, status_code=204
        )
        admin = Admin(mock_client)

        response = admin.delete_set("1234567890")

        assert len(mock_client.calls["delete"]) == 1
        call = mock_client.calls["delete"][0]
        assert call["endpoint"] == "almaws/v1/conf/sets/1234567890"
        assert response is mock_client.delete_response

    def test_delete_set_rejects_empty_set_id(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.delete_set("")

    def test_delete_set_propagates_api_error(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Delete of Set Failed.", status_code=400, alma_code="402282"
        )
        admin = Admin(mock_client)

        with pytest.raises(AlmaAPIError):
            admin.delete_set("1234567890")

        assert mock_client.logger.error.called


# ---------------------------------------------------------------------------
# add_members_to_set
# ---------------------------------------------------------------------------


class TestAddMembersToSet:
    """Tests for ``Admin.add_members_to_set``."""

    def test_add_members_uses_op_add_members_query(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        admin = Admin(mock_client)

        admin.add_members_to_set("1234567890", ["m1", "m2", "m3"])

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/conf/sets/1234567890"
        assert call["params"] == {"op": "add_members"}

    def test_add_members_body_shape(self):
        """Body must wrap the IDs as members.member[*].id (per Alma spec)."""
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        admin = Admin(mock_client)

        admin.add_members_to_set("set-1", ["m1", "m2"])

        body = mock_client.calls["post"][0]["data"]
        assert body == {
            "members": {"member": [{"id": "m1"}, {"id": "m2"}]}
        }

    def test_add_members_returns_response(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"id": "set-1", "number_of_members": {"value": 5}}
        )
        admin = Admin(mock_client)

        response = admin.add_members_to_set("set-1", ["m1"])

        assert response is mock_client.post_response

    def test_add_members_rejects_empty_set_id(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.add_members_to_set("", ["m1"])

    def test_add_members_rejects_empty_list(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.add_members_to_set("set-1", [])

    def test_add_members_rejects_non_list(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.add_members_to_set("set-1", "not a list")  # type: ignore[arg-type]

    def test_add_members_rejects_non_string_entry(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.add_members_to_set("set-1", ["m1", 12345])  # type: ignore[list-item]

    def test_add_members_rejects_blank_entry(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.add_members_to_set("set-1", ["m1", "   "])

    def test_add_members_propagates_api_error(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "A member ID is already in the set.",
            status_code=400,
            alma_code="60115",
        )
        admin = Admin(mock_client)

        with pytest.raises(AlmaAPIError):
            admin.add_members_to_set("set-1", ["m1"])

        assert mock_client.logger.error.called


# ---------------------------------------------------------------------------
# remove_members_from_set
# ---------------------------------------------------------------------------


class TestRemoveMembersFromSet:
    """Tests for ``Admin.remove_members_from_set``."""

    def test_remove_members_uses_op_delete_members_query(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        admin = Admin(mock_client)

        admin.remove_members_from_set("1234567890", ["m1"])

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/conf/sets/1234567890"
        assert call["params"] == {"op": "delete_members"}

    def test_remove_members_body_shape(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        admin = Admin(mock_client)

        admin.remove_members_from_set("set-1", ["m1", "m2"])

        body = mock_client.calls["post"][0]["data"]
        assert body == {
            "members": {"member": [{"id": "m1"}, {"id": "m2"}]}
        }

    def test_remove_members_rejects_empty_set_id(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.remove_members_from_set("", ["m1"])

    def test_remove_members_rejects_empty_list(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.remove_members_from_set("set-1", [])

    def test_remove_members_rejects_non_string_entry(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaValidationError

        admin = Admin(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            admin.remove_members_from_set("set-1", [None])  # type: ignore[list-item]

    def test_remove_members_propagates_api_error(self):
        from almaapitk.domains.admin import Admin
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Input set member ID is not in set.",
            status_code=400,
            alma_code="60117",
        )
        admin = Admin(mock_client)

        with pytest.raises(AlmaAPIError):
            admin.remove_members_from_set("set-1", ["m1"])

        assert mock_client.logger.error.called


# ---------------------------------------------------------------------------
# Cross-cutting: the two member-management methods must differ ONLY by op
# ---------------------------------------------------------------------------


class TestMemberManagementOpDispatch:
    """Add and remove must hit the same endpoint with different ``op`` values."""

    def test_add_and_remove_differ_only_in_op(self):
        from almaapitk.domains.admin import Admin

        mock_client = MockAlmaAPIClient()
        admin = Admin(mock_client)

        admin.add_members_to_set("set-1", ["m1"])
        admin.remove_members_from_set("set-1", ["m1"])

        add_call, remove_call = mock_client.calls["post"]
        assert add_call["endpoint"] == remove_call["endpoint"]
        assert add_call["data"] == remove_call["data"]
        assert add_call["params"] == {"op": "add_members"}
        assert remove_call["params"] == {"op": "delete_members"}
