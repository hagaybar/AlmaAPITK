# PyPI First Publish Implementation Plan

> **For agentic workers:** This plan is designed for `/babysitter:call` execution. Steps use checkbox (`- [ ]`) syntax for tracking. The plan is procedural (audit → build → upload → verify) rather than feature-development TDD; the verification gates after each phase take the place of unit tests.

**Goal:** Publish `almaapitk 0.3.0` to PyPI as the first registered release; validate end-to-end via three fresh-venv smoke scripts.

**Architecture:** Five-phase manual recipe — Phase 0 (audit) → Phase 1 (pre-flight) → Phase 2 (TestPyPI dry run) → Phase 3 (PyPI publish) → Phase 4 (housekeeping). Each phase halts on failure. User decision gates exist after audit triage, after TestPyPI visual verification, after PyPI visual verification, and at token rotation.

**Tech Stack:** Python 3.12+, Poetry 2.x, twine (via pipx), ruff, bandit, vulture, git, gh (GitHub CLI), curl.

**Reference spec:** `docs/superpowers/specs/2026-04-27-pypi-publishing-design.md` (commits `aa82886`, `a7a8b69`, `30b919f`, `6960ef1`).

**Pre-state confirmed at plan-write time (2026-04-27):**
- Prerequisites P1–P7 done by user
- P8 (`scripts/post_publish/smoke_config.json`) created locally with `sandbox_mms_id = "990025559030204146"` and URL-encoded `analytics_report_path`
- `~/.pypirc` populated with project-rotated tokens (user rotated post-disclosure earlier today)
- `src/almaapitk/alma_logging/` doc files moved out of the package (commit `30b919f`); `find src/almaapitk -type f ! -name "*.py" ! -path "*/__pycache__/*"` returns empty
- `pyproject.toml` is at version `0.2.0`; no `include`/`exclude` blocks yet under `[tool.poetry]`
- Working branch: `main`. Per project memory: changes go to `main`; merge to `prod` is manual on user request only.

---

## Pre-flight Verification

Before starting Phase 0, verify the run environment is consistent with prerequisites.

### Task P.1: Verify prerequisites

**Goal:** Fail fast if any prerequisite is missing.

- [ ] **Step 1: Verify `~/.pypirc` exists with 0600 perms**

Run:
```bash
ls -l ~/.pypirc
```
Expected: `-rw-------` and a non-zero size.
On failure: HALT and surface "P7 missing — user must populate `~/.pypirc` per spec §5".

- [ ] **Step 2: Verify both sections present (without reading token values)**

Run:
```bash
grep -cE "^\[(pypi|testpypi)\]$" ~/.pypirc; grep -cE "^username = __token__$" ~/.pypirc
```
Expected: `2` and `2`.
On failure: HALT — `~/.pypirc` is malformed.

- [ ] **Step 3: Verify smoke_config.json exists locally**

Run:
```bash
test -f scripts/post_publish/smoke_config.json && python3 -c "import json; cfg=json.load(open('scripts/post_publish/smoke_config.json')); assert 'sandbox_mms_id' in cfg and 'analytics_report_path' in cfg; print('OK')"
```
Expected: `OK`.
On failure: HALT — P8 missing.

- [ ] **Step 4: Verify smoke_config.json is gitignored**

Run:
```bash
git check-ignore -v scripts/post_publish/smoke_config.json
```
Expected: a line like `.gitignore:NN:scripts/post_publish/smoke_config.json    scripts/post_publish/smoke_config.json`.
On failure: HALT — gitignore mismatch; do NOT proceed (risk of committing identifiers).

- [ ] **Step 5: Verify environment variables are set**

Run:
```bash
test -n "$ALMA_SB_API_KEY" && test -n "$ALMA_PROD_API_KEY" && echo "OK"
```
Expected: `OK`.
On failure: HALT — surface "Both `ALMA_SB_API_KEY` and `ALMA_PROD_API_KEY` must be exported. Smoke script 03 needs PROD because Analytics is PROD-only."

- [ ] **Step 6: Verify branch is `main` and tree is clean**

Run:
```bash
git rev-parse --abbrev-ref HEAD
git status --porcelain
```
Expected: `main` and empty (no `M`/`A`/`??` lines except untracked `.a5c/cache/...` which is fine).
On failure: HALT.

- [ ] **Step 7: Verify required tools available**

Run:
```bash
poetry --version && pipx --version && git --version && gh --version && curl --version | head -1
```
Expected: a version string from each.
On failure: HALT — name the missing tool.

---

## Phase 0 — Pre-publish audit

### Task 0.1: Install audit tools in a dedicated venv

**Goal:** Get ruff, bandit, vulture without polluting the project venv.

- [ ] **Step 1: Create venv**

Run:
```bash
rm -rf /tmp/almaapitk-audit-venv
python3 -m venv /tmp/almaapitk-audit-venv
```

- [ ] **Step 2: Install tools**

Run:
```bash
/tmp/almaapitk-audit-venv/bin/pip install --quiet ruff bandit vulture
```

- [ ] **Step 3: Verify**

Run:
```bash
/tmp/almaapitk-audit-venv/bin/ruff --version
/tmp/almaapitk-audit-venv/bin/bandit --version
/tmp/almaapitk-audit-venv/bin/vulture --version
```
Expected: three version strings.

### Task 0.2: Run ruff over the package source

- [ ] **Step 1: Run and capture**

Run:
```bash
/tmp/almaapitk-audit-venv/bin/ruff check src/almaapitk/ > /tmp/audit-ruff.txt 2>&1; echo "ruff_exit=$?"
```
Expected: `ruff_exit=0` (no findings) or `ruff_exit=1` (findings present). Both acceptable; capture findings either way.

- [ ] **Step 2: Show first 50 lines for record**

Run:
```bash
head -50 /tmp/audit-ruff.txt
```

### Task 0.3: Run bandit (security/secrets scanner)

- [ ] **Step 1: Run and capture**

Run:
```bash
/tmp/almaapitk-audit-venv/bin/bandit -r src/almaapitk/ -f txt -o /tmp/audit-bandit.txt -ll; echo "bandit_exit=$?"
```
Note: `-ll` = report low+ severity. Exit code 0 = clean, 1 = findings.

- [ ] **Step 2: Show summary**

Run:
```bash
grep -E "Severity|Issue:|Test results" /tmp/audit-bandit.txt | head -40
```

### Task 0.4: Run vulture (dead code detection)

- [ ] **Step 1: Run and capture**

Run:
```bash
/tmp/almaapitk-audit-venv/bin/vulture src/almaapitk/ --min-confidence 70 > /tmp/audit-vulture.txt 2>&1; echo "vulture_exit=$?"
```
Note: min-confidence 70 prunes most false positives.

### Task 0.5: Grep sweep for textual patterns

- [ ] **Step 1: TODO/FIXME/HACK/XXX in package source**

Run:
```bash
grep -rEn 'TODO|FIXME|XXX|HACK' src/almaapitk/ > /tmp/audit-todo.txt 2>&1 || true
echo "todo_lines=$(wc -l < /tmp/audit-todo.txt)"
```

- [ ] **Step 2: Stray `print()` calls (anywhere not following a `#`)**

Run:
```bash
grep -rEn '^[^#]*\bprint\(' src/almaapitk/ > /tmp/audit-print.txt 2>&1 || true
echo "print_lines=$(wc -l < /tmp/audit-print.txt)"
```

- [ ] **Step 3: Identifying institution info / hardcoded credential lookalikes**

Run:
```bash
grep -rEni 'tauex\.tau\.ac\.il|your-api-key|your_api_key' src/almaapitk/ > /tmp/audit-identifying.txt 2>&1 || true
echo "ident_lines=$(wc -l < /tmp/audit-identifying.txt)"
```

- [ ] **Step 4: Confirm no non-Python files in package source**

Run:
```bash
find src/almaapitk -type f ! -name "*.py" ! -path "*/__pycache__/*"
```
Expected: empty (the alma_logging doc move in commit `30b919f` should have already cleaned this up).
On failure: list paths — they will become 🔴 findings.

### Task 0.6: Manual public-API review

**Goal:** Read the surface a stranger sees first.

- [ ] **Step 1: Read `src/almaapitk/__init__.py`**

Action: Read the file. For each name in `__all__` (or each public re-export), check: is there a docstring on the underlying class/function? Is the name consistent with naming conventions? Is anything exported that shouldn't be public (helper functions, private internals)?

- [ ] **Step 2: Read each domain class**

Action: Open each of: `src/almaapitk/domains/{acquisition,admin,analytics,bibs,resource_sharing,users}.py`. For each public method (no leading underscore): note missing type hints on params/return, missing docstring, bare `except:` clauses, `except Exception:` without re-raise, mutable default arguments.

Capture findings as bullets in /tmp/audit-manual.txt:
```bash
cat > /tmp/audit-manual.txt <<'EOF'
[fill in observed issues, one bullet each]
EOF
```

### Task 0.7: Compile audit findings report

**Files:**
- Create: `docs/superpowers/specs/2026-04-27-pypi-publishing-audit-findings.md`

- [ ] **Step 1: Write the report**

Use this template, replacing each bracketed section with actual findings from /tmp/audit-*.txt files. If a category has no findings, write "None found." (do not omit the heading).

Content:
```markdown
# Pre-Publish Audit Findings — almaapitk 0.3.0

**Date run:** [substitute today's date in YYYY-MM-DD]
**Tools:** ruff, bandit, vulture, grep, manual review of public API
**Source under review:** `src/almaapitk/`

## 🔴 Block publish (must fix before any upload)

Items in this section are hard blockers. Each line below should describe one specific finding with file:line and a brief note on why it blocks publish.

[Bullets, one per item. If none: "None found."]

Examples of what belongs here:
- Real API key, password, or token committed in code
- Real institution-specific user IDs, library codes, or MMS IDs in fixtures inside src/almaapitk/
- Real internal hostnames or URLs in package source
- Critical bandit High-severity findings

## 🟡 Should fix (fix unless reason to defer)

[Bullets. If none: "None found."]

Examples:
- TODO/FIXME comments in package source
- Stray print() calls in package source
- Vulture high-confidence dead code
- Missing docstrings on public API surface
- Bare `except:` or unhandled `except Exception:`
- Bandit Medium-severity findings

## 🟢 FYI (style nits, opinions)

[Bullets. If none: "None found."]

Examples:
- ruff style warnings
- Vulture low-confidence findings
- Naming preference observations

## Tool output excerpts

### ruff
```
[contents of /tmp/audit-ruff.txt; if empty, write "No findings."]
```

### bandit
```
[Severity-grouped excerpt of /tmp/audit-bandit.txt]
```

### vulture (min-confidence 70)
```
[contents of /tmp/audit-vulture.txt; if empty, write "No findings."]
```

### grep
- `TODO/FIXME/XXX/HACK` lines in /tmp/audit-todo.txt: [count]
- `print()` lines in /tmp/audit-print.txt: [count]
- Identifying-info lines in /tmp/audit-identifying.txt: [count]

[For each above with count > 0, paste the lines verbatim.]

### Manual review notes
[Bullets from /tmp/audit-manual.txt]
```

- [ ] **Step 2: Commit findings**

Run:
```bash
git add docs/superpowers/specs/2026-04-27-pypi-publishing-audit-findings.md
git commit -m "Phase 0 audit findings for almaapitk 0.3.0 pre-publish"
```

### Task 0.8: HALT — User triage

- [ ] **Step 1: Surface findings to user**

Surface message:
> Phase 0 audit complete. Findings written to `docs/superpowers/specs/2026-04-27-pypi-publishing-audit-findings.md` and committed.
>
> Please review and reply with: which 🔴 items must be fixed (mandatory; cannot proceed without), which 🟡 to fix vs defer, and any 🟢 to act on.
>
> Phase 1 will not start until you respond.

- [ ] **Step 2: Wait for user response.** Capture the agreed fix list.

### Task 0.9: Apply agreed audit fixes

- [ ] **Step 1: For each agreed fix from Task 0.8**

Action: Edit the relevant file. Follow this loop per fix:
1. Make the change.
2. Run `poetry run pytest tests/ -x` (existing test suite). Expected: still passes.
3. Run `poetry run python scripts/smoke_import.py`. Expected: success.
4. `git add <file> && git commit -m "fix(audit): <one-line description of fix>"`.

If the agreed list is empty (audit was clean): skip all steps in this task.

- [ ] **Step 2: Re-verify package source is clean of non-Python files**

Run:
```bash
find src/almaapitk -type f ! -name "*.py" ! -path "*/__pycache__/*"
```
Expected: empty.

---

## Phase 1 — Pre-flight / packaging hygiene

### Task 1.1: Verify name availability on PyPI

- [ ] **Step 1: Query PyPI**

Run:
```bash
HTTP=$(curl -s -o /dev/null -w '%{http_code}' https://pypi.org/pypi/almaapitk/json); echo "http=$HTTP"
```
Expected: `http=404` (name is FREE).
On `http=200`: HALT — surface "Name `almaapitk` is already registered on PyPI. Re-plan with an alternative name (suggested: `almaapitk-tau`, `pyalmaapi`, `almaapi-toolkit`). This requires updating spec §1.1 and `pyproject.toml` `[project] name`."
On any other code: HALT — investigate (network issue, PyPI degradation, etc).

### Task 1.2: Bump version to 0.3.0

**Files:**
- Modify: `pyproject.toml` (line beginning `version = `)

- [ ] **Step 1: Edit pyproject.toml**

Use the Edit tool to change `version = "0.2.0"` to `version = "0.3.0"`.

- [ ] **Step 2: Verify**

Run:
```bash
grep -n '^version = ' pyproject.toml
```
Expected: a single line: `3:version = "0.3.0"` (or whatever the line number is — single match, with `0.3.0`).

- [ ] **Step 3: Commit**

Run:
```bash
git add pyproject.toml
git commit -m "Bump version to 0.3.0 for first PyPI release"
```

### Task 1.3: Configure inclusion list (Option 2 allowlist)

**Goal:** sdist contains exactly `src/almaapitk/**`, `pyproject.toml` (auto), `README.md`, `LICENSE`, `docs/releases/0.3.0.md`. Wheel is already an allowlist via `packages = [...]`.

**Files:**
- Modify: `pyproject.toml` (`[tool.poetry]` section, after `packages = [...]`)

- [ ] **Step 1: Edit pyproject.toml**

Locate the line:
```toml
[tool.poetry]
packages = [{ include = "almaapitk", from = "src" }]
```

Insert the following AFTER `packages = [...]` and within the same `[tool.poetry]` block:
```toml
include = [
    { path = "README.md", format = "sdist" },
    { path = "LICENSE", format = "sdist" },
    { path = "docs/releases/0.3.0.md", format = "sdist" },
]
exclude = ["**/*"]
```

- [ ] **Step 2: Validate TOML syntax**

Run:
```bash
python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('OK')"
```
Expected: `OK`.

- [ ] **Step 3: Commit**

Run:
```bash
git add pyproject.toml
git commit -m "Configure pyproject.toml inclusion list for sdist (Option 2 allowlist)"
```

Note: Per spec §17, Poetry 2.x's exact handling of `exclude = ["**/*"]` combined with `include` is the documented fiddly area. Phase 1.7 inspection is the verification gate — if the sdist contents are wrong, return here and adjust.

### Task 1.4: Write release notes

**Files:**
- Create: `docs/releases/0.3.0.md`

- [ ] **Step 1: Create directory**

Run:
```bash
mkdir -p docs/releases
```

- [ ] **Step 2: Write the file**

Substitute today's date for `[YYYY-MM-DD]` below.

Content:
```markdown
# almaapitk 0.3.0

**Release date:** [YYYY-MM-DD]

First publish of `almaapitk` to PyPI.

## What's new since 0.2.0 (built locally on 2026-03-16, never published)

- **`Analytics` domain class.** Supports Alma Analytics reports via `get_report_headers()` and `fetch_report_rows()` with built-in pagination. Note: Alma Analytics is backed by a single shared database accessible only via PRODUCTION credentials; SANDBOX has no analytics endpoint.
- **`progress_callback` hook on `Analytics.fetch_report_rows()`.** Invoked after each page so callers can display progress for long-running fetches.
- **Documentation moved out of the package.** Three internal docs files that previously lived in `src/almaapitk/alma_logging/` were moved to `docs/alma_logging/` so the published wheel contains zero non-Python content.

## Public API

```python
from almaapitk import (
    AlmaAPIClient,
    AlmaResponse,
    AlmaAPIError, AlmaValidationError,
    Admin, Users, BibliographicRecords, Acquisitions, ResourceSharing, Analytics,
    TSVGenerator, CitationMetadataError,
)
```

## Installation

```bash
pip install almaapitk
```

## Repository

`https://github.com/hagaybar/AlmaAPITK`
```

- [ ] **Step 3: Commit**

Run:
```bash
git add docs/releases/0.3.0.md
git commit -m "Add release notes for almaapitk 0.3.0"
```

### Task 1.5: Build artifacts

- [ ] **Step 1: Clean prior dist**

Run:
```bash
rm -rf dist/
```

- [ ] **Step 2: Build**

Run:
```bash
poetry build
```
Expected: output ends with two `Built ...` lines naming the .tar.gz and the .whl.

- [ ] **Step 3: Verify both files present**

Run:
```bash
ls -la dist/
```
Expected: exactly two files — `almaapitk-0.3.0-py3-none-any.whl` and `almaapitk-0.3.0.tar.gz`.

### Task 1.6: Inspect wheel contents

**Goal:** Confirm wheel contains only `src/almaapitk/**/*.py` plus standard `.dist-info/` metadata.

- [ ] **Step 1: List wheel contents**

Run:
```bash
unzip -l dist/almaapitk-0.3.0-py3-none-any.whl | tee /tmp/wheel-contents.txt
```

- [ ] **Step 2: Verify no unexpected paths**

Run:
```bash
unzip -l dist/almaapitk-0.3.0-py3-none-any.whl | awk 'NR>3 && NF>=4 {print $4}' | grep -vE '\.py$|^almaapitk-0\.3\.0\.dist-info/(METADATA|RECORD|WHEEL|entry_points\.txt|LICENSE|top_level\.txt)$|^$' || echo "OK: clean wheel"
```
Expected: `OK: clean wheel`.
On failure: HALT — investigate the unexpected file. Either (a) it slipped into `src/almaapitk/` (find and remove) or (b) Poetry config issue. Fix and re-run from Task 1.5.

### Task 1.7: Inspect sdist contents

**Goal:** Confirm sdist matches the §7.3 allowlist exactly.

- [ ] **Step 1: List sdist contents**

Run:
```bash
tar -tzf dist/almaapitk-0.3.0.tar.gz | sort | tee /tmp/sdist-contents.txt
```

- [ ] **Step 2: Verify allowed paths only**

Expected paths (inside the top-level `almaapitk-0.3.0/` directory):
- `almaapitk-0.3.0/PKG-INFO` (auto)
- `almaapitk-0.3.0/pyproject.toml`
- `almaapitk-0.3.0/README.md`
- `almaapitk-0.3.0/LICENSE`
- `almaapitk-0.3.0/docs/releases/0.3.0.md`
- `almaapitk-0.3.0/src/almaapitk/...` (recursive — all .py files)
- (Possibly directory entries ending with `/` — those are fine.)

Run:
```bash
tar -tzf dist/almaapitk-0.3.0.tar.gz | grep -vE '/$' | grep -vE '^almaapitk-0\.3\.0/(PKG-INFO|pyproject\.toml|README\.md|LICENSE|docs/releases/0\.3\.0\.md|src/almaapitk/.*\.py)$' || echo "OK: clean sdist"
```
Expected: `OK: clean sdist`.
On failure: HALT — output the unexpected paths. The most common cause: `exclude = ["**/*"]` may not interact with `include` the way we expect under Poetry 2.x. Fixes to try in order:
1. Replace `exclude = ["**/*"]` with explicit per-path exclusions for the offending paths.
2. Move the included files (README.md, LICENSE, docs/releases/0.3.0.md) under a top-level allow-pattern.
3. Consult Poetry 2.x docs on `[tool.poetry] include` and `exclude`.
After fixing, return to Task 1.5 (rebuild).

### Task 1.8: Run twine check

- [ ] **Step 1: Run**

Run:
```bash
pipx run twine check dist/*
```
Expected: two `PASSED` lines.
On failure: HALT — common causes are `long_description_content_type` missing (look at twine's output), README.md containing rST/HTML that doesn't render, or LICENSE not picked up. Fix and re-run from Task 1.5.

### Task 1.9: Create smoke test scripts

**Files:**
- Create: `scripts/post_publish/01_test_connection.py`
- Create: `scripts/post_publish/02_get_bib.py`
- Create: `scripts/post_publish/03_analytics_headers.py`
- Create: `scripts/post_publish/smoke_config.example.json`
- Create: `scripts/post_publish/.gitignore`

(`scripts/post_publish/` directory already exists from prerequisite work, but the files inside it are not yet created.)

- [ ] **Step 1: Write `scripts/post_publish/01_test_connection.py`**

Content:
```python
"""Smoke test 01: confirm SANDBOX auth works.

Reads ALMA_SB_API_KEY from environment.
"""
from almaapitk import AlmaAPIClient

client = AlmaAPIClient("SANDBOX")
client.test_connection()  # raises AlmaAPIError on failure; success is silent
print("OK: test_connection passed")
```

- [ ] **Step 2: Write `scripts/post_publish/02_get_bib.py`**

Content:
```python
"""Smoke test 02: fetch a known SANDBOX bib record.

Reads ALMA_SB_API_KEY and scripts/post_publish/smoke_config.json.
"""
import json
import pathlib
from almaapitk import AlmaAPIClient, BibliographicRecords

cfg = json.loads(pathlib.Path(__file__).parent.joinpath("smoke_config.json").read_text())
client = AlmaAPIClient("SANDBOX")
bibs = BibliographicRecords(client)
result = bibs.get_bib(cfg["sandbox_mms_id"])
assert result is not None, f"get_bib returned None for {cfg['sandbox_mms_id']}"
print(f"OK: got bib {cfg['sandbox_mms_id']}")
```

- [ ] **Step 3: Write `scripts/post_publish/03_analytics_headers.py`**

Content:
```python
"""Smoke test 03: fetch Alma Analytics report headers.

Important: Alma Analytics has a single shared DB accessible only via
PRODUCTION credentials. SANDBOX has no analytics endpoint. This script
therefore uses ALMA_PROD_API_KEY (not ALMA_SB_API_KEY).
"""
import json
import pathlib
from almaapitk import AlmaAPIClient, Analytics

cfg = json.loads(pathlib.Path(__file__).parent.joinpath("smoke_config.json").read_text())
client = AlmaAPIClient("PRODUCTION")
analytics = Analytics(client)
headers = analytics.get_report_headers(cfg["analytics_report_path"])
assert headers, "no headers returned"
print(f"OK: got {len(headers)} headers")
```

- [ ] **Step 4: Write `scripts/post_publish/smoke_config.example.json`**

Content:
```json
{
  "sandbox_mms_id": "REPLACE_WITH_KNOWN_SANDBOX_BIB_MMS_ID",
  "analytics_report_path": "REPLACE_WITH_URL_ENCODED_PROD_ANALYTICS_REPORT_PATH"
}
```

- [ ] **Step 5: Write `scripts/post_publish/.gitignore` (per-directory safety net)**

Content:
```
smoke_config.json
```

- [ ] **Step 6: Verify smoke_config.json (already in place locally) is gitignored**

Run:
```bash
git check-ignore -v scripts/post_publish/smoke_config.json
```
Expected: a line confirming the gitignore match.
On failure: HALT — do NOT commit. Investigate (project-root .gitignore plus per-dir .gitignore should both apply).

- [ ] **Step 7: Verify scripts execute against the source tree (sanity check before publish)**

Run:
```bash
poetry run python scripts/post_publish/01_test_connection.py
poetry run python scripts/post_publish/02_get_bib.py
poetry run python scripts/post_publish/03_analytics_headers.py
```
Expected: each prints exactly one `OK:` line.
On failure of script 01: SANDBOX connection issue or `ALMA_SB_API_KEY` not set.
On failure of script 02: MMS ID `990025559030204146` may not exist in SANDBOX or `BibliographicRecords.get_bib` returns something unexpected. Investigate; the smoke config value was confirmed by the user on 2026-04-27.
On failure of script 03: confirm `ALMA_PROD_API_KEY` is set and the analytics report path resolves on PROD.

- [ ] **Step 8: Commit**

Run:
```bash
git add scripts/post_publish/01_test_connection.py scripts/post_publish/02_get_bib.py scripts/post_publish/03_analytics_headers.py scripts/post_publish/smoke_config.example.json scripts/post_publish/.gitignore
git status --short  # verify smoke_config.json does NOT appear
git commit -m "Add post-publish smoke test scripts and example config"
```

After the commit: confirm via `git log -1 --stat` that `smoke_config.json` is NOT in the listing. If it is, HALT and reset.

---

## Phase 2 — TestPyPI dry run

### Task 2.1: Upload to TestPyPI

- [ ] **Step 1: Upload**

Run:
```bash
pipx run twine upload --repository testpypi dist/*
```
Expected: a "View at: https://test.pypi.org/project/almaapitk/0.3.0/" line.
On failure (`401`): token issue — HALT, user must check `[testpypi]` token in `~/.pypirc`.
On failure (`400` "File already exists"): TestPyPI version `0.3.0` was uploaded before. Either delete on test.pypi.org UI and re-upload, OR proceed assuming the existing one matches (less safe — prefer delete-and-reupload).
On failure (`400` README/metadata): HALT, return to Phase 1 fix.

### Task 2.2: HALT — Visual verification on TestPyPI

- [ ] **Step 1: Surface URL to user**

Surface message:
> Open https://test.pypi.org/project/almaapitk/0.3.0/ in a browser.
>
> Confirm:
> - README renders correctly (the "Project description" tab matches your `README.md`)
> - Classifiers appear in the sidebar (Beta, MIT, Python 3.12+)
> - Project URLs (Homepage, Repository, Issues, Documentation) are clickable and resolve to your GitHub repo
> - Version shows `0.3.0`
> - License is MIT
>
> Reply OK to proceed to Phase 2.3, or describe any defect.

- [ ] **Step 2: Wait for user OK.**
On user-reported defect: HALT phase. Defects on TestPyPI are recoverable (delete + re-upload after fixing).

### Task 2.3: Create fresh venv for TestPyPI smoke test

- [ ] **Step 1: Create venv**

Run:
```bash
rm -rf /tmp/almaapitk-smoke-testpypi
python3 -m venv /tmp/almaapitk-smoke-testpypi
```

- [ ] **Step 2: Install from TestPyPI (with extra index for real-PyPI deps)**

Run:
```bash
/tmp/almaapitk-smoke-testpypi/bin/pip install --quiet -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ almaapitk==0.3.0
```
Expected: `Successfully installed almaapitk-0.3.0` (and dependencies).

- [ ] **Step 3: Confirm version installed**

Run:
```bash
/tmp/almaapitk-smoke-testpypi/bin/pip show almaapitk | grep -E '^(Name|Version):'
```
Expected:
```
Name: almaapitk
Version: 0.3.0
```

### Task 2.4: Run smoke 01 against TestPyPI install

- [ ] **Step 1: Run**

Run:
```bash
/tmp/almaapitk-smoke-testpypi/bin/python scripts/post_publish/01_test_connection.py
```
Expected: `OK: test_connection passed`.
On failure: HALT phase. The published wheel cannot connect — packaging is wrong somehow.

### Task 2.5: Run smoke 02 against TestPyPI install

- [ ] **Step 1: Run**

Run:
```bash
/tmp/almaapitk-smoke-testpypi/bin/python scripts/post_publish/02_get_bib.py
```
Expected: `OK: got bib 990025559030204146`.

### Task 2.6: Run smoke 03 against TestPyPI install

- [ ] **Step 1: Run**

Run:
```bash
/tmp/almaapitk-smoke-testpypi/bin/python scripts/post_publish/03_analytics_headers.py
```
Expected: `OK: got N headers` where N is a positive integer.

### Task 2.7: Cleanup TestPyPI venv

- [ ] **Step 1: Remove**

Run:
```bash
rm -rf /tmp/almaapitk-smoke-testpypi
```

---

## Phase 3 — PyPI publish

### Task 3.1: Upload to PyPI

- [ ] **Step 1: Upload**

Run:
```bash
pipx run twine upload dist/*
```
(no `-r/--repository` flag → defaults to `[pypi]` from `~/.pypirc`)
Expected: a "View at: https://pypi.org/project/almaapitk/0.3.0/" line.
On failure (`401`): token issue — HALT, check `[pypi]` token in `~/.pypirc`.
On failure (`400` "File already exists"): IMPOSSIBLE on a brand-new project, but if it occurs HALT and investigate (probably a re-run after partial success).

### Task 3.2: HALT — Visual verification on PyPI

- [ ] **Step 1: Surface URL to user**

Surface message:
> Open https://pypi.org/project/almaapitk/0.3.0/ — confirm the same checklist as TestPyPI (README, classifiers, URLs, version 0.3.0, license MIT).
>
> **Important:** PyPI uploads are immutable. If you find a defect now, the only fix is publishing 0.3.1 — this 0.3.0 stays on the registry forever (you can yank it but the file persists).
>
> Reply OK to proceed, or describe any defect (which means we plan a 0.3.1 release as a separate task).

- [ ] **Step 2: Wait for user OK.**

### Task 3.3: Create second fresh venv for PyPI smoke test

- [ ] **Step 1: Create**

Run:
```bash
rm -rf /tmp/almaapitk-smoke-pypi
python3 -m venv /tmp/almaapitk-smoke-pypi
```

- [ ] **Step 2: Install from real PyPI**

Run:
```bash
/tmp/almaapitk-smoke-pypi/bin/pip install --quiet almaapitk==0.3.0
```
Expected: `Successfully installed almaapitk-0.3.0`.

- [ ] **Step 3: Confirm version**

Run:
```bash
/tmp/almaapitk-smoke-pypi/bin/pip show almaapitk | grep -E '^(Name|Version):'
```
Expected: `Name: almaapitk` and `Version: 0.3.0`.

### Task 3.4: Run smoke 01 against PyPI install

- [ ] **Step 1: Run**

Run:
```bash
/tmp/almaapitk-smoke-pypi/bin/python scripts/post_publish/01_test_connection.py
```
Expected: `OK: test_connection passed`.

### Task 3.5: Run smoke 02 against PyPI install

- [ ] **Step 1: Run**

Run:
```bash
/tmp/almaapitk-smoke-pypi/bin/python scripts/post_publish/02_get_bib.py
```
Expected: `OK: got bib 990025559030204146`.

### Task 3.6: Run smoke 03 against PyPI install

- [ ] **Step 1: Run**

Run:
```bash
/tmp/almaapitk-smoke-pypi/bin/python scripts/post_publish/03_analytics_headers.py
```
Expected: `OK: got N headers`.

### Task 3.7: Cleanup PyPI venv

- [ ] **Step 1: Remove**

Run:
```bash
rm -rf /tmp/almaapitk-smoke-pypi
```

---

## Phase 4 — Repo housekeeping

### Task 4.1: Tag and push v0.3.0

- [ ] **Step 1: Create annotated tag**

Run:
```bash
git tag -a v0.3.0 -m "almaapitk 0.3.0 — first PyPI release"
```

- [ ] **Step 2: Push tag**

Run:
```bash
git push origin v0.3.0
```
Expected: `* [new tag] v0.3.0 -> v0.3.0`.

### Task 4.2: Create GitHub Release

- [ ] **Step 1: Use the release notes file as body, mark as latest**

Run:
```bash
gh release create v0.3.0 --title "almaapitk 0.3.0" --notes-file docs/releases/0.3.0.md --latest
```
Expected: a URL pointing to the new release.
On failure: investigate `gh auth status`. If gh isn't authenticated, surface the URL and ask the user to create the release manually with `gh release create` after authenticating.

### Task 4.3: Verify README installation instructions

- [ ] **Step 1: Confirm README points users at PyPI**

Run:
```bash
grep -n "pip install almaapitk" README.md
```
Expected: at least one line. README was prepped on commit `17313cd` to already say `pip install almaapitk`.
On failure: edit README.md to add the instruction in the Installation section, then commit with message `Document pip install almaapitk in README`.

### Task 4.4: Write HOW_TO_RELEASE.md

**Files:**
- Create: `docs/releases/HOW_TO_RELEASE.md`

- [ ] **Step 1: Write**

Content:
```markdown
# How to release a new version of almaapitk (manual recipe)

This is the step-by-step recipe used for almaapitk 0.3.0 (2026-04-27). Use it for subsequent releases until the Trusted-Publisher / GitHub-Actions automation lands (Approach 3, separate spec).

## Prerequisites
- `~/.pypirc` populated with project-scoped tokens for `pypi` and `testpypi`, perms `0600`
- Working tree on `main`, clean, up to date with `origin/main`
- Both `ALMA_SB_API_KEY` and `ALMA_PROD_API_KEY` exported in the shell session
- `scripts/post_publish/smoke_config.json` present locally (gitignored)
- Tools available: `poetry`, `pipx`, `twine` (via `pipx run`), `gh`, `git`, `curl`

## Steps

1. Update `pyproject.toml` `version = "X.Y.Z"`; commit.
2. Write `docs/releases/X.Y.Z.md`; update the path in the `[tool.poetry] include = [...]` block to point at the new release notes file; commit.
3. `rm -rf dist/ && poetry build`
4. Inspect outputs:
   - `unzip -l dist/*.whl` — only `src/almaapitk/**/*.py` plus `*.dist-info/`
   - `tar -tzf dist/*.tar.gz` — only the explicit allowlist (PKG-INFO, pyproject.toml, README.md, LICENSE, docs/releases/X.Y.Z.md, src/almaapitk/**)
5. `pipx run twine check dist/*` — must `PASSED` both files.
6. `pipx run twine upload --repository testpypi dist/*`
7. Open `https://test.pypi.org/project/almaapitk/X.Y.Z/`, verify rendering and metadata.
8. In a fresh venv:
   ```bash
   python3 -m venv /tmp/smoke-testpypi
   /tmp/smoke-testpypi/bin/pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ almaapitk==X.Y.Z
   /tmp/smoke-testpypi/bin/python scripts/post_publish/01_test_connection.py
   /tmp/smoke-testpypi/bin/python scripts/post_publish/02_get_bib.py
   /tmp/smoke-testpypi/bin/python scripts/post_publish/03_analytics_headers.py
   ```
   All three must print `OK: ...`.
9. `pipx run twine upload dist/*` (real PyPI).
10. Open `https://pypi.org/project/almaapitk/X.Y.Z/`. Verify.
11. In another fresh venv:
    ```bash
    python3 -m venv /tmp/smoke-pypi
    /tmp/smoke-pypi/bin/pip install almaapitk==X.Y.Z
    # rerun the three smoke scripts from /tmp/smoke-pypi/bin/python
    ```
12. `git tag -a vX.Y.Z -m "almaapitk X.Y.Z" && git push origin vX.Y.Z`
13. `gh release create vX.Y.Z --title "almaapitk X.Y.Z" --notes-file docs/releases/X.Y.Z.md --latest`
14. Cleanup: `rm -rf /tmp/smoke-testpypi /tmp/smoke-pypi`.

## After the very first release (0.3.0, 2026-04-27)
The "Entire account" PyPI / TestPyPI tokens used for the very first publish were rotated to project-scoped `almaapitk` tokens immediately after Phase 3 succeeded (Task 4.5 of the original plan). Project-scoped tokens cannot be created until a project exists on the registry, hence the broad-scope tokens were temporary.

## Reference
- Initial design: `docs/superpowers/specs/2026-04-27-pypi-publishing-design.md`
- Initial plan: `docs/superpowers/plans/2026-04-27-pypi-publishing.md`
- Approach 3 (CI/CD automation, future): tracked as a follow-up GitHub issue.
```

- [ ] **Step 2: Commit**

Run:
```bash
git add docs/releases/HOW_TO_RELEASE.md
git commit -m "Document manual release recipe in HOW_TO_RELEASE.md"
git push origin main
```

### Task 4.5: HALT — Token rotation

- [ ] **Step 1: Surface to user**

Surface message:
> Now that `almaapitk` exists on PyPI and TestPyPI, please rotate both API tokens to project-scoped:
>
> 1. Visit https://pypi.org/manage/account/token/ — revoke the broad-scope token. Generate a new token scoped to project `almaapitk`. Open `~/.pypirc` and replace the password value in the `[pypi]` section with the new token (keep `username = __token__` unchanged, keep the `pypi-` prefix on the new token).
> 2. Repeat at https://test.pypi.org/manage/account/token/ for the `[testpypi]` section.
>
> Reply OK once both tokens are rotated.

- [ ] **Step 2: Wait for user OK.**

### Task 4.6: Open follow-up issue for Approach 3

- [ ] **Step 1: Write issue body to a tmp file**

Run:
```bash
cat > /tmp/approach3-issue.md <<'EOF'
Follow-up to the manual first publish (almaapitk 0.3.0, 2026-04-27).

Now that the project exists on PyPI, configure PyPI Trusted Publisher (OIDC) and add a `.github/workflows/release.yml` that builds and publishes on tag push. This eliminates manual twine commands and removes API tokens from `~/.pypirc` entirely.

## Scope (for the follow-up spec)

- Configure Trusted Publisher on https://pypi.org/manage/account/publishing/ for repo `hagaybar/AlmaAPITK`
- Add `.github/workflows/release.yml`: triggered on tag push matching `v*.*.*`, runs `poetry build`, then publishes via `pypa/gh-action-pypi-publish`
- Optional: TestPyPI publish on every push to `main` for continuous validation
- Internal consumer migration plan (per repo, lazily) — separate sub-task

## References

- Design spec: `docs/superpowers/specs/2026-04-27-pypi-publishing-design.md` (§13 names this as Phase 5 / out of scope of the manual publish)
- Manual recipe: `docs/releases/HOW_TO_RELEASE.md`
EOF
```

- [ ] **Step 2: Create the issue**

Run:
```bash
gh issue create --title "Approach 3: Trusted Publisher (OIDC) + GitHub Actions release workflow" --body-file /tmp/approach3-issue.md --label enhancement
```
Expected: a URL to the new issue.
On `unable to add label`: re-run without `--label enhancement` (the label may not exist in this repo); the issue still gets created.

- [ ] **Step 3: Cleanup**

Run:
```bash
rm /tmp/approach3-issue.md
```

---

## Self-Review Checklist (run by implementer at end of run)

Before claiming the run complete, verify each item:

- [ ] `https://pypi.org/project/almaapitk/0.3.0/` exists and renders cleanly
- [ ] `pip install almaapitk==0.3.0` in a fresh venv succeeds
- [ ] All three smoke scripts return `OK: ...` against the PyPI install
- [ ] `v0.3.0` tag pushed; GitHub Release exists with `docs/releases/0.3.0.md` body
- [ ] `docs/releases/HOW_TO_RELEASE.md` committed
- [ ] PyPI and TestPyPI tokens rotated to project-scoped (user-confirmed via Task 4.5)
- [ ] Follow-up issue for Approach 3 is open
- [ ] Working tree clean except `.a5c/cache/...` (untracked) and `dist/` (built artifacts)
- [ ] All audit-agreed fixes from Phase 0 landed
- [ ] No commits accidentally include `scripts/post_publish/smoke_config.json` (verify with `git log --all -- scripts/post_publish/smoke_config.json` returns empty)

---

## Out of scope (do NOT do in this run)

- Configure Trusted Publisher / OIDC (next spec)
- Create `.github/workflows/release.yml` (next spec)
- Migrate any internal consumer repo from git pin to PyPI install
- Bump version past 0.3.0
- Pre-existing AGENTS.md staleness (lines 11, 123 still reference `src/alma_logging/` instead of `src/almaapitk/alma_logging/`) — does not affect the published wheel under Option 2
- Merging `main` to `prod` (per project memory, manual user request only)
