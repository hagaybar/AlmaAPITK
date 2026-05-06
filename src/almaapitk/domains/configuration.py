"""
Configuration Domain Class for Alma API
Foundation skeleton for the Configuration API surface (issue #22).

This module establishes the Configuration domain class with the minimal
plumbing required by sibling tickets (issues 24-35) — environment
introspection and a smoke-test connection check. Concrete API methods
(libraries, locations, code tables, calendars, etc.) land in those
sibling tickets and intentionally do NOT live here.

Pattern source: mirrors ``src/almaapitk/domains/admin.py`` and
``src/almaapitk/domains/acquisition.py`` for ``__init__`` /
``get_environment`` / ``test_connection`` shape.
"""
from almaapitk.client.AlmaAPIClient import AlmaAPIClient
from almaapitk.alma_logging import get_logger


class Configuration:
    """
    Domain class for handling Alma Configuration API operations.

    This class is a foundation skeleton (issue #22). It establishes the
    public-API entry point for configuration endpoints — concrete methods
    (libraries, locations, code tables, calendars, etc.) ship in sibling
    tickets (issues 24-35).

    This class uses the AlmaAPIClient as its foundation for all HTTP
    operations.
    """

    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the Configuration domain.

        Args:
            client: The AlmaAPIClient instance for making HTTP requests.
        """
        # Pattern source: Acquisitions.__init__ in acquisition.py.
        self.client = client
        self.environment = client.get_environment()
        self.logger = get_logger('configuration', environment=self.environment)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_environment(self) -> str:
        """
        Get the current environment from the underlying client.

        Returns:
            The environment string ('SANDBOX' or 'PRODUCTION').
        """
        # Pattern source: Admin.get_environment in admin.py.
        self.logger.debug("Configuration.get_environment called")
        environment = self.client.get_environment()
        self.logger.debug(f"Configuration.get_environment returning: {environment}")
        return environment

    def test_connection(self) -> bool:
        """
        Test if the Alma API connection is working.

        Delegates to ``AlmaAPIClient.test_connection``. Configuration
        endpoints are exercised by sibling tickets — at the foundation
        level we simply confirm the client itself can reach the API.

        Returns:
            True if the underlying client connection succeeds, False
            otherwise.
        """
        # Pattern source: Admin.test_connection in admin.py — but here we
        # delegate to the client rather than hitting a domain-specific
        # endpoint, since no Configuration endpoints are wired up yet.
        self.logger.info(
            f"Testing Configuration API connection ({self.environment})"
        )
        success = self.client.test_connection()

        if success:
            self.logger.info(
                f"✓ Configuration API connection successful ({self.environment})"
            )
        else:
            self.logger.error(
                f"✗ Configuration API connection failed ({self.environment})"
            )

        return success
