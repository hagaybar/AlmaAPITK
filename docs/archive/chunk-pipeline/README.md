# Chunk pipeline (archived)

**Retired 2026-10-07.** This folder preserves the record of the chunk-driven
implementation pipeline that AlmaAPITK used from May to October 2026.

## What it was

GitHub issues were grouped into "chunks". A bash CLI (`scripts/agentic/chunks`)
defined chunks and tracked their lifecycle. Two babysitter orchestration
processes (`.a5c/processes/chunk-template-impl.js` and `chunk-test.js`), driven
from the `/chunk-run-impl` and `/chunk-run-test` slash commands, ran an
implement agent per issue, gated each attempt (static checks, deny-paths, unit
and contract tests), wrote a SANDBOX test plan, and then ran the live SANDBOX
tests.

## Why it was retired

The babysitter orchestration plugin was uninstalled, so the driven
impl/test paths no longer run. The decision and the options considered are in
[`docs/dashboards/chunk-pipeline-decision.html`](../../dashboards/chunk-pipeline-decision.html).

## What was kept, and where it went

- Live SANDBOX smokes: `chunks/<name>/sandbox-tests/` → `tests/sandbox/<name>/`,
  re-run with `poetry run python -m scripts.regression_smoke` (not a release gate).
- Swagger error-code harvester: `scripts/error_codes/` (unchanged).
- R10 regression tests: `tests/unit/regressions/` (unchanged).
- R7 deny-paths (`guardrails.json`) → permission deny rules in `.claude/settings.json`.

## What is in this folder

- `chunks/` — per-chunk `manifest.json`, `status.json`, `test-recommendation.json`
  and `test-results.json` as they stood at retirement.
- `AGENTIC_RUN_LOG.md` — the per-chunk run log.
- `AGENTIC_ORCHESTRATION_HANDBOOK.md`, `CHUNK_PLAYBOOK.md`, `ISSUE_PIPELINE.md` —
  the design handbook, operator playbook and lifecycle reference.

The pipeline code itself (`scripts/agentic/`, `tests/agentic/`, `.a5c/`) is in
git history before this retirement commit.
