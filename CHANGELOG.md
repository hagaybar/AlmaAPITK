# Changelog

All notable changes to `almaapitk` are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/).

## [Unreleased]

### Added

- **`AlmaAPIClient(api_key=...)` constructor injection** (issue #143). The
  client now accepts an optional keyword-only `api_key`, mirroring the
  `OpenAI(api_key=...)` / `Anthropic(api_key=...)` pattern. An explicit key
  is used verbatim and takes precedence; when omitted the client falls back
  to the existing environment variables (`ALMA_SB_API_KEY` /
  `ALMA_PROD_API_KEY`), so all existing callers are unchanged. Enables
  injecting keys from a secrets manager, keyring, or CLI argument, and
  running two clients with different keys in one process.
- **`CredentialError`** exception, exported from the public package (issue
  #143). Raised when no API key can be resolved from either the `api_key`
  argument or the environment-variable fallback, with a message naming both
  options. Subclasses `AlmaValidationError` (and therefore `ValueError`), so
  code that previously caught the bare `ValueError` on a missing key keeps
  working.

### Changed

- **Logging defaults are now safe and quiet** (issue #142, problems #2/#3):
  - All domains default to `INFO`. Previously `acquisitions` and
    `api_client` defaulted to `DEBUG`, so a bare `get_logger()` call dumped
    request/response detail. Verbosity is now opt-in.
  - File output is **off by default** — the toolkit no longer creates a
    `logs/api_requests/<date>/<domain>.log` file under the consumer's
    working directory unprompted. Enable it with `output.file = true`.
  - The level gate moved to the shared `almapi` parent logger, so the whole
    toolkit can be quieted (or opened up) with a single call —
    `logging.getLogger("almapi").setLevel(logging.WARNING)` — instead of
    reconfiguring each `almapi.<domain>` logger by name. This resolves the
    logger-namespace fragmentation noted in 0.4.5 and completes issue #142.

### Security

- **Personal data (PII) is now redacted from all log output by default**
  (issue #142), at every level, on both the console and file handlers. User
  identifiers (`user_id`, `primary_id`, …) keep only their last three
  characters (`123456789` → `<...>789`), including ids embedded in
  `users/<id>` request URLs; names, emails, addresses and phone numbers are
  blanked entirely. Bibliographic identifiers (`mms_id`) are not personal
  and remain visible. The credential redaction shipped in 0.4.5 is unchanged.
- **Full request/response bodies are no longer logged** unless the new
  `log_bodies` configuration flag is explicitly enabled (issue #142). A
  single user lookup returns the entire patron record, so bodies were the
  largest single PII source.

  R10 regression suites for the above: `tests/unit/regressions/test_issue_142.py`,
  `tests/unit/regressions/test_issue_143.py`.

### CI

- Added a push-time CI workflow (`.github/workflows/ci.yml`) with two guards
  on every push to `main` and every PR (issues #150, #151): a wheel/sdist
  **contents check** (catches packaging regressions such as the pre-0.3.1
  empty wheel, or stray `tests/`/`docs/`/secrets leaking into a release) and
  a **bandit** scan that fails on any High-severity finding (adoption
  baseline: 0 High). Neither affects the installed package.

## [0.4.5] — 2026-05-18

### Fixed

- **Logging: `TextFormatter` no longer leaks `Authorization` header values
  to stderr** (issue #142, problem #1). The toolkit's `redact_sensitive_data()`
  helper was wired into `JSONFormatter` only — `TextFormatter` (the stderr
  console handler) rendered structured fields straight from
  `record.__dict__`, so every `api_client` DEBUG request line printed
  `headers={'Authorization': 'apikey <real_key>', ...}` in plain text.
  `TextFormatter.format()` now recursively redacts custom fields the same
  way `JSONFormatter` does, using the same default pattern set
  (`apikey`, `api_key`, `password`, `token`, `secret`, `authorization`).
  The module-level default in `redact_sensitive_data()` was also expanded
  to include `'authorization'` so direct callers of the helper get the
  same protection. R10 regression suite:
  `tests/unit/regressions/test_issue_142.py`.

  **Strongly recommended for anyone running the toolkit with DEBUG-level
  logging enabled.** This was the cause of the 2026-05-18 in-session
  leaks documented in the rotation history of the maintainer's keys.

  Note: this is the narrow patch fix for problem #1 from issue #142.
  Problems #2 (CWD `FileHandler` default) and #3 (logger namespace
  fragmentation) remain open and target 0.5.0.

### Rollback

If 0.4.5 misbehaves in your environment, three rollback paths are
available:

1. **PyPI yank** — maintainer-side, via the PyPI web UI's "Yank this
   release" button on the 0.4.5 release page. Pinned consumers continue
   to resolve 0.4.5; new installs see 0.4.4 as the latest.
2. **Explicit downgrade** — `pip install almaapitk==0.4.4` (or
   `poetry add almaapitk@0.4.4`). One command, immediate revert.
3. **Git tag** — `git checkout v0.4.4` returns the source tree to the
   previous release state.

The 0.4.4 → 0.4.5 surface change is intentionally minimal (one method
in `alma_logging/formatters.py` plus a regression test). If a downstream
fault is observed, the rollback to 0.4.4 is safe; the only behavior
change in 0.4.5 is *more redaction*, never less data fidelity for
non-secret fields.

## [0.4.3] — 2026-05-11

### Fixed

- `almaapitk.__version__` now reads dynamically from the installed
  distribution's metadata (`importlib.metadata.version("almaapitk")`)
  instead of a hardcoded string. The hardcoded value had drifted —
  `0.4.2` shipped to PyPI with `__version__ == "0.3.1"` baked into
  `src/almaapitk/__init__.py` because the version-bump step only
  touched `pyproject.toml`. A regression test at `tests/test_version.py`
  now asserts `__version__` matches the installed-metadata version,
  per CLAUDE.md R10 (bug-driven regression tests).

## [0.4.2] — 2026-05-11 [YANKED 2026-05-11]

> **⚠️ Yanked from PyPI on 2026-05-11.** This release shipped with a
> stale `__version__` string: `pip install almaapitk==0.4.2` resolved
> correctly, but `import almaapitk; almaapitk.__version__` returned
> `"0.3.1"` because `src/almaapitk/__init__.py` had a hardcoded version
> constant that drifted from `pyproject.toml`. Fixed in `0.4.3` —
> `__version__` is now resolved dynamically from package metadata, and
> a regression test (`tests/test_version.py`) prevents the bug from
> recurring. Upgrade to `0.4.3`; pinned consumers can keep `0.4.2`
> safely (the API surface is identical to `0.4.3`; only the reported
> `__version__` string differs).

First publish of the 0.4.x series to PyPI. (`0.4.0` and `0.4.1` were
uploaded to TestPyPI during pre-publish verification but never
released to real PyPI; doc-completeness corrections caught during the
TestPyPI gate required two version bumps in succession, mirroring the
`0.3.0` → `0.3.1` path. The final bump to `0.4.2` added `Analytics`
and `Configuration` to the top-level discoverability surfaces —
`README.md`, `docs/index.md`, `docs/getting-started.md` — and noted
that `Configuration` is the active expansion area going into 0.5.x.)
The full 0.4.0 content set is preserved below.

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

[Unreleased]: https://github.com/hagaybar/AlmaAPITK/compare/v0.4.5...HEAD
[0.4.5]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.4.5
[0.4.3]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.4.3
[0.4.2]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.4.2
[0.3.1]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.3.1
