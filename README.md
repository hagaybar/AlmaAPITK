# almaapitk

A Python toolkit for interacting with the Ex Libris Alma ILS (Integrated Library System) API.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Simple API Client**: Easy-to-use HTTP client with automatic authentication and error handling
- **Domain Classes**: High-level abstractions for common Alma operations
  - `Acquisitions` - POL operations, invoicing, item receiving
  - `Users` - User management, email updates
  - `BibliographicRecords` - Bib records, holdings, items
  - `Admin` - Sets management (BIB_MMS, USER)
  - `ResourceSharing` - Lending/borrowing via Partners API
- **Environment Support**: Seamless switching between Sandbox and Production
- **Response Wrapper**: Consistent response handling with `AlmaResponse`
- **Comprehensive Logging**: Built-in logging with automatic API key redaction

## Installation

```bash
pip install almaapitk
```

Or with Poetry:

```bash
poetry add almaapitk
```

## Quick Start

### Setup

Set your Alma API keys as environment variables:

```bash
export ALMA_SB_API_KEY="your-sandbox-api-key"
export ALMA_PROD_API_KEY="your-production-api-key"
```

### Basic Usage

```python
from almaapitk import AlmaAPIClient, AlmaAPIError

# Initialize client (uses ALMA_SB_API_KEY)
client = AlmaAPIClient('SANDBOX')

# Make API calls
try:
    response = client.get('almaws/v1/conf/libraries')
    if response.success:
        libraries = response.json()
        for lib in libraries.get('library', []):
            print(f"Library: {lib['name']}")
except AlmaAPIError as e:
    print(f"API error: {e} (status: {e.status_code})")
```

### Using Domain Classes

```python
from almaapitk import AlmaAPIClient, Acquisitions, Users

client = AlmaAPIClient('SANDBOX')

# Acquisitions operations
acq = Acquisitions(client)
pol = acq.get_pol("POL-12345")
print(f"POL Status: {pol['status']['value']}")

# User operations
users = Users(client)
user = users.get_user("user@example.com")
print(f"User: {user['full_name']}")
```

### Working with Bibliographic Records

```python
from almaapitk import AlmaAPIClient, BibliographicRecords

client = AlmaAPIClient('SANDBOX')
bibs = BibliographicRecords(client)

# Get a bib record
record = bibs.get_bib("99123456789")

# Get holdings for a bib
holdings = bibs.get_holdings("99123456789")
```

### Resource Sharing

```python
from almaapitk import AlmaAPIClient, ResourceSharing

client = AlmaAPIClient('SANDBOX')
rs = ResourceSharing(client)

# Create a lending request
request_data = {
    "title": "Introduction to Python",
    "author": "Smith, John",
    "format_type": "PHYSICAL",
    "citation_type": "BOOK"
}
result = rs.create_lending_request("PARTNER_CODE", request_data)
```

## API Reference

### Core Classes

| Class | Description |
|-------|-------------|
| `AlmaAPIClient` | Main HTTP client for Alma API |
| `AlmaResponse` | Response wrapper with `.data`, `.json()`, `.success`, `.status_code` |
| `AlmaAPIError` | Base exception for API errors |
| `AlmaValidationError` | Exception for validation failures |

### Domain Classes

| Class | Description |
|-------|-------------|
| `Acquisitions` | POL operations, invoicing, item receiving |
| `Users` | User management, email updates |
| `BibliographicRecords` | Bib records, holdings, items, scan-in |
| `Admin` | Sets management (BIB_MMS, USER sets) |
| `ResourceSharing` | Lending/borrowing via Partners API |

### Utilities

| Class | Description |
|-------|-------------|
| `TSVGenerator` | TSV file generation utilities |
| `CitationMetadataError` | Exception for citation metadata errors |

## Environment Configuration

The client automatically selects the appropriate API key based on the environment:

```python
# Uses ALMA_SB_API_KEY
client = AlmaAPIClient('SANDBOX')

# Uses ALMA_PROD_API_KEY
client = AlmaAPIClient('PRODUCTION')
```

## Error Handling

```python
from almaapitk import AlmaAPIClient, AlmaAPIError, AlmaValidationError

client = AlmaAPIClient('SANDBOX')

try:
    response = client.get('almaws/v1/users/invalid-user')
except AlmaValidationError as e:
    # Input validation failed
    print(f"Validation error: {e}")
except AlmaAPIError as e:
    # API returned an error
    print(f"API error: {e}")
    print(f"Status code: {e.status_code}")
    print(f"Response: {e.response}")
```

## Requirements

- Python 3.12+
- requests
- pandas
- openpyxl
- boto3
- pypdf2

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Links

- [Alma API Documentation](https://developers.exlibrisgroup.com/alma/apis/)
- [GitHub Repository](https://github.com/hagaybar/AlmaAPITK)
