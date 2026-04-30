# Agentic Orchestration Handbook for AlmaAPITK

**Audience:** the engineer (or future agent) who will build a babysitter-driven
pipeline that semi-autonomously implements the 77-issue backlog (architecture
`#3–#21` + coverage `#22–#79`).

**Goal of this document:** prescribe a *concrete*, opinionated design that
maximizes successful, reviewable PRs per dollar of agent runtime, while keeping
the human (you) firmly in the merge loop.

**Author's stance:** I have built and operated agentic implementation pipelines.
The biggest failure mode is not "the agent writes bad code." It is *amplifying
ambiguity at scale* — running 50 agents in parallel against under-specified
tickets, then drowning in PRs that all need rework. This handbook is structured
to prevent that.

**Prerequisites read:** `CLAUDE.md`, `docs/superpowers/specs/2026-04-30-coverage-expansion-design.md`.

---

## 0. TL;DR

- Build a **supervised-generation** pipeline, not an autonomous one. Each
  ticket → one branch → one PR → human approves → merge.
- Use babysitter as the **journal + scheduler**, not as the brain. The
  intelligence lives in well-shaped subagent prompts and tight quality gates.
- **Pilot 5 tickets first** before scaling. Calibrate prompts on real failures,
  then scale.
- **Honor the priority order in `coverage-expansion-design.md` §5.5.** Skipping
  the architecture foundation makes every coverage PR worse.
- Hard rule: **integration tests against SANDBOX are NOT in the autonomous
  loop.** They run as a separate manual batch when you've stockpiled enough
  PRs.

---

## 1. Mission and what success looks like

We are turning a 77-issue backlog into merged, working code without doing 77
issues' worth of typing. Concrete success criteria for the pipeline:

| Metric | Target |
|---|---|
| Tickets attempted per week | 8–15 (sustainable) |
| First-pass-clean rate (mocked tests pass, ready for review) | ≥ 60% |
| PRs merged per attempted ticket | ≥ 80% (within 1–2 refinement rounds) |
| Average human review time per PR | ≤ 10 minutes |
| Regressions introduced into existing tests | 0 |
| Tickets requiring full hand-implementation | ≤ 15% |

If you hit these numbers, the pipeline is paying for itself many times over.
If you fall below them — especially on regression count or review time — stop
and recalibrate before continuing.

What the pipeline is **not** trying to be:

- It is not a substitute for code review.
- It is not a replacement for SANDBOX integration testing — that stays
  manual and stays out of the auto-loop.
- It is not faster than a human for any single ticket — its win is throughput
  and consistency across many tickets.

---

## 2. Operating model: supervised generation

Three operating modes you could pick. Pick **B**.

| Mode | Description | When to use |
|---|---|---|
| A. Fully autonomous | Agent picks ticket, implements, tests, merges, moves on. No human gate. | Never. The blast radius of a bad merge into `main` is too high, and "tests pass" ≠ "code is correct" for an API client where many cases need real-API verification. |
| **B. Supervised generation** | Agent generates branch + PR. Human reviews and merges. | **Default.** Highest leverage for the lowest risk. |
| C. Pair-programming assist | Agent drafts an implementation but waits for the human at every decision point. | Only for high-risk tickets (e.g., MARC manipulation, rate-limit logic, anything that touches `_handle_response`). |

**Mode B in one sentence:** the agent's job is to produce a *reviewable* PR
that ≥80% of the time can be merged with at most a 5-minute polish.

---

## 3. The 77-ticket landscape

Numbers and shape, so the process knows what it's dealing with.

- 19 architecture tickets (`#3–#21`): mostly mechanical, well-bounded, fix
  cross-cutting concerns. *Do these first.*
- 4 foundation/bootstrap tickets (`#22, #66, #70, #75`): create empty domain
  classes; trivial; unblock siblings.
- 54 coverage tickets: add domain methods. ~70% are CRUD-shaped (high agent
  success rate); ~30% have quirks (action-on-`op`, multipart uploads, MARC).
- 4 partial-overlap tickets (`#23, #32, #40, #51`): extend existing classes;
  carry an explicit `DO NOT re-implement` block in their body.

**Every ticket** carries:
- `Domain`, `Priority`, `Effort` at the top
- `API endpoints touched`, `Methods to add`, `Files to touch`
- `References` (Alma dev-network URL + `alma-api-expert` skill + existing
  patterns in `src/almaapitk/`)
- `Prerequisites` (hard blockers + recommended soft prereqs)
- `Acceptance criteria` (testable)
- `Notes for the implementing agent`

This structure is the *contract* between the spec and the agent. If a ticket
is missing any of these, fix the ticket before running the pipeline on it.

---

## 4. Babysitter primer (the parts you actually need)

Babysitter is a process orchestrator. It does not run code itself; it emits
*effects* that the host (Claude Code, here) executes, then it journals the
results. You will use a small subset of its features.

### 4.1 The pieces

- **Process file** (`*.mjs` ESM): defines the workflow. Returns from
  `process(inputs, ctx)`. Calls `ctx.task(taskFn, args)` to dispatch work.
- **Task** (defined with `defineTask(id, factory)`): a unit of work. Has a
  `kind`:
  - `'shell'` — runs a shell command. Use for: git, gh CLI, pytest, smoke
    test, syntax checks.
  - `'agent'` — dispatches a Claude Code subagent. Use for: anything that
    needs reasoning (writing code, writing tests, code review, deciding
    whether refinement is needed).
  - `'breakpoint'` — pauses the run and waits for human input.
- **Run** (`.a5c/runs/<runId>/`): an instance of a process. Carries journal,
  task results, completion proof.
- **Iterate** (`run:iterate`): advances the run by one step. Emits effects;
  host executes; host posts results; loop.

### 4.2 Tasks vs. subagents — when to use which

The fundamental design decision in any agent pipeline.

| Task kind | Good for | Bad for |
|---|---|---|
| `shell` | Anything deterministic (commands, scripts, tests). Output is bytes/JSON. | Anything that needs judgment about the result. |
| `agent` (general-purpose) | Writing code, writing tests, summarizing, deciding pass/fail with nuance. | Anything that doesn't fit in one prompt's context budget. |
| `agent` (Plan / Explore / specialized) | Use when the babysitter SDK supports them and the work matches. | Don't dispatch a specialized agent just to feel sophisticated. |
| `breakpoint` | Truly destructive operations, ambiguous specs, repeated refinement failures. | Routine reviews — those are the human's job *outside* the run, via PR review. |

**Rule of thumb:** if a 5-line bash script can produce a deterministic answer,
use `shell`. Save `agent` calls for the parts that genuinely require an LLM.

### 4.3 Refinement loops

Babysitter doesn't have a first-class "loop" primitive. You build loops in the
process function with bounded iteration:

```js
let attempt = 0;
const MAX_ATTEMPTS = 3;
let result;
while (attempt < MAX_ATTEMPTS) {
  result = await ctx.task(implementTask, { issueNumber, feedback: prevFeedback });
  const verdict = await ctx.task(verifyTask, { branch: result.branch });
  if (verdict.pass) break;
  prevFeedback = verdict.failureSummary;
  attempt++;
}
if (!verdict.pass) {
  // breakpoint to ask for human help
}
```

Bounded retries are non-negotiable. An unbounded loop *will* find a way to
spend $500 on one ticket.

---

## 5. Process architecture

### 5.1 State machine, top level

```
┌──────────────────────────────────────────────────────────────────────┐
│  PER-RUN INPUT: ticket_number (or batch of N tickets)                │
└──────────────────────────────────────────────────────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │ pre-flight checks   │  ← shell
                        └─────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │ prereq enforcement  │  ← shell + agent
                        └─────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │ branch + scaffold   │  ← shell
                        └─────────────────────┘
                                   ▼
       ┌────────────── per-ticket inner loop ────────────────┐
       │   ┌─────────────────────────────────────────────┐   │
       │   │ implement (agent)                           │   │
       │   │   ↓                                          │   │
       │   │ static gates (shell)                         │   │
       │   │   ↓                                          │   │
       │   │ test (shell + agent)                         │   │
       │   │   ↓                                          │   │
       │   │ self-review (agent, optional)               │   │
       │   └─────────────────────────────────────────────┘   │
       │                  pass? ────► next                    │
       │                  fail? ────► refine (≤ 3 attempts)   │
       └──────────────────────────────────────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │ open PR             │  ← shell
                        └─────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │ post-flight summary │  ← shell
                        └─────────────────────┘
                                   ▼
                                  END
                       (human reviews + merges)
```

### 5.2 Task graph: detailed

Concrete tasks the process file should define. Each is reusable across
tickets (don't fork the process file per ticket).

| Task ID | Kind | Purpose | Inputs | Outputs |
|---|---|---|---|---|
| `validate-environment` | shell | Confirm git clean, on `main`, ALMA_SB_API_KEY present, smoke test passes baseline | — | `{ok: bool, baseline: {tests_passing, smoke_clean}}` |
| `fetch-issue-spec` | shell | `gh issue view N --json body,title,labels` and parse the structured fields | `{issueNumber}` | `{title, body, parsedSpec: {priority, effort, endpoints, methods, files, references, hardPrereqs, softPrereqs, acceptance, notes, extends_existing}}` |
| `check-prereqs-merged` | shell | For each hard prereq, check whether the corresponding code exists in `main` (not just whether the issue is closed) | `{parsedSpec.hardPrereqs}` | `{allMerged: bool, missing: [{issue, why}]}` |
| `create-branch` | shell | `git checkout -b feat/issue-<N>-<slug>` from `main` | `{issueNumber, slug}` | `{branch}` |
| `implement` | agent | Implement methods + unit tests | `{issueSpec, branch, feedback?}` | `{filesChanged, summary}` |
| `static-gates` | shell | `python -m py_compile`, ruff/black if configured, smoke import test | `{branch}` | `{pass: bool, failures: []}` |
| `unit-tests` | shell | `pytest tests/unit/ -v --tb=short` against the changed files | `{branch}` | `{pass: bool, failed: [], passed: int}` |
| `contract-test` | shell | `pytest tests/test_public_api_contract.py -v` | `{branch}` | `{pass: bool}` |
| `self-review` | agent | Optional: independent agent reads the diff and identifies issues | `{branch, issueSpec}` | `{verdict: ok/concerns, comments: []}` |
| `open-pr` | shell | `gh pr create` with auto-generated title, body, labels | `{issueNumber, branch, summary}` | `{prUrl}` |
| `post-flight` | shell | Append a summary to the run journal; record metrics | `{issueNumber, prUrl, metrics}` | — |

### 5.3 Per-ticket inner loop

```js
async function processTicket(ctx, issueNumber) {
  const spec = await ctx.task(fetchIssueSpec, { issueNumber });
  const prereqs = await ctx.task(checkPrereqsMerged, { hardPrereqs: spec.parsedSpec.hardPrereqs });
  if (!prereqs.allMerged) {
    return { skipped: true, reason: 'unmet hard prereqs', missing: prereqs.missing };
  }

  const branch = await ctx.task(createBranch, { issueNumber, slug: spec.titleSlug });

  let feedback = null;
  let lastFailure = null;
  for (let attempt = 1; attempt <= 3; attempt++) {
    await ctx.task(implementTask, { issueSpec: spec.parsedSpec, branch: branch.branch, feedback });

    const sg = await ctx.task(staticGates, { branch: branch.branch });
    if (!sg.pass) { feedback = formatFailure('static', sg); lastFailure = sg; continue; }

    const ut = await ctx.task(unitTests, { branch: branch.branch });
    if (!ut.pass) { feedback = formatFailure('unit', ut); lastFailure = ut; continue; }

    const ct = await ctx.task(contractTest, { branch: branch.branch });
    if (!ct.pass) { feedback = formatFailure('contract', ct); lastFailure = ct; continue; }

    const sr = await ctx.task(selfReview, { branch: branch.branch, issueSpec: spec.parsedSpec });
    if (sr.verdict !== 'ok') { feedback = formatFailure('review', sr); lastFailure = sr; continue; }

    // all green
    const pr = await ctx.task(openPr, { issueNumber, branch: branch.branch, summary: spec.parsedSpec.title });
    return { merged: false, prUrl: pr.prUrl, attempts: attempt };
  }

  // Exhausted attempts — pause for human
  return await ctx.breakpoint({
    title: `Ticket #${issueNumber} failed after 3 attempts`,
    context: { lastFailure, branch: branch.branch },
    options: ['human takes over', 'skip ticket', 'extend retries'],
  });
}
```

This is the only loop you need. Treat it as pseudocode; translate to your
actual `defineTask` calls.

---

## 6. Subagent prompt design

This is the most leveraged part of the whole system. Bad prompts → bad PRs at
scale. The patterns below are derived from running real pipelines.

### 6.1 The implementation agent

The single most important prompt in the whole pipeline. Templates below assume
Claude Code's `general-purpose` subagent. Adapt for other harnesses.

**Required ingredients in every implementation prompt:**

1. **Identity.** "You are a senior Python developer maintaining the
   `almaapitk` package. Mirror the existing style exactly."
2. **Concrete spec.** Paste the *full body* of the GitHub issue. Don't
   summarize. The agent has no other source of truth.
3. **Project pattern references.** Cite the closest existing method as the
   pattern source: e.g., for a new "create_X" method, cite
   `Acquisitions.create_invoice_simple` at line 282 of
   `src/almaapitk/domains/acquisition.py`.
4. **Skills to invoke.** Explicitly: "Use the `alma-api-expert` skill for
   endpoint quirks. Use the `python-dev-expert` skill for code patterns."
5. **Inviolable rules.** "Never use `print`. Always use `self.logger`. All
   public methods MUST have type hints + Google-style docstrings. Validate
   inputs at top of method via `AlmaValidationError`."
6. **Test requirements.** "Add unit tests under `tests/unit/domains/` using
   `pytest` with mocked HTTP via `responses` or `requests-mock`. Do NOT
   write integration tests in this PR."
7. **Output format.** "When done, list every file you changed and write a
   concise PR summary suitable for the body."
8. **Scope discipline.** "Implement only what the issue says. Do NOT
   refactor unrelated code. Do NOT add type stubs to other modules. Do NOT
   touch any file not in `Files to touch`."
9. **If refining:** include the previous failure summary verbatim, and tell
   the agent what specifically to address.

**Anti-patterns in implementation prompts (don't do these):**

- "Implement the issue however you see fit." → produces inconsistent style.
- "Improve the package while you're at it." → scope creep, regressions.
- Listing 50 rules with no examples. → agent ignores tail of list.
- Omitting the `DO NOT re-implement` block for partial-overlap tickets. →
  the agent will duplicate existing methods.
- Letting the agent invent a test data shape. → fragile tests. Always show
  a real Alma response payload as a fixture if you have one.

### 6.2 The verifier (static + tests)

These should be **shell tasks**, not agent tasks. Verifying syntax and tests
is deterministic; agents are slower and less reliable than `pytest`.

The only place an agent is justified at this stage is interpreting test
failures into a feedback string for the next refinement loop. That can be a
small focused prompt:

```
A pytest run failed. Here is the output:
<paste output>

Identify the root cause in 3-5 bullet points. State which file and which
test, and what the agent that wrote this code most likely got wrong.

Output format: JSON
{ "root_cause": "...", "file": "...", "test": "...", "fix_hint": "..." }
```

### 6.3 The self-review agent (optional, recommended)

Adds 30–60 seconds per ticket; catches a meaningful fraction of obvious
problems before you see the PR.

Prompt template:

```
You are reviewing a diff submitted by another agent. The diff implements
issue #N. Your job is to spot problems the unit tests can't catch.

Issue body:
<paste body>

Diff (git diff main..HEAD):
<paste diff>

Check for:
1. Methods missing type hints or docstrings.
2. Use of `print` instead of `self.logger`.
3. Bare `except:` clauses.
4. Hardcoded API keys, URLs, or institution-specific values.
5. New public symbols not added to `almaapitk/__init__.py` `__all__`.
6. Methods that swallow exceptions and return `None` (the `safe_request`
   anti-pattern).
7. Tests that don't actually assert behavior (just call the method).
8. Files modified that aren't in the issue's "Files to touch" list.

Return JSON: { "verdict": "ok"|"concerns", "comments": [{"severity": "low"|"medium"|"high", "file": "...", "line": N, "issue": "..."}] }
```

Treat this agent's output as advisory — it is a *fast* second pair of eyes,
not a gate. Concerns flag the PR for closer human review; they do not
automatically block.

### 6.4 Prompt hygiene rules

- **Stable templates, dynamic inputs.** Don't write a fresh prompt per ticket.
  Templated string + injected ticket data.
- **Cap context.** Don't paste the entire `acquisition.py` (2,371 lines) into
  the prompt for #58 (vendors). Paste only the closest *single method* as a
  pattern reference.
- **Explicit non-goals.** Tell the agent what NOT to do. This is more
  effective than telling it what to do.
- **No "be careful." No "use best practices."** Vague instructions waste
  tokens. Concrete rules only.
- **Format the output strictly.** JSON or named sections. Anything that needs
  to be parsed downstream must be parseable.

---

## 7. Quality gates

Order from cheapest to most expensive. Fail fast.

| # | Gate | Cost | What it catches |
|---|---|---|---|
| 1 | `python -m py_compile` on changed files | <1s | Syntax errors |
| 2 | `scripts/smoke_import.py` | ~1s | Public API broken |
| 3 | Pre-existing `tests/test_public_api_contract.py` | ~3s | Public symbols regressed |
| 4 | `pytest` against new unit tests only | 2-30s | New code is wrong |
| 5 | `pytest` full unit suite | 1-3 min | New code regressed something else |
| 6 | Self-review agent (optional) | 30-60s tokens | Style + obvious mistakes |
| 7 | **Human PR review** | 5-15 min | Everything else |

Hard rule: **a ticket does not get a PR opened unless gates 1–5 pass and 6
returns `ok`.** A blocked ticket goes to a `breakpoint` for human help.

What's NOT in the auto-gates:

- **SANDBOX integration tests.** Run these as a separate batch, manually,
  after a phase's worth of PRs are merged. Trying to run integration tests
  from inside the auto-loop:
  - hits Alma rate limits unpredictably,
  - depends on test fixtures (real records, vendors, POLs) that drift,
  - creates flaky failures that train the agent to add `try/except: pass`,
  - costs SANDBOX state that other staff care about.
- **`mypy` / strict type checking.** If your codebase isn't already 100%
  mypy-clean, don't make agents fight it. Add it later.
- **Linting that auto-fixes.** Run `ruff --fix` *as part of* the
  implementation step, not as a gate after it.

---

## 8. Breakpoints — when to pause for the human

Profile signal: your `breakpointTolerance` is `minimal` and
`alwaysBreakOn` includes `destructive-git`, `deploy`,
`delete-production`, `external-api-cost`. Calibrate the breakpoints
accordingly. The pipeline should pause for these and basically nothing else.

| Pause when | Why |
|---|---|
| First ticket of any new phase (1, 4, 6, 7 in spec §5.5) | Calibrate prompts on a single ticket before scaling. |
| Hard prereq is unmerged | Don't even start. |
| Refinement loop exhausted (3 attempts failed) | Agent isn't going to figure it out without help. |
| Self-review returns `concerns: high` | Worth a glance before it becomes a PR. |
| Merge conflict against `main` (rebase fails) | Always human. |
| Diff touches a file outside `Files to touch` | Likely scope creep; verify intent. |
| Diff includes a TODO, FIXME, or `# noqa` | Probable fudge. |
| Test was *deleted* or marked `pytest.skip` | Hard fail; the agent is hiding a problem. |

Do **not** breakpoint for:

- "Tests passed but I want to look at the diff" — that's PR review, not
  a breakpoint.
- Routine smoke-test failures — let the refinement loop handle them.
- Long-running tasks — those are notifications, not pauses.

---

## 9. The pilot: 5 tickets

Don't run the full backlog through the pipeline on day one. Run a calibration
pilot of exactly 5 tickets, in this order:

| # | Ticket | Rationale |
|---|---|---|
| 1 | `#3` Persistent `requests.Session` | Smallest meaningful architecture ticket. Tests the basic flow. |
| 2 | `#4` Consolidate verbs into `_request()` | Larger refactor. Tests the agent's discipline against scope creep. |
| 3 | `#14` Replace `print()` with logger | Mechanical, multi-file. Tests bulk find-and-replace style work. |
| 4 | `#22` Configuration domain bootstrap | Foundation ticket; tests new-domain creation flow. |
| 5 | `#36` Users: list & search | First coverage ticket; tests the standard CRUD pattern. |

After the pilot, you'll have answers to:

- Does the implementation prompt produce code matching project style? *(if not, refine the prompt)*
- Do the unit tests actually exercise behavior, or just call methods? *(if shallow, add a "tests must use assertions on response shape" rule)*
- Does the agent invent endpoints not in the spec? *(if yes, add the verbatim endpoint list to a "ONLY use these endpoints" block)*
- Does the agent re-implement existing methods? *(if yes, the `DO NOT re-implement` block needs to move to the *top* of the prompt)*
- What's the actual token cost per ticket? *(use to budget the rest)*
- What's the actual human review time per PR? *(use to plan throughput)*

Do NOT scale the pipeline before you know all six answers.

---

## 10. Calibration & scaling

After the pilot:

1. **Capture the failure modes.** For each ticket that needed refinement,
   write down (a) what the agent did wrong, (b) what fixed it. This is your
   prompt-improvement backlog.
2. **Update the prompt template.** Add concrete rules for each recurring
   failure. Keep the template versioned (commit it).
3. **Re-run the pilot tickets** if anything materially changed. Cheap to
   re-run, expensive to scale on a broken prompt.
4. **Scale in waves of 10–15 tickets.** Same priority order. Re-evaluate
   after each wave: review time per PR, refinement count, regression count.
5. **Stop and recalibrate** if any wave's metrics drop below the targets in
   §1. Don't keep grinding through bad PRs.

### 10.1 Suggested wave structure

| Wave | Tickets | Phase reference (spec §5.5) |
|---|---|---|
| W1 | `#3, #4, #5, #6, #14` | Phase 1 (HTTP foundation) |
| W2 | `#16, #9, #10, #13, #7` | Phase 2 (correctness/UX) |
| W3 | `#11, #15` + `#22` | Phase 3 + Phase 4 (Configuration foundation) |
| W4 | `#23–#28` | Phase 5: Configuration sets/orgs/locations/code-tables/jobs (high priority) |
| W5 | `#29–#35` | Phase 5: Configuration remaining (high priority) |
| W6 | `#36–#45` | Phase 5: all Users tickets (high priority) |
| W7 | `#8, #18, #21, #19, #20, #12` | Phase 6 (architecture: rate-limit, async, advanced) |
| W8–W11 | Coverage medium priority (~29 tickets) | Phase 7 |
| W12 | `#17` + low-priority cleanup | Phase 8/9 |

The key sequencing rule: never skip a wave. Phase 6's async work changes how
Phase 7 batch operations get implemented; doing Phase 7 before Phase 6 means
re-touching every ticket later.

---

## 11. Operational setup

What you need ready before launching the pipeline.

### 11.1 Environment

- `ALMA_SB_API_KEY` set in the orchestration environment. (Production key:
  do **not** expose to the agent. Pipeline runs against SANDBOX only, even
  though most tasks won't touch the API at all.)
- `gh` CLI authenticated as a user with PR-creation rights.
- `git` configured with the agent's commit identity (the `Co-Authored-By:
  Claude` footer convention from `CLAUDE.md` is correct).
- Python venv with project dependencies installed (`poetry install`).
- `pytest`, `ruff` (or whatever the project uses) on path.
- Babysitter SDK installed in `.a5c/node_modules` (already present).

### 11.2 Files to create / maintain

- `.a5c/processes/agentic-coverage.mjs` — the process file. Single source
  of truth for the orchestration shape.
- `scripts/agentic/` — directory holding shell-task helper scripts (issue
  fetcher/parser, prereq checker, branch creator, PR opener). Keep these
  small and tested; they're the glue.
- `scripts/agentic/prompts/` — versioned prompt templates (Markdown). Tag
  releases when you change them so old runs are reproducible.
- `docs/AGENTIC_RUN_LOG.md` — append-only log of pipeline runs: ticket,
  PR, refinement count, total tokens, time-to-merge. Don't skip this; you
  cannot calibrate without it.

### 11.3 SANDBOX hygiene

Even though the auto-loop doesn't run integration tests, you'll be running
SANDBOX tests *manually* between waves. Establish a clean baseline:

- Pin the test fixtures (specific user IDs, vendor codes, MMS IDs) in
  `tests/integration/conftest.py`. Document them.
- Keep a "smoke" set of integration tests that exercise one read endpoint
  per domain — run after each merged PR as a regression canary.
- Reserve a dedicated vendor or fund for test invoices/POLs so the agent's
  test data doesn't pollute real workflows.

---

## 12. Cost & budget controls

The pipeline can quietly burn money. Set hard caps.

| Control | Recommended value | Where |
|---|---|---|
| Max refinement attempts per ticket | 3 | Process loop bound |
| Max tokens per implementation prompt | 50k input / 30k output | Subagent kwargs |
| Max wall-clock per ticket | 30 minutes | Outer timeout in process |
| Max active runs in parallel | 1 (during pilot), 3 (post-calibration) | Don't fan out 50 at once |
| Token budget per wave | ~$50–$150 | Track via `babysitter tokens:stats` |
| Stop-loss threshold | 3 tickets in a row hit max attempts | Pipeline halts; recalibrate |

**Budget monitoring:** after each ticket, log token spend to
`docs/AGENTIC_RUN_LOG.md`. After each wave, sum and compare against the
phase budget. If actual > 1.5× budget, stop.

---

## 13. Failure modes & recovery

The failures you will see, in roughly descending order of frequency:

| Failure | Symptom | Recovery |
|---|---|---|
| Agent re-implements an existing method | Two methods with same name; tests don't import the new one | Surface `DO NOT re-implement` more prominently in the prompt. Re-run. |
| Agent invents an endpoint the API doesn't have | Tests pass (mocked) but the call would 404 | Add hard rule: only use endpoints from the issue's `API endpoints touched` list. Cross-reference at lint time. |
| Agent writes shallow tests | Tests pass without exercising behavior | Add: "Each test must assert on the response shape, not just that the method was called." Re-run. |
| Agent uses `print` | Self-review or grep catches it | Add to refinement feedback. Usually one retry fixes. |
| Refinement loop exhausted | 3 attempts, still failing | Breakpoint. Inspect the failure pattern; usually the spec is wrong or the test fixture is stale. |
| Merge conflict against `main` | Branch can't rebase cleanly | Breakpoint. Human resolves; resume from `open-pr` step. |
| Hard prereq merged but functionality not yet wired in | Mocked tests pass; real call would break because (e.g.) `client._request` doesn't exist on the version in `main` yet | Pipeline thinks prereq is merged, code disagrees. Add a code-level check, not just an issue-state check. |
| Subagent times out / runs out of context | No output, partial diff | Re-run with same args. If it happens twice on the same ticket, the prompt is too big — trim references. |
| `gh issue view` returns stale body (cached) | Pipeline acts on out-of-date prereqs | Use `gh issue view N --json body` (no caching layer) and verify the prereq markers in the auto-block. |

Make the runbook for each of these explicit in `docs/AGENTIC_RUNBOOK.md`
once you've seen it twice.

---

## 14. Anti-patterns (do not do these)

In rough order of "how badly this will hurt":

1. **Auto-merging.** Once. You will eventually merge a regression nobody
   noticed in mocked tests. Then the next ticket builds on the regression.
   Don't. Every PR opens; human merges.
2. **Running integration tests in the auto-loop.** SANDBOX flakiness will
   train the agent to retry until it passes (or worse, to skip the test).
   Keep integration testing manual.
3. **Letting the agent edit unrelated files "for hygiene".** The diff will
   balloon, review will take 30 minutes, and you'll merge unrelated changes
   you didn't really audit.
4. **Skipping the pilot.** "It worked on issue #3, let's run the rest." If
   the prompt template has a flaw, you'll discover it 30 PRs in.
5. **Using `agent` tasks where `shell` tasks would do.** Adds tokens,
   latency, and nondeterminism for no benefit.
6. **Letting the same ticket retry indefinitely.** Caps exist for a reason.
7. **Not logging.** No log → no calibration → no improvement → eventually
   the pipeline goes feral.
8. **Tweaking the prompt mid-wave.** Either run all of W4 with prompt v3,
   then evaluate, or run W4 with prompt v3 and W5 with v4. Mixing within a
   wave makes the metrics meaningless.
9. **Dispatching architecture tickets and coverage tickets in parallel.**
   The architecture tickets *change the pattern* the coverage tickets are
   supposed to follow. Sequence them.
10. **Trusting the `## Prerequisites` block more than the actual code.** A
    prereq issue can be merged in name but not have its functionality fully
    deployed. Always verify at code level.

---

## 15. Open questions / future work

Things this handbook doesn't solve and that you may need to address as you
operate the pipeline:

- **Prompt versioning workflow.** When does a prompt change warrant
  re-running already-merged tickets? Probably never, but you should have a
  policy.
- **Agent attribution in commit history.** The current footer convention
  (`Co-Authored-By: Claude`) is fine, but consider also recording the run
  ID for traceability: `Babysitter-Run: 01KQF86VAD...`.
- **Cross-ticket refactoring.** When implementing #58 (vendors) reveals
  that #4's `_request()` is missing a feature, who opens that ticket? Add
  an "agent observations" section to PR descriptions; triage at the end of
  each wave.
- **Multi-agent specialization.** Currently `general-purpose` does
  everything. Future split: a "writer" agent and a "reviewer" agent with
  different prompts and possibly different models. Worth experimenting
  after the pilot, not before.
- **Parallel runs.** During the pilot keep parallelism = 1. After
  calibration, you can run 2–3 tickets in parallel as long as their hard
  prereqs don't overlap. Don't go above 3 without metrics evidence.
- **Failure-mode taxonomy.** Build it as you go. After 30–50 PRs you'll
  have a real catalog. Codify it in the prompt (i.e., "do not do X — we
  saw this in tickets #58 and #62").

---

## Appendix A — Process file skeleton

Drop this in `.a5c/processes/agentic-coverage.mjs` as a starting point.
Replace `<...>` placeholders with real implementations.

```js
/**
 * @process agentic-coverage
 * @description Supervised-generation pipeline for one ticket of the AlmaAPITK backlog
 * @inputs { issueNumber: number }
 * @outputs { prUrl: string|null, status: 'opened'|'skipped'|'breakpoint' }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

const REPO = '/home/hagaybar/projects/AlmaAPITK';

// --- shell tasks (deterministic) ---

export const validateEnvTask = defineTask('validate-env', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Validate baseline (clean tree, on main, smoke passes)',
  shell: {
    command: `cd ${REPO} && git diff --quiet && git symbolic-ref --short HEAD | grep -qx main && python scripts/smoke_import.py`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const fetchIssueTask = defineTask('fetch-issue', (args, taskCtx) => ({
  kind: 'shell',
  title: `Fetch issue #${args.issueNumber}`,
  shell: {
    command: `gh issue view ${args.issueNumber} --json title,body,labels`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// ... checkPrereqsMergedTask, createBranchTask, staticGatesTask,
//     unitTestsTask, contractTestTask, openPrTask — all shell ...

// --- agent tasks (reasoning) ---

export const implementTask = defineTask('implement', (args, taskCtx) => ({
  kind: 'agent',
  title: `Implement issue #${args.issueNumber}`,
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer maintaining the almaapitk package',
      task: `Implement GitHub issue #${args.issueNumber}.`,
      context: {
        issueBody: args.issueBody,
        branch: args.branch,
        feedbackFromPreviousAttempt: args.feedback || null,
        patternSource: args.patternSource,
      },
      instructions: [
        'Mirror the existing project style. Use AlmaAPIClient for HTTP.',
        'Validate inputs with AlmaValidationError.',
        'Use self.logger for everything; never print.',
        'All public methods need type hints + Google-style docstrings.',
        'Implement ONLY what the issue says. Do not refactor unrelated code.',
        'Do not modify any file not in the issue\'s "Files to touch" list.',
        'Add unit tests under tests/unit/domains/ with mocked HTTP.',
        'When done, list every file you changed and write a 3-bullet PR summary.',
      ],
      outputFormat: 'JSON: { filesChanged: string[], summary: string, testsAdded: string[] }',
    },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const selfReviewTask = defineTask('self-review', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Self-review the diff against project rules',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior code reviewer for the almaapitk package',
      task: 'Review the diff submitted by another agent for issue #' + args.issueNumber,
      context: { branch: args.branch, issueBody: args.issueBody },
      instructions: [
        'Run `git diff main..HEAD` to see the changes.',
        'Check: type hints present, docstrings present, no print, no bare except,',
        'no hardcoded secrets/URLs, files modified are in the "Files to touch" list,',
        'tests assert on response shape (not just method invocation).',
        'Do not block on stylistic nits; flag only real concerns.',
      ],
      outputFormat: 'JSON: { verdict: "ok"|"concerns", comments: [{severity, file, line, issue}] }',
    },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// --- the process ---

export async function process(inputs, ctx) {
  const { issueNumber } = inputs;

  await ctx.task(validateEnvTask, {});
  const issue = await ctx.task(fetchIssueTask, { issueNumber });

  // <parse issue body for endpoints/methods/files/prereqs>

  // <check hard prereqs are merged in code, not just issue-closed>

  // <create branch>

  let feedback = null;
  for (let attempt = 1; attempt <= 3; attempt++) {
    await ctx.task(implementTask, {
      issueNumber, issueBody: issue.body, branch: '...', feedback,
      patternSource: '<closest existing method>',
    });
    // <static gates, unit tests, contract test, self-review>
    // if all pass: open PR and return
    // else: feedback = formatFailure(...); continue;
  }

  // breakpoint for human help
  return { status: 'breakpoint', issueNumber };
}
```

---

## Appendix B — PR body template

Auto-fill at PR-open time:

```markdown
Closes #<N>

## What this implements

<3-5 bullets from the agent's summary>

## Files changed

<auto-list>

## Tests added

<auto-list>

## Verification done in the loop

- [x] `python -m py_compile` on changed files
- [x] `scripts/smoke_import.py` passes
- [x] `tests/test_public_api_contract.py` passes
- [x] New unit tests pass (full output below)
- [x] Self-review verdict: ok
- [ ] **Pending**: SANDBOX integration tests (run manually before merge)
- [ ] **Pending**: Human review

## Prereqs verified merged

<list of hard prereqs from the issue with the commit hash where each landed>

## Refinement attempts

This PR was produced on attempt <K> of <max>.

## Pipeline metadata

- Babysitter run: <run-id>
- Implementation prompt version: <vN>
- Token spend (approx): <input/output>
```

---

## Appendix C — Calibration metrics to log

For each ticket, log to `docs/AGENTIC_RUN_LOG.md`:

| Field | Type |
|---|---|
| ticket_number | int |
| date | ISO 8601 |
| run_id | string |
| status | opened / skipped / breakpoint |
| attempts_used | int |
| time_total_seconds | int |
| tokens_input | int |
| tokens_output | int |
| pr_url | string |
| pr_merged_at | ISO 8601 (filled in later) |
| review_minutes | int (filled in later) |
| post_merge_regressions | int (filled in later) |
| notes | free text |

After every wave, compute aggregates per the success criteria in §1. If
metrics drift, fix before scaling.

---

*End of handbook.*
