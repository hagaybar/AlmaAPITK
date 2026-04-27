# AlmaAPITK Logging Configuration Guide

This guide provides comprehensive documentation for using the logging system in AlmaAPITK. The logging infrastructure captures API requests, responses, errors, and performance metrics with automatic sensitive data redaction.

## Table of Contents

- [Logging Overview](#logging-overview)
- [Using the Logger](#using-the-logger)
- [Log Levels](#log-levels)
- [What to Log](#what-to-log)
- [Log File Structure](#log-file-structure)
- [Configuration](#configuration)
- [Security Notes](#security-notes)

---

## Logging Overview

The AlmaAPITK logging system provides structured logging for all API operations with the following features:

### What Gets Logged

| Category | Description | Example |
|----------|-------------|---------|
| **API Requests** | HTTP method, endpoint, parameters, headers | `POST /almaws/v1/acq/invoices` |
| **API Responses** | Status code, response body, timing | `200 OK (234ms)` |
| **Errors** | Error codes, messages, stack traces | `AlmaAPIError: 60260` |
| **Operations** | Method entry/exit, results | `Invoice created: INV-001` |
| **Performance** | Request duration, timing metrics | `duration_ms: 234` |

### Automatic API Key Redaction

All sensitive data is automatically redacted before being written to logs:

```
Original header: "Authorization": "apikey l7xx1234567890abcdef"
Logged header:   "Authorization": "apikey ***REDACTED***"
```

Redaction patterns include:
- `apikey`, `api_key`
- `password`
- `token`
- `secret`
- `authorization`, `auth`

### Log File Locations

All logs are stored in the `logs/` directory (automatically excluded from git):

```
logs/
├── api_requests/YYYY-MM-DD/     # Daily API request/response logs
│   ├── acquisitions.log         # Acquisitions domain operations
│   ├── users.log                # User management operations
│   ├── bibs.log                 # Bibliographic record operations
│   ├── admin.log                # Administrative operations
│   └── api_client.log           # Low-level HTTP operations
├── errors/YYYY-MM-DD.log        # All errors across domains
├── performance/YYYY-MM-DD.log   # Performance metrics
└── tests/YYYY-MM-DD/            # Test execution logs
```

---

## Using the Logger

### Import and Initialize

The primary entry point is the `get_logger()` function:

```python
from almaapitk.alma_logging import get_logger

# Create a logger for a specific domain
logger = get_logger('acquisitions', environment='SANDBOX')
```

Parameters:
- `domain`: Domain name (acquisitions, users, bibs, admin, api_client, or custom)
- `environment`: Alma environment (SANDBOX or PRODUCTION)
- `config`: Optional LoggingConfig instance (uses defaults if not provided)

### In Domain Classes

Integrate logging in domain classes by initializing the logger in `__init__`:

```python
from almaapitk.alma_logging import get_logger

class Acquisitions:
    def __init__(self, client):
        self.client = client
        self.logger = get_logger('acquisitions', client.environment)

    def create_invoice_simple(self, invoice_number, vendor_code, total_amount):
        # Log method entry with parameters
        self.logger.info(
            "Creating simple invoice",
            invoice_number=invoice_number,
            vendor_code=vendor_code,
            total_amount=total_amount
        )

        try:
            result = self._create_invoice(...)

            # Log success with result identifiers
            self.logger.info(
                "Invoice created successfully",
                invoice_id=result['id'],
                invoice_number=invoice_number
            )
            return result

        except AlmaAPIError as e:
            # Log error with full context
            self.logger.error(
                "Failed to create invoice",
                invoice_number=invoice_number,
                error_code=e.status_code,
                error_message=str(e),
                tracking_id=getattr(e, 'tracking_id', None)
            )
            raise
```

### In Scripts

For standalone scripts, initialize the logger at the start:

```python
from almaapitk.alma_logging import get_logger

def main():
    # Initialize logger for the script
    logger = get_logger('test_invoice_creation', environment='SANDBOX')

    logger.info(
        "Starting test suite",
        environment='SANDBOX',
        mode='DRY_RUN',
        config_file='config/test_config.json'
    )

    try:
        # Run operations...
        results = run_tests()

        logger.info(
            "Test suite completed",
            total=len(results),
            passed=sum(1 for r in results if r['success']),
            failed=sum(1 for r in results if not r['success'])
        )

    except Exception as e:
        logger.log_error(e, operation="test_suite")
        raise

if __name__ == "__main__":
    main()
```

### Logging API Requests and Responses

Use the specialized methods for request/response logging:

```python
# Log an outgoing API request
logger.log_request(
    method='POST',
    endpoint='almaws/v1/acq/invoices',
    params={'op': 'paid'},
    headers={'Content-Type': 'application/json'},
    body={'invoice_number': 'INV-001'}
)

# Log the API response with timing
import time
start_time = time.time()
response = requests.post(...)
duration_ms = (time.time() - start_time) * 1000

logger.log_response(response, duration_ms=duration_ms)
```

### Logging Exceptions with Context

Use `log_error()` to capture exceptions with full context:

```python
try:
    result = client.get(endpoint)
except AlmaAPIError as e:
    logger.log_error(
        e,
        operation="get_invoice",
        invoice_number="INV-001",
        endpoint=endpoint
    )
    raise
```

This logs:
- Exception type and message
- Full stack trace
- All provided context fields
- Domain and environment

---

## Log Levels

The logging system supports five standard log levels:

| Level | When to Use | Example |
|-------|-------------|---------|
| **DEBUG** | Detailed diagnostic information, API request/response bodies | `logger.debug("POL data", pol=data)` |
| **INFO** | Normal operations, success messages, operational events | `logger.info("Invoice created", invoice_id="123")` |
| **WARNING** | Recoverable issues, retries, fallback behavior | `logger.warning("Retrying request", attempt=2)` |
| **ERROR** | Operation failures, API errors, validation failures | `logger.error("Create failed", error_code=60260)` |
| **CRITICAL** | System failures, cannot continue, authentication failures | `logger.critical("Auth failed", reason="Invalid API key")` |

### Level Selection Guidelines

```python
# DEBUG - Detailed data for troubleshooting
logger.debug("Raw API response", response_body=response.json())

# INFO - Standard operational messages
logger.info("Processing batch", batch_size=100, batch_number=3)

# WARNING - Non-critical issues
logger.warning("Rate limit approaching", remaining=5)

# ERROR - Failures that need attention
logger.error("Invoice creation failed", invoice_number="INV-001", error="Vendor not found")

# CRITICAL - System-level failures
logger.critical("Database connection lost", retry_in_seconds=30)
```

### Domain Default Levels

| Domain | Default Level | Description |
|--------|---------------|-------------|
| acquisitions | DEBUG | Detailed logging for invoice/POL operations |
| api_client | DEBUG | All HTTP request/response details |
| users | INFO | Standard user operation logging |
| bibs | INFO | Standard bibliographic logging |
| admin | INFO | Standard administrative logging |

---

## What to Log

### Always Log

| Event Type | What to Include | Example |
|------------|-----------------|---------|
| **Method entry** | Method name, key parameters | `logger.info("Creating invoice", invoice_number="INV-001")` |
| **Successful operations** | Result identifiers, key outcomes | `logger.info("Invoice approved", invoice_id="123")` |
| **API errors** | Error code, message, tracking ID | `logger.error("API error", code=60260, tracking_id="E01-...")` |
| **Validation failures** | Failed field, expected vs actual | `logger.warning("Validation failed", field="amount", expected=">0")` |
| **State changes** | Old state, new state | `logger.info("Invoice status changed", old="Draft", new="Active")` |
| **Test execution** | Test name, parameters, result | `logger.info("Test passed", test="create_invoice")` |

### Example: Comprehensive Method Logging

```python
def receive_items_for_pol(self, pol_id: str, items: list) -> dict:
    """Receive items for a POL with full logging."""

    # Log method entry
    self.logger.info(
        "Receiving items for POL",
        pol_id=pol_id,
        item_count=len(items)
    )

    results = {'received': [], 'failed': []}

    for item in items:
        try:
            # Log individual item processing
            self.logger.debug(
                "Processing item",
                pol_id=pol_id,
                item_barcode=item.get('barcode')
            )

            result = self._receive_item(pol_id, item)
            results['received'].append(result)

            self.logger.info(
                "Item received",
                pol_id=pol_id,
                item_id=result['id']
            )

        except AlmaAPIError as e:
            results['failed'].append({'item': item, 'error': str(e)})

            self.logger.error(
                "Failed to receive item",
                pol_id=pol_id,
                item_barcode=item.get('barcode'),
                error_code=e.status_code,
                error_message=str(e)
            )

    # Log method completion with summary
    self.logger.info(
        "Receiving complete",
        pol_id=pol_id,
        received_count=len(results['received']),
        failed_count=len(results['failed'])
    )

    return results
```

### Never Log

| Data Type | Reason |
|-----------|--------|
| API keys | Security - automatically redacted |
| Passwords/tokens | Security - automatically redacted |
| Full responses with PII | Privacy - log summary instead |
| Credit card numbers | Compliance |
| Social security numbers | Compliance |

---

## Log File Structure

### Directory Layout

```
logs/
├── api_requests/                    # Domain-specific request logs
│   └── 2025-10-23/                 # Organized by date
│       ├── acquisitions.log        # Acquisitions domain
│       ├── users.log               # Users domain
│       ├── bibs.log                # Bibs domain
│       ├── admin.log               # Admin domain
│       └── api_client.log          # Low-level HTTP
│
├── errors/                          # Consolidated error logs
│   └── 2025-10-23.log              # All errors from all domains
│
├── performance/                     # Performance metrics
│   └── 2025-10-23.log
│
└── tests/                           # Test execution logs
    └── 2025-10-23/
        └── test_invoice_creation.log
```

### Log Rotation

Logs automatically rotate based on size:

| Setting | Default | Description |
|---------|---------|-------------|
| `max_bytes` | 10MB (10485760) | Maximum size before rotation |
| `backup_count` | 10 | Number of backup files to keep |

When a log reaches `max_bytes`, it's renamed to `{filename}.1`, existing `.1` becomes `.2`, etc. Files beyond `backup_count` are deleted.

### JSON Log Format

Log files use JSON Lines format (one JSON object per line):

```json
{"timestamp":"2025-10-23T14:30:45.123Z","level":"INFO","logger":"almapi.acquisitions","domain":"acquisitions","environment":"SANDBOX","message":"Creating invoice","context":{"invoice_number":"INV-001","vendor_code":"RIALTO"}}
{"timestamp":"2025-10-23T14:30:46.345Z","level":"INFO","logger":"almapi.acquisitions","domain":"acquisitions","environment":"SANDBOX","message":"Invoice created successfully","context":{"invoice_id":"35925532970004146"}}
```

Human-readable format (for documentation):

```json
{
  "timestamp": "2025-10-23T14:30:45.123Z",
  "level": "INFO",
  "logger": "almapi.acquisitions",
  "domain": "acquisitions",
  "environment": "SANDBOX",
  "message": "Creating invoice",
  "context": {
    "invoice_number": "INV-001",
    "vendor_code": "RIALTO"
  }
}
```

### Console Output Format

Console uses color-coded text format:

```
[2025-10-23 14:30:45] INFO     [acquisitions] Creating invoice (invoice_number=INV-001, vendor_code=RIALTO)
[2025-10-23 14:30:46] ERROR    [acquisitions] Failed to create invoice (error_code=60260)
```

Color codes:
- **DEBUG**: Cyan
- **INFO**: Green
- **WARNING**: Yellow
- **ERROR**: Red
- **CRITICAL**: Magenta

---

## Configuration

### Default Configuration

The logging system works out-of-the-box with sensible defaults. No configuration file is required.

Default settings:
- Log level: INFO for most domains, DEBUG for acquisitions and api_client
- Output: Both console and file
- Format: JSON for files, colored text for console
- Rotation: 10MB max, 10 backups
- Redaction: API keys, passwords, tokens, secrets

### Custom Configuration

1. **Copy the example configuration:**

```bash
cp config/logging_config.example.json config/logging_config.json
```

2. **Customize settings:**

```json
{
  "log_level": "INFO",
  "domains": {
    "acquisitions": {
      "enabled": true,
      "level": "DEBUG",
      "log_requests": true,
      "log_responses": true
    },
    "users": {
      "enabled": true,
      "level": "INFO",
      "log_requests": true,
      "log_responses": true
    },
    "bibs": {
      "enabled": true,
      "level": "INFO",
      "log_requests": true,
      "log_responses": true
    },
    "admin": {
      "enabled": true,
      "level": "INFO",
      "log_requests": true,
      "log_responses": true
    },
    "api_client": {
      "enabled": true,
      "level": "DEBUG",
      "log_requests": true,
      "log_responses": true
    }
  },
  "rotation": {
    "max_bytes": 10485760,
    "backup_count": 10
  },
  "redact_patterns": [
    "apikey",
    "api_key",
    "password",
    "token",
    "secret",
    "authorization"
  ],
  "output": {
    "console": true,
    "file": true,
    "format": "json"
  }
}
```

3. **Load custom configuration:**

```python
from almaapitk.alma_logging import load_config, get_logger

# Load custom configuration
config = load_config('config/logging_config.json')

# Create logger with custom config
logger = get_logger('acquisitions', environment='SANDBOX', config=config)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_level` | string | "INFO" | Global default log level |
| `domains` | object | see below | Domain-specific settings |
| `rotation.max_bytes` | int | 10485760 | Max file size before rotation (10MB) |
| `rotation.backup_count` | int | 10 | Number of backup files to keep |
| `redact_patterns` | array | see below | Field names to redact |
| `output.console` | bool | true | Enable console output |
| `output.file` | bool | true | Enable file output |
| `output.format` | string | "json" | File format (json or text) |

### Domain Configuration

Each domain can have individual settings:

```json
{
  "domains": {
    "acquisitions": {
      "enabled": true,
      "level": "DEBUG",
      "log_requests": true,
      "log_responses": true
    }
  }
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | true | Enable logging for this domain |
| `level` | string | "INFO" | Log level for this domain |
| `log_requests` | bool | true | Log API requests |
| `log_responses` | bool | true | Log API responses |

### Environment-Specific Configuration

Create separate configs for different environments:

```bash
config/
├── logging_config.json           # Default (SANDBOX)
├── logging_config.sandbox.json   # Explicit sandbox config
└── logging_config.production.json # Production config (less verbose)
```

Production configuration example (less verbose):

```json
{
  "log_level": "WARNING",
  "domains": {
    "acquisitions": { "level": "INFO", "log_responses": false },
    "api_client": { "level": "WARNING", "log_responses": false }
  },
  "output": {
    "console": false,
    "file": true
  }
}
```

---

## Security Notes

### What Gets Redacted Automatically

The following patterns are automatically redacted from all logs:

| Pattern | Example Original | Example Logged |
|---------|------------------|----------------|
| `apikey` | `"apikey": "l7xx123abc"` | `"apikey": "***REDACTED***"` |
| `api_key` | `"api_key": "secret"` | `"api_key": "***REDACTED***"` |
| `password` | `"password": "pass123"` | `"password": "***REDACTED***"` |
| `token` | `"auth_token": "xyz"` | `"auth_token": "***REDACTED***"` |
| `secret` | `"client_secret": "abc"` | `"client_secret": "***REDACTED***"` |
| `authorization` | `"Authorization": "Bearer xyz"` | `"Authorization": "***REDACTED***"` |

### Adding Custom Redaction Patterns

Add patterns to the configuration file:

```json
{
  "redact_patterns": [
    "apikey",
    "api_key",
    "password",
    "token",
    "secret",
    "authorization",
    "ssn",
    "credit_card",
    "custom_field"
  ]
}
```

### Never Commit Logs to Git

Logs are automatically excluded via `.gitignore`:

```gitignore
# Log files
logs/
logs/**/*
*.log
```

**Always verify before committing:**

```bash
# Check that logs aren't staged
git status

# Verify logs directory is ignored
git check-ignore logs/api_requests/2025-10-23/acquisitions.log
```

### Log Review Best Practices

Before sharing logs for debugging:

1. **Review for PII**: Check for personal information in API responses
2. **Verify redaction**: Ensure API keys show `***REDACTED***`
3. **Sanitize if needed**: Remove or mask any sensitive data manually
4. **Use excerpts**: Share only relevant portions, not entire log files

### Production Security

For production environments:

```python
# Reduce logging verbosity in production
config = load_config('config/logging_config.production.json')

# Or disable console output
# config/logging_config.production.json:
# { "output": { "console": false, "file": true } }
```

---

## Troubleshooting

### Logs Not Being Created

1. Check if the `logs/` directory exists and is writable
2. Verify the domain is enabled in configuration
3. Check log level settings (DEBUG shows all, ERROR shows only errors)
4. Ensure the logger is properly initialized

```python
# Verify logger is working
logger = get_logger('acquisitions', 'SANDBOX')
logger.info("Test message")
# Check: logs/api_requests/YYYY-MM-DD/acquisitions.log
```

### Logs Too Large

1. Reduce log level (INFO instead of DEBUG)
2. Adjust rotation settings in configuration
3. Disable request/response logging for high-volume operations

```json
{
  "domains": {
    "acquisitions": {
      "level": "INFO",
      "log_responses": false
    }
  },
  "rotation": {
    "max_bytes": 5242880,
    "backup_count": 5
  }
}
```

### Performance Impact

Logging adds minimal overhead (< 5ms per operation) when properly configured:

- Use INFO level in production (DEBUG only for troubleshooting)
- Disable console output for production batch operations
- Consider disabling response logging for high-volume APIs

---

## Additional Resources

- **Module README**: `docs/alma_logging/README.md`
- **Implementation Plan**: `docs/alma_logging/LOGGING_IMPLEMENTATION_PLAN.md`
- **Example Configuration**: `config/logging_config.example.json`
- **CLAUDE.md Logging Section**: Project-wide logging requirements

---

*Last updated: 2026-03-16*
*Module version: 1.0.0*
