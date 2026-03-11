"""
Resource Sharing Domain Class for Alma API
Handles resource sharing operations including lending and borrowing requests
using the Alma Partners API.

API Documentation:
https://developers.exlibrisgroup.com/alma/apis/partners/

Key Endpoints:
- POST /almaws/v1/partners/{partner_code}/lending-requests
- GET /almaws/v1/partners/{partner_code}/lending-requests/{request_id}

Schema Reference:
https://developers.exlibrisgroup.com/alma/apis/xsd/rest_user_resource_sharing_request.xsd
"""

from typing import Any, Dict, Optional

from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError, AlmaResponse
from almaapitk.alma_logging import get_logger


class ResourceSharing:
    """
    Domain class for handling Alma Resource Sharing API operations.

    Focuses on lending requests created "for a partner" using Alma's
    Resource Sharing Partners API.

    This class uses the AlmaAPIClient as its foundation for all HTTP operations.

    Attributes:
        client: AlmaAPIClient instance for making HTTP requests
        environment: Current environment (SANDBOX/PRODUCTION)
        logger: Logger instance for this domain
    """

    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the ResourceSharing domain.

        Args:
            client: The AlmaAPIClient instance for making HTTP requests
        """
        self.client = client
        self.environment = client.get_environment()
        self.logger = get_logger('resource_sharing', environment=self.environment)

        self.logger.info(
            "ResourceSharing domain initialized",
            environment=self.environment
        )

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def _validate_lending_request_data(
        self,
        data: Dict[str, Any],
        check_external_id: bool = True
    ) -> None:
        """
        Validate lending request data against mandatory field requirements.

        Validates that all mandatory fields are present and non-empty according
        to the Resource Sharing Request schema requirements.

        Mandatory fields for lending requests:
        - external_id: External identifier (mandatory for creation)
        - owner: Resource sharing library code
        - partner: Partner code
        - format: Request format (physical/digital)
        - citation_type: Resource type (unless mms_id is supplied)
        - title: Resource title (unless mms_id is supplied)

        Args:
            data: Request data dictionary to validate
            check_external_id: Whether to validate external_id (True for creation)

        Raises:
            ValueError: If any mandatory field is missing or invalid

        Examples:
            >>> rs._validate_lending_request_data({
            ...     "external_id": "EXT-001",
            ...     "owner": "MAIN",  # Plain string!
            ...     "partner": {"value": "PARTNER_01"},
            ...     "format": {"value": "PHYSICAL"},
            ...     "citation_type": {"value": "BOOK"},
            ...     "title": "Example Book"
            ... })
            # No exception raised - validation passed
        """
        errors = []

        # Validate external_id (mandatory for creation)
        if check_external_id:
            if not data.get('external_id'):
                errors.append("external_id is mandatory when creating a lending request")

        # Validate owner (mandatory for lending requests)
        # CRITICAL: owner is a PLAIN STRING, not wrapped (discovered 2025-12-24)
        owner = data.get('owner')
        if not owner or not isinstance(owner, str):
            errors.append(
                "owner is mandatory for lending requests "
                "(must be resource sharing library code as plain string). "
                "Example: 'AS1' or 'MAIN'"
            )

        # Validate partner (mandatory for lending requests)
        partner = data.get('partner', {})
        if not partner or not partner.get('value'):
            errors.append(
                "partner is mandatory when creating a lending request "
                "(must be partner code). "
                "Example: {'value': 'PARTNER_01'}"
            )

        # Validate format (mandatory)
        format_field = data.get('format', {})
        if not format_field or not format_field.get('value'):
            errors.append(
                "format is mandatory (e.g., physical/digital; "
                "controlled by RequestFormats code table). "
                "Example: {'value': 'PHYSICAL'}"
            )

        # Check if mms_id is supplied
        mms_id = data.get('mms_id', {}).get('value') if isinstance(data.get('mms_id'), dict) else data.get('mms_id')

        # Validate citation_type (mandatory unless mms_id is supplied)
        if not mms_id:
            citation_type = data.get('citation_type', {})
            if not citation_type or not citation_type.get('value'):
                errors.append(
                    "citation_type is mandatory when creating a lending request "
                    "unless mms_id is supplied (e.g., BOOK/JOURNAL). "
                    "Example: {'value': 'BOOK'}"
                )

            # Validate title (mandatory unless mms_id is supplied)
            if not data.get('title'):
                errors.append(
                    "title is mandatory unless mms_id is supplied. "
                    "Example: 'Introduction to Library Science'"
                )

        if errors:
            error_message = "Validation failed for lending request:\n" + "\n".join(f"  - {err}" for err in errors)
            self.logger.error(
                "Lending request validation failed",
                errors=errors,
                data_keys=list(data.keys())
            )
            raise ValueError(error_message)

        self.logger.debug("Lending request validation passed", data_keys=list(data.keys()))

    # =========================================================================
    # Lending Request Operations
    # =========================================================================

    def create_lending_request(
        self,
        partner_code: str,
        external_id: str,
        owner: str,
        format_type: str,
        title: str,
        citation_type: Optional[str] = None,
        mms_id: Optional[str] = None,
        **optional_fields
    ) -> Dict[str, Any]:
        """
        Create a new lending request for a partner.

        Creates a lending request through the Alma Partners API. This represents
        a request from a partner institution to borrow material from your library.

        API Endpoint:
            POST /almaws/v1/partners/{partner_code}/lending-requests

        Mandatory Parameters:
            partner_code: Partner institution code (URL path parameter)
            external_id: External identifier for the request
            owner: Resource sharing library code (e.g., 'MAIN')
            format_type: Request format - 'PHYSICAL' or 'DIGITAL'
            title: Resource title (required unless mms_id is provided)

        Optional Parameters:
            citation_type: Resource type (e.g., 'BOOK', 'JOURNAL') - required if no mms_id
            mms_id: Alma MMS ID if resource exists in your catalog
            **optional_fields: Additional fields from the schema:
                - author: str
                - isbn: str
                - issn: str
                - publisher: str
                - year: str (publication year, e.g., "2024")
                - edition: str
                - volume: str
                - issue: str
                - pages: str
                - doi: str
                - pmid: str
                - call_number: str
                - oclc_number: str
                - status: Dict[str, str] (e.g., {'value': 'REQUEST_CREATED_LEN'})
                - requested_media: Dict[str, str]
                - preferred_send_method: Dict[str, str]
                - pickup_location: Dict[str, str]
                - last_interest_date: str (ISO format date)
                - level_of_service: Dict[str, str]
                - copyright_status: Dict[str, str]
                - rs_note: List[Dict] (notes array - note: singular field name!)
                - And other fields per schema

        Args:
            partner_code: Partner institution code
            external_id: External identifier for this request
            owner: Resource sharing library code
            format_type: Request format (PHYSICAL/DIGITAL)
            title: Resource title
            citation_type: Resource type (BOOK/JOURNAL/etc.), required if no mms_id
            mms_id: Alma MMS ID if resource is in catalog
            **optional_fields: Additional optional fields

        Returns:
            Created lending request as dictionary with request_id and all fields

        Raises:
            ValueError: If mandatory fields are missing or invalid
            AlmaAPIError: If API request fails

        Examples:
            >>> # Create basic lending request
            >>> rs = ResourceSharing(client)
            >>> request = rs.create_lending_request(
            ...     partner_code="PARTNER_01",
            ...     external_id="EXT-2025-001",
            ...     owner="MAIN",
            ...     format_type="PHYSICAL",
            ...     title="Introduction to Library Science",
            ...     citation_type="BOOK",
            ...     author="Smith, John",
            ...     isbn="978-0-123456-78-9",
            ...     publisher="Academic Press",
            ...     year="2024"
            ... )
            >>> print(request['request_id'])

            >>> # Create request for known catalog item
            >>> request = rs.create_lending_request(
            ...     partner_code="PARTNER_02",
            ...     external_id="EXT-2025-002",
            ...     owner="MAIN",
            ...     format_type="DIGITAL",
            ...     title="Advanced Cataloging",
            ...     mms_id="991234567890123456",
            ...     level_of_service={"value": "Rush"}
            ... )
        """
        self.logger.info(
            "Creating lending request",
            partner_code=partner_code,
            external_id=external_id,
            owner=owner,
            format_type=format_type,
            title=title
        )

        # Build request data structure
        # CRITICAL DISCOVERY (2025-12-24): owner field format differs from schema docs!
        #   - CREATE: Send PLAIN STRING "AS1" (NOT wrapped - API rejects wrapped format)
        #   - RETRIEVE: Returns PLAIN STRING "AS1"
        #   - Schema documentation incorrectly shows wrapped format for creation
        # Other code table fields (partner, format, citation_type) are wrapped as documented.
        request_data = {
            "external_id": external_id,
            "owner": owner,  # Plain string! (API rejects wrapped format)
            "partner": {"value": partner_code},
            "format": {"value": format_type},
            "title": title
        }

        # Add citation_type if provided
        if citation_type:
            request_data["citation_type"] = {"value": citation_type}

        # Add mms_id if provided
        if mms_id:
            request_data["mms_id"] = {"value": mms_id}

        # Add optional fields
        for field_name, field_value in optional_fields.items():
            # Handle fields that should be wrapped in dict with 'value' key
            code_table_fields = [
                'status', 'requested_media', 'preferred_send_method',
                'pickup_location', 'level_of_service', 'copyright_status',
                'requested_language', 'reading_room'
            ]

            if field_name in code_table_fields and isinstance(field_value, str):
                request_data[field_name] = {"value": field_value}
            else:
                request_data[field_name] = field_value

        # Validate request data
        self._validate_lending_request_data(request_data, check_external_id=True)

        # Make API request
        endpoint = f"almaws/v1/partners/{partner_code}/lending-requests"

        try:
            self.logger.debug(
                "Sending POST request to create lending request",
                endpoint=endpoint,
                request_data_keys=list(request_data.keys())
            )

            response = self.client.post(endpoint, data=request_data)

            # Extract response data
            if isinstance(response, AlmaResponse):
                result = response.data
            else:
                result = response

            request_id = result.get('request_id', 'unknown')

            self.logger.info(
                "Lending request created successfully",
                request_id=request_id,
                partner_code=partner_code,
                external_id=external_id
            )

            return result

        except AlmaAPIError as e:
            self.logger.error(
                "Failed to create lending request",
                partner_code=partner_code,
                external_id=external_id,
                error_code=e.status_code,
                error_message=str(e)
            )
            raise

    def get_lending_request(
        self,
        partner_code: str,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve a lending request by ID.

        Fetches complete details of an existing lending request from the
        Alma Partners API.

        API Endpoint:
            GET /almaws/v1/partners/{partner_code}/lending-requests/{request_id}

        Args:
            partner_code: Partner institution code
            request_id: Lending request identifier

        Returns:
            Lending request data as dictionary

        Raises:
            AlmaAPIError: If API request fails or request not found

        Examples:
            >>> rs = ResourceSharing(client)
            >>> request = rs.get_lending_request(
            ...     partner_code="PARTNER_01",
            ...     request_id="12345678"
            ... )
            >>> print(f"Title: {request['title']}")
            >>> print(f"Status: {request['status']['value']}")
            >>> print(f"Format: {request['format']['value']}")
        """
        self.logger.info(
            "Retrieving lending request",
            partner_code=partner_code,
            request_id=request_id
        )

        endpoint = f"almaws/v1/partners/{partner_code}/lending-requests/{request_id}"

        try:
            self.logger.debug(
                "Sending GET request to retrieve lending request",
                endpoint=endpoint
            )

            response = self.client.get(endpoint)

            # Extract response data
            if isinstance(response, AlmaResponse):
                result = response.data
            else:
                result = response

            self.logger.info(
                "Lending request retrieved successfully",
                request_id=result.get('request_id', 'unknown'),
                title=result.get('title', 'N/A'),
                status=result.get('status', {}).get('value', 'N/A')
            )

            return result

        except AlmaAPIError as e:
            self.logger.error(
                "Failed to retrieve lending request",
                partner_code=partner_code,
                request_id=request_id,
                error_code=e.status_code,
                error_message=str(e)
            )
            raise

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def get_request_summary(self, request_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract key information from a lending request for display.

        Creates a simplified summary dictionary with the most important
        fields from a lending request response.

        Args:
            request_data: Complete lending request data dictionary

        Returns:
            Dictionary with summary information:
                - request_id: Request identifier
                - external_id: External identifier
                - title: Resource title
                - author: Resource author (if present)
                - citation_type: Resource type
                - format: Request format
                - status: Current status
                - partner: Partner code
                - owner: Owning library

        Examples:
            >>> request = rs.get_lending_request("PARTNER_01", "12345678")
            >>> summary = rs.get_request_summary(request)
            >>> print(f"{summary['title']} - {summary['status']}")
        """
        def safe_get(data: Dict, *keys, default: str = "N/A") -> str:
            """Safely extract nested dictionary values."""
            current = data
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key, {})
                else:
                    return default
            return current if current else default

        return {
            "request_id": safe_get(request_data, 'request_id'),
            "external_id": safe_get(request_data, 'external_id'),
            "title": safe_get(request_data, 'title'),
            "author": safe_get(request_data, 'author'),
            "citation_type": safe_get(request_data, 'citation_type', 'value'),
            "format": safe_get(request_data, 'format', 'value'),
            "status": safe_get(request_data, 'status', 'value'),
            "partner": safe_get(request_data, 'partner', 'value'),
            "owner": safe_get(request_data, 'owner', 'value'),
        }

    def create_lending_request_from_citation(
        self,
        partner_code: str,
        external_id: str,
        owner: str,
        format_type: str,
        pmid: Optional[str] = None,
        doi: Optional[str] = None,
        source_type: Optional[str] = None,
        **override_fields
    ) -> Dict[str, Any]:
        """
        Create a lending request with metadata auto-populated from PubMed or Crossref.

        Fetches article metadata from PubMed (using PMID) or Crossref (using DOI)
        and creates a lending request with automatically populated citation fields.

        When source_type is specified, ONLY that source is used (no fallback).
        This is recommended when you know the identifier type upfront (e.g., from a form).

        When source_type is None, uses auto-detect mode with fallback.

        Args:
            partner_code: Partner institution code
            external_id: External identifier for this request
            owner: Resource sharing library code
            format_type: Request format (PHYSICAL/DIGITAL)
            pmid: PubMed ID (optional)
            doi: Digital Object Identifier (optional)
            source_type: Explicit source type - 'pmid' or 'doi' (optional).
                         If specified, only that source is tried (no fallback).
                         Recommended for form inputs where type is known.
            **override_fields: Additional fields to override auto-populated values

        Returns:
            Created lending request as dictionary

        Raises:
            ValueError: If neither pmid nor doi provided, or validation fails
            CitationMetadataError: If metadata fetch fails
            AlmaAPIError: If API request fails

        Examples:
            >>> # Explicit PMID source (recommended for form inputs)
            >>> request = rs.create_lending_request_from_citation(
            ...     partner_code="RELAIS",
            ...     external_id="ILL-2025-001",
            ...     owner="MAIN",
            ...     format_type="DIGITAL",
            ...     pmid="33219451",
            ...     source_type='pmid'
            ... )

            >>> # Explicit DOI source (recommended for form inputs)
            >>> request = rs.create_lending_request_from_citation(
            ...     partner_code="RELAIS",
            ...     external_id="ILL-2025-002",
            ...     owner="MAIN",
            ...     format_type="DIGITAL",
            ...     doi="10.1038/s41591-020-1124-9",
            ...     source_type='doi'
            ... )

            >>> # Auto-detect mode (backward compatible)
            >>> request = rs.create_lending_request_from_citation(
            ...     partner_code="RELAIS",
            ...     external_id="ILL-2025-003",
            ...     owner="MAIN",
            ...     format_type="DIGITAL",
            ...     pmid="33219451"
            ... )

            >>> # Override specific fields
            >>> request = rs.create_lending_request_from_citation(
            ...     partner_code="RELAIS",
            ...     external_id="ILL-2025-004",
            ...     owner="MAIN",
            ...     format_type="PHYSICAL",
            ...     doi="10.1038/s41591-020-1124-9",
            ...     source_type='doi',
            ...     title="Custom Title Override"  # Override auto-fetched title
            ... )
        """
        from almaapitk.utils.citation_metadata import enrich_citation_metadata

        self.logger.info(
            "Creating lending request with metadata enrichment",
            partner_code=partner_code,
            external_id=external_id,
            pmid=pmid,
            doi=doi,
            source_type=source_type
        )

        # Fetch metadata from PubMed or Crossref
        try:
            metadata = enrich_citation_metadata(pmid=pmid, doi=doi, source_type=source_type)
            self.logger.info(
                "Fetched citation metadata",
                source=metadata.get('source'),
                title=metadata.get('title', '')[:50]
            )
        except Exception as e:
            self.logger.error(
                "Failed to fetch citation metadata",
                pmid=pmid,
                doi=doi,
                error=str(e)
            )
            raise

        # Build request fields from metadata
        request_fields = {
            'title': metadata.get('title', ''),
            'author': metadata.get('author', ''),
            'citation_type': 'JOURNAL',  # Default for articles
            'year': metadata.get('publication_date', metadata.get('year', '')),  # Full date when available, fallback to year only
            'volume': metadata.get('volume', ''),
            'issue': metadata.get('issue', ''),
            'pages': metadata.get('pages', ''),
        }

        # Add identifiers
        if metadata.get('doi'):
            request_fields['doi'] = metadata['doi']
        if metadata.get('pmid'):
            request_fields['pmid'] = metadata['pmid']
        if metadata.get('issn'):
            request_fields['issn'] = metadata['issn']

        # Add journal as publisher AND journal_title (for article requests)
        if metadata.get('journal'):
            request_fields['publisher'] = metadata['journal']
            request_fields['journal_title'] = metadata['journal']  # Mandatory for JOURNAL citation type

        # Override with any user-provided fields
        request_fields.update(override_fields)

        # Log what we're creating
        self.logger.debug(
            "Creating lending request with enriched fields",
            enriched_fields=list(request_fields.keys()),
            overridden_fields=list(override_fields.keys()) if override_fields else []
        )

        # Create the request using standard method
        return self.create_lending_request(
            partner_code=partner_code,
            external_id=external_id,
            owner=owner,
            format_type=format_type,
            **request_fields
        )
