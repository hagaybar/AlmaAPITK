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
   - **update_expired_user_emails.py**: Script for updating email addresses of expired users
   - **Alma_File_Loader_from_Set.py**: Utility for loading files from Alma sets

4. **Utilities** (`src/utils/`)
   - **tsv_generator.py**: TSV file generation utilities

### Key Design Patterns

- **Client-Domain Pattern**: AlmaAPIClient serves as the foundation, domain classes use it for specific operations
- **Environment-Aware**: All classes support SANDBOX/PRODUCTION environments
- **Response Wrapping**: AlmaResponse class provides consistent response handling
- **Error Hierarchy**: AlmaAPIError, AlmaValidationError, AlmaRateLimitError for specific error types

## Development Commands

### Running Scripts
```bash
# Run email update script
python src/projects/update_expired_user_emails.py --set-id 12345678900004146 --environment SANDBOX

# Run with configuration file
python src/projects/update_expired_user_emails.py --config config.json --live

# Run with TSV input
python src/projects/update_expired_user_emails.py --tsv users.tsv --pattern "expired-{user_id}@university.edu"
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

## Configuration Files

The project uses JSON configuration files for different environments:
- `src/tests/email_update_config.json` - Sandbox configuration
- `src/tests/email_update_config_prod.json` - Production configuration
- `src/tests/email_update_config_from_tsv.json` - TSV-based configuration

## Key Usage Patterns

### Creating API Client
```python
from src.client.AlmaAPIClient import AlmaAPIClient

# Initialize client
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'

# Test connection
if client.test_connection():
    print("Connected successfully")
```

### Working with Sets
```python
from src.domains.admin import Admin

admin = Admin(client)
members = admin.get_set_members('25793308630004146')  # Returns list of IDs
```

### Processing Users
```python
from src.domains.users import Users

users = Users(client)
user_data = users.get_user_by_id('user123')
```

## Important Notes

- Always test in SANDBOX environment before running in PRODUCTION
- The API client includes rate limiting and retry logic
- All domain classes inherit logging from the main client
- Email update scripts support both set-based and TSV-based input
- Configuration files should never contain actual API keys (use environment variables)

## File Structure Context

- `src/client/` - Core API client implementation
- `src/domains/` - Domain-specific API wrappers
- `src/projects/` - Standalone scripts and utilities
- `src/tests/` - Test scripts and configuration files
- `src/utils/` - Shared utilities and helpers