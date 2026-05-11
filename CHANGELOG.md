# Changelog

All notable changes to `almaapitk` are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/).

## [Unreleased]

## [0.4.0] — 2026-05-10

### Added

- `AlmaAPIClient` now uses a persistent `requests.Session` for all HTTP calls
  (issue #3) and routes every verb through a single `_request()` method
  (issue #4), giving every later feature one chokepoint for retry, timeout,
  and rate-limit policy.
- HTTP retry with exponential backoff for transient failures
  (`429`, `500`, `502`, `503`, `504`) (issue #5).
- Configurable per-call timeout (default lowered from 300s to 60s) and
  a region map covering the published Alma endpoints (NA, EU, APAC,
  China) (issues #6, #7).
- Mapped Alma error codes to `AlmaAPIError` subclasses
  (`AlmaAuthenticationError`, `AlmaRateLimitError`, `AlmaServerError`,
  `AlmaResourceNotFoundError`, `AlmaDuplicateInvoiceError`,
  `AlmaInvalidPolModeError`) and surfaced `tracking_id` / `error_code`
  on raised exceptions (issues #9, #10).
- `client.iter_paged(endpoint, ...)` generator that walks paged Alma
  endpoints with on-demand fetching, `max_records` cap, and centralized
  `limit` / `offset` / `total_record_count` bookkeeping (issue #11).
  `Acquisitions.list_invoices` and `Acquisitions.search_invoices` migrated
  as proof points.
- `AlmaAPIClient` is now a context manager (`with AlmaAPIClient(...) as c:`)
  and exposes an explicit `close()` (issue #13).
- `AlmaResponse.data` caches its parsed payload across repeated access
  (issue #16).
- `Configuration` domain foundation skeleton added under
  `almaapitk.domains.configuration` (issue #22). Concrete methods land
  in sibling tickets #24–#35.
- `Admin.Sets` full CRUD + member management (issue #23).
- `Configuration` organizations and locations methods
  (issues #24, #25).
- `Configuration` code-table methods (issues #26, #27).
- `Configuration` letters and grab-bag methods
  (issues #30, #33, #35).
- `Users.list_users` / `search_users` / `get_user_personal_data`
  (PR #117).
- `Users.create_user` / `delete_user` (PR #122).
- `Users` grab-bag methods (issues #39, #44, #45).
- `Users` loans coverage (issue #40).
- `Users` requests coverage (issue #41).

### Changed

- Replaced direct `print()` calls in domain code with the project logger
  (issue #14). All operational events now flow through
  `almaapitk.alma_logging`.
- Tightened `try / except` blocks across the client to catch only the
  exceptions actually raised, not bare `Exception` (issue #16).

### Fixed

- Filtered `taskName` from custom-context log output. Python 3.12 added
  `taskName` as a built-in `LogRecord` attribute, which both formatters
  were leaking into every log line as `(taskName=None)` (issue #2).
- `Configuration.update_letter` now sends an XML body; previously
  silently broken (issue #114).

### Removed

- Dropped 7 unused dependencies, including the transitive
  CVE-2023-36464 source. Runtime dependency surface is now `requests`
  only (issue #83).
- `BibliographicRecords.search_records` removed. `q=` against
  `/bibs` was never functional, so no consumer could have a
  working dependency on it. Not considered a breaking change.
  (Commit `72b0d93`.)

## [0.3.1] — 2026-04-27

First publish of `almaapitk` to PyPI. (0.3.0 was uploaded to TestPyPI
during pre-publish verification but never released; README content
corrections caught during the TestPyPI gate required a version bump
to 0.3.1.)

### Added

- `Analytics` domain class with `get_report_headers()` and
  `fetch_report_rows()`, including built-in pagination. Alma Analytics
  is backed by a single shared database accessible only via PRODUCTION
  credentials; SANDBOX has no analytics endpoint.
- `progress_callback` hook on `Analytics.fetch_report_rows()`, invoked
  after each page so callers can display progress for long-running
  fetches.
- Generous `timeout=300` on every `requests` call in `AlmaAPIClient` to
  prevent indefinite hangs.

### Changed

- Documented `process_users_batch.max_workers` as a no-op pending a
  future concurrency feature, instead of implying parallelism.
- Moved internal `alma_logging` documentation out of the package source
  tree to `docs/alma_logging/` so the published wheel contains zero
  non-Python content.

[Unreleased]: https://github.com/hagaybar/AlmaAPITK/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.4.0
[0.3.1]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.3.1
