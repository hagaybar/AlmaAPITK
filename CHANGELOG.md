# Changelog

All notable changes to `almaapitk` are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/).

## [Unreleased]

## [0.5.0] — 2026-07-07

### Added

- **Structure-driven bib creation** (`BibliographicRecords`, issue #179).
  Three layers, all funnelling into the existing `create_record(xml)`:
  - `build_alma_bib_xml(spec) -> str` — a **pure**, network-free builder that
    turns a native JSON field structure into Alma's non-namespaced
    `<bib><record>…</record></bib>` MARCXML. Preserves field order, supports
    repeated fields (multiple `650`) and repeated subfields, maps control
    fields (`00X`) to `<controlfield>`/`data` and data fields to
    `ind1`/`ind2` + `<subfield>`, defaults the leader when omitted
    (`DEFAULT_BIB_LEADER`), and lets `ElementTree` escape once (no
    double-escaping). Unit-testable in isolation.
  - `create_record_from_fields(spec)` — builds the XML and POSTs it via
    `create_record` (dependency-free; usable from non-Python callers such as
    Power Automate).
  - `create_record_from_pymarc(record)` — optional adapter converting a
    `pymarc.Record` → spec → builder → `create_record`. `pymarc` is a new
    optional extra (`pip install almaapitk[pymarc]`), imported lazily; calling
    the adapter without it installed raises a clear, actionable `ImportError`.
    The core install pulls no new dependencies.

  Purely additive — no existing signature or behavior changed. Regression test:
  `tests/unit/regressions/test_issue_179.py`.

### Documentation

- **Hosted documentation site** (MkDocs Material) published to GitHub Pages at
  <https://hagaybar.github.io/AlmaAPITK/>, built and deployed by
  `.github/workflows/docs.yml` on every push to `main`. Includes the existing
  getting-started / examples / error-handling / logging guides plus a full
  **API reference auto-generated from the source docstrings** (mkdocstrings),
  so method signatures and parameters can never drift from the code. Source
  lives in `docs/site/` + `mkdocs.yml`; the PyPI `Documentation` URL now points
  at the site. (`close()`'s docstring changed a `Raises: None` block to a
  `Note:` — no behavior change.)

### Added

- **L1 ResourceSharing contract tests** (`tests/unit/contracts/test_resource_sharing_contract.py`).
  Pin the `almaapitk` surface the `Alma-RS-lending-request-automation`
  consumer relies on — importable symbols, `ResourceSharing` construction,
  `create_lending_request` (returns a dict with `request_id`; `owner` sent as
  a plain string while `partner`/`format`/`citation_type` are wrapped;
  POSTs to `partners/{code}/lending-requests`; missing mandatory fields raise
  a client-side `ValueError` before any request), `get_lending_request`,
  `get_request_summary` output shape, `create_lending_request_from_citation`
  enrich-and-delegate, and the error hierarchy. Run with no creds/network via
  the dry-run harness; a regression in any pinned behavior goes red before a
  release is cut. Part of the consumer-rollout gate work (meta #158).
- **L1 BibliographicRecords collection contract tests** (`tests/unit/contracts/test_bibs_collections_contract.py`).
  Pin the surface the `Update_Alma_Digital_Collections` consumer relies on —
  `get_collection_members` (GET `bibs/collections/{id}/bibs`, paged, with
  `response.json()["total_record_count"]` exposed), `add_to_collection`
  (POST `{"mms_id": ...}` to the same path), `remove_from_collection`
  (DELETE `bibs/collections/{id}/bibs/{mms_id}`), and client-side
  `AlmaValidationError` on empty `collection_id`/`mms_id` before any request.
  This consumer is pinned far back (`>= 0.3.1`), so these contracts plus its
  own live SANDBOX smoke de-risk the bump to the current release. Part of the
  consumer-rollout gate work (meta #158).

### Changed

- **`almaapitk.testing.build_smoke_client` now enforces R-H2 in the Infra.**
  Building a *writable* PRODUCTION smoke client
  (`environment="PRODUCTION", readonly=False`) now raises `ValueError` at
  construction instead of silently returning an unguarded client — "PRODUCTION
  is read-only, always" is no longer left to the caller to remember.
  Read-only PRODUCTION smokes and writable SANDBOX smokes are unchanged.
  Surfaced by the first mutating consumer (RS-lending), whose L3 smoke is the
  first to pass `readonly=False`.

## [0.4.6] — 2026-06-01

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
- **HTTP retry policy no longer retries `POST`** (issue #166). The urllib3
  `Retry` mounted on the session previously listed `POST` alongside the
  429/5xx status forcelist. POST is non-idempotent, so an automatic retry
  after a 5xx that may already have committed a create could produce a
  duplicate (e.g. a duplicate invoice). POST is now excluded, matching
  urllib3's own default; the idempotent verbs (GET/PUT/DELETE) are still
  retried. **Behaviour change:** a `POST` that hits a transient 429/5xx now
  surfaces that error to the caller instead of being silently retried.
- **`Users.get_user` validates the `expand` parameter client-side** (issue
  #144). Unknown values previously forwarded to Alma and failed with an
  opaque HTTP 400 (`alma_code 401666`) only after the round-trip. Invalid
  values now raise `AlmaValidationError` immediately, listing the allowed
  options (`loans`, `requests`, `fees`; comma-separated; default `none`).

### Fixed

- **`Admin` set-member operations no longer crash on real responses** (issue
  #164). Alma serialises `number_of_members.value` as a string; the code fed
  it straight to `range()` and integer arithmetic, raising `TypeError` on
  every non-empty set (and the empty-set guard `"0" == 0` also failed). The
  count is now coerced to `int` at the extraction points, so pagination, the
  empty-set guard, and the metadata math all work.
- **`Users.list_user_deposits` returns the user's deposits** (issue #162). It
  unwrapped the response under the non-existent key `deposit`; the schema key
  is `user_deposit`, so it silently returned `[]` for users who had deposits.
  It now reads `user_deposit` (with a `deposit` fallback).
- **`Configuration.get_fee_transactions_report` returns transactions** (issue
  #163). It unwrapped under `fee_transaction`, which is not in the `rest_fees`
  schema (the array key is `fee`), so it always returned `[]`. It now reads
  `fee`.
- **Bib create/update send a valid XML `Content-Type`** (issue #167).
  `BibliographicRecords.create_record` / `update_record` passed
  `content_type='xml'`, producing an invalid `Content-Type: xml` header and a
  mismatched `Accept: application/json` over a MARCXML body. They now send
  `application/xml`.
- **`Analytics.fetch_report_rows` accepts a non-int `limit`/`max_rows`**
  (issue #177). A `limit` supplied as a string (e.g. from a JSON config or
  CLI argument) raised a raw `TypeError`; a float was sent to Alma as an
  invalid token. Both are now coerced to `int`, with a clear
  `AlmaValidationError` on non-numeric input.

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
- **Email addresses no longer leak into log messages** (issue #168).
  `Users.update_user_email` / `bulk_update_emails` interpolated the email into
  the log *message* via f-strings, bypassing the redactor (which only scrubs
  structured fields and the `users/<id>` URL form), so the address — PII under
  R9 — reached the console and JSON file handlers verbatim. These calls now
  log via structured kwargs so the redactor blanks the address, and the
  `Invalid email format` validation errors no longer embed it. The remaining
  `user_id`-only message sites in `users.py` were converted in the same pass.
  R10 regression suite: `tests/unit/regressions/test_issue_168.py`.

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

[Unreleased]: https://github.com/hagaybar/AlmaAPITK/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.5.0
[0.4.6]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.4.6
[0.4.5]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.4.5
[0.4.3]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.4.3
[0.4.2]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.4.2
[0.3.1]: https://github.com/hagaybar/AlmaAPITK/releases/tag/v0.3.1
