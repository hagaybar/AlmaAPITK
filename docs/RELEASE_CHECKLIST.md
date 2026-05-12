# Release Checklist (binding)

This checklist is the gate for every `almaapitk` release to PyPI. Every box must be checked before `twine upload` to real PyPI. It exists because the `0.4.x` cycle burned four version bumps (`0.4.0` → `0.4.1` → `0.4.2` → `0.4.3`) on gaps the validation didn't catch.

Each section below has a one-line **what** and **why**. If a box can't be checked, stop — don't try to bump your way out.

---

## Phase A — Pre-flight (before touching anything)

- [ ] **On `main`, clean tree, synced with `origin/main`.** `git checkout main && git pull && git status -sb && git diff --quiet`. The remote and local tip must match.
- [ ] **All chunks intended for this release are merged.** `scripts/agentic/chunks list` shows no in-flight chunks whose merge was promised in the changelog.
- [ ] **No critical open issues block the release.** `gh issue list --label "priority:high" --state open --search "in:title release"` returns nothing fresh.
- [ ] **`ALMA_PROD_API_KEY` is unset.** R8 enforcement: `env | grep ALMA_PROD` returns nothing.

---

## Phase B — Open the release branch

- [ ] **Branch created from main.** `git checkout -b release/<version>`. Version is whatever's *next* — bump by patch/minor/major per SemVer; check the current value with `grep '^version' pyproject.toml`.

---

## Phase C — Documentation completeness (the layer that caused 0.4.1 + 0.4.2 bumps)

Each domain class shipped in this release must appear in **every** discoverability surface, not just the deep reference docs.

- [ ] **`README.md`** — every domain class listed in `src/almaapitk/__init__.py` `__all__` is in the README's "Domain Classes" bullet list. Run `grep -oE 'Acquisitions|Admin|Analytics|BibliographicRecords|Configuration|ResourceSharing|Users' src/almaapitk/__init__.py` against `grep -oE 'Acquisitions|Admin|Analytics|BibliographicRecords|Configuration|ResourceSharing|Users' README.md` to compare.
- [ ] **`docs/index.md`** — domain table has one row per domain class, in alphabetical order. Each row has a "View Guide" link to `domains/<name>.md` (or a fallback to api-reference.md if the per-domain guide doesn't exist yet).
- [ ] **`docs/getting-started.md`** — the import example near the bottom lists every domain class in alphabetical order.
- [ ] **`docs/api-reference.md`** — Version header at the top matches `pyproject.toml`. New methods on existing classes are documented. New error subclasses (if any) are in the Exceptions section.
- [ ] **`docs/domains/<new-domain>.md`** — for every domain class that's *new* in this release, a dedicated guide exists matching the style of `docs/domains/admin.md` (sections: Overview, Initialization, Methods Reference, Common Workflows, Best Practices, Alma API Reference).
- [ ] **Per-method docstrings present in source.** Public methods in `src/almaapitk/domains/*.py` have a Google-style docstring with Args, Returns, Raises.

**Why this section is here:** `0.4.1` and `0.4.2` were caused by exactly this gap. Per-domain reference docs and api-reference.md got the new methods; the top-level surfaces (README/index/getting-started) didn't, so the new domain (Configuration) was invisible to anyone landing on the PyPI project page.

---

## Phase D — CHANGELOG

- [ ] **CHANGELOG includes every user-visible change** since the previous release. Cross-reference: `git log v<prev>..HEAD --oneline | grep -E '^[0-9a-f]+ (feat|fix|perf)'` — every line should map to a CHANGELOG bullet, or be intentionally excluded as internal infrastructure.
- [ ] **Behavior changes are explicitly called out.** Examples: default timeouts, exception class lists, request-format changes. These are easy to forget because they're not "new methods".
- [ ] **`### Removed` section accounts for every removed public symbol.** Even if the symbol was non-functional (like `BibliographicRecords.search_records` in `0.4.0`), it must be documented as removed.
- [ ] **Section heading renamed.** `## [Unreleased]` → `## [<version>] — <YYYY-MM-DD>`. Insert a fresh empty `## [Unreleased]` above.
- [ ] **Link references at the bottom updated.** `[Unreleased]: .../compare/v<version>...HEAD` and a new `[<version>]: .../releases/tag/v<version>` entry.

---

## Phase E — Version bump (the layer that caused the 0.4.2 yank)

- [ ] **`pyproject.toml` is the *only* place a version literal lives.** Verify with `grep -rn 'version *= *"[0-9]' src/almaapitk/` and `grep -rn '__version__ *= *"[0-9]' src/almaapitk/`. **If either returns a literal version string, fix it before continuing — use `importlib.metadata.version("almaapitk")` instead.**
- [ ] **`pyproject.toml` version bumped** to the new value. Anchored sed: `sed -i 's/^version = "<old>"$/version = "<new>"/' pyproject.toml`. The `^version =` anchor avoids matching `docs/releases/<old>.md` paths in the include list.
- [ ] **`docs/api-reference.md` Version header bumped** if present.
- [ ] **No hardcoded fallback equals the new version.** If `src/almaapitk/__init__.py` has a `PackageNotFoundError` fallback for `__version__`, it should be `"0.0.0+unknown"` or similar — never a real-looking version string.

---

## Phase F — Local validation suite

Run from `release/<version>` after Phase C–E commits. Any failure stops the release.

- [ ] `poetry install --sync` — refreshes the venv against the bumped `pyproject.toml`. Without this, `importlib.metadata.version("almaapitk")` will still report the old version.
- [ ] `poetry run python scripts/smoke_import.py` passes.
- [ ] `poetry run pytest tests/test_public_api_contract.py -v` passes.
- [ ] `poetry run pytest tests/test_version.py -v` passes. **This is the version-drift guard.** If it fails, Phase E was incomplete.
- [ ] `poetry run pytest tests/unit/ tests/logging/ tests/integration/client/ tests/meta/ tests/agentic/ -q` — 0 failures, 0 errors (not just "skipped"). `tests/meta/` is the structural-guard tier (no-print, no-hardcoded-`__version__`, docs vs `__all__` consistency, Version-heading vs `pyproject.toml`) — it catches Phase-C / Phase-E drift before TestPyPI does (issue #131). If pre-existing broken-test files surface, move them out of `tests/` (e.g., to `scripts/investigations/`) and document in CHANGELOG.
- [ ] `scripts/agentic/chunks regression-smoke` — every chunk's SANDBOX smoke tests pass. Acceptable exception: chunks documented as environmentally blocked at the time of the release (file a follow-up issue, don't block on tenant-config issues).

---

## Phase G — Build + inspect

- [ ] `rm -rf dist/ && poetry build` — produces `dist/almaapitk-<version>-py3-none-any.whl` and `dist/almaapitk-<version>.tar.gz`. The filename version must match `pyproject.toml`.
- [ ] **Wheel filename matches `pyproject.toml`.** `ls dist/` should show only the just-bumped version. If you see two versions, you have a stale `dist/` — re-run the `rm -rf`.
- [ ] **Wheel contents verified.** `unzip -l dist/almaapitk-<version>-py3-none-any.whl` must show only `almaapitk/` package code + `almaapitk-<version>.dist-info/`. No `tests/`, `scripts/`, `docs/` (except inside dist-info), `.a5c/`, `logs/`, `config/`, `CLAUDE.md`, `AGENTS.md`.

---

## Phase H — TestPyPI dry-run

- [ ] **Upload to TestPyPI.** `poetry run twine upload --repository testpypi dist/almaapitk-<version>*`. (Twine reads `~/.pypirc`; poetry does not. The `--repository testpypi` line requires `repositories.testpypi.url = "https://test.pypi.org/legacy/"` configured in poetry — see `poetry config repositories.testpypi`.)
- [ ] **Wait for TestPyPI indexing** — 90–180 seconds. Don't trust the immediate-publish "view at" URL; pip won't see the new version for a minute or two.
- [ ] **Install from TestPyPI into a throwaway venv.** Standard pattern: `python3.12 -m venv $(mktemp -d)/venv && . .../bin/activate && pip install --upgrade pip && pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ almaapitk==<version>`. The `--extra-index-url https://pypi.org/simple/` is required because TestPyPI doesn't mirror runtime deps.
- [ ] **Smoke import reads `__version__` *dynamically*.** **The smoke command must NOT have a hardcoded version string in its `print` call** — that's the line that masked the `0.4.2` bug. Use:

  ```python
  python -c "
  import almaapitk
  from importlib.metadata import version
  expected = '<EXPECTED_VERSION>'
  attr = almaapitk.__version__
  meta = version('almaapitk')
  assert attr == meta == expected, f'version mismatch: attr={attr!r} meta={meta!r} expected={expected!r}'
  # exercise every public symbol from __init__.py __all__
  from almaapitk import (AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError, AlmaAuthenticationError, AlmaRateLimitError, AlmaServerError, AlmaResourceNotFoundError, AlmaDuplicateInvoiceError, AlmaInvalidPolModeError, Admin, Users, BibliographicRecords, Acquisitions, ResourceSharing, Analytics, Configuration, TSVGenerator, CitationMetadataError)
  print(f'TESTPYPI SMOKE OK: {attr}')
  "
  ```

  Update the imports as new exports land.

- [ ] **README renders correctly on TestPyPI.** Open `https://test.pypi.org/project/almaapitk/<version>/` in a browser. The README markdown must render. Tables, code blocks, headings all visible. Any rendering glitch (e.g., raw `[link]` text) means PyPI rejected the markdown — fix before real publish.
- [ ] **All `[project.urls]` links visible.** Homepage, Repository, Documentation, Issues, Changelog. Click each one in the browser.

---

## Phase I — Release PR

- [ ] **Push the release branch.** `git push -u origin release/<version>`.
- [ ] **Open PR into `main`** with `--title "Release <version>"` and a body covering: summary, version, post-merge actions, TestPyPI link.
- [ ] **Squash-merge with branch deletion.** `gh pr merge <num> --squash --delete-branch`.
- [ ] **Switch to main and pull.** `git checkout main && git pull`. Verify the squash commit is the new tip.

---

## Phase J — Real PyPI publish (irreversible)

- [ ] **Rebuild on main** to confirm artifacts match the merged code. `rm -rf dist/ && poetry build`. Filename version should match `pyproject.toml`.
- [ ] **`twine upload dist/almaapitk-<version>*`** — to real PyPI. **Once this returns success, the version cannot be re-uploaded under any circumstances.** Yanking is possible but only discourages new installs; pinned consumers still get the artifact.
- [ ] **Verify on `https://pypi.org/project/almaapitk/<version>/`** — version is listed, README renders.

---

## Phase K — Tag + GitHub Release

- [ ] **Tag the merged commit.** `git tag -a v<version> -m "Release <version>" && git push origin v<version>`.
- [ ] **Extract the CHANGELOG excerpt** to a file: `awk '/^## \[<version>\]/,/^## \[<prev>\]/' CHANGELOG.md | head -n -1 > /tmp/release-<version>-notes.md`. Verify it's non-empty and starts with the version heading.
- [ ] **Create the GitHub Release.** `gh release create v<version> --title "v<version>" --notes-file /tmp/release-<version>-notes.md`.

---

## Phase L — Post-release smoke + follow-ups

- [ ] **Fresh-venv install from real PyPI** with strict `__version__` check (same template as Phase H). Wait 60–180 seconds for PyPI indexing.
- [ ] **File follow-up issues** for any items you punted: SANDBOX fixtures that need refresh, additional doc cleanup, CI workflow tasks, etc.
- [ ] **Update memory if you learned something new** that future-releases-you should remember.

---

## Yank protocol (only if something broke through to PyPI)

PyPI does not allow deleting a version. Yank is the strongest discouragement:

1. **Web UI only.** No CLI. Go to `https://pypi.org/manage/project/almaapitk/release/<broken-version>/` and click "Yank this release" at the bottom. Provide a clear reason.
2. **Bump and re-publish.** PyPI rejects re-upload of the same version. Follow the full checklist from Phase B onward for the next patch version.
3. **Document the yank.** Add a prominent banner to the yanked release's CHANGELOG section AND to the GitHub Release notes pointing to the fix version, with an explanation of what was broken and whether existing pinned consumers should upgrade.

**Yank semantics:** pip resolvers with range or unpinned requirements (e.g., `>=`, `~=`, no version) will skip the yanked version. Pinned consumers (`==<broken>`) still resolve to it — yank is *discouragement*, not removal. This is deliberate so existing lockfiles don't break.

---

## Why each phase exists (anti-patterns this prevents)

| Phase | Anti-pattern it prevents |
|---|---|
| C | Per-domain docs updated, top-level discoverability surfaces (README / index / getting-started) forgotten. Caused `0.4.1` and `0.4.2` bumps. |
| E | Hardcoded version literal in `src/` drifting from `pyproject.toml`. Caused the `0.4.2` yank. |
| F | Pre-existing broken test files (manual scripts misfiled in `tests/`) failing collection. Caused validation-suite reruns. |
| G | Excluded paths (tests/, docs/, scripts/) leaking into the wheel. |
| H | Trusting TestPyPI's immediate-publish URL before indexing completes (90–180 s). Smoke command with hardcoded `print` string masking version drift. Poetry can't auth without `~/.config/pypoetry/auth.toml` — use twine if creds are in `~/.pypirc`. |
| L | Forgetting to file follow-ups for known issues. Future-you will be confused. |

---

## When to update this checklist

Every release that catches a *new* class of problem at any phase should add a checkbox documenting how to prevent the same class in the next release. The checklist grows; future releases get less painful.
