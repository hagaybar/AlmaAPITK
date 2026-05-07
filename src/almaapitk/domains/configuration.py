"""
Configuration Domain Class for Alma API
Foundation skeleton for the Configuration API surface (issue #22), extended
with organizational-structure read methods (issue #24), locations CRUD
(issue #25), code-tables list/get/replace (issue #26), and mapping-tables
list/get/replace (issue #27).

Issue #22 established the Configuration domain class with the minimal
plumbing required by sibling tickets — environment introspection and a
smoke-test connection check.

Issue #24 adds five read-only organizational-structure endpoints
(libraries, departments, circulation desks).

Issue #25 adds full CRUD for per-library locations (list / get / create /
update / delete).

Issue #26 adds code-tables coverage: list institution-wide code tables,
fetch a single table (with rows), and replace an entire table via PUT.

Issue #27 adds mapping-tables coverage: list institution-wide mapping
tables, fetch a single table (with rows), and replace an entire table
via PUT. Mapping tables are structurally identical to code tables at the
API surface — they differ only in semantic intent (mapping tables map a
key to a value, code tables enumerate codes). Concrete API methods for
the remaining sibling tickets (calendars, etc.) land in those tickets
and intentionally do NOT live here.
"""
from typing import Any, Dict, List

from almaapitk.client.AlmaAPIClient import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaResponse,
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

    # =========================================================================
    # Locations CRUD (issue #25)
    #
    # Read patterns mirror ``Configuration.list_libraries`` /
    # ``Configuration.get_library`` (just merged in issue #24): single GET,
    # unwrap the Alma envelope, normalise dict→list, propagate AlmaAPIError
    # with full context. Write patterns mirror ``Admin.create_set`` /
    # ``Admin.update_set`` / ``Admin.delete_set`` (admin.py:598+):
    # validate-up-top, log entry, ``self.client.<verb>``, log success-with-id
    # / error-with-context, return ``AlmaResponse`` or re-raise.
    # =========================================================================

    @staticmethod
    def _validate_location_data_for_create(location_data: Any) -> None:
        """Validate the ``location_data`` argument to ``create_location``.

        Alma requires at minimum ``code``, ``name``, and ``type`` on the
        body sent to ``POST /almaws/v1/conf/libraries/{libraryCode}/locations``.
        ``type`` may be either a bare string (``"OPEN"``) or the canonical
        ``{"value": "OPEN"}`` dict shape Alma returns on reads — we accept
        both, mirroring ``Admin._validate_set_data_for_create``.

        Args:
            location_data: Candidate payload for ``create_location``.

        Raises:
            AlmaValidationError: If ``location_data`` is not a non-empty
                dict, or if any of ``code`` / ``name`` / ``type`` is
                missing or empty.
        """
        # Pattern source: Admin._validate_set_data_for_create (admin.py:862).
        if not isinstance(location_data, dict) or not location_data:
            raise AlmaValidationError(
                "location_data must be a non-empty dict"
            )
        code = location_data.get("code")
        if not isinstance(code, str) or not code.strip():
            raise AlmaValidationError(
                "location_data['code'] is required and must be a "
                "non-empty string"
            )
        name = location_data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise AlmaValidationError(
                "location_data['name'] is required and must be a "
                "non-empty string"
            )
        loc_type = location_data.get("type")
        if isinstance(loc_type, dict):
            type_value = loc_type.get("value")
            if not isinstance(type_value, str) or not type_value.strip():
                raise AlmaValidationError(
                    "location_data['type']['value'] is required and must "
                    "be a non-empty string (e.g. 'OPEN' or 'CLOSED_STACK')"
                )
        elif isinstance(loc_type, str):
            if not loc_type.strip():
                raise AlmaValidationError(
                    "location_data['type'] must be a non-empty string"
                )
        else:
            raise AlmaValidationError(
                "location_data['type'] is required (string or "
                "{'value': '<TYPE>'} dict)"
            )

    def list_locations(self, library_code: str) -> List[Dict[str, Any]]:
        """List all locations configured for a given library.

        Calls ``GET /almaws/v1/conf/libraries/{libraryCode}/locations``
        and unwraps the Alma response envelope
        (``{"location": [...], "total_record_count": N}``) into a flat
        list. Locations are scoped to a single library — the same
        ``locationCode`` may be reused by another library — so callers
        must always supply ``library_code``.

        Args:
            library_code: The Alma library code whose locations to list.

        Returns:
            List of location dicts as returned by Alma. Returns an empty
            list when the library has no locations configured (or when
            the response envelope is missing the ``location`` key).

        Raises:
            AlmaValidationError: If ``library_code`` is empty or not a
                string.
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Configuration.list_circ_desks (issue #24, above).
        code = self._validate_code(library_code, "library_code")
        self.logger.info(
            f"Listing locations for library {code} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/libraries/{code}/locations",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            locations = payload.get("location") or []
            if isinstance(locations, dict):
                # Single-record responses can come back as a dict; normalise.
                locations = [locations]
            self.logger.info(
                f"✓ Retrieved {len(locations)} locations for library {code}"
            )
            return locations
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to list locations for library {code}",
                extra={
                    "library_code": code,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_location(
        self, library_code: str, location_code: str
    ) -> Dict[str, Any]:
        """Get configuration details for a single location.

        Calls
        ``GET /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}``.

        Note: location codes are unique **per library**, not globally.
        The same ``location_code`` value may be reused across libraries,
        so callers must always supply both codes.

        Args:
            library_code: The Alma library code that owns the location.
            location_code: The location code (unique within ``library_code``).

        Returns:
            The location configuration dict as returned by Alma.

        Raises:
            AlmaValidationError: If either code is empty or not a string.
            AlmaAPIError: If the API request fails (including 404 when
                the location does not exist within the library).
        """
        # Pattern source: Configuration.get_circ_desk (issue #24, above).
        lib_code = self._validate_code(library_code, "library_code")
        loc_code = self._validate_code(location_code, "location_code")
        self.logger.info(
            f"Getting location {loc_code} for library {lib_code} "
            f"({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/libraries/{lib_code}/locations/{loc_code}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved location {loc_code} for library {lib_code}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get location {loc_code} for library {lib_code}",
                extra={
                    "library_code": lib_code,
                    "location_code": loc_code,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def create_location(
        self, library_code: str, location_data: Dict[str, Any]
    ) -> AlmaResponse:
        """Create a new location within a library.

        Wraps
        ``POST /almaws/v1/conf/libraries/{libraryCode}/locations``. The
        body Alma expects is the location object directly (not wrapped).
        ``location_data`` must include at minimum the ``code``, ``name``,
        and ``type`` fields Alma requires; the rest of the payload
        (description, fulfillment unit, call-number type, etc.) is
        passed through verbatim so callers can build any location Alma
        accepts without waiting for explicit kwargs.

        Args:
            library_code: The Alma library code the new location will
                belong to.
            location_data: Location object payload. Required keys:

                - ``code`` (str): The location code, unique within
                  ``library_code``.
                - ``name`` (str): The location name shown in Alma.
                - ``type`` (str | dict): The location type, e.g.
                  ``"OPEN"`` or ``{"value": "CLOSED_STACK"}``.

        Returns:
            AlmaResponse wrapping the create response. The created
            location body lives on ``response.data``.

        Raises:
            AlmaValidationError: If ``library_code`` is empty / not a
                string, or if ``location_data`` is empty / not a dict /
                missing any required field.
            AlmaAPIError: On API failure (typed subclass when the Alma
                error code or HTTP status maps to one — see
                ``AlmaAPIClient._classify_error``).

        Example:
            >>> response = config.create_location(
            ...     "MAIN",
            ...     {
            ...         "code": "STACKS",
            ...         "name": "Main Stacks",
            ...         "type": {"value": "OPEN"},
            ...     },
            ... )
            >>> created_code = response.data.get("code")
        """
        # Pattern source: Admin.create_set (admin.py:598).
        lib_code = self._validate_code(library_code, "library_code")
        self._validate_location_data_for_create(location_data)
        location_code = location_data.get("code")
        location_name = location_data.get("name")

        # ``type`` may be either a bare string or the canonical
        # ``{"value": "..."}`` dict shape -- normalise here for the log
        # record only; the body sent to Alma is forwarded verbatim.
        raw_type = location_data.get("type")
        type_value = (
            raw_type.get("value") if isinstance(raw_type, dict) else raw_type
        )

        self.logger.info(
            f"Creating location: {location_code} in library {lib_code}",
            library_code=lib_code,
            location_code=location_code,
            location_name=location_name,
            location_type=type_value,
        )

        try:
            response = self.client.post(
                f"almaws/v1/conf/libraries/{lib_code}/locations",
                data=location_data,
            )
            created_code = None
            try:
                created_code = response.data.get("code")
            except (ValueError, AttributeError):
                # Body may not be JSON / dict; the response itself is
                # still a valid AlmaResponse and we should hand it back.
                created_code = None

            if created_code:
                self.logger.info(
                    f"✓ Created location: {created_code} in library {lib_code}",
                    library_code=lib_code,
                    location_code=created_code,
                )
            else:
                self.logger.info(
                    f"✓ Created location in library {lib_code}",
                    library_code=lib_code,
                )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to create location {location_code} in library "
                f"{lib_code}",
                library_code=lib_code,
                location_code=location_code,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    def update_location(
        self,
        library_code: str,
        location_code: str,
        location_data: Dict[str, Any],
    ) -> AlmaResponse:
        """Update an existing location's metadata.

        Wraps
        ``PUT /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}``.
        Alma expects a complete location object (see ``get_location`` for
        the shape Alma returns); callers typically read the current
        location, mutate the fields they want to change, and pass the
        whole dict here.

        Args:
            library_code: The Alma library code that owns the location.
            location_code: The location code to update.
            location_data: Full location object payload. Must be a
                non-empty dict.

        Returns:
            AlmaResponse wrapping the updated location object.

        Raises:
            AlmaValidationError: If either code is empty / not a string,
                or ``location_data`` is empty / not a dict.
            AlmaAPIError: On API failure.

        Example:
            >>> info = config.get_location("MAIN", "STACKS")
            >>> info["name"] = "Main Stacks (renamed)"
            >>> response = config.update_location("MAIN", "STACKS", info)
        """
        # Pattern source: Admin.update_set (admin.py:697).
        lib_code = self._validate_code(library_code, "library_code")
        loc_code = self._validate_code(location_code, "location_code")
        if not isinstance(location_data, dict) or not location_data:
            raise AlmaValidationError(
                "location_data must be a non-empty dict"
            )

        self.logger.info(
            f"Updating location: {loc_code} in library {lib_code}",
            library_code=lib_code,
            location_code=loc_code,
            location_name=location_data.get("name"),
        )

        try:
            response = self.client.put(
                f"almaws/v1/conf/libraries/{lib_code}/locations/{loc_code}",
                data=location_data,
            )
            self.logger.info(
                f"✓ Updated location: {loc_code} in library {lib_code}",
                library_code=lib_code,
                location_code=loc_code,
            )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to update location {loc_code} in library "
                f"{lib_code}",
                library_code=lib_code,
                location_code=loc_code,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    def delete_location(
        self, library_code: str, location_code: str
    ) -> AlmaResponse:
        """Delete a location.

        Wraps
        ``DELETE /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}``.

        Failure mode: Alma rejects the delete with a typed 4xx error
        when the location still has linked items (or holdings). This
        method does NOT swallow that error — the underlying
        ``AlmaAPIError`` propagates verbatim with its ``alma_code``,
        ``tracking_id``, and message intact so callers can surface
        Alma's own diagnostic to the operator.

        Args:
            library_code: The Alma library code that owns the location.
            location_code: The location code to delete.

        Returns:
            AlmaResponse wrapping the delete response. Alma typically
            returns an empty body on a successful delete.

        Raises:
            AlmaValidationError: If either code is empty / not a string.
            AlmaAPIError: On API failure (e.g. when the location has
                linked items the API surface refuses to orphan).
        """
        # Pattern source: Admin.delete_set (admin.py:756).
        lib_code = self._validate_code(library_code, "library_code")
        loc_code = self._validate_code(location_code, "location_code")

        self.logger.info(
            f"Deleting location: {loc_code} in library {lib_code}",
            library_code=lib_code,
            location_code=loc_code,
        )

        try:
            response = self.client.delete(
                f"almaws/v1/conf/libraries/{lib_code}/locations/{loc_code}"
            )
            self.logger.info(
                f"✓ Deleted location: {loc_code} in library {lib_code}",
                library_code=lib_code,
                location_code=loc_code,
            )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to delete location {loc_code} in library "
                f"{lib_code}",
                library_code=lib_code,
                location_code=loc_code,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    # =========================================================================
    # Code tables (issue #26)
    #
    # Read methods mirror ``Configuration.list_libraries`` /
    # ``Configuration.get_library`` (issue #24): single GET, unwrap the Alma
    # envelope (``{"code_table": [...], "total_record_count": N}`` for the
    # collection endpoint), normalise dict→list, propagate AlmaAPIError with
    # full context. The PUT mirrors ``Configuration.update_location``
    # (issue #25): validate-up-top, log entry, ``self.client.put``, log
    # success-with-name / error-with-context, return ``AlmaResponse`` or
    # re-raise. The collection endpoint takes NO ``scope`` parameter — the
    # Alma docs do not advertise one and an audit flagged it as
    # undocumented; do not add it here.
    # =========================================================================

    def list_code_tables(self) -> List[Dict[str, Any]]:
        """List all code tables configured in the Alma institution.

        Calls ``GET /almaws/v1/conf/code-tables`` and unwraps the Alma
        response envelope (``{"code_table": [...], "total_record_count": N}``)
        into a flat list. The endpoint takes no ``scope`` filter — the
        Alma documentation does not advertise one and an audit flagged
        it as undocumented, so this method intentionally exposes no
        filter parameters.

        Returns:
            List of code-table summary dicts (typically containing
            ``name``, ``description``, ``sub_system``, etc.). Returns an
            empty list when the institution has no code tables (or when
            the response envelope is missing the ``code_table`` key).

        Raises:
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Configuration.list_libraries (issue #24, above).
        self.logger.info(
            f"Listing code tables ({self.environment})"
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/code-tables",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            code_tables = payload.get("code_table") or []
            if isinstance(code_tables, dict):
                # Single-record responses can come back as a dict; normalise.
                code_tables = [code_tables]
            self.logger.info(
                f"✓ Retrieved {len(code_tables)} code tables"
            )
            return code_tables
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to list code tables",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_code_table(self, code_table_name: str) -> Dict[str, Any]:
        """Get a single code table including all of its rows.

        Calls ``GET /almaws/v1/conf/code-tables/{codeTableName}``. The
        full code-table object is returned unwrapped — including the
        ``row`` collection that holds the table's individual entries —
        so callers can mutate rows in place and pass the dict back to
        :meth:`update_code_table`.

        Args:
            code_table_name: The Alma code-table name (e.g.
                ``"AcqInvoiceLineType"``).

        Returns:
            The full code-table object as returned by Alma. Includes
            metadata (``name``, ``description``, ``sub_system``, etc.)
            and the ``row`` array of entries.

        Raises:
            AlmaValidationError: If ``code_table_name`` is empty or not
                a string.
            AlmaAPIError: If the API request fails (including 400 with
                Alma error code ``90101`` "Table does not exist." for
                an unknown table name).
        """
        # Pattern source: Configuration.get_library (issue #24, above).
        name = self._validate_code(code_table_name, "code_table_name")
        self.logger.info(
            f"Getting code table: {name} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/code-tables/{name}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved code table {name}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get code table {name}",
                extra={
                    "code_table_name": name,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def update_code_table(
        self, code_table_name: str, code_table_data: Dict[str, Any]
    ) -> AlmaResponse:
        """Replace an entire code table.

        Wraps ``PUT /almaws/v1/conf/code-tables/{codeTableName}``. **The
        PUT replaces the entire table — it is NOT a partial update.**
        Alma requires the complete code-table object on the wire,
        including every row that should remain in the table. Callers
        typically read the table with :meth:`get_code_table`, mutate
        the dict (add / remove / edit ``row`` entries), then pass the
        whole thing back here. Rows omitted from the request body are
        dropped from the table.

        Args:
            code_table_name: The Alma code-table name (e.g.
                ``"AcqInvoiceLineType"``).
            code_table_data: Full code-table object payload. Must be a
                non-empty dict.

        Returns:
            AlmaResponse wrapping the updated code-table object.

        Raises:
            AlmaValidationError: If ``code_table_name`` is empty / not a
                string, or ``code_table_data`` is empty / not a dict.
            AlmaAPIError: On API failure. Notable Alma error codes for
                this endpoint include ``90100`` ("Code table name is
                empty."), ``90101`` ("Table does not exist."),
                ``90102`` ("Requested table is hidden."), ``90121``
                ("Requested table scope is not legal."), ``90122``
                ("Multiple default codes."), and ``90123`` ("Requested
                table is not customizable").

        Example:
            >>> table = config.get_code_table("AcqInvoiceLineType")
            >>> # Mutate rows in place — e.g. flip a row's enabled flag.
            >>> for row in table.get("row", []):
            ...     if row.get("code") == "REGULAR":
            ...         row["enabled"] = {"value": "false"}
            >>> response = config.update_code_table(
            ...     "AcqInvoiceLineType", table
            ... )
        """
        # Pattern source: Configuration.update_location (issue #25, above).
        name = self._validate_code(code_table_name, "code_table_name")
        if not isinstance(code_table_data, dict) or not code_table_data:
            raise AlmaValidationError(
                "code_table_data must be a non-empty dict"
            )

        self.logger.info(
            f"Updating code table: {name}",
            code_table_name=name,
        )

        try:
            response = self.client.put(
                f"almaws/v1/conf/code-tables/{name}",
                data=code_table_data,
            )
            self.logger.info(
                f"✓ Updated code table: {name}",
                code_table_name=name,
            )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to update code table {name}",
                code_table_name=name,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    # =========================================================================
    # Mapping tables (issue #27)
    #
    # Identical shape to the code-tables block above (issue #26) — the Alma
    # API surface is structurally the same; mapping tables and code tables
    # differ only in semantic intent (mapping tables map a key to a value,
    # code tables enumerate codes). The collection endpoint takes NO ``scope``
    # parameter; same audit guidance as #26 applies — do not add one.
    # =========================================================================

    def list_mapping_tables(self) -> List[Dict[str, Any]]:
        """List all mapping tables configured in the Alma institution.

        Calls ``GET /almaws/v1/conf/mapping-tables`` and unwraps the Alma
        response envelope
        (``{"mapping_table": [...], "total_record_count": N}``) into a
        flat list. The endpoint takes no ``scope`` filter — mirroring
        :meth:`list_code_tables`, this method intentionally exposes no
        filter parameters.

        Returns:
            List of mapping-table summary dicts (typically containing
            ``name``, ``description``, ``sub_system``, etc.). Returns an
            empty list when the institution has no mapping tables (or
            when the response envelope is missing the ``mapping_table``
            key).

        Raises:
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Configuration.list_code_tables (issue #26, above).
        self.logger.info(
            f"Listing mapping tables ({self.environment})"
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/mapping-tables",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            mapping_tables = payload.get("mapping_table") or []
            if isinstance(mapping_tables, dict):
                # Single-record responses can come back as a dict; normalise.
                mapping_tables = [mapping_tables]
            self.logger.info(
                f"✓ Retrieved {len(mapping_tables)} mapping tables"
            )
            return mapping_tables
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to list mapping tables",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_mapping_table(self, mapping_table_name: str) -> Dict[str, Any]:
        """Get a single mapping table including all of its rows.

        Calls ``GET /almaws/v1/conf/mapping-tables/{mappingTableName}``.
        The full mapping-table object is returned unwrapped — including
        the ``row`` collection that holds the table's individual entries
        — so callers can mutate rows in place and pass the dict back to
        :meth:`update_mapping_table`.

        Args:
            mapping_table_name: The Alma mapping-table name.

        Returns:
            The full mapping-table object as returned by Alma. Includes
            metadata (``name``, ``description``, ``sub_system``, etc.)
            and the ``row`` array of entries.

        Raises:
            AlmaValidationError: If ``mapping_table_name`` is empty or
                not a string.
            AlmaAPIError: If the API request fails (including 400 with
                Alma error code ``90101`` "Table does not exist." for
                an unknown table name).
        """
        # Pattern source: Configuration.get_code_table (issue #26, above).
        name = self._validate_code(mapping_table_name, "mapping_table_name")
        self.logger.info(
            f"Getting mapping table: {name} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/mapping-tables/{name}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved mapping table {name}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get mapping table {name}",
                extra={
                    "mapping_table_name": name,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def update_mapping_table(
        self,
        mapping_table_name: str,
        mapping_table_data: Dict[str, Any],
    ) -> AlmaResponse:
        """Replace an entire mapping table.

        Wraps ``PUT /almaws/v1/conf/mapping-tables/{mappingTableName}``.
        **The PUT replaces the entire table — it is NOT a partial
        update.** Alma requires the complete mapping-table object on the
        wire, including every row that should remain in the table.
        Mapping tables can be large; callers typically read the table
        with :meth:`get_mapping_table`, mutate the dict (add / remove /
        edit ``row`` entries), then pass the whole thing back here. Rows
        omitted from the request body are dropped from the table.

        Args:
            mapping_table_name: The Alma mapping-table name.
            mapping_table_data: Full mapping-table object payload. Must
                be a non-empty dict.

        Returns:
            AlmaResponse wrapping the updated mapping-table object.

        Raises:
            AlmaValidationError: If ``mapping_table_name`` is empty / not
                a string, or ``mapping_table_data`` is empty / not a
                dict.
            AlmaAPIError: On API failure. Notable Alma error codes for
                this endpoint include ``90101`` ("Table does not
                exist."), ``90102`` ("Requested table is hidden."),
                ``90121`` / ``90127`` ("Requested table scope is not
                legal."), ``90123`` ("Requested table is not
                customizable"), and ``90126`` ("Mapping table name is
                empty.").

        Example:
            >>> table = config.get_mapping_table("RecallDueDate")
            >>> # Mutate rows in place — e.g. flip a row's enabled flag.
            >>> for row in table.get("row", []):
            ...     if row.get("column0") == "STAFF":
            ...         row["enabled"] = {"value": "false"}
            >>> response = config.update_mapping_table(
            ...     "RecallDueDate", table
            ... )
        """
        # Pattern source: Configuration.update_code_table (issue #26, above).
        name = self._validate_code(mapping_table_name, "mapping_table_name")
        if not isinstance(mapping_table_data, dict) or not mapping_table_data:
            raise AlmaValidationError(
                "mapping_table_data must be a non-empty dict"
            )

        self.logger.info(
            f"Updating mapping table: {name}",
            mapping_table_name=name,
        )

        try:
            response = self.client.put(
                f"almaws/v1/conf/mapping-tables/{name}",
                data=mapping_table_data,
            )
            self.logger.info(
                f"✓ Updated mapping table: {name}",
                mapping_table_name=name,
            )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to update mapping table {name}",
                mapping_table_name=name,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise
