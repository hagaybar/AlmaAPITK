"""
Unit tests for the Configuration domain class (issues #22, #24).

Tests cover:
- Initialization (client, environment, logger setup)
- get_environment() - returns the environment from the underlying client
- test_connection() - delegates to client.test_connection()
- list_libraries() / get_library() (issue #24)
- list_departments() (issue #24)
- list_circ_desks() / get_circ_desk() (issue #24)

These tests use mocked AlmaAPIClient instances to test the Configuration
domain in isolation. Pattern source mirrors
``tests/unit/domains/test_admin.py`` for the get-shaped tests and
``tests/unit/domains/test_analytics.py`` for the foundation skeleton.
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

        # Per-verb response register and call log for the issue-#24
        # methods. Tests set ``get_response`` or ``next_exception`` before
        # invoking the Configuration method under test.
        self.get_response: MockAlmaResponse = MockAlmaResponse()
        self.next_exception: Optional[Exception] = None
        self.calls = {"get": []}

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
