# pypi-publish-0.3.0 — Process Description

Orchestrates the first PyPI publish of `almaapitk` 0.3.0 by executing the implementation plan at `docs/superpowers/plans/2026-04-27-pypi-publishing.md`.

## Phases (high level)

1. **Pre-flight verification** — confirm `~/.pypirc`, smoke config, env vars, branch state, tools.
2. **Phase 0 — Audit.** Run `ruff` / `bandit` / `vulture` / grep / manual public-API review on `src/almaapitk/`. Compile findings to `docs/superpowers/specs/2026-04-27-pypi-publishing-audit-findings.md`. **User breakpoint:** triage findings (🔴 must fix, 🟡 should fix, 🟢 FYI). Apply agreed fixes.
3. **Phase 1 — Pre-flight packaging.** Verify name `almaapitk` is free on PyPI. Bump version to 0.3.0. Configure inclusion-list allowlist in `pyproject.toml`. Write release notes. `poetry build`. Inspect wheel & sdist contents (must match the inclusion list exactly). `twine check`. Create the three smoke scripts + example config + per-dir gitignore.
4. **Phase 2 — TestPyPI dry run.** `twine upload --repository testpypi`. **User breakpoint:** verify the rendered TestPyPI page. Fresh venv install + run all three smoke scripts.
5. **Phase 3 — PyPI publish (irreversible).** **User breakpoint (mandatory deploy gate per profile):** authorize the actual PyPI publish. `twine upload`. **User breakpoint:** verify the rendered PyPI page. Fresh venv install + run all three smoke scripts again from real PyPI.
6. **Phase 4 — Repo housekeeping.** Tag `v0.3.0`, push, GitHub Release. Confirm README install instructions. Write `docs/releases/HOW_TO_RELEASE.md`. **User breakpoint:** rotate broad PyPI/TestPyPI tokens to project-scoped (manual web UI). Open follow-up issue for Approach 3 (OIDC / GitHub Actions).

## User decision gates (5 breakpoints)

| Gate | Stage | Why it's here |
|---|---|---|
| Audit triage | After Phase 0 | Findings often need human judgment on what's load-bearing |
| TestPyPI verification | After Phase 2.1 | Cheap-fix moment before irreversible PyPI |
| Pre-PyPI deploy authorization | Before Phase 3.1 | Mandatory per user profile `alwaysBreakOn=[deploy, external-api-cost]`. PyPI uploads are immutable. |
| PyPI verification | After Phase 3.1 | Final visual sanity check (defects here mean planning a 0.3.1) |
| Token rotation | Phase 4.5 | Manual web UI work; agent cannot do it |

## Inputs

```json
{
  "planPath": "/home/hagaybar/projects/AlmaAPITK/docs/superpowers/plans/2026-04-27-pypi-publishing.md",
  "repoRoot": "/home/hagaybar/projects/AlmaAPITK",
  "version": "0.3.0"
}
```

## Success criteria

- `https://pypi.org/project/almaapitk/0.3.0/` exists and renders cleanly
- All three smoke scripts pass against fresh PyPI install
- `v0.3.0` tag pushed, GitHub Release created
- `docs/releases/HOW_TO_RELEASE.md` committed
- Tokens rotated to project-scoped
- Follow-up issue for Approach 3 opened
