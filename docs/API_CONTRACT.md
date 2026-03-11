# AlmaAPITK Public API Contract

**Version:** 0.1.0

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
```

## Public API Symbols

The following symbols are exported and part of the stable public API:

| Symbol | Type | Description |
|--------|------|-------------|
| `__version__` | str | Package version string (currently "0.1.0") |
| `AlmaAPIClient` | class | Main API client providing HTTP methods (GET, POST, PUT, DELETE), environment management, and authentication |
| `AlmaResponse` | class | Response wrapper with `.data`, `.json()`, `.text()`, `.success`, and `.status_code` properties |
| `AlmaAPIError` | exception | Base exception for Alma API errors with `status_code` and `response` attributes |
| `AlmaValidationError` | exception | Exception for input validation failures (inherits from `ValueError`) |

### Basic Usage

```python
from almaapitk import AlmaAPIClient, AlmaAPIError

# Initialize client (requires ALMA_SB_API_KEY or ALMA_PROD_API_KEY env var)
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'

# Make API calls
try:
    response = client.get('almaws/v1/conf/libraries')
    if response.success:
        data = response.json()
except AlmaAPIError as e:
    print(f"API error: {e} (status: {e.status_code})")
```

## Internal/Unsupported Modules

The following modules are **internal implementation details** and should NOT be imported directly. They may change without notice:

| Module | Status | Notes |
|--------|--------|-------|
| `src.client.*` | Internal | Use `almaapitk.AlmaAPIClient` instead |
| `src.domains.*` | Internal | Domain classes (Admin, Users, Bibs, Acquisitions, etc.) |
| `src.utils.*` | Internal | Utility modules |
| `src.alma_logging.*` | Internal | Logging infrastructure |

## Migration Guide

If you currently import from internal modules, please migrate to the public API:

### Before (deprecated)

```python
# These imports may break in future versions
from src.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError
from client.AlmaAPIClient import AlmaResponse
```

### After (recommended)

```python
# Stable public API
from almaapitk import AlmaAPIClient, AlmaAPIError, AlmaResponse
```

## Versioning Policy

- Public API symbols follow semantic versioning
- Breaking changes will increment the major version
- Internal modules may change at any time without version bumps

## Questions?

See the main [CLAUDE.md](../CLAUDE.md) for development guidelines and project documentation.
