# Getting Started with AlmaAPITK

**Version:** 0.2.0 | **License:** MIT | **Author:** Hagay Bar

AlmaAPITK is a Python toolkit for interacting with the Ex Libris Alma ILS (Integrated Library System) API. It provides a structured approach to API operations with domain-specific classes and comprehensive error handling.

---

## Prerequisites

### Python Version

AlmaAPITK requires **Python 3.12 or higher**.

```bash
# Check your Python version
python --version
# Expected: Python 3.12.x or higher
```

### Alma API Keys

You need API keys from the Ex Libris Developer Network to authenticate with the Alma API. AlmaAPITK supports two environments:

| Environment | Purpose | API Key Variable |
|-------------|---------|------------------|
| **SANDBOX** | Testing and development | `ALMA_SB_API_KEY` |
| **PRODUCTION** | Live operations | `ALMA_PROD_API_KEY` |

#### How to Obtain API Keys

1. **Register** at the [Ex Libris Developer Network](https://developers.exlibrisgroup.com/)
2. **Navigate** to your institution's API configuration in the Alma Admin Console
3. **Create** API keys with appropriate permissions for the operations you need:
   - **Read-only** keys for GET operations
   - **Read/Write** keys for POST, PUT, DELETE operations
4. **Note** your API region (EU, NA, APAC) - the toolkit is pre-configured for the EU region (`api-eu.hosted.exlibrisgroup.com`)

> **Security Note:** Never commit API keys to version control. Always use environment variables.

---

## Installation

### From PyPI (when published)

```bash
pip install almaapitk
```

### Using Poetry (recommended for development)

```bash
# Add to existing project
poetry add almaapitk

# Or install with all dependencies
poetry install
```

### From GitHub

```bash
# Install directly from GitHub
pip install git+https://github.com/hagaybar/AlmaAPITK.git

# Or clone and install in development mode
git clone https://github.com/hagaybar/AlmaAPITK.git
cd AlmaAPITK
pip install -e .
```

### Verify Installation

```python
import almaapitk
print(almaapitk.__version__)
# Expected output: 0.2.0
```

---

## Configuration

### Setting Environment Variables

AlmaAPITK reads API keys from environment variables. Set them based on your operating system:

#### Linux / macOS

```bash
# For sandbox/development
export ALMA_SB_API_KEY='your_sandbox_api_key_here'

# For production
export ALMA_PROD_API_KEY='your_production_api_key_here'

# Add to ~/.bashrc or ~/.zshrc for persistence
echo 'export ALMA_SB_API_KEY="your_sandbox_api_key_here"' >> ~/.bashrc
```

#### Windows (PowerShell)

```powershell
# Temporary (current session only)
$env:ALMA_SB_API_KEY = 'your_sandbox_api_key_here'
$env:ALMA_PROD_API_KEY = 'your_production_api_key_here'

# Permanent (requires admin)
[Environment]::SetEnvironmentVariable('ALMA_SB_API_KEY', 'your_key', 'User')
```

#### Windows (Command Prompt)

```cmd
set ALMA_SB_API_KEY=your_sandbox_api_key_here
set ALMA_PROD_API_KEY=your_production_api_key_here
```

#### Using a .env File (with python-dotenv)

Create a `.env` file in your project root:

```ini
# .env file (add to .gitignore!)
ALMA_SB_API_KEY=your_sandbox_api_key_here
ALMA_PROD_API_KEY=your_production_api_key_here
```

Load it in your Python code:

```python
from dotenv import load_dotenv
load_dotenv()

from almaapitk import AlmaAPIClient
client = AlmaAPIClient('SANDBOX')
```

> **Important:** Always add `.env` to your `.gitignore` file to prevent accidentally committing API keys.

---

## Quick Start (5-minute tutorial)

### Step 1: Initialize the Client

```python
from almaapitk import AlmaAPIClient

# Initialize for sandbox environment (default)
client = AlmaAPIClient('SANDBOX')
# Output: Configured for SANDBOX environment

# Or for production
# client = AlmaAPIClient('PRODUCTION')
```

### Step 2: Test Your Connection

```python
# Verify API connectivity
if client.test_connection():
    print("Ready to use Alma API!")
else:
    print("Check your API key and network connection")
```

**Expected output:**
```
Successfully connected to Alma API (SANDBOX)
Ready to use Alma API!
```

### Step 3: Make Your First API Call

```python
# Get list of libraries configured in Alma
response = client.get('almaws/v1/conf/libraries')

# Check if request was successful
if response.success:
    data = response.json()
    print(f"Found {data['total_record_count']} libraries")

    # List library names
    for library in data.get('library', []):
        print(f"  - {library['name']} (Code: {library['code']})")
else:
    print(f"Request failed with status: {response.status_code}")
```

**Expected output:**
```
Found 5 libraries
  - Main Library (Code: MAIN)
  - Science Library (Code: SCI)
  - Law Library (Code: LAW)
  ...
```

### Step 4: Handle Errors Gracefully

```python
from almaapitk import AlmaAPIClient, AlmaAPIError, AlmaValidationError

client = AlmaAPIClient('SANDBOX')

try:
    # Try to get a non-existent bibliographic record
    response = client.get('almaws/v1/bibs/invalid_mms_id')
    print(response.json())

except AlmaAPIError as e:
    print(f"API Error: {e}")
    print(f"Status Code: {e.status_code}")

except AlmaValidationError as e:
    print(f"Validation Error: {e}")
```

### Complete Working Example

Here is a complete script you can save and run:

```python
#!/usr/bin/env python3
"""
AlmaAPITK Quick Start Example
Demonstrates basic API connectivity and operations.
"""

from almaapitk import AlmaAPIClient, AlmaAPIError

def main():
    # Initialize client (uses ALMA_SB_API_KEY environment variable)
    try:
        client = AlmaAPIClient('SANDBOX')
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Make sure ALMA_SB_API_KEY environment variable is set")
        return

    # Test connection
    print("\n=== Testing Connection ===")
    if not client.test_connection():
        print("Connection failed. Check your API key.")
        return

    # Get libraries
    print("\n=== Listing Libraries ===")
    try:
        response = client.get('almaws/v1/conf/libraries')
        data = response.json()

        print(f"Total libraries: {data['total_record_count']}")
        for lib in data.get('library', [])[:5]:  # Show first 5
            print(f"  - {lib['name']} ({lib['code']})")

    except AlmaAPIError as e:
        print(f"Error fetching libraries: {e}")

    # Check current environment
    print(f"\n=== Environment Info ===")
    print(f"Current environment: {client.get_environment()}")
    print(f"Base URL: {client.get_base_url()}")

if __name__ == '__main__':
    main()
```

Save this as `quickstart.py` and run:

```bash
python quickstart.py
```

---

## Working with Domain Classes

AlmaAPITK provides specialized domain classes for common operations:

```python
from almaapitk import (
    AlmaAPIClient,
    Admin,           # Set management
    Users,           # User operations
    Acquisitions,    # POL and invoicing
    BibliographicRecords,  # Bib records
    ResourceSharing  # Lending/borrowing
)

# Initialize client
client = AlmaAPIClient('SANDBOX')

# Create domain instances
admin = Admin(client)
users = Users(client)
acquisitions = Acquisitions(client)

# Example: List available sets
sets_response = admin.list_sets(limit=10)
print(f"Found {sets_response.json()['total_record_count']} sets")

# Example: Get user information
# user_data = users.get_user('user_primary_id')
```

---

## Next Steps

### Domain Guides

- **[Resource Sharing Guide](./RESOURCE_SHARING_GUIDE.md)** - Lending and borrowing operations via the Partners API

### API Reference

- **[API Contract](./API_CONTRACT.md)** - Complete list of public API symbols and migration guide

### Additional Resources

- **[Ex Libris Developer Network](https://developers.exlibrisgroup.com/)** - Official Alma API documentation
- **[GitHub Repository](https://github.com/hagaybar/AlmaAPITK)** - Source code and issue tracking
- **[Alma REST APIs Documentation](https://developers.exlibrisgroup.com/alma/apis/)** - Endpoint reference

### Getting Help

If you encounter issues:

1. Check that your API key has the required permissions
2. Verify you're using the correct environment (SANDBOX vs PRODUCTION)
3. Review the error message - AlmaAPITK extracts detailed error information from Alma responses
4. Open an issue on the [GitHub repository](https://github.com/hagaybar/AlmaAPITK/issues)

---

## Summary

| Step | Action |
|------|--------|
| 1. Prerequisites | Python 3.12+, Alma API keys |
| 2. Install | `pip install almaapitk` or `poetry add almaapitk` |
| 3. Configure | Set `ALMA_SB_API_KEY` or `ALMA_PROD_API_KEY` environment variable |
| 4. Connect | `client = AlmaAPIClient('SANDBOX')` |
| 5. Use | `response = client.get('almaws/v1/...')` |

**You're ready to start building with AlmaAPITK!**
