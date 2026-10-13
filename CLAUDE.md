# CLAUDE.md

Guidance for Claude Code in this repository. Keep this file short: it holds rules and
pointers, not reference material. Reference lives in `docs/`.

## What this repo is

`almaapitk`, a Python toolkit for the Ex Libris Alma ILS REST API, published on PyPI.
It is a **core library only**. Workflows that use it live in their own repos (the
production consumers): `Fetch_Alma_Analytics_Reports`, `Alma-RS-lending-request-automation`,
`Update_Alma_Digital_Collections`, `Alma-Digital-Upload`, `Alma-update-expired-users-emails`.
Keep them on the current release: bump the pin → validate → `main`→`prod` (the user deploys
`prod`).

## Rules

- **R7 (deny-paths):** `.github/**` and `secrets/**` are blocked by deny rules in
  `.claude/settings.json`. Changes there need the owner.
- **R8:** never run SANDBOX tooling with `ALMA_PROD_API_KEY` set. `scripts/regression_smoke.py`
  refuses to run if it is set; tell the operator to `unset ALMA_PROD_API_KEY` and retry.
- **R9 (public repo, no real identifiers):** never put real user IDs, MMS IDs, vendor codes,
  POL IDs, institution codes or emails in committed files, commit messages, PR or issue
  text, docs, or `example` fields. Use placeholders (`<user_primary_id>`, `tau000000`).
  Operator-supplied IDs may be used for a run but are redacted in anything written or pushed.
  `tests/sandbox/*/test-data.json` is gitignored for this reason.
- **R10 (bug-driven regression tests):** for every real bug, first write a failing test in
  `tests/unit/regressions/test_issue_<N>.py` (or `test_bug_found_at_<YYYY-MM-DD>.py` if there
  is no issue), confirm it fails, fix, confirm it passes, and commit test and fix together.
  A SANDBOX smoke does not count as the R10 test.

## How work is done

Work issues directly from GitHub (the chunk pipeline was retired in 2026-10; it is archived
in `docs/archive/chunk-pipeline/`). The loop:

1. One issue, or a small group of related issues (grouped by GitHub milestone), per branch.
2. Bugs: R10 test first. Features: tests alongside the code.
3. Before the PR, run `poetry run python scripts/smoke_import.py` and
   `poetry run pytest tests/unit tests/logging tests/integration tests/meta -q`.
4. PR → CI green → review (`/code-review`) → merge when the user asks.
5. If a change alters API request/response shapes, run the live SANDBOX smokes before the next
   release: `poetry run python -m scripts.regression_smoke` (needs `ALMA_SB_API_KEY` and local
   fixtures; this is not a release gate).

Releases follow `docs/RELEASE_CHECKLIST.md`; a `v*` tag triggers `.github/workflows/release.yml`.

## Backlog

- Architecture: `is:open is:issue label:enhancement -label:api-coverage`
- API coverage: `is:open is:issue label:api-coverage` (use `priority:*` labels to narrow)
- Bugs: `is:open is:issue label:bug`

Coverage issues follow a standard body (Domain, Priority, Effort, endpoints, methods to add,
files to touch, acceptance criteria). Check the backlog before proposing a new improvement;
it is probably already filed. Design rationale:
`docs/superpowers/specs/2026-04-30-coverage-expansion-design.md`.

## Alma swagger snapshot

`docs/alma-swagger/` holds a committed copy of Ex Libris' OpenAPI per domain (retrieved
2026-05-29; `task-lists` has none). Treat it as the source of truth for endpoints, verbs,
params, body shapes and error codes. How to refresh it and the domain/file aliases are in
`docs/alma-swagger/README.md`. Gotcha: numeric fields inside `{value, link}` objects are
typed `string` (e.g. `number_of_members.value`), so coerce with `int()`.

## Architecture

```python
from almaapitk import AlmaAPIClient, Acquisitions, ResourceSharing
```

- `src/almaapitk/client/`: `AlmaAPIClient` (persistent session, retry/backoff, timeouts,
  `iter_paged`), `AlmaResponse`, and the error hierarchy (`AlmaAPIError`,
  `AlmaValidationError`, `AlmaRateLimitError`, `AlmaAuthenticationError`, …).
- `src/almaapitk/domains/`: `Acquisitions`, `Admin`, `Analytics`, `BibliographicRecords`,
  `Configuration`, `ResourceSharing`, `Users`, plus `Electronic` (import from
  `almaapitk.domains.electronic`; not exported at top level).
- `src/almaapitk/utils/`: `TSVGenerator`, citation metadata. Body builders live with their
  domain (`build_alma_bib_xml` in `bibs.py`, `build_user_rs_request` in `users.py`).
- `src/almaapitk/testing/`: smoke-test harness and pytest plugin (`almaapitk[smoke]`).
- The public surface is defined in `docs/API_CONTRACT.md` and guarded by
  `tests/test_public_api_contract.py`.

Patterns: domain classes take a client instance and log via `get_logger`; every call goes
through `AlmaAPIClient`; walk paged endpoints with `client.iter_paged(path, params=...,
record_key=..., max_records=...)` (a generator, so stop early when you can). Method names
are `get_*` / `create_*` / `update_*` / `delete_*`.

## Coding standards

- PEP 8, type hints and docstrings on public methods; functions focused (~50 lines max).
- Domain-flavoured names (`bib_mms_id`, `user_primary_id`).
- Logging through `almaapitk.alma_logging.get_logger`, never `print`. Log method entry with
  key IDs, successes with result IDs, and errors with code, message and tracking ID. Never
  log keys or full personal-data payloads. Details: `docs/logging.md`.
- No hardcoded keys; configuration comes from env vars. Scripts default to dry-run.
- Test in SANDBOX (`ALMA_SB_API_KEY`) before PRODUCTION (`ALMA_PROD_API_KEY`).

## Commands

```bash
poetry install
poetry run python scripts/smoke_import.py                                 # public API imports
poetry run pytest tests/unit tests/logging tests/integration tests/meta -q   # release test set
poetry run pytest tests/unit/regressions/ -q                              # R10 suite
make smoke / make smoke-live                                              # workflow smokes
```

## Skills and git

- `alma-api-expert`: Alma endpoints, error codes, quirks, digital uploads.
- `python-dev-expert`: code quality and structure.
- `git-expert`: commits and PRs. Commit granularly with descriptive messages and push after
  committing; never push to `prod`.

These skills are installed at user level (`~/.claude/skills/`), not in this repo.
