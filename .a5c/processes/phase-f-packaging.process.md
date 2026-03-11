# Phase F: AlmaAPITK Packaging Process

## Overview

Make AlmaAPITK a properly installable Python package named `almaapitk` so downstream projects can depend on it via Poetry/pip without PYTHONPATH workarounds.

## Current State

- AlmaAPITK has `src/almaapitk/` package with proper `__init__.py` and public API v0.2.0
- `pyproject.toml` incorrectly has `name = "src"` instead of `name = "almaapitk"`
- Downstream consumer (`Alma-update-expired-users-emails`) requires `PYTHONPATH` workaround

## Target State

- `pyproject.toml` declares `name = "almaapitk"` with proper package configuration
- `from almaapitk import AlmaAPIClient, Admin, Users` works after `pip install` or `poetry add`
- Downstream consumer works without PYTHONPATH

## Process Phases

### Phase F1: Package AlmaAPITK (5 tasks)

| Task | Description | Agent | Output |
|------|-------------|-------|--------|
| create-branch | Create `phase-f-packaging` branch | general-purpose | branch name |
| fix-packaging | Update pyproject.toml for proper packaging | general-purpose | changes list |
| validate-install | Run `poetry install` and verify imports | general-purpose | success status |
| add-import-tests | Create `tests/test_public_api_imports.py` | general-purpose | test file path |
| build-and-test | Run `poetry build` and `pytest` | general-purpose | build artifacts |

### Phase F2: Update Consumer (2 tasks)

| Task | Description | Agent | Output |
|------|-------------|-------|--------|
| update-consumer | Add almaapitk as path dependency | general-purpose | lock updated |
| e2e-validation | Run dry-run without PYTHONPATH | general-purpose | success status |

### Phase F3: Documentation & Commit (2 tasks)

| Task | Description | Agent | Output |
|------|-------------|-------|--------|
| update-docs | Remove PYTHONPATH instructions from READMEs | general-purpose | files updated |
| commit-and-push | Commit and push to GitHub | general-purpose | commit hashes |

### Final Breakpoint

Review commits and test results before completion.

## Hard Constraints

- Do NOT break existing production consumers
- Do NOT delete legacy modules
- Do NOT do broad refactoring - surgical changes only
- No secrets or credentials
- Tests must be offline (no network calls)

## Rollback Plan

All work on dedicated branch. Rollback: `git switch main && git branch -D phase-f-packaging`

## Definition of Done

1. Standalone repo runs dry-run without PYTHONPATH
2. Imports stable from `almaapitk`
3. `poetry build` succeeds and tests pass
4. Changes pushed and reproducible via README instructions
