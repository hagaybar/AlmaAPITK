# How to release a new version of `almaapitk` (manual recipe)

This is the step-by-step recipe used for the first PyPI publish (`almaapitk 0.3.1`, 2026-04-27). Use it for subsequent releases until the Trusted-Publisher / GitHub-Actions automation lands (see "Approach 3" follow-up issue).

## Prerequisites

- `~/.pypirc` populated with **project-scoped** tokens for `pypi` and `testpypi`, perms `0600`. (Initial release used "Entire account" tokens which were rotated to project-scoped immediately after publishing — never go back to the broad scope.)
- Working tree on `main`, clean, up to date with `origin/main`.
- Both `ALMA_SB_API_KEY` and `ALMA_PROD_API_KEY` exported in the shell session. (The 03 smoke script needs PROD because Alma Analytics is PROD-only.)
- `scripts/post_publish/smoke_config.json` present locally (gitignored). Schema:
  ```json
  {
    "sandbox_mms_id": "<known SANDBOX bib MMS ID>",
    "analytics_report_path": "/shared/Your University/Reports/.../<report name>"
  }
  ```
  Note: the analytics path is a **raw**, URL-decoded path. The Analytics class encodes via the `requests` `params` dict.
- Tools available: `poetry`, `pipx`, `git`, `gh`, `curl`.

## Steps

1. **Pick the next version** (semver: bump patch for fixes, minor for new domain methods, major for breaking changes).

2. **Update version in two places** — these must always agree:
   - `pyproject.toml`: `version = "X.Y.Z"`
   - `src/almaapitk/__init__.py`: `__version__ = "X.Y.Z"`

3. **Write release notes** at `docs/releases/X.Y.Z.md`. Cover what's new, public API changes, breaking changes (if any).

4. **Update the include path** in `pyproject.toml` `[tool.poetry] include = [...]` so the new release notes file ships in the sdist:
   ```toml
   { path = "docs/releases/X.Y.Z.md", format = "sdist" },
   ```

5. **Build:**
   ```bash
   rm -rf dist/ && poetry build
   ```

6. **Inspect both artifacts** — these checks are non-negotiable. The `exclude = ["**/*"]` form does NOT work as intended; use the explicit denylist already in `pyproject.toml`.
   ```bash
   # Wheel: only src/almaapitk/**/*.py + dist-info metadata
   unzip -l dist/almaapitk-X.Y.Z-py3-none-any.whl | awk 'NR>3 && NF>=4 && $1+0==$1 {print $4}' | grep -vE '\.py$|^almaapitk-X\.Y\.Z\.dist-info/' || echo "OK: clean wheel"

   # Sdist: only the explicit allowlist
   tar -tzf dist/almaapitk-X.Y.Z.tar.gz | grep -vE '/$' | grep -vE '^almaapitk-X\.Y\.Z/(PKG-INFO|pyproject\.toml|README\.md|LICENSE|docs/releases/X\.Y\.Z\.md|src/almaapitk/.*\.py)$' || echo "OK: clean sdist"
   ```

7. **`twine check`:**
   ```bash
   pipx run twine check dist/*
   ```
   Both must `PASSED`.

8. **Upload to TestPyPI** as a dry run:
   ```bash
   pipx run twine upload --repository testpypi dist/*
   ```

9. **Visually verify** `https://test.pypi.org/project/almaapitk/X.Y.Z/`. README rendering, classifiers, project URLs, version. **TestPyPI is also immutable** — if you find a defect, you cannot re-upload `X.Y.Z`. You must bump and re-build (e.g. `X.Y.(Z+1)`). This is what happened with `0.3.0` → `0.3.1`.

10. **Smoke test against TestPyPI** in a fresh venv:
    ```bash
    rm -rf /tmp/smoke-testpypi
    python3 -m venv /tmp/smoke-testpypi
    /tmp/smoke-testpypi/bin/pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ almaapitk==X.Y.Z
    /tmp/smoke-testpypi/bin/python scripts/post_publish/01_test_connection.py
    /tmp/smoke-testpypi/bin/python scripts/post_publish/02_get_bib.py
    /tmp/smoke-testpypi/bin/python scripts/post_publish/03_analytics_headers.py
    rm -rf /tmp/smoke-testpypi
    ```
    All three must print `OK: ...`.

11. **Upload to real PyPI:**
    ```bash
    pipx run twine upload dist/*
    ```

12. **Visually verify** `https://pypi.org/project/almaapitk/X.Y.Z/`. **Real PyPI is immutable** — the file persists forever even after yank.

13. **Smoke test against real PyPI** in a SECOND fresh venv:
    ```bash
    rm -rf /tmp/smoke-pypi
    python3 -m venv /tmp/smoke-pypi
    /tmp/smoke-pypi/bin/pip install almaapitk==X.Y.Z
    # rerun the three smoke scripts from /tmp/smoke-pypi/bin/python
    rm -rf /tmp/smoke-pypi
    ```

14. **Tag and push:**
    ```bash
    git tag -a vX.Y.Z -m "almaapitk X.Y.Z"
    git push origin vX.Y.Z
    ```

15. **Create GitHub Release:**
    ```bash
    gh release create vX.Y.Z --title "almaapitk X.Y.Z" --notes-file docs/releases/X.Y.Z.md --latest
    ```

## Notes from the first release (2026-04-27)

- **Skipped 0.3.0.** The 0.3.0 build was uploaded to TestPyPI for verification, README inaccuracies were caught at the TestPyPI gate (Users example used email instead of primary ID; Bibs example used `get_bib` instead of `get_record`; ResourceSharing example used a wrong signature; Requirements list missing three deps). PyPI / TestPyPI prohibit re-uploading the same version even after deletion, so the corrected build was uploaded as `0.3.1` and is the first version on real PyPI.
- **`__version__` was stale at `"0.2.0"`** even though `pyproject.toml` had been bumped to `"0.3.0"` weeks earlier. Always change both. The `0.3.1` release fixed this and added the README correction set.
- **Audit gate.** Before the first publish we ran `ruff` + `bandit` + `vulture` + grep + manual review. Found two real bugs worth fixing pre-publish: `process_users_batch(max_workers)` was undocumented as a no-op, and several `requests` calls in `AlmaAPIClient` had no timeout. Both fixed. Findings report committed at `docs/superpowers/specs/2026-04-27-pypi-publishing-audit-findings.md`.
- **Token rotation.** Initial publish used "Entire account" PyPI/TestPyPI tokens because project-scoped tokens cannot be created until a project exists. Immediately after the first successful PyPI upload, both broad tokens were revoked and replaced with project-scoped `almaapitk` tokens.

## Reference

- Initial design spec: `docs/superpowers/specs/2026-04-27-pypi-publishing-design.md`
- Initial plan: `docs/superpowers/plans/2026-04-27-pypi-publishing.md`
- Approach 3 (CI/CD automation, future): tracked as a follow-up GitHub issue.
