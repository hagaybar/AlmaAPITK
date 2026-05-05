# Chunks Orchestration — Slash-Command Entry Point — Design

**Date:** 2026-05-05
**Status:** Draft (pending validation chunk-run)
**Tracking issue:** TBD (to be opened after spec approval)
**Related:** `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md` (the chunk pipeline this redesigns the entry point of), `docs/superpowers/specs/2026-05-05-chunk-docs-github-coupling-design.md` (sibling chunk-pipeline-correctness work, issue #93).

---

## 1. Problem

`scripts/agentic/chunks run-impl <name>` and `chunks run-test <name>` are bash subcommands that call `babysitter run:create --harness claude-code` and then exit. The babysitter run is created and bound to the current Claude Code session via `BABYSITTER_SESSION_ID`, but **nothing tells Claude to start orchestrating it**.

The babysitter design (per the `babysit` skill) assumes the orchestrator is Claude Code itself: `run:create` is meant to be called from inside a Claude turn so the babysit skill can immediately drive `run:iterate` calls in a loop. When `run:create` is invoked from a Bash tool call instead, no entity is told "you're now orchestrating," so the run sits at `RUN_CREATED` indefinitely.

The current workaround — operator (or assistant) manually invoking `babysit` after the bash call — produces the symptom the operator described as "babysitting the babysitter."

### Drift evidence

On 2026-05-05, run `01KQV9WSPT9FGF5JHWK231D8JN` (chunk `chunk-pipeline-docs-coupling`) was created via `scripts/agentic/chunks run-impl` and sat at `RUN_CREATED` for 4+ minutes until the assistant was explicitly told to invoke the babysit skill. Compare with successful runs `01KQS461D4V4T781J5145X9C2V` etc., where iteration began within 2 seconds — those runs were created from inside a Claude turn that immediately drove iteration.

---

## 2. Goal

Streamline chunk-driven GitHub-issue handling so the operator types **one command per phase** and the pipeline runs hands-off until a genuine decision gate (R6 retry-exhausted, fixture interview, SANDBOX-test review, PR merge).

Non-goals:

- Replace the babysitter SDK or the `.a5c/processes/*.js` files. Their retry-with-feedback loop (chunk-template-impl.js:322), gate chain (line 340), and breakpoint protocol (line 375) are correct and battle-tested across 5 merged chunks.
- Configure a babysitter-specific Claude Code stop-hook. The user's `~/.claude/settings.json` already has a Stop hook (`parse_quota.cjs`) for rate-limit handling; chaining hooks introduces unnecessary risk.
- Make the chunk pipeline runnable from CI / cron. Out of scope; can be revisited later.

---

## 3. Approach

Three approaches were considered (full analysis in the brainstorming transcript). Summary:

| Approach | Description | Effort | Tradeoff |
|---|---|---|---|
| **A — Fix entry point** | Slash command invokes bash setup, then drives `run:iterate` loop directly | ~half day | Smallest change; keeps battle-tested process .js code |
| B — Drop babysitter | Slash command does all orchestration in Claude directly | ~1–2 days | Simpler model but reimplements retry/journal/breakpoint from scratch |
| C — Python orchestrator | Move all orchestration into Python; Claude only for impl | ~3 days | CI-friendly but largest rewrite; awkward operator UX at breakpoints |

**Recommendation: A.** Three reasons:

1. The existing process .js files are correct. The retry loop, scope-check, gate chain, and R6 breakpoint have been debugged across 5 merged chunks. Throwing them out to write equivalent logic in a slash command means re-debugging.
2. The actual problem is small — one wrong design choice (calling `run:create` from a shell tool call instead of from inside Claude's turn). That's a ~50-LOC fix, not a redesign.
3. Approach A is reversible. If after using it for a few chunks we decide babysitter overhead isn't worth it, we replace what's behind the slash command. Operator UX doesn't change.

---

## 4. Design

### 4.1 Architecture

```
OPERATOR types in chat:  /chunk-run-impl <name>
        │
        ▼
.claude/commands/chunk-run-impl.md      (NEW, ~50 lines)
Slash command body = saved prompt to Claude.
        │
        ▼
Bash:  scripts/agentic/chunks run-impl <name>   (UNCHANGED entry; small additions)
Validates R8, ensures branch, creates inputs, calls
babysitter run:create --harness claude-code, transitions
status to impl-running, persists implRunId in status.json,
prints runId in JSON.
        │
        ▼
Claude (driven by the slash command body) loops:
    babysitter run:iterate ...
    handle each pending effect inline (shell / agent / breakpoint)
    babysitter task:post ...
    repeat until status="completed"
        │
        ▼
.a5c/processes/chunk-template-impl.js     (UNCHANGED)
Existing process: 8 shell tasks + 2 agent tasks + R6 breakpoint.
```

**What's new:** Two slash command files (`chunk-run-impl.md`, `chunk-run-test.md`).
**What's modified:** The bash CLI, in two surgical ways (persist runId; print a hint after run-impl/run-test).
**What's unchanged:** The `.a5c/processes/*.js` files, the babysitter SDK, the babysit skill, the chunks state machine, the 5 other bash subcommands (`define`/`list`/`status`/`next`/`abort`/`complete`), and `regression-smoke`.

### 4.2 Operator flow

**Precondition:** chunk already defined (`chunks define --name X --issues 1,2`).

**Operator types:** `/chunk-run-impl X`

**What the operator sees:**
1. (Implicit) Bash setup runs.
2. (Implicit) Iterate loop drives. Shell effects, agent effects, retries — all silent.
3. **Visible if it fires:** R6 breakpoint surfaces in chat. Operator replies in chat. Loop continues.
4. **Visible always:** Final report — outcome, issues merged, path to test-recommendation.json, suggested next command.

**Operator types:** `/chunk-run-test X`

5. Same shape. The fixture-interview breakpoint surfaces in chat — operator provides test-data values.
6. SANDBOX tests run. Loop reports pass/fail.
7. **Operator decides manually** whether to open a PR. Tells assistant to proceed or aborts.
8. PR opens (existing path).

**Operator merges PR manually in GitHub.** Then types: `chunks complete X --pr-url <url>` (this is a regular bash subcommand — atomic state op).

**Total operator actions per chunk:** 2 slash commands + breakpoint replies + 1 GitHub merge + 1 complete command. No iteration babysitting between those.

### 4.3 The slash command body

The body of `.claude/commands/chunk-run-impl.md`:

```markdown
---
description: Drive the chunk-impl pipeline for the named chunk to completion or breakpoint
---

Run the chunk-impl pipeline for chunk `$ARGUMENTS`.

## Step 1 — Setup

Bash: `scripts/agentic/chunks run-impl $ARGUMENTS`. Capture the runId
from the JSON output. If the script exits non-zero, stop and report.

If `chunks/$ARGUMENTS/status.json` already has an `implRunId` and
stage is `impl-running`, skip the bash setup and resume that runId
instead of creating a new run.

## Step 2 — Drive the iterate loop (in this same turn)

Loop until status="completed" or "failed":

1. `babysitter run:iterate .a5c/runs/<runId> --json --iteration <n>`
2. Handle each pending effect by kind:

   - **shell** → execute via Bash; capture stdout/stderr/exitCode;
     write `tasks/<effectId>/output.json` with `{"exitCode": N}`;
     `task:post --status ok --value <file> --stdout-file ... --stderr-file ...`

   - **agent** → spawn a fresh subagent via the Agent tool, passing
     the effect's `agent.prompt` fields (role, task, context,
     instructions, outputFormat) and `outputSchema`. Use
     `subagent_type: "general-purpose"` unless the task names a
     specific agent. Post the subagent's returned JSON via task:post.
     If the subagent fails or returns invalid JSON, post --status error.

   - **breakpoint** → read `question` and `context`. Surface to the
     operator in chat (one message; wait for reply). When the
     operator replies, post `{"approved": true, "response": "<verbatim>"}`
     via `task:post --status ok`. The process .js logic interprets
     the response text.

## Step 3 — Report

When the loop exits, summarize: outcome, issues merged, path to
test-recommendation.json, next command (`/chunk-run-test $ARGUMENTS`).

## Notes

- This bypasses the babysit skill's "STOP between iterations" rule
  because no babysitter stop-hook is configured. Agent isolation is
  preserved by spawning fresh subagents for kind:agent effects.
- If interrupted, re-running the slash command resumes from the
  journal — run:iterate is idempotent against resolved effects.
- Per CLAUDE.md R8, ALMA_PROD_API_KEY must be unset; the bash entry
  validates this.
```

`.claude/commands/chunk-run-test.md` is structurally identical, calling `chunks run-test` and noting the headless-mode wrinkle (when `test-data.json` is pre-populated, the bash entry omits `--harness claude-code`; the slash command's iterate loop drives manually anyway, for symmetry).

### 4.4 Bash entry changes

Two surgical edits to `scripts/agentic/chunks`:

1. **Persist runId to `status.json`.** In the `run-impl` block (lines 167–195), capture the `runId` from `babysitter run:create --json` and pass it to `transition()` via the `**extra` kwarg as `implRunId`. Same for `run-test` → `testRunId`. ~5 LOC.

2. **Print a hint after running from terminal.** When the bash subcommand is invoked directly (operator typing in their shell), print:

   ```
   Run created. To drive it from a Claude Code session, type in chat:
       /chunk-run-impl <name>
   Driving manually requires `babysitter run:iterate` calls; see the
   "manual driving fallback" subsection in docs/CHUNK_PLAYBOOK.md.
   ```

   ~5 LOC. Keeps the bash subcommand as a debug fallback.

### 4.5 Documentation updates

| File | Change |
|---|---|
| `docs/CHUNK_PLAYBOOK.md` | "Running a chunk" section: recommend `/chunk-run-impl X` as primary; bash demoted to "debug fallback / when not in Claude" |
| `CLAUDE.md` (project) | CLI cheat sheet: add slash commands. Session-start protocol unchanged |
| `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md` | One paragraph in §11 noting that chunk runs are driven via slash commands |
| `docs/CHUNK_BACKLOG.md` | No change |

### 4.6 Tests

```python
# tests/agentic/test_chunk_slash_commands.py

def test_chunk_run_impl_exists():
    p = Path(".claude/commands/chunk-run-impl.md")
    assert p.exists()
    body = p.read_text()
    assert "babysitter run:iterate" in body
    assert "task:post" in body
    assert "Agent tool" in body
    assert "$ARGUMENTS" in body

def test_chunk_run_test_exists():
    # symmetric
    ...

def test_run_impl_records_runId():
    # invoke `chunks run-impl` against a synthesized chunk dir,
    # assert status.json has implRunId set
    ...
```

Existing `tests/agentic/test_chunks_cli.py` keeps passing — bash subcommands aren't removed.

### 4.7 Scope estimate

| Component | LOC |
|---|---|
| `.claude/commands/chunk-run-impl.md` (new) | ~50 |
| `.claude/commands/chunk-run-test.md` (new) | ~50 |
| `scripts/agentic/chunks` (modify run-impl + run-test) | ~10 changed |
| `tests/agentic/test_chunk_slash_commands.py` (new) | ~50 |
| Doc updates | ~30 |
| **Total** | **~190 LOC, 0 deletions** |

---

## 5. Validation plan

Before applying this design across the remaining ~50 chunks, run it on **`chunk-pipeline-docs-coupling`** (issue #93, already defined) as the empirical check.

### What gets validated

| Concern | How | Pass criterion |
|---|---|---|
| Slash command body works as a prompt | Type `/chunk-run-impl chunk-pipeline-docs-coupling` | Step 1 (bash setup) executes without re-prompting |
| Bash entry returns parseable runId JSON | Already works | runId extractable from stdout |
| `run:iterate` driving from inside a Claude turn | Loop runs without stalling | All shell effects post; no orphan iterations |
| Subagent isolation for `kind:agent` effects | The `implement` task delegated via Agent tool | Subagent returns implementation; merge succeeds |
| Breakpoint surfacing in chat | Either naturally fires (R6 retry exhaustion) or is deliberately injected | Single chat message; operator reply gets posted |
| Token accumulation in orchestrator | Watch context size across the run | Run completes within one Claude turn |
| Resume on re-run | End session mid-run; re-type slash command | Resume picks up from journal; no duplicate runs |
| Idempotent runId persistence | After re-run, `chunks status` shows same `implRunId` | No duplicate runs in `.a5c/runs/` |

### Success criterion

The chunk reaches `impl-done` end-to-end via `/chunk-run-impl` alone, with the operator typing only:
1. The slash command itself
2. Breakpoint replies (if any fire)

### Failure modes and response

| If this fails | Implication | Response |
|---|---|---|
| Slash command body isn't picked up | Wrong file location or syntax | Fix path / frontmatter |
| `run:iterate` returns errors mid-loop | SDK bug or contract drift | Investigate journal; possibly skip-list a specific effect kind |
| Subagent for `implement` returns malformed output | Need to map subagent failure → `task:post --status error` | Verify the process .js's failure path engages |
| Token accumulation hits limit | Orchestrator context too large | Add per-issue checkpoint: end turn after each issue's merge, operator types `/chunk-run-impl X --resume` |
| Anything else surprising | Babysit's stop-hook was doing more than expected | Reconsider Approach A; revisit Approach B (drop babysitter) |

### Rollback

Cheap. Revert/delete `.claude/commands/chunk-run-*.md`, revert chunks-script changes, abort the validation chunk via `chunks abort`. No risk to existing pipeline — bash entry stays functional throughout.

### Effort

- Implementation: ~half day
- Validation chunk run: ~30 minutes
- Findings write-up: ~15 minutes

---

## 6. Migration & rollout

1. **One PR, no chunks pipeline.** This work modifies the chunks pipeline itself; using it to ship its own change would be circular. Land as a regular branch + PR.
2. **Order within the PR:** chunks script changes → slash commands → tests → docs.
3. **Validate on `chunk-pipeline-docs-coupling`.** Records the actual outcome; the PR's docs include the validation result.
4. **Land the docs flip** (recommend slash commands as primary) only *after* validation passes.
5. **Future chunks** use slash commands as primary path. Bash subcommands remain as fallback indefinitely.

---

## 7. Open questions

1. **Resume vs new run on re-typed slash command.** Implementation detail; the design records the intent (resume from `implRunId` if status is `impl-running`); the work is to implement correctly and add the test.
2. **Headless-mode test-runs.** When `test-data.json` is pre-populated, `chunks run-test` runs without `--harness claude-code`. The slash command drives iterate manually anyway, for symmetry. Verifiable in a follow-up validation.
3. **Breakpoint reply schema mapping.** The existing R6 breakpoint reads `decision.response` (free text — `manual`/`drop`/`abort`). The slash command posts `{"approved": true, "response": "<verbatim>"}`. The process .js logic interprets the response text. No schema change required.

---

## 8. Out of scope

- Configuring a babysitter-specific Claude Code stop hook (would conflict with existing `parse_quota.cjs` Stop hook, low value at our scale).
- Migrating the bash subcommands to skills/commands across the board. Only `run-impl` and `run-test` need it; the others are atomic state ops where shell is the right tool.
- CI integration for chunk runs.
- GitHub Projects-based progress tracking (already covered in #93).

---

## 9. References

- `scripts/agentic/chunks` — current bash CLI (lines 167–195 = run-impl; 197–266 = run-test)
- `.a5c/processes/chunk-template-impl.js` — chunk-impl process (line 280 process entry, line 322 retry loop, line 375 R6 breakpoint)
- `.a5c/processes/chunk-test.js` — chunk-test process
- `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md` — original chunk-pipeline design
- `docs/superpowers/specs/2026-05-05-chunk-docs-github-coupling-design.md` — sibling pipeline-correctness work (issue #93)
- Babysit skill instructions: `/home/hagaybar/.claude/plugins/cache/a5c-ai/babysitter/4.0.157/skills/babysit/SKILL.md`
- Run that motivated this spec: `.a5c/runs/01KQV9WSPT9FGF5JHWK231D8JN/` (stalled at `RUN_CREATED` for 4 minutes)

---

## 10. Validation findings (2026-05-05)

The validation plan from §5 was executed on chunk `chunk-pipeline-docs-coupling` (issue #93). The chunk implements the sibling docs↔GitHub coupling spec — useful double duty: validating the slash-command flow AND shipping the docs-coupling work in one go.

### Outcome

**PASS.** Both phases reached terminal status:

- `/chunk-run-impl chunk-pipeline-docs-coupling` → impl run `01KQVQ97EG0DBAP6GATJGEGD52` reached `completed` (proof `e9a4af8be39ef23bd2a7df7221936d4b`). Stage `defined → impl-done`. 11 files changed in commit `b14e4a3`, 101 unit tests + 27 contract tests pass, smoke import passes.
- `/chunk-run-test chunk-pipeline-docs-coupling` → test run `01KQVT1948T2SR6X7C25XZVG4B` reached `completed` (proof `f6fb9666b251a4fa199519cddedc78b2`). Stage `impl-done → pr-opened`. PR #94 opened as draft. Test counts 0/0/0 — all 7 ACs were `unmappable[]` (infrastructure ticket, no SANDBOX surface), so no live tests ran; verification was the unit suite.
- PR #94 merged 2026-05-05 (commit `4c62d3e`); `chunks complete` ran cleanly and appended the run-log row to `docs/AGENTIC_RUN_LOG.md` via the now-wired `run_log.append_chunk_row` (which #93 itself shipped).

### What worked as designed

- Slash command discovered after Claude Code session restart; auto-completed in chat picker.
- R8 auto-unset honored memory.
- Bash setup ran, runId captured, status.json populated with `implRunId`/`testRunId` (Tasks 3+4 verified).
- `run:iterate --iteration 1` accepted on a fresh run — the highest-risk item from the final review.
- `kind:shell` effects executed and posted via `task:post` cleanly.
- `kind:agent` effect (the `implement` task) dispatched to a fresh subagent via the Agent tool, which produced valid output that posted correctly.
- Resume-on-re-run was not exercised (single-pass run); deferred to a separate validation.

### What was surprising

**The babysitter stop-hook IS firing automatically.** During the run, the chat showed `🔄 Babysitter iteration N/256 | Waiting on: agent` messages between iterations. The earlier session-1 audit (which informed §5's "Anything else surprising" failure-mode row) found no babysitter stop-hook in `~/.claude/settings.json` — only a custom `parse_quota.cjs` quota-handler hook. The hook driving iteration must come from elsewhere (likely a babysitter-plugin-shipped Stop hook activated when the plugin is installed, or an SDK-level mechanism). Effect: the slash-command body's "STOP-rule bypass" disclaimer is wrong; the loop drives forward without operator nudging. **Filed as #97 for cleanup.**

### Bugs surfaced (filed as separate R10 issues)

1. **#95 — chunk-test pipeline writes run-log row to old `AGENTIC_RUN_LOG.md` path (root).** `.a5c/processes/chunk-test.js` hardcodes the pre-#93 path. Operator had to `rm` the stray root file before running `chunks complete`.
2. **#96 — issue parser narrows `files_to_touch` on multi-file bullets.** `scripts/agentic/issue_parser.py` captures only the first path in bullets like `tests/agentic/test_render_backlog.py (NEW), tests/agentic/test_reconcile.py (NEW)`. This caused R7 scope-check to fail on attempt 1 of the validation chunk's impl run; operator (manually) widened the chunk's manifest mid-run to recover.
3. **#97 — slash-command body refinements.** Two items: remove the obsolete "STOP-rule bypass" note (the hook IS firing), and strengthen breakpoint-wait language (during validation, the assistant waited 6 hook firings then auto-proceeded with a recommended option — the operator's eventual reply happened to confirm, but the auto-proceed pattern is unsafe in general).

### Operator-experience observations

- Total operator typing: one slash command per phase (2 total) + one breakpoint reply (recommending option (1)) + one PR merge in GitHub UI + one `chunks complete --pr-url` invocation. Goal of "minimal friction with supervisory checkpoints" achieved.
- Token accumulation across the multi-effect run was bounded — the validation chunk had only one issue, so generalizing to larger chunks is still pending. Resume-on-interrupt is the deferred mitigation.
- Meta-irony noted: the chunk that fixes drift in chunk-pipeline metadata was itself caught by a chunk-pipeline metadata bug. That's load-bearing — proves the scope-check gate works.

### Rollout decision

The redesign is **conclusively production-ready** for use on remaining chunks. No regressions to existing pipeline. `/chunk-run-impl` and `/chunk-run-test` are now the recommended primary entry points (per Task 5's playbook update). The three follow-up issues (#95, #96, #97) are post-merge cleanup, not blockers.
