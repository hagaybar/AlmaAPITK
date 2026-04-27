# Design: First PyPI Release of `almaapitk`

**Date:** 2026-04-27
**Status:** Approved (pending user review of this written spec)
**Target version:** `0.3.0`
**Execution mechanism:** `/babysitter:call`
**Follow-up spec (out of scope here):** Trusted Publisher (OIDC) + GitHub Actions release workflow

---

## 1. Context

Today, `almaapitk` is consumed by 4–6 internal repositories that pin it via git URL/tag (e.g. `git+https://github.com/hagaybar/AlmaAPITK@v0.2.0`). The package metadata, `LICENSE`, and `README.md` are already PyPI-shaped (see commit `17313cd`, 2026-03-16), and a `0.2.0` build was verified locally. Since that prep, two real additions landed on `main`:

- `Analytics` domain class with `get_report_headers` / `fetch_report_rows` (commit `29c7491`)
- `progress_callback` hook on `fetch_report_rows` (commit `dde7b1d`)

The package has not been pushed to any registry. This spec covers the first publish.

## 2. Goals

1. Publish `almaapitk 0.3.0` to PyPI so internal projects (and external users) can `pip install almaapitk`.
2. Validate the published artifact end-to-end as if installed by an outsider.
3. Leave a repeatable manual recipe for future releases.
4. Set up cleanly for a follow-up spec that introduces OIDC + GitHub Actions automation.

## 3. Non-goals

- Migrating internal consumer repositories from git pins to `almaapitk` from PyPI. Those repos migrate lazily, on their own dep-bump schedule.
- Setting up Trusted Publisher / OIDC / GitHub Actions release workflow. That belongs in the next spec.
- Committing to `1.0.0` API stability. We're shipping `0.3.0` (Beta classifier).
- Creating an Anaconda / conda-forge package.

## 4. Decisions taken during brainstorming

| # | Decision | Reasoning |
|---|---|---|
| D1 | Audience: internal-first, public-friendly | User answer "C". Shapes polish, support burden, BC commitments. |
| D2 | Trigger: manual now, automate next | User answer "D". Iteration on first publish is much faster locally than via CI. |
| D3 | Scope: publish only, no consumer migration | User decision. Validation done via fresh smoke scripts instead. |
| D4 | TestPyPI dry run before PyPI | User answer "A". PyPI uploads are immutable; TestPyPI absorbs first-time mistakes. |
| D5 | Sequencing: 2-then-3 (manual publish first, OIDC/CI in follow-up spec) | First-publish iteration speed; Trusted Publisher cleanly slots in *after* the project exists on PyPI. |
| D6 | Pre-publish audit added | User request. PyPI artifacts are public and immutable — cheapest insurance. |
| D7 | Version bump `0.2.0 → 0.3.0` | Analytics domain + `progress_callback` are real feature additions since `17313cd`. Minor bump is honest. |
| D8 | Exclude `tests/` from wheel and sdist | User decision. Prevents shipping fixtures, keeps wheel small, follows the dominant convention. |
| D9 | Publish tool: `twine`, not `poetry publish` | Poetry's credential reading from `~/.pypirc` is inconsistent across versions. `twine` reads it natively. Single source of truth. |

## 5. Prerequisites (human, before any babysitter run)

These are interactive web/local steps no agent can perform.

| ID | Action | Status |
|---|---|---|
| P1 | TestPyPI account created at `https://test.pypi.org/account/register/` | ✅ Done |
| P2 | TestPyPI 2FA enabled | ✅ Done |
| P3 | TestPyPI "Entire account" API token generated | ✅ Done |
| P4 | PyPI account created at `https://pypi.org/account/register/` | ✅ Done |
| P5 | PyPI 2FA enabled (mandatory) | ✅ Done |
| P6 | PyPI "Entire account" API token generated | ✅ Done |
| P7 | `~/.pypirc` populated with both tokens, `chmod 600` | ✅ Done |
| P8 | Smoke-test config file at `scripts/post_publish/smoke_config.json` (gitignored) | ⏳ Pending — user creates before run |

**P8 contents (template):**

```json
{
  "sandbox_mms_id": "<a known existing bib MMS ID in the SANDBOX environment>",
  "analytics_report_path": "<URL-encoded analytics report path; PROD only — see note below>"
}
```

**Important constraint:** Alma Analytics has a single shared database that is only accessible with **PRODUCTION** credentials. There is no analytics endpoint in SANDBOX. So smoke script `03_analytics_headers.py` must instantiate `AlmaAPIClient("PRODUCTION")` and read `ALMA_PROD_API_KEY` from env, while `01_test_connection.py` and `02_get_bib.py` use SANDBOX. The report path is stored URL-encoded as the API expects it.

This file must be in place locally before babysitter runs Phase 2.5 / 3.5. It is gitignored — never committed. **(Already created on 2026-04-27 with confirmed values.)**

## 6. Architecture

Five phases, executed in order. A failed step halts the run; do not skip ahead.

```
Prerequisites (human, P1–P8) ─→ [Phase 0: Audit]
                                       │
                                  user triages 🔴/🟡/🟢
                                       │
                                       ▼
                                 [Phase 1: Pre-flight]
                                       │
                                       ▼
                                 [Phase 2: TestPyPI dry run]
                                       │
                                       ▼
                                 [Phase 3: PyPI publish]
                                       │
                                       ▼
                                 [Phase 4: Repo housekeeping]
                                       │
                                       ▼
                                 (Phase 5 = next spec)
```

## 7. Phase 0 — Pre-publish audit

**Goal:** Walk the source tree as if reading a stranger's published wheel. Surface anything embarrassing, identifying, dangerous, or wrong.

### 7.1 Categories checked

1. **Secrets & credentials** — hardcoded API keys, sandbox tokens, test passwords, `.env` files tracked, real values in `config/*.example.*` files.
2. **Identifying / internal info** — TAU-specific library codes, institution hostnames, real user primary IDs, real MMS IDs in fixtures or examples (other than the sample identifiers used legitimately in tests), internal-only URLs, personal data.
3. **Cruft / leftover dev material** — `TODO`, `FIXME`, `XXX`, `HACK` comments; commented-out code blocks; stray `print(` calls in `src/almaapitk/` that should be `self.logger.*`; debug flags; backup files (`*.bak`, `*~`).
4. **Bad practices** — bare `except:`, swallowed exceptions, mutable default args, missing type hints on public API, undocumented public methods, inconsistent naming.
5. **Files that should not be in the artifact** — explicit denylist below.
6. **Light logic checks** — resource leaks (unclosed `requests.Session`), pagination correctness in `_fetch_all_pages` patterns, retry logic, error-class hierarchy consistency.

### 7.2 Tools used

- `ruff check src/almaapitk` — style + many real bugs
- `bandit -r src/almaapitk` — security issues, especially the hardcoded-secrets detector
- `vulture src/almaapitk` — dead code
- `grep -rEn 'TODO|FIXME|XXX|HACK|print\(|tauex\.tau\.ac\.il|localhost|your-api-key|your_api_key' src/almaapitk` — text patterns
- `unzip -l dist/*.whl` and `tar -tzf dist/*.tar.gz` — wheel/sdist contents (run after Phase 1.5 build)
- Manual read of `src/almaapitk/__init__.py` and each domain's public method signatures + docstrings

### 7.3 Wheel/sdist exclusion list (D8)

The build must not include any of these:

- `tests/` and any `test_*.py` outside `src/`
- `logs/`
- `backups/`
- `.a5c/`
- `dist/` (must not bundle prior artifacts)
- `docs/PROJECT_STATUS_*.md`
- `docs/TASKS.md`
- `docs/superpowers/` (this directory)
- `scripts/investigations/`
- Root-level `CLAUDE.md`, `AGENTS.md`, `CLAUDE_tmp.html`, `ALMA_DIGITAL_DOCUMENTATION_EVALUATION.md`
- Any `.env`, `*.example.json` containing non-template values, `__pycache__`, `*.pyc`

### 7.4 Output and decision gate

Findings are written to `docs/superpowers/specs/2026-04-27-pypi-publishing-audit-findings.md`, categorized:

- **🔴 Block publish** — secrets, credentials, identifying info. Must be fixed before Phase 1.
- **🟡 Should fix** — cruft, bad practices, files in the wheel. Fix unless there's a documented reason not to.
- **🟢 FYI** — style nits, opinions, future improvements.

**Gate:** Babysitter halts after Phase 0, hands findings to user, waits for explicit "fix items X, Y, Z; defer the rest" decision. No publish step starts until agreed fixes land on `main`.

## 8. Phase 1 — Pre-flight / packaging hygiene

| Step | Action | Halt condition |
|---|---|---|
| 1.1 | `curl -sf https://pypi.org/pypi/almaapitk/json -o /dev/null && echo TAKEN \|\| echo FREE` | If `TAKEN`, halt. Re-plan name with user (candidates: `almaapitk-tau`, `pyalmaapi`, `almaapi-toolkit`) |
| 1.2 | Bump `pyproject.toml` version `0.2.0 → 0.3.0`. Commit on `main` (per memory: all changes go to `main`; `prod` is manual). | Build fails after bump |
| 1.3 | Configure exclusions (see 7.3). For Poetry, this means `[tool.poetry]` `exclude` list and ensuring `include` doesn't broaden. Update `MANIFEST.in` if present (sdist control). | Exclusion list disagreement with Phase 7.3 |
| 1.4 | Write release notes for `0.3.0`. Location: `docs/releases/0.3.0.md`. Cover: Analytics domain, `progress_callback`, README/LICENSE additions, packaging metadata polish. | — |
| 1.5 | `rm -rf dist/ && poetry build`. Inspect `unzip -l dist/*.whl` and `tar -tzf dist/*.tar.gz`. Hand-verify nothing on the 7.3 list slipped in. | Any excluded path is present |
| 1.6 | `pipx run twine check dist/*` | Any rendering or metadata error reported |
| 1.7 | Create `scripts/post_publish/` with the three smoke scripts (§11), `smoke_config.example.json` (placeholder values, committed), and a `.gitignore` excluding `smoke_config.json`. Commit. | — |
| 1.8 | Create `docs/releases/` directory if missing. Place `0.3.0.md` (Phase 1.4 output) there. Commit. | — |

## 9. Phase 2 — TestPyPI dry run

Same artifacts that will go to real PyPI in Phase 3. **No re-builds between Phase 2 and Phase 3.**

| Step | Action | Halt condition |
|---|---|---|
| 2.1 | Verify `~/.pypirc` is `0600` and contains both `[pypi]` and `[testpypi]` sections with `username = __token__`. (Token values not read.) | Permissions wrong, sections missing |
| 2.2 | `pipx run twine upload --repository testpypi dist/*` | Upload error (most likely: token issue, name conflict, README rendering rejection) |
| 2.3 | Open `https://test.pypi.org/project/almaapitk/0.3.0/` and visually verify: README renders, classifiers show, project URLs work, version is correct, license is MIT. | Any visible defect |
| 2.4 | Create fresh venv in `/tmp/almaapitk-smoke-testpypi/` (outside the project tree to avoid editable-install shadowing). `python -m venv /tmp/almaapitk-smoke-testpypi/venv && source /tmp/almaapitk-smoke-testpypi/venv/bin/activate && pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ almaapitk==0.3.0`. The `--extra-index-url` is required because dependencies live on real PyPI. | Install fails |
| 2.5 | Run all three smoke scripts (see §11). Scripts 01 and 02 hit `SANDBOX` (need `ALMA_SB_API_KEY`); script 03 hits `PRODUCTION` because Analytics is a single shared DB accessible only via PROD credentials (needs `ALMA_PROD_API_KEY`). All three read `scripts/post_publish/smoke_config.json`. | Any of the three returns non-zero |
| 2.6 | Run `pip show almaapitk` — version must be `0.3.0`, not a cached older version. | Wrong version |

## 10. Phase 3 — PyPI publish

| Step | Action | Halt condition |
|---|---|---|
| 3.1 | `pipx run twine upload dist/*` (no `-r` flag → defaults to PyPI per `~/.pypirc`) | Upload error |
| 3.2 | Open `https://pypi.org/project/almaapitk/0.3.0/` and visually verify (same checklist as 2.3). | Any visible defect — note that you cannot re-upload `0.3.0`; a fix means publishing `0.3.1` |
| 3.3 | Create a *second* fresh venv in `/tmp/almaapitk-smoke-pypi/`. `pip install almaapitk==0.3.0` (no `-i` flag). | Install fails |
| 3.4 | Re-run all three smoke scripts. | Any failure |
| 3.5 | `pip show almaapitk` — confirm `0.3.0`. | Wrong version |

## 11. Smoke test scripts

Location: `scripts/post_publish/`. Committed to the repo (no secrets — they read env vars and the gitignored `smoke_config.json`).

### 11.1 `01_test_connection.py`

```python
"""Smoke test: instantiate the client and confirm SANDBOX auth works."""
from almaapitk import AlmaAPIClient

client = AlmaAPIClient("SANDBOX")
client.test_connection()  # raises AlmaAPIError on failure; success is silent
print("OK: test_connection passed")
```

(Pattern follows the existing CLAUDE.md example: `test_connection()` is called without asserting on return value because its return contract is "raise on failure".)

### 11.2 `02_get_bib.py`

```python
"""Smoke test: fetch a known bib record from SANDBOX."""
import json, pathlib
from almaapitk import AlmaAPIClient, BibliographicRecords

config = json.loads(pathlib.Path(__file__).parent.joinpath("smoke_config.json").read_text())
client = AlmaAPIClient("SANDBOX")
bibs = BibliographicRecords(client)
result = bibs.get_bib(config["sandbox_mms_id"])
assert result is not None
print(f"OK: got bib {config['sandbox_mms_id']}")
```

### 11.3 `03_analytics_headers.py`

```python
"""Smoke test: fetch report headers (validates Analytics domain shipped).

Note: Analytics has a single shared database accessible only via PRODUCTION
credentials. SANDBOX has no analytics endpoint. This script therefore uses
the PROD client; ALMA_PROD_API_KEY must be set.
"""
import json, pathlib
from almaapitk import AlmaAPIClient, Analytics

config = json.loads(pathlib.Path(__file__).parent.joinpath("smoke_config.json").read_text())
client = AlmaAPIClient("PRODUCTION")
analytics = Analytics(client)
headers = analytics.get_report_headers(config["analytics_report_path"])
assert headers, "no headers returned"
print(f"OK: got {len(headers)} headers")
```

All three exit non-zero on assertion failure (default Python behavior). Each prints exactly one `OK:` line on success.

**Env vars required when running smoke tests:** `ALMA_SB_API_KEY` (for scripts 01 and 02) and `ALMA_PROD_API_KEY` (for script 03).

A `scripts/post_publish/.gitignore` excludes `smoke_config.json`. A `scripts/post_publish/smoke_config.example.json` is committed with placeholder values. Both files (the example and the gitignore) are created in Phase 1.7. The user fills `smoke_config.json` locally as prerequisite P8.

## 12. Phase 4 — Repo housekeeping

| Step | Action |
|---|---|
| 4.1 | `git tag v0.3.0 && git push origin v0.3.0` |
| 4.2 | Create GitHub Release at `v0.3.0` using `docs/releases/0.3.0.md` as the body. Mark as latest release. |
| 4.3 | Verify README's installation section says `pip install almaapitk` (it already does — just confirm) |
| 4.4 | Write `docs/releases/HOW_TO_RELEASE.md`: the step-by-step manual recipe that just worked, captured for the next release / your future self. Includes the token-rotation note from 4.5. |
| 4.5 | **Token rotation.** On both PyPI and TestPyPI: revoke the broad "Entire account" tokens. Generate new tokens scoped to project `almaapitk`. Update `~/.pypirc` with the project-scoped tokens. The broad tokens are necessary only for the very first publish of a brand-new project name. |
| 4.6 | Open a tracking issue: "Approach 3 — Trusted Publisher (OIDC) + GH Actions release workflow". Link to this spec. Do not implement yet. |

## 13. Phase 5 — Out of scope (next spec)

The follow-up spec, written separately when you're ready, will cover:

- PyPI Trusted Publisher (OIDC) configuration for the `hagaybar/AlmaAPITK` GitHub repo
- `.github/workflows/release.yml` — tag-triggered or release-triggered build + publish
- Optional: TestPyPI publish on every push to `main` for continuous validation
- Internal consumer migration plan (per repo, lazily)

## 14. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Name `almaapitk` is taken on PyPI | Low (very specific name) | Halts Phase 1 | Phase 1.1 checks first; name fallback list documented |
| README renders badly on PyPI | Medium (first time) | Cosmetic, not functional | Phase 1.6 `twine check` + Phase 2.3 visual check on TestPyPI |
| Excluded directory leaks into wheel | Medium (Poetry exclusion config is finicky) | Privacy / size | Phase 1.5 wheel-contents inspection; Phase 0 audit |
| Smoke test fixture values reveal internal info if committed | High if not careful | Privacy | `smoke_config.json` gitignored; only `smoke_config.example.json` committed |
| `0.3.0` shipped, defect found, can't re-upload | Inherent to PyPI | Embarrassing, bumps to `0.3.1` | TestPyPI dry run absorbs most; accept the residual risk |
| Token leak | Addressed | High | `~/.pypirc` is `0600`; broad tokens rotated to project-scoped in Phase 4.5 |
| Babysitter run interrupted mid-phase | Low | Recovery confusion | Each phase produces a checkpoint (artifact, tag, or commit). Resume by skipping completed phases. |

## 15. Success criteria

The release is "done" when **all** of the following hold:

1. `https://pypi.org/project/almaapitk/0.3.0/` exists and renders cleanly.
2. `pip install almaapitk==0.3.0` in a fresh venv installs successfully.
3. All three smoke scripts (§11) pass against the PyPI install.
4. `v0.3.0` tag is pushed; GitHub Release exists with notes from `docs/releases/0.3.0.md`.
5. `docs/releases/HOW_TO_RELEASE.md` is committed.
6. PyPI and TestPyPI tokens have been rotated to project-scoped `almaapitk`.
7. Follow-up issue for Approach 3 is open.

## 16. Execution

This spec is implemented via `/babysitter:call`. The babysitter run owns Phases 0 through 4. Prerequisites P1–P8 are user responsibility before the run starts.

If the audit (Phase 0) finds blockers, the run halts and surfaces findings to the user; the implementation plan must include this gate.

## 17. Open items the implementation plan should address

- Confirm the exact `pyproject.toml` exclusion syntax that Poetry 2.x honors for both wheel and sdist (Poetry's `exclude` historically applies to sdist; wheel may need additional handling).
- Decide whether release notes live in `docs/releases/0.3.0.md` *and* the GitHub Release body, or only the latter (recommendation: both, the file is the durable record).
- Confirm whether `pipx` is available in the babysitter environment, or fall back to installing `twine` in a dedicated venv.
