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
- Use present tense and imperative mood: "Add feature" not "Added feature"
- Be specific about what changed: "Add domain filtering to email validation" not "Update script"
- For bug fixes: "Fix email pattern validation for special characters"
- For features: "Add TSV revert mode support for email updates"
- For refactoring: "Extract email validation logic to separate method"
- For cleanup: "Remove obsolete update_expired_user_emails.py (superseded by _2 version)"
- For documentation: "Update claude.md with git workflow and organization guidance"

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

## File Structure Context

- `src/client/` - Core API client implementation
- `src/domains/` - Domain-specific API wrappers
- `src/projects/` - Standalone scripts and utilities
- `src/tests/` - Test scripts and configuration files
- `src/utils/` - Shared utilities and helpers