"""
Unit tests for the Configuration domain class (issue #22).

Tests cover:
- Initialization (client, environment, logger setup)
- get_environment() - returns the environment from the underlying client
- test_connection() - delegates to client.test_connection()

These tests use mocked AlmaAPIClient instances to test the Configuration
domain in isolation. Pattern source mirrors
``tests/unit/domains/test_analytics.py``.
"""

from unittest.mock import MagicMock

import pytest


class MockAlmaAPIClient:
    """Mock AlmaAPIClient for testing the Configuration domain.

    Mirrors the shape of ``MockAlmaAPIClient`` in
    ``tests/unit/domains/test_analytics.py``.
    """

    def __init__(self, environment: str = 'SANDBOX',
                 connection_result: bool = True):
        self.environment = environment
        self.logger = MagicMock()
        self._connection_result = connection_result
        self.test_connection_call_count = 0

    def get_environment(self) -> str:
        return self.environment

    def test_connection(self) -> bool:
        self.test_connection_call_count += 1
        return self._connection_result


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


class TestConfigurationDoesNotCallHTTP:
    """Foundation-only guard: no API methods should be wired up yet."""

    def test_no_api_endpoint_methods_yet(self):
        """Foundation skeleton: only the trivial methods should exist.

        Sibling tickets (issues 24-35) add concrete endpoint methods.
        """
        from almaapitk.domains.configuration import Configuration

        # Public methods that are NOT inherited from object — just the
        # foundation skeleton.
        public_methods = {
            name for name in dir(Configuration)
            if not name.startswith('_')
        }
        # Exactly the two foundation methods plus nothing else added by
        # this PR. If a sibling ticket extends this set the assertion
        # protects against accidental scope-creep in this PR specifically.
        assert public_methods == {'get_environment', 'test_connection'}, (
            f"Foundation skeleton must only expose get_environment and "
            f"test_connection; found {public_methods}"
        )
