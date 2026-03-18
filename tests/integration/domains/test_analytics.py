#!/usr/bin/env python3
"""
Integration Tests for Analytics Domain Class

Tests the Analytics domain class methods:
- get_report_headers(report_path) - Get column headers/schema for an Analytics report
- fetch_report_rows(report_path, limit, max_rows) - Fetch rows with pagination

These tests require:
- ALMA_PROD_API_KEY environment variable to be set (Analytics only works in production)
- A valid report path in the production environment

Run with: pytest tests/integration/domains/test_analytics.py -v
"""

import os
import pytest

from almaapitk import AlmaAPIClient, Analytics, AlmaAPIError, AlmaValidationError


# Test configuration - use a known report path
# Override with environment variable if needed
TEST_REPORT_PATH = os.getenv(
    'TEST_ANALYTICS_REPORT_PATH',
    '/shared/Your University/Reports/Production/AAS Loans'
)


def _has_alma_prod_api_key() -> bool:
    """Check if production API key is available."""
    return bool(os.getenv('ALMA_PROD_API_KEY'))


# Skip markers
skip_if_no_api_key = pytest.mark.skipif(
    not _has_alma_prod_api_key(),
    reason="ALMA_PROD_API_KEY environment variable not set"
)


@pytest.fixture(scope='module')
def alma_client():
    """
    Create an AlmaAPIClient instance for testing.

    Uses PRODUCTION environment because Analytics API only works in production.
    Skips tests if API key is not configured.
    """
    api_key = os.getenv('ALMA_PROD_API_KEY')
    if not api_key:
        pytest.skip("ALMA_PROD_API_KEY environment variable not set")

    client = AlmaAPIClient('PRODUCTION')
    return client


@pytest.fixture(scope='module')
def analytics(alma_client):
    """Create an Analytics instance for testing."""
    return Analytics(alma_client)


@pytest.mark.integration
@skip_if_no_api_key
class TestAnalyticsIntegration:
    """
    Integration tests for Analytics domain methods.

    These tests interact with the live Alma production API.
    Analytics API is only available in production environments.
    """

    def test_get_report_headers_real(self, analytics):
        """
        Test fetching real report headers from Analytics API.

        Verifies:
        - Method returns a list of headers
        - Headers list is not empty for a valid report
        - Each header is a string
        """
        try:
            headers = analytics.get_report_headers(TEST_REPORT_PATH)

            assert headers is not None, "Headers should not be None"
            assert isinstance(headers, list), "Headers should be a list"
            assert len(headers) > 0, "Headers list should not be empty for valid report"

            # Verify all headers are strings
            for header in headers:
                assert isinstance(header, str), f"Each header should be a string, got {type(header)}"

            print(f"Found {len(headers)} headers: {headers[:5]}...")  # Print first 5 for debugging

        except AlmaAPIError as e:
            if e.status_code == 404:
                pytest.skip(f"Report not found: {TEST_REPORT_PATH}")
            elif e.status_code == 400:
                pytest.skip(f"Invalid report path or access denied: {TEST_REPORT_PATH}")
            raise

    def test_fetch_report_rows_real(self, analytics):
        """
        Test fetching real report rows from Analytics API.

        Uses max_rows=10 to limit test duration and data volume.

        Verifies:
        - Method returns a list of row dictionaries
        - Each row is a dictionary with string keys
        - Row count respects max_rows limit
        """
        try:
            rows = analytics.fetch_report_rows(
                TEST_REPORT_PATH,
                limit=10,
                max_rows=10
            )

            assert rows is not None, "Rows should not be None"
            assert isinstance(rows, list), "Rows should be a list"
            assert len(rows) <= 10, f"Should return at most 10 rows, got {len(rows)}"

            # If report has data, verify row structure
            if len(rows) > 0:
                first_row = rows[0]
                assert isinstance(first_row, dict), "Each row should be a dictionary"

                # Verify keys are strings (Column0, Column1, etc.)
                for key in first_row.keys():
                    assert isinstance(key, str), f"Row keys should be strings, got {type(key)}"

                print(f"Fetched {len(rows)} rows with columns: {list(first_row.keys())[:5]}...")

        except AlmaAPIError as e:
            if e.status_code == 404:
                pytest.skip(f"Report not found: {TEST_REPORT_PATH}")
            elif e.status_code == 400:
                pytest.skip(f"Invalid report path or access denied: {TEST_REPORT_PATH}")
            raise

    def test_fetch_report_rows_pagination_real(self, analytics):
        """
        Test pagination behavior when fetching report rows.

        Uses small limits to test pagination mechanics without
        fetching excessive data.

        Verifies:
        - Method handles multiple pages correctly
        - max_rows limit is respected across pages
        - Results are consistent lists of dictionaries
        """
        try:
            # First, fetch with a small limit per page and max_rows
            rows_small_limit = analytics.fetch_report_rows(
                TEST_REPORT_PATH,
                limit=3,  # Small page size to force pagination
                max_rows=10
            )

            assert rows_small_limit is not None, "Rows should not be None"
            assert isinstance(rows_small_limit, list), "Rows should be a list"
            assert len(rows_small_limit) <= 10, f"Should respect max_rows=10, got {len(rows_small_limit)}"

            # Verify all rows are dictionaries
            for row in rows_small_limit:
                assert isinstance(row, dict), "Each row should be a dictionary"

            print(f"Pagination test: fetched {len(rows_small_limit)} rows with limit=3, max_rows=10")

        except AlmaAPIError as e:
            if e.status_code == 404:
                pytest.skip(f"Report not found: {TEST_REPORT_PATH}")
            elif e.status_code == 400:
                pytest.skip(f"Invalid report path or access denied: {TEST_REPORT_PATH}")
            raise

    def test_fetch_report_rows_max_rows_zero(self, analytics):
        """
        Test that max_rows=0 returns empty list without API call.

        Verifies:
        - Method returns empty list immediately when max_rows=0
        """
        rows = analytics.fetch_report_rows(
            TEST_REPORT_PATH,
            limit=10,
            max_rows=0
        )

        assert rows == [], "Should return empty list when max_rows=0"

    def test_get_report_headers_invalid_path(self, analytics):
        """
        Test get_report_headers with invalid report path.

        Verifies:
        - Method raises AlmaAPIError for non-existent report
        - Error contains appropriate status code (400/404)
        """
        invalid_report_path = "/shared/NonExistent/Reports/InvalidReport123"

        with pytest.raises(AlmaAPIError) as exc_info:
            analytics.get_report_headers(invalid_report_path)

        # Expect 400 (Bad Request) or 404 (Not Found) for invalid paths
        assert exc_info.value.status_code in [400, 404], \
            f"Expected 400/404 for invalid report, got {exc_info.value.status_code}"

    def test_fetch_report_rows_invalid_path(self, analytics):
        """
        Test fetch_report_rows with invalid report path.

        Verifies:
        - Method raises AlmaAPIError for non-existent report
        - Error contains appropriate status code (400/404)
        """
        invalid_report_path = "/shared/NonExistent/Reports/InvalidReport123"

        with pytest.raises(AlmaAPIError) as exc_info:
            analytics.fetch_report_rows(invalid_report_path, limit=10, max_rows=5)

        assert exc_info.value.status_code in [400, 404], \
            f"Expected 400/404 for invalid report, got {exc_info.value.status_code}"


@pytest.mark.integration
@skip_if_no_api_key
class TestAnalyticsValidation:
    """
    Tests for input validation in Analytics methods.

    These tests verify that validation errors are raised
    before making API calls for invalid inputs.
    """

    def test_get_report_headers_empty_path(self, analytics):
        """Test that empty report_path raises validation error."""
        with pytest.raises(AlmaValidationError):
            analytics.get_report_headers("")

    def test_get_report_headers_none_path(self, analytics):
        """Test that None report_path raises validation error."""
        with pytest.raises(AlmaValidationError):
            analytics.get_report_headers(None)

    def test_fetch_report_rows_empty_path(self, analytics):
        """Test that empty report_path raises validation error."""
        with pytest.raises(AlmaValidationError):
            analytics.fetch_report_rows("")

    def test_fetch_report_rows_none_path(self, analytics):
        """Test that None report_path raises validation error."""
        with pytest.raises(AlmaValidationError):
            analytics.fetch_report_rows(None)

    def test_fetch_report_rows_negative_max_rows(self, analytics):
        """Test that negative max_rows raises validation error."""
        with pytest.raises(AlmaValidationError):
            analytics.fetch_report_rows(TEST_REPORT_PATH, max_rows=-1)

    def test_fetch_report_rows_zero_limit(self, analytics):
        """Test that zero limit raises validation error."""
        with pytest.raises(AlmaValidationError):
            analytics.fetch_report_rows(TEST_REPORT_PATH, limit=0)


@pytest.mark.integration
@skip_if_no_api_key
class TestAnalyticsWorkflow:
    """
    End-to-end workflow tests for Analytics operations.

    These tests verify complete workflows combining multiple methods.
    """

    def test_headers_and_rows_consistency(self, analytics):
        """
        Test that headers and row columns are consistent.

        Fetches both headers and rows from the same report and verifies
        that the column structure is consistent.

        Verifies:
        - Headers can be fetched successfully
        - Rows can be fetched successfully
        - Row column names follow expected pattern (Column0, Column1, etc.)
        """
        try:
            # Fetch headers
            headers = analytics.get_report_headers(TEST_REPORT_PATH)
            assert len(headers) > 0, "Should have at least one header"

            # Fetch a few rows
            rows = analytics.fetch_report_rows(
                TEST_REPORT_PATH,
                limit=5,
                max_rows=5
            )

            # If we have rows, verify column consistency
            if len(rows) > 0:
                row_columns = list(rows[0].keys())
                # Row columns should match number of headers
                # (columns are named Column0, Column1, etc.)
                print(f"Headers count: {len(headers)}, Row columns: {row_columns}")

                # Both should have the same count
                # Note: Analytics returns Column0, Column1, etc. as keys
                assert len(row_columns) == len(headers), \
                    f"Row column count ({len(row_columns)}) should match header count ({len(headers)})"

        except AlmaAPIError as e:
            if e.status_code in [400, 404]:
                pytest.skip(f"Report not accessible: {TEST_REPORT_PATH}")
            raise


# Convenience function for running tests directly
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])
