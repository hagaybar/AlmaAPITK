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

## Skills Integration

This project uses two complementary Claude Code skills:

### **📘 python-dev-expert** - Python Code Quality
**Use for:** Python coding, refactoring, architecture, code organization
- Code quality standards (PEP 8, type hints, docstrings)
- Refactoring workflows and patterns
- Architecture patterns (Client-Domain, error hierarchy)
- Code templates (domain classes, scripts, tests)
- API client patterns (pagination, rate limiting)

**The skill auto-triggers** when working on Python code.

### **🔍 alma-api-expert** - Alma API Knowledge
**Use for:** Alma API endpoints, errors, validation, quirks
- API endpoint reference with parameters
- Error codes and troubleshooting
- Data structures and field formats
- API quirks and undocumented behavior
- Validation rules and required fields
- Query syntax and pagination
- Example requests and responses

**When to use alma-api-expert:**
- Looking up API endpoints and parameters
- Debugging API errors (402459, 400, etc.)
- Understanding field formats and validation
- Learning workflow sequences (invoice creation, receiving)
- Finding query syntax examples
- Discovering API quirks (owner field format, payment status location)

**Quick access:** `/skill alma-api-expert` or check `.claude/skills/alma-api-expert/`

## Claude's Role and Organization Focus

### Primary Role
- Act as a senior Python developer familiar with API clients and library systems
- **Use `python-dev-expert` skill** for all Python coding decisions
- **Use `alma-api-expert` skill** for Alma API knowledge and troubleshooting
- **Proactively suggest code organization improvements** when working with any file
- Help identify and eliminate code duplication
- Focus on project-specific patterns and implementations

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

#### Future Enhancement Recommendations
These patterns should be integrated into `AlmaAPIClient.py` during planned architectural improvements:
1. **Implement rolling window rate limiting** instead of current basic protection
2. **Add retry logic with exponential backoff** for resilient API calls
3. **Enhance error classes** with Alma-specific error types
4. **Add configurable timeouts** with sensible defaults
5. **Consider configuration manager** for complex deployment scenarios

## Alma API Quick Reference

**📖 For complete Alma API documentation → use `alma-api-expert` skill**

### Domain Knowledge Glossary

Key Alma terminology:
- **MMS ID**: Bibliographic record identifier
- **User Primary ID**: Unique user identifier in Alma
- **Sets**: Collections of records (BIB_MMS or USER types)
- **Holdings**: Physical/electronic item information
- **Portfolios**: Electronic resource access points
- **POL (Purchase Order Line)**: Line items in purchase orders with pricing
- **Item**: Physical/electronic items associated with POLs

**→ See alma-api-expert skill for complete glossary and domain documentation**

### Critical Workflows

**⚠️ MUST READ: Duplicate Invoice Prevention**

**INCIDENT**: Duplicate payment occurred for POL-12352 (2025-10-23). See `INCIDENT_REPORT_DUPLICATE_PAYMENT_POL12352.md`.

**MANDATORY Pre-Flight Checks before any invoice operation:**

```python
# ✅ RULE 1: ALWAYS check for existing invoices BEFORE creating
check = acq.check_pol_invoiced(pol_id)
if check['is_invoiced']:
    print(f"⚠️ STOP! POL {pol_id} already has {check['invoice_count']} invoice(s)")
    # REVIEW existing - DO NOT create new

# ✅ RULE 2: NEVER skip approval step
invoice = acq.create_invoice_simple(...)
line = acq.create_invoice_line_simple(...)
acq.approve_invoice(invoice_id)  # MANDATORY
acq.mark_invoice_paid(invoice_id)  # Has automatic duplicate protection

# ✅ RULE 3: When error occurs, FIX existing - DON'T create new
if payment_fails_with_error_402459:
    acq.approve_invoice(existing_invoice_id)  # Fix it
    acq.mark_invoice_paid(existing_invoice_id)
    # ✗ DON'T create new invoice - causes duplicate!
```

**Protection Layers** (automatic by default):
1. `check_pol_invoiced()` - Detects existing invoices for POL
2. `check_invoice_payment_status()` - Checks if invoice already paid
3. `mark_invoice_paid()` - Automatic duplicate payment protection

**→ See alma-api-expert skill for complete invoice workflow documentation**

### Common API Patterns

**Invoice Creation Workflow:**
```python
# 1. Check duplicates
check = acq.check_pol_invoiced(pol_id)

# 2. Create invoice
invoice = acq.create_invoice_simple(invoice_number, date, vendor, amount)

# 3. Add lines
line = acq.create_invoice_line_simple(invoice_id, pol_id, amount)

# 4. Approve (MANDATORY)
acq.approve_invoice(invoice_id)

# 5. Mark paid
acq.mark_invoice_paid(invoice_id)
```

**Item Receiving Workflow:**
```python
# Standard (item goes to "in transit"):
acq.receive_item(pol_id, item_id)

# Keep in department (prevents transit):
acq.receive_and_keep_in_department(
    pol_id, item_id, mms_id, holding_id,
    library, department, work_order_type, status
)
```

**Resource Sharing Lending Request:**
```python
request = rs.create_lending_request(
    partner_code="RELAIS",
    external_id="ILL-12345",
    owner="MAIN",  # ⚠️ Plain string (not wrapped) - API quirk!
    format_type="PHYSICAL",
    title="Book Title",
    citation_type="BOOK"
)
```

**Digital File Upload:**
```python
# 1. Create representation
rep = bibs.create_representation(
    mms_id=mms_id,
    access_rights_value="",  # Empty = system default
    access_rights_desc="",
    lib_code="MAIN_LIB",
    usage_type="PRESERVATION_MASTER"
)

# 2. Upload to S3 (using boto3)
s3_key = f"{institution_code}/upload/{mms_id}/{filename}"
bucket.upload_file(local_path, s3_key)

# 3. Link file to representation
bibs.link_file_to_representation(mms_id, rep['id'], s3_key)
```

**→ See alma-api-expert skill for:**
- Complete endpoint reference
- Error codes and solutions
- Data structure details
- API quirks and gotchas
- Validation rules
- Query syntax
- Example requests/responses
- Digital file upload workflows and AWS integration

### When to Use alma-api-expert Skill

**Use alma-api-expert when you need:**
- API endpoint URLs and parameters
- Error troubleshooting (402459, 400, 40166411, etc.)
- Field format validation (owner field, payment_status location)
- Understanding data structures (POL items path, invoice structure)
- Query syntax (searching invoices by POL)
- Workflow sequences (invoice approval, item receiving, digital file upload)
- AWS S3 integration for digital file uploads
- API quirks (owner field format, undocumented fields)

**Access:** `/skill alma-api-expert` or `.claude/skills/alma-api-expert/`

## AlmaAPITK Domain Implementation

**Domain Classes** (`src/domains/`):
- **Acquisitions** (`acquisition.py`) - POL operations, invoicing, item receiving
- **ResourceSharing** (`resource_sharing.py`) - Lending/borrowing requests
- **Users** (`users.py`) - User management, email updates, expiry dates
- **Bibs** (`bibs.py`) - Bibliographic records, holdings, items, scan-in
- **Admin** (`admin.py`) - Sets management (BIB_MMS, USER)
- **Analytics** (`analytics.py`) - Analytics reports (PRODUCTION only, read-only)

**Available Methods:**

Use `alma-api-expert` skill to look up:
- Method signatures and parameters
- Required vs optional parameters
- Return value structures
- Error handling patterns
- Usage examples

**Test Scripts** (`src/tests/`):
- `test_invoice_creation.py` - Invoice creation workflows
- `test_resource_sharing_lending.py` - Lending requests
- `test_users_script.py` - User operations
- `test_sets_ret.py` - Sets processing
- `acquisitions_test_script.py` - Acquisitions operations

## File Structure Context

- `src/client/` - Core API client implementation
- `src/domains/` - Domain-specific API wrappers
- `src/projects/` - Standalone scripts and utilities
- `src/tests/` - Test scripts and configuration files
- `src/utils/` - Shared utilities and helpers
- `src/logging/` - Logging infrastructure
- `config/` - Configuration files
- `logs/` - Log files (gitignored)
