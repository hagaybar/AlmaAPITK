# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AlmaAPITK is a Python toolkit for interacting with the Alma ILS (Integrated Library System) API. It provides a structured approach to API operations with domain-specific classes and utilities.

## Environment Setup

### Prerequisites
- Python 3.12+
- Poetry for dependency management
- Environment variables for API keys:
  - `ALMA_SB_API_KEY` - Sandbox API key
  - `ALMA_PROD_API_KEY` - Production API key

### Installation and Setup
```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Test connection
python -c "from src.client.AlmaAPIClient import AlmaAPIClient; client = AlmaAPIClient('SANDBOX'); client.test_connection()"
```

## Architecture Overview

### Core Components

1. **AlmaAPIClient** (`src/client/AlmaAPIClient.py`)
   - Main API client providing HTTP methods (GET, POST, PUT, DELETE)
   - Environment management (SANDBOX/PRODUCTION)
   - Authentication handling and connection testing
   - Base class for all API interactions

2. **Domain Classes** (`src/domains/`)
   - **Admin**: Handles sets and administrative operations (BIB_MMS and USER sets)
   - **Users**: User management operations, email updates, expiry date processing
   - **Bibs**: Bibliographic records operations
   - **Acquisition**: Acquisition-related operations
   - **Analytics**: Analytics report fetching (PRODUCTION only, read-only)
   - **ResourceSharing**: Resource sharing lending and borrowing requests via Partners API

3. **Projects** (`src/projects/`)
   - **update_expired_user_emails_2.py**: Script for updating email addresses of expired users (latest version)
   - **Alma_File_Loader_from_Set.py**: Utility for loading files from Alma sets

4. **Utilities** (`src/utils/`)
   - **tsv_generator.py**: TSV file generation utilities

### Key Design Patterns

- **Client-Domain Pattern**: AlmaAPIClient serves as the foundation, domain classes use it for specific operations
- **Environment-Aware**: All classes support SANDBOX/PRODUCTION environments
- **Response Wrapping**: AlmaResponse class provides consistent response handling
- **Error Hierarchy**: AlmaAPIError, AlmaValidationError, AlmaRateLimitError for specific error types

## Python Development Standards

**📘 For all Python coding, refactoring, and architectural decisions → use the `python-dev-expert` skill**

The `python-dev-expert` skill provides:
- ✅ Code quality standards (PEP 8, type hints, docstrings, logic density)
- ✅ Refactoring workflows (code smells, extraction patterns, 50-line max per function)
- ✅ Architecture patterns (Client-Domain, error hierarchy, composition over inheritance)
- ✅ Code templates (domain classes, project scripts, tests, utilities)
- ✅ API client patterns (pagination, rate limiting, error handling, logging)

**The skill auto-triggers** when working on Python code. You can also explicitly invoke it for code reviews.

## Claude's Role and Organization Focus

### Primary Role
- Act as a senior Python developer familiar with API clients and library systems
- **Use `python-dev-expert` skill** for all Python coding decisions
- **Proactively suggest code organization improvements** when working with any file
- Help identify and eliminate code duplication
- Focus on Alma API domain knowledge and project-specific patterns

### Git Integration and Commit Management
- **Always commit significant changes** - Claude has full permission to make commits without asking
- **Write clear, descriptive commit messages** following conventional commit format when possible
- **Commit granularly** - separate logical changes into individual commits rather than bundling everything together
- **Commit before and after major refactoring** to create clean checkpoints

#### Commit Message Standards

**Detailed Messages for Future Understanding**: Commit messages must provide sufficient detail for future Claude Code sessions to understand what was changed and why. These messages serve as documentation for code evolution and help Claude understand the context of changes when examining commit history.

**Format and Content Guidelines**:
- Use present tense and imperative mood: "Add feature" not "Added feature"
- Include comprehensive summary with specific implementation details
- List major changes using bullet points or numbered lists
- Explain the reasoning behind changes when not obvious
- Reference specific files, functions, or classes that were modified
- Include before/after context for refactoring changes
- Document any breaking changes or compatibility impacts

**Examples of Detailed Commit Messages**:

```
Add domain filtering functionality to email validation system

- Implement is_domain_allowed() method in EmailUpdateScript class
- Add allowed_domains configuration parameter with @ prefix validation
- Filter users by email domain before processing in validate_user_email_structure()
- Add domain_filtered flag to user results for tracking exclusions
- Update CLI validation to check allowed_domains format (must start with @)
- Maintain backward compatibility - no domain filter means allow all domains

Files modified: update_expired_user_emails_2.py (lines 442-472, 341-349)
Configuration: email_update_config.json now supports "allowed_domains": ["@university.edu"]
```

```
Refactor inline imports to module level across all domain classes

## Import Organization Changes
- Move all inline imports to top-level following PEP 8 standards
- Organize imports alphabetically within standard library, third-party, and local groups
- Remove duplicate import statements and redundant inline imports

## Files Modified
- src/domains/users.py: Move logging, time, datetime imports from functions to module level
- src/domains/admin.py: Consolidate json, time, datetime imports, add Users import for line 652
- src/domains/acquisition.py: Remove duplicate AlmaAPIClient import, organize alphabetically  
- src/domains/bibs.py: Remove obsolete commented base_client import, organize imports

## Code Quality Impact
- Improves import visibility and follows Python conventions
- Eliminates import-time overhead in frequently called functions
- Makes dependencies explicit at module level for better maintainability
```

**Key Requirements**:
1. **Specificity**: Mention exact files, line numbers, function names when relevant
2. **Context**: Explain why changes were made, not just what was changed
3. **Impact**: Describe how changes affect functionality or architecture  
4. **Traceability**: Enable future Claude sessions to understand the evolution
5. **Completeness**: Cover all significant modifications in the commit

#### When to Commit and Push
1. **Before starting any significant work** - commit current state as checkpoint
2. **After completing a logical unit of work** - new feature, bug fix, refactor, cleanup
3. **Before and after file removals or renames** - preserve history
4. **After updating documentation** - especially claude.md changes
5. **After test additions or modifications**
6. **When user says "commit" or "save progress"** - interpret as instruction to commit current changes

**Standard Workflow**: Every commit should be immediately followed by `git push origin main` to keep GitHub repository synchronized with local changes. This ensures work is backed up and visible to collaborators immediately.

#### Manual Commit Commands
Claude should recognize these phrases as instructions to commit immediately:
- "commit" or "commit this" or "commit changes"
- "save progress" or "save this"
- "checkpoint" or "create checkpoint"
- "git commit" (explicit git instruction)

When any of these commands are used, Claude should:
1. Review what changes have been made since last commit
2. Create an appropriate commit message based on the changes
3. Execute the git commit
4. Push the commit to GitHub with `git push origin main`
5. Confirm both commit and push were successful

#### What NOT to commit
- Temporary debug print statements
- API keys or sensitive configuration
- Large binary files without good reason
- Half-finished features that break existing functionality

### Code Organization Standards

**See `python-dev-expert` skill for code organization, refactoring, and cleanliness standards.**

#### Project-Specific File Organization
- Configuration files → `config/` directory
- Test data and samples → `test_data/` or `samples/`
- Remove obsolete file versions (e.g., when `_2` version exists, remove original)

## Development Commands

### Running Scripts
```bash
# Run email update script (latest version)
python src/projects/update_expired_user_emails_2.py --set-id 12345678900004146 --environment SANDBOX

# Run with configuration file
python src/projects/update_expired_user_emails_2.py --config config.json --live

# Run with TSV input
python src/projects/update_expired_user_emails_2.py --tsv users.tsv --pattern "expired-{user_id}@university.edu"
```

### Testing
```bash
# Run individual test scripts
python src/tests/test_users_script.py
python src/tests/test_sets_ret.py
python src/tests/acquisitions_test_script.py

# Test API connection
python alma_client_test.py
```

## Coding Standards and Preferences

### Python Style Guidelines
- Follow PEP 8 strictly
- Use type hints for all function parameters and return values
- Prefer composition over inheritance where appropriate
- Keep functions focused and single-purpose (max 50 lines)
- Use descriptive variable names that reflect the Alma API domain (e.g., `bib_mms_id`, `user_primary_id`)

### API Client Patterns
- All API calls should go through AlmaAPIClient methods
- New domain classes should follow the existing pattern (inherit logging, use client instance)
- Always handle rate limiting and provide meaningful error messages
- Include request/response logging for debugging

### Logging Requirements

**IMPORTANT**: All test scripts and production code MUST include comprehensive logging.

#### Logging Infrastructure
The project includes a comprehensive logging system located in `src/logging/`:
- **Automatic API key redaction** - Sensitive data never appears in logs
- **Request/response logging** - Full HTTP details with timing
- **Error tracking** - Stack traces and context for debugging
- **Domain-specific logs** - Separate logs for acquisitions, users, bibs, admin
- **JSON format** - Machine-parseable structured logs
- **Git-safe** - All logs are gitignored and never committed

#### Using the Logger

**Import and Initialize**:
```python
from src.logging import get_logger

# In domain classes
class Acquisitions:
    def __init__(self, client):
        self.client = client
        self.logger = get_logger('acquisitions', client.environment)

# In test scripts
logger = get_logger('test_invoice_creation', environment='SANDBOX')
```

**Log Operational Events**:
```python
# Log method entry with parameters
self.logger.info(
    "Creating invoice",
    invoice_number=invoice_number,
    vendor_code=vendor_code,
    total_amount=total_amount
)

# Log success with results
self.logger.info(
    "Invoice created successfully",
    invoice_id=result['id'],
    invoice_number=invoice_number
)
```

**Log Errors with Full Context**:
```python
try:
    result = self.create_invoice(...)
except AlmaAPIError as e:
    self.logger.error(
        "Failed to create invoice",
        invoice_number=invoice_number,
        error_code=e.status_code,
        error_message=str(e),
        tracking_id=getattr(e, 'tracking_id', None)
    )
    raise
```

**Log API Requests/Responses** (in AlmaAPIClient):
```python
# Before request
self.logger.log_request('POST', endpoint, params=params, body=data)

# After response
self.logger.log_response(response, duration_ms=elapsed_time * 1000)
```

#### What to Log

**✅ ALWAYS LOG**:
- Method entry with key parameters (invoice number, POL ID, user ID)
- Successful operations with result identifiers
- API errors with full context (error code, message, tracking ID)
- Validation failures with specific reasons
- Important state changes (invoice approved, item received)
- Test execution start/end with parameters
- Test results (pass/fail) with details

**❌ NEVER LOG**:
- API keys (automatically redacted by logger)
- Passwords or tokens (automatically redacted)
- Full API responses containing personal data (use summary instead)

#### Log Levels Guide

| Level    | When to Use                                | Example                              |
|----------|--------------------------------------------|--------------------------------------|
| DEBUG    | Detailed diagnostic info, API responses    | `logger.debug("POL data", pol=data)` |
| INFO     | Normal operations, success messages        | `logger.info("Invoice created")`     |
| WARNING  | Recoverable issues, retries                | `logger.warning("Retrying request")` |
| ERROR    | Operation failures, API errors             | `logger.error("Create failed")`      |
| CRITICAL | System failures, cannot continue           | `logger.critical("Auth failed")`     |

#### Log Files Location

All logs are stored in `logs/` directory (gitignored):
```
logs/
├── api_requests/YYYY-MM-DD/
│   ├── acquisitions.log    # Acquisitions API operations
│   ├── users.log            # User operations
│   └── bibs.log             # Bibliographic operations
├── errors/YYYY-MM-DD.log    # All errors across domains
├── performance/             # Performance metrics
└── tests/YYYY-MM-DD/        # Test execution logs
```

#### Configuration

Default configuration works out-of-the-box. For custom settings:
```bash
# Copy example configuration
cp config/logging_config.example.json config/logging_config.json

# Customize log levels, rotation, redaction patterns
```

See `src/logging/README.md` and `src/logging/docs/LOGGING_IMPLEMENTATION_PLAN.md` for complete documentation.

#### Security Notes
- **Never commit logs to GitHub** - they may contain API responses with sensitive data
- Logs are automatically excluded via `.gitignore`
- API keys and tokens are automatically redacted from all logs
- Review logs before sharing to ensure no sensitive data exposure

### Configuration Management
- Never hardcode API keys or sensitive data
- Use environment variables for all configuration
- Provide clear examples in comments without actual values
- Support both sandbox and production environments

## Script Template Standards

### Use update_expired_user_emails_2.py as Template
This script demonstrates the ideal structure for new project scripts:

#### Required Components
1. **Comprehensive CLI with argparse**
   - Multiple input methods (set ID, config file, data file)
   - Environment selection with safety confirmations
   - Help text with usage examples

2. **Safety-First Design**
   - Dry-run as default mode
   - Explicit confirmation for production operations
   - Input validation at multiple levels
   - Comprehensive error tracking

3. **Logging and Results**
   - File and console logging with timestamps
   - Structured result tracking and CSV export
   - Progress indicators for long operations
   - Backup logging of original data before changes

4. **Class-Based Organization**
   - Main script logic in a dedicated class
   - Clear separation of concerns (configuration, processing, reporting)
   - Type hints throughout
   - Comprehensive docstrings

#### CLI Pattern to Follow
```python
# Always include these argument patterns:
parser.add_argument("--config", help="JSON configuration file")
parser.add_argument("--environment", choices=["SANDBOX", "PRODUCTION"], default="SANDBOX")
parser.add_argument("--dry-run", action="store_true", default=True)
parser.add_argument("--live", action="store_true", help="Disable dry-run mode")
```

## Development Context

**For code templates and development workflows → see `python-dev-expert` skill**

### Project-Specific Development Principles
- **Test in SANDBOX first** before PRODUCTION
- **Use AlmaResponse wrapper** for all API responses
- **Follow AlmaAPIError hierarchy**: AlmaAPIError, AlmaValidationError, AlmaRateLimitError
- **Use src/logging/ framework** (never print statements)
- **Include dry-run mode** in operational scripts
- **Method naming**: `get_*`, `update_*`, `create_*`, `delete_*`

### Alma API Response Handling
- Use `AlmaResponse` wrapper for consistent handling
- Handle pagination using `_fetch_all_pages()` pattern (see python-dev-expert templates)
- Include progress indicators for operations >100 items

## Project-Specific Organization Notes

**For general code organization and refactoring guidance, see `python-dev-expert` skill.**

### Known File Cleanup Tasks
- **Remove obsolete script versions** when newer versions exist with additional functionality
- **Consolidate configuration files** in `config/` directory
- **Archive old test data** to `test_data/archive/` when no longer needed

## Archived Advanced Features Documentation

### BaseAPIClient Advanced Patterns (Removed 2025-09-10)

The `src/core/base_client.py` file contained enterprise-grade API client patterns that were removed due to missing dependencies but contained valuable architectural improvements over the current `AlmaAPIClient.py`. These patterns should be considered for future enhancement cycles:

#### Advanced Rate Limiting Implementation
```python
# Sophisticated request tracking with rolling window
_request_times: List[float] = []
DEFAULT_RATE_LIMIT = 100  # requests per minute

def _enforce_rate_limit(self) -> None:
    now = time.time()
    # Remove requests older than 1 minute
    self._request_times = [t for t in self._request_times if now - t < 60]
    
    if len(self._request_times) >= self._rate_limit:
        sleep_time = 60 - (now - self._request_times[0])
        if sleep_time > 0:
            time.sleep(sleep_time)
    
    self._request_times.append(now)
```

#### Retry Logic with Exponential Backoff
```python
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# In request method:
if (response.status_code in self.RETRY_STATUS_CODES and retry_count < self.MAX_RETRIES):
    delay = self.RETRY_DELAY * (2 ** retry_count)  # Exponential backoff
    time.sleep(delay)
    return self._make_request(method, url, headers, data, params, retry_count + 1)
```

#### Enhanced Error Handling with Alma-Specific Mapping
```python
class AlmaRateLimitError(AlmaAPIError):
    """Exception raised when API rate limit is exceeded."""
    pass

class AlmaAuthenticationError(AlmaAPIError): 
    """Exception raised when API authentication fails."""
    pass

def _handle_error_response(self, response, request_method, url):
    # Extract Alma-specific error information from errorList structure
    if isinstance(error_data, dict) and 'errorList' in error_data:
        errors = error_data['errorList'].get('error', [])
        if errors:
            error_details = errors[0] if isinstance(errors, list) else errors
            error_message += f": {error_details.get('errorMessage', 'Unknown error')}"
    
    # Map to specific exception types
    if status_code == 401:
        raise AlmaAuthenticationError(error_message, status_code, error_data)
    elif status_code == 429:
        raise AlmaRateLimitError(error_message, status_code, error_data)
```

#### Request Timeout Protection
```python
# 30-second timeout on all requests
response = requests.get(url, headers=headers, params=params, timeout=30)
```

#### Configuration Abstraction Pattern
The file attempted to use external configuration and logger managers:
```python
# Pattern for future configuration management:
from archived.config_manager import ConfigManager
from archived.logger_manager import LoggerManager

def __init__(self, config_manager: ConfigManager, logger_manager: LoggerManager):
    self.config_manager = config_manager
    self.logger = logger_manager.get_logger()
    self.base_url = self.config_manager.get_base_url()
    self.headers = self.config_manager.get_headers()
```

#### Removal Reasons
1. **Missing Dependencies**: Required `archived.config_manager` and `archived.logger_manager` modules that no longer exist
2. **Zero Active Usage**: Only commented reference in `bibs.py`, no active imports
3. **Cannot Function**: Import failures prevent instantiation
4. **Functionality Duplicated**: Current `AlmaAPIClient.py` provides working equivalent
5. **Incomplete Migration**: Represents partial architectural upgrade that was never completed

#### Future Enhancement Recommendations
These patterns should be integrated into `AlmaAPIClient.py` during planned architectural improvements:
1. **Implement rolling window rate limiting** instead of current basic protection
2. **Add retry logic with exponential backoff** for resilient API calls
3. **Enhance error classes** with Alma-specific error types
4. **Add configurable timeouts** with sensible defaults
5. **Consider configuration manager** for complex deployment scenarios

## Library System Domain Knowledge

When working with Alma API concepts, remember:
- **MMS ID**: Bibliographic record identifier
- **User Primary ID**: Unique user identifier in Alma
- **Sets**: Collections of records (BIB_MMS or USER types)
- **Holdings**: Physical/electronic item information
- **Portfolios**: Electronic resource access points
- **POL (Purchase Order Line)**: Individual line items in purchase orders containing item and pricing information
- **Item**: Physical or electronic items associated with POLs, tracked through acquisition to receiving

## ⚠️ CRITICAL: Prevent Duplicate Invoices/Payments (MUST READ)

**INCIDENT**: On 2025-10-23, duplicate payment occurred for POL-12352. Two invoices were created and BOTH paid for the same POL, resulting in 50.00 ILS paid for a single 25.00 ILS order. See `INCIDENT_REPORT_DUPLICATE_PAYMENT_POL12352.md` for full details.

### MANDATORY Pre-Flight Checks

**Before ANY invoice creation or payment, you MUST:**

```python
# ✅ RULE 1: ALWAYS check for existing invoices BEFORE creating new one
check = acq.check_pol_invoiced(pol_id)
if check['is_invoiced']:
    print(f"⚠️ STOP! POL {pol_id} already has {check['invoice_count']} invoice(s)")
    for inv in check['invoices']:
        print(f"  - Invoice {inv['invoice_number']}")
        print(f"    Status: {inv['invoice_status']} / Payment: {inv['payment_status']}")
    # REVIEW existing invoices - DO NOT create new one
    # USE existing invoice instead
else:
    # Only NOW is it safe to create new invoice
    invoice = acq.create_invoice_simple(...)

# ✅ RULE 2: NEVER skip approval step
invoice = acq.create_invoice_simple(...)
line = acq.create_invoice_line_simple(...)
processed = acq.approve_invoice(invoice_id)  # MANDATORY - do not skip!
paid = acq.mark_invoice_paid(invoice_id)     # Includes automatic protection

# ❌ RULE 3: When error occurs, FIX existing invoice - DON'T create new one
if payment_fails_with_error_402459:
    # CORRECT: Fix the existing invoice
    acq.approve_invoice(existing_invoice_id)  # Process it first
    acq.mark_invoice_paid(existing_invoice_id)  # Then pay

    # WRONG: Create new invoice (causes duplicate!)
    # new_invoice = acq.create_invoice_simple(...)  # ✗ DON'T DO THIS

# ✅ RULE 4: Trust the protection - do NOT bypass
try:
    result = acq.mark_invoice_paid(invoice_id)  # Has automatic protection
except AlmaAPIError as e:
    # Protection blocked payment for good reason
    print(f"Payment prevented: {e}")
    # Review the error - do NOT use force=True
```

### Why This Matters

Duplicate invoices cause:
- **Financial errors**: Overpayment from wrong fund
- **System corruption**: Multiple invoice records for single order
- **Manual cleanup**: Library staff must reconcile accounts
- **Data integrity**: Incorrect fund balances and expenditures

### Protection Layers Implemented

1. **`check_pol_invoiced()`** - Detects existing invoices for POL
2. **`check_invoice_payment_status()`** - Checks if invoice already paid
3. **`mark_invoice_paid()`** - Automatic duplicate payment protection (default)

All protection is AUTOMATIC by default. You must explicitly use `force=True` to bypass (never recommended).

## Alma Resource Sharing API Reference

### Official Documentation
- **Partners API Base URL**: `https://developers.exlibrisgroup.com/alma/apis/partners/`
- **API Docs**: `https://developers.exlibrisgroup.com/alma/apis/`
- **Schema Reference**: `https://developers.exlibrisgroup.com/alma/apis/xsd/rest_user_resource_sharing_request.xsd`
- **OpenAPI/Swagger**: Available for download at developers.exlibrisgroup.com

### Key Resource Sharing Endpoints

#### Lending Requests (Partners API)

**Create Lending Request**
```
POST /almaws/v1/partners/{partner_code}/lending-requests
```
- Creates a new lending request from a partner institution
- Represents a partner's request to borrow material from your library
- Returns created request with generated request_id

**Retrieve Lending Request**
```
GET /almaws/v1/partners/{partner_code}/lending-requests/{request_id}
```
- Retrieves complete details of an existing lending request
- Returns full request object with current status

### Data Object Structure

**Lending Request Object Key Fields**:

**Mandatory Fields (for creation)**:
- `external_id`: string - External identifier for the request (mandatory for creation)
- `owner`: object - Resource sharing library code (mandatory)
  - `value`: Library code (e.g., "MAIN")
- `partner`: object - Partner institution code (mandatory)
  - `value`: Partner code (e.g., "RELAIS", "ILL_PARTNER")
- `format`: object - Request format (mandatory)
  - `value`: "PHYSICAL" or "DIGITAL"
- `citation_type`: object - Resource type (mandatory unless mms_id supplied)
  - `value`: "BOOK", "JOURNAL", etc.
- `title`: string - Resource title (mandatory unless mms_id supplied)

**Optional Fields**:
- `mms_id`: object - Alma catalog record ID if item exists
  - `value`: MMS ID (e.g., "991234567890123456")
- `request_id`: string - System-generated identifier (output only)
- `status`: object - Current workflow status
  - `value`: Status code (e.g., "REQUEST_CREATED_LEN")
- `author`: string - Resource author
- `isbn`: string - ISBN for books
- `issn`: string - ISSN for journals
- `publisher`: string - Publisher name
- `publication_date`: string - Publication year
- `edition`: string - Edition information
- `volume`: string - Volume number (journals)
- `issue`: string - Issue number (journals)
- `pages`: string - Page range
- `doi`: string - Digital Object Identifier
- `pmid`: string - PubMed ID
- `call_number`: string - Library call number
- `oclc_number`: string - OCLC number
- `requested_media`: object - Media description
- `preferred_send_method`: object - Preferred delivery method
- `pickup_location`: object - Delivery location
- `last_interest_date`: string - Need-by date (ISO format)
- `level_of_service`: object - Service level (e.g., Rush)
- `copyright_status`: object - Copyright status
- `rs_notes`: array - Notes array with note objects
- `allow_other_formats`: boolean - Accept alternative formats (default: false)

### Validation Rules

**Critical Validation Requirements**:

1. **external_id** is mandatory when creating a lending request
2. **owner** is mandatory for lending requests (must be resource sharing library code)
3. **partner** is mandatory when creating a lending request (must be partner code)
4. **format** is mandatory (controlled by RequestFormats code table)
5. **citation_type** is mandatory when creating a lending request UNLESS mms_id is supplied
6. **title** is mandatory UNLESS mms_id is supplied

**Field Value Wrapping**:
- Code table fields must be wrapped in dict with 'value' key:
  - `owner`, `partner`, `format`, `citation_type`, `status`
  - `requested_media`, `preferred_send_method`, `pickup_location`
  - `level_of_service`, `copyright_status`, `requested_language`

**Examples**:
```python
# Correct format:
{"format": {"value": "PHYSICAL"}}

# Incorrect format (will cause validation error):
{"format": "PHYSICAL"}
```

### Implementation in ResourceSharing Domain

**Location**: `src/domains/resource_sharing.py`

**Available Methods**:
1. **`create_lending_request()`** - Create new lending request with validation
2. **`get_lending_request()`** - Retrieve lending request by ID
3. **`get_request_summary()`** - Extract key information for display

**Basic Usage Example**:
```python
from src.client.AlmaAPIClient import AlmaAPIClient
from src.domains.resource_sharing import ResourceSharing

# Initialize
client = AlmaAPIClient('SANDBOX')
rs = ResourceSharing(client)

# Create lending request
request = rs.create_lending_request(
    partner_code="RELAIS",
    external_id="EXT-2025-001",
    owner="MAIN",
    format_type="PHYSICAL",
    title="Introduction to Library Science",
    citation_type="BOOK",
    author="Smith, John A.",
    isbn="978-0-123456-78-9",
    publisher="Academic Press"
)

print(f"Created request: {request['request_id']}")

# Retrieve lending request
retrieved = rs.get_lending_request(
    partner_code="RELAIS",
    request_id=request['request_id']
)

# Get summary
summary = rs.get_request_summary(retrieved)
print(f"Title: {summary['title']}")
print(f"Status: {summary['status']}")
```

**Advanced Usage with MMS ID**:
```python
# Create request for known catalog item
request = rs.create_lending_request(
    partner_code="PARTNER_01",
    external_id="EXT-2025-002",
    owner="MAIN",
    format_type="DIGITAL",
    title="Advanced Cataloging",
    mms_id="991234567890123456",  # Item in catalog
    level_of_service={"value": "Rush"}
)
# When mms_id is provided, citation_type is optional
```

**Validation Error Handling**:
```python
try:
    request = rs.create_lending_request(
        partner_code="PARTNER_01",
        external_id="",  # Missing - will fail
        owner="MAIN",
        format_type="PHYSICAL",
        title="Test Book"
    )
except ValueError as e:
    print(f"Validation error: {e}")
    # Output includes helpful message about missing fields
```

### Testing

**Test Script**: `src/tests/test_resource_sharing_lending.py`

**Run Tests**:
```bash
# Dry-run test (no actual API calls)
python src/tests/test_resource_sharing_lending.py --dry-run

# Live test (creates requests in SANDBOX)
python src/tests/test_resource_sharing_lending.py --live

# Test with custom partner and owner
python src/tests/test_resource_sharing_lending.py --live --partner CUSTOM_PARTNER --owner BRANCH_LIB

# Test validation errors
python src/tests/test_resource_sharing_lending.py --live --test-validation
```

**Test Coverage**:
- Basic physical lending request creation
- Journal article request creation
- Request retrieval by ID
- Validation error handling
- Summary helper functionality

### Critical API Behavior Insights (Discovered 2025-12-24)

**Real-World Testing with SANDBOX Data**

Testing with actual lending request (ID: 35889547910004146, External ID: "test primo 200825") revealed important API behaviors not documented in schema:

#### API Input/Output Asymmetry ⚠️

**The `owner` field format - Schema Documentation Error** ⚠️

**CRITICAL DISCOVERY (2025-12-24)**: The official Alma API schema documentation is **WRONG** about owner field format!

```python
# SCHEMA DOCUMENTATION SAYS (INCORRECT):
request_data = {
    "owner": {"value": "AS1"},  # ❌ Schema shows wrapped - causes 400 error!
}

# API REALITY (CORRECT):
request_data = {
    "owner": "AS1",  # ✅ Plain string required for CREATE
}

# RETRIEVE ALSO RETURNS:
response = {
    "owner": "AS1",  # ✅ Plain string in responses
}
```

**Testing confirmed:**
- Sending wrapped format `{"value": "AS1"}` causes **400 BAD_REQUEST** error:
  ```
  Cannot deserialize value of type `java.lang.String` from Object value
  ```
- Sending plain string `"AS1"` **succeeds** (tested, verified, working)
- Other fields (partner, format, citation_type) ARE wrapped correctly as documented

**Why this matters:**
- Schema documentation at https://developers.exlibrisgroup.com/alma/apis/xsd/ is incorrect for this field
- Our `create_lending_request()` now correctly sends plain string
- Our `_validate_lending_request_data()` now expects plain string
- **No asymmetry** - owner is ALWAYS plain string (both CREATE and RETRIEVE)

**Recommendation**: When implementing UPDATE operations, use plain string for owner field.

#### Additional Fields Not in Schema Documentation

Real API responses include many undocumented fields:

**Operational Metadata:**
- `printed`: boolean - Whether request has been printed
- `reported`: boolean - Whether request has been reported
- `has_active_notes`: boolean - Quick check for notes without parsing array
- `created_time`: string - Precise ISO timestamp (vs `created_date`)
- `last_modified_time`: string - Precise ISO timestamp

**Item Integration:**
- `barcode`: string - Physical item barcode (e.g., "2239409-10")
  - **Very useful** - links request to actual physical item
  - Not mentioned in schema but appears in SHIPPED requests
- `mms_id`: string - Alma catalog record ID
  - Shows request is linked to catalog item
  - Example: "990022394090204146"

**Communication:**
- `text_email`: string - Contact email for request
  - Example: "requester@example.com"
  - Useful for automated notifications

**Fulfillment Details:**
- `supplied_format`: object - What was actually supplied vs requested
  - Can differ from `format` (what was requested)
  - Structure: `{"value": "PHYSICAL", "desc": "Physical"}`
- `shipping_cost`: object - Actual cost tracking
  - Structure: `{"sum": 0, "currency": {"value": "ILS", "desc": "New Israeli Sheqel"}}`
  - Always present even if zero

**Workflow Fields:**
- `user_request`: object - Empty dict in lending requests (used for borrowing)
- `level_of_service`: object - May have empty desc: `{"desc": ""}`
- `copyright_status`: object - May be empty dict `{}`
- `rs_note`: array - Notes array (may be empty)

#### Real Status Values Observed

**Documented status** "REQUEST_CREATED_LEN" vs **actual statuses** in production:
- `SHIPPED_PHYSICALLY` - Item physically shipped to partner
- Other statuses exist based on workflow configuration

#### Field Format Patterns

**Consistent Wrapping (value/desc):**
- `partner`: Always wrapped with link
- `format`: Always wrapped
- `citation_type`: Always wrapped
- `status`: Always wrapped
- `supplied_format`: Always wrapped

**Always Plain String** (despite schema docs showing wrapped):
- `owner`: **ALWAYS plain string** (schema docs wrong - wrapped format causes 400 error!)
- `requested_media`: **Plain string** code (e.g., "7")

**Always Plain Values:**
- `title`, `author`, `year`: Plain strings
- `external_id`, `request_id`: Plain strings
- `barcode`: Plain string
- `text_email`: Plain string
- Boolean flags: `printed`, `reported`, `allow_other_formats`

#### Date Format Precision

```json
{
  "created_date": "2025-08-20Z",           // Day precision - what we send
  "created_time": "2025-08-20T05:42:24.143Z",  // Millisecond precision - Alma internal
  "last_modified_date": "2025-09-18Z",
  "last_modified_time": "2025-09-18T11:10:20.491Z"
}
```

Both `*_date` and `*_time` fields are returned for creation and modification tracking.

#### Partner Code Display Names

Partner codes have internal codes vs display names:
```json
"partner": {
  "value": "ANC",           // Internal code (use in API calls)
  "desc": "ANCA-TEST",      // Display name (for UI)
  "link": "https://api-eu.hosted.exlibrisgroup.com/almaws/v1/partners/ANC"
}
```

**Always use the internal code** (`value`) in API calls, not the display name.

#### Practical Implications

**For Development:**
1. **Don't assume symmetry** - input format may differ from output format
2. **Use barcode field** - valuable for item tracking and fulfillment
3. **Check supplied_format** - may differ from requested format
4. **Parse both date formats** - `*_date` for day precision, `*_time` for exact timestamp
5. **Use partner value, not desc** - "ANC" not "ANCA-TEST"

**For Data Integration:**
- `mms_id` + `barcode` enable full item tracking
- `text_email` enables automated partner communication
- `shipping_cost` supports financial reconciliation
- `supplied_format` tracks format substitutions

**For Testing:**
- Real SANDBOX data shows SHIPPED_PHYSICALLY status
- Empty dicts (`{}`) are valid for optional complex objects
- Some code table fields may have empty descriptions

#### Example: Complete Real Response

See `docs/examples/lending_request_example.json` for complete real-world example showing all fields.

### Important Notes

- **Partner Codes**: Must exist in Alma configuration (Configuration > Resource Sharing > Partners)
- **Owner Codes**: Must be valid resource sharing library codes
- **Format Values**: Controlled by RequestFormats code table
- **Citation Types**: BOOK, JOURNAL, and other values from code table
- **Status Workflow**: Managed by Alma based on request lifecycle
- **External ID**: Should be unique identifier from external system (ILL, Rapido, etc.)

### Common Patterns

**Pattern 1: Create Request from ILL System**
```python
# Receive ILL request from external system
ill_request = {
    "external_id": "ILL-12345",
    "patron_name": "John Doe",
    "title": "Example Book",
    "author": "Smith, Jane",
    "isbn": "978-0-123456-78-9"
}

# Create lending request in Alma
request = rs.create_lending_request(
    partner_code="RELAIS",
    external_id=ill_request['external_id'],
    owner="MAIN",
    format_type="PHYSICAL",
    title=ill_request['title'],
    citation_type="BOOK",
    author=ill_request['author'],
    isbn=ill_request['isbn']
)

# Store request_id for tracking
ill_request['alma_request_id'] = request['request_id']
```

**Pattern 2: Batch Request Creation**
```python
# Process multiple requests
external_requests = load_ill_requests()

created_requests = []
for ext_req in external_requests:
    try:
        request = rs.create_lending_request(
            partner_code=ext_req['partner'],
            external_id=ext_req['id'],
            owner="MAIN",
            format_type=ext_req['format'],
            title=ext_req['title'],
            citation_type=ext_req['type'],
            author=ext_req.get('author'),
            isbn=ext_req.get('isbn')
        )
        created_requests.append({
            'external_id': ext_req['id'],
            'alma_id': request['request_id'],
            'status': 'SUCCESS'
        })
    except (ValueError, AlmaAPIError) as e:
        created_requests.append({
            'external_id': ext_req['id'],
            'status': 'FAILED',
            'error': str(e)
        })

# Generate report
save_report(created_requests)
```

**Pattern 3: Monitor Request Status**
```python
# Retrieve and check status
request = rs.get_lending_request(
    partner_code="RELAIS",
    request_id="12345678"
)

status = request.get('status', {}).get('value')

if status == "REQUEST_CREATED_LEN":
    print("Request created, awaiting processing")
elif status == "IN_PROCESS":
    print("Request being processed")
elif status == "SHIPPED":
    print("Item shipped to partner")
# Handle other statuses
```

### Future Enhancements (Not Yet Implemented)

The following endpoints are available in the Partners API but not yet implemented:
- Update lending request
- List lending requests with filters
- Add notes to lending request
- Update request status
- Borrowing requests (requests TO partner)
- Request cancellation

## Alma Acquisitions API Reference

### Official Documentation
- **Base URL**: `https://developers.exlibrisgroup.com/alma/apis/acq/`
- **API Docs**: `https://developers.exlibrisgroup.com/alma/apis/`
- **OpenAPI/Swagger**: Available for download at developers.exlibrisgroup.com

### Key Acquisitions Endpoints

#### Purchase Order Lines (POL)

**Get POL**
```
GET /almaws/v1/acq/po-lines/{po_line_id}
```
- Retrieves complete POL information including items, pricing, and status
- Returns POL object with embedded item details

**Get POL Items**
```
GET /almaws/v1/acq/po-lines/{po_line_id}/items
```
- Returns list of all items associated with a POL
- Each item includes: item_id, status, receiving information, barcode, location

**Update POL**
```
PUT /almaws/v1/acq/po-lines/{po_line_id}
```
- Updates POL data including pricing, vendor information, notes
- Requires complete POL object in request body

#### Items and Receiving

**Receive Existing Item**
```
POST /almaws/v1/acq/po-lines/{po_line_id}/items/{item_id}?op=receive
```
- **Required Query Parameter**: `op=receive`
- **Optional Parameters**:
  - `receive_date`: Date of receipt (format: YYYY-MM-DDZ)
  - `department`: Department code for receiving
  - `department_library`: Library code of receiving department
- **Content-Type**: `application/xml`
- **Request Body**: Empty `<item/>` or item object with updates
- **Response**: Updated Item object
- **Effect**:
  - Changes item status to "received"
  - Updates process type from "acquisition" to "in transit"
  - Automatically creates request if configured

**Error Codes**:
- `40166411`: Invalid parameter value
- `401875`: Department not found
- `401871`: PO Line not found
- `401877`: Failed to receive PO Line

**Add and Receive New Item**
```
POST /almaws/v1/acq/po-lines/{po_line_id}/items
```
- Adds a new item to POL and marks it as received
- Request body contains complete item object
- Returns created Item object

#### Invoices

**Get Invoice**
```
GET /almaws/v1/acq/invoices/{invoice_id}
```
- Retrieves complete invoice data including lines, amounts, status
- Optional parameter: `view=brief|full` (default: full)

**List Invoices**
```
GET /almaws/v1/acq/invoices
```
- Query parameters: `limit`, `offset`, `q` (query string)
- Supports filtering by status, vendor, date ranges
- Query format: `invoice_status~WAITING_TO_BE_SENT AND vendor~VENDOR_CODE`

**Invoice Service Operations**
```
POST /almaws/v1/acq/invoices/{invoice_id}?op={operation}
```
- **Operations**:
  - `paid`: Mark invoice as paid
  - `process_invoice`: Approve/process invoice (mandatory after creation)
  - `mark_in_erp`: Mark as sent to ERP system
  - `rejected`: Reject invoice
- **Request Body**: Empty object `{}`
- **Effect**: Updates invoice status and payment_status fields

**Create Invoice**
```
POST /almaws/v1/acq/invoices
```
- Creates new invoice with vendor and date information
- Returns invoice object with generated invoice_id

**Create Invoice Line**
```
POST /almaws/v1/acq/invoices/{invoice_id}/lines
```
- Adds line item to existing invoice
- Links to POL via reference in line data
- Must be done before processing invoice

### Data Object Structures

**Item Object Key Fields**:
- `item_id`: Unique identifier for item
- `barcode`: Item barcode
- `receiving_date`: Date item was received
- `receiving_operator`: User who received item
- `process_type`: Current status (acquisition, in_transit, etc.)
- `po_line`: Reference to parent POL

**Invoice Object Key Fields**:

Based on Alma API XSD Schema (`rest_invoice.xsd`):

**Top-Level Fields**:
- `id`: string - Invoice identifier (output only, unique)
- `number`: string - Vendor invoice number (mandatory)
- `invoice_date`: date - Date of invoice (mandatory)
- `vendor`: object - Vendor code with attributes (mandatory)
  - `value`: Vendor code
  - `desc`: Vendor description
- `total_amount`: **decimal** - Total invoice amount (mandatory, simple numeric type)
- `currency`: object - Currency information (optional, defaults to institution currency)
  - `value`: Currency code
  - `desc`: Currency description
- `invoice_status`: object - Invoice processing status
  - `value`: Status code (WAITING_TO_BE_SENT, APPROVED, CLOSED, etc.)
  - `desc`: Status description
- `payment`: object - Payment information (contains payment_status)
  - `prepaid`: boolean
  - `internal_copy`: boolean
  - `payment_status`: object - **Payment status is nested here**
    - `value`: Status code (NOT_PAID, PAID, FULLY_PAID, etc.)
    - `desc`: Status description
  - `voucher_number`: string
  - `voucher_amount`: string
- `invoice_line`: array - Array of invoice line items (complex objects)
- `creation_date`: date - When invoice was created in Alma
- `owner`: object - Owner of the invoice

**Nested Complex Objects**:

1. **invoice_vat** (VAT/Tax information):
   - `report_tax`: boolean
   - `vat_code`: string with attributes
   - `percentage`: decimal
   - `type`: string with attributes

2. **payment** (Payment details):
   - `prepaid`: boolean
   - `payment_status`: string with attributes (NOT_PAID, PAID, etc.)
   - `voucher_number`: string
   - `voucher_amount`: string

3. **additional_charges**:
   - `shipment`: decimal
   - `overhead`: decimal
   - `insurance`: decimal
   - `discount`: decimal

**Important Notes**:
- `total_amount` is a **simple decimal field**, not a complex object with nested 'sum' and 'currency'
- Some API responses may wrap numeric fields differently depending on view parameter
- Currency information is separate in the `currency` field
- Full XSD available at: `/wp-content/uploads/alma/xsd/rest_invoice.xsd`

**POL Object Key Fields**:
- `number`: POL reference number
- `type`: POL type (ONE_TIME, STANDING_ORDER, APPROVAL, etc.)
- `status`: POL status (ACTIVE, CLOSED, CANCELLED, etc.)
- `vendor`: Vendor information
- `price`: Pricing information including list price, discount
- `location`: Holding location details
- `item`: Array of associated items

### Workflow Patterns

**Receiving Workflow (One-Time POL)**:
1. Get POL data to extract item_id and verify status
2. Receive item via POST with `op=receive` parameter
3. Item status changes to "received", POL may auto-close depending on configuration

**Invoice Creation Workflow**:
1. Create invoice with vendor and date information
2. Add invoice lines linking to POLs
3. Process invoice (mandatory) using `op=process_invoice`
4. Optionally mark as paid using `op=paid`
5. Invoice status progresses: WAITING_TO_BE_SENT → APPROVED → CLOSED

**EDI Vendor Integration (Rialto Pattern)**:
- One-time POL with EDI vendor
- Receiving item and paying invoice results in POL closure
- Workflow: receive item → mark invoice paid → POL auto-closes

### Important Notes

- **XML vs JSON**: Most endpoints support both, but item receiving requires XML format
- **Empty Payloads**: Some operations require explicit empty objects `{}` or `<item/>`
- **Date Formats**: Use ISO 8601 format with timezone: `YYYY-MM-DDZ` (e.g., `2025-01-15Z`)
- **POL Closure**: POLs typically close automatically when all items received and invoices paid
- **Invoice Processing**: `process_invoice` operation is mandatory after creating invoice and lines
- **Error Tracking**: Alma errors include `errorCode`, `errorMessage`, and `trackingId` for support

### CRITICAL: Invoice Workflow Requirements (Documented 2025-10-23)

**⚠️ MANDATORY INVOICE PROCESSING SEQUENCE**:

Invoices MUST be processed/approved BEFORE they can be paid. This is enforced by Alma API and will fail if not followed:

```python
# ✅ CORRECT WORKFLOW:
# Step 1: Create invoice
invoice = acq.create_invoice_simple(...)

# Step 2: Add invoice lines
line = acq.create_invoice_line_simple(invoice_id, pol_id, ...)

# Step 3: MUST PROCESS FIRST (mandatory!)
processed = acq.approve_invoice(invoice_id)
# API: POST /almaws/v1/acq/invoices/{id}?op=process_invoice

# Step 4: Then can mark as paid (NOW WITH AUTOMATIC DUPLICATE PROTECTION!)
paid = acq.mark_invoice_paid(invoice_id)
# API: POST /almaws/v1/acq/invoices/{id}?op=paid

# ❌ WRONG - Will fail with error 402459:
invoice = acq.create_invoice_simple(...)
line = acq.create_invoice_line_simple(...)
paid = acq.mark_invoice_paid(invoice_id)  # FAILS - not processed yet!
```

**Invoice State Transitions**:
1. **Created**: `invoice_status=ACTIVE`, `workflow_status=InReview`, `approval_status=PENDING`, `payment_status=NOT_PAID`
2. **After Processing**: `approval_status=APPROVED`, `workflow_status=Approved`
3. **After Payment**: `payment_status=PAID` or `FULLY_PAID`

**Common Errors**:
- **Error 402459**: "Error while trying to retrieve invoice" - Usually means invoice not processed yet or deleted
- **Solution**: Always call `approve_invoice()` before `mark_invoice_paid()`

### CRITICAL: Duplicate Payment Protection (Added 2025-10-23)

**⚠️ AUTOMATIC DUPLICATE PAYMENT PROTECTION**:

The `mark_invoice_paid()` method now includes automatic duplicate payment protection to prevent accidentally paying the same invoice twice.

```python
# ✅ SAFE - Automatic protection (default behavior):
try:
    result = acq.mark_invoice_paid(invoice_id)
    # Protection automatically checks:
    # - Is invoice already paid? (PAID, FULLY_PAID, PARTIALLY_PAID)
    # - Is invoice already closed?
    # - Is invoice approved?
except AlmaAPIError as e:
    # Will raise error if invoice already paid or not ready
    print(f"Payment prevented: {e}")

# ⚠️ BYPASS PROTECTION (dangerous, not recommended):
result = acq.mark_invoice_paid(invoice_id, force=True)

# ✅ MANUAL CHECK before payment:
check = acq.check_invoice_payment_status(invoice_id)
if check['is_paid']:
    print(f"⚠️ Invoice already paid: {check['payment_status']}")
elif check['can_pay']:
    acq.mark_invoice_paid(invoice_id)
else:
    print(f"Cannot pay: {check['warnings']}")
```

**Protection Features**:
- Automatically checks invoice payment status before paying
- Prevents duplicate payments (PAID, FULLY_PAID, PARTIALLY_PAID states)
- Prevents paying closed invoices
- Prevents paying unapproved invoices
- Provides clear error messages with current state
- Includes `force=True` option to bypass (not recommended)

**New Methods**:
- `check_invoice_payment_status(invoice_id)` - Returns detailed payment status
- `mark_invoice_paid(invoice_id, force=False)` - Now includes protection

**check_invoice_payment_status() Returns**:
```python
{
    'is_paid': bool,          # Is invoice already paid?
    'payment_status': str,    # PAID, NOT_PAID, etc.
    'invoice_status': str,    # ACTIVE, CLOSED, etc.
    'approval_status': str,   # APPROVED, PENDING, etc.
    'can_pay': bool,          # Safe to pay?
    'warnings': List[str]     # Any warnings
}
```

**When Protection Triggers**:
1. Invoice already paid (status: PAID, FULLY_PAID, PARTIALLY_PAID)
2. Invoice already closed (status: CLOSED)
3. Invoice not yet approved (must call approve_invoice first)

**Error Message Example**:
```
AlmaAPIError: ⚠️ DUPLICATE PAYMENT PREVENTED!
Invoice 123456 is already paid.
Payment Status: PAID
Invoice Status: CLOSED
Use force=True to bypass this protection (not recommended).
```

### Verified Working Methods for Rialto Flow (Tested 2025-09-30)

**POL Operations**:
- ✓ `acq.get_pol(pol_id)` - Retrieves complete POL data
- ✓ `acq.extract_items_from_pol_data(pol_data)` - Extracts items from location→copy structure
- ✓ Extract invoice ID from POL: `pol_data.get('invoice_reference')`

**Invoice Operations**:
- ✓ `acq.get_invoice(invoice_id)` - Retrieves invoice data
- ✓ `acq.get_invoice_summary(invoice_id)` - Returns formatted summary with correct payment_status
- ✓ `acq.get_invoice_lines(invoice_id)` - Gets lines from dedicated endpoint
- ✓ `acq.approve_invoice(invoice_id)` - Processes/approves invoice (MANDATORY before payment)
- ✓ `acq.check_invoice_payment_status(invoice_id)` - Checks payment status (duplicate protection helper)
- ✓ `acq.mark_invoice_paid(invoice_id, force=False)` - Marks as paid with automatic duplicate protection
- ✓ `acq.check_pol_invoiced(pol_id)` - Returns payment_status, approval_status for duplicate detection

**Item Receiving Operations**:
- ✓ `acq.receive_item(pol_id, item_id, receive_date, department, department_library)` - Receives item (modifies data)
- ✓ `acq.receive_and_keep_in_department(pol_id, item_id, mms_id, holding_id, library, department, ...)` - Receives item and keeps it in department
- ✓ `bibs.scan_in_item(mms_id, holding_id, item_pid, library, department, work_order_type, status, done)` - Scans item into department with work order
- Method implemented and tested with XML endpoint
- ⚠️ Pending: Test with actual unreceived item

**Item Work Order Management (NEW - 2025-10-21)**:

Problem: When receiving items via `acq.receive_item()`, items automatically move to "in transit" process_type instead of staying in the acquisitions department.

Solution: Use the new `receive_and_keep_in_department()` workflow that combines receiving with scan-in operation to keep items in department.

**Available Methods**:
1. **`bibs.scan_in_item()`** - Low-level scan-in operation
   - Simulates UI "Scan In Items" function
   - Places item in work order within department
   - Prevents Transit status when used after receiving
   - Parameters: mms_id, holding_id, item_pid, library, department, work_order_type, status, done

2. **`acq.receive_and_keep_in_department()`** - High-level combined workflow
   - Receives item via acquisitions API
   - Immediately scans item into department with work order
   - Single method call for complete workflow
   - Parameters: pol_id, item_id, mms_id, holding_id, library, department, work_order_type, work_order_status

**Workflow Pattern (Receive and Keep in Department)**:
```python
# Get POL data first to extract MMS and holding IDs
pol_data = acq.get_pol(pol_id)
items = acq.extract_items_from_pol_data(pol_data)
unreceived = [item for item in items if not item.get('receive_date')]

if unreceived:
    item = unreceived[0]
    item_id = item['pid']

    # Extract MMS and holding IDs from POL data
    mms_id = pol_data.get('resource_metadata', {}).get('mms_id', {}).get('value')
    holding_id = pol_data.get('location', [{}])[0].get('holding_id')

    # Receive and keep in department (prevents Transit)
    result = acq.receive_and_keep_in_department(
        pol_id=pol_id,
        item_id=item_id,
        mms_id=mms_id,
        holding_id=holding_id,
        library="MAIN",
        department="ACQ",
        work_order_type="AcqWorkOrder",
        work_order_status="CopyCataloging"
    )

    # Item is now received and in work order, NOT in Transit
```

**Configuration Requirements**:
- Work order types and statuses must be configured in Alma:
  - Path: Configuration > Fulfillment > Physical Fulfillment > Work Order Types
- Common work order types: `AcqWorkOrder`, `CatalogingWorkOrder`, `ConservationWorkOrder`
- Common statuses for AcqWorkOrder: `CopyCataloging`, `Labeling`, `Processing`, `Review`
- Example configuration: `/config/rialto_workflow_config.example.json`

**Test Script**:
- `test_receive_keep_in_dept.py` - Tests complete receive and keep in department workflow
- Usage: `python test_receive_keep_in_dept.py <POL_ID> <ITEM_ID> <MMS_ID> <HOLDING_ID>`

**Complete Rialto Workflow Pattern (Original)**:
```python
# 1. Get POL and extract data
pol_data = acq.get_pol(pol_id)
items = acq.extract_items_from_pol_data(pol_data)
invoice_id = pol_data.get('invoice_reference')

# 2. Find unreceived item
unreceived = [item for item in items if not item.get('receive_date')]
if unreceived:
    item_id = unreceived[0]['pid']

    # 3. Receive item
    acq.receive_item(pol_id, item_id)

# 4. Mark invoice as paid
acq.mark_invoice_paid(invoice_id)

# 5. Verify POL closure
updated_pol = acq.get_pol(pol_id)
status = updated_pol.get('status', {}).get('value')  # Should be 'CLOSED'
```

### Critical Data Structure Findings (Tested 2025-09-30)

**POL Items Structure**:
- Items are NOT at POL root level
- Path: `POL → location (list) → copy (list of item objects)`
- Each `copy` object is an item
- Item ID field: `pid` (not `item_id`)
- Receive status: Check for `receive_date` field (null = unreceived)

**Invoice-POL Linkage** (Updated 2025-10-21):

The relationship between invoices and POLs works through **invoice lines**, not direct POL fields:

**Alma Acquisitions Hierarchy**:
```
Purchase Order (PO)
  └── Purchase Order Lines (POLs)
        └── Invoice Lines (link POLs to Invoices)
              └── Invoice
```

**How Linkage Works**:
1. Invoice has invoice lines (retrieved via `/almaws/v1/acq/invoices/{invoice_id}/lines`)
2. Each invoice line has a `po_line` field containing the POL ID (e.g., "POL-12347")
3. Multiple invoice lines can reference the same invoice
4. One invoice can have lines for multiple POLs

**Finding POL-Invoice Links**:
```python
# Get invoice lines
invoice_lines = acq.get_invoice_lines(invoice_id)

# Check which POL each line references
for line in invoice_lines:
    pol_id = line.get('po_line')  # e.g., "POL-12347"
    quantity = line.get('quantity')
    price = line.get('price')
    total = line.get('total_price')
```

**Important Notes**:
- POL's `invoice_reference` field is often NOT populated (even when linked correctly)
- The authoritative link is in the **invoice line's `po_line` field**
- To verify linkage: Get invoice lines and check `po_line` field
- When invoice is paid, all linked POLs update automatically
- POL auto-closure depends on: all items received + all linked invoice lines paid

**Example Linkage Verification**:
```python
# Verify if invoice is linked to POL
invoice_lines = acq.get_invoice_lines(invoice_id)
linked_pols = [line.get('po_line') for line in invoice_lines]

if 'POL-12347' in linked_pols:
    print("Invoice is linked to POL-12347")
```

**Invoice Payment Status**:
- Path: `invoice → payment → payment_status → value`
- NOT at root level of invoice
- Values: "PAID", "NOT_PAID", "FULLY_PAID", etc.
- Always check inside `payment` object

**Invoice Total Amount**:
- Field: `total_amount` at root level
- Type: Simple decimal/float (not nested object)
- Currency is separate field: `currency.value`

**Invoice Lines Endpoint**:
- Must use dedicated endpoint: `GET /almaws/v1/acq/invoices/{invoice_id}/lines`
- Do NOT extract from embedded invoice_line in full invoice response
- Supports pagination: `limit` and `offset` parameters

**Searching Invoices by POL** (Critical Finding - 2025-10-22):

The Alma API supports **direct search of invoices by POL number**, making duplicate invoice detection efficient:

**Correct Query Format**:
```python
# Direct POL search - EFFICIENT
query = f"pol_number~{pol_id}"  # Use tilde format
endpoint = "almaws/v1/acq/invoices"
params = {"q": query, "limit": 100}

# Example: Search for invoices containing POL-12347
response = client.get("almaws/v1/acq/invoices", params={"q": "pol_number~POL-12347"})
# Returns all invoices that have lines referencing POL-12347
```

**Query Format Testing Results**:
- ✅ `pol_number~POL-12347` (tilde format) - **WORKS** (recommended)
- ✅ `pol_number=POL-12347` (equals format) - Works
- ❌ `pol_number:POL-12347` (colon format) - Server error

**Important Notes**:
- This query searches **across all invoice lines** automatically
- Much more efficient than iterating through invoices manually
- Returns complete invoice objects that contain the POL
- Use `check_pol_invoiced()` method which implements this correctly
- Prevents double-invoicing by detecting existing invoice lines

**Implementation in check_pol_invoiced()**:
```python
# Correct implementation (as of 2025-10-22)
def check_pol_invoiced(self, pol_id: str) -> Dict[str, Any]:
    query = f"pol_number~{pol_id}"  # Direct POL search
    params = {"q": query, "limit": 100}
    response = self.client.get("almaws/v1/acq/invoices", params=params)

    # Returns: {'is_invoiced': bool, 'invoice_count': int, 'invoices': [...]}
```

**Bug History**:
- **Initial Implementation (2025-10-22)**: Inefficiently iterated through 100 active invoices
- **Fixed Implementation (2025-10-22)**: Uses direct `pol_number~{pol_id}` query
- **Impact**: Correctly detects all existing invoices for a POL, prevents double-invoicing

### Invoice Creation Helper Methods (Added 2025-10-22)

The `Acquisitions` domain now includes comprehensive invoice creation helper methods providing three levels of abstraction for creating and managing invoices programmatically.

#### Three Levels of Abstraction

**Level 1: Core Utility Methods** (Private, for internal use)
- `_format_invoice_date()`: Handles date formatting to Alma's YYYY-MM-DDZ format
- `_build_invoice_structure()`: Constructs complete invoice data dictionary
- `_build_invoice_line_structure()`: Constructs complete invoice line data dictionary with fund distribution

**Level 2: Simple Helper Methods** (Public, simplified parameters)
- `create_invoice_simple()`: Create invoice with simplified parameters
- `create_invoice_line_simple()`: Create invoice line with auto-fund extraction

**Level 3: Complete Workflow** (Public, full automation)
- `create_invoice_with_lines()`: Complete end-to-end invoice workflow in single call

#### Quick Start Examples

**Example 1: Simple Invoice Creation**
```python
from src.domains.acquisition import Acquisitions

acq = Acquisitions(client)

# Create invoice with minimal parameters
invoice = acq.create_invoice_simple(
    invoice_number="INV-2025-001",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    total_amount=100.00
)

print(f"Invoice created: {invoice['id']}")
```

**Example 2: Invoice with Lines (Manual)**
```python
# Step 1: Create invoice
invoice = acq.create_invoice_simple(
    invoice_number="INV-2025-002",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    total_amount=125.00
)

# Step 2: Add lines (fund auto-extracted from POL)
line1 = acq.create_invoice_line_simple(
    invoice_id=invoice['id'],
    pol_id="POL-12347",
    amount=50.00,
    quantity=1
)

line2 = acq.create_invoice_line_simple(
    invoice_id=invoice['id'],
    pol_id="POL-12348",
    amount=75.00,
    quantity=1
)

# Step 3: Process invoice
acq.approve_invoice(invoice['id'])

# Step 4: Mark as paid
acq.mark_invoice_paid(invoice['id'])
```

**Example 3: Complete Automated Workflow**
```python
# Single method call for entire workflow
lines = [
    {"pol_id": "POL-12347", "amount": 50.00, "quantity": 1},
    {"pol_id": "POL-12348", "amount": 75.00, "quantity": 1}
]

result = acq.create_invoice_with_lines(
    invoice_number="INV-2025-003",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    lines=lines,
    auto_process=True,  # Automatically approve invoice
    auto_pay=True       # Automatically mark as paid
)

# Check results
print(f"Invoice ID: {result['invoice_id']}")
print(f"Lines created: {len(result['line_ids'])}")
print(f"Processed: {result['processed']}")
print(f"Paid: {result['paid']}")
print(f"Errors: {result['errors']}")
```

#### Method Details

**create_invoice_simple()**
```python
def create_invoice_simple(
    invoice_number: str,
    invoice_date: str,           # "YYYY-MM-DD" or datetime object
    vendor_code: str,
    total_amount: float,
    currency: str = "ILS",
    **optional_fields              # payment, invoice_vat, etc.
) -> Dict[str, Any]
```

**create_invoice_line_simple()**
```python
def create_invoice_line_simple(
    invoice_id: str,
    pol_id: str,
    amount: float,
    quantity: int = 1,
    fund_code: Optional[str] = None,  # Auto-extracted from POL if None
    currency: str = "ILS",
    **optional_fields                  # note, subscription dates, vat
) -> Dict[str, Any]
```

**create_invoice_with_lines()**
```python
def create_invoice_with_lines(
    invoice_number: str,
    invoice_date: str,
    vendor_code: str,
    lines: List[Dict[str, Any]],  # [{"pol_id": str, "amount": float, ...}]
    currency: str = "ILS",
    auto_process: bool = True,     # Approve invoice automatically
    auto_pay: bool = False,        # Mark as paid automatically
    **invoice_kwargs               # Additional invoice fields
) -> Dict[str, Any]
```

Returns comprehensive result:
```python
{
    'invoice_id': str,           # Created invoice ID
    'invoice_number': str,       # Invoice number
    'line_ids': List[str],       # Created line IDs
    'total_amount': float,       # Calculated total
    'status': str,               # Final invoice status
    'processed': bool,           # Whether processed
    'paid': bool,                # Whether paid
    'errors': List[str]          # Any errors encountered
}
```

#### POL Utility Methods

**get_vendor_from_pol()**
```python
vendor_code = acq.get_vendor_from_pol("POL-12347")
# Returns vendor code or None
```

**get_fund_from_pol()**
```python
fund_code = acq.get_fund_from_pol("POL-12347")
# Returns primary fund code or None
# If multiple funds, returns first and logs note
```

**get_price_from_pol()** (Added 2025-10-22)
```python
price = acq.get_price_from_pol("POL-12347")
# Returns POL list price as float
# Returns: 180.0 (for POL-12347)
```

**check_pol_invoiced()** (Added 2025-10-22)
```python
check = acq.check_pol_invoiced("POL-12347")
# Returns dict with:
#   - is_invoiced: bool
#   - invoice_count: int
#   - invoices: List[Dict] with existing invoice details

if check['is_invoiced']:
    print(f"⚠️  POL already has {check['invoice_count']} invoice(s)")
    for inv in check['invoices']:
        print(f"  - {inv['invoice_number']}: {inv['amount']}")
```

#### Best Practices

**1. Use Auto-Fund Extraction**
```python
# Recommended - fund auto-extracted from POL
line = acq.create_invoice_line_simple(
    invoice_id=invoice_id,
    pol_id="POL-12347",
    amount=100.00
)

# Only specify fund_code if overriding POL fund
line = acq.create_invoice_line_simple(
    invoice_id=invoice_id,
    pol_id="POL-12347",
    amount=100.00,
    fund_code="SPECIAL_FUND"
)
```

**2. Use Workflow Method for Bulk Operations**
```python
# For creating multiple invoices with lines
# Use create_invoice_with_lines() for cleaner code
lines = [
    {"pol_id": "POL-12347", "amount": 50.00},
    {"pol_id": "POL-12348", "amount": 75.00},
    {"pol_id": "POL-12349", "amount": 100.00}
]

result = acq.create_invoice_with_lines(
    invoice_number="INV-2025-004",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    lines=lines,
    auto_process=True,
    auto_pay=False  # Leave for manual payment approval
)
```

**3. Handle Errors Gracefully**
```python
try:
    result = acq.create_invoice_with_lines(...)

    if result['errors']:
        print(f"Warnings: {len(result['errors'])} issues")
        for error in result['errors']:
            print(f"  - {error}")

    if len(result['line_ids']) < len(lines):
        print(f"Only {len(result['line_ids'])}/{len(lines)} lines created")

except ValueError as e:
    print(f"Invalid parameters: {e}")
except AlmaAPIError as e:
    print(f"API error: {e}")
```

**4. Use POL's Actual Price** (Added 2025-10-22)
```python
# RECOMMENDED: Extract price from POL to avoid errors
pol_ids = ["POL-12347", "POL-12348"]
lines = []
for pol_id in pol_ids:
    price = acq.get_price_from_pol(pol_id)
    if price:
        lines.append({"pol_id": pol_id, "amount": price})

result = acq.create_invoice_with_lines(
    invoice_number="INV-2025-001",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    lines=lines
)

# AVOID: Hardcoding amounts (may not match POL price)
# lines = [{"pol_id": "POL-12347", "amount": 50.00}]  # Wrong if POL is 180.00!
```

**5. Prevent Double Invoicing** (Added 2025-10-22)
```python
# Option 1: Manual check before creating
check = acq.check_pol_invoiced("POL-12347")
if check['is_invoiced']:
    raise ValueError(f"POL already invoiced!")

# Option 2: Use check_duplicates parameter (slower but automatic)
result = acq.create_invoice_with_lines(
    invoice_number="INV-2025-001",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    lines=lines,
    check_duplicates=True  # Will validate all POLs before creating
)
```

**6. Workflow Stages**
```python
# Stage 1: Create but don't process (for review)
result = acq.create_invoice_with_lines(
    ...,
    auto_process=False,
    auto_pay=False
)

# Stage 2: Create and process (ready for payment)
result = acq.create_invoice_with_lines(
    ...,
    auto_process=True,
    auto_pay=False
)

# Stage 3: Full automation (complete workflow)
result = acq.create_invoice_with_lines(
    ...,
    auto_process=True,
    auto_pay=True
)
```

#### Common Patterns

**Pattern 1: Invoice from POL Data**
```python
# Extract vendor and fund from POL
pol_data = acq.get_pol("POL-12347")
vendor = acq.get_vendor_from_pol("POL-12347")
fund = acq.get_fund_from_pol("POL-12347")

# Create invoice with extracted data
invoice = acq.create_invoice_simple(
    invoice_number="INV-2025-005",
    invoice_date="2025-10-22",
    vendor_code=vendor,
    total_amount=100.00
)

# Add line with explicit fund
line = acq.create_invoice_line_simple(
    invoice_id=invoice['id'],
    pol_id="POL-12347",
    amount=100.00,
    fund_code=fund
)
```

**Pattern 2: Batch Invoice Creation**
```python
# Process multiple POLs
pol_ids = ["POL-12347", "POL-12348", "POL-12349"]
invoice_num = f"INV-{datetime.now().strftime('%Y%m%d')}"

lines = []
for pol_id in pol_ids:
    pol_data = acq.get_pol(pol_id)
    price = pol_data['price']['sum']
    lines.append({
        "pol_id": pol_id,
        "amount": float(price),
        "quantity": 1
    })

result = acq.create_invoice_with_lines(
    invoice_number=invoice_num,
    invoice_date=datetime.now().strftime("%Y-%m-%d"),
    vendor_code="RIALTO",
    lines=lines,
    auto_process=True
)
```

**Pattern 3: Error Recovery**
```python
result = acq.create_invoice_with_lines(...)

# Invoice created even if some lines failed
if result['invoice_id']:
    print(f"Invoice {result['invoice_id']} created")

    # Retry failed lines
    if result['errors']:
        print("Retrying failed lines...")
        for error in result['errors']:
            # Parse error and retry logic
            pass

    # Continue with processing if lines succeeded
    if len(result['line_ids']) > 0:
        if not result['processed']:
            acq.approve_invoice(result['invoice_id'])
```

#### Date Handling

The system accepts multiple date formats:

```python
# String format
invoice = acq.create_invoice_simple(
    invoice_date="2025-10-22",  # Automatically converts to "2025-10-22Z"
    ...
)

# Already formatted
invoice = acq.create_invoice_simple(
    invoice_date="2025-10-22Z",  # Used as-is
    ...
)

# Datetime object
from datetime import datetime
invoice = acq.create_invoice_simple(
    invoice_date=datetime(2025, 10, 22),  # Converts to "2025-10-22Z"
    ...
)

# Current date
invoice = acq.create_invoice_simple(
    invoice_date=datetime.now(),
    ...
)
```

#### Testing

Comprehensive test suite available: `src/tests/test_invoice_creation.py`

```bash
# Dry-run validation (no API calls)
python3 src/tests/test_invoice_creation.py --environment SANDBOX

# Live tests (creates real invoices)
python3 src/tests/test_invoice_creation.py --environment SANDBOX --live

# Run specific test
python3 src/tests/test_invoice_creation.py --test 5

# All tests
python3 src/tests/test_invoice_creation.py --test all --live
```

Test coverage:
- Test 1-3: Core utility methods
- Test 4-5: POL utility methods
- Test 6-7: Simple helper methods
- Test 8-10: Complete workflow variations

#### Implementation Details

**Location**: `src/domains/acquisition.py`
- Lines 34-272: Core utility methods
- Lines 282-492: Simple helper methods
- Lines 502-789: Complete workflow method
- Lines 1237-1358: POL utility methods

**Dependencies**:
- `datetime` module for date handling
- Existing `create_invoice()` and `create_invoice_line()` methods
- Existing `approve_invoice()` and `mark_invoice_paid()` methods

**Error Handling**:
- `ValueError`: Invalid parameters or missing required fields
- `AlmaAPIError`: API operation failures

**Progress Logging**:
All methods include progress logging for debugging:
- Invoice creation confirmation
- Line creation progress (e.g., "Line 2/5: POL POL-12348, Amount: 75.0")
- Processing and payment status
- Final workflow summary

#### Known Issues and Bug Fixes (2025-10-22)

**Bug Fix 1: fund_distribution Structure**

**Issue**: Invoice line creation was failing with error:
```
Invoice line fund percentage or amount must be declared, not both and not neither.
```

**Root Cause**: The `fund_distribution` array was incorrectly including both `amount` and `percent` fields. Alma API requires EITHER `amount` OR `percent`, not both.

**Incorrect Structure**:
```python
"fund_distribution": [{
    "fund_code": {"value": "GENERIC_FUND"},
    "amount": 50.0,        # ← Can't have both amount and percent
    "percent": 100
}]
```

**Correct Structure**:
```python
"fund_distribution": [{
    "fund_code": {"value": "GENERIC_FUND"},
    "percent": 100  # 100% of line amount allocated to this fund
}]
```

**When to Use Each**:
- **Use `percent`**: For percentage-based allocation (e.g., 100% to one fund, or 50/50 split)
  ```python
  "fund_distribution": [
      {"fund_code": {"value": "FUND_A"}, "percent": 50},
      {"fund_code": {"value": "FUND_B"}, "percent": 50}
  ]
  ```
- **Use `amount`**: For explicit dollar amounts (e.g., $50 to Fund A, $30 to Fund B)
  ```python
  "fund_distribution": [
      {"fund_code": {"value": "FUND_A"}, "amount": 50.00},
      {"fund_code": {"value": "FUND_B"}, "amount": 30.00}
  ]
  ```

**Resolution**: Fixed in `_build_invoice_line_structure()` to use only `percent: 100` for single-fund allocations (commit 8cda081).

**Tested**: Live test in SANDBOX confirmed working (Invoice ID: 35925532970004146).

**Bug Fix 2: check_pol_invoiced() Query Efficiency**

**Issue**: The `check_pol_invoiced()` method was not detecting existing invoices for POLs that were already invoiced, leading to potential double-invoicing.

**Original Implementation** (Inefficient):
```python
# Iterated through 100 active invoices manually
query = "invoice_status~ACTIVE OR invoice_status~WAITING_TO_BE_SENT..."
# Then checked each invoice's lines one by one
for invoice in invoices:
    lines = self.get_invoice_lines(invoice_id)
    for line in lines:
        if line.get('po_line') == pol_id:
            # Found match
```

**Problems**:
- Only checked first 100 active invoices
- Multiple API calls (1 list call + N get_invoice_lines calls)
- Did not detect invoices with statuses outside the hardcoded list
- Could miss invoices in large datasets

**Fixed Implementation** (Efficient):
```python
# Direct POL search using Alma's built-in query capability
query = f"pol_number~{pol_id}"
response = self.client.get("almaws/v1/acq/invoices", params={"q": query})
# Returns ALL invoices containing the POL, regardless of status
```

**Benefits**:
- ✅ Single API call instead of multiple
- ✅ Searches across ALL invoice lines automatically
- ✅ No status filtering needed - finds all invoices
- ✅ Correctly detected 2 existing invoices for POL-12347 (one manual 180 ILS, one test 50 ILS)

**Discovery Process**:
1. Initial implementation failed to detect existing invoices
2. Consulted Alma REST API documentation online
3. Discovered `pol_number~{value}` query parameter support
4. Tested three formats: tilde (✅), colon (❌), equals (✅)
5. Implemented direct POL search query

**Resolution**: Fixed in `check_pol_invoiced()` method (lines 1753-1888) - now uses direct POL query.

**Tested**: Live test confirmed correct detection:
- POL-12347: Correctly found 2 invoices (PO-1769001 CLOSED 180 ILS, TEST-INV-20251022_153408-8 ACTIVE 50 ILS)

**Related Enhancements**:
- Added `get_price_from_pol()` to extract actual POL prices (prevents hardcoding errors)
- Added `check_duplicates` parameter to `create_invoice_with_lines()` workflow
- See "Searching Invoices by POL" section above for detailed query format documentation

## File Structure Context

- `src/client/` - Core API client implementation
- `src/domains/` - Domain-specific API wrappers
- `src/projects/` - Standalone scripts and utilities
- `src/tests/` - Test scripts and configuration files
- `src/utils/` - Shared utilities and helpers