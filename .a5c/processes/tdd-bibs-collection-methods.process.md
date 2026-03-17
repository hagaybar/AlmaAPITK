# TDD Process: Add Collection Methods to bibs.py

## Overview

This process implements three collection management methods in the `BibliographicRecords` domain class using Test-Driven Development (TDD).

## Methods to Implement

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_collection_members(collection_id, limit, offset)` | GET /bibs/collections/{pid}/bibs | List all bibs in a collection |
| `add_to_collection(collection_id, mms_id)` | POST /bibs/collections/{pid}/bibs | Add a bib to a collection |
| `remove_from_collection(collection_id, mms_id)` | DELETE /bibs/collections/{pid}/bibs/{mms_id} | Remove a bib from a collection |

## TDD Phases

### Phase 1: RED (Write Tests First)
1. Create integration test file at `tests/integration/domains/test_bibs_collections.py`
2. Write tests for all three methods
3. Include error case tests
4. Run tests - they should FAIL (no implementation yet)

### Phase 2: GREEN (Implement to Pass Tests)
1. Add methods to `src/almaapitk/domains/bibs.py`
2. Follow existing patterns in the class
3. Run tests - they should PASS

### Phase 3: REFACTOR (Quality Check)
1. Review code quality and consistency
2. Ensure proper docstrings and type hints
3. Verify smoke import still works
4. Optional: Run integration tests against Alma Sandbox

## Breakpoint

One breakpoint for optional Sandbox collection ID for live API testing.

## Expected Output

- Updated `bibs.py` with three new methods
- New test file `test_bibs_collections.py`
- All tests passing
- Smoke import passing
