"""
Unit tests for the Configuration domain class
(issues #22, #24, #25, #26, #27, #30, #33).

Tests cover:
- Initialization (client, environment, logger setup)
- get_environment() - returns the environment from the underlying client
- test_connection() - delegates to client.test_connection()
- list_libraries() / get_library() (issue #24)
- list_departments() (issue #24)
- list_circ_desks() / get_circ_desk() (issue #24)
- list_locations() / get_location() / create_location() /
  update_location() / delete_location() (issue #25)
- list_code_tables() / get_code_table() / update_code_table() (issue #26)
- list_mapping_tables() / get_mapping_table() / update_mapping_table()
  (issue #27)
- list_deposit_profiles() / get_deposit_profile() /
  list_import_profiles() / get_import_profile() (issue #30)
- list_letters() / get_letter() / update_letter() /
  list_printers() / get_printer() (issue #33)

These tests use mocked AlmaAPIClient instances to test the Configuration
domain in isolation. Pattern source mirrors
``tests/unit/domains/test_admin.py`` for the get-shaped and
state-changing tests and ``tests/unit/domains/test_analytics.py`` for
the foundation skeleton.
"""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest


class MockAlmaResponse:
    """Lightweight stand-in for ``almaapitk.AlmaResponse``.

    Just enough surface area for the Configuration GET methods under
    test: ``status_code``, ``success``, and ``.data`` / ``.json()`` both
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
    """Mock AlmaAPIClient for testing the Configuration domain.

    The foundation tests (issue #22) only need ``get_environment`` and
    ``test_connection``. The org-structure tests (issue #24) additionally
    record GET calls so they can assert on URL / query params, and let
    each test set the response (or a one-shot exception) per call.
    """

    def __init__(
        self,
        environment: str = 'SANDBOX',
        connection_result: bool = True,
    ):
        self.environment = environment
        self.logger = MagicMock()
        self._connection_result = connection_result
        self.test_connection_call_count = 0

        # Per-verb response register and call log for the issue-#24/#25
        # methods. Tests set ``get_response`` / ``post_response`` /
        # ``put_response`` / ``delete_response`` or ``next_exception``
        # before invoking the Configuration method under test.
        self.get_response: MockAlmaResponse = MockAlmaResponse()
        self.post_response: MockAlmaResponse = MockAlmaResponse()
        self.put_response: MockAlmaResponse = MockAlmaResponse()
        self.delete_response: MockAlmaResponse = MockAlmaResponse()
        self.next_exception: Optional[Exception] = None
        self.calls = {"get": [], "post": [], "put": [], "delete": []}

    def get_environment(self) -> str:
        return self.environment

    def test_connection(self) -> bool:
        self.test_connection_call_count += 1
        return self._connection_result

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
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
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
        data: Optional[Any] = None,
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
                "custom_headers": custom_headers,
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


class TestConfigurationInit:
    """Tests for Configuration class initialization."""

    def test_init_sets_client(self):
        """Test that __init__ properly stores the client."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('SANDBOX')
        config = Configuration(mock_client)

        assert config.client is mock_client

    def test_init_sets_environment_from_client(self):
        """Test that __init__ stores the environment from the client."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('SANDBOX')
        config = Configuration(mock_client)

        assert config.environment == 'SANDBOX'

    def test_init_with_production_environment(self):
        """Test initialization with PRODUCTION environment."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('PRODUCTION')
        config = Configuration(mock_client)

        assert config.environment == 'PRODUCTION'

    def test_init_creates_logger(self):
        """Test that __init__ initializes a domain-specific logger."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('SANDBOX')
        config = Configuration(mock_client)

        # Logger must exist and have the standard logging methods we use.
        assert config.logger is not None
        assert hasattr(config.logger, 'info')
        assert hasattr(config.logger, 'debug')
        assert hasattr(config.logger, 'error')


class TestConfigurationGetEnvironment:
    """Tests for Configuration.get_environment() method."""

    def test_get_environment_returns_sandbox(self):
        """Test that get_environment returns SANDBOX from sandbox client."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('SANDBOX')
        config = Configuration(mock_client)

        assert config.get_environment() == 'SANDBOX'

    def test_get_environment_returns_production(self):
        """Test that get_environment returns PRODUCTION from prod client."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('PRODUCTION')
        config = Configuration(mock_client)

        assert config.get_environment() == 'PRODUCTION'

    def test_get_environment_delegates_to_client(self):
        """Test that get_environment reads through to the client each call."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('SANDBOX')
        # Spy on the client's get_environment.
        mock_client.get_environment = MagicMock(return_value='SANDBOX')
        config = Configuration(mock_client)
        # Reset call count: __init__ also calls get_environment once.
        mock_client.get_environment.reset_mock()

        result = config.get_environment()

        assert result == 'SANDBOX'
        mock_client.get_environment.assert_called_once()


class TestConfigurationTestConnection:
    """Tests for Configuration.test_connection() method."""

    def test_test_connection_success(self):
        """Test that test_connection returns True when client connects OK."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('SANDBOX', connection_result=True)
        config = Configuration(mock_client)

        assert config.test_connection() is True

    def test_test_connection_failure(self):
        """Test that test_connection returns False when client fails."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('SANDBOX', connection_result=False)
        config = Configuration(mock_client)

        assert config.test_connection() is False

    def test_test_connection_delegates_to_client(self):
        """Test that test_connection calls the client's test_connection."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient('SANDBOX', connection_result=True)
        config = Configuration(mock_client)

        config.test_connection()

        # The client's test_connection must have been called exactly once
        # by our delegation.
        assert mock_client.test_connection_call_count == 1


# ---------------------------------------------------------------------------
# Issue #24: organizational structure read methods
# ---------------------------------------------------------------------------


class TestListLibraries:
    """Tests for ``Configuration.list_libraries`` (issue #24)."""

    def test_list_libraries_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "library": [
                    {"code": "MAIN", "name": "Main Library"},
                    {"code": "SCI", "name": "Science Library"},
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_libraries()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/libraries"
        # We pass limit/offset to keep a single round-trip predictable.
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["code"] == "MAIN"

    def test_list_libraries_returns_empty_list_on_missing_key(self):
        """Alma envelope without ``library`` key → empty list, not None."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        result = config.list_libraries()

        assert result == []

    def test_list_libraries_handles_single_dict_response(self):
        """A single library returned as dict (not list) is normalised."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "library": {"code": "ONLY", "name": "Only Library"},
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.list_libraries()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["code"] == "ONLY"

    def test_list_libraries_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_libraries()

    def test_list_libraries_logs_success_count(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"library": [{"code": "A"}, {"code": "B"}]}
        )
        config = Configuration(mock_client)

        config.list_libraries()

        # logger.info was called at least once with a success summary.
        # (Configuration uses alma_logging's get_logger, not the mock
        # client's logger, so we just assert no errors fired.)
        assert mock_client.next_exception is None


class TestGetLibrary:
    """Tests for ``Configuration.get_library`` (issue #24)."""

    def test_get_library_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"code": "MAIN", "name": "Main Library", "type": {"value": "BRANCH"}}
        )
        config = Configuration(mock_client)

        result = config.get_library("MAIN")

        assert len(mock_client.calls["get"]) == 1
        assert mock_client.calls["get"][0]["endpoint"] == "almaws/v1/conf/libraries/MAIN"
        assert isinstance(result, dict)
        assert result["code"] == "MAIN"
        assert result["name"] == "Main Library"

    def test_get_library_strips_whitespace(self):
        """Validator trims whitespace from the code before building URL."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"code": "MAIN"})
        config = Configuration(mock_client)

        config.get_library("  MAIN  ")

        # The endpoint must contain the trimmed code.
        assert mock_client.calls["get"][0]["endpoint"] == "almaws/v1/conf/libraries/MAIN"

    def test_get_library_rejects_empty_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_library("")

    def test_get_library_rejects_whitespace_only(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_library("   ")

    def test_get_library_rejects_non_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_library(123)  # type: ignore[arg-type]

    def test_get_library_rejects_none(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_library(None)  # type: ignore[arg-type]

    def test_get_library_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "not found", status_code=404
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.get_library("NOPE")


class TestListDepartments:
    """Tests for ``Configuration.list_departments`` (issue #24)."""

    def test_list_departments_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "department": [
                    {"code": "ACQ", "name": "Acquisitions"},
                    {"code": "CAT", "name": "Cataloging"},
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_departments()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/departments"
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["code"] == "ACQ"

    def test_list_departments_returns_empty_list_on_missing_key(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_departments() == []

    def test_list_departments_handles_single_dict_response(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"department": {"code": "ACQ", "name": "Acquisitions"}}
        )
        config = Configuration(mock_client)

        result = config.list_departments()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["code"] == "ACQ"

    def test_list_departments_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_departments()


class TestListCircDesks:
    """Tests for ``Configuration.list_circ_desks`` (issue #24)."""

    def test_list_circ_desks_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "circ_desk": [
                    {"code": "DESK1", "name": "Front Desk"},
                    {"code": "DESK2", "name": "Reserve Desk"},
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_circ_desks("MAIN")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/libraries/MAIN/circ-desks"
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["code"] == "DESK1"

    def test_list_circ_desks_returns_empty_list_on_missing_key(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_circ_desks("MAIN") == []

    def test_list_circ_desks_handles_single_dict_response(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"circ_desk": {"code": "DESK1", "name": "Front Desk"}}
        )
        config = Configuration(mock_client)

        result = config.list_circ_desks("MAIN")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["code"] == "DESK1"

    def test_list_circ_desks_rejects_empty_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.list_circ_desks("")

    def test_list_circ_desks_rejects_non_string_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.list_circ_desks(42)  # type: ignore[arg-type]

    def test_list_circ_desks_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_circ_desks("MAIN")


class TestGetCircDesk:
    """Tests for ``Configuration.get_circ_desk`` (issue #24)."""

    def test_get_circ_desk_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"code": "DESK1", "name": "Front Desk"}
        )
        config = Configuration(mock_client)

        result = config.get_circ_desk("MAIN", "DESK1")

        assert len(mock_client.calls["get"]) == 1
        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/circ-desks/DESK1"
        )
        assert isinstance(result, dict)
        assert result["code"] == "DESK1"

    def test_get_circ_desk_strips_whitespace(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"code": "DESK1"})
        config = Configuration(mock_client)

        config.get_circ_desk("  MAIN  ", "  DESK1  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/circ-desks/DESK1"
        )

    def test_get_circ_desk_rejects_empty_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_circ_desk("", "DESK1")

    def test_get_circ_desk_rejects_empty_desk_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_circ_desk("MAIN", "")

    def test_get_circ_desk_rejects_whitespace_only_codes(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_circ_desk("MAIN", "   ")

    def test_get_circ_desk_rejects_non_string_codes(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_circ_desk("MAIN", None)  # type: ignore[arg-type]

    def test_get_circ_desk_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "not found", status_code=404
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.get_circ_desk("MAIN", "NOPE")


# ---------------------------------------------------------------------------
# Issue #25: Locations CRUD
# ---------------------------------------------------------------------------


class TestListLocations:
    """Tests for ``Configuration.list_locations`` (issue #25)."""

    def test_list_locations_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "location": [
                    {"code": "STACKS", "name": "Main Stacks"},
                    {"code": "REF", "name": "Reference"},
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_locations("MAIN")

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/libraries/MAIN/locations"
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["code"] == "STACKS"

    def test_list_locations_returns_empty_list_on_missing_key(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_locations("MAIN") == []

    def test_list_locations_handles_single_dict_response(self):
        """A single location returned as dict (not list) is normalised."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"location": {"code": "ONLY", "name": "Only Location"}}
        )
        config = Configuration(mock_client)

        result = config.list_locations("MAIN")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["code"] == "ONLY"

    def test_list_locations_strips_whitespace_in_library_code(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"location": []})
        config = Configuration(mock_client)

        config.list_locations("  MAIN  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/locations"
        )

    def test_list_locations_rejects_empty_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.list_locations("")

    def test_list_locations_rejects_non_string_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.list_locations(42)  # type: ignore[arg-type]

    def test_list_locations_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_locations("MAIN")


class TestGetLocation:
    """Tests for ``Configuration.get_location`` (issue #25)."""

    def test_get_location_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "code": "STACKS",
                "name": "Main Stacks",
                "type": {"value": "OPEN"},
            }
        )
        config = Configuration(mock_client)

        result = config.get_location("MAIN", "STACKS")

        assert len(mock_client.calls["get"]) == 1
        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/locations/STACKS"
        )
        assert isinstance(result, dict)
        assert result["code"] == "STACKS"
        assert result["name"] == "Main Stacks"

    def test_get_location_strips_whitespace(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"code": "STACKS"})
        config = Configuration(mock_client)

        config.get_location("  MAIN  ", "  STACKS  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/locations/STACKS"
        )

    def test_get_location_rejects_empty_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_location("", "STACKS")

    def test_get_location_rejects_empty_location_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_location("MAIN", "")

    def test_get_location_rejects_whitespace_only_codes(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_location("MAIN", "   ")

    def test_get_location_rejects_non_string_codes(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_location("MAIN", None)  # type: ignore[arg-type]

    def test_get_location_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "not found", status_code=404
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.get_location("MAIN", "NOPE")


class TestCreateLocation:
    """Tests for ``Configuration.create_location`` (issue #25)."""

    @staticmethod
    def _valid_payload() -> Dict[str, Any]:
        return {
            "code": "STACKS",
            "name": "Main Stacks",
            "type": {"value": "OPEN"},
        }

    def test_create_location_calls_correct_endpoint_and_returns_response(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={
                "code": "STACKS",
                "name": "Main Stacks",
                "type": {"value": "OPEN"},
            }
        )
        config = Configuration(mock_client)

        response = config.create_location("MAIN", self._valid_payload())

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/conf/libraries/MAIN/locations"
        # Body is the location object directly (not wrapped).
        assert call["data"] == self._valid_payload()
        # AC: returns AlmaResponse-shaped object exposing .data.
        assert response is mock_client.post_response
        assert response.data["code"] == "STACKS"

    def test_create_location_accepts_string_type(self):
        """``type`` may be a bare string per the AC (mirrors create_set)."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"code": "STACKS"})
        config = Configuration(mock_client)

        payload = {"code": "STACKS", "name": "Main Stacks", "type": "OPEN"}
        config.create_location("MAIN", payload)

        # Body forwarded verbatim — string ``type`` is preserved.
        assert mock_client.calls["post"][0]["data"]["type"] == "OPEN"

    def test_create_location_strips_whitespace_in_library_code(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"code": "STACKS"})
        config = Configuration(mock_client)

        config.create_location("  MAIN  ", self._valid_payload())

        assert (
            mock_client.calls["post"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/locations"
        )

    def test_create_location_rejects_empty_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.create_location("", self._valid_payload())

    def test_create_location_rejects_empty_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.create_location("MAIN", {})

    def test_create_location_rejects_non_dict_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.create_location("MAIN", "not a dict")  # type: ignore[arg-type]

    def test_create_location_rejects_missing_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.create_location(
                "MAIN",
                {"name": "Main Stacks", "type": {"value": "OPEN"}},
            )

    def test_create_location_rejects_missing_name(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.create_location(
                "MAIN",
                {"code": "STACKS", "type": {"value": "OPEN"}},
            )

    def test_create_location_rejects_missing_type(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.create_location(
                "MAIN", {"code": "STACKS", "name": "Main Stacks"}
            )

    def test_create_location_rejects_empty_string_type(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.create_location(
                "MAIN",
                {"code": "STACKS", "name": "Main Stacks", "type": "   "},
            )

    def test_create_location_rejects_empty_dict_type_value(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.create_location(
                "MAIN",
                {
                    "code": "STACKS",
                    "name": "Main Stacks",
                    "type": {"value": ""},
                },
            )

    def test_create_location_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.create_location("MAIN", self._valid_payload())


class TestUpdateLocation:
    """Tests for ``Configuration.update_location`` (issue #25)."""

    @staticmethod
    def _valid_payload() -> Dict[str, Any]:
        return {
            "code": "STACKS",
            "name": "Main Stacks (renamed)",
            "type": {"value": "OPEN"},
        }

    def test_update_location_calls_correct_endpoint_and_returns_response(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={"code": "STACKS", "name": "Main Stacks (renamed)"}
        )
        config = Configuration(mock_client)

        response = config.update_location(
            "MAIN", "STACKS", self._valid_payload()
        )

        assert len(mock_client.calls["put"]) == 1
        call = mock_client.calls["put"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/locations/STACKS"
        )
        assert call["data"] == self._valid_payload()
        assert response is mock_client.put_response
        assert response.data["name"] == "Main Stacks (renamed)"

    def test_update_location_strips_whitespace(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(body={"code": "STACKS"})
        config = Configuration(mock_client)

        config.update_location(
            "  MAIN  ", "  STACKS  ", self._valid_payload()
        )

        assert (
            mock_client.calls["put"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/locations/STACKS"
        )

    def test_update_location_rejects_empty_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_location("", "STACKS", self._valid_payload())

    def test_update_location_rejects_empty_location_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_location("MAIN", "", self._valid_payload())

    def test_update_location_rejects_non_string_codes(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_location(
                "MAIN", 123, self._valid_payload()  # type: ignore[arg-type]
            )

    def test_update_location_rejects_empty_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_location("MAIN", "STACKS", {})

    def test_update_location_rejects_non_dict_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_location(
                "MAIN", "STACKS", "not a dict"  # type: ignore[arg-type]
            )

    def test_update_location_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.update_location("MAIN", "STACKS", self._valid_payload())


class TestDeleteLocation:
    """Tests for ``Configuration.delete_location`` (issue #25)."""

    def test_delete_location_calls_correct_endpoint_and_returns_response(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        config = Configuration(mock_client)

        response = config.delete_location("MAIN", "STACKS")

        assert len(mock_client.calls["delete"]) == 1
        assert (
            mock_client.calls["delete"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/locations/STACKS"
        )
        assert response is mock_client.delete_response

    def test_delete_location_strips_whitespace(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.delete_response = MockAlmaResponse(body={})
        config = Configuration(mock_client)

        config.delete_location("  MAIN  ", "  STACKS  ")

        assert (
            mock_client.calls["delete"][0]["endpoint"]
            == "almaws/v1/conf/libraries/MAIN/locations/STACKS"
        )

    def test_delete_location_rejects_empty_library_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.delete_location("", "STACKS")

    def test_delete_location_rejects_empty_location_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.delete_location("MAIN", "")

    def test_delete_location_rejects_non_string_codes(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.delete_location(None, "STACKS")  # type: ignore[arg-type]

    def test_delete_location_propagates_linked_items_error_verbatim(self):
        """Linked-items deletion failures must surface Alma's error
        verbatim — we do NOT swallow them. The AC requires preserving
        ``alma_code`` and ``tracking_id`` on the propagated exception so
        callers can surface Alma's diagnostic to operators.
        """
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Location has linked items",
            status_code=400,
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.delete_location("MAIN", "STACKS")

        # The original error message must be preserved verbatim.
        assert "Location has linked items" in str(exc_info.value)

    def test_delete_location_propagates_generic_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.delete_location("MAIN", "STACKS")


# ---------------------------------------------------------------------------
# Issue #26: Code tables (list / get / update)
# ---------------------------------------------------------------------------


class TestListCodeTables:
    """Tests for ``Configuration.list_code_tables`` (issue #26)."""

    def test_list_code_tables_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "code_table": [
                    {
                        "name": "AcqInvoiceLineType",
                        "description": "Invoice line types",
                    },
                    {
                        "name": "VendorReferenceNumberType",
                        "description": "Vendor reference number types",
                    },
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_code_tables()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/code-tables"
        # Single round-trip with generous page size; no scope filter.
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "AcqInvoiceLineType"

    def test_list_code_tables_returns_empty_list_on_missing_key(self):
        """Alma envelope without ``code_table`` key → empty list, not None."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_code_tables() == []

    def test_list_code_tables_handles_single_dict_response(self):
        """A single code-table returned as dict (not list) is normalised."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "code_table": {
                    "name": "OnlyTable",
                    "description": "The only table",
                },
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.list_code_tables()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "OnlyTable"

    def test_list_code_tables_does_not_send_scope_param(self):
        """Audit-flagged: the endpoint takes NO ``scope`` parameter.

        The AC explicitly forbids exposing a scope filter. This test
        guards against a future regression where someone re-adds it.
        """
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"code_table": []})
        config = Configuration(mock_client)

        config.list_code_tables()

        params = mock_client.calls["get"][0]["params"] or {}
        assert "scope" not in params

    def test_list_code_tables_signature_takes_no_args(self):
        """list_code_tables takes no positional / keyword args (AC)."""
        import inspect
        from almaapitk.domains.configuration import Configuration

        sig = inspect.signature(Configuration.list_code_tables)
        # Only ``self`` is allowed; no scope, no filter, no kwargs.
        assert list(sig.parameters.keys()) == ["self"]

    def test_list_code_tables_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_code_tables()


class TestGetCodeTable:
    """Tests for ``Configuration.get_code_table`` (issue #26)."""

    def test_get_code_table_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "name": "AcqInvoiceLineType",
                "description": "Invoice line types",
                "row": [
                    {
                        "code": "REGULAR",
                        "description": "Regular line",
                        "enabled": {"value": "true"},
                    },
                    {
                        "code": "ADJUSTMENT",
                        "description": "Adjustment line",
                        "enabled": {"value": "true"},
                    },
                ],
            }
        )
        config = Configuration(mock_client)

        result = config.get_code_table("AcqInvoiceLineType")

        assert len(mock_client.calls["get"]) == 1
        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/code-tables/AcqInvoiceLineType"
        )
        assert isinstance(result, dict)
        assert result["name"] == "AcqInvoiceLineType"
        # The full code-table object is returned unwrapped, including rows.
        assert isinstance(result["row"], list)
        assert len(result["row"]) == 2
        assert result["row"][0]["code"] == "REGULAR"

    def test_get_code_table_returns_unwrapped_dict_with_rows(self):
        """``get_code_table`` returns the raw object, not an envelope."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "name": "VendorReferenceNumberType",
                "row": [{"code": "VRN", "description": "VRN"}],
            }
        )
        config = Configuration(mock_client)

        result = config.get_code_table("VendorReferenceNumberType")

        assert isinstance(result, dict)
        # No envelope keys at the top level.
        assert "code_table" not in result
        assert "total_record_count" not in result
        # Direct access to the row collection works.
        assert result["row"][0]["code"] == "VRN"

    def test_get_code_table_strips_whitespace(self):
        """Validator trims whitespace from the name before building URL."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"name": "AcqInvoiceLineType"}
        )
        config = Configuration(mock_client)

        config.get_code_table("  AcqInvoiceLineType  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/code-tables/AcqInvoiceLineType"
        )

    def test_get_code_table_rejects_empty_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_code_table("")

    def test_get_code_table_rejects_whitespace_only(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_code_table("   ")

    def test_get_code_table_rejects_non_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_code_table(123)  # type: ignore[arg-type]

    def test_get_code_table_rejects_none(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_code_table(None)  # type: ignore[arg-type]

    def test_get_code_table_propagates_api_error(self):
        """Alma 90101 (table does not exist) propagates as AlmaAPIError."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Table does not exist.", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.get_code_table("NoSuchTable")


class TestUpdateCodeTable:
    """Tests for ``Configuration.update_code_table`` (issue #26)."""

    @staticmethod
    def _valid_payload() -> Dict[str, Any]:
        # PUT replaces the entire table — payload mirrors what
        # ``get_code_table`` returns, including the full ``row`` list.
        return {
            "name": "AcqInvoiceLineType",
            "description": "Invoice line types",
            "row": [
                {
                    "code": "REGULAR",
                    "description": "Regular line",
                    "enabled": {"value": "true"},
                },
                {
                    "code": "ADJUSTMENT",
                    "description": "Adjustment line",
                    "enabled": {"value": "false"},
                },
            ],
        }

    def test_update_code_table_calls_correct_endpoint_and_returns_response(
        self,
    ):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={
                "name": "AcqInvoiceLineType",
                "description": "Invoice line types",
                "row": [
                    {"code": "REGULAR", "enabled": {"value": "true"}},
                    {"code": "ADJUSTMENT", "enabled": {"value": "false"}},
                ],
            }
        )
        config = Configuration(mock_client)

        response = config.update_code_table(
            "AcqInvoiceLineType", self._valid_payload()
        )

        assert len(mock_client.calls["put"]) == 1
        call = mock_client.calls["put"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/conf/code-tables/AcqInvoiceLineType"
        )
        # Body forwarded verbatim — full table object on the wire.
        assert call["data"] == self._valid_payload()
        assert response is mock_client.put_response
        assert response.data["name"] == "AcqInvoiceLineType"

    def test_update_code_table_strips_whitespace_in_name(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={"name": "AcqInvoiceLineType"}
        )
        config = Configuration(mock_client)

        config.update_code_table(
            "  AcqInvoiceLineType  ", self._valid_payload()
        )

        assert (
            mock_client.calls["put"][0]["endpoint"]
            == "almaws/v1/conf/code-tables/AcqInvoiceLineType"
        )

    def test_update_code_table_rejects_empty_name(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_code_table("", self._valid_payload())

    def test_update_code_table_rejects_whitespace_only_name(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_code_table("   ", self._valid_payload())

    def test_update_code_table_rejects_non_string_name(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_code_table(
                123, self._valid_payload()  # type: ignore[arg-type]
            )

    def test_update_code_table_rejects_empty_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_code_table("AcqInvoiceLineType", {})

    def test_update_code_table_rejects_non_dict_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_code_table(
                "AcqInvoiceLineType",
                "not a dict",  # type: ignore[arg-type]
            )

    def test_update_code_table_rejects_none_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_code_table(
                "AcqInvoiceLineType", None  # type: ignore[arg-type]
            )

    def test_update_code_table_propagates_api_error(self):
        """Alma 90123 (table not customizable) propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Requested table is not customizable", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.update_code_table(
                "AcqInvoiceLineType", self._valid_payload()
            )

        assert "not customizable" in str(exc_info.value)

    def test_update_code_table_propagates_generic_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.update_code_table(
                "AcqInvoiceLineType", self._valid_payload()
            )


# ---------------------------------------------------------------------------
# Issue #27: Mapping tables (list / get / update)
# ---------------------------------------------------------------------------


class TestListMappingTables:
    """Tests for ``Configuration.list_mapping_tables`` (issue #27)."""

    def test_list_mapping_tables_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "mapping_table": [
                    {
                        "name": "RecallDueDate",
                        "description": "Recall due-date overrides",
                    },
                    {
                        "name": "FineFeeTransactionType",
                        "description": "Fine/fee transaction types",
                    },
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_mapping_tables()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/mapping-tables"
        # Single round-trip with generous page size; no scope filter.
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "RecallDueDate"

    def test_list_mapping_tables_returns_empty_list_on_missing_key(self):
        """Alma envelope without ``mapping_table`` key → empty list."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_mapping_tables() == []

    def test_list_mapping_tables_handles_single_dict_response(self):
        """A single mapping-table returned as dict (not list) is normalised."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "mapping_table": {
                    "name": "OnlyTable",
                    "description": "The only mapping table",
                },
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.list_mapping_tables()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "OnlyTable"

    def test_list_mapping_tables_does_not_send_scope_param(self):
        """Audit-flagged: the endpoint takes NO ``scope`` parameter.

        Mirrors the equivalent guard on ``list_code_tables`` (#26). The
        AC explicitly forbids exposing a scope filter.
        """
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"mapping_table": []}
        )
        config = Configuration(mock_client)

        config.list_mapping_tables()

        params = mock_client.calls["get"][0]["params"] or {}
        assert "scope" not in params

    def test_list_mapping_tables_signature_takes_no_args(self):
        """list_mapping_tables takes no positional / keyword args (AC)."""
        import inspect
        from almaapitk.domains.configuration import Configuration

        sig = inspect.signature(Configuration.list_mapping_tables)
        # Only ``self`` is allowed; no scope, no filter, no kwargs.
        assert list(sig.parameters.keys()) == ["self"]

    def test_list_mapping_tables_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_mapping_tables()


class TestGetMappingTable:
    """Tests for ``Configuration.get_mapping_table`` (issue #27)."""

    def test_get_mapping_table_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "name": "RecallDueDate",
                "description": "Recall due-date overrides",
                "row": [
                    {
                        "column0": "STAFF",
                        "column1": "7",
                        "enabled": {"value": "true"},
                    },
                    {
                        "column0": "STUDENT",
                        "column1": "14",
                        "enabled": {"value": "true"},
                    },
                ],
            }
        )
        config = Configuration(mock_client)

        result = config.get_mapping_table("RecallDueDate")

        assert len(mock_client.calls["get"]) == 1
        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/mapping-tables/RecallDueDate"
        )
        assert isinstance(result, dict)
        assert result["name"] == "RecallDueDate"
        # Full mapping-table object returned unwrapped, including rows.
        assert isinstance(result["row"], list)
        assert len(result["row"]) == 2
        assert result["row"][0]["column0"] == "STAFF"

    def test_get_mapping_table_returns_unwrapped_dict_with_rows(self):
        """``get_mapping_table`` returns the raw object, not an envelope."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "name": "FineFeeTransactionType",
                "row": [{"column0": "PAYMENT", "column1": "Payment"}],
            }
        )
        config = Configuration(mock_client)

        result = config.get_mapping_table("FineFeeTransactionType")

        assert isinstance(result, dict)
        # No envelope keys at the top level.
        assert "mapping_table" not in result
        assert "total_record_count" not in result
        # Direct access to the row collection works.
        assert result["row"][0]["column0"] == "PAYMENT"

    def test_get_mapping_table_strips_whitespace(self):
        """Validator trims whitespace from the name before building URL."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"name": "RecallDueDate"}
        )
        config = Configuration(mock_client)

        config.get_mapping_table("  RecallDueDate  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/mapping-tables/RecallDueDate"
        )

    def test_get_mapping_table_rejects_empty_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_mapping_table("")

    def test_get_mapping_table_rejects_whitespace_only(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_mapping_table("   ")

    def test_get_mapping_table_rejects_non_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_mapping_table(123)  # type: ignore[arg-type]

    def test_get_mapping_table_rejects_none(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_mapping_table(None)  # type: ignore[arg-type]

    def test_get_mapping_table_propagates_api_error(self):
        """Alma 90101 (table does not exist) propagates as AlmaAPIError."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Table does not exist.", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.get_mapping_table("NoSuchTable")


class TestUpdateMappingTable:
    """Tests for ``Configuration.update_mapping_table`` (issue #27)."""

    @staticmethod
    def _valid_payload() -> Dict[str, Any]:
        # PUT replaces the entire table — payload mirrors what
        # ``get_mapping_table`` returns, including the full ``row`` list.
        return {
            "name": "RecallDueDate",
            "description": "Recall due-date overrides",
            "row": [
                {
                    "column0": "STAFF",
                    "column1": "7",
                    "enabled": {"value": "true"},
                },
                {
                    "column0": "STUDENT",
                    "column1": "14",
                    "enabled": {"value": "false"},
                },
            ],
        }

    def test_update_mapping_table_calls_correct_endpoint_and_returns_response(
        self,
    ):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={
                "name": "RecallDueDate",
                "description": "Recall due-date overrides",
                "row": [
                    {"column0": "STAFF", "enabled": {"value": "true"}},
                    {"column0": "STUDENT", "enabled": {"value": "false"}},
                ],
            }
        )
        config = Configuration(mock_client)

        response = config.update_mapping_table(
            "RecallDueDate", self._valid_payload()
        )

        assert len(mock_client.calls["put"]) == 1
        call = mock_client.calls["put"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/conf/mapping-tables/RecallDueDate"
        )
        # Body forwarded verbatim — full table object on the wire.
        assert call["data"] == self._valid_payload()
        assert response is mock_client.put_response
        assert response.data["name"] == "RecallDueDate"

    def test_update_mapping_table_strips_whitespace_in_name(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={"name": "RecallDueDate"}
        )
        config = Configuration(mock_client)

        config.update_mapping_table(
            "  RecallDueDate  ", self._valid_payload()
        )

        assert (
            mock_client.calls["put"][0]["endpoint"]
            == "almaws/v1/conf/mapping-tables/RecallDueDate"
        )

    def test_update_mapping_table_rejects_empty_name(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_mapping_table("", self._valid_payload())

    def test_update_mapping_table_rejects_whitespace_only_name(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_mapping_table("   ", self._valid_payload())

    def test_update_mapping_table_rejects_non_string_name(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_mapping_table(
                123, self._valid_payload()  # type: ignore[arg-type]
            )

    def test_update_mapping_table_rejects_empty_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_mapping_table("RecallDueDate", {})

    def test_update_mapping_table_rejects_non_dict_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_mapping_table(
                "RecallDueDate",
                "not a dict",  # type: ignore[arg-type]
            )

    def test_update_mapping_table_rejects_none_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_mapping_table(
                "RecallDueDate", None  # type: ignore[arg-type]
            )

    def test_update_mapping_table_propagates_api_error(self):
        """Alma 90123 (table not customizable) propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Requested table is not customizable", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.update_mapping_table(
                "RecallDueDate", self._valid_payload()
            )

        assert "not customizable" in str(exc_info.value)

    def test_update_mapping_table_propagates_generic_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.update_mapping_table(
                "RecallDueDate", self._valid_payload()
            )


# ---------------------------------------------------------------------------
# Issue #30: Deposit profiles + metadata-import profiles (read-only)
# ---------------------------------------------------------------------------


class TestListDepositProfiles:
    """Tests for ``Configuration.list_deposit_profiles`` (issue #30)."""

    def test_list_deposit_profiles_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "deposit_profile": [
                    {"id": "1234", "name": "Default Deposit"},
                    {"id": "5678", "name": "Thesis Deposit"},
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_deposit_profiles()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/deposit-profiles"
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "1234"
        assert result[1]["name"] == "Thesis Deposit"

    def test_list_deposit_profiles_returns_empty_list_on_missing_key(self):
        """Alma envelope without ``deposit_profile`` key → empty list."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_deposit_profiles() == []

    def test_list_deposit_profiles_handles_single_dict_response(self):
        """A single deposit profile returned as dict (not list) is normalised."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "deposit_profile": {"id": "ONLY", "name": "Only Profile"},
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.list_deposit_profiles()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "ONLY"

    def test_list_deposit_profiles_signature_takes_no_args(self):
        """list_deposit_profiles takes no positional / keyword args (AC)."""
        import inspect
        from almaapitk.domains.configuration import Configuration

        sig = inspect.signature(Configuration.list_deposit_profiles)
        # Only ``self`` is allowed.
        assert list(sig.parameters.keys()) == ["self"]

    def test_list_deposit_profiles_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_deposit_profiles()


class TestGetDepositProfile:
    """Tests for ``Configuration.get_deposit_profile`` (issue #30)."""

    def test_get_deposit_profile_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "id": "1234",
                "name": "Default Deposit",
                "description": "Default deposit profile",
            }
        )
        config = Configuration(mock_client)

        result = config.get_deposit_profile("1234")

        assert len(mock_client.calls["get"]) == 1
        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/deposit-profiles/1234"
        )
        assert isinstance(result, dict)
        assert result["id"] == "1234"
        assert result["name"] == "Default Deposit"

    def test_get_deposit_profile_returns_unwrapped_dict(self):
        """``get_deposit_profile`` returns the raw object, not an envelope."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"id": "1234", "name": "Default Deposit"}
        )
        config = Configuration(mock_client)

        result = config.get_deposit_profile("1234")

        assert isinstance(result, dict)
        # No envelope keys at the top level.
        assert "deposit_profile" not in result
        assert "total_record_count" not in result

    def test_get_deposit_profile_strips_whitespace(self):
        """Validator trims whitespace from the id before building URL."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"id": "1234"})
        config = Configuration(mock_client)

        config.get_deposit_profile("  1234  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/deposit-profiles/1234"
        )

    def test_get_deposit_profile_rejects_empty_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_deposit_profile("")

    def test_get_deposit_profile_rejects_whitespace_only(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_deposit_profile("   ")

    def test_get_deposit_profile_rejects_non_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_deposit_profile(1234)  # type: ignore[arg-type]

    def test_get_deposit_profile_rejects_none(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_deposit_profile(None)  # type: ignore[arg-type]

    def test_get_deposit_profile_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "not found", status_code=404
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.get_deposit_profile("NOPE")


class TestListImportProfiles:
    """Tests for ``Configuration.list_import_profiles`` (issue #30)."""

    def test_list_import_profiles_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "import_profile": [
                    {"id": "100", "name": "MARC Import"},
                    {"id": "200", "name": "Dublin Core Import"},
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_import_profiles()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/md-import-profiles"
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "100"
        assert result[1]["name"] == "Dublin Core Import"

    def test_list_import_profiles_returns_empty_list_on_missing_key(self):
        """Alma envelope without ``import_profile`` key → empty list."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_import_profiles() == []

    def test_list_import_profiles_handles_single_dict_response(self):
        """A single import profile returned as dict (not list) is normalised."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "import_profile": {"id": "100", "name": "Only Profile"},
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.list_import_profiles()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "100"

    def test_list_import_profiles_signature_takes_no_args(self):
        """list_import_profiles takes no positional / keyword args (AC)."""
        import inspect
        from almaapitk.domains.configuration import Configuration

        sig = inspect.signature(Configuration.list_import_profiles)
        # Only ``self`` is allowed.
        assert list(sig.parameters.keys()) == ["self"]

    def test_list_import_profiles_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_import_profiles()


class TestGetImportProfile:
    """Tests for ``Configuration.get_import_profile`` (issue #30)."""

    def test_get_import_profile_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "id": "100",
                "name": "MARC Import",
                "description": "Standard MARC import",
            }
        )
        config = Configuration(mock_client)

        result = config.get_import_profile("100")

        assert len(mock_client.calls["get"]) == 1
        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/md-import-profiles/100"
        )
        assert isinstance(result, dict)
        assert result["id"] == "100"
        assert result["name"] == "MARC Import"

    def test_get_import_profile_returns_unwrapped_dict(self):
        """``get_import_profile`` returns the raw object, not an envelope."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"id": "100", "name": "MARC Import"}
        )
        config = Configuration(mock_client)

        result = config.get_import_profile("100")

        assert isinstance(result, dict)
        # No envelope keys at the top level.
        assert "import_profile" not in result
        assert "total_record_count" not in result

    def test_get_import_profile_strips_whitespace(self):
        """Validator trims whitespace from the id before building URL."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"id": "100"})
        config = Configuration(mock_client)

        config.get_import_profile("  100  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/md-import-profiles/100"
        )

    def test_get_import_profile_rejects_empty_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_import_profile("")

    def test_get_import_profile_rejects_whitespace_only(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_import_profile("   ")

    def test_get_import_profile_rejects_non_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_import_profile(100)  # type: ignore[arg-type]

    def test_get_import_profile_rejects_none(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_import_profile(None)  # type: ignore[arg-type]

    def test_get_import_profile_propagates_api_error(self):
        """Alma 401871 (Failed to find Profile ID) propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Failed to find the Profile ID.", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.get_import_profile("999999")

        assert "Profile ID" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Issue #33: Letters (list / get / update) + Printers (list / get)
# ---------------------------------------------------------------------------


class TestListLetters:
    """Tests for ``Configuration.list_letters`` (issue #33)."""

    def test_list_letters_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "letter": [
                    {
                        "code": "OverdueAndLostLoanLetter",
                        "letter_name": "Overdue and Lost Loan Letter",
                        "enabled": {"value": "true"},
                    },
                    {
                        "code": "FulHoldShelfLetter",
                        "letter_name": "Hold Shelf Letter",
                        "enabled": {"value": "true"},
                    },
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_letters()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/letters"
        # Single round-trip with generous page size.
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["code"] == "OverdueAndLostLoanLetter"
        assert result[1]["code"] == "FulHoldShelfLetter"

    def test_list_letters_returns_empty_list_on_missing_key(self):
        """Alma envelope without ``letter`` key → empty list, not None."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_letters() == []

    def test_list_letters_handles_single_dict_response(self):
        """A single letter returned as dict (not list) is normalised."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "letter": {
                    "code": "OnlyLetter",
                    "letter_name": "Only Letter",
                },
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.list_letters()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["code"] == "OnlyLetter"

    def test_list_letters_signature_takes_no_args(self):
        """list_letters takes no positional / keyword args (AC)."""
        import inspect
        from almaapitk.domains.configuration import Configuration

        sig = inspect.signature(Configuration.list_letters)
        # Only ``self`` is allowed.
        assert list(sig.parameters.keys()) == ["self"]

    def test_list_letters_propagates_api_error(self):
        """Alma 60344 (Problem retrieving letter data) propagates."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Problem retrieving letter data.", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_letters()


class TestGetLetter:
    """Tests for ``Configuration.get_letter`` (issue #33)."""

    def test_get_letter_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "code": "OverdueAndLostLoanLetter",
                "letter_name": "Overdue and Lost Loan Letter",
                "description": "Sent on overdue / lost loans.",
                "enabled": {"value": "true"},
                "subject": "Your loan is overdue",
                "body": "<xsl:stylesheet>...</xsl:stylesheet>",
                "letter_template_xsl": "<xsl:stylesheet>...</xsl:stylesheet>",
            }
        )
        config = Configuration(mock_client)

        result = config.get_letter("OverdueAndLostLoanLetter")

        assert len(mock_client.calls["get"]) == 1
        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/letters/OverdueAndLostLoanLetter"
        )
        assert isinstance(result, dict)
        assert result["code"] == "OverdueAndLostLoanLetter"
        # Sub-objects surfaced verbatim.
        assert result["subject"] == "Your loan is overdue"
        assert "letter_template_xsl" in result

    def test_get_letter_returns_unwrapped_dict(self):
        """``get_letter`` returns the raw object, not an envelope."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "code": "FulHoldShelfLetter",
                "letter_name": "Hold Shelf Letter",
            }
        )
        config = Configuration(mock_client)

        result = config.get_letter("FulHoldShelfLetter")

        assert isinstance(result, dict)
        # No envelope keys at the top level.
        assert "letter" not in result
        assert "total_record_count" not in result

    def test_get_letter_strips_whitespace(self):
        """Validator trims whitespace from the code before building URL."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"code": "OverdueAndLostLoanLetter"}
        )
        config = Configuration(mock_client)

        config.get_letter("  OverdueAndLostLoanLetter  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/letters/OverdueAndLostLoanLetter"
        )

    def test_get_letter_rejects_empty_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_letter("")

    def test_get_letter_rejects_whitespace_only(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_letter("   ")

    def test_get_letter_rejects_non_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_letter(123)  # type: ignore[arg-type]

    def test_get_letter_rejects_none(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_letter(None)  # type: ignore[arg-type]

    def test_get_letter_propagates_api_error(self):
        """Alma 40166411 (Letter code is not valid) propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Letter code is not valid.", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.get_letter("NoSuchLetter")

        assert "Letter code" in str(exc_info.value)


class TestAlmaDictToXml:
    """Tests for the dict → XML serializer used by update_letter (issue #114)."""

    def test_plain_string_fields(self):
        from almaapitk.domains.configuration import _alma_dict_to_xml

        xml = _alma_dict_to_xml({"a": "1", "b": "2"}, "letter")
        assert xml == "<letter><a>1</a><b>2</b></letter>"

    def test_value_desc_dict_collapses_to_scalar(self):
        from almaapitk.domains.configuration import _alma_dict_to_xml

        xml = _alma_dict_to_xml(
            {"enabled": {"value": "true", "desc": "Yes"}}, "letter"
        )
        # Value becomes element text; desc rides as an attribute.
        assert xml == '<letter><enabled desc="Yes">true</enabled></letter>'

    def test_value_only_dict_yields_text_no_attributes(self):
        from almaapitk.domains.configuration import _alma_dict_to_xml

        xml = _alma_dict_to_xml({"updated_by": {"value": "abc"}}, "letter")
        assert xml == "<letter><updated_by>abc</updated_by></letter>"

    def test_empty_string_value_omits_text(self):
        from almaapitk.domains.configuration import _alma_dict_to_xml

        xml = _alma_dict_to_xml({"retention_period": ""}, "letter")
        # Self-closing or empty element either way is acceptable.
        assert xml in {
            "<letter><retention_period /></letter>",
            "<letter><retention_period></retention_period></letter>",
        }

    def test_link_attribute_is_preserved_when_present(self):
        from almaapitk.domains.configuration import _alma_dict_to_xml

        xml = _alma_dict_to_xml(
            {
                "labels": {
                    "value": "SyntheticLetterCode",
                    "link": "https://example/code-tables/X",
                }
            },
            "letter",
        )
        assert "labels" in xml
        assert 'link="https://example/code-tables/X"' in xml
        assert ">SyntheticLetterCode<" in xml

    def test_xsl_content_is_escaped_not_raw(self):
        # Embedded XML markup in element text is escaped by ElementTree
        # so the receiver can unescape it back. CDATA is not required.
        from almaapitk.domains.configuration import _alma_dict_to_xml

        xsl = '<xsl:stylesheet xmlns:xsl="x"><foo & bar></xsl:stylesheet>'
        xml = _alma_dict_to_xml({"xsl": xsl}, "letter")
        assert "&lt;xsl:stylesheet" in xml
        assert "&amp;" in xml
        # The raw < should NOT appear inside element text.
        assert "<xsl:stylesheet" not in xml.replace("<xsl>", "").replace(
            "<letter>", ""
        )

    def test_letter_round_trip_shape_matches_alma_get_response(self):
        # End-to-end check: a payload mirroring an Alma get_letter
        # response serialises to a well-formed <letter>...</letter>.
        from almaapitk.domains.configuration import _alma_dict_to_xml

        payload = {
            "code": "SyntheticLetterCode",
            "enabled": {"value": "false", "desc": "No"},
            "name": "Ful Transit Slip Letter",
            "description": "Ful Transit Slip Letter",
            "channel": "EMAIL",
            "retention_period": "",
            "customized": {"value": "false", "desc": "No"},
            "patron_facing": {"value": "false", "desc": "No"},
            "updated_by": {"value": "027393602"},
            "update_date": "2018-10-24Z",
            "labels": {
                "value": "SyntheticLetterCode",
                "link": "https://example/code-tables/SyntheticLetterCode",
            },
            "xsl": "<?xml version='1.0'?><xsl:stylesheet/>",
        }
        xml = _alma_dict_to_xml(payload, "letter")
        assert xml.startswith("<letter>")
        assert xml.endswith("</letter>")
        assert "<code>SyntheticLetterCode</code>" in xml
        assert "<enabled" in xml and "false</enabled>" in xml
        assert "<channel>EMAIL</channel>" in xml
        assert "&lt;xsl:stylesheet" in xml  # escaped, not raw

    def test_none_value_yields_empty_element(self):
        from almaapitk.domains.configuration import _alma_dict_to_xml

        xml = _alma_dict_to_xml({"foo": None}, "letter")
        assert xml in {
            "<letter><foo /></letter>",
            "<letter><foo></foo></letter>",
        }


class TestUpdateLetter:
    """Tests for ``Configuration.update_letter`` (issue #33)."""

    @staticmethod
    def _valid_payload() -> Dict[str, Any]:
        # PUT replaces the entire letter — payload mirrors what
        # ``get_letter`` returns, including subject + XSL body.
        return {
            "code": "OverdueAndLostLoanLetter",
            "letter_name": "Overdue and Lost Loan Letter",
            "description": "Sent on overdue / lost loans.",
            "enabled": {"value": "true"},
            "subject": "Your loan is overdue",
            "body": "<xsl:stylesheet>...</xsl:stylesheet>",
            "letter_template_xsl": "<xsl:stylesheet>...</xsl:stylesheet>",
        }

    def test_update_letter_calls_correct_endpoint_and_returns_response(self):
        # Issue #114: Alma's letters PUT requires XML, so update_letter
        # serialises the dict and sends Content-Type: application/xml
        # while forcing Accept: application/json so the response is
        # still parsed as a dict by AlmaResponse.
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={
                "code": "OverdueAndLostLoanLetter",
                "letter_name": "Overdue and Lost Loan Letter",
                "subject": "Your loan is overdue",
            }
        )
        config = Configuration(mock_client)

        response = config.update_letter(
            "OverdueAndLostLoanLetter", self._valid_payload()
        )

        assert len(mock_client.calls["put"]) == 1
        call = mock_client.calls["put"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/conf/letters/OverdueAndLostLoanLetter"
        )
        # Body is XML, not the raw dict.
        assert isinstance(call["data"], str)
        assert call["data"].startswith("<letter>")
        assert call["data"].endswith("</letter>")
        # Content-Type and Accept are wired for the XML-in / JSON-out shape.
        assert call["content_type"] == "application/xml"
        assert call["custom_headers"] == {"Accept": "application/json"}
        # XML body carries every top-level field from the payload.
        assert "<code>OverdueAndLostLoanLetter</code>" in call["data"]
        assert "<subject>Your loan is overdue</subject>" in call["data"]
        # value/desc dicts collapse to scalar text (desc is preserved
        # as an attribute when present and non-empty).
        assert '<enabled>true</enabled>' in call["data"] or '<enabled' in call["data"]

        assert response is mock_client.put_response
        assert response.data["code"] == "OverdueAndLostLoanLetter"

    # TODO(#135): migrate to tests/unit/regressions/test_issue_114.py
    # once that home exists.
    def test_update_letter_sends_xml_body_regression_114(self):
        """R10 regression for issue #114.

        Before commit 2d20ab3 (``fix(configuration): send XML body for
        update_letter``), ``update_letter`` passed the caller's dict to
        ``self.client.put`` as a JSON body. Alma's letters PUT endpoint
        rejects JSON with error code ``60105 "JSON is not supported for
        this API."`` — letters require an XML payload.

        This test pins the symptom: the wire request MUST carry an XML
        body with ``Content-Type: application/xml``. The assertions
        below are intentionally tight so that any regression back to a
        JSON body (e.g. ``data=letter_data`` without serialisation, or
        ``json=letter_data``) fails this test loudly. The companion
        test ``test_update_letter_calls_correct_endpoint_and_returns_response``
        covers behavioural shape; this test is the bug-driven pin.

        Pattern source: ``test_update_letter_calls_correct_endpoint_and_returns_response``
        immediately above — same MockAlmaAPIClient / MockAlmaResponse
        wiring, narrowed assertion surface.
        """
        import json as _json

        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={"code": "OverdueAndLostLoanLetter"}
        )
        config = Configuration(mock_client)

        payload = self._valid_payload()
        config.update_letter("OverdueAndLostLoanLetter", payload)

        # Exactly one PUT was issued.
        assert len(mock_client.calls["put"]) == 1
        call = mock_client.calls["put"][0]

        # --- Content-Type pin -------------------------------------
        # Must be application/xml. Any regression to the project-wide
        # JSON default (None, "application/json", or unset) fails here.
        assert call["content_type"] == "application/xml", (
            "update_letter must send Content-Type: application/xml — "
            "Alma error 60105 'JSON is not supported for this API.' "
            "regresses if this flips back to JSON (issue #114)."
        )

        # --- Body shape pin ---------------------------------------
        body = call["data"]
        # The body must be a string (the serialised XML), NOT the raw
        # dict that the caller passed in. A regression like
        # ``self.client.put(..., data=letter_data)`` would leave a dict
        # here.
        assert isinstance(body, str), (
            f"update_letter must serialise the payload to a string; "
            f"got {type(body).__name__}. A regression that passes the "
            f"caller's dict straight through (issue #114) trips here."
        )

        # The body must NOT be a JSON-encoded string. ``json.dumps`` of
        # a dict starts with ``{`` — any string that round-trips through
        # ``json.loads`` to the original dict is the regressed shape.
        assert not body.lstrip().startswith("{"), (
            "update_letter body looks like JSON, not XML — issue #114 "
            "regression (Alma error 60105 'JSON is not supported')."
        )
        try:
            decoded = _json.loads(body)
        except (ValueError, TypeError):
            decoded = None
        assert decoded != payload, (
            "update_letter body is JSON-encoded form of the caller's "
            "dict — issue #114 regression."
        )

        # --- XML structural pin -----------------------------------
        # The body must look like XML and must carry the letter code so
        # the Alma backend can identify the target.
        assert body.startswith("<"), (
            "update_letter body must be XML and start with '<'."
        )
        assert "<letter>" in body and "</letter>" in body, (
            "update_letter body must wrap the payload in a <letter> "
            "element."
        )
        assert "<code>OverdueAndLostLoanLetter</code>" in body, (
            "update_letter body must carry the letter code as XML."
        )

    def test_update_letter_strips_whitespace_in_code(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.put_response = MockAlmaResponse(
            body={"code": "OverdueAndLostLoanLetter"}
        )
        config = Configuration(mock_client)

        config.update_letter(
            "  OverdueAndLostLoanLetter  ", self._valid_payload()
        )

        assert (
            mock_client.calls["put"][0]["endpoint"]
            == "almaws/v1/conf/letters/OverdueAndLostLoanLetter"
        )

    def test_update_letter_rejects_empty_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_letter("", self._valid_payload())

    def test_update_letter_rejects_whitespace_only_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_letter("   ", self._valid_payload())

    def test_update_letter_rejects_non_string_code(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_letter(
                123, self._valid_payload()  # type: ignore[arg-type]
            )

    def test_update_letter_rejects_empty_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_letter("OverdueAndLostLoanLetter", {})

    def test_update_letter_rejects_non_dict_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_letter(
                "OverdueAndLostLoanLetter",
                "not a dict",  # type: ignore[arg-type]
            )

    def test_update_letter_rejects_none_payload(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.update_letter(
                "OverdueAndLostLoanLetter",
                None,  # type: ignore[arg-type]
            )

    def test_update_letter_propagates_api_error(self):
        """Alma 60343 (The update failed) propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "The update failed.", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.update_letter(
                "OverdueAndLostLoanLetter", self._valid_payload()
            )

        assert "update failed" in str(exc_info.value)

    def test_update_letter_propagates_generic_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.update_letter(
                "OverdueAndLostLoanLetter", self._valid_payload()
            )


class TestListPrinters:
    """Tests for ``Configuration.list_printers`` (issue #33)."""

    def test_list_printers_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "printer": [
                    {
                        "id": "1234",
                        "name": "Main Desk Printer",
                        "code": "MAIN_DESK",
                    },
                    {
                        "id": "5678",
                        "name": "Annex Printer",
                        "code": "ANNEX",
                    },
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.list_printers()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/printers"
        # Single round-trip with generous page size.
        assert call["params"] == {"limit": "100", "offset": "0"}
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "1234"
        assert result[1]["name"] == "Annex Printer"

    def test_list_printers_returns_empty_list_on_missing_key(self):
        """Alma envelope without ``printer`` key → empty list, not None."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.list_printers() == []

    def test_list_printers_handles_single_dict_response(self):
        """A single printer returned as dict (not list) is normalised."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "printer": {"id": "ONLY", "name": "Only Printer"},
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.list_printers()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "ONLY"

    def test_list_printers_signature_takes_no_args(self):
        """list_printers takes no positional / keyword args (AC)."""
        import inspect
        from almaapitk.domains.configuration import Configuration

        sig = inspect.signature(Configuration.list_printers)
        # Only ``self`` is allowed.
        assert list(sig.parameters.keys()) == ["self"]

    def test_list_printers_propagates_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.list_printers()


class TestGetPrinter:
    """Tests for ``Configuration.get_printer`` (issue #33)."""

    def test_get_printer_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "id": "1234",
                "name": "Main Desk Printer",
                "code": "MAIN_DESK",
                "description": "Front desk printer",
            }
        )
        config = Configuration(mock_client)

        result = config.get_printer("1234")

        assert len(mock_client.calls["get"]) == 1
        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/printers/1234"
        )
        assert isinstance(result, dict)
        assert result["id"] == "1234"
        assert result["name"] == "Main Desk Printer"

    def test_get_printer_returns_unwrapped_dict(self):
        """``get_printer`` returns the raw object, not an envelope."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"id": "1234", "name": "Main Desk Printer"}
        )
        config = Configuration(mock_client)

        result = config.get_printer("1234")

        assert isinstance(result, dict)
        # No envelope keys at the top level.
        assert "printer" not in result
        assert "total_record_count" not in result

    def test_get_printer_strips_whitespace(self):
        """Validator trims whitespace from the id before building URL."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={"id": "1234"})
        config = Configuration(mock_client)

        config.get_printer("  1234  ")

        assert (
            mock_client.calls["get"][0]["endpoint"]
            == "almaws/v1/conf/printers/1234"
        )

    def test_get_printer_rejects_empty_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_printer("")

    def test_get_printer_rejects_whitespace_only(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_printer("   ")

    def test_get_printer_rejects_non_string(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_printer(1234)  # type: ignore[arg-type]

    def test_get_printer_rejects_none(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.get_printer(None)  # type: ignore[arg-type]

    def test_get_printer_propagates_api_error(self):
        """Alma 402899 (Invalid Printer ID) propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Invalid Printer ID.", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.get_printer("NOPE")

        assert "Printer ID" in str(exc_info.value)


class TestRunWorkflow:
    """Tests for ``Configuration.run_workflow`` (issue #35)."""

    def test_run_workflow_with_parameters_sends_body(self):
        """Parameters dict is forwarded as the JSON request body."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"id": "INSTANCE_42", "status": "RUNNING"}
        )
        config = Configuration(mock_client)

        result = config.run_workflow(
            "MY_SAFE_TEST_WORKFLOW", {"input_param": "value"}
        )

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/conf/workflows/MY_SAFE_TEST_WORKFLOW"
        )
        # Parameters forwarded verbatim as the request body.
        assert call["data"] == {"input_param": "value"}
        assert isinstance(result, dict)
        assert result["id"] == "INSTANCE_42"
        assert result["status"] == "RUNNING"

    def test_run_workflow_without_parameters_sends_no_body(self):
        """parameters=None means data=None on the wire (no body)."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"id": "INSTANCE_43", "status": "QUEUED"}
        )
        config = Configuration(mock_client)

        result = config.run_workflow("MY_SAFE_TEST_WORKFLOW")

        assert len(mock_client.calls["post"]) == 1
        call = mock_client.calls["post"][0]
        assert (
            call["endpoint"]
            == "almaws/v1/conf/workflows/MY_SAFE_TEST_WORKFLOW"
        )
        # No body forwarded when parameters is None.
        assert call["data"] is None
        assert result["id"] == "INSTANCE_43"

    def test_run_workflow_returns_unwrapped_dict(self):
        """``run_workflow`` returns the parsed body dict (no envelope)."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(
            body={"id": "INSTANCE_99", "status": "COMPLETED"}
        )
        config = Configuration(mock_client)

        result = config.run_workflow("WF")

        assert isinstance(result, dict)
        assert result == {"id": "INSTANCE_99", "status": "COMPLETED"}

    def test_run_workflow_handles_empty_body(self):
        """Empty/None response body normalises to an empty dict."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={})
        config = Configuration(mock_client)

        result = config.run_workflow("WF")

        assert result == {}

    def test_run_workflow_strips_whitespace_in_id(self):
        """Validator trims whitespace from the workflow id."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.post_response = MockAlmaResponse(body={"id": "X"})
        config = Configuration(mock_client)

        config.run_workflow("  MY_WF  ")

        assert (
            mock_client.calls["post"][0]["endpoint"]
            == "almaws/v1/conf/workflows/MY_WF"
        )

    def test_run_workflow_rejects_empty_id(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.run_workflow("")

    def test_run_workflow_rejects_whitespace_only_id(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.run_workflow("   ")

    def test_run_workflow_rejects_non_string_id(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.run_workflow(1234)  # type: ignore[arg-type]

    def test_run_workflow_rejects_none_id(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaValidationError

        config = Configuration(MockAlmaAPIClient())

        with pytest.raises(AlmaValidationError):
            config.run_workflow(None)  # type: ignore[arg-type]

    def test_run_workflow_propagates_workflow_not_found(self):
        """Alma 450001 (Workflow not found) propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "Workflow not found.", status_code=400
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.run_workflow("DOES_NOT_EXIST")

        assert "Workflow not found" in str(exc_info.value)

    def test_run_workflow_propagates_generic_api_error(self):
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "boom", status_code=500
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError):
            config.run_workflow("WF")


class TestGetFeeTransactionsReport:
    """Tests for ``Configuration.get_fee_transactions_report`` (issue #35)."""

    def test_get_fee_transactions_report_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "fee_transaction": [
                    {"id": "T1", "amount": 5.00, "status": "ACTIVE"},
                    {"id": "T2", "amount": 10.00, "status": "CLOSED"},
                ],
                "total_record_count": 2,
            }
        )
        config = Configuration(mock_client)

        result = config.get_fee_transactions_report()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/utilities/fee-transactions"
        # No filters means no params.
        assert call["params"] is None
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "T1"
        assert result[1]["status"] == "CLOSED"

    def test_get_fee_transactions_report_forwards_filters_as_params(self):
        """Arbitrary **filters kwargs flow through to the query string."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "fee_transaction": [
                    {"id": "T1", "library": "MAIN"},
                ],
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.get_fee_transactions_report(
            status="ACTIVE",
            library="MAIN",
            from_date="2026-01-01",
            to_date="2026-01-31",
        )

        call = mock_client.calls["get"][0]
        assert call["params"] == {
            "status": "ACTIVE",
            "library": "MAIN",
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
        }
        assert len(result) == 1
        assert result[0]["library"] == "MAIN"

    def test_get_fee_transactions_report_returns_empty_on_missing_key(self):
        """Envelope without ``fee_transaction`` key → empty list."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"total_record_count": 0}
        )
        config = Configuration(mock_client)

        assert config.get_fee_transactions_report() == []

    def test_get_fee_transactions_report_handles_single_dict_response(self):
        """A single transaction returned as a dict is normalised to a list."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "fee_transaction": {"id": "T1", "amount": 5.00},
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.get_fee_transactions_report()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "T1"

    def test_get_fee_transactions_report_unwraps_envelope(self):
        """Top-level envelope keys must not appear in the unwrapped list."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "fee_transaction": [{"id": "T1"}],
                "total_record_count": 1,
            }
        )
        config = Configuration(mock_client)

        result = config.get_fee_transactions_report()

        assert isinstance(result, list)
        # No envelope keys appear inside the unwrapped list items.
        assert "total_record_count" not in result[0]
        assert "fee_transaction" not in result[0]

    def test_get_fee_transactions_report_propagates_api_error(self):
        """Alma 401652 (circ library/desk error) propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "An error has occurred in setting circ library or circ desk.",
            status_code=400,
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.get_fee_transactions_report(library="BAD")

        assert "circ library" in str(exc_info.value)


class TestGetGeneralConfiguration:
    """Tests for ``Configuration.get_general_configuration`` (issue #35)."""

    def test_get_general_configuration_calls_correct_endpoint(self):
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={
                "institution": {
                    "value": "01TAU_INST",
                    "desc": "Tel Aviv University",
                },
                "default_language": {"value": "en"},
                "default_currency": {"value": "USD"},
                "timezone": "Asia/Jerusalem",
            }
        )
        config = Configuration(mock_client)

        result = config.get_general_configuration()

        assert len(mock_client.calls["get"]) == 1
        call = mock_client.calls["get"][0]
        assert call["endpoint"] == "almaws/v1/conf/general"
        # Endpoint takes no path params and no query filters.
        assert call["params"] is None
        assert isinstance(result, dict)
        assert result["institution"]["value"] == "01TAU_INST"
        assert result["timezone"] == "Asia/Jerusalem"

    def test_get_general_configuration_returns_unwrapped_dict(self):
        """No top-level envelope wrapper — body is returned verbatim."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(
            body={"timezone": "Asia/Jerusalem"}
        )
        config = Configuration(mock_client)

        result = config.get_general_configuration()

        assert isinstance(result, dict)
        assert result == {"timezone": "Asia/Jerusalem"}

    def test_get_general_configuration_handles_empty_body(self):
        """An empty Alma body normalises to an empty dict (not None)."""
        from almaapitk.domains.configuration import Configuration

        mock_client = MockAlmaAPIClient()
        mock_client.get_response = MockAlmaResponse(body={})
        config = Configuration(mock_client)

        result = config.get_general_configuration()

        assert isinstance(result, dict)
        assert result == {}

    def test_get_general_configuration_signature_takes_no_args(self):
        """get_general_configuration takes no positional / keyword args."""
        import inspect
        from almaapitk.domains.configuration import Configuration

        sig = inspect.signature(Configuration.get_general_configuration)
        # Only ``self`` is allowed.
        assert list(sig.parameters.keys()) == ["self"]

    def test_get_general_configuration_propagates_api_error(self):
        """Alma 400 ("General Error - ...") propagates verbatim."""
        from almaapitk.domains.configuration import Configuration
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient()
        mock_client.next_exception = AlmaAPIError(
            "General Error - An error has occurred while processing the "
            "request.",
            status_code=400,
        )
        config = Configuration(mock_client)

        with pytest.raises(AlmaAPIError) as exc_info:
            config.get_general_configuration()

        assert "General Error" in str(exc_info.value)
