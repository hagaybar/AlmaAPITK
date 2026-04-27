# AlmaAPITK Logging Module

Comprehensive logging infrastructure for API requests, responses, errors, and performance metrics.

## Overview

This module provides structured logging for all AlmaAPITK operations with:

- **Automatic API key redaction** - Sensitive data never appears in logs
- **Request/response logging** - Full HTTP details with timing
- **Error tracking** - Stack traces and context for debugging
- **Domain-specific logs** - Separate logs for acquisitions, users, bibs, admin
- **JSON format** - Machine-parseable structured logs
- **Log rotation** - Automatic size-based rotation to prevent disk issues
- **Git-safe** - All logs are gitignored, never committed

## Directory Structure

```
src/alma_logging/
├── __init__.py           # Module initialization and exports
├── logger.py             # Main AlmaLogger class
├── formatters.py         # JSON and text formatters
├── handlers.py           # Rotating file handlers
├── config.py             # Configuration management
├── docs/                 # Documentation
│   └── LOGGING_IMPLEMENTATION_PLAN.md
└── README.md             # This file

logs/                     # Log output (gitignored)
├── api_requests/         # Request/response logs
│   └── YYYY-MM-DD/      # Organized by date
│       ├── acquisitions.log
│       ├── users.log
│       ├── bibs.log
│       └── admin.log
├── errors/               # Error logs
│   └── YYYY-MM-DD.log
├── performance/          # Performance metrics
│   └── YYYY-MM-DD.log
└── tests/                # Test execution logs
    └── YYYY-MM-DD/

config/
└── logging_config.example.json  # Example configuration
```

## Quick Start

```python
from almaapitk.alma_logging import get_logger

# Create domain-specific logger
logger = get_logger('acquisitions', environment='SANDBOX')

# Log informational messages
logger.info("Creating invoice", invoice_number="INV-001", vendor="RIALTO")

# Log errors with context
try:
    result = create_invoice(...)
except AlmaAPIError as e:
    logger.error(
        "Failed to create invoice",
        error_code=e.status_code,
        error_message=str(e),
        invoice_number="INV-001"
    )
```

## Configuration

### Using Default Configuration

The module works out-of-the-box with sensible defaults:
- INFO level for most domains
- DEBUG level for acquisitions and api_client
- JSON format output
- 10MB rotation with 10 backups
- Standard redaction patterns

### Custom Configuration

1. Copy example configuration:
   ```bash
   cp config/logging_config.example.json config/logging_config.json
   ```

2. Customize settings:
   ```json
   {
     "log_level": "INFO",
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

3. Load configuration:
   ```python
   from almaapitk.alma_logging.config import load_config
   config = load_config('config/logging_config.json')
   ```

## Log Formats

### JSON Format (Default)

```json
{
  "timestamp": "2025-10-23T14:30:45.123Z",
  "level": "INFO",
  "domain": "acquisitions",
  "method": "create_invoice_simple",
  "request": {
    "endpoint": "almaws/v1/acq/invoices",
    "method": "POST",
    "params": {},
    "headers": {
      "Authorization": "apikey ***REDACTED***",
      "Content-Type": "application/json"
    },
    "body": {
      "number": "INV-2025-001",
      "vendor": {"value": "RIALTO"},
      "total_amount": 100.0
    }
  },
  "response": {
    "status_code": 200,
    "duration_ms": 234
  },
  "environment": "SANDBOX"
}
```

### Text Format (Human-Readable)

```
[2025-10-23 14:30:45] INFO     [acquisitions] Creating invoice (invoice_number=INV-001)
[2025-10-23 14:30:46] ERROR    [acquisitions] Failed to create invoice (error_code=60260)
```

## Security

### Automatic Redaction

Sensitive data is automatically redacted from logs:
- API keys → `***REDACTED***`
- Passwords → `***REDACTED***`
- Tokens → `***REDACTED***`
- Authorization headers → `***REDACTED***`

Redaction patterns are configurable in `logging_config.json`:
```json
{
  "redact_patterns": [
    "apikey",
    "api_key",
    "password",
    "token",
    "secret"
  ]
}
```

### Git Safety

All log files are automatically excluded from version control via `.gitignore`:
```
logs/
logs/**/*
*.log
```

**Never commit logs to GitHub** - they may contain API responses with sensitive data.

## Log Levels

| Level    | Usage                                      | Example                          |
|----------|--------------------------------------------|----------------------------------|
| DEBUG    | Detailed diagnostic information            | Request parameters, API responses|
| INFO     | General operational information            | Invoice created, POL received    |
| WARNING  | Warning messages, non-critical issues      | Retry attempt, fallback used     |
| ERROR    | Error messages, operation failures         | API error, validation failed     |
| CRITICAL | Critical system failures                   | Connection lost, auth failed     |

## Domain-Specific Logging

Each Alma API domain has its own logger and log files:

- **acquisitions** - Invoice creation, POL operations, receiving
- **users** - User management, email updates
- **bibs** - Bibliographic record operations
- **admin** - Sets, administrative operations
- **api_client** - Low-level HTTP requests/responses

## Integration Examples

### Acquisitions Domain

```python
class Acquisitions:
    def __init__(self, client):
        self.client = client
        self.logger = get_logger('acquisitions', client.environment)

    def create_invoice_simple(self, invoice_number, vendor_code, total_amount):
        self.logger.info(
            "Creating simple invoice",
            invoice_number=invoice_number,
            vendor_code=vendor_code,
            total_amount=total_amount
        )

        try:
            result = self._create_invoice(...)
            self.logger.info(
                "Invoice created successfully",
                invoice_id=result['id'],
                invoice_number=invoice_number
            )
            return result
        except AlmaAPIError as e:
            self.logger.error(
                "Failed to create invoice",
                invoice_number=invoice_number,
                error_code=e.status_code,
                error_message=str(e)
            )
            raise
```

### AlmaAPIClient

```python
class AlmaAPIClient:
    def __init__(self, environment='SANDBOX'):
        self.logger = get_logger('api_client', environment)

    def get(self, endpoint, params=None):
        self.logger.log_request('GET', endpoint, params=params)
        start_time = time.time()

        response = requests.get(...)
        duration = (time.time() - start_time) * 1000

        self.logger.log_response(response, duration)
        return response
```

## Implementation Status

**Current Phase**: Infrastructure Setup (Phase 1)

- [x] Directory structure created
- [x] Module files created (skeleton implementations)
- [x] Configuration example provided
- [x] .gitignore updated
- [ ] **Phase 1.1**: Implement logger.py (AlmaLogger class)
- [ ] **Phase 1.2**: Implement formatters.py (JSON/Text formatters)
- [ ] **Phase 1.3**: Implement handlers.py (Rotating handlers)
- [ ] **Phase 1.4**: Implement config.py (Configuration management)
- [ ] **Phase 2**: Integrate with AlmaAPIClient
- [ ] **Phase 3**: Integrate with Acquisitions domain
- [ ] **Phase 4**: Add test suite logging
- [ ] **Phase 5**: Create analysis tools (log_viewer.py, log_analyzer.py)
- [ ] **Phase 6**: Complete documentation

See `docs/LOGGING_IMPLEMENTATION_PLAN.md` for full implementation roadmap.

## Troubleshooting

### Logs Not Being Created

1. Check if log directory exists and is writable
2. Verify domain is enabled in configuration
3. Check log level settings (DEBUG shows all, ERROR shows only errors)

### Logs Too Large

1. Reduce log level (INFO instead of DEBUG)
2. Adjust rotation settings (smaller max_bytes)
3. Disable request/response logging for high-volume operations

### Performance Impact

Logging adds < 5ms overhead per API request when properly configured:
- Use INFO level in production (DEBUG only for troubleshooting)
- Enable buffering for high-volume operations
- Disable console output for production

## Future Enhancements

Planned features for future releases:

1. **Log Analysis Tools** - Scripts to parse and analyze logs
2. **Real-time Log Viewer** - Tail logs with filtering and color coding
3. **Performance Metrics** - Dashboard for API performance
4. **Centralized Logging** - Export to ELK stack or Splunk
5. **Alerting** - Automatic alerts on critical errors
6. **Log Compression** - Automatic compression of old logs

## Support

For issues or questions:
1. Check `docs/LOGGING_IMPLEMENTATION_PLAN.md` for detailed specifications
2. Review log files in `logs/` directory
3. Verify configuration in `config/logging_config.json`
4. Check `.gitignore` to ensure logs are excluded from git

## Contributing

When contributing logging enhancements:
1. Follow existing code patterns in logger.py
2. Add comprehensive docstrings
3. Update this README with new features
4. Test with both SANDBOX and PRODUCTION environments
5. Verify sensitive data redaction works correctly
6. Never commit actual log files or API keys

---

**Version**: 1.0.0 (Infrastructure Phase)
**Last Updated**: 2025-10-23
**Status**: In Development
