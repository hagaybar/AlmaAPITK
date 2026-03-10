#!/usr/bin/env python3
"""
Quick test script for logging implementation.

Tests:
- Basic logging (info, debug, warning, error, critical)
- Custom context fields
- Sensitive data redaction
- File and console output
- JSON and text formatters
"""

from src.alma_logging import get_logger

def test_basic_logging():
    """Test basic logging functionality."""
    print("=" * 70)
    print("TEST 1: Basic Logging")
    print("=" * 70)

    logger = get_logger('acquisitions', environment='SANDBOX')

    logger.info("Testing INFO level logging")
    logger.debug("Testing DEBUG level logging")
    logger.warning("Testing WARNING level logging")
    logger.error("Testing ERROR level logging")
    logger.critical("Testing CRITICAL level logging")

    print("\n✓ Basic logging test complete\n")


def test_context_fields():
    """Test logging with custom context fields."""
    print("=" * 70)
    print("TEST 2: Context Fields")
    print("=" * 70)

    logger = get_logger('acquisitions', environment='SANDBOX')

    logger.info(
        "Creating invoice",
        invoice_number="INV-2025-001",
        vendor="RIALTO",
        total_amount=180.0,
        currency="ILS"
    )

    logger.info(
        "Invoice created successfully",
        invoice_id="35925532970004146",
        invoice_number="INV-2025-001",
        status="WAITING_TO_BE_SENT"
    )

    logger.error(
        "Failed to create invoice line",
        invoice_number="INV-2025-002",
        error_code="60260",
        error_message="License Term Type valid values"
    )

    print("\n✓ Context fields test complete\n")


def test_sensitive_data_redaction():
    """Test automatic redaction of sensitive data."""
    print("=" * 70)
    print("TEST 3: Sensitive Data Redaction")
    print("=" * 70)

    logger = get_logger('api_client', environment='SANDBOX')

    # This should redact the apikey value
    logger.debug(
        "API Request",
        method="POST",
        endpoint="almaws/v1/acq/invoices",
        headers={
            "apikey": "l8xxSHOULD_BE_REDACTED_xxxxxx",
            "Content-Type": "application/json"
        },
        params={"op": "paid"}
    )

    logger.debug(
        "Authentication",
        username="testuser",
        password="THIS_SHOULD_BE_REDACTED",
        token="ALSO_SHOULD_BE_REDACTED"
    )

    print("\n✓ Sensitive data redaction test complete\n")


def test_api_logging():
    """Test API request/response logging methods."""
    print("=" * 70)
    print("TEST 4: API Request/Response Logging")
    print("=" * 70)

    logger = get_logger('api_client', environment='SANDBOX')

    # Test log_request
    logger.log_request(
        'POST',
        'almaws/v1/acq/invoices',
        params={'op': 'paid'},
        headers={'Content-Type': 'application/json'},
        body={'invoice_number': 'INV-001'}
    )

    # Test log_response (mock response object)
    class MockResponse:
        status_code = 200

    logger.log_response(MockResponse(), duration_ms=234.5)

    # Test log_error
    try:
        raise ValueError("Test error for logging")
    except ValueError as e:
        logger.log_error(e, invoice_number="INV-001", operation="create")

    print("\n✓ API logging test complete\n")


def test_multiple_domains():
    """Test logging from multiple domains."""
    print("=" * 70)
    print("TEST 5: Multiple Domains")
    print("=" * 70)

    acq_logger = get_logger('acquisitions', environment='SANDBOX')
    users_logger = get_logger('users', environment='SANDBOX')
    bibs_logger = get_logger('bibs', environment='SANDBOX')

    acq_logger.info("Acquisitions domain log", pol_id="POL-12350")
    users_logger.info("Users domain log", user_id="test@example.com")
    bibs_logger.info("Bibs domain log", mms_id="9933853977604146")

    print("\n✓ Multiple domains test complete\n")


def main():
    """Run all logging tests."""
    print("\n")
    print("*" * 70)
    print(" AlmaAPITK Logging Implementation Test Suite")
    print("*" * 70)
    print("\nThis test will create logs in: logs/api_requests/<date>/")
    print("Console output uses colored text formatter")
    print("File output uses JSON Lines formatter\n")

    test_basic_logging()
    test_context_fields()
    test_sensitive_data_redaction()
    test_api_logging()
    test_multiple_domains()

    print("=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)
    print("\nCheck log files in logs/api_requests/")
    print("Example: cat logs/api_requests/$(date +%Y-%m-%d)/acquisitions.log | jq\n")


if __name__ == "__main__":
    main()
