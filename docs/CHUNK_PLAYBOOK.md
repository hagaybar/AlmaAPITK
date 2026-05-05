# Chunk Playbook — Operator's Cheat Sheet

This is your reference for running chunks day-to-day. Design context lives in `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md`. This document is operational, not architectural.

## Session-start convention (for the agent)

When a Claude Code session opens in this repo and `chunks/` contains active chunks (any chunk whose `stage` is not `merged` or `aborted`), the agent's first message MUST include a one-paragraph dashboard built from `scripts/agentic/chunks list`:

> *"You have N active chunks. **`<name>`** (#X, #Y): `<stage>`, last event `<lastEvent>`, next `<nextAction>`. ..."*

The agent then asks what you want to do (drill into one, define a new one, no-op).

## Inviolable rules (R1–R8 from the spec)

| Rule | Plain English |
|---|---|
| R1 | Never push or merge to `prod`. The agent never touches `prod`. |
| R2 | No PR is auto-merged. PRs always open as drafts. You merge. |
| R3 | Implementation and testing are separate runs. You trigger each. |
| R4 | Auto-close only when every AC has a passing SANDBOX test. |
| R5 | Every state-changing test has a cleanup. Cleanup failure is a hard stop. |
| R6 | 3-attempt cap on implementation refinement. After that, you decide. |
| R7 | Agents don't edit files outside the issue's Files-to-touch list. |
| R8 | Orchestration env is SANDBOX-only. `ALMA_PROD_API_KEY` must not be set. |

## End-to-end walkthrough

### 1. Define a chunk

Pick 1–5 related issues. Name the chunk something short and specific.

```bash
scripts/agentic/chunks define --name http-foundation --issues 3,4
```

What this does:
- Calls `gh issue view` for each number; parses Domain, Priority, Effort, Files-to-touch, Prereqs, ACs.
- Code-checks every hard prereq against `main` (per handbook §13).
- Writes `chunks/http-foundation/manifest.json` + `status.json` (stage: `defined`).

If a hard prereq is missing in code, the CLI exits 2 and you must merge that prereq first.

### 2. Trigger implementation

**Primary path (recommended):** in your Claude Code chat, type:

```
/chunk-run-impl http-foundation
```

This invokes the slash command, which runs the bash setup, then drives
the babysitter `run:iterate` loop directly until completion or a
breakpoint. Operator only sees breakpoints in chat.

**Fallback path (terminal):** if you're not in Claude Code, run:

```bash
scripts/agentic/chunks run-impl http-foundation
```

This creates the run but does NOT drive iteration. The run will sit at
`RUN_CREATED` until something invokes `babysitter run:iterate` against
the runId (printed in the JSON output).

What this does:
- Creates the integration branch `chunk/http-foundation` off `main` if it doesn't exist.
- Creates a babysitter run using `.a5c/processes/chunk-template-impl.js`.
- Updates status to `impl-running`.

The babysitter run will:
- For each issue, create `feat/<N>-<slug>`, run the implementation agent (max 3 attempts), run static-gates → scope-check (R7) → unit tests → contract tests, then merge into the integration branch with `--no-ff`.
- After all issues, generate `chunks/http-foundation/test-recommendation.json`.
- Set status to `impl-done`.

If any issue exhausts 3 attempts: the run breakpoints. Pick `manual` (you fix it), `drop` (skip this issue, continue), or `abort`.

### 3. Inspect the implementation

```bash
scripts/agentic/chunks status http-foundation
git log --oneline main..chunk/http-foundation
cat chunks/http-foundation/test-recommendation.json | jq .
cat chunks/http-foundation/implementation-summary.md
```

Edit the test-recommendation.json if you want to drop a test or add a fixture. The testing process reads it as-is.

### 4. Trigger testing

When you're ready to put fixtures together:

**Primary path (recommended):** in your Claude Code chat, type:

```
/chunk-run-test http-foundation
```

This invokes the slash command, which runs the bash setup, then drives
the babysitter `run:iterate` loop directly until completion or a
breakpoint. Operator only sees breakpoints in chat.

**Fallback path (terminal):** if you're not in Claude Code, run:

```bash
scripts/agentic/chunks run-test http-foundation
```

This creates the run but does NOT drive iteration. The run will sit at
`RUN_CREATED` until something invokes `babysitter run:iterate` against
the runId (printed in the JSON output).

What this does:
- Creates a babysitter run using `.a5c/processes/chunk-test.js`.
- The run will breakpoint on a single fixture interview — you'll see one form-style prompt asking for every fixture key the chunk's tests need.
- After you answer, the run executes each test against SANDBOX, captures pass/fail, runs cleanups, and writes `chunks/http-foundation/test-results.json`.
- Status moves through `test-data-pending` → `test-running` → `test-done`.

### 5. PR and triage

After tests complete, the run:
- Opens a draft PR `chunk/http-foundation` → `main` (R2 enforced — always draft).
- Per issue: auto-closes if perfect-green (R4), else applies a label.
- Appends to `docs/AGENTIC_RUN_LOG.md`.

Status moves to `pr-opened`.

### 6. Manual merge (your call, your hands)

Open the PR. Review the diff. Flip ready. Merge to `main`.

Status: still `pr-opened` (the agent doesn't auto-update on merge — `gh pr merge` is yours). Optionally:

```bash
scripts/agentic/chunks status http-foundation  # to refresh after manual update if you wire that
```

You can manually transition the chunk to `merged`:

```bash
python -c "from scripts.agentic.chunk_status import transition; from pathlib import Path; transition(Path('chunks/http-foundation'), 'merged', 'merged via gh', 'soak before prod release')"
```

### 7. Prod promotion (entirely outside this pipeline — R1)

When you're ready, your manual flow:
1. Cut a GitHub test release from `main`.
2. Soak it.
3. `git checkout prod && git merge main && git push origin prod`.

The agent never participates in step 1, 2, or 3. R1 is hard.

## Coverage-issue acceptance criterion: swagger error codes accounted for

When you open a NEW coverage issue (`#22-#79` style), include this acceptance criterion in the issue body:

> All Alma error codes documented in the swagger for the touched endpoints are accounted for in `ERROR_CODE_REGISTRY` (mapped to a typed `AlmaAPIError` subclass, or explicitly noted as `# unmapped: <reason>`).

Why this is here, not on the existing `#22-#79` issues: those were authored before issue #90 landed; we don't retroactively edit them. The new AC applies to any coverage issue opened after #90 merged. Backfill happens organically — whenever a chunk next touches a domain, it sees the full documented-code list for that domain and adds anything missing.

How the chunk pipeline supports this AC:

- `scripts/error_codes/fetch_domain_codes.py <domain>` — CLI to download the per-domain swagger (`https://developers.exlibrisgroup.com/wp-content/uploads/alma/openapi/<domain>.json`) and emit documented codes as JSON. Caches to `scripts/error_codes/swagger_cache/<domain>.json` (raw swagger) + `<domain>.fetched.json` (URL + ISO fetch timestamp). Re-run with `--force` to refresh.
- `.a5c/processes/chunk-template-impl.js` — before each issue's `implement` agent task fires, the per-issue `fetch-swagger-codes` shell step infers the swagger domain(s) from the issue's Files-to-touch / endpoints (via `scripts.agentic.issue_parser.infer_swagger_domains`) and writes a sidecar at `chunks/<name>/_swagger_errors_<issue_number>.json`. The implement agent's prompt receives the path as `context.swaggerErrorsPath` and is instructed to cross-check `ERROR_CODE_REGISTRY` against the documented codes whose declaring endpoints overlap the issue's "API endpoints touched".
- Failure of the swagger fetch (network outage, dev-network down) is non-fatal: the sidecar is written with an empty `reports[]` and the chunk continues. The new AC degrades to best-effort in that case rather than blocking the chunk.

`scripts/agentic/issue_parser.py` carries a small `DOMAIN_ALIASES` map (in `scripts/error_codes/fetch_domain_codes.py`) that translates `src/almaapitk/domains/<file>.py` filenames to Alma's swagger domain names — e.g. `acquisition.py` → `acq`, `admin.py` → `conf`. Add to that table when introducing a new domain class.

## Common things you'll do

### See what's active

```bash
scripts/agentic/chunks list
```

### See what to do next

```bash
scripts/agentic/chunks next
```

### Drill into one chunk

```bash
scripts/agentic/chunks status <name>
```

### Abort

```bash
scripts/agentic/chunks abort <name>
```

This marks the chunk aborted but **leaves all branches alive** so you can inspect.

## Failure recipes

### "A hard prereq isn't merged"

Two options: merge it first, OR drop the dependent issue from the chunk and try again.

### "Implementation failed 3 attempts on issue #X"

You'll get a breakpoint. Pick `manual` and:
1. Check out `feat/X-<slug>`.
2. Fix it by hand.
3. Run `python -m py_compile` + `pytest tests/unit/` to confirm green.
4. Approve the breakpoint with `manual`; the run merges your work into integration.

### "SANDBOX cleanup failed"

Hard breakpoint. Note the entity that wasn't cleaned (POL, invoice, user attachment, etc.) from the breakpoint message; remove it manually via Alma UI or a one-off script. Resume the run.

### "Test interview asks for a fixture I don't have"

Either provision the fixture in SANDBOX (create a test vendor, etc.) or edit `test-recommendation.json` to drop the test that needs it. Re-run `chunks run-test`.

## Notes

- `chunks/<name>/` is checked into git per the user-memory rule "always include `.a5c/` artifacts in commits". `sandbox-test-output/` and `sandbox-tests/` are gitignored (raw logs, not historical truth).
- Prompt templates are versioned (`scripts/agentic/prompts/implement.v1.md`, etc.). When you change one, bump to `v2.md`. Existing chunk artifacts are not re-generated retroactively.
- The run log (`docs/AGENTIC_RUN_LOG.md`) is your calibration data. After every wave of chunks, look at attempts/passes/review-time and tune the prompt.

## Manual driving fallback

If you've created a chunk run via the bash subcommands but cannot use
the slash command (e.g., not currently in a Claude Code session),
drive it manually:

```bash
RUN_ID=$(jq -r '.implRunId // .testRunId' chunks/<name>/status.json)
while :; do
  out=$(babysitter run:iterate ".a5c/runs/$RUN_ID" --json --iteration 1)
  status=$(echo "$out" | jq -r '.status')
  case "$status" in
    completed|failed) echo "$out"; break ;;
    waiting)
      # Inspect $out, execute the pending effect, post via task:post,
      # and re-iterate. Effects with kind=agent or kind=breakpoint
      # require a Claude session; you cannot drive them from raw bash.
      echo "$out"; break ;;
  esac
done
```

For chunks that contain only shell effects, this works end to end.
For chunks with `kind: "agent"` effects (e.g. the `implement` task in
chunk-impl), use the slash command from a Claude Code session.
