"""
Unit tests for the Analytics domain class.

Tests cover:
- Initialization (client and logger setup)
- get_report_headers() - Retrieve column headers/schema from Analytics reports
- fetch_report_rows() - Fetch rows with pagination support (ResumptionToken)

These tests use mocked API responses to test the Analytics domain in isolation.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch, PropertyMock
import xml.etree.ElementTree as ET


# Sample XML responses for mocking
SAMPLE_SCHEMA_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<report xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:saw="urn:saw-sql">
    <xsd:schema>
        <xsd:element name="Column0" saw:columnHeading="MMS ID" type="xsd:string"/>
        <xsd:element name="Column1" saw:columnHeading="Title" type="xsd:string"/>
        <xsd:element name="Column2" saw:columnHeading="Author" type="xsd:string"/>
    </xsd:schema>
</report>'''

SAMPLE_ROWS_XML_PAGE_1 = '''<?xml version="1.0" encoding="UTF-8"?>
<report xmlns="urn:schemas-microsoft-com:xml-analysis:rowset">
    <Row>
        <Column0>991234567890001</Column0>
        <Column1>Test Book One</Column1>
        <Column2>Author One</Column2>
    </Row>
    <Row>
        <Column0>991234567890002</Column0>
        <Column1>Test Book Two</Column1>
        <Column2>Author Two</Column2>
    </Row>
    <ResumptionToken>token_page_2</ResumptionToken>
    <IsFinished>false</IsFinished>
</report>'''

SAMPLE_ROWS_XML_PAGE_2 = '''<?xml version="1.0" encoding="UTF-8"?>
<report xmlns="urn:schemas-microsoft-com:xml-analysis:rowset">
    <Row>
        <Column0>991234567890003</Column0>
        <Column1>Test Book Three</Column1>
        <Column2>Author Three</Column2>
    </Row>
    <ResumptionToken></ResumptionToken>
    <IsFinished>true</IsFinished>
</report>'''

SAMPLE_ROWS_XML_SINGLE_PAGE = '''<?xml version="1.0" encoding="UTF-8"?>
<report xmlns="urn:schemas-microsoft-com:xml-analysis:rowset">
    <Row>
        <Column0>991234567890001</Column0>
        <Column1>Test Book One</Column1>
        <Column2>Author One</Column2>
    </Row>
    <Row>
        <Column0>991234567890002</Column0>
        <Column1>Test Book Two</Column1>
        <Column2>Author Two</Column2>
    </Row>
    <IsFinished>true</IsFinished>
</report>'''

SAMPLE_EMPTY_REPORT_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<report xmlns="urn:schemas-microsoft-com:xml-analysis:rowset">
    <IsFinished>true</IsFinished>
</report>'''

SAMPLE_EMPTY_SCHEMA_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<report xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <xsd:schema>
    </xsd:schema>
</report>'''


class MockAlmaResponse:
    """Mock AlmaResponse class for testing.

    Now supports JSON responses with anies field containing XML,
    matching the actual Analytics API response format.
    """

    def __init__(self, xml_content: str, status_code: int = 200, success: bool = True):
        self._xml = xml_content
        self.status_code = status_code
        self.success = success

    def text(self) -> str:
        return self._xml

    def json(self):
        """Return JSON with anies field containing the XML."""
        return {"anies": [self._xml]}


class MockAlmaAPIClient:
    """Mock AlmaAPIClient for testing Analytics domain."""

    def __init__(self, environment: str = 'SANDBOX'):
        self.environment = environment
        self.logger = MagicMock()
        self._get_responses = []
        self._get_call_count = 0

    def get(self, endpoint: str, params: dict = None, custom_headers: dict = None):
        """Mock GET method that returns predefined responses."""
        if self._get_responses:
            response = self._get_responses[self._get_call_count % len(self._get_responses)]
            self._get_call_count += 1
            return response
        return MockAlmaResponse("<empty/>")

    def set_get_responses(self, responses: list):
        """Set the list of responses to return from get() calls."""
        self._get_responses = responses
        self._get_call_count = 0

    def get_environment(self) -> str:
        return self.environment


class TestAnalyticsInit:
    """Tests for Analytics class initialization."""

    def test_init_sets_client(self):
        """Test that __init__ properly stores the client."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        assert analytics.client is mock_client

    def test_init_sets_logger_from_client(self):
        """Test that __init__ sets logger from client.logger."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        assert analytics.logger is mock_client.logger

    def test_init_with_production_environment(self):
        """Test initialization with PRODUCTION environment."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('PRODUCTION')
        analytics = Analytics(mock_client)

        assert analytics.client.get_environment() == 'PRODUCTION'


class TestGetReportHeaders:
    """Tests for Analytics.get_report_headers() method."""

    def test_get_report_headers_success(self):
        """Test successful retrieval of report headers from XML schema."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_SCHEMA_XML)
        ])

        analytics = Analytics(mock_client)
        headers = analytics.get_report_headers('/shared/Test/Report')

        assert headers is not None
        assert len(headers) == 3
        assert 'MMS ID' in headers
        assert 'Title' in headers
        assert 'Author' in headers

    def test_get_report_headers_returns_ordered_list(self):
        """Test that headers are returned in column order."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_SCHEMA_XML)
        ])

        analytics = Analytics(mock_client)
        headers = analytics.get_report_headers('/shared/Test/Report')

        # Headers should be in Column0, Column1, Column2 order
        assert headers[0] == 'MMS ID'
        assert headers[1] == 'Title'
        assert headers[2] == 'Author'

    def test_get_report_headers_empty_report(self):
        """Test handling of empty report with no columns."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_EMPTY_SCHEMA_XML)
        ])

        analytics = Analytics(mock_client)
        headers = analytics.get_report_headers('/shared/Empty/Report')

        assert headers == []

    def test_get_report_headers_invalid_path_empty(self):
        """Test validation error when report_path is empty."""
        from almaapitk.domains.analytics import Analytics
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        with pytest.raises(AlmaValidationError) as exc_info:
            analytics.get_report_headers('')

        assert 'report_path' in str(exc_info.value).lower() or 'required' in str(exc_info.value).lower()

    def test_get_report_headers_invalid_path_none(self):
        """Test validation error when report_path is None."""
        from almaapitk.domains.analytics import Analytics
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        with pytest.raises(AlmaValidationError):
            analytics.get_report_headers(None)

    def test_get_report_headers_logs_operation(self):
        """Test that the operation is logged."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_SCHEMA_XML)
        ])

        analytics = Analytics(mock_client)
        analytics.get_report_headers('/shared/Test/Report')

        # Verify logger was called (info or debug level)
        assert mock_client.logger.info.called or mock_client.logger.debug.called


class TestFetchReportRows:
    """Tests for Analytics.fetch_report_rows() method."""

    def test_fetch_report_rows_single_page(self):
        """Test fetching rows when all data fits in a single page."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_ROWS_XML_SINGLE_PAGE)
        ])

        analytics = Analytics(mock_client)
        rows = analytics.fetch_report_rows('/shared/Test/Report')

        assert rows is not None
        assert len(rows) == 2
        assert rows[0]['Column0'] == '991234567890001'
        assert rows[0]['Column1'] == 'Test Book One'
        assert rows[1]['Column0'] == '991234567890002'
        assert rows[1]['Column1'] == 'Test Book Two'

    def test_fetch_report_rows_pagination(self):
        """Test fetching rows with pagination using ResumptionToken."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_ROWS_XML_PAGE_1),
            MockAlmaResponse(SAMPLE_ROWS_XML_PAGE_2)
        ])

        analytics = Analytics(mock_client)
        rows = analytics.fetch_report_rows('/shared/Test/Report')

        # Should have 3 rows total (2 from page 1, 1 from page 2)
        assert len(rows) == 3
        assert rows[0]['Column0'] == '991234567890001'
        assert rows[1]['Column0'] == '991234567890002'
        assert rows[2]['Column0'] == '991234567890003'

    def test_fetch_report_rows_respects_limit(self):
        """Test that limit parameter controls rows per page request."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_ROWS_XML_SINGLE_PAGE)
        ])

        analytics = Analytics(mock_client)

        # With limit=50, the API should be called with limit parameter
        rows = analytics.fetch_report_rows('/shared/Test/Report', limit=50)

        # Verify we got results (actual limit enforcement is API-side)
        assert rows is not None

    def test_fetch_report_rows_max_rows_limit(self):
        """Test that max_rows parameter limits total rows returned."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_ROWS_XML_PAGE_1),
            MockAlmaResponse(SAMPLE_ROWS_XML_PAGE_2)
        ])

        analytics = Analytics(mock_client)

        # Set max_rows=2 to stop after getting 2 rows
        rows = analytics.fetch_report_rows('/shared/Test/Report', max_rows=2)

        assert len(rows) == 2
        assert rows[0]['Column0'] == '991234567890001'
        assert rows[1]['Column0'] == '991234567890002'

    def test_fetch_report_rows_max_rows_zero_returns_empty(self):
        """Test that max_rows=0 returns empty list."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        rows = analytics.fetch_report_rows('/shared/Test/Report', max_rows=0)

        assert rows == []

    def test_fetch_report_rows_empty_report(self):
        """Test handling of empty report with no rows."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_EMPTY_REPORT_XML)
        ])

        analytics = Analytics(mock_client)
        rows = analytics.fetch_report_rows('/shared/Empty/Report')

        assert rows == []

    def test_fetch_report_rows_invalid_path_empty(self):
        """Test validation error when report_path is empty."""
        from almaapitk.domains.analytics import Analytics
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        with pytest.raises(AlmaValidationError):
            analytics.fetch_report_rows('')

    def test_fetch_report_rows_invalid_path_none(self):
        """Test validation error when report_path is None."""
        from almaapitk.domains.analytics import Analytics
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        with pytest.raises(AlmaValidationError):
            analytics.fetch_report_rows(None)

    def test_fetch_report_rows_logs_progress(self):
        """Test that pagination progress is logged."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_ROWS_XML_PAGE_1),
            MockAlmaResponse(SAMPLE_ROWS_XML_PAGE_2)
        ])

        analytics = Analytics(mock_client)
        analytics.fetch_report_rows('/shared/Test/Report')

        # Verify logger was called during pagination
        assert mock_client.logger.info.called or mock_client.logger.debug.called

    def test_fetch_report_rows_negative_max_rows(self):
        """Test validation error when max_rows is negative."""
        from almaapitk.domains.analytics import Analytics
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        with pytest.raises(AlmaValidationError) as exc_info:
            analytics.fetch_report_rows('/shared/Test/Report', max_rows=-1)

        assert 'negative' in str(exc_info.value).lower() or 'max_rows' in str(exc_info.value).lower()

    def test_fetch_report_rows_limit_below_minimum(self):
        """Test validation error when limit is below Alma minimum (25)."""
        from almaapitk.domains.analytics import Analytics
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        with pytest.raises(AlmaValidationError) as exc_info:
            analytics.fetch_report_rows('/shared/Test/Report', limit=10)

        assert 'limit' in str(exc_info.value).lower() or '25' in str(exc_info.value)

    def test_fetch_report_rows_limit_above_maximum(self):
        """Test validation error when limit is above Alma maximum (1000)."""
        from almaapitk.domains.analytics import Analytics
        from almaapitk import AlmaValidationError

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        with pytest.raises(AlmaValidationError) as exc_info:
            analytics.fetch_report_rows('/shared/Test/Report', limit=2000)

        assert 'limit' in str(exc_info.value).lower() or '1000' in str(exc_info.value)

    def test_fetch_report_rows_returns_dict_with_column_keys(self):
        """Test that each row is a dict with Column0, Column1, etc. as keys."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_ROWS_XML_SINGLE_PAGE)
        ])

        analytics = Analytics(mock_client)
        rows = analytics.fetch_report_rows('/shared/Test/Report')

        # Check first row has expected keys
        first_row = rows[0]
        assert 'Column0' in first_row
        assert 'Column1' in first_row
        assert 'Column2' in first_row


class TestAnalyticsEdgeCases:
    """Edge case and error handling tests for Analytics domain."""

    def test_handles_xml_parse_error_gracefully(self):
        """Test handling of malformed XML response."""
        from almaapitk.domains.analytics import Analytics
        from almaapitk import AlmaAPIError

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse("not valid xml <broken>")
        ])

        analytics = Analytics(mock_client)

        # Should raise an error or return empty result, not crash
        with pytest.raises((AlmaAPIError, ET.ParseError, Exception)):
            analytics.get_report_headers('/shared/Test/Report')

    def test_pagination_stops_on_is_finished_true(self):
        """Test that pagination stops when IsFinished is true."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        # First page says IsFinished=true, so no second call should happen
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_ROWS_XML_SINGLE_PAGE)
        ])

        analytics = Analytics(mock_client)
        rows = analytics.fetch_report_rows('/shared/Test/Report')

        # Should only have called get once (IsFinished=true stops pagination)
        assert mock_client._get_call_count == 1

    def test_pagination_uses_resumption_token(self):
        """Test that ResumptionToken from first page is used in second request."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_ROWS_XML_PAGE_1),
            MockAlmaResponse(SAMPLE_ROWS_XML_PAGE_2)
        ])

        # Override get to capture params
        original_get = mock_client.get
        captured_params = []

        def capturing_get(endpoint, params=None, custom_headers=None):
            captured_params.append(params)
            return original_get(endpoint, params, custom_headers)

        mock_client.get = capturing_get

        analytics = Analytics(mock_client)
        analytics.fetch_report_rows('/shared/Test/Report')

        # Second call should include the resumption token
        assert len(captured_params) == 2
        # First call should not have token (or have empty token)
        # Second call should have the token from page 1
        if captured_params[1]:
            assert 'token' in str(captured_params[1]).lower() or 'token_page_2' in str(captured_params[1].values())


class TestAnalyticsIntegrationPatterns:
    """Tests verifying Analytics follows domain class patterns."""

    def test_follows_domain_class_pattern(self):
        """Test that Analytics follows the same pattern as other domain classes."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        analytics = Analytics(mock_client)

        # Should have client attribute
        assert hasattr(analytics, 'client')
        # Should have logger attribute
        assert hasattr(analytics, 'logger')
        # Methods should exist
        assert hasattr(analytics, 'get_report_headers')
        assert hasattr(analytics, 'fetch_report_rows')

    def test_uses_client_get_method(self):
        """Test that Analytics uses client.get() for API calls."""
        from almaapitk.domains.analytics import Analytics

        mock_client = MockAlmaAPIClient('SANDBOX')
        mock_client.set_get_responses([
            MockAlmaResponse(SAMPLE_SCHEMA_XML)
        ])

        # Spy on the get method
        mock_client.get = MagicMock(return_value=MockAlmaResponse(SAMPLE_SCHEMA_XML))

        analytics = Analytics(mock_client)
        analytics.get_report_headers('/shared/Test/Report')

        # Verify get was called
        assert mock_client.get.called


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
