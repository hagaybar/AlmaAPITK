"""
Electronic Domain Class for Alma API.

Foundation skeleton for the Electronic API surface (issue #66). The
Electronic domain wraps Alma's ``/almaws/v1/electronic/*`` endpoints —
e-collections, e-services, and portfolios. This module deliberately
ships only the class skeleton (environment introspection and a smoke
connection check) so the sibling coverage tickets (#67 e-collections,
#68 e-services, #69 portfolios) can each land one focused PR on top of
this foundation.

Concrete API methods do NOT live here — they belong to the sibling
tickets.
"""
from almaapitk.client.AlmaAPIClient import AlmaAPIClient
from almaapitk.alma_logging import get_logger


class Electronic:
    """
    Domain class for handling Alma Electronic API operations.

    Foundation skeleton (issue #66). Sibling tickets layer the concrete
    endpoints on top of this class:

    - issue #67: e-collections coverage
    - issue #68: e-services coverage
    - issue #69: portfolios coverage

    This class uses the AlmaAPIClient as its foundation for all HTTP
    operations.
    """

    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the Electronic domain.

        Args:
            client: The AlmaAPIClient instance for making HTTP requests.
        """
        # Pattern source: Configuration.__init__ in configuration.py
        # (which itself mirrors Admin.__init__ in admin.py). Store the
        # client, snapshot the environment for log context, and create
        # a domain-specific logger via the shared logging factory.
        self.client = client
        self.environment = client.get_environment()
        self.logger = get_logger('electronic', environment=self.environment)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_environment(self) -> str:
        """
        Get the current environment from the underlying client.

        Returns:
            The environment string ('SANDBOX' or 'PRODUCTION').
        """
        # Pattern source: Configuration.get_environment in configuration.py.
        self.logger.debug("Electronic.get_environment called")
        environment = self.client.get_environment()
        self.logger.debug(f"Electronic.get_environment returning: {environment}")
        return environment

    def test_connection(self) -> bool:
        """
        Test if the Alma API connection is working.

        Delegates to ``AlmaAPIClient.test_connection``. Electronic
        endpoints are exercised by sibling tickets — at the foundation
        level we simply confirm the client itself can reach the API.

        Returns:
            True if the underlying client connection succeeds, False
            otherwise.
        """
        # Pattern source: Configuration.test_connection in configuration.py
        # — delegate to the client rather than hitting a domain-specific
        # endpoint, since no Electronic endpoints are wired up yet.
        self.logger.info(
            f"Testing Electronic API connection ({self.environment})"
        )
        success = self.client.test_connection()

        if success:
            self.logger.info(
                f"✓ Electronic API connection successful ({self.environment})"
            )
        else:
            self.logger.error(
                f"✗ Electronic API connection failed ({self.environment})"
            )

        return success
