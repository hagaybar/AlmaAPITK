# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AlmaAPITK is a Python toolkit for interacting with the Alma ILS (Integrated Library System) API. It provides a structured approach to API operations with domain-specific classes and utilities.

**This is a core library package.** Project-specific workflows have been extracted to standalone repositories:

| Extracted Repository | Purpose | Status |
|---------------------|---------|--------|
| `Alma-update-expired-users-emails` | User email expiry processing | Production |
| `Alma-RS-lending-request-automation` | Resource sharing lending automation | Production |
| `Alma-Digital-Upload` | Digital file uploads to Alma | Development |
| `Alma-Acquisitions-Automation` | Rialto POL processing, invoicing | Testing |

**Backup references** (full monolith before cleanup):
- Branch: `deprecated`
- Tag: `pre-cleanup-monolith`

## Import Pattern

```python
from almaapitk import AlmaAPIClient, Acquisitions, ResourceSharing
```

### Validation Requirements:

- After your changes, `scripts/smoke_import.py` must still pass
- If there is a test suite, it must pass

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
python -c "from almaapitk import AlmaAPIClient; client = AlmaAPIClient('SANDBOX'); client.test_connection()"
```

## Architecture Overview

### Core Package: `src/almaapitk/`

The primary deliverable - a clean, importable Python package.

**Public API** (from `almaapitk`):
- `AlmaAPIClient` - Main HTTP client for Alma API
- `AlmaResponse` - Response wrapper with `.data`, `.json()`, `.success`
- `AlmaAPIError`, `AlmaValidationError` - Exception classes
- `Admin`, `Users`, `BibliographicRecords`, `Acquisitions`, `ResourceSharing` - Domain classes
- `TSVGenerator` - TSV file utilities
- `CitationMetadataError` - Metadata enrichment errors

### Domain Classes (`src/almaapitk/domains/`)

| Domain | File | Key Operations |
|--------|------|----------------|
| **Acquisitions** | `acquisition.py` | POL operations, invoicing, item receiving |
| **Admin** | `admin.py` | Sets management (BIB_MMS, USER) |
| **BibliographicRecords** | `bibs.py` | Bib records, holdings, items, scan-in |
| **ResourceSharing** | `resource_sharing.py` | Lending/borrowing via Partners API |
| **Users** | `users.py` | User management, email updates |

### Key Design Patterns

- **Client-Domain Pattern**: AlmaAPIClient serves as the foundation, domain classes use it for specific operations
- **Environment-Aware**: All classes support SANDBOX/PRODUCTION environments
- **Response Wrapping**: AlmaResponse class provides consistent response handling
- **Error Hierarchy**: AlmaAPIError, AlmaValidationError, AlmaRateLimitError for specific error types

## Skills Integration

This project uses three complementary Claude Code skills:

### **📘 python-dev-expert** - Python Code Quality
**Use for:** Python coding, refactoring, architecture, code organization
- Code quality standards (PEP 8, type hints, docstrings)
- Refactoring workflows and patterns
- Architecture patterns (Client-Domain, error hierarchy)
- Code templates (domain classes, scripts, tests)
- API client patterns (pagination, rate limiting)

**The skill auto-triggers** when working on Python code.

### **🔍 alma-api-expert** - Alma API Knowledge
**Use for:** Alma API endpoints, errors, validation, quirks, digital file uploads
- API endpoint reference with parameters
- Error codes and troubleshooting
- Data structures and field formats (including Representation objects)
- API quirks and undocumented behavior
- Validation rules and required fields
- Query syntax and pagination
- Digital representations and AWS S3 file uploads
- Usage types (PRIMARY, DERIVATIVE, AUXILIARY) and entity types
- Example requests and responses

**When to use alma-api-expert:**
- Looking up API endpoints and parameters
- Debugging API errors (402459, 400, etc.)
- Understanding field formats and validation
- Learning workflow sequences (invoice creation, receiving, digital uploads)
- Uploading files to Alma (representations, S3 integration)
- Working with usage types and entity types for digital assets
- Finding query syntax examples
- Discovering API quirks (owner field format, payment status location)

**Quick access:** `/skill alma-api-expert` or check `.claude/skills/alma-api-expert/`

### **🔧 git-expert** - Git and GitHub Workflow Management
**Use for:** Git operations, commits, pull requests, branch management
- Commit message standards and formatting
- Git safety protocols (avoiding dangerous operations)
- Automated commit and push workflows
- Pull request creation with comprehensive descriptions
- Branch management and GitHub CLI usage
- Security and sensitive information protection

**The skill auto-triggers** when performing git operations, creating commits, or working with GitHub.

**When to use git-expert:**
- Creating commits with proper messages
- Making pull requests
- Understanding when to commit and push
- Following git best practices
- Avoiding destructive git operations

**Quick access:** `/skill git-expert` or check `.claude/skills/git-expert/`

## Claude's Role and Organization Focus

### Primary Role
- Act as a senior Python developer familiar with API clients and library systems
- **Use `python-dev-expert` skill** for all Python coding decisions
- **Use `alma-api-expert` skill** for Alma API knowledge and troubleshooting
- **Use `git-expert` skill** for all git operations and GitHub workflows
- **Proactively suggest code organization improvements** when working with any file
- Help identify and eliminate code duplication
- Focus on project-specific patterns and implementations

### Git Integration and Commit Management

**See `git-expert` skill for complete git workflow documentation.**

**Quick reference:**
- Claude has full permission to commit without asking
- Commit granularly with detailed messages
- Always push immediately after committing
- Follow commit message standards (see git-expert skill)
- Recognize manual commit commands: "commit", "save progress", "checkpoint"

### Code Organization Standards

**See `python-dev-expert` skill for code organization, refactoring, and cleanliness standards.**

#### Project-Specific File Organization
- Configuration files → `config/` directory
- Test data and samples → `test_data/` or `samples/`
- Remove obsolete file versions (e.g., when `_2` version exists, remove original)

## Development Commands

### Smoke Test
```bash
# Validate package imports work correctly
poetry run python scripts/smoke_import.py
```

### Testing
```bash
# Test core package imports
python -c "from almaapitk import AlmaAPIClient, Acquisitions; print('OK')"

# Test legacy imports still work (with deprecation warning)
python -c "from src.client.AlmaAPIClient import AlmaAPIClient; print('OK')"

# Run core library tests
poetry run pytest tests/test_public_api_contract.py -v
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
The project includes a comprehensive logging system located in `src/alma_logging/`:
- **Automatic API key redaction** - Sensitive data never appears in logs
- **Request/response logging** - Full HTTP details with timing
- **Error tracking** - Stack traces and context for debugging
- **Domain-specific logs** - Separate logs for acquisitions, users, bibs, admin
- **JSON format** - Machine-parseable structured logs
- **Git-safe** - All logs are gitignored and never committed

#### Using the Logger

**Import and Initialize**:
```python
from almaapitk.alma_logging import get_logger

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

See `src/alma_logging/README.md` and `src/alma_logging/docs/LOGGING_IMPLEMENTATION_PLAN.md` for complete documentation.

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

## Script Standards for Consumers

Projects using `almaapitk` should follow these patterns:

### Recommended CLI Pattern
```python
parser.add_argument("--config", help="JSON configuration file")
parser.add_argument("--environment", choices=["SANDBOX", "PRODUCTION"], default="SANDBOX")
parser.add_argument("--dry-run", action="store_true", default=True)
parser.add_argument("--live", action="store_true", help="Disable dry-run mode")
```

### Safety-First Design
- Dry-run as default mode
- Explicit confirmation for production operations
- Comprehensive logging with `almaapitk.alma_logging`

**See extracted repos for complete examples** (e.g., `Alma-Acquisitions-Automation/docs/DEVELOPER_GUIDE.md`).

## Development Context

**For code templates and development workflows → see `python-dev-expert` skill**

### Project-Specific Development Principles
- **Test in SANDBOX first** before PRODUCTION
- **Use AlmaResponse wrapper** for all API responses
- **Follow AlmaAPIError hierarchy**: AlmaAPIError, AlmaValidationError, AlmaRateLimitError
- **Use almaapitk.alma_logging framework** (never print statements)
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

**📖 For complete Alma API documentation, workflows, and troubleshooting → use `alma-api-expert` skill**

### Domain Knowledge Glossary

Key Alma terminology (quick reference):
- **MMS ID**: Bibliographic record identifier
- **User Primary ID**: Unique user identifier in Alma
- **Sets**: Collections of records (BIB_MMS or USER types)
- **Holdings**: Physical/electronic item information
- **Portfolios**: Electronic resource access points
- **POL (Purchase Order Line)**: Line items in purchase orders with pricing
- **Item**: Physical/electronic items associated with POLs
- **Representation**: Digital file container with metadata (usage type, access rights)
- **Usage Type**: Purpose of representation (PRIMARY, DERIVATIVE, AUXILIARY)
- **Entity Type**: Content type (REPRESENTATION, CHAPTER, ARTICLE, AUDIOVISUAL)

**→ For complete workflows, error codes, endpoints, and API quirks, use the `alma-api-expert` skill**

## Domain Method Reference

Use `alma-api-expert` skill to look up:
- Method signatures and parameters
- Required vs optional parameters
- Return value structures
- Error handling patterns
- Usage examples

## File Structure

```
AlmaAPITK/
├── src/
│   ├── almaapitk/              # CORE PACKAGE
│   │   ├── __init__.py         # Public API (v0.2.0)
│   │   ├── client/             # AlmaAPIClient
│   │   ├── domains/            # Domain classes
│   │   ├── utils/              # Utilities (TSVGenerator, citation_metadata)
│   │   └── alma_logging/       # Logging infrastructure
│
├── tests/                      # Core library tests
│   ├── test_public_api_contract.py
│   ├── logging/                # Logging tests
│   ├── unit/                   # Unit tests (domains, utils)
│   ├── integration/client/     # Client integration tests
│   └── meta/                   # Dependency/reorganization tests
│
├── scripts/
│   ├── smoke_import.py         # Package validation
│   └── investigations/         # Debug utilities
│
├── config/                     # Configuration templates
├── docs/                       # Documentation
├── .a5c/                       # Babysitter artifacts
└── logs/                       # Log files (gitignored)
```
