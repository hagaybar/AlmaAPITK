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

import time
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, Tuple

from almaapitk.client.AlmaAPIClient import (
    AlmaAnalyticsStalledError,
    AlmaAPIClient,
    AlmaAPIError,
    AlmaOperationCancelled,
    AlmaValidationError,
)

# Issue #229: an empty, unfinished page means Alma is still preparing the
# report. Wait before asking again, doubling up to this ceiling, and sleep
# in short ticks so a should_stop() request is noticed promptly.
_MAX_EMPTY_PAGE_DELAY = 30.0
_STOP_CHECK_INTERVAL = 0.5


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
        max_rows: Optional[int] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        *,
        max_pages: Optional[int] = None,
        max_empty_pages: int = 20,
        max_stall_seconds: float = 600,
        empty_page_delay: float = 2.0,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch rows from an Analytics report with pagination support.

        A page that adds no rows while the report is unfinished is treated
        as "Alma still preparing": the fetch waits ``empty_page_delay``
        seconds (doubling, at most 30 s) before asking again. Any page with
        new rows resets the stall counters, so slow reports that keep
        progressing are unaffected (issue #229).

        Args:
            report_path: Path to the Analytics report
            limit: Number of rows per page request (default 1000)
            max_rows: Maximum total rows to return (None for unlimited).
                Results are truncated silently at this size.
            progress_callback: Optional callable invoked once per page with
                the cumulative row count fetched so far. Exceptions raised
                by the callback are caught and logged; they do not abort
                the fetch.
            max_pages: Optional hard cap on page requests. Exceeding it
                raises ``AlmaAnalyticsStalledError`` (None = no cap).
            max_empty_pages: Consecutive pages without new rows after
                which the fetch gives up (default 20).
            max_stall_seconds: Seconds without new rows after which the
                fetch gives up (default 600).
            empty_page_delay: First wait, in seconds, after an empty page.
            should_stop: Optional callable checked before every request and
                during waits. When it returns True the fetch raises
                ``AlmaOperationCancelled``. Its exceptions are not caught.

        Returns:
            List of row dictionaries with Column0, Column1, etc. as keys

        Raises:
            AlmaValidationError: If an argument is invalid
            AlmaAnalyticsStalledError: If the report stops making progress
                or ``max_pages`` is exceeded
            AlmaOperationCancelled: If ``should_stop`` returned True
            AlmaAPIError: If the API request fails
        """
        if not report_path:
            raise AlmaValidationError("report_path is required")

        # Coerce numeric params before any comparison: consumers commonly supply
        # limit/max_rows from a JSON config or CLI args (strings), and a float
        # would reach Alma as an invalid token like "1000.0". Normalise to int
        # with a clear error instead of a raw TypeError (issue #177).
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise AlmaValidationError(f"limit must be an integer, got {limit!r}")

        if max_rows is not None:
            try:
                max_rows = int(max_rows)
            except (TypeError, ValueError):
                raise AlmaValidationError(
                    f"max_rows must be an integer or None, got {max_rows!r}"
                )

        if limit < 25:
            raise AlmaValidationError("limit must be at least 25 (Alma Analytics API minimum)")

        if limit > 1000:
            raise AlmaValidationError("limit must be at most 1000 (Alma Analytics API maximum)")

        if max_rows is not None and max_rows < 0:
            raise AlmaValidationError("max_rows cannot be negative")

        self._validate_fetch_controls(
            max_pages, max_empty_pages, max_stall_seconds, empty_page_delay, should_stop
        )

        if max_rows == 0:
            return []

        self.logger.info(f"Fetching rows from report: {report_path}")

        all_rows: List[Dict[str, Any]] = []
        resumption_token = None
        pages = 0
        empty_pages = 0
        delay = empty_page_delay
        last_progress = time.monotonic()

        while True:
            # Check if we've reached max_rows
            if max_rows is not None and len(all_rows) >= max_rows:
                break

            self._check_stop(should_stop, pages, len(all_rows))
            if max_pages is not None and pages >= max_pages:
                raise AlmaAnalyticsStalledError(
                    f"Analytics report {report_path!r} needed more than "
                    f"max_pages={max_pages} pages ({len(all_rows)} rows so far)"
                )

            rows, resumption_token, is_finished, got_xml = self._fetch_rows_page(
                report_path, limit, resumption_token
            )
            if not got_xml:
                break
            pages += 1
            all_rows.extend(rows)

            self.logger.debug(f"Fetched {len(rows)} rows, total: {len(all_rows)}, finished: {is_finished}")

            if progress_callback is not None:
                try:
                    progress_callback(len(all_rows))
                except Exception:
                    self.logger.warning("progress_callback raised; continuing fetch", exc_info=True)

            # Break if no more pages
            if not resumption_token or is_finished:
                break

            if rows:
                empty_pages = 0
                delay = empty_page_delay
                last_progress = time.monotonic()
                continue

            empty_pages += 1
            stalled_for = time.monotonic() - last_progress
            if empty_pages >= max_empty_pages or stalled_for >= max_stall_seconds:
                raise AlmaAnalyticsStalledError(
                    f"Analytics report {report_path!r} made no progress: "
                    f"{empty_pages} consecutive pages without new rows over "
                    f"{stalled_for:.0f} s (limits: max_empty_pages={max_empty_pages}, "
                    f"max_stall_seconds={max_stall_seconds}); {pages} pages and "
                    f"{len(all_rows)} rows fetched"
                )
            self.logger.info(
                f"Analytics report not ready yet (empty page {empty_pages}); "
                f"waiting {delay:.1f} s"
            )
            self._wait(delay, should_stop, pages, len(all_rows))
            delay = min(delay * 2, _MAX_EMPTY_PAGE_DELAY)

        # Apply max_rows limit
        if max_rows is not None and len(all_rows) > max_rows:
            all_rows = all_rows[:max_rows]

        self.logger.info(f"Total rows fetched: {len(all_rows)}")
        return all_rows

    def _fetch_rows_page(
        self, report_path: str, limit: int, resumption_token: Optional[str]
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool, bool]:
        """Request one page of report rows.

        Returns:
            ``(rows, resumption_token, is_finished, got_xml)``; ``got_xml``
            is False when the response carried no XML at all.
        """
        params = {"path": report_path, "limit": str(limit)}
        if resumption_token:
            params["token"] = resumption_token

        # Analytics API returns XML inside the JSON "anies" field
        response = self.client.get(
            "almaws/v1/analytics/reports",
            params=params,
            custom_headers={"Accept": "application/json"}
        )
        xml_text = self._extract_xml_from_response(response)
        if not xml_text:
            return [], None, True, False
        rows, token, is_finished = self._parse_rows_from_xml(xml_text)
        return rows, token, is_finished, True

    @staticmethod
    def _validate_fetch_controls(
        max_pages: Any,
        max_empty_pages: Any,
        max_stall_seconds: Any,
        empty_page_delay: Any,
        should_stop: Any,
    ) -> None:
        """Validate the stall-guard and cancellation arguments (issue #229)."""
        def is_number(value: Any) -> bool:
            return isinstance(value, (int, float)) and not isinstance(value, bool)

        if max_pages is not None and not (isinstance(max_pages, int) and max_pages >= 1):
            raise AlmaValidationError(f"max_pages must be a positive integer or None, got {max_pages!r}")
        if not (isinstance(max_empty_pages, int) and max_empty_pages >= 1):
            raise AlmaValidationError(f"max_empty_pages must be a positive integer, got {max_empty_pages!r}")
        if not (is_number(max_stall_seconds) and max_stall_seconds > 0):
            raise AlmaValidationError(f"max_stall_seconds must be a positive number, got {max_stall_seconds!r}")
        if not (is_number(empty_page_delay) and empty_page_delay >= 0):
            raise AlmaValidationError(f"empty_page_delay must be a non-negative number, got {empty_page_delay!r}")
        if should_stop is not None and not callable(should_stop):
            raise AlmaValidationError("should_stop must be callable or None")

    @staticmethod
    def _check_stop(
        should_stop: Optional[Callable[[], bool]], pages: int, rows: int
    ) -> None:
        """Raise ``AlmaOperationCancelled`` if the caller asked to stop."""
        if should_stop is not None and should_stop():
            raise AlmaOperationCancelled(
                f"Analytics fetch cancelled by should_stop after {pages} pages "
                f"and {rows} rows"
            )

    def _wait(
        self,
        seconds: float,
        should_stop: Optional[Callable[[], bool]],
        pages: int,
        rows: int,
    ) -> None:
        """Sleep ``seconds`` in short ticks, checking ``should_stop`` each tick."""
        if should_stop is None:
            time.sleep(seconds)
            return
        remaining = seconds
        while remaining > 0:
            tick = min(_STOP_CHECK_INTERVAL, remaining)
            time.sleep(tick)
            remaining -= tick
            self._check_stop(should_stop, pages, rows)

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
