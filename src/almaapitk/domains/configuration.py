"""
Configuration Domain Class for Alma API
Foundation skeleton for the Configuration API surface (issue #22), extended
with organizational-structure read methods (issue #24).

Issue #22 established the Configuration domain class with the minimal
plumbing required by sibling tickets — environment introspection and a
smoke-test connection check.

Issue #24 adds five read-only organizational-structure endpoints
(libraries, departments, circulation desks). Concrete API methods for
the remaining sibling tickets (locations, code tables, calendars, etc.)
land in those tickets and intentionally do NOT live here.
"""
from typing import Any, Dict, List

from almaapitk.client.AlmaAPIClient import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaValidationError,
)
from almaapitk.alma_logging import get_logger


class Configuration:
    """
    Domain class for handling Alma Configuration API operations.

    Foundation skeleton (issue #22) plus organizational-structure read
    methods (issue #24). Sibling tickets (issues 25-35) layer additional
    Configuration endpoints (locations, code tables, calendars, etc.) on
    top of this class.

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

    # =========================================================================
    # Organizational structure (issue #24)
    # =========================================================================

    @staticmethod
    def _validate_code(value: Any, field_name: str) -> str:
        """Validate a code-style identifier.

        Used by the per-library / per-circ-desk endpoints. The Alma API
        treats library and circ-desk codes as opaque non-empty strings —
        we only enforce that here and let the API surface domain-specific
        errors (404, "Parameter value missing or invalid", etc.).

        Args:
            value: The candidate value passed by the caller.
            field_name: The argument name to surface in the error message.

        Returns:
            The trimmed string when validation passes.

        Raises:
            AlmaValidationError: When the value is not a non-empty string.
        """
        if not isinstance(value, str):
            raise AlmaValidationError(
                f"{field_name} is required and must be a string"
            )
        trimmed = value.strip()
        if not trimmed:
            raise AlmaValidationError(f"{field_name} is required")
        return trimmed

    def list_libraries(self) -> List[Dict[str, Any]]:
        """
        List all libraries configured in the Alma institution.

        Calls ``GET /almaws/v1/conf/libraries`` and unwraps the Alma
        response envelope (``{"library": [...], "total_record_count": N}``)
        into a flat list. The organizational-structure tables are small —
        institutions typically have at most a few dozen libraries — so a
        single call with a generous page size is sufficient.

        Returns:
            List of library dicts as returned by Alma. Returns an empty
            list when the institution has no libraries configured (or
            when the response envelope is missing the ``library`` key).

        Raises:
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Admin.list_sets shape (admin.py line 439) for the
        # "single GET, return list" idiom — the org tables are tiny so we
        # do not need iter_paged here.
        self.logger.info(
            f"Listing libraries ({self.environment})"
        )
        try:
            # Use a generous page size so a single request covers any
            # plausible institution. Alma caps at 100; libraries rarely
            # exceed that.
            response = self.client.get(
                "almaws/v1/conf/libraries",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            libraries = payload.get("library") or []
            if isinstance(libraries, dict):
                # Single-record responses can come back as a dict; normalise.
                libraries = [libraries]
            self.logger.info(
                f"✓ Retrieved {len(libraries)} libraries"
            )
            return libraries
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to list libraries",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_library(self, library_code: str) -> Dict[str, Any]:
        """
        Get configuration details for a single library.

        Calls ``GET /almaws/v1/conf/libraries/{libraryCode}``.

        Args:
            library_code: The Alma library code (e.g., ``"MAIN"``).

        Returns:
            The library configuration dict as returned by Alma.

        Raises:
            AlmaValidationError: If ``library_code`` is empty or not a
                string.
            AlmaAPIError: If the API request fails (including 404 when
                the library code does not exist).
        """
        # Pattern source: Admin.get_set_info shape (admin.py line 313) —
        # validate, log entry, GET, log success, propagate API errors.
        code = self._validate_code(library_code, "library_code")
        self.logger.info(
            f"Getting library: {code} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/libraries/{code}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved library {code}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get library {code}",
                extra={
                    "library_code": code,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def list_departments(self) -> List[Dict[str, Any]]:
        """
        List all departments configured in the Alma institution.

        Calls ``GET /almaws/v1/conf/departments`` and unwraps the Alma
        response envelope (``{"department": [...], "total_record_count": N}``)
        into a flat list.

        Returns:
            List of department dicts. Returns an empty list when the
            institution has no departments configured.

        Raises:
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Admin.list_sets shape (admin.py line 439).
        self.logger.info(
            f"Listing departments ({self.environment})"
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/departments",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            departments = payload.get("department") or []
            if isinstance(departments, dict):
                departments = [departments]
            self.logger.info(
                f"✓ Retrieved {len(departments)} departments"
            )
            return departments
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to list departments",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def list_circ_desks(self, library_code: str) -> List[Dict[str, Any]]:
        """
        List circulation desks configured for a given library.

        Calls ``GET /almaws/v1/conf/libraries/{libraryCode}/circ-desks``
        and unwraps the Alma envelope
        (``{"circ_desk": [...], "total_record_count": N}``) into a flat
        list.

        Args:
            library_code: The Alma library code whose circ desks to list.

        Returns:
            List of circ-desk dicts. Returns an empty list when the
            library has no circ desks configured.

        Raises:
            AlmaValidationError: If ``library_code`` is empty or not a
                string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Admin.list_sets shape (admin.py line 439) +
        # Admin.get_set_info input validation (admin.py line 313).
        code = self._validate_code(library_code, "library_code")
        self.logger.info(
            f"Listing circ desks for library {code} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/libraries/{code}/circ-desks",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            circ_desks = payload.get("circ_desk") or []
            if isinstance(circ_desks, dict):
                circ_desks = [circ_desks]
            self.logger.info(
                f"✓ Retrieved {len(circ_desks)} circ desks for library {code}"
            )
            return circ_desks
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to list circ desks for library {code}",
                extra={
                    "library_code": code,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_circ_desk(
        self, library_code: str, circ_desk_code: str
    ) -> Dict[str, Any]:
        """
        Get configuration details for a single circulation desk.

        Calls
        ``GET /almaws/v1/conf/libraries/{libraryCode}/circ-desks/{circDeskCode}``.

        Args:
            library_code: The Alma library code that owns the circ desk.
            circ_desk_code: The circulation-desk code.

        Returns:
            The circ-desk configuration dict as returned by Alma.

        Raises:
            AlmaValidationError: If either code is empty or not a string.
            AlmaAPIError: If the API request fails (including 404 when
                the circ desk does not exist).
        """
        # Pattern source: Admin.get_set_info shape (admin.py line 313).
        lib_code = self._validate_code(library_code, "library_code")
        desk_code = self._validate_code(circ_desk_code, "circ_desk_code")
        self.logger.info(
            f"Getting circ desk {desk_code} for library {lib_code} "
            f"({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/libraries/{lib_code}/circ-desks/{desk_code}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved circ desk {desk_code} for library {lib_code}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get circ desk {desk_code} for library {lib_code}",
                extra={
                    "library_code": lib_code,
                    "circ_desk_code": desk_code,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise
