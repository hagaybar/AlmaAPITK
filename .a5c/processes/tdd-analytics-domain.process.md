# TDD Analytics Domain Process

## Overview
Create a new Analytics domain class for almaapitk using Test-Driven Development methodology.

## Goal
Add `Analytics` class to `src/almaapitk/domains/analytics.py` with methods for fetching data from Alma Analytics reports.

## Methods to Implement

### 1. `get_report_headers(report_path)`
- **Purpose**: Get column headers/schema for an Analytics report
- **Endpoint**: GET `/almaws/v1/analytics/reports`
- **Returns**: Dict mapping column names to headings

### 2. `fetch_report_rows(report_path, limit, max_rows)`
- **Purpose**: Fetch rows from Analytics report with pagination
- **Endpoint**: GET `/almaws/v1/analytics/reports`
- **Returns**: Generator yielding row dicts
- **Features**: ResumptionToken pagination, max_rows limit

## TDD Phases

### Phase 1: RED (Write Tests First)
1. Create unit tests with mocked responses
2. Create integration tests for real API
3. Run tests - expect failures

### Phase 2: GREEN (Implement)
1. Create Analytics class following existing domain patterns
2. Implement get_report_headers with XML parsing
3. Implement fetch_report_rows with pagination
4. Run tests - should pass

### Phase 3: REFACTOR
1. Export Analytics from `__init__.py`
2. Code quality review
3. Final verification with smoke test

## Files Created/Modified
- `src/almaapitk/domains/analytics.py` - New domain class
- `tests/unit/domains/test_analytics.py` - Unit tests
- `tests/integration/domains/test_analytics.py` - Integration tests
- `src/almaapitk/__init__.py` - Add Analytics export

## Reference
Based on implementation in:
`/home/hagaybar/projects/Fetch_Alma_Analytics_Reports/fetch_reports_from_alma_analytics.py`
