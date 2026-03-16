# Error Handling Guide

This guide provides comprehensive documentation for error handling in AlmaAPITK, including exception types, HTTP status codes, Alma-specific error codes, and best practices for handling errors.

## Table of Contents

- [Exception Hierarchy](#exception-hierarchy)
- [HTTP Status Codes](#http-status-codes)
- [Alma-Specific Error Codes](#alma-specific-error-codes)
- [Error Handling Patterns](#error-handling-patterns)
- [Debugging Tips](#debugging-tips)

---

## Exception Hierarchy

AlmaAPITK provides a structured exception hierarchy for handling different types of errors.

### AlmaAPIError (Base Exception)

The base exception class for all Alma API errors. All API-related exceptions inherit from this class.

```python
from almaapitk import AlmaAPIError

class AlmaAPIError(Exception):
    """General Alma API error."""

    def __init__(self, message: str, status_code: int = None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
```

**Attributes:**
- `message` (str): Human-readable error description extracted from API response
- `status_code` (int): HTTP status code (e.g., 400, 401, 404, 500)
- `response` (requests.Response): The raw HTTP response object for detailed inspection

**When Raised:**
- HTTP responses with status code >= 400
- All API errors from Alma are wrapped in this exception

**Example:**
```python
from almaapitk import AlmaAPIClient, AlmaAPIError

client = AlmaAPIClient('SANDBOX')

try:
    response = client.get('almaws/v1/bibs/invalid_mms_id')
except AlmaAPIError as e:
    print(f"Error: {e}")
    print(f"Status Code: {e.status_code}")
    print(f"Response: {e.response.text if e.response else 'N/A'}")
```

### AlmaValidationError

Exception raised for client-side validation failures before API calls are made.

```python
from almaapitk import AlmaValidationError

class AlmaValidationError(ValueError):
    """Validation error for Alma API requests."""
    pass
```

**When Raised:**
- Missing required parameters
- Invalid parameter formats (e.g., date format validation)
- Invalid enumeration values
- Business logic validation failures

**Example:**
```python
from almaapitk import AlmaValidationError

def create_invoice(invoice_number: str, total_amount: float):
    if not invoice_number:
        raise AlmaValidationError("invoice_number is required")
    if total_amount <= 0:
        raise AlmaValidationError("total_amount must be positive")
    # ... proceed with API call
```

### CitationMetadataError

Exception raised for citation metadata enrichment failures.

```python
from almaapitk import CitationMetadataError

class CitationMetadataError(Exception):
    """Base exception for citation metadata errors."""
    pass
```

**Subclasses:**
- `PubMedError`: Raised when PubMed API fails
- `CrossrefError`: Raised when Crossref API fails

**When Raised:**
- PubMed API request failures
- Crossref API request failures
- Invalid PMID or DOI identifiers
- Network errors during metadata fetch

**Example:**
```python
from almaapitk import CitationMetadataError

try:
    request = rs.create_lending_request_from_citation(
        pmid="invalid_pmid",
        partner_code="RELAIS"
    )
except CitationMetadataError as e:
    print(f"Failed to fetch citation metadata: {e}")
except AlmaAPIError as e:
    print(f"API error after metadata fetch: {e}")
```

---

## HTTP Status Codes

### 400 Bad Request

**Description:** The request was malformed or contained invalid parameters.

**Common Causes:**
- Invalid JSON structure
- Wrong field format (e.g., wrapped vs plain string)
- Missing required fields
- Invalid date format
- Invalid code table values

**Handling:**
```python
from almaapitk import AlmaAPIError

try:
    result = acq.create_invoice_simple(
        invoice_number="INV-001",
        invoice_date="2025-01-15",  # Missing 'Z' suffix
        vendor_code="VENDOR1",
        total_amount=100.00
    )
except AlmaAPIError as e:
    if e.status_code == 400:
        logger.error(
            "Bad request - check parameters",
            error=str(e),
            suggestion="Verify date format, field formats, and required fields"
        )
```

**Prevention:**
- Always use ISO 8601 format with 'Z' suffix for dates: `YYYY-MM-DDZ`
- Validate parameters before API calls
- Check field format requirements (some fields need plain strings, others need wrapped objects)

### 401 Unauthorized

**Description:** Authentication failed - invalid or missing API key.

**Common Causes:**
- Invalid API key
- API key for wrong environment (SANDBOX key in PRODUCTION)
- Expired or revoked API key
- Missing API key environment variable

**Handling:**
```python
try:
    client = AlmaAPIClient('SANDBOX')
    client.test_connection()
except ValueError as e:
    # Environment variable not set
    print(f"Configuration error: {e}")
except AlmaAPIError as e:
    if e.status_code == 401:
        logger.error(
            "Authentication failed",
            suggestion="Check ALMA_SB_API_KEY or ALMA_PROD_API_KEY environment variables"
        )
```

**Prevention:**
- Store API keys in environment variables
- Use different keys for SANDBOX and PRODUCTION
- Test connection before operations:
  ```python
  client = AlmaAPIClient('SANDBOX')
  if not client.test_connection():
      raise RuntimeError("Cannot connect to Alma API")
  ```

### 403 Forbidden

**Description:** The API key does not have permission for the requested operation.

**Common Causes:**
- API key lacks required permissions
- Attempting to access restricted resources
- Wrong API permission scope

**Handling:**
```python
try:
    result = admin.delete_set(set_id)
except AlmaAPIError as e:
    if e.status_code == 403:
        logger.error(
            "Permission denied",
            operation="delete_set",
            set_id=set_id,
            suggestion="Verify API key has required permissions in Alma"
        )
```

**Prevention:**
- Verify API key permissions in Alma Developer Network
- Use appropriate API key scopes for operations
- Check Alma Configuration > Integrations > API Keys

### 404 Not Found

**Description:** The requested resource does not exist.

**Common Causes:**
- Invalid MMS ID, user ID, POL ID, etc.
- Resource has been deleted
- Typo in identifier
- Wrong identifier format

**Handling:**
```python
try:
    pol_data = acq.get_pol("POL-9999999")
except AlmaAPIError as e:
    if e.status_code == 404:
        logger.warning(
            "Resource not found",
            resource_type="POL",
            resource_id="POL-9999999",
            suggestion="Verify the identifier exists and is spelled correctly"
        )
        # Handle missing resource gracefully
        return None
```

**Prevention:**
- Verify identifiers before use
- Check for typos in IDs
- Use proper ID format (e.g., POL-XXXXXXX for purchase order lines)

### 429 Too Many Requests

**Description:** API rate limit exceeded.

**Common Causes:**
- More than 100 requests per minute (typical limit)
- Burst of rapid requests
- Multiple processes using same API key

**Handling:**
```python
import time

def api_call_with_retry(func, max_retries=3):
    """Retry API call with exponential backoff for rate limits."""
    for attempt in range(max_retries):
        try:
            return func()
        except AlmaAPIError as e:
            if e.status_code == 429:
                wait_time = (2 ** attempt) * 60  # Exponential backoff
                logger.warning(
                    f"Rate limit exceeded, waiting {wait_time}s",
                    attempt=attempt + 1,
                    max_retries=max_retries
                )
                time.sleep(wait_time)
            else:
                raise
    raise AlmaAPIError("Max retries exceeded for rate limit", 429)
```

**Prevention:**
- Add delays between requests: `time.sleep(0.1)`
- Implement rate limiting in application code
- Use batch operations where available
- Monitor API usage in Alma analytics

### 500 Internal Server Error

**Description:** Alma server encountered an internal error.

**Common Causes:**
- Alma server issue
- Data corruption in Alma
- Complex request that times out
- Bug in Alma API

**Handling:**
```python
try:
    result = api_call()
except AlmaAPIError as e:
    if e.status_code == 500:
        logger.error(
            "Server error",
            status_code=e.status_code,
            suggestion="Retry after short delay or contact Ex Libris support"
        )
        # Implement retry with backoff
        time.sleep(5)
        # Retry once
        result = api_call()
```

**Prevention:**
- Implement retry logic with exponential backoff
- Simplify complex requests
- Contact Ex Libris support with tracking ID for persistent issues

---

## Alma-Specific Error Codes

### Error 402459 - Invoice Not Approved Before Payment

**Full Error:**
```
Error 402459: Error while trying to retrieve invoice
```

**When It Occurs:**
- Attempting to mark an invoice as paid before it has been processed/approved

**Root Cause:**
Alma requires invoices to be processed/approved before they can be marked as paid.

**Correct Workflow:**
```python
# Step 1: Create invoice
invoice = acq.create_invoice_simple(
    invoice_number="INV-001",
    invoice_date="2025-01-15Z",
    vendor_code="VENDOR1",
    total_amount=100.00
)
invoice_id = invoice['id']

# Step 2: Add invoice lines
line = acq.create_invoice_line_simple(
    invoice_id=invoice_id,
    pol_id="POL-12347",
    price=100.00
)

# Step 3: MANDATORY - Approve invoice first
acq.approve_invoice(invoice_id)

# Step 4: Now mark as paid
acq.mark_invoice_paid(invoice_id)
```

**Handling:**
```python
try:
    acq.mark_invoice_paid(invoice_id)
except AlmaAPIError as e:
    if '402459' in str(e) or e.status_code == 400:
        logger.info("Invoice not approved, processing first")
        acq.approve_invoice(invoice_id)
        acq.mark_invoice_paid(invoice_id)
```

### Error 40166411 - Invalid Parameter

**Full Error:**
```
Error 40166411: Invalid parameter value
```

**When It Occurs:**
- Incorrect date format
- Invalid enum value
- Out-of-range numeric values

**Common Fixes:**

**Date Format:**
```python
# WRONG
receive_date = "2025-01-15"      # Missing timezone
receive_date = "01/15/2025"      # Wrong format

# CORRECT
receive_date = "2025-01-15Z"     # ISO 8601 with timezone
```

**Enum Values:**
```python
# WRONG
format_type = "Physical"         # Wrong case

# CORRECT
format_type = "PHYSICAL"         # Exact enum value
```

### Error 401875 - Department Not Found

**Full Error:**
```
Error 401875: Department not found
```

**When It Occurs:**
- Receiving an item to a non-existent department
- Invalid department code for the specified library

**Verification Steps:**
1. Check Configuration > Fulfillment > Physical Fulfillment > Departments
2. Verify department is enabled and not deleted
3. Confirm department belongs to the correct library
4. Ensure department code matches exactly (case-sensitive)

**Example:**
```python
# WRONG
acq.receive_item(
    pol_id="POL-12347",
    item_id="23123456780004146",
    department="NONEXISTENT",
    department_library="MAIN"
)

# CORRECT
acq.receive_item(
    pol_id="POL-12347",
    item_id="23123456780004146",
    department="ACQ",
    department_library="MAIN"
)
```

### Error 401871 - PO Line Not Found

**Full Error:**
```
Error 401871: PO Line not found
```

**When It Occurs:**
- POL ID doesn't exist
- POL has been closed or deleted
- Typo in POL ID

**Handling:**
```python
try:
    pol_data = acq.get_pol(pol_id)
except AlmaAPIError as e:
    if '401871' in str(e) or e.status_code == 404:
        logger.error(f"POL {pol_id} not found - verify ID exists and is not closed")
        return None
```

### Error 401877 - Failed to Receive PO Line

**Full Error:**
```
Error 401877: Failed to receive PO Line
```

**When It Occurs:**
- Item already received
- POL is in wrong state for receiving
- Item doesn't exist in POL
- POL is closed or cancelled

**Debugging:**
```python
# Check POL status first
pol_data = acq.get_pol(pol_id)
status = pol_data.get('status', {}).get('value')

if status in ['CLOSED', 'CANCELLED']:
    logger.error(f"POL {pol_id} is {status}, cannot receive")
    return

# Check if item already received
items = acq.extract_items_from_pol_data(pol_data)
for item in items:
    if item['pid'] == item_id and item.get('receive_date'):
        logger.error(f"Item {item_id} already received on {item['receive_date']}")
        return
```

### Error 400 - Fund Distribution Error

**Full Error:**
```
Error 400: Invoice line fund percentage or amount must be declared, not both and not neither.
```

**Correct Structure:**
```python
# Use EITHER percent OR amount, never both

# Correct - single fund with percent
"fund_distribution": [{
    "fund_code": {"value": "GENERIC_FUND"},
    "percent": 100
}]

# Correct - split by percentage
"fund_distribution": [
    {"fund_code": {"value": "FUND_A"}, "percent": 50},
    {"fund_code": {"value": "FUND_B"}, "percent": 50}
]

# Correct - split by amount
"fund_distribution": [
    {"fund_code": {"value": "FUND_A"}, "amount": 50.00},
    {"fund_code": {"value": "FUND_B"}, "amount": 30.00}
]

# WRONG - both amount and percent
"fund_distribution": [{
    "fund_code": {"value": "GENERIC_FUND"},
    "amount": 50.0,
    "percent": 100  # Cannot have both!
}]
```

### Error 400 - Owner Field Format (Resource Sharing)

**Full Error:**
```
Error 400: Cannot deserialize value of type `java.lang.String` from Object value
```

**When It Occurs:**
Using wrapped object format for `owner` field in lending request creation.

**Root Cause:**
The Alma API schema documentation is **incorrect** for the `owner` field. It shows a wrapped object, but the API requires a plain string.

**Correct Format:**
```python
# WRONG - causes 400 error
request_data = {
    "owner": {"value": "MAIN"}  # Wrapped format from schema
}

# CORRECT - plain string required
request_data = {
    "owner": "MAIN"  # Plain string
}

# Note: other fields DO use wrapped format
{
    "owner": "MAIN",                      # Plain string (critical!)
    "partner": {"value": "RELAIS"},       # Wrapped (correct)
    "format": {"value": "PHYSICAL"},      # Wrapped (correct)
    "citation_type": {"value": "BOOK"}    # Wrapped (correct)
}
```

### Error 404 - Partner Not Found (Resource Sharing)

**Full Error:**
```
Error 404: Partner not found: {partner_code}
```

**Verification:**
1. Check Configuration > Resource Sharing > Partners
2. Verify partner code matches exactly (case-sensitive)
3. Confirm partner is active and not deleted
4. Check partner code in both SANDBOX and PRODUCTION (may differ)

### Error 400 - Validation Failed (Lending Request)

**Full Error:**
```
Error 400: Validation failed: {field} is required and must be non-empty
```

**Mandatory Fields for Lending Requests:**
- `external_id` - Always required
- `owner` - Always required
- `partner` - Always required (via partner_code parameter)
- `format` - Always required
- `citation_type` - Required UNLESS mms_id provided
- `title` - Required UNLESS mms_id provided

**Correct Example:**
```python
# With explicit metadata
request = rs.create_lending_request(
    partner_code="RELAIS",
    external_id="EXT-001",
    owner="MAIN",
    format_type="PHYSICAL",
    title="Example Book",
    citation_type="BOOK"
)

# With MMS ID (title and citation_type optional)
request = rs.create_lending_request(
    partner_code="RELAIS",
    external_id="EXT-001",
    owner="MAIN",
    format_type="PHYSICAL",
    mms_id="991234567890123456"
)
```

---

## Error Handling Patterns

### Basic Try/Except Pattern

```python
from almaapitk import AlmaAPIClient, AlmaAPIError, AlmaValidationError
from almaapitk.alma_logging import get_logger

logger = get_logger('my_script', environment='SANDBOX')

try:
    result = acq.create_invoice_simple(
        invoice_number="INV-001",
        invoice_date="2025-01-15Z",
        vendor_code="VENDOR1",
        total_amount=100.00
    )
    logger.info("Invoice created successfully", invoice_id=result['id'])

except AlmaValidationError as e:
    # Client-side validation error - fix parameters
    logger.error("Validation failed", error=str(e))

except AlmaAPIError as e:
    # API error - handle based on status code
    logger.error(
        "API error",
        status_code=e.status_code,
        error_message=str(e)
    )
```

### Specific Error Type Handling

```python
from almaapitk import AlmaAPIError, AlmaValidationError, CitationMetadataError

try:
    # Create lending request with citation metadata
    request = rs.create_lending_request_from_citation(
        pmid="33219451",
        partner_code="RELAIS",
        owner="MAIN"
    )

except AlmaValidationError as e:
    # Missing or invalid parameters
    logger.error("Invalid parameters", error=str(e))
    raise

except CitationMetadataError as e:
    # Citation metadata fetch failed
    logger.error("Could not fetch citation metadata", error=str(e))
    # Fallback: create request with manual metadata
    request = rs.create_lending_request(
        external_id="fallback-001",
        partner_code="RELAIS",
        owner="MAIN",
        format_type="PHYSICAL",
        title="Manual Title Entry"
    )

except AlmaAPIError as e:
    # Alma API error
    if e.status_code == 404:
        logger.error("Partner not found", partner_code="RELAIS")
    elif e.status_code == 400:
        logger.error("Bad request", error_details=str(e))
    else:
        logger.error("Unexpected API error", status_code=e.status_code)
    raise
```

### Retry Logic for Rate Limits and Transient Errors

```python
import time
from almaapitk import AlmaAPIError
from almaapitk.alma_logging import get_logger

logger = get_logger('retry_logic', environment='SANDBOX')

def api_call_with_retry(func, max_retries=3, retry_status_codes=(429, 500, 502, 503, 504)):
    """
    Execute an API call with retry logic for transient errors.

    Args:
        func: Callable that makes the API request
        max_retries: Maximum number of retry attempts
        retry_status_codes: HTTP status codes that should trigger a retry

    Returns:
        Result from successful API call

    Raises:
        AlmaAPIError: If all retries fail or non-retryable error occurs
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()

        except AlmaAPIError as e:
            last_exception = e

            if e.status_code not in retry_status_codes:
                # Non-retryable error - fail immediately
                raise

            if attempt >= max_retries:
                # Max retries exceeded
                logger.error(
                    "Max retries exceeded",
                    status_code=e.status_code,
                    attempts=attempt + 1
                )
                raise

            # Calculate wait time with exponential backoff
            if e.status_code == 429:
                # Rate limit - wait longer
                wait_time = (2 ** attempt) * 60
            else:
                # Server error - shorter wait
                wait_time = (2 ** attempt) * 5

            logger.warning(
                f"Transient error, retrying in {wait_time}s",
                status_code=e.status_code,
                attempt=attempt + 1,
                max_retries=max_retries
            )
            time.sleep(wait_time)

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception

# Usage
result = api_call_with_retry(
    lambda: acq.create_invoice_simple(
        invoice_number="INV-001",
        invoice_date="2025-01-15Z",
        vendor_code="VENDOR1",
        total_amount=100.00
    )
)
```

### Logging Errors Properly

```python
from almaapitk import AlmaAPIError
from almaapitk.alma_logging import get_logger

logger = get_logger('invoice_processing', environment='SANDBOX')

def receive_item_with_logging(pol_id: str, item_id: str, department: str):
    """Receive an item with comprehensive error logging."""

    logger.info(
        "Attempting to receive item",
        pol_id=pol_id,
        item_id=item_id,
        department=department
    )

    try:
        result = acq.receive_item(
            pol_id=pol_id,
            item_id=item_id,
            department=department
        )

        logger.info(
            "Item received successfully",
            pol_id=pol_id,
            item_id=item_id,
            receive_date=result.get('receive_date')
        )
        return result

    except AlmaAPIError as e:
        # Log with full context for debugging
        logger.error(
            "Failed to receive item",
            pol_id=pol_id,
            item_id=item_id,
            department=department,
            error_code=e.status_code,
            error_message=str(e),
            # Include tracking ID if available
            tracking_id=getattr(e, 'tracking_id', None)
        )

        # Log response body for detailed debugging
        if e.response:
            try:
                response_body = e.response.json()
                logger.debug(
                    "Error response body",
                    response=response_body
                )
            except:
                pass

        raise
```

### Pre-Validation Pattern

```python
from almaapitk import AlmaValidationError
from datetime import datetime

def create_invoice_safely(
    invoice_number: str,
    invoice_date: str,
    vendor_code: str,
    total_amount: float
):
    """Create invoice with comprehensive pre-validation."""

    # Validate required fields
    if not invoice_number or not invoice_number.strip():
        raise AlmaValidationError("invoice_number is required and cannot be empty")

    if not vendor_code or not vendor_code.strip():
        raise AlmaValidationError("vendor_code is required and cannot be empty")

    # Validate numeric values
    if total_amount is None:
        raise AlmaValidationError("total_amount is required")
    if total_amount <= 0:
        raise AlmaValidationError("total_amount must be positive")

    # Validate and fix date format
    if isinstance(invoice_date, str):
        # Ensure proper format with timezone indicator
        if not invoice_date.endswith('Z'):
            invoice_date = invoice_date + 'Z'

        # Validate date format
        try:
            datetime.strptime(invoice_date.rstrip('Z'), '%Y-%m-%d')
        except ValueError:
            raise AlmaValidationError(
                f"Invalid date format: {invoice_date}. "
                "Use ISO 8601 format: YYYY-MM-DDZ"
            )

    # All validations passed - make API call
    return acq.create_invoice_simple(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        vendor_code=vendor_code,
        total_amount=total_amount
    )
```

---

## Debugging Tips

### Using Response Data for Debugging

```python
try:
    result = client.get('almaws/v1/bibs/invalid_id')
except AlmaAPIError as e:
    print(f"Status Code: {e.status_code}")
    print(f"Error Message: {e}")

    if e.response:
        # Get full response details
        print(f"Response Headers: {dict(e.response.headers)}")

        try:
            error_data = e.response.json()
            print(f"Error Structure: {error_data}")

            # Extract specific error details
            if 'errorList' in error_data:
                errors = error_data['errorList'].get('error', [])
                for err in errors:
                    print(f"  Error Code: {err.get('errorCode')}")
                    print(f"  Error Message: {err.get('errorMessage')}")
                    print(f"  Tracking ID: {err.get('trackingId')}")
        except:
            print(f"Raw Response: {e.response.text[:500]}")
```

### Common Mistakes and Solutions

| Mistake | Solution |
|---------|----------|
| Missing 'Z' in date | Use `invoice_date + 'Z'` or `datetime.strftime('%Y-%m-%dZ')` |
| Using wrapped format for owner | Use plain string: `"owner": "MAIN"` |
| Missing required fields | Check mandatory fields before API call |
| Wrong environment key | Use `ALMA_SB_API_KEY` for SANDBOX, `ALMA_PROD_API_KEY` for PRODUCTION |
| Paying invoice before approval | Always call `approve_invoice()` before `mark_invoice_paid()` |
| Both amount and percent in fund | Use EITHER `amount` OR `percent`, never both |
| Case-sensitive codes | Match exact case for department codes, partner codes, etc. |

### SANDBOX vs PRODUCTION Considerations

**SANDBOX:**
- Test all new code in SANDBOX first
- Use `ALMA_SB_API_KEY` environment variable
- Data can be freely modified
- Some features may behave differently than PRODUCTION

**PRODUCTION:**
- Always use dry-run mode first
- Use `ALMA_PROD_API_KEY` environment variable
- All changes are permanent
- Rate limits may be different

**Switching Environments:**
```python
# Initialize for SANDBOX
client = AlmaAPIClient('SANDBOX')

# Test operations...

# Switch to PRODUCTION when ready
client.switch_environment('PRODUCTION')

# Or create new client
prod_client = AlmaAPIClient('PRODUCTION')
```

### Debug Checklist

When encountering an error:

- [ ] Check error code in this guide
- [ ] Verify all required parameters are present
- [ ] Check date format (`YYYY-MM-DDZ`)
- [ ] Verify code table values exist in Alma configuration
- [ ] Check field format (wrapped vs plain string)
- [ ] Review API logs in `logs/api_requests/`
- [ ] Test in SANDBOX before PRODUCTION
- [ ] Check Alma configuration for referenced entities
- [ ] Verify API key is correct for environment
- [ ] Check for recent Alma API changes or known issues

### Getting Help

**Information to Collect:**
1. Error code and full error message
2. Tracking ID from error response
3. Request details (endpoint, parameters, body)
4. Environment (SANDBOX or PRODUCTION)
5. Timestamp of error
6. Steps to reproduce

**Support Resources:**
- Ex Libris Documentation: https://developers.exlibrisgroup.com/alma/apis/
- Ex Libris Support: Include tracking ID in support tickets
- API Logs: Check `logs/api_requests/` for request/response details
- Error Logs: Check `logs/errors/` for error context
