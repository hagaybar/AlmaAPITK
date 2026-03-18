"""
Analytics Domain Class for Alma API

Handles Alma Analytics API operations for retrieving report data.
Provides methods to:
- Get report column headers/schema
- Fetch report rows with pagination support

This domain class follows the standard domain class pattern:
- Takes an AlmaAPIClient instance for HTTP requests
- Uses the client's logger for all logging
- Raises AlmaValidationError for input validation failures
- Raises AlmaAPIError for API and parsing errors
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError, AlmaValidationError


class Analytics:
    """
    Domain class for handling Alma Analytics API operations.

    Provides access to Analytics reports through the Alma API,
    with support for pagination via ResumptionToken.
    """

    # XML namespaces used in Analytics responses
    NAMESPACES = {
        'xsd': 'http://www.w3.org/2001/XMLSchema',
        'saw': 'urn:saw-sql',
        'rowset': 'urn:schemas-microsoft-com:xml-analysis:rowset'
    }

    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the Analytics domain.

        Args:
            client: The AlmaAPIClient instance for making HTTP requests
        """
        self.client = client
        self.logger = client.logger

    def get_report_headers(self, report_path: str) -> List[str]:
        """
        Get column headers/schema for an Analytics report.

        Args:
            report_path: Path to the Analytics report (e.g., '/shared/University/Reports/MyReport')

        Returns:
            List of column header names in order (Column0, Column1, etc.)

        Raises:
            AlmaValidationError: If report_path is empty or None
            AlmaAPIError: If the API request fails
        """
        if not report_path:
            raise AlmaValidationError("report_path is required")

        self.logger.info(f"Fetching headers for report: {report_path}")

        # Build endpoint and params
        # Note: Alma Analytics API requires limit between 25 and 1000
        endpoint = "almaws/v1/analytics/reports"
        params = {
            "path": report_path,
            "limit": "25"  # Minimum allowed by Analytics API
        }

        # Request with JSON Accept header (Analytics API returns XML inside JSON anies field)
        response = self.client.get(
            endpoint,
            params=params,
            custom_headers={"Accept": "application/json"}
        )

        # Extract XML from JSON response
        xml_text = self._extract_xml_from_response(response)
        if not xml_text:
            return []

        return self._parse_headers_from_xml(xml_text)

    def _extract_xml_from_response(self, response) -> Optional[str]:
        """
        Extract XML content from Analytics API JSON response.

        The Analytics API returns JSON with an 'anies' field containing XML.

        Args:
            response: AlmaResponse object from client.get()

        Returns:
            XML string extracted from the anies field, or None if not present

        Raises:
            AlmaAPIError: If response cannot be parsed
        """
        try:
            data = response.json()
            anies = data.get("anies", [])
            if anies and len(anies) > 0:
                return anies[0]
            return None
        except Exception as e:
            self.logger.error(f"Failed to extract XML from response: {e}")
            raise AlmaAPIError(f"Failed to parse Analytics response: {e}")

    def _parse_headers_from_xml(self, xml_text: str) -> List[str]:
        """
        Parse column headers from Analytics XML response.

        Args:
            xml_text: Raw XML response text

        Returns:
            List of column header names in order

        Raises:
            AlmaAPIError: If XML parsing fails
        """
        headers = []

        try:
            root = ET.fromstring(xml_text)

            # Find all xsd:element nodes with saw:columnHeading attribute
            # The schema may be at different levels depending on response format
            for elem in root.iter():
                if 'element' in elem.tag:
                    # Check for columnHeading in various namespace forms
                    column_heading = (
                        elem.get('{urn:saw-sql}columnHeading') or
                        elem.get('columnHeading') or
                        elem.get('{%s}columnHeading' % self.NAMESPACES['saw'])
                    )
                    if column_heading:
                        headers.append(column_heading)

        except ET.ParseError as e:
            self.logger.error(f"Failed to parse XML response: {e}")
            raise AlmaAPIError(f"Failed to parse Analytics response: {e}")

        self.logger.info(f"Found {len(headers)} column headers")
        return headers

    def fetch_report_rows(
        self,
        report_path: str,
        limit: int = 1000,
        max_rows: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch rows from an Analytics report with pagination support.

        Args:
            report_path: Path to the Analytics report
            limit: Number of rows per page request (default 1000)
            max_rows: Maximum total rows to return (None for unlimited)

        Returns:
            List of row dictionaries with Column0, Column1, etc. as keys

        Raises:
            AlmaValidationError: If report_path is empty or None
            AlmaAPIError: If the API request fails
        """
        if not report_path:
            raise AlmaValidationError("report_path is required")

        if limit < 25:
            raise AlmaValidationError("limit must be at least 25 (Alma Analytics API minimum)")

        if limit > 1000:
            raise AlmaValidationError("limit must be at most 1000 (Alma Analytics API maximum)")

        if max_rows is not None and max_rows < 0:
            raise AlmaValidationError("max_rows cannot be negative")

        if max_rows == 0:
            return []

        self.logger.info(f"Fetching rows from report: {report_path}")

        all_rows = []
        resumption_token = None
        is_finished = False

        while not is_finished:
            # Check if we've reached max_rows
            if max_rows is not None and len(all_rows) >= max_rows:
                all_rows = all_rows[:max_rows]
                break

            # Build request
            endpoint = "almaws/v1/analytics/reports"
            params = {
                "path": report_path,
                "limit": str(limit)
            }

            if resumption_token:
                params["token"] = resumption_token

            # Make request with JSON Accept header (Analytics API returns XML inside JSON anies field)
            response = self.client.get(
                endpoint,
                params=params,
                custom_headers={"Accept": "application/json"}
            )

            # Extract XML from JSON response
            xml_text = self._extract_xml_from_response(response)
            if not xml_text:
                break
            rows, resumption_token, is_finished = self._parse_rows_from_xml(xml_text)

            all_rows.extend(rows)

            self.logger.debug(f"Fetched {len(rows)} rows, total: {len(all_rows)}, finished: {is_finished}")

            # Break if no more pages
            if not resumption_token or is_finished:
                break

        # Apply max_rows limit
        if max_rows is not None and len(all_rows) > max_rows:
            all_rows = all_rows[:max_rows]

        self.logger.info(f"Total rows fetched: {len(all_rows)}")
        return all_rows

    def _parse_rows_from_xml(self, xml_text: str) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
        """
        Parse rows from Analytics XML response.

        Args:
            xml_text: Raw XML response text

        Returns:
            Tuple of (rows_list, resumption_token, is_finished) where:
                - rows_list: List of row dictionaries with Column0, Column1, etc. as keys
                - resumption_token: Token for fetching next page, or None if no more pages
                - is_finished: True if this is the last page of results

        Raises:
            AlmaAPIError: If XML parsing fails
        """
        rows = []
        resumption_token = None
        is_finished = True

        try:
            root = ET.fromstring(xml_text)

            # Find all Row elements
            for row_elem in root.iter():
                if 'Row' in row_elem.tag and row_elem.tag.endswith('Row'):
                    row_data = {}
                    for child in row_elem:
                        # Extract column name from tag (remove namespace)
                        tag = child.tag
                        if '}' in tag:
                            tag = tag.split('}')[1]
                        row_data[tag] = child.text or ''
                    if row_data:
                        rows.append(row_data)

            # Find ResumptionToken
            for elem in root.iter():
                if 'ResumptionToken' in elem.tag:
                    resumption_token = elem.text if elem.text and elem.text.strip() else None
                    break

            # Find IsFinished flag
            for elem in root.iter():
                if 'IsFinished' in elem.tag:
                    is_finished = elem.text and elem.text.lower() == 'true'
                    break

        except ET.ParseError as e:
            self.logger.error(f"Failed to parse XML response: {e}")
            raise AlmaAPIError(f"Failed to parse Analytics response: {e}")

        return rows, resumption_token, is_finished
