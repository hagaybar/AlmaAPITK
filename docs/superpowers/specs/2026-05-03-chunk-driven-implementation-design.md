# Chunk-Driven Implementation + Interactive SANDBOX Testing — Design

**Date:** 2026-05-03
**Status:** Approved (pending spec self-review and user review)
**Supersedes:** the autonomous-loop sections of `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md` (§5, §7, §10). The handbook's prompt-design guidance (§6), failure-mode catalog (§13), and operational setup (§11) remain valid and are referenced inline.
**Inputs read while drafting:**
- `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md`
- `docs/issue-finalization-report-2026-05-01.md`
- User-stated principles (1) careful and gradual; (2) multiple branches for rollback; (3) priority infra → domains; (4) clear plan and execution; (5) acceptance = real SANDBOX tests.

---

## 1. Goal

Replace the previous "supervised generation pipeline" model (large autonomous batches of tickets, mocked tests only, integration testing as a separate manual phase) with a **chunk-driven** model: the human picks small groups of related issues, an implementation process runs them on dedicated branches, and a separate human-triggered testing process exercises them against SANDBOX before any PR is opened.

The win: every PR that ever appears has already been verified against the live API. The cost: throughput drops; the human is in the loop at three explicit points per chunk (chunk definition, test data interview, PR merge / prod promotion).

---

## 2. Hard rules (invariants)

These rules apply to every chunk, every run, every iteration. Violations are bugs, not edge cases.

| # | Rule | Why |
|---|---|---|
| **R1** | **NEVER push to or merge into the `prod` branch automatically.** All work targets `main`. Promotion to `prod` is a manual human action, performed only after a GitHub test release has been used in production for a soak period. | Production stability. The user's release flow is: `main` → test release → soak → manual `prod` merge. The agent has no place in that chain. |
| **R2** | **No PR is ever auto-merged into `main`.** Even on a perfect-green SANDBOX run the PR stays in draft until the human flips it ready and merges. | `merge` is destructive (matches `alwaysBreakOn: destructive-git`). |
| **R3** | **No autonomous loop spans the implementation → testing boundary.** The two processes (`chunk-<name>-impl.js` and `chunk-test.js`) are two separate runs the human triggers. | Forces human inspection of the diff before any SANDBOX state-change. |
| **R4** | **Auto-close only on perfect-green.** An issue can be closed by the agent only if every acceptance criterion maps to at least one SANDBOX test that passed, with no skips and no warnings. Anything else stays open with a summary comment. | Closing an issue is irreversible-ish (matches `alwaysBreakOn: delete-production`). Strong evidence required. |
| **R5** | **No SANDBOX state-change is unaccounted for.** Every test classified `stateChanging: true` carries a `cleanup` block. Cleanup failure is a hard breakpoint, never a silent leak. | Shared SANDBOX. Test debris pollutes other staff's workflows. |
| **R6** | **Refinement is bounded at 3 attempts per issue.** After 3 failures the run breakpoints. The human picks one of: take over manually, drop the issue from the chunk, abort the chunk. | Cost cap. An unbounded refinement loop can spend hundreds of dollars on one ticket. |
| **R7** | **No agent edits files outside the issue's `Files to touch` list.** Enforced by the `scope-check` gate (§5.2); if violated, the refinement attempt is rejected and feedback fed back to the agent. | Scope discipline; review economy. |
| **R8** | **The agent never sets or reads `ALMA_PROD_API_KEY`.** Only `ALMA_SB_API_KEY` is available in the orchestration environment. | Defense in depth: even if a test would otherwise reach prod, it cannot. |

---

## 3. Architecture overview

Two babysitter processes joined by a JSON contract; the human triggers each separately.

```
┌──────────────────────┐    chunks/<name>/                       ┌──────────────────────┐
│ chunk-<name>-impl.js │ ─► test-recommendation.json ─►          │   chunk-test.js      │
│  (you trigger)       │    + integration branch                 │   (you trigger)      │
└──────────────────────┘                                          └──────────────────────┘
        │                                                                    │
        ▼                                                                    ▼
  [stages 1–3]                                                       [stages 4–7]
  define chunk                                                       data interview
  generate process                                                   SANDBOX run
  implement issues                                                   summary + auto-close
  build test plan                                                    open PR (draft)
```

The seven user-facing stages:

1. Define the chunk (which issues belong together)
2. Generate the per-chunk implementation process
3. Run implementation (sub-branches → integration branch, unit-tested locally)
4. Implementation produces `test-recommendation.json` (the test plan)
5. You provide test data interactively when ready
6. Tests run against SANDBOX
7. Summary, per-issue triage (close on perfect-green; label otherwise), draft PR opened

---

## 4. Stage 1 — Chunk definition

You name the chunk and list the issues. Convention:

```
/chunk new --name http-foundation --issues 3,4,14
```

What the agent does in response:

1. Fetches each issue's body via `gh issue view` (uncached, per handbook §13).
2. Parses the standard structured fields (`Domain`, `Priority`, `Effort`, `API endpoints touched`, `Methods to add`, `Files to touch`, `References`, `Prerequisites`, `Acceptance criteria`).
3. Validates **hard prerequisites at the code level** — i.e., grep `main` for the symbol the prereq introduces, not just `gh issue view <prereq> --json state`. (Per handbook §13: a prereq issue can be closed in name but its functionality may not be fully wired.)
4. Writes `chunks/<name>/manifest.json`.
5. Asks for confirmation before the implementation process is generated.

Recommended chunk size: **1–5 issues**. No hard cap, but past 5 the integration branch's diff becomes hard to review and rollback gets messy.

What makes a good chunk:

- Issues that share a Domain (e.g., all of `Configuration` in one chunk after #22 bootstrap)
- Issues with a sequential prereq chain (e.g., #3 → #4 → #14)
- Issues that share fixtures (e.g., bib endpoints that all need the same MMS ID)

What makes a bad chunk:

- Mixing domains arbitrarily (`#3` HTTP refactor + `#62` invoice attachments — no fixture overlap, no shared review context)
- Mixing risk levels (`#5` retry logic + `#28` simple list endpoint — one needs careful eyes, the other doesn't; the careful issue gates the simple one for no good reason)
- Anything with `needs-decision` label (audit conflict — resolve before chunking)

---

## 5. Stages 2–3 — Implementation flow

### 5.1 Branch model (Approach B — sub-branches per issue)

```
main
 └── chunk/<name>                 (integration branch — exactly one PR per chunk)
      ├── feat/<N1>-<slug>        (sub-branch per issue)
      ├── feat/<N2>-<slug>
      └── feat/<N3>-<slug>
```

- Each sub-branch is created off the integration branch, implementation lands there, unit tests run there.
- On green: sub-branch merges into integration via `git merge --no-ff` (preserves issue-level boundary).
- On red after 3 attempts: sub-branch stays alive but is not merged; user decides what to do at the breakpoint.
- Rollback is a simple branch delete + integration rebuild — no `revert` commits clutter history.

### 5.2 Per-issue inner loop

Inherited from `AGENTIC_ORCHESTRATION_HANDBOOK.md` §5.2 with one structural change: **no SANDBOX step in this loop.** SANDBOX testing is the testing process's job (stage 6).

```
validate-env (shell)
  ├── git tree clean
  ├── on chunk integration branch
  └── smoke import passes baseline
        │
create-sub-branch (shell): git checkout -b feat/<N>-<slug>
        │
implement (agent, max 3 attempts)
        │
        ├─── feedback loop ────┐
        │                       │
static-gates (shell)            │
  ├── py_compile changed files  │
  └── smoke_import.py           │
        │ on red ───────────────┤
scope-check (shell)             │
  └── git diff --name-only feat/<N>-<slug>...chunk/<name>
      ⊆ issue's Files-to-touch list
        │ on red ───────────────┤
unit-tests (shell)              │
  └── pytest tests/unit/        │
        │ on red ───────────────┤
contract-test (shell)           │
  └── tests/test_public_api_contract.py
        │ on red ───────────────┘
        │ on green
merge-to-integration (shell)
  └── git checkout chunk/<name> && git merge --no-ff feat/<N>-<slug>
```

After 3 refinement attempts on the same issue, the run breakpoints and offers:

- **Take over manually** — human implements, run resumes from `merge-to-integration`
- **Drop the issue from this chunk** — sub-branch stays for inspection, integration proceeds without it; chunk manifest updated
- **Abort the chunk** — leave both integration and sub-branches in place for inspection; the run ends

### 5.3 Implementation prompts

The handbook §6 prompt design rules apply unchanged. Key reminders:

- Paste the **full** issue body into the prompt; don't summarize.
- Cite the closest existing method as the pattern source (e.g., for a `create_X` method, cite `Acquisitions.create_invoice_simple` at `src/almaapitk/domains/acquisition.py:282`).
- Explicit non-goals: "Do not modify any file not in the issue's Files to touch list. Do not refactor unrelated code."
- For partial-overlap tickets (`#23, #32, #40, #51`): the `DO NOT re-implement` block goes at the **top** of the prompt, not buried.
- Test requirement: "Add unit tests under `tests/unit/domains/`. Use `responses` or `requests-mock` for mocked HTTP. Do NOT write integration tests in this PR — those live in the testing process."

### 5.4 Outputs of stage 3

When the implementation process finishes successfully:

- **Integration branch** `chunk/<name>` containing N merged sub-branches, all green on local tests.
- **`chunks/<name>/test-recommendation.json`** — the contract for the testing process (schema in §6).
- **`chunks/<name>/implementation-summary.md`** — per-issue: files changed, methods added, attempts used, deviations from spec, agent-flagged concerns.

---

## 6. Stage 4 — Test recommendation JSON

Generated at the end of stage 3 by an agent that reads each issue's acceptance criteria + the diff.

### 6.1 Schema

```json
{
  "chunk": "http-foundation",
  "branch": "chunk/http-foundation",
  "createdAt": "2026-05-03T12:00:00Z",
  "issues": [
    {
      "number": 3,
      "title": "HTTP: persistent requests.Session",
      "classification": "general | api-coverage",
      "subBranch": "feat/3-session",
      "tests": [
        {
          "id": "t-3-1",
          "kind": "smoke | round-trip | edge-case",
          "scope": "Verify _request() reuses Session between calls",
          "endpoints": ["GET /almaws/v1/users/{user_id}"],
          "stateChanging": false,
          "needsHumanInput": [
            {
              "key": "test_user_id",
              "description": "Existing user primary_id in SANDBOX",
              "example": "tau000123"
            }
          ],
          "pythonCalls": [
            "client.users.get_user('${test_user_id}')",
            "client.users.get_user('${test_user_id}')"
          ],
          "passCriteria": [
            "Both calls return AlmaResponse.success == True",
            "client._session is the same object across calls"
          ],
          "cleanup": null
        }
      ],
      "acceptanceMapping": {
        "AC-1: persistent Session created in __init__": ["t-3-1"],
        "AC-2: Session reused across requests": ["t-3-1"],
        "AC-3: Session closed on client.close()": ["t-3-2"]
      },
      "unmappable": [
        {
          "ac": "AC-4: Session reuses connection pool across threads",
          "reason": "Cannot exercise multi-threading in a single SANDBOX call sequence; recommend manual verification."
        }
      ]
    }
  ]
}
```

### 6.2 Field semantics

| Field | Meaning | Required for auto-close? |
|---|---|---|
| `tests[].kind` | One of three categories: **smoke** (one read call, no state change), **round-trip** (CRUD with cleanup), **edge-case** (intentionally bad inputs to verify error paths) | n/a |
| `tests[].stateChanging` | Whether this test mutates SANDBOX state. If `true`, `cleanup` is required. | n/a |
| `tests[].needsHumanInput` | Fixtures the testing process must ask the human for. Aggregated across all tests in the chunk for a single up-front interview. | n/a |
| `tests[].pythonCalls` | Exact Python statements to execute. Use `${var}` syntax for fixture substitution. | n/a |
| `tests[].passCriteria` | Plain-English criteria the test must satisfy to be "passed". Each criterion becomes a pytest `assert`. | n/a |
| `tests[].cleanup` | List of `pythonCalls` to run after a passing state-changing test. Failure here is a hard breakpoint. | for `stateChanging: true` |
| `acceptanceMapping` | Object: each issue AC → array of `test.id` strings that exercise it. | **Yes — every AC must map to at least one test for auto-close to fire.** |
| `unmappable` | Array of `{ac, reason}` for any AC the agent could not exercise via SANDBOX (e.g., concurrency, observability internals). Presence of any entry **disqualifies the issue from auto-close** under R4. | n/a — its existence is what gates auto-close |

### 6.3 Construction rule

The agent producing `test-recommendation.json` must:

1. Read every AC line from the issue body literally.
2. Assign at least one `test.id` per AC. If it cannot, it must flag the AC under `unmappable` so the human knows auto-close is impossible by design.
3. Default to `kind: smoke` when in doubt — easier to upgrade to `round-trip` later than to retract a state-changing test that polluted SANDBOX.

---

## 7. Stages 5–6 — Testing process

Generic babysitter process: **`.a5c/processes/chunk-test.js`**. One file, parameterized by chunk name. Same file across all chunks.

### 7.1 Flow

1. **Read** `chunks/<name>/test-recommendation.json`.
2. **One up-front data interview (single breakpoint).** Aggregate every unique `needsHumanInput.key` across all tests in the chunk into one form-style prompt. Save responses to `chunks/<name>/test-data.json`. Rationale: avoid the human ping-ponging between Claude and Alma to grab IDs five separate times.
3. **Verify fixtures exist** — quick read calls in SANDBOX confirming each provided ID resolves. Fail fast before running real tests.
4. **Checkout integration branch** `chunk/<name>`.
5. **For each test in the recommendation:**
   - Substitute `${var}` placeholders from `test-data.json` into `pythonCalls`.
   - Generate a temp pytest file at `chunks/<name>/sandbox-tests/test_<id>.py`.
   - Run with `ALMA_SB_API_KEY` set; capture status, response shape, timing.
   - If `stateChanging` and the test passed: run the `cleanup` block.
   - If cleanup fails: hard breakpoint (R5).
6. **Aggregate** outcomes to `chunks/<name>/test-results.json`.

### 7.2 Failure handling

| Situation | Behavior |
|---|---|
| Single test fails | Continue running rest; collect all failures in `test-results.json` |
| Cleanup fails on a state-changing test | **Hard breakpoint** — human resolves SANDBOX state |
| SANDBOX rate limit (HTTP 429) | Honor `Retry-After`; sleep + retry up to 5 minutes total; then breakpoint |
| Provided fixture doesn't exist | Re-prompt the human for that key only; skip running anything against bad data |
| Integration branch dirty (uncommitted changes) | Hard breakpoint — refuse to test against unknown state |

### 7.3 Outputs of stage 6

- `chunks/<name>/test-data.json` — fixtures the human provided
- `chunks/<name>/test-results.json` — per-test outcomes, response shapes, timing, errors
- `chunks/<name>/sandbox-tests/test_<id>.py` — the actual pytest files (kept for reproducibility)
- `chunks/<name>/sandbox-test-output/<id>.log` — raw pytest output per test

---

## 8. Stage 7 — Summary + close

After testing finishes, in this exact order:

1. **Open a draft PR** from `chunk/<name>` → `main` via `gh pr create --draft`. Body auto-filled with the per-issue summary, test outcomes, fixtures used, and `Closes #N` lines for each issue.
2. **Per-issue triage:**

   | Test outcome for an issue | Action |
   |---|---|
   | All AC mapped + every test passed + zero skips/warnings | **Close issue** with summary comment + PR link |
   | Pass with partial AC coverage OR with skips/warnings | Leave open, post summary, label `tested:passing-needs-review` |
   | Any test failure | Leave open, post summary with failure details, label `tested:failing` |

3. **PR remains draft.** R2 — never auto-merge. Human flips ready and merges.
4. **No prod activity.** R1 — the agent does not touch `prod`. The user's release flow (test release → soak → manual prod merge) is entirely outside this design.
5. **Append a row to** `docs/AGENTIC_RUN_LOG.md` with: chunk name, issue numbers, attempts used, token spend (approx), test outcome counts, total time, PR URL.

---

## 8.5 Operator UX (the agent as guide)

The whole pipeline is human-paced. The human triggers stages, but should never have to remember which chunk is at which stage, or what the "next thing to do" is. The agent — Claude Code in the operator's session — is responsible for:

1. **Knowing the state of every chunk at all times.** A `chunks/<name>/status.json` file is the source of truth. Each stage updates it as it transitions.
2. **Surfacing a dashboard on demand or unprompted.** When the operator opens a session in this repo, or asks "what's the state of things", the agent reads all `chunks/*/status.json` and presents:
   - One line per chunk: name, current stage, blocking action, last update timestamp.
   - A "next recommended action" pointer per active chunk (e.g., "chunk `http-foundation`: implementation done; review the diff and trigger `chunk-test http-foundation` when ready").
3. **Walking the operator through every interactive stage** — chunk definition, fixture interview, post-test triage. Not just "tell me the answer" prompts; the agent explains what's being asked, why, and what the impact of each option is.
4. **Announcing transitions.** When a stage finishes (impl done, test results in, PR opened), the agent posts a concise status update unprompted.

### `chunks/<name>/status.json` schema

```json
{
  "chunk": "http-foundation",
  "issues": [3, 4, 14],
  "stage": "defined | impl-running | impl-done | test-data-pending | test-running | test-done | pr-opened | merged | aborted",
  "branch": "chunk/http-foundation",
  "createdAt": "2026-05-03T12:00:00Z",
  "updatedAt": "2026-05-03T12:34:00Z",
  "lastEvent": "Implementation complete; test-recommendation.json written. Review and trigger chunk-test when ready.",
  "nextAction": "chunk-test http-foundation",
  "openBreakpoints": [],
  "implRunId": "01KQH...",
  "testRunId": null,
  "prUrl": null
}
```

### CLI helper: `scripts/agentic/chunks`

A small bash CLI the operator (and the agent) call to interact with chunk state. Subcommands:

| Subcommand | Purpose |
|---|---|
| `chunks list` | One-line summary of every chunk in `chunks/*/status.json`, sorted by `updatedAt` |
| `chunks status <name>` | Full status block for one chunk (manifest, status, next-action, open files) |
| `chunks next` | Across all chunks, list the recommended next actions in priority order |
| `chunks define --name <n> --issues <ids>` | Stage 1 entrypoint: builds manifest, validates prereqs, generates impl process, writes initial `status.json` |
| `chunks run-impl <name>` | Triggers the per-chunk implementation babysitter run; updates `status.json` as it transitions |
| `chunks run-test <name>` | Triggers `chunk-test.js` against the named chunk; orchestrates the data interview and updates `status.json` |
| `chunks abort <name>` | Marks the chunk aborted, leaves branches in place for inspection |

These commands are **scripts** so the operator can call them by hand (e.g., from a non-Claude shell) and so the agent has a stable interface to call them from. They are NOT a substitute for the agent's narration — they're the source of truth, the agent is the guide.

### Session-start convention

When a Claude Code session opens in this repo and `chunks/` contains active chunks (`stage` ∉ `{merged, aborted}`), the agent's first message in that session must include a one-paragraph dashboard:

> *"You have 2 active chunks. **`http-foundation`** (#3, #4): implementation done, awaiting your test trigger. **`config-bootstrap`** (#22): impl-running, attempt 2/3 on issue #22. Want me to dig into either, or define a new chunk?"*

This is captured in `docs/CHUNK_PLAYBOOK.md` as standing instruction.

### What the agent does NOT do

- Auto-trigger any stage. Even if a chunk has been sitting at `impl-done` for a week, the agent does not auto-start `run-test`. It surfaces the state and waits.
- Decide for the operator at any breakpoint. The agent presents context and options, never picks.
- Hide failures. If something is in `aborted` or has failing tests, the dashboard says so explicitly.

---

## 9. File layout per chunk

```
.a5c/processes/
  chunk-template-impl.js          # Generator template (used to produce per-chunk files)
  chunk-<name>-impl.js            # Generated per chunk; bespoke to that chunk's issues
  chunk-test.js                   # Generic, parameterized, same file for all chunks

chunks/
  <name>/
    manifest.json                 # Issue list + parsed prereqs (stage 1)
    status.json                   # Lifecycle state, source of truth for §8.5 (stages 1–7)
    implementation-summary.md     # What got built per issue (stage 3)
    test-recommendation.json      # The contract (stage 3 output → stage 5 input)
    test-data.json                # Human's fixture answers (stage 5)
    test-results.json             # Aggregated outcomes (stage 6)
    sandbox-tests/                # Generated pytest files
      test_t-3-1.py
      test_t-3-2.py
    sandbox-test-output/          # Per-test pytest stdout/stderr
      t-3-1.log
      t-3-2.log

scripts/agentic/
  chunks                          # CLI helper (§8.5): list/status/next/define/run-impl/run-test/abort
  ...                             # other helpers (issue parser, prereq checker, scope-check, etc.)

docs/
  AGENTIC_RUN_LOG.md              # Append-only chunk log (calibration metrics)
  CHUNK_PLAYBOOK.md               # Operator cheat sheet + session-start convention (§8.5)
```

`chunks/` is checked into git per the user's auto-memory ("Always include `.a5c/` artifacts in commits"). The same applies to chunk artifacts: the run log of a chunk lives forever for traceability.

---

## 10. Failure modes (catalog)

Beyond the in-loop failure handling above, these are run-level failure modes worth naming:

| Failure | Likely cause | Recovery |
|---|---|---|
| Implementation: agent re-implements an existing method | Partial-overlap ticket; `DO NOT re-implement` block buried | Move it to the top of the prompt; re-run |
| Implementation: agent invents an endpoint not in the issue | Spec ambiguity, bad reference | Add hard rule: only use endpoints from the issue's `API endpoints touched` list; lint at static-gates |
| Implementation: agent writes shallow tests | Prompt didn't enforce assertions | Add: "Each test must assert on the response shape" |
| Implementation: 3 attempts exhausted | Spec is wrong, fixture stale, or genuinely hard | Breakpoint; human takes over / drops / aborts |
| Implementation: integration merge conflict between sub-branches | Two issues touched the same line | Breakpoint; human resolves |
| Testing: data interview never gets answered | Human not available | Run pauses indefinitely; resume when ready (babysitter is journaled) |
| Testing: cleanup leaks SANDBOX state | Cleanup block has a bug | Hard breakpoint with diagnostic output; human resolves and re-runs cleanup manually |
| Testing: SANDBOX endpoint returns unexpected response | Alma changed shape, or test expectation was wrong | Mark test failed; surface in summary; do not auto-close |

---

## 11. What this design intentionally does NOT do

- **No automatic chunk suggestion.** The human picks chunks. (A `/chunk suggest` helper is future work.)
- **No cross-chunk dependency check.** Each chunk validates its prereqs against `main` only. Coordinating two unmerged chunks with overlapping prereqs is the human's responsibility.
- **No SANDBOX broad cleanup tooling.** Per-test cleanup only. A "burn down everything we created" utility is future work.
- **No auto-merge to `main`.** R2.
- **No `prod` interaction whatsoever.** R1.
- **No mocked-test-only PRs.** Implementation produces a tested local build but no PR opens until SANDBOX has been exercised.
- **No prompt-versioning workflow.** When the prompt template changes, prior chunk artifacts are not retroactively re-generated. (Handbook §15 open question — out of scope.)

---

## 12. Operational prerequisites

Before running the first chunk:

- `ALMA_SB_API_KEY` set in the orchestration environment. **`ALMA_PROD_API_KEY` MUST NOT be set in this environment** (R8).
- `gh` CLI authenticated as a user with PR-creation rights.
- `git` configured with the agent's commit identity (the `Co-Authored-By: Claude` footer convention).
- Python venv with project dependencies installed (`poetry install`).
- `pytest` and any linters on the path.
- Babysitter SDK installed in `.a5c/node_modules` (already present).
- One **dedicated SANDBOX test fixture set** documented somewhere durable (e.g., `tests/integration/conftest.py` or a chunks-level README): a known-good user primary_id, a known-good MMS ID, a dedicated test vendor, a dedicated test fund. The data interview asks for these by reference.

---

## 13. Open questions / future work

| Question | Trigger to revisit |
|---|---|
| Should there be a `/chunk suggest` helper that proposes chunks from the finalization report's groupings? | After 5+ manually-defined chunks, when patterns are clear |
| Should the auto-close criteria be per-AC (mapped + passing) or per-issue (all-or-nothing)? Current design is the latter. | If issues with many ACs routinely get one trivial AC failing while everything substantive passes |
| Should the testing process support "reuse last chunk's test-data.json"? | When two chunks back-to-back use the same fixtures and the data interview becomes annoying |
| Should the per-chunk PR cap stay at 1, or split when the chunk's diff exceeds a size threshold? | If a chunk's PR ever exceeds ~500 LOC and review time blows up |
| When does prompt template version warrant re-running merged chunks? | Probably never; document the policy when first asked |

---

*End of design.*
