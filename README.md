# almaapitk

A Python toolkit for interacting with the Ex Libris Alma ILS (Integrated Library System) API.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Simple API Client**: Easy-to-use HTTP client with automatic authentication and error handling
- **Domain Classes**: High-level abstractions for common Alma operations
  - `Acquisitions` - POL operations, invoicing, item receiving
  - `Analytics` - Analytics reports with pagination support
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
# Note: Acquisitions.get_pol returns a plain dict directly
pol = acq.get_pol("POL-12345")
print(f"POL Status: {pol['status']['value']}")

# User operations
# Note: get_user takes a primary ID (NOT email) and returns an AlmaResponse
users = Users(client)
user_response = users.get_user("PRIMARY_ID_12345")
user_data = user_response.json()
print(f"User: {user_data['full_name']}")
```

### Working with Bibliographic Records

```python
from almaapitk import AlmaAPIClient, BibliographicRecords

client = AlmaAPIClient('SANDBOX')
bibs = BibliographicRecords(client)

# Get a bib record (signature: get_record(mms_id, view="full", expand=None))
record = bibs.get_record("99123456789")

# Get holdings for a bib
holdings = bibs.get_holdings("99123456789")
```

### Resource Sharing

```python
from almaapitk import AlmaAPIClient, ResourceSharing

client = AlmaAPIClient('SANDBOX')
rs = ResourceSharing(client)

# Create a lending request
# Mandatory: partner_code, external_id, owner, format_type, title
# (citation_type is required unless mms_id is supplied)
result = rs.create_lending_request(
    partner_code="PARTNER_CODE",
    external_id="EXT-2025-001",
    owner="MAIN",                  # resource sharing library code
    format_type="PHYSICAL",
    title="Introduction to Python",
    citation_type="BOOK",
    author="Smith, John",
)
```

### Analytics Reports

```python
from almaapitk import AlmaAPIClient, Analytics

# Analytics API only works with PRODUCTION
client = AlmaAPIClient('PRODUCTION')
analytics = Analytics(client)

# Get column headers for a report
report_path = "/shared/University/Reports/MyReport"
headers = analytics.get_report_headers(report_path)
print(f"Columns: {headers}")

# Fetch rows with pagination (limit must be 25-1000)
rows = analytics.fetch_report_rows(report_path, limit=100, max_rows=500)
for row in rows:
    print(row)  # Dict with Column0, Column1, etc.

# Optional: pass a progress_callback to track progress for large reports.
# The callback receives one argument: the cumulative row count fetched so far.
def show_progress(rows_so_far: int) -> None:
    print(f"  fetched {rows_so_far} rows...")

rows = analytics.fetch_report_rows(
    report_path,
    limit=100,
    max_rows=500,
    progress_callback=show_progress,
)
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
| `Analytics` | Analytics reports with pagination (ResumptionToken) |
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

See [Quick Start → Setup](#setup) for environment variable setup. The client
automatically picks `ALMA_SB_API_KEY` for `'SANDBOX'` and `ALMA_PROD_API_KEY`
for `'PRODUCTION'`.

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

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Links

- [Alma API Documentation](https://developers.exlibrisgroup.com/alma/apis/)
- [GitHub Repository](https://github.com/hagaybar/AlmaAPITK)
