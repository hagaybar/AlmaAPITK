"""
Unit tests for the Electronic domain class (issue #66).

Tests cover the foundation skeleton only:
- Initialization (client, environment, logger setup)
- get_environment() - returns the environment from the underlying client
- test_connection() - delegates to client.test_connection()

Concrete Electronic API methods (e-collections, e-services, portfolios)
land in sibling tickets (#67, #68, #69) and are tested there.

These tests use a mocked AlmaAPIClient to exercise the Electronic
domain in isolation. Pattern source mirrors
``tests/unit/domains/test_configuration.py`` (the most recent foundation
skeleton, issue #22).
"""

from unittest.mock import MagicMock

import pytest


class MockAlmaAPIClient:
    """Mock AlmaAPIClient for testing the Electronic domain.

    The foundation tests (issue #66) only need ``get_environment`` and
    ``test_connection``. Pattern source mirrors the foundation-tier of
    ``tests/unit/domains/test_configuration.py``'s
    ``MockAlmaAPIClient``.
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

    def get_environment(self) -> str:
        return self.environment

    def test_connection(self) -> bool:
        self.test_connection_call_count += 1
        return self._connection_result


class TestElectronicInit:
    """Tests for Electronic class initialization."""

    def test_init_sets_client(self):
        """Test that __init__ properly stores the client."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('SANDBOX')
        electronic = Electronic(mock_client)

        assert electronic.client is mock_client

    def test_init_sets_environment_from_client(self):
        """Test that __init__ stores the environment from the client."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('SANDBOX')
        electronic = Electronic(mock_client)

        assert electronic.environment == 'SANDBOX'

    def test_init_with_production_environment(self):
        """Test initialization with PRODUCTION environment."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('PRODUCTION')
        electronic = Electronic(mock_client)

        assert electronic.environment == 'PRODUCTION'

    def test_init_creates_logger(self):
        """Test that __init__ initializes a domain-specific logger."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('SANDBOX')
        electronic = Electronic(mock_client)

        # Logger must exist and have the standard logging methods we use.
        assert electronic.logger is not None
        assert hasattr(electronic.logger, 'info')
        assert hasattr(electronic.logger, 'debug')
        assert hasattr(electronic.logger, 'error')


class TestElectronicGetEnvironment:
    """Tests for Electronic.get_environment() method."""

    def test_get_environment_returns_sandbox(self):
        """Test that get_environment returns SANDBOX from sandbox client."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('SANDBOX')
        electronic = Electronic(mock_client)

        assert electronic.get_environment() == 'SANDBOX'

    def test_get_environment_returns_production(self):
        """Test that get_environment returns PRODUCTION from prod client."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('PRODUCTION')
        electronic = Electronic(mock_client)

        assert electronic.get_environment() == 'PRODUCTION'

    def test_get_environment_delegates_to_client(self):
        """Test that get_environment reads through to the client each call."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('SANDBOX')
        # Spy on the client's get_environment.
        mock_client.get_environment = MagicMock(return_value='SANDBOX')
        electronic = Electronic(mock_client)
        # Reset call count: __init__ also calls get_environment once.
        mock_client.get_environment.reset_mock()

        result = electronic.get_environment()

        assert result == 'SANDBOX'
        mock_client.get_environment.assert_called_once()


class TestElectronicTestConnection:
    """Tests for Electronic.test_connection() method."""

    def test_test_connection_success(self):
        """Test that test_connection returns True when client connects OK."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('SANDBOX', connection_result=True)
        electronic = Electronic(mock_client)

        assert electronic.test_connection() is True

    def test_test_connection_failure(self):
        """Test that test_connection returns False when client fails."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('SANDBOX', connection_result=False)
        electronic = Electronic(mock_client)

        assert electronic.test_connection() is False

    def test_test_connection_delegates_to_client(self):
        """Test that test_connection calls the client's test_connection."""
        from almaapitk.domains.electronic import Electronic

        mock_client = MockAlmaAPIClient('SANDBOX', connection_result=True)
        electronic = Electronic(mock_client)

        electronic.test_connection()

        # The client's test_connection must have been called exactly once
        # by our delegation.
        assert mock_client.test_connection_call_count == 1
