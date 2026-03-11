# Phase F Packaging Process Diagram

```
                    +------------------+
                    |   Phase F Start  |
                    +------------------+
                             |
                             v
    =============================================
    ||          PHASE F1: Package AlmaAPITK   ||
    =============================================
                             |
                             v
                    +------------------+
                    | 1. Create Branch |
                    | phase-f-packaging|
                    +------------------+
                             |
                             v
                    +------------------+
                    | 2. Fix Packaging |
                    | pyproject.toml   |
                    | name = almaapitk |
                    +------------------+
                             |
                             v
                    +------------------+
                    | 3. Validate      |
                    | poetry install   |
                    | import test      |
                    +------------------+
                             |
                             v
                    +------------------+
                    | 4. Add Tests     |
                    | test_public_api  |
                    | _imports.py      |
                    +------------------+
                             |
                             v
                    +------------------+
                    | 5. Build & Test  |
                    | poetry build     |
                    | pytest           |
                    +------------------+
                             |
                             v
    =============================================
    ||    PHASE F2: Update Consumer Repo      ||
    =============================================
                             |
                             v
                    +------------------+
                    | 6. Update        |
                    | Dependency       |
                    | path = ../       |
                    | AlmaAPITK        |
                    +------------------+
                             |
                             v
                    +------------------+
                    | 7. E2E Validation|
                    | dry-run test     |
                    | NO PYTHONPATH    |
                    +------------------+
                             |
                             v
    =============================================
    ||      PHASE F3: Docs & Commit           ||
    =============================================
                             |
                             v
                    +------------------+
                    | 8. Update Docs   |
                    | Remove PYTHONPATH|
                    | Add install inst |
                    +------------------+
                             |
                             v
                    +------------------+
                    | 9. Commit & Push |
                    | Both repos       |
                    +------------------+
                             |
                             v
                    +------------------+
                    | BREAKPOINT:      |
                    | Final Review     |
                    +------------------+
                             |
                             v
                    +------------------+
                    |  Phase F Done    |
                    +------------------+
```

## Success Criteria

1. `python -c "from almaapitk import AlmaAPIClient, Admin, Users; print('ok')"` works without PYTHONPATH
2. Standalone repo dry-run works without PYTHONPATH
3. Public API contract (v0.2.0) remains stable
4. Changes are minimal and reversible

## Rollback

```bash
git switch main && git branch -D phase-f-packaging
```
