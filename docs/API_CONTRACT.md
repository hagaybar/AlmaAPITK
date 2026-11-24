# AlmaAPITK Public API Contract

**Version:** 0.2.0

## Overview

AlmaAPITK provides a Python toolkit for interacting with the Alma ILS (Integrated Library System) API. This document defines the stable public API surface that consumers should rely on.

## Supported Imports

**All consumer code should import from `almaapitk` only:**

```python
# Recommended: Import the package
import almaapitk
client = almaapitk.AlmaAPIClient('SANDBOX')

# Alternative: Import specific symbols
from almaapitk import AlmaAPIClient, AlmaAPIError, AlmaValidationError

# Domain classes for specific operations
from almaapitk import Acquisitions, Users, Admin, BibliographicRecords, ResourceSharing
```

## Public API Symbols

The following symbols are exported and part of the stable public API:

### Core Classes

| Symbol | Type | Description |
|--------|------|-------------|
| `__version__` | str | Package version string (currently "0.2.0") |
| `AlmaAPIClient` | class | Main API client providing HTTP methods (GET, POST, PUT, DELETE), `iter_paged`, `raw_request` (call any Alma path; lower guarantee tier, see `guides/raw-requests.md`), environment management, and authentication |
| `AlmaResponse` | class | Response wrapper with `.data`, `.json()`, `.text()`, `.success`, and `.status_code` properties |
| `AlmaAPIError` | exception | Base exception for Alma API errors with `status_code` and `response` attributes |
| `AlmaValidationError` | exception | Exception for input validation failures (inherits from `ValueError`) |

### Domain Classes

| Symbol | Type | Description |
|--------|------|-------------|
| `Admin` | class | Sets management (BIB_MMS, USER sets) |
| `Users` | class | User management, email updates |
| `BibliographicRecords` | class | Bib records, holdings, items, scan-in |
| `Acquisitions` | class | POL operations, invoicing, item receiving |
| `ResourceSharing` | class | Lending/borrowing via Partners API |

### Utilities

| Symbol | Type | Description |
|--------|------|-------------|
| `TSVGenerator` | class | TSV file generation utilities |
| `CitationMetadataError` | exception | Exception for citation metadata enrichment errors |

### Personal-data mask (issue #256)

| Symbol | Type | Description |
|--------|------|-------------|
| `redact` | function | `redact(obj)`: masked **copy** of a record, list or string, by Alma field name. The argument is never changed. |
| `redact_text` | function | `redact_text(text)`: masked copy of a string (log line, message, serialised body). Non-strings are returned unchanged. |

Returned **data** stays raw in every public method (in-memory data is never masked).
One exception, by design: where a method puts an error's text into its returned dict
(`result['error']` in `Users` and `Admin`, built from `str(exc)`), that string is masked.
`str()` / `repr()` of `AlmaAPIError`, `AlmaValidationError` and their subclasses are masked
(`repr` shows only the masked message); `exc.args` keep the raw message. `requests`
errors chained as `__cause__` or re-raised by the client are masked copies of the same
type. `repr(AlmaResponse)` shows status only. Field list and
rules: `docs/site/guides/personal-data-mask.md`.

### Basic Usage

```python
from almaapitk import AlmaAPIClient, AlmaAPIError, Acquisitions

# Initialize client (requires ALMA_SB_API_KEY or ALMA_PROD_API_KEY env var)
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'

# Make direct API calls
try:
    response = client.get('almaws/v1/conf/libraries')
    if response.success:
        data = response.json()
except AlmaAPIError as e:
    print(f"API error: {e} (status: {e.status_code})")

# Use domain classes for specialized operations
acq = Acquisitions(client)
pol_data = acq.get_pol("POL-12345")
```

## Internal/Unsupported Modules

The following modules are **internal implementation details** and should NOT be imported directly. They may change without notice:

| Module | Status | Notes |
|--------|--------|-------|
| `almaapitk.client.*` | Internal | Use `almaapitk.AlmaAPIClient` instead |
| `almaapitk.domains.*` | Internal | Use domain classes from `almaapitk` directly |
| `almaapitk.utils.*` | Internal | Use `almaapitk.TSVGenerator` instead |
| `almaapitk.alma_logging.*` | Internal | Logging infrastructure |

## Migration Guide

If you currently import from internal modules, please migrate to the public API:

### Before (deprecated)

```python
# These imports may break in future versions
from almaapitk.client.AlmaAPIClient import AlmaAPIClient
from almaapitk.domains.acquisition import Acquisitions
```

### After (recommended)

```python
# Stable public API
from almaapitk import AlmaAPIClient, Acquisitions, AlmaAPIError, AlmaResponse
```

## Versioning Policy

- Public API symbols follow semantic versioning
- Breaking changes will increment the major version
- Internal modules may change at any time without version bumps

## Questions?

See the main [CLAUDE.md](../CLAUDE.md) for development guidelines and project documentation.
