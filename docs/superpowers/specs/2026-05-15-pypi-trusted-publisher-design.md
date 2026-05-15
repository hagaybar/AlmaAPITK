# Design: Approach 3 — Trusted Publisher (OIDC) + GitHub Actions Release Workflow

**Date:** 2026-05-15
**Status:** DRAFT — awaiting maintainer review and decision on open items
**Successor to:** `docs/superpowers/specs/2026-04-27-pypi-publishing-design.md` §13 (Phase 5)
**Tracked by:** GitHub issue #1
**Current package version:** `0.4.3` (as of this spec)

---

## 1. Context

`almaapitk 0.3.1` shipped to PyPI on 2026-04-27 via the manual recipe documented in
`docs/releases/HOW_TO_RELEASE.md`. The project is now at version `0.4.3` on `main`.

The manual recipe proved the publish pipeline works but has three friction points:

1. **Stored tokens.** Publishing requires `~/.pypirc` with project-scoped tokens.
   Tokens can drift, leak, or be accidentally revoked.
2. **Version-string drift.** During the 0.3.1 release, `src/almaapitk/__init__.py`
   held `__version__ = "0.2.0"` while `pyproject.toml` was already at `"0.3.0"` —
   for weeks. There was no CI guard to catch the divergence.
3. **Wheel contents not continuously verified.** The `exclude = ["**/*"]` footgun
   produced an empty wheel in an earlier draft. The current explicit denylist in
   `pyproject.toml` is correct, but it is only verified manually at release time.

Approach 3 automates the release, eliminates stored tokens, and adds CI guards that
catch packaging regressions on every push to `main`.

**Note on `__version__` drift (lesson learned → current state):** As of the 0.4.2/0.4.3
development cycle, `src/almaapitk/__init__.py` now derives `__version__` dynamically
via `importlib.metadata.version("almaapitk")` rather than a hardcoded string. This
eliminates the two-file-must-match footgun for the `__version__` attribute. The CI
guard described in §7.1 adapts accordingly: instead of diffing two text strings, it
builds the wheel, installs it in a fresh venv, and asserts the installed version
matches `pyproject.toml` — catching any build/metadata mismatch.

---

## 2. Goals

1. Remove `~/.pypirc` from the release workflow. All PyPI publishing happens via
   OIDC short-lived tokens — no stored API tokens, no rotation burden.
2. Automate the release: push tag `vX.Y.Z` → build → validate → publish, with no
   operator running local commands beyond creating the tag.
3. Add CI guards on `main` pushes that catch packaging regressions early.
4. Provide a TestPyPI dry-run path so packaging quality is continuously validated,
   not only at release time.
5. Run post-publish smoke tests as part of the automated release, replacing the
   manual smoke step in `HOW_TO_RELEASE.md`.

---

## 3. Non-goals

- Migrating internal consumer repositories from git pins to PyPI. Tracked in §10.
- `1.0.0` API stability commitment. Still Beta (`0.x`).
- Anaconda / conda-forge packaging.
- Implementing the workflow YAML, CI scripts, or any code changes. This is a
  **draft spec only** — implementation follows in a separate chunk after the
  maintainer approves and resolves the open items in §13.

---

## 4. Decisions to confirm with maintainer

| # | Question | Options | Recommendation |
|---|---|---|---|
| D1 | GitHub environment name(s) | Single `pypi` environment, or separate `pypi` (prod) and `testpypi` (dev) | Single `pypi` for release; separate `testpypi` for the continuous dry-run (§8) |
| D2 | Audit gate strictness | Non-blocking (findings surface as annotations only) vs. blocking (fails the build on new findings) | Non-blocking for all ruff/vulture; **blocking only for new High-severity bandit findings** (current codebase has 0 High findings, so this won't cause immediate breakage) |
| D3 | Internal-consumer migration timing | Coordinated cutover vs. per-repo lazy bump | Per-repo lazy bump on each repo's next planned dep-bump cycle (see §10) |
| D4 | Smoke config in CI | Write `smoke_config.json` on the fly from GitHub secrets vs. redesign smoke scripts to accept env vars | Write from secrets (zero code change to existing smoke scripts); refactor to env vars is recommended as a follow-up |
| D5 | TestPyPI dry-run cadence | Every push to `main` vs. only on pre-release tags (`v*.*.*rcN`) | Every push to `main` using a `.devN` version suffix (see §8.2) |

---

## 5. PyPI Trusted Publisher (OIDC) Setup

### 5.1 What is Trusted Publisher

PyPI Trusted Publisher uses OIDC (OpenID Connect) to let GitHub Actions obtain
short-lived upload tokens without any stored secret. The workflow presents a
GitHub-issued OIDC token to PyPI; PyPI validates it against the registered
publisher configuration and issues a temporary API token scoped to that upload.

No `~/.pypirc`, no GitHub secret containing a PyPI token, no rotation burden.

### 5.2 One-time manual setup (maintainer — web UI)

**This cannot be automated by an agent.** The maintainer must complete both registrations
before the first automated release.

#### 5.2.1 PyPI (real publishing)

1. Navigate to `https://pypi.org/manage/project/almaapitk/settings/publishing/`
   (the project already exists on PyPI, so use the project-level publisher page, not
   the pending-publisher page).
2. Click **"Add a new publisher"**.
3. Fill in the form:

   | Field | Value |
   |---|---|
   | Owner | `hagaybar` |
   | Repository name | `AlmaAPITK` |
   | Workflow filename | `release.yml` |
   | Environment name | `pypi` |

4. Click **Add**.

#### 5.2.2 TestPyPI (dry-run publishing)

Repeat on `https://test.pypi.org/manage/project/almaapitk/settings/publishing/`
(or the account-level pending-publisher page if the project does not yet exist on
TestPyPI):

   | Field | Value |
   |---|---|
   | Owner | `hagaybar` |
   | Repository name | `AlmaAPITK` |
   | Workflow filename | `ci.yml` |
   | Environment name | `testpypi` |

Skip this step if the TestPyPI dry-run feature (§8) is not being enabled immediately.
The `ci.yml` workflow can run in a `twine check`-only mode until the TestPyPI
registration is completed.

### 5.3 GitHub environments (maintainer — web UI)

Navigate to `https://github.com/hagaybar/AlmaAPITK/settings/environments`.

Create two environments:

| Environment | Purpose | Recommended protection rule |
|---|---|---|
| `pypi` | Tag-triggered real-PyPI publish | Require maintainer manual approval before deployment |
| `testpypi` | Continuous dry-run to TestPyPI | No approval gate (runs automatically on every `main` push) |

No secrets live in these environments. Trusted Publisher uses OIDC, not stored tokens.

### 5.4 GitHub workflow permission required

Any job that publishes via Trusted Publisher must declare:

```yaml
permissions:
  id-token: write   # required for OIDC token exchange
  contents: read    # minimum needed for checkout
```

Without `id-token: write`, the OIDC exchange fails with a 403.

---

## 6. `.github/workflows/release.yml` — Tag-Triggered Publish

### 6.1 Trigger

```yaml
on:
  push:
    tags:
      - 'v*.*.*'
```

Fires on any annotated or lightweight tag matching `vMAJOR.MINOR.PATCH`, including
pre-release tags like `v0.5.0rc1` (which also match the `v*.*.*` glob via the dots).

**Open question:** Should pre-release tags (`rc`, `a`, `b`) publish to TestPyPI
instead of real PyPI? A conditional on `contains(github.ref_name, 'rc')` can route
them. Deferring to maintainer (part of D1 resolution).

### 6.2 Job structure

```
build  ──►  validate  ──►  publish-pypi  ──►  post-publish-smoke
```

| Job | Purpose |
|---|---|
| `build` | checkout, install Poetry, `poetry build`, upload `dist/` as a workflow artifact |
| `validate` | download `dist/`, run `twine check`, run artifact-contents check, run version-string agreement check |
| `publish-pypi` | download `dist/`, call `pypa/gh-action-pypi-publish`; runs in environment `pypi` |
| `post-publish-smoke` | install from real PyPI in a fresh venv, run all three smoke scripts |

Separating `build` from `publish-pypi` ensures the artifact uploaded to PyPI is
byte-for-byte identical to what was validated.

### 6.3 Annotated YAML sketch

```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install Poetry
        run: pipx install poetry
      - name: Build wheel and sdist
        run: |
          rm -rf dist/
          poetry build
      - name: Upload dist artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  validate:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install twine
        run: pip install twine
      - name: twine check
        run: twine check dist/*
      - name: Artifact contents check
        run: |
          pip install dist/*.whl
          python scripts/ci/check_artifact_contents.py
      - name: Version-string agreement check
        run: python scripts/ci/check_version.py

  publish-pypi:
    needs: validate
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - name: Publish to PyPI via Trusted Publisher
        uses: pypa/gh-action-pypi-publish@release/v1

  post-publish-smoke:
    needs: publish-pypi
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Extract version from tag
        run: echo "VERSION=${GITHUB_REF_NAME#v}" >> $GITHUB_ENV
      - name: Write smoke_config.json from secrets
        run: |
          python -c "
          import json, os
          cfg = {
              'sandbox_mms_id': os.environ['SMOKE_SANDBOX_MMS_ID'],
              'analytics_report_path': os.environ['SMOKE_ANALYTICS_REPORT_PATH'],
          }
          with open('scripts/post_publish/smoke_config.json', 'w') as f:
              json.dump(cfg, f)
          "
        env:
          SMOKE_SANDBOX_MMS_ID: ${{ secrets.SMOKE_SANDBOX_MMS_ID }}
          SMOKE_ANALYTICS_REPORT_PATH: ${{ secrets.SMOKE_ANALYTICS_REPORT_PATH }}
      - name: Wait for PyPI propagation
        run: sleep 60
      - name: Create fresh smoke venv and install from PyPI
        run: |
          python -m venv /tmp/smoke-venv
          /tmp/smoke-venv/bin/pip install almaapitk==${{ env.VERSION }}
      - name: Smoke 01 — SANDBOX connection
        run: /tmp/smoke-venv/bin/python scripts/post_publish/01_test_connection.py
        env:
          ALMA_SB_API_KEY: ${{ secrets.ALMA_SB_API_KEY }}
      - name: Smoke 02 — SANDBOX bib fetch
        run: /tmp/smoke-venv/bin/python scripts/post_publish/02_get_bib.py
        env:
          ALMA_SB_API_KEY: ${{ secrets.ALMA_SB_API_KEY }}
      - name: Smoke 03 — PROD Analytics headers
        run: /tmp/smoke-venv/bin/python scripts/post_publish/03_analytics_headers.py
        env:
          ALMA_PROD_API_KEY: ${{ secrets.ALMA_PROD_API_KEY }}
      - name: Cleanup
        if: always()
        run: rm -rf /tmp/smoke-venv scripts/post_publish/smoke_config.json
```

### 6.4 Manual prerequisites (maintainer — one-time before first automated release)

The following GitHub Actions secrets must be set at
`https://github.com/hagaybar/AlmaAPITK/settings/secrets/actions`:

| Secret name | Description | Required by |
|---|---|---|
| `ALMA_SB_API_KEY` | Sandbox Alma API key | Smoke 01, 02 |
| `ALMA_PROD_API_KEY` | Production Alma API key | Smoke 03 (Analytics is PROD-only) |
| `SMOKE_SANDBOX_MMS_ID` | A known bib MMS ID in the SANDBOX environment | Smoke 02 |
| `SMOKE_ANALYTICS_REPORT_PATH` | URL-encoded analytics report path (PROD only) | Smoke 03 |

`smoke_config.json` remains gitignored. The workflow generates it on the fly from
the secrets above and deletes it in the `Cleanup` step. The maintainer does **not**
need a local `smoke_config.json` to trigger an automated release.

---

## 7. CI Guards — Every Push to `main`

These guards run in `.github/workflows/ci.yml` on every push to `main` and on
pull requests targeting `main`. They are designed to catch regressions before
the release tag is pushed.

### 7.1 Version-string agreement check

**Lesson baked in:** `__version__` was `"0.2.0"` in `__init__.py` while
`pyproject.toml` was at `"0.3.0"` for weeks — no CI caught it.

**Current state:** `__init__.py` now resolves `__version__` from
`importlib.metadata.version("almaapitk")`, so there is no hardcoded string to
drift. The guard shifts to verifying the **installed wheel** reports what `pyproject.toml`
declares, which catches mismatches caused by build configuration bugs or
packaging toolchain quirks.

Proposed script (`scripts/ci/check_version.py`):

```python
"""CI guard: installed almaapitk.__version__ must match pyproject.toml version."""
import sys
import tomllib
import subprocess

with open("pyproject.toml", "rb") as f:
    expected = tomllib.load(f)["project"]["version"]

result = subprocess.run(
    [sys.executable, "-c", "import almaapitk; print(almaapitk.__version__)"],
    capture_output=True, text=True, check=False
)
actual = result.stdout.strip()

if result.returncode != 0 or actual != expected:
    print(f"FAIL: installed __version__ is {actual!r}; "
          f"pyproject.toml declares {expected!r}")
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    sys.exit(1)

print(f"OK: __version__ == {expected!r}")
```

This script runs **after** `pip install dist/*.whl` in the CI step — it tests the
installed artifact, not the source tree.

### 7.2 Wheel and sdist contents check

**Lesson baked in:** `exclude = ["**/*"]` produced an empty wheel in an earlier
draft (Poetry applied it after `packages`, leaving nothing). The current per-directory
denylist in `pyproject.toml` is correct; CI should verify it on every push.

The `validate` job in `release.yml` already runs this check for release builds. On
`main` pushes (CI workflow), the same check runs against a fresh `poetry build` so
that regressions are caught days or weeks before any release tag is pushed.

Proposed script (`scripts/ci/check_artifact_contents.py`):

```python
"""CI guard: wheel and sdist must contain exactly the expected file sets."""
import sys
import glob
import zipfile
import tarfile
import re
import pathlib

def check_wheel(path: str) -> list[str]:
    """Return a list of unexpected entries in the wheel."""
    unexpected = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if re.match(r'^almaapitk-[\d.]+\.dist-info/', name):
                continue  # wheel metadata, always expected
            if name.endswith('/'):
                continue  # directory entries
            if not name.endswith('.py'):
                unexpected.append(f"wheel: unexpected non-.py file: {name}")
    return unexpected

def check_sdist(path: str) -> list[str]:
    """Return a list of unexpected entries in the sdist."""
    unexpected = []
    # Strip the top-level directory prefix (almaapitk-X.Y.Z/)
    prefix_re = re.compile(r'^almaapitk-[\d.]+/')
    allowed_re = re.compile(
        r'^(PKG-INFO|pyproject\.toml|README\.md|CHANGELOG\.md|LICENSE'
        r'|docs/releases/[^/]+\.md'
        r'|src/almaapitk/.*\.py'
        r'|src/almaapitk/.*)$'
    )
    with tarfile.open(path, 'r:gz') as tf:
        for member in tf.getmembers():
            name = prefix_re.sub('', member.name)
            if not name or name.endswith('/'):
                continue  # directory entries
            if not allowed_re.match(name):
                unexpected.append(f"sdist: unexpected file: {name}")
    return unexpected

errors = []

wheels = glob.glob("dist/*.whl")
sdists = glob.glob("dist/*.tar.gz")

if not wheels:
    errors.append("No wheel found in dist/")
if not sdists:
    errors.append("No sdist found in dist/")

for w in wheels:
    errors.extend(check_wheel(w))
for s in sdists:
    errors.extend(check_sdist(s))

if errors:
    print("FAIL: artifact contents check")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"OK: wheel and sdist contents look clean ({len(wheels)} wheel, {len(sdists)} sdist)")
```

### 7.3 Audit gate (non-blocking)

**Lesson baked in:** The pre-0.3.1 manual audit (ruff + bandit + vulture + grep)
found two real bugs worth fixing before the first public release. Running the same
tools in CI surfaces new findings during PRs before they accumulate.

The audit job uses `continue-on-error: true` so it never blocks a merge. Its
output appears in the Actions summary as a workflow annotation visible during PR
review. Per D2, only new High-severity `bandit` findings should be considered for
making this gate blocking (current codebase: 0 High-severity findings).

```yaml
  audit:
    runs-on: ubuntu-latest
    continue-on-error: true   # non-blocking
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install audit tools
        run: pip install ruff bandit vulture
      - name: ruff
        run: ruff check src/almaapitk/ || true
      - name: bandit
        run: bandit -r src/almaapitk/ -ll || true
      - name: vulture
        run: vulture src/almaapitk/ --min-confidence 70 || true
      - name: grep — stray print() calls
        run: |
          grep -rEn '^[^#]*\bprint\(' src/almaapitk/ || echo "(none)"
      - name: grep — TODO/FIXME/XXX/HACK
        run: |
          grep -rEn 'TODO|FIXME|XXX|HACK' src/almaapitk/ || echo "(none)"
```

Counts from the 2026-04-27 manual audit (for baseline comparison in future runs):
- ruff: 47 findings (30× F541, 8× F401, 6× E722, 2× F841, 1× F811)
- bandit: 14 Medium (6× B113, 8× B314), 0 High
- vulture: 2 findings (100%: `max_workers` unused; 90%: unused `timedelta` import)
- print(): 272 across 7 files
- TODO/FIXME: 16 in `alma_logging/`

---

## 8. TestPyPI Dry-Run on Every `main` Push (Optional)

### 8.1 Purpose

Catch packaging regressions early. Every push to `main` builds a `.devN` artifact,
validates it with `twine check`, uploads it to TestPyPI, and verifies install.
This means defects appear days or weeks before the release tag is pushed, when
they are cheapest to fix.

### 8.2 Dev-version suffix strategy

TestPyPI prohibits re-uploading the same version string even after deletion. To
avoid conflicts, the workflow appends a `devN` suffix using the UTC date and short
commit SHA:

```bash
BASE_VERSION=$(poetry version --short)
DEV_VERSION="${BASE_VERSION}.dev$(date -u +%Y%m%d)$(git rev-parse --short HEAD)"
poetry version "$DEV_VERSION"
poetry build
```

The version string mutation is local to the runner and is **never committed**.

### 8.3 Cleanup

After the dry-run job, the `dist/` directory on the runner is removed. Dev releases
accumulate on TestPyPI but are harmless — TestPyPI is a throwaway registry. The
maintainer can periodically clean stale dev releases via the TestPyPI web UI.

### 8.4 TestPyPI Trusted Publisher requirement

The dry-run workflow also publishes via OIDC (no stored token). This requires the
separate TestPyPI Trusted Publisher registration described in §5.2.2.

Until that registration is in place, the dry-run job can run in validation-only
mode (build + `twine check` only, no upload), which still catches most regressions.

### 8.5 Sketch of dry-run steps in `ci.yml`

```yaml
  testpypi-dry-run:
    runs-on: ubuntu-latest
    environment: testpypi
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install Poetry
        run: pipx install poetry
      - name: Build with dev suffix
        run: |
          BASE=$(poetry version --short)
          DEV="${BASE}.dev$(date -u +%Y%m%d)$(git rev-parse --short HEAD)"
          poetry version "$DEV"
          rm -rf dist/ && poetry build
      - name: twine check
        run: pip install twine && twine check dist/*
      - name: Upload to TestPyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
      - name: Cleanup dist
        if: always()
        run: rm -rf dist/
```

---

## 9. Post-Publish Smoke Tests

### 9.1 Current state

Three smoke scripts exist at `scripts/post_publish/`:

| Script | Env key | Needs config | Notes |
|---|---|---|---|
| `01_test_connection.py` | `ALMA_SB_API_KEY` | No | SANDBOX auth check |
| `02_get_bib.py` | `ALMA_SB_API_KEY` | `sandbox_mms_id` | SANDBOX bib fetch |
| `03_analytics_headers.py` | `ALMA_PROD_API_KEY` | `analytics_report_path` | **PROD-only** — Alma Analytics has no SANDBOX endpoint |

All three currently read identifiers from `smoke_config.json`, which is gitignored.

### 9.2 Config injection for CI

The release workflow (§6.3) writes `smoke_config.json` on the fly from GitHub
secrets (`SMOKE_SANDBOX_MMS_ID`, `SMOKE_ANALYTICS_REPORT_PATH`) and deletes it
in the cleanup step. This requires zero changes to the existing smoke scripts.

A cleaner long-term approach (D4) is to refactor the smoke scripts to check env
vars first, falling back to `smoke_config.json` for local runs:

```python
import os, json, pathlib

def load_config() -> dict:
    sandbox_mms_id = os.environ.get("SMOKE_SANDBOX_MMS_ID")
    analytics_path = os.environ.get("SMOKE_ANALYTICS_REPORT_PATH")
    if sandbox_mms_id and analytics_path:
        return {"sandbox_mms_id": sandbox_mms_id,
                "analytics_report_path": analytics_path}
    config_path = pathlib.Path(__file__).parent / "smoke_config.json"
    return json.loads(config_path.read_text())
```

This refactor is recommended for the implementation chunk but is not required to
unblock the initial Approach 3 rollout.

### 9.3 PROD key for smoke 03

`ALMA_PROD_API_KEY` must be set as a GitHub Actions secret. Alma Analytics is
backed by a single shared database accessible only via PRODUCTION credentials —
the SANDBOX environment has no analytics endpoint. This is the same constraint as
the manual recipe (§5 of `HOW_TO_RELEASE.md`), now encoded in the workflow.

### 9.4 Failure handling after publish

If a smoke script fails after the PyPI upload, the package is already live and
cannot be deleted (PyPI is immutable; yanking hides but does not remove). The
operator response path:

1. Investigate the failure (infrastructure issue vs. genuine regression).
2. If genuine regression: yank the defective version on PyPI (web UI →
   "Yank" button, or `pip` equivalent), then fix on `main` and push a
   `vX.Y.(Z+1)` tag. The automated workflow handles the re-release.
3. If infrastructure issue (expired key, transient API outage): the package
   is still usable. Decide whether to yank based on whether the smoke failure
   reflects a real user-facing problem.

See §11 for the general version-bump-on-defect path.

---

## 10. Internal Consumer Migration

This section is **informational only**; migration is not in scope for this spec.

### 10.1 Current consumers

The following repositories currently pin `almaapitk` via git URL or tag:

| Repository | Notes |
|---|---|
| `Alma-Acquisitions-Automation` | Production; active |
| `Alma-Digital-Upload` | Development |
| `Alma-RS-lending-request-automation` | Production |
| `Alma-update-expired-users-emails` | Production |
| `Update_Alma_Digital_Collections` | Status unclear |
| `Fetch_Alma_Analytics_Reports` | Status unclear |

### 10.2 Migration target

Replace each git-pin dependency with a semver range from PyPI:

```toml
# Before (git pin — Poetry style)
almaapitk = {git = "https://github.com/hagaybar/AlmaAPITK", tag = "v0.4.3"}

# After (PyPI — Poetry style)
almaapitk = ">=0.4.3,<1.0.0"
```

For `requirements.txt`-based repos:
```
# Before
almaapitk @ git+https://github.com/hagaybar/AlmaAPITK@v0.4.3

# After
almaapitk>=0.4.3,<1.0.0
```

### 10.3 Timing options

| Option | Description | Trade-off |
|---|---|---|
| **A. Per-repo lazy bump** | Each repo migrates on its next planned dependency-bump cycle | Low disruption; migration can span months or never happen for dormant repos |
| **B. Coordinated cutover** | All repos migrate in a single planned sprint | Clean state sooner; higher short-term effort |
| **C. Mixed** | Active/production repos migrate first; dormant repos migrate lazily | Pragmatic balance |

**Recommendation:** Option C. `Alma-Acquisitions-Automation` and
`Alma-RS-lending-request-automation` are production-active; migrate them first on
their next dep-bump. Dormant repos migrate lazily or not at all.

No specific timeline commitment is made here — that belongs in each consumer
repo's backlog.

### 10.4 Validation per repo after migration

1. `poetry install` (or `pip install -r requirements.txt`) resolves `almaapitk`
   from PyPI, not GitHub. Confirm with `pip show almaapitk`.
2. Remove the `git+https://` or `{git = ...}` stanza from the dependency config.
3. Run the repo's own test suite or smoke scripts.
4. Check that `almaapitk.__version__` matches the expected release.

---

## 11. Token Migration and `~/.pypirc` Cleanup

Once Trusted Publisher is active and the **first automated release has succeeded**:

1. **Revoke the project-scoped PyPI token.** On
   `https://pypi.org/manage/account/tokens/`: revoke the `almaapitk`-scoped token
   that was created after the 0.3.1 manual release.
2. **Revoke the project-scoped TestPyPI token.** On
   `https://test.pypi.org/manage/account/tokens/`.
3. **Remove `~/.pypirc`** (or at minimum remove the `[pypi]` and `[testpypi]`
   sections). With Trusted Publisher active, `~/.pypirc` is unused for this
   project; its presence is a residual exposure.
4. **Smoke the local path.** Run `poetry build && python -m twine upload --repository pypi dist/*`
   locally to confirm it fails with a credentials error, proving the local upload
   route is disabled and automated publishing is the only active path.

**Timing:** Token revocation should happen within 24 hours of the first successful
automated release. Stored tokens are a revocable risk; do not defer.

---

## 12. Version-Bump-on-Defect Path

**Lesson baked in:** During the 0.3.1 release, a defect was found at the TestPyPI
gate. Because PyPI prohibits re-uploading the same version string even after
deletion, the fix required bumping to `0.3.1` (skipping `0.3.0` on real PyPI
entirely).

Under Approach 3, the automated workflow structurally mitigates this by running the
full `validate` job — `twine check`, artifact contents, version-string agreement —
**before** any upload. Most regressions are caught at the `validate` gate; the
operator simply fixes and re-tags.

For the residual case where a defect slips past `validate` and is caught by the
post-publish smoke tests:

1. The package is already live on PyPI (immutable). Yank it on the web UI if the
   defect actively misleads users.
2. Fix the regression on `main`.
3. Bump `pyproject.toml` to `X.Y.(Z+1)`.
4. Push a new tag `vX.Y.(Z+1)`. The automated workflow handles the rest.

There is no mechanism in this design to "re-try the same version" — that is
an intentional constraint of PyPI's immutability model, not a gap in this spec.

---

## 13. Open Items and Implementation Pointers

These must be resolved before implementation begins (marked **blocking**) or
during the implementation chunk (marked **in-impl**).

| # | Item | Priority | Notes |
|---|---|---|---|
| O1 | Submit Trusted Publisher form on PyPI web UI | **Blocking** | Maintainer must do this; agent cannot access the PyPI web UI (§5.2.1) |
| O2 | Create `pypi` (and optionally `testpypi`) GitHub environments | **Blocking** | Maintainer web UI action (§5.3) |
| O3 | Decide D1: single vs. dual environments | **Blocking** | Affects workflow YAML structure |
| O4 | Decide D2: audit gate strictness | Before impl | Affects `ci.yml` `continue-on-error` setting |
| O5 | Set four GitHub Actions secrets (§6.4) | **Blocking** | Must be set before first automated release; maintainer only |
| O6 | Implement `scripts/ci/check_version.py` | In-impl | Spec in §7.1; straightforward |
| O7 | Implement `scripts/ci/check_artifact_contents.py` | In-impl | Spec in §7.2; straightforward |
| O8 | Register TestPyPI Trusted Publisher (§5.2.2) | Optional | Only needed if continuous dry-run is enabled; can be deferred |
| O9 | Decide D4: smoke-script config injection approach | In-impl | File-write-from-secrets is safe for v1; env-var refactor is cleaner long-term |
| O10 | Decide D5: TestPyPI dry-run cadence | In-impl | Every-push vs. pre-release-tags only |
| O11 | Verify `CHANGELOG.md` exists in repo root | In-impl | `pyproject.toml` includes it in the sdist `include` list and the `Changelog` URL points to it; it must exist |

---

## 14. Success Criteria

This Approach 3 design is "done" when **all** of the following hold:

1. A tag push `vX.Y.Z` triggers the release workflow without operator running any
   local commands beyond `git tag` and `git push`.
2. The release workflow uses OIDC (no stored API token in `~/.pypirc` or GitHub
   secrets for the upload itself).
3. The `validate` job catches a wheel with unexpected file inclusions and fails
   before any upload.
4. The `validate` job catches a version-string mismatch (pyproject.toml vs. installed
   wheel) and fails before any upload.
5. The post-publish smoke job verifies all three smoke scripts against the just-published
   artifact in a fresh venv.
6. The audit job surfaces ruff/bandit/vulture findings on every push to `main` as
   PR annotations, without blocking merges.
7. The old project-scoped PyPI and TestPyPI tokens have been revoked; `~/.pypirc`
   no longer contains upload credentials for `almaapitk`.

---

## 15. References

- Predecessor spec: `docs/superpowers/specs/2026-04-27-pypi-publishing-design.md`
  (§13 names this spec as "Phase 5 — out of scope")
- Manual release recipe: `docs/releases/HOW_TO_RELEASE.md`
- Audit findings: `docs/superpowers/specs/2026-04-27-pypi-publishing-audit-findings.md`
- Publishing plan (executed): `docs/superpowers/plans/2026-04-27-pypi-publishing.md`
- GitHub issue: #1
- PyPI Trusted Publisher documentation: https://docs.pypi.org/trusted-publishers/
- `pypa/gh-action-pypi-publish` action: https://github.com/pypa/gh-action-pypi-publish
- Poetry `version` command: https://python-poetry.org/docs/cli/#version
