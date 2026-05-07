"""
Configuration Domain Class for Alma API
Foundation skeleton for the Configuration API surface (issue #22), extended
with organizational-structure read methods (issue #24), locations CRUD
(issue #25), code-tables list/get/replace (issue #26), mapping-tables
list/get/replace (issue #27), deposit / metadata-import profile read
methods (issue #30), letters + printers read coverage plus letter
update (issue #33), and the workflow-runner / fee-transactions /
general-configuration utility endpoints (issue #35).

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
key to a value, code tables enumerate codes).

Issue #30 adds read-only coverage for deposit profiles and metadata
import (md-import) profiles: list / get on each. All four endpoints are
plain GETs and mirror the libraries read shape from issue #24.

Issue #33 adds letters list/get/update plus printers list/get. The PUT
on /almaws/v1/conf/letters/{letterCode} replaces the entire letter
template (subject + XSL body) — Alma does not support partial updates.

Issue #35 adds the workflow runner (POST /conf/workflows/{workflow_id})
and two utility GETs: fee-transactions report
(/conf/utilities/fee-transactions) and general institutional
configuration (/conf/general). The workflow runner has real side
effects — callers must restrict it to known-safe workflow ids.

Concrete API methods for the remaining sibling tickets (calendars, etc.)
land in those tickets and intentionally do NOT live here.
"""
from typing import Any, Dict, List, Optional

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
            and a top-level ``row`` array of entries.

            **Response-shape note:** the entries live at the top-level
            ``row`` key (singular), NOT wrapped in ``rows.row``. Access
            via ``table["row"]``. This differs from some other Alma
            list endpoints (where the wrapper is ``{"rows": {"row":
            [...]}}``) — verified live against SANDBOX 2026-05-07.

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
            and a top-level ``row`` array of entries.

            **Response-shape note:** the entries live at the top-level
            ``row`` key (singular), NOT wrapped in ``rows.row``. Access
            via ``table["row"]``. This mirrors :meth:`get_code_table`
            and differs from some other Alma list endpoints whose
            wrapper is ``{"rows": {"row": [...]}}``.

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

    # =========================================================================
    # Deposit profiles + metadata-import profiles (issue #30)
    #
    # All four endpoints are plain GETs. The list shapes mirror
    # ``Configuration.list_libraries`` (issue #24): single GET, unwrap the
    # Alma envelope, normalise dict→list, propagate AlmaAPIError with full
    # context. The get shapes mirror ``Configuration.get_library``
    # (issue #24): validate the id, GET, return the unwrapped dict, propagate
    # AlmaAPIError. Issue #30 is read-only — no mutators belong here.
    # =========================================================================

    def list_deposit_profiles(self) -> List[Dict[str, Any]]:
        """List all deposit profiles configured in the Alma institution.

        Calls ``GET /almaws/v1/conf/deposit-profiles`` and unwraps the
        Alma response envelope
        (``{"deposit_profile": [...], "total_record_count": N}``) into a
        flat list. Deposit profiles are typically few — a single call
        with a generous page size is sufficient.

        Returns:
            List of deposit-profile dicts as returned by Alma. Returns an
            empty list when the institution has no deposit profiles
            configured (or when the response envelope is missing the
            ``deposit_profile`` key).

        Raises:
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Configuration.list_libraries (issue #24, above).
        self.logger.info(
            f"Listing deposit profiles ({self.environment})"
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/deposit-profiles",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            deposit_profiles = payload.get("deposit_profile") or []
            if isinstance(deposit_profiles, dict):
                # Single-record responses can come back as a dict; normalise.
                deposit_profiles = [deposit_profiles]
            self.logger.info(
                f"✓ Retrieved {len(deposit_profiles)} deposit profiles"
            )
            return deposit_profiles
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to list deposit profiles",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_deposit_profile(
        self, deposit_profile_id: str
    ) -> Dict[str, Any]:
        """Get configuration details for a single deposit profile.

        Calls ``GET /almaws/v1/conf/deposit-profiles/{deposit_profile_id}``.

        Args:
            deposit_profile_id: The Alma deposit-profile identifier.

        Returns:
            The deposit-profile configuration dict as returned by Alma.

        Raises:
            AlmaValidationError: If ``deposit_profile_id`` is empty or
                not a string.
            AlmaAPIError: If the API request fails (including 4xx when
                the profile id does not exist).
        """
        # Pattern source: Configuration.get_library (issue #24, above).
        profile_id = self._validate_code(
            deposit_profile_id, "deposit_profile_id"
        )
        self.logger.info(
            f"Getting deposit profile: {profile_id} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/deposit-profiles/{profile_id}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved deposit profile {profile_id}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get deposit profile {profile_id}",
                extra={
                    "deposit_profile_id": profile_id,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def list_import_profiles(self) -> List[Dict[str, Any]]:
        """List all metadata-import profiles configured in the institution.

        Calls ``GET /almaws/v1/conf/md-import-profiles`` and unwraps the
        Alma response envelope
        (``{"import_profile": [...], "total_record_count": N}``) into a
        flat list. The Alma developer-network docs use ``import_profile``
        as the singular envelope key for this endpoint; the older
        ``md_import_profile`` form has not been observed on the wire.

        Returns:
            List of import-profile dicts as returned by Alma. Returns an
            empty list when the institution has no import profiles
            configured (or when the response envelope is missing the
            ``import_profile`` key).

        Raises:
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Configuration.list_libraries (issue #24, above).
        self.logger.info(
            f"Listing import profiles ({self.environment})"
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/md-import-profiles",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            import_profiles = payload.get("import_profile") or []
            if isinstance(import_profiles, dict):
                # Single-record responses can come back as a dict; normalise.
                import_profiles = [import_profiles]
            self.logger.info(
                f"✓ Retrieved {len(import_profiles)} import profiles"
            )
            return import_profiles
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to list import profiles",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_import_profile(self, profile_id: str) -> Dict[str, Any]:
        """Get configuration details for a single metadata-import profile.

        Calls ``GET /almaws/v1/conf/md-import-profiles/{profile_id}``.

        Args:
            profile_id: The Alma metadata-import-profile identifier.

        Returns:
            The import-profile configuration dict as returned by Alma.

        Raises:
            AlmaValidationError: If ``profile_id`` is empty or not a
                string.
            AlmaAPIError: If the API request fails. Notable Alma error
                code for this endpoint: ``401871`` ("Failed to find the
                Profile ID.") for an unknown profile id.
        """
        # Pattern source: Configuration.get_library (issue #24, above).
        pid = self._validate_code(profile_id, "profile_id")
        self.logger.info(
            f"Getting import profile: {pid} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/md-import-profiles/{pid}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved import profile {pid}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get import profile {pid}",
                extra={
                    "profile_id": pid,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    # =========================================================================
    # Letters + printers (issue #33)
    #
    # Read shapes mirror ``Configuration.list_libraries`` /
    # ``Configuration.get_library`` (issue #24): single GET, unwrap the Alma
    # envelope, normalise dict→list for collections, propagate AlmaAPIError
    # with full context. The PUT on letters mirrors
    # ``Configuration.update_code_table`` / ``Configuration.update_mapping_table``
    # (issues #26 / #27): validate-up-top, log entry, ``self.client.put``,
    # log success-with-name / error-with-context, return ``AlmaResponse`` or
    # re-raise. The Alma PUT on /letters/{letterCode} replaces the entire
    # letter template (subject + XSL body) — partial updates are not
    # supported by the API surface (60343 "The update failed.",
    # 40166411 "Letter code or other parameter is not valid.").
    # =========================================================================

    def list_letters(self) -> List[Dict[str, Any]]:
        """List all letters configured in the Alma institution.

        Calls ``GET /almaws/v1/conf/letters`` and unwraps the Alma
        response envelope (``{"letter": [...], "total_record_count": N}``)
        into a flat list. Letters define the templates Alma uses to
        render notifications (overdue, hold-pickup, fulfillment, etc.) —
        the catalogue is small (a few hundred at most) so a single call
        with a generous page size is sufficient.

        Returns:
            List of letter dicts as returned by Alma. Returns an empty
            list when the institution has no letters configured (or when
            the response envelope is missing the ``letter`` key).

        Raises:
            AlmaAPIError: If the API request fails. Notable Alma error
                code for this endpoint: ``60344`` ("Problem retrieving
                letter data.").
        """
        # Pattern source: Configuration.list_libraries (issue #24, above).
        self.logger.info(
            f"Listing letters ({self.environment})"
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/letters",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            letters = payload.get("letter") or []
            if isinstance(letters, dict):
                # Single-record responses can come back as a dict; normalise.
                letters = [letters]
            self.logger.info(
                f"✓ Retrieved {len(letters)} letters"
            )
            return letters
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to list letters",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_letter(self, letter_code: str) -> Dict[str, Any]:
        """Get a single letter's full configuration including its template.

        Calls ``GET /almaws/v1/conf/letters/{letterCode}``. The full
        letter object is returned unwrapped — including ``subject``,
        ``body``, ``description``, ``enabled``, ``letter_name``, and the
        ``letter_template_xsl`` payload that holds the XSL template.
        Callers typically read the letter, mutate the dict (edit
        subject / template), and pass the whole thing back to
        :meth:`update_letter`.

        Args:
            letter_code: The Alma letter code (e.g. ``"OverdueAndLostLoanLetter"``).

        Returns:
            The full letter object as returned by Alma. The response is
            the raw Alma payload — sub-objects like ``subject``,
            ``body``, ``description``, ``enabled``, ``letter_name``, and
            ``letter_template_xsl`` are surfaced verbatim.

        Raises:
            AlmaValidationError: If ``letter_code`` is empty or not a
                string.
            AlmaAPIError: If the API request fails. Notable Alma error
                codes for this endpoint: ``60344`` ("Problem retrieving
                letter data.") and ``40166411`` ("Letter code is not
                valid.") for an unknown letter code.
        """
        # Pattern source: Configuration.get_library (issue #24, above).
        code = self._validate_code(letter_code, "letter_code")
        self.logger.info(
            f"Getting letter: {code} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/letters/{code}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved letter {code}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get letter {code}",
                extra={
                    "letter_code": code,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def update_letter(
        self, letter_code: str, letter_data: Dict[str, Any]
    ) -> AlmaResponse:
        """Replace an entire letter template.

        .. warning::
            **Known limitation as of 2026-05-07:** the live Alma
            letters PUT endpoint requires an XML request body and
            rejects JSON with HTTP 400 + Alma error code ``60105``
            ("JSON is not supported for this API."). This method
            sends JSON like the rest of the toolkit, so calls against
            live Alma will fail. The implementation is correct for a
            JSON-accepting endpoint and is exercised by the unit-test
            suite (mocked HTTP); XML body support is tracked as a
            follow-up issue. Until that ships, treat this method as
            non-functional against live Alma.

        Wraps ``PUT /almaws/v1/conf/letters/{letterCode}``. **The PUT
        replaces the entire letter — it is NOT a partial update.** Alma
        requires the complete letter object on the wire (subject, body,
        XSL template, enabled flag, etc.). Callers typically read the
        letter with :meth:`get_letter`, mutate the dict (edit the
        subject text or the ``letter_template_xsl`` body), then pass
        the whole thing back here. Fields omitted from the request body
        are dropped from the letter.

        Args:
            letter_code: The Alma letter code (e.g.
                ``"OverdueAndLostLoanLetter"``).
            letter_data: Full letter object payload. Must be a non-empty
                dict.

        Returns:
            AlmaResponse wrapping the updated letter object.

        Raises:
            AlmaValidationError: If ``letter_code`` is empty / not a
                string, or ``letter_data`` is empty / not a dict.
            AlmaAPIError: On API failure. Notable Alma error codes for
                this endpoint include ``60105`` ("JSON is not supported
                for this API." — letters require XML), ``60343`` ("The
                update failed."), ``60344`` ("Problem retrieving letter
                data."), and ``40166411`` ("Letter code or other
                parameter is not valid.").

        Example:
            >>> letter = config.get_letter("OverdueAndLostLoanLetter")
            >>> letter["subject"] = "Overdue notice — please return"
            >>> response = config.update_letter(
            ...     "OverdueAndLostLoanLetter", letter
            ... )
        """
        # Pattern source: Configuration.update_code_table (issue #26, above).
        code = self._validate_code(letter_code, "letter_code")
        if not isinstance(letter_data, dict) or not letter_data:
            raise AlmaValidationError(
                "letter_data must be a non-empty dict"
            )

        self.logger.info(
            f"Updating letter: {code}",
            letter_code=code,
        )

        try:
            response = self.client.put(
                f"almaws/v1/conf/letters/{code}",
                data=letter_data,
            )
            self.logger.info(
                f"✓ Updated letter: {code}",
                letter_code=code,
            )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to update letter {code}",
                letter_code=code,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    def list_printers(self) -> List[Dict[str, Any]]:
        """List all printers configured in the Alma institution.

        Calls ``GET /almaws/v1/conf/printers`` and unwraps the Alma
        response envelope (``{"printer": [...], "total_record_count": N}``)
        into a flat list. The printer catalogue is institution-wide and
        typically small — a single call with a generous page size is
        sufficient.

        Returns:
            List of printer dicts as returned by Alma. Returns an empty
            list when the institution has no printers configured (or
            when the response envelope is missing the ``printer`` key).

        Raises:
            AlmaAPIError: If the API request fails. Notable Alma error
                codes for this endpoint: ``402469`` ("The library code
                is not valid.") and ``40166410`` ("Invalid parameter.").
        """
        # Pattern source: Configuration.list_libraries (issue #24, above).
        self.logger.info(
            f"Listing printers ({self.environment})"
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/printers",
                params={"limit": "100", "offset": "0"},
            )
            payload = response.json() or {}
            printers = payload.get("printer") or []
            if isinstance(printers, dict):
                # Single-record responses can come back as a dict; normalise.
                printers = [printers]
            self.logger.info(
                f"✓ Retrieved {len(printers)} printers"
            )
            return printers
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to list printers",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_printer(self, printer_id: str) -> Dict[str, Any]:
        """Get configuration details for a single printer.

        Calls ``GET /almaws/v1/conf/printers/{printer_id}``.

        Args:
            printer_id: The Alma printer identifier.

        Returns:
            The printer configuration dict as returned by Alma.

        Raises:
            AlmaValidationError: If ``printer_id`` is empty or not a
                string.
            AlmaAPIError: If the API request fails. Notable Alma error
                code for this endpoint: ``402899`` ("Invalid Printer
                ID.") for an unknown printer id.
        """
        # Pattern source: Configuration.get_library (issue #24, above).
        pid = self._validate_code(printer_id, "printer_id")
        self.logger.info(
            f"Getting printer: {pid} ({self.environment})"
        )
        try:
            response = self.client.get(
                f"almaws/v1/conf/printers/{pid}"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Retrieved printer {pid}"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to get printer {pid}",
                extra={
                    "printer_id": pid,
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    # =========================================================================
    # Workflows runner + utilities (issue #35)
    #
    # Three small endpoints round out the Configuration grab-bag:
    #
    #   POST /almaws/v1/conf/workflows/{workflow_id}
    #     -- triggers a configured workflow. Side effects depend entirely
    #        on the workflow's configuration; callers must restrict
    #        themselves to known-safe workflow ids.
    #
    #   GET  /almaws/v1/conf/utilities/fee-transactions
    #     -- fee-transactions report. Filter set is operator-supplied
    #        (status, library, from_date, to_date, ...). Envelope key is
    #        ``fee_transaction``.
    #
    #   GET  /almaws/v1/conf/general
    #     -- general institutional configuration. Returned unwrapped.
    #
    # Pattern sources called out per-method below.
    # =========================================================================

    def run_workflow(
        self,
        workflow_id: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a configured Alma workflow.

        Wraps ``POST /almaws/v1/conf/workflows/{workflow_id}``.

        **WARNING:** This method actually triggers an Alma workflow.
        Side effects depend entirely on the workflow's configuration —
        a workflow can mutate records, send notifications, kick off
        long-running jobs, etc. Test against a known-safe ``workflow_id``
        only; never bind this method to untrusted input.

        Args:
            workflow_id: The Alma workflow identifier to execute.
            parameters: Optional workflow-specific parameter payload.
                When provided, sent as the JSON request body. When
                ``None``, no body is sent — Alma accepts a parameterless
                workflow trigger.

        Returns:
            The parsed response dict from Alma. Alma typically returns a
            workflow-instance object containing at least an instance id
            and a status code; the exact shape varies per workflow.

        Raises:
            AlmaValidationError: If ``workflow_id`` is empty or not a
                string.
            AlmaAPIError: On API failure. Notable Alma error codes for
                this endpoint include ``450001`` ("Workflow not
                found."), ``450002`` ("Workflow inactive."), ``450003``
                ("Workflow missing trigger node."), and ``450004``
                ("Workflow missing trigger configuration.").

        Example:
            >>> result = config.run_workflow(
            ...     "MY_SAFE_TEST_WORKFLOW",
            ...     {"input_param": "value"},
            ... )
            >>> instance_id = result.get("id")
        """
        # Pattern source: Configuration.update_letter (issue #33, above) for
        # the validate -> log entry -> client.<verb> -> log success -> on
        # AlmaAPIError, log + re-raise shape; Configuration.get_library
        # (issue #24) for unwrapping the response body via response.json().
        wf_id = self._validate_code(workflow_id, "workflow_id")

        self.logger.info(
            f"Running workflow: {wf_id} ({self.environment})",
            workflow_id=wf_id,
            has_parameters=parameters is not None,
        )

        try:
            response = self.client.post(
                f"almaws/v1/conf/workflows/{wf_id}",
                data=parameters,
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                f"✓ Ran workflow: {wf_id}",
                workflow_id=wf_id,
            )
            return data

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to run workflow {wf_id}",
                workflow_id=wf_id,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    def get_fee_transactions_report(
        self, **filters: Any
    ) -> List[Dict[str, Any]]:
        """Fetch the Alma fee-transactions report.

        Wraps ``GET /almaws/v1/conf/utilities/fee-transactions`` and
        unwraps the Alma response envelope
        (``{"fee_transaction": [...], "total_record_count": N}``) into a
        flat list. The endpoint accepts a flexible set of filters
        (``status``, ``library``, ``from_date``, ``to_date``,
        ``transaction_type``, etc.); rather than enumerate them in the
        signature this method forwards arbitrary keyword args verbatim
        as query parameters so callers can drive any filter Alma
        accepts.

        Args:
            **filters: Arbitrary query-parameter filters forwarded to
                Alma. Common filters per the Alma docs:

                - ``status`` (str): transaction status filter.
                - ``library`` (str): library code to scope the report.
                - ``from_date`` (str): inclusive lower bound (YYYY-MM-DD).
                - ``to_date`` (str): inclusive upper bound (YYYY-MM-DD).
                - ``transaction_type`` (str): transaction-type filter.

        Returns:
            List of fee-transaction dicts as returned by Alma. Returns
            an empty list when no matching transactions are found (or
            when the response envelope is missing the
            ``fee_transaction`` key).

        Raises:
            AlmaAPIError: If the API request fails. Notable Alma error
                codes for this endpoint include ``401652`` ("An error
                has occurred in setting circ library or circ desk."),
                ``40166410`` ("An error has occurred in setting from
                and/or to dates."), and ``40166413`` ("An error has
                occurred in setting transaction type.").

        Example:
            >>> txs = config.get_fee_transactions_report(
            ...     library="MAIN",
            ...     from_date="2026-01-01",
            ...     to_date="2026-01-31",
            ... )
        """
        # Pattern source: Configuration.list_libraries (issue #24, above) for
        # the GET-then-unwrap-envelope-into-list shape; the **filters
        # forwarding mirrors Acquisitions.search_invoices kwargs handling.
        self.logger.info(
            f"Fetching fee-transactions report ({self.environment})",
            filters=dict(filters) if filters else None,
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/utilities/fee-transactions",
                params=dict(filters) if filters else None,
            )
            payload = response.json() or {}
            transactions = payload.get("fee_transaction") or []
            if isinstance(transactions, dict):
                # Single-record responses can come back as a dict; normalise.
                transactions = [transactions]
            self.logger.info(
                f"✓ Retrieved {len(transactions)} fee transactions"
            )
            return transactions
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to fetch fee-transactions report",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise

    def get_general_configuration(self) -> Dict[str, Any]:
        """Get the institution's general configuration.

        Calls ``GET /almaws/v1/conf/general`` and returns the unwrapped
        institutional-configuration dict (Alma surfaces fields like
        ``institution``, ``default_language``, ``default_currency``,
        ``timezone``, etc. directly at the top level of the response —
        there is no envelope wrapper).

        Returns:
            The general-configuration dict as returned by Alma. Returns
            an empty dict if Alma returns an empty body.

        Raises:
            AlmaAPIError: If the API request fails.
        """
        # Pattern source: Configuration.get_library (issue #24, above) — but
        # without the path-param validation, since this endpoint takes no
        # arguments.
        self.logger.info(
            f"Getting general configuration ({self.environment})"
        )
        try:
            response = self.client.get(
                "almaws/v1/conf/general"
            )
            data: Dict[str, Any] = response.json() or {}
            self.logger.info(
                "✓ Retrieved general configuration"
            )
            return data
        except AlmaAPIError as e:
            self.logger.error(
                "✗ Failed to get general configuration",
                extra={
                    "alma_code": getattr(e, "alma_code", ""),
                    "tracking_id": getattr(e, "tracking_id", None),
                    "status_code": getattr(e, "status_code", None),
                },
            )
            raise
