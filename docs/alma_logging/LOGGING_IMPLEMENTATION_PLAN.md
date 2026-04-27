# Logging Implementation Plan

**Created**: 2025-10-23
**Last Updated**: 2025-10-23
**Status**: Phase 1 Complete (Infrastructure Setup)
**Priority**: High
**Branch**: `feature/invoice-creation-helpers`
**Commit**: c3f2f33 (2025-10-23)

---

## Overview

Implement comprehensive logging system for AlmaAPITK to capture all API requests, responses, parameters, and errors for debugging and production troubleshooting.

### Key Requirements

1. **Request/Response Logging**: Capture full HTTP requests and responses
2. **Parameter Logging**: Log all parameters sent to API methods
3. **Error Logging**: Detailed error information with stack traces
4. **Security**: Ensure logs are NOT committed to GitHub (contain API keys, sensitive data)
5. **Performance**: Minimal performance impact on API calls
6. **Flexibility**: Configurable log levels and output locations
7. **Rotation**: Automatic log rotation to prevent disk space issues

---

## Architecture Design

### Log Structure

```
AlmaAPITK/
├── logs/                          # Log directory (gitignored)
│   ├── api_requests/              # Request/response logs
│   │   ├── YYYY-MM-DD/           # Organized by date
│   │   │   ├── acquisitions.log
│   │   │   ├── users.log
│   │   │   └── bibs.log
│   ├── errors/                    # Error logs
│   │   └── YYYY-MM-DD.log
│   ├── performance/               # Performance metrics
│   │   └── YYYY-MM-DD.log
│   └── tests/                     # Test execution logs
│       └── YYYY-MM-DD/
├── src/
│   ├── logging/                   # NEW: Logging infrastructure
│   │   ├── __init__.py
│   │   ├── logger.py              # Main logger class
│   │   ├── formatters.py          # Log formatters
│   │   ├── handlers.py            # File handlers, rotation
│   │   └── config.py              # Logging configuration
│   └── domains/
│       └── acquisition.py         # Enhanced with logging
└── .gitignore                     # Updated to exclude logs/
```

### Log Levels

1. **DEBUG**: Detailed information for diagnosing problems
2. **INFO**: General informational messages (API calls, operations)
3. **WARNING**: Warning messages (retries, fallbacks)
4. **ERROR**: Error messages (API failures, validation errors)
5. **CRITICAL**: Critical errors (connection failures, system issues)

### Log Format

**Log files are plain text files** where each line contains a single JSON object (JSON Lines / JSONL format).

**File Output Format** (`logs/api_requests/2025-10-23/acquisitions.log`):
```jsonl
{"timestamp":"2025-10-23T14:30:45.123Z","level":"INFO","domain":"acquisitions","method":"create_invoice_simple","request":{"endpoint":"almaws/v1/acq/invoices","method":"POST","params":{},"headers":{"Authorization":"apikey ***REDACTED***","Content-Type":"application/json"},"body":{"number":"INV-2025-001","vendor":{"value":"RIALTO"},"total_amount":100.0}},"response":{"status_code":200,"headers":{},"body":{}},"duration_ms":234,"environment":"SANDBOX"}
{"timestamp":"2025-10-23T14:30:46.345Z","level":"INFO","domain":"acquisitions","message":"Invoice created successfully","context":{"invoice_id":"35925532970004146"}}
```

**Advantages of JSON Lines**:
- Machine-parseable (each line is valid JSON)
- Streamable (process line-by-line without loading entire file)
- Appendable (add new entries without parsing existing file)
- Grep-friendly (can search for text patterns)
- Tool-compatible (works with jq, logstash, etc.)

**Example Parsing**:
```python
import json
with open('logs/api_requests/2025-10-23/acquisitions.log') as f:
    for line in f:
        entry = json.loads(line)
        if entry['level'] == 'ERROR':
            print(f"Error: {entry['message']}")
```

**Request Log Entry Structure** (shown pretty-printed for documentation):
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
    "headers": {...},
    "body": {...}
  },
  "duration_ms": 234,
  "environment": "SANDBOX"
}
```
(Note: Actual file output is compact JSON, one entry per line)

**Error Log Entry**:
```json
{
  "timestamp": "2025-10-23T14:30:45.123Z",
  "level": "ERROR",
  "domain": "acquisitions",
  "method": "mark_invoice_paid",
  "error": {
    "type": "AlmaAPIError",
    "code": "60260",
    "message": "License Term Type valid values {0} found {1}.",
    "tracking_id": "E01-2310083458-ZJXK6-AWAE2031933601"
  },
  "request": {...},
  "stack_trace": "..."
}
```

---

## Phase 1: Infrastructure Setup ✅ COMPLETE

**Status**: ✅ Complete (2025-10-23)
**Commit**: c3f2f33

### Milestone 1.1: Create Logging Module ✅

**Tasks**:
- [x] Create `src/alma_logging/` directory structure
- [x] Implement `logger.py` with AlmaLogger class (skeleton with comprehensive TODOs)
- [x] Implement `formatters.py` with JSON and text formatters (skeleton)
- [x] Implement `handlers.py` with rotating file handlers (skeleton)
- [x] Implement `config.py` with configuration management (skeleton with default config)
- [x] Create `logs/` directory structure
- [x] Update `.gitignore` to exclude logs/ (already present, verified)

**Deliverables**:
- ✅ `src/alma_logging/__init__.py` - Module exports and documentation
- ✅ `src/alma_logging/logger.py` - AlmaLogger class with placeholder methods
- ✅ `src/alma_logging/formatters.py` - JSONFormatter, TextFormatter, redact_sensitive_data()
- ✅ `src/alma_logging/handlers.py` - AlmaRotatingFileHandler, DateOrganizedFileHandler
- ✅ `src/alma_logging/config.py` - LoggingConfig with DEFAULT_CONFIG

**Acceptance Criteria**:
- ✅ Logger can be instantiated for different domains (skeleton ready)
- ✅ Supports multiple log levels (methods defined)
- ✅ Can write to multiple log files simultaneously (handler infrastructure ready)
- ✅ API keys are automatically redacted from logs (redact_sensitive_data() implemented)

**Note**: Files created with skeleton implementations containing comprehensive docstrings and TODO markers for Phase 1.1 actual implementation.

### Milestone 1.2: Update .gitignore ✅

**Tasks**:
- [x] Add `logs/` directory to .gitignore (already present)
- [x] Add `*.log` pattern to .gitignore (already present)
- [x] Verify existing logs are not tracked (verified)
- [x] Add documentation comment in .gitignore (already present)

**Deliverables**:
- ✅ `.gitignore` already contains logs/ and *.log patterns (lines 58-67)

**Acceptance Criteria**:
- ✅ `git status` does not show logs/ directory
- ✅ Existing log files are not tracked

### Milestone 1.3: Logging Configuration ✅

**Tasks**:
- [x] Create `config/logging_config.example.json` template
- [x] Support environment-specific settings (SANDBOX/PRODUCTION)
- [x] Support configurable log levels per domain
- [x] Support log rotation settings (max size, backup count)

**Example Configuration**:
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
      "level": "INFO"
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
    "token"
  ]
}
```

**Deliverables**:
- ✅ `config/logging_config.example.json` - Complete example with all domains
- ✅ Default configuration in LoggingConfig.DEFAULT_CONFIG

**Acceptance Criteria**:
- ✅ Configuration example includes all required settings
- ✅ Default configuration available when no file provided
- ✅ Domain-specific settings supported

### Additional Deliverables (Phase 1)

**Documentation**:
- [x] Create `src/alma_logging/README.md` - Complete usage guide
- [x] Create `src/alma_logging/docs/` directory
- [x] Move LOGGING_IMPLEMENTATION_PLAN.md to src/alma_logging/docs/
- [x] Update CLAUDE.md with logging requirements section

**Deliverables**:
- ✅ `src/alma_logging/README.md` - 400+ lines comprehensive guide
  - Quick start examples
  - Configuration instructions
  - Log formats (JSON/Text)
  - Security considerations
  - Troubleshooting guide
  - Implementation status
- ✅ `CLAUDE.md` updated with "Logging Requirements" section (lines 222-349)
  - Usage examples for domain classes and test scripts
  - Log levels guide
  - What to log vs. what not to log
  - Security notes

**Acceptance Criteria**:
- ✅ README provides complete usage documentation
- ✅ CLAUDE.md instructs future sessions on logging requirements
- ✅ All examples are clear and actionable

---

## Phase 1.1-1.3: Actual Implementation (NEXT STEPS)

**Status**: 🔄 Pending
**Priority**: High

These milestones involve implementing the actual functionality in the skeleton files created in Phase 1.

### Milestone 1.1: Implement AlmaLogger Class

**Tasks**:
- [ ] Implement logger initialization with handlers
- [ ] Implement info(), debug(), warning(), error(), critical() methods
- [ ] Implement log_request() with API key redaction
- [ ] Implement log_response() with timing
- [ ] Implement log_error() with stack traces
- [ ] Add logger caching in get_logger()
- [ ] Set up file and console handlers
- [ ] Connect formatters to handlers

**Files to Update**:
- `src/alma_logging/logger.py` (replace TODO markers with implementations)

### Milestone 1.2: Implement Formatters

**Tasks**:
- [ ] Implement JSONFormatter.format() with field extraction
- [ ] Implement TextFormatter.format() with color coding
- [ ] Implement redact_sensitive_data() recursive logic
- [ ] Add timestamp formatting
- [ ] Test redaction with various data structures

**Files to Update**:
- `src/alma_logging/formatters.py` (complete the format() methods)

### Milestone 1.3: Implement Handlers

**Tasks**:
- [ ] Complete DateOrganizedFileHandler.emit()
- [ ] Implement date-based file switching
- [ ] Test log rotation with size limits
- [ ] Implement create_log_directory_structure()
- [ ] Test concurrent logging from multiple threads

**Files to Update**:
- `src/alma_logging/handlers.py` (complete handler implementations)

### Milestone 1.4: Implement Configuration

**Tasks**:
- [ ] Implement configuration file loading with validation
- [ ] Add error handling for invalid JSON
- [ ] Merge loaded config with defaults
- [ ] Test configuration loading
- [ ] Document configuration options

**Files to Update**:
- `src/alma_logging/config.py` (complete _load_from_file() method)

---

## Phase 2: AlmaAPIClient Integration

**Status**: 🔜 Not Started
**Prerequisites**: Phase 1.1-1.3 complete

### Milestone 2.1: Enhance AlmaAPIClient

**Tasks**:
- [ ] Add logger instance to AlmaAPIClient
- [ ] Log all HTTP requests (method, URL, params, headers)
- [ ] Log all HTTP responses (status, headers, body)
- [ ] Redact API keys from logged headers
- [ ] Add request/response timing
- [ ] Log errors with full context

**Location**: `src/client/AlmaAPIClient.py`

**Changes**:
```python
class AlmaAPIClient:
    def __init__(self, environment='SANDBOX'):
        # ... existing code ...
        self.logger = get_logger('api_client', environment)

    def get(self, endpoint, params=None):
        self.logger.log_request('GET', endpoint, params=params)
        start_time = time.time()

        try:
            response = requests.get(...)
            duration = (time.time() - start_time) * 1000

            self.logger.log_response(response, duration)
            return self._handle_response(response)
        except Exception as e:
            self.logger.log_error(e, endpoint=endpoint, params=params)
            raise
```

**Deliverables**:
- Enhanced `AlmaAPIClient.get()`
- Enhanced `AlmaAPIClient.post()`
- Enhanced `AlmaAPIClient.put()`
- Enhanced `AlmaAPIClient.delete()`

---

## Phase 3: Acquisitions Domain Logging

### Milestone 3.1: Add Domain-Level Logging

**Tasks**:
- [ ] Add logger instance to Acquisitions class
- [ ] Log method entry with parameters
- [ ] Log method exit with results
- [ ] Log intermediate steps for complex operations
- [ ] Log validation errors with context

**Location**: `src/domains/acquisition.py`

**Example Implementation**:
```python
class Acquisitions:
    def __init__(self, client):
        self.client = client
        self.logger = get_logger('acquisitions', client.environment)

    def create_invoice_simple(self, invoice_number, invoice_date, vendor_code, total_amount, **kwargs):
        self.logger.info(
            "Creating simple invoice",
            invoice_number=invoice_number,
            vendor_code=vendor_code,
            total_amount=total_amount
        )

        try:
            # ... existing logic ...

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

**Methods to Enhance** (Priority Order):
1. [ ] `create_invoice()` - Core method
2. [ ] `create_invoice_simple()` - Helper method
3. [ ] `create_invoice_line()` - Core method
4. [ ] `create_invoice_line_simple()` - Helper method
5. [ ] `create_invoice_with_lines()` - Workflow method
6. [ ] `approve_invoice()` - Process method
7. [ ] `mark_invoice_paid()` - Payment method
8. [ ] `get_invoice()` - Retrieval method
9. [ ] `get_invoice_lines()` - Retrieval method
10. [ ] `check_pol_invoiced()` - Validation method

**Deliverables**:
- Enhanced Acquisitions class with comprehensive logging

---

## Phase 4: Test Suite Integration

### Milestone 4.1: Add Test Logging

**Tasks**:
- [ ] Create test logger that writes to `logs/tests/`
- [ ] Log test execution start/end
- [ ] Log test parameters and configuration
- [ ] Log test results (pass/fail)
- [ ] Capture and log assertion failures

**Location**: `src/tests/test_invoice_creation.py`

**Example**:
```python
def main():
    test_logger = get_logger('test_invoice_creation', environment)

    test_logger.info(
        "Starting test suite",
        environment=environment,
        mode='LIVE' if not dry_run else 'DRY_RUN',
        tests=args.test
    )

    # ... run tests ...

    test_logger.info(
        "Test suite completed",
        total=len(results),
        passed=passed_count,
        failed=failed_count
    )
```

**Deliverables**:
- Enhanced test scripts with logging
- Test execution logs in `logs/tests/`

---

## Phase 5: Utilities and Tools

### Milestone 5.1: Log Analysis Tools

**Tasks**:
- [ ] Create `src/utils/log_analyzer.py` script
- [ ] Parse and analyze request logs
- [ ] Extract error patterns
- [ ] Generate summary reports
- [ ] Filter logs by date/domain/error type

**Example Usage**:
```bash
# Show all errors from today
python src/utils/log_analyzer.py --date today --level ERROR

# Show all requests to acquisitions API
python src/utils/log_analyzer.py --domain acquisitions --date 2025-10-23

# Generate summary report
python src/utils/log_analyzer.py --summary --date 2025-10-23
```

**Deliverables**:
- `src/utils/log_analyzer.py`
- Documentation for log analysis

### Milestone 5.2: Log Viewer

**Tasks**:
- [ ] Create `src/utils/log_viewer.py` script
- [ ] Pretty-print JSON logs
- [ ] Tail logs in real-time
- [ ] Filter and search capabilities
- [ ] Color-coded output by log level

**Example Usage**:
```bash
# Tail acquisitions log
python src/utils/log_viewer.py --tail --domain acquisitions

# View specific log file
python src/utils/log_viewer.py --file logs/api_requests/2025-10-23/acquisitions.log

# Search for invoice ID
python src/utils/log_viewer.py --search "35925645920004146"
```

**Deliverables**:
- `src/utils/log_viewer.py`
- Real-time log viewing capability

---

## Phase 6: Documentation

### Milestone 6.1: Documentation

**Tasks**:
- [ ] Update CLAUDE.md with logging information
- [ ] Create logging usage guide
- [ ] Document log formats and structure
- [ ] Add troubleshooting guide
- [ ] Document log analysis tools

**Topics to Cover**:
1. How to enable/disable logging
2. How to configure log levels
3. Where logs are stored
4. How to analyze logs
5. Security considerations
6. Log retention policies

**Deliverables**:
- Updated `CLAUDE.md`
- New `docs/LOGGING_GUIDE.md`

---

## Phase 7: Other Domains (Future)

### Milestone 7.1: Users Domain
- [ ] Add logging to Users domain
- [ ] Same pattern as Acquisitions

### Milestone 7.2: Bibs Domain
- [ ] Add logging to Bibs domain

### Milestone 7.3: Admin Domain
- [ ] Add logging to Admin domain

---

## Security Considerations

### What Gets Logged

**✅ DO LOG**:
- Request endpoints and methods
- Request parameters (except sensitive data)
- Response status codes
- Response body (redacted)
- Timestamps and durations
- Error messages and codes

**❌ DO NOT LOG (Must Redact)**:
- API keys (replace with `***REDACTED***`)
- Passwords
- Authentication tokens
- User personal information (if in responses)
- Credit card numbers
- Social security numbers

### Redaction Implementation

```python
def redact_sensitive_data(data, patterns=['apikey', 'password', 'token']):
    """Recursively redact sensitive data from dict/list."""
    if isinstance(data, dict):
        return {
            k: '***REDACTED***' if any(p in k.lower() for p in patterns)
            else redact_sensitive_data(v, patterns)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_sensitive_data(item, patterns) for item in data]
    else:
        return data
```

---

## Performance Considerations

### Impact Minimization

1. **Async Logging**: Use background threads for file writes
2. **Buffering**: Buffer log entries before writing
3. **Conditional Logging**: Check log level before expensive operations
4. **Rotation**: Use log rotation to prevent large files

### Benchmarks (Target)

- **Request Overhead**: < 5ms per API call
- **Log File Size**: < 50MB per domain per day (with rotation)
- **Memory Usage**: < 10MB for logging infrastructure

---

## Testing Strategy

### Unit Tests

- [ ] Test logger initialization
- [ ] Test log formatting (JSON, text)
- [ ] Test log rotation
- [ ] Test sensitive data redaction
- [ ] Test configuration loading

### Integration Tests

- [ ] Test logging in AlmaAPIClient
- [ ] Test logging in Acquisitions domain
- [ ] Test log file creation and writing
- [ ] Test concurrent logging from multiple threads

### Manual Tests

- [ ] Verify logs are created in correct locations
- [ ] Verify logs are not committed to git
- [ ] Verify sensitive data is redacted
- [ ] Verify log rotation works
- [ ] Verify log analysis tools work

---

## Rollout Plan

### Phase 1: Infrastructure Setup (Week 1) ✅ COMPLETE
1. ✅ Create branch `feature/invoice-creation-helpers` (logging added to this branch)
2. ✅ Implement infrastructure skeleton (Milestones 1.1-1.3)
3. ✅ Verify .gitignore (already configured)
4. ✅ Create comprehensive documentation
5. 🔄 Unit tests (pending - Phase 1.1-1.3 implementation)

**Completed**: 2025-10-23
**Commit**: c3f2f33

### Phase 1.1-1.3: Actual Implementation (Next) 🔄 PENDING
1. Implement AlmaLogger class functionality
2. Implement formatters with actual formatting logic
3. Implement handlers with rotation
4. Unit tests for logging components

### Phase 2: Integration (Future)
1. Integrate with AlmaAPIClient (Milestone 2.1)
2. Integrate with Acquisitions (Milestone 3.1)
3. Integration tests
4. Manual verification

### Phase 3: Testing (Future)
1. Add test suite logging (Milestone 4.1)
2. Create analysis tools (Milestone 5.1-5.2)
3. End-to-end testing

### Phase 4: Documentation & Merge (Future)
1. Complete documentation (Milestone 6.1)
2. Code review
3. Merge to main
4. Monitor in production

---

## Success Criteria

**Phase 1 (Infrastructure)** ✅:
- [x] Directory structure created
- [x] Skeleton implementations with comprehensive docstrings
- [x] Logs are organized by domain and date (structure ready)
- [x] Logs are NOT committed to GitHub (.gitignore verified)
- [x] Documentation is complete (README + CLAUDE.md + implementation plan)

**Phase 1.1-1.3 (Implementation)** 🔄:
- [ ] Logger can instantiate and write logs
- [ ] Sensitive data is automatically redacted (function exists, needs integration)
- [ ] Log rotation prevents disk space issues
- [ ] All unit tests pass

**Phase 2+ (Integration)** 🔜:
- [ ] All API requests/responses are logged
- [ ] Performance overhead < 5ms per request
- [ ] Log analysis tools are functional
- [ ] Integration tests pass

---

## Future Enhancements

1. **Centralized Logging**: Send logs to external service (ELK, Splunk)
2. **Real-time Monitoring**: Dashboard for live log viewing
3. **Alerting**: Automatic alerts on critical errors
4. **Metrics**: API performance metrics and dashboards
5. **Audit Trail**: Compliance and audit logging
6. **Log Compression**: Compress old logs automatically

---

## Notes

- Start with Acquisitions domain as proof of concept
- Ensure logging is opt-in (can be disabled via config)
- Keep performance impact minimal
- Make logs human-readable and machine-parseable
- Prioritize security (redaction) over detail

### Implementation Notes (2025-10-23)

**Phase 1 Complete**:
- ✅ All infrastructure files created with skeleton implementations
- ✅ Comprehensive documentation added (README, CLAUDE.md updates)
- ✅ Configuration example provided
- ✅ .gitignore already properly configured

**Key Decisions**:
- Skeleton implementations include comprehensive TODOs for Phase 1.1-1.3
- All files have detailed docstrings explaining intended functionality
- Default configuration provides sensible defaults (DEBUG for acquisitions, INFO for others)
- Security prioritized: redact_sensitive_data() function implemented and ready
- Branch: Using existing `feature/invoice-creation-helpers` instead of new branch

**Next Steps**:
- Implement actual logging functionality (Phase 1.1-1.3)
- Then integrate with AlmaAPIClient (Phase 2)
- Then integrate with Acquisitions domain (Phase 3)

---

**Created**: 2025-10-23
**Last Updated**: 2025-10-23
**Phase 1 Completed**: 2025-10-23 (Commit c3f2f33)
**Next Review**: After Phase 1.1-1.3 implementation
