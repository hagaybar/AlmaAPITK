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

## Claude's Role and Organization Focus

### Primary Role
- Act as a senior Python developer familiar with API clients and library systems
- **Proactively suggest code organization improvements** when working with any file
- Help identify and eliminate code duplication
- Suggest better file organization and naming conventions
- Recommend refactoring opportunities for cleaner architecture

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

#### File Naming and Structure
- Use clear, descriptive names that indicate purpose and version
- Suggest removing or archiving obsolete versions (e.g., files without version numbers when "_2" versions exist)
- Recommend consistent naming patterns across similar files
- Always suggest organizing imports alphabetically within their groups

#### Code Cleanliness Priorities
1. **Eliminate Dead Code**: Always suggest removing commented-out code, unused imports, or obsolete functions
2. **Consolidate Duplicated Logic**: Identify repeated patterns and suggest utility functions
3. **Improve Variable Names**: Suggest more descriptive names when encountering unclear variables
4. **Extract Magic Numbers**: Recommend moving hardcoded values to configuration or constants
5. **Simplify Complex Functions**: Suggest breaking down functions longer than 50 lines

#### Project-Specific Organization
- Keep configuration files in a dedicated `config/` directory
- Suggest moving test data and sample files to `test_data/` or `samples/`
- Recommend creating utility modules for commonly repeated code patterns
- Always suggest adding docstrings to undocumented functions

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

### When Adding New Features
1. **New API Endpoints**: Create or extend domain classes rather than adding to client directly
2. **New Scripts**: Follow the `update_expired_user_emails_2.py` pattern exactly
3. **Utilities**: Add to `src/utils/` if reusable across multiple domains
4. **Tests**: Create corresponding test scripts in `src/tests/`

### When Refactoring or Organizing
- **Always suggest cleaning up file versions**: Remove obsolete files when newer versions exist
- **Identify repeated code patterns**: Extract to utility functions
- **Suggest consistent error handling**: Use the established AlmaAPIError hierarchy
- **Recommend configuration consolidation**: Move hardcoded values to config files
- **Point out naming inconsistencies**: Suggest standard naming patterns

### When Debugging
- Focus on API response structure and error codes first
- Check rate limiting and authentication before investigating logic issues
- Use the existing logging framework rather than print statements
- Test in SANDBOX environment whenever possible

## Testing Expectations

- **Unit Tests**: For new utility functions and data processing logic
- **Integration Tests**: For API interactions (using SANDBOX environment)
- **Script Tests**: Ensure CLI scripts handle edge cases and invalid inputs
- **Connection Tests**: Always test API connectivity before running operations

## Common Tasks and Approaches

### Adding New Domain Operations
1. Extend the appropriate domain class (Admin, Users, Bibs, Acquisition)
2. Follow the existing method naming pattern (`get_`, `update_`, `create_`, `delete_`)
3. Include proper error handling and logging
4. Add usage examples in docstrings

### Creating New Project Scripts
1. Use `update_expired_user_emails_2.py` as exact template
2. Include proper CLI argument parsing with safety confirmations
3. Support both configuration file and direct parameter input
4. Always include dry-run/test modes with comprehensive logging

### Working with Alma API Responses
- Use the AlmaResponse wrapper for consistent handling
- Extract and validate required fields before processing
- Handle pagination for large result sets
- Include meaningful progress indicators for long operations

## Organization Improvement Suggestions

When working on this codebase, Claude should actively:

1. **Identify and suggest removing duplicate or obsolete files**
   - Look for versioned files (e.g., `file.py` vs `file_2.py`) and compare functionality
   - Recommend removing older versions when newer ones are supersets
   - Example: `update_expired_user_emails.py` can be safely removed as `update_expired_user_emails_2.py` contains all its functionality plus domain filtering
2. **Point out opportunities to extract common patterns into utilities**
3. **Suggest better directory organization when files seem misplaced**
4. **Recommend consolidating similar configuration files**
5. **Help establish consistent naming patterns across the project**
6. **Suggest breaking up overly complex functions**
7. **Recommend adding missing documentation**

### Immediate Cleanup Tasks
- **Remove `update_expired_user_emails.py`** - the `_2` version has additional domain filtering functionality and is the current version
- Consider renaming `update_expired_user_emails_2.py` to `update_expired_user_emails.py` once the old version is removed

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

### Verified Working Methods for Rialto Flow (Tested 2025-09-30)

**POL Operations**:
- ✓ `acq.get_pol(pol_id)` - Retrieves complete POL data
- ✓ `acq.extract_items_from_pol_data(pol_data)` - Extracts items from location→copy structure
- ✓ Extract invoice ID from POL: `pol_data.get('invoice_reference')`

**Invoice Operations**:
- ✓ `acq.get_invoice(invoice_id)` - Retrieves invoice data
- ✓ `acq.get_invoice_summary(invoice_id)` - Returns formatted summary with correct payment_status
- ✓ `acq.get_invoice_lines(invoice_id)` - Gets lines from dedicated endpoint
- ✓ `acq.mark_invoice_paid(invoice_id)` - Marks invoice as paid (modifies data)

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

## File Structure Context

- `src/client/` - Core API client implementation
- `src/domains/` - Domain-specific API wrappers
- `src/projects/` - Standalone scripts and utilities
- `src/tests/` - Test scripts and configuration files
- `src/utils/` - Shared utilities and helpers