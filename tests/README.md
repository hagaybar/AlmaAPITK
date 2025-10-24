# AlmaAPITK Test Suite

**Last Updated**: 2025-10-24

## Test Organization

This directory contains all tests and test-related files for the AlmaAPITK project, organized by type and purpose:

### Directory Structure

- **unit/** - Fast, isolated unit tests (no API calls)
  - `domains/` - Domain class tests (Acquisitions, Admin, Users)
  - `acquisition/` - Acquisition-specific function tests
  - `bibs/` - Bibliographic record function tests
  - `utils/` - Utility function tests

- **integration/** - API integration tests (requires Alma connection)
  - `client/` - API client tests
  - `invoices/` - Invoice creation, payment, and status tests
  - `pols/` - Purchase Order Line (POL) tests
  - `items/` - Item receiving and management tests

- **case_studies/** - POL-specific workflow documentation and tests
  - `POL-12345/` - Rialto complete flow case study
  - `POL-12346/` - Rialto flow variation
  - `POL-12347/` - Receive and keep in department workflow
  - `POL-12352/` - Invoice creation and payment workflow (includes duplicate payment incident)

- **logging/** - Logging infrastructure tests
  - Various logging configuration and output tests

- **meta/** - Tests about the project structure itself
  - Dependency analysis and reorganization validation tests

## Running Tests

### Unit Tests (No API Calls Required)

```bash
# Run all unit tests
pytest tests/unit/

# Run specific domain tests
pytest tests/unit/domains/test_acquisitions.py
pytest tests/unit/domains/test_admin.py
pytest tests/unit/domains/test_users.py

# Run utility tests
pytest tests/unit/utils/
```

### Integration Tests (Requires API Keys)

**IMPORTANT**: Integration tests make actual API calls to Alma. Always use SANDBOX environment unless explicitly testing production.

```bash
# Set environment variable
export ALMA_SB_API_KEY="your-sandbox-api-key"

# Run invoice tests
python3 tests/integration/invoices/test_invoice_operations.py <invoice_id>
python3 tests/integration/invoices/test_pay_invoice.py <invoice_id>

# Run POL tests
python3 tests/integration/pols/test_pol_verification.py <pol_id>

# Run item tests
python3 tests/integration/items/test_receive_item.py <pol_id> <item_id>
```

### Case Studies

Case studies are complete workflow tests with detailed documentation. Each case study directory contains a README with specific instructions.

```bash
# Example: Run POL-12352 complete workflow
python3 tests/case_studies/POL-12352/complete_invoice_workflow_POL12352.py

# See individual case study READMEs for details:
# - tests/case_studies/POL-12345/README.md
# - tests/case_studies/POL-12346/README.md
# - tests/case_studies/POL-12347/README.md
# - tests/case_studies/POL-12352/README.md
```

## Test Development Guidelines

### Unit Tests
- No API calls (mock external dependencies)
- Fast execution (< 1 second per test)
- Test single functions or classes in isolation
- Use pytest for assertion and organization

### Integration Tests
- Test actual API interactions
- Always use SANDBOX environment by default
- Include clear error messages and logging
- Document expected outcomes and API behavior

### Case Studies
- Document complete workflows from start to finish
- Include README explaining purpose and findings
- Capture API responses and state transitions
- Serve as executable documentation

## Environment Configuration

### Required Environment Variables

```bash
# Sandbox (for testing)
export ALMA_SB_API_KEY="your-sandbox-api-key"

# Production (use with extreme caution)
export ALMA_PROD_API_KEY="your-production-api-key"
```

### Safety Guidelines

1. **Always use SANDBOX first** - Never test new code in production
2. **Verify data before operations** - Check for existing records to avoid duplicates
3. **Follow documented workflows** - Especially for invoice and POL operations
4. **Read case study documentation** - Learn from documented incidents and findings

## Important Case Study: Duplicate Payment Prevention

The POL-12352 case study documents a critical duplicate payment incident and the protective measures implemented. **Required reading** for anyone working with invoice operations:

- **Location**: `tests/case_studies/POL-12352/README.md`
- **Incident Report**: `INCIDENT_REPORT_DUPLICATE_PAYMENT_POL12352.md` (project root)
- **Key Lessons**:
  1. Always check for existing invoices before creating new ones
  2. Never skip the invoice approval/processing step
  3. Fix existing invoices on error - don't create duplicates
  4. Trust the automatic duplicate payment protection

## Contributing

When adding new tests:

1. **Choose the right category**:
   - Unit test? → `tests/unit/`
   - Integration test? → `tests/integration/`
   - Complete workflow documentation? → `tests/case_studies/`

2. **Follow naming conventions**:
   - Test files: `test_*.py`
   - Descriptive names indicating what's being tested

3. **Include documentation**:
   - Docstrings explaining test purpose
   - Comments for complex test logic
   - README for case studies

4. **Use absolute imports**:
   ```python
   from src.domains.acquisition import Acquisition
   from src.client.AlmaAPIClient import AlmaAPIClient
   ```

## Maintenance

- **Review case studies periodically** - Update with new findings
- **Archive old test data** - Keep test results in `archive/` subdirectories
- **Update documentation** - Keep READMEs current with code changes
- **Clean up obsolete tests** - Remove tests that no longer provide value

## Questions or Issues?

See the main project documentation:
- `CLAUDE.md` - Comprehensive project guidance
- `FILE_ORGANIZATION_REPORT.md` - File organization rationale
- `TEST_REORGANIZATION_PLAN.md` - Details of test structure reorganization
