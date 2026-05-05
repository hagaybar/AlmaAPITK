# Chunk Docs ↔ GitHub Coupling — Design

**Date:** 2026-05-05
**Status:** Draft (pending user review)
**Tracking issue:** #93
**Supersedes nothing.** Patches the operational layer described in `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md` §8 step 5 and `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md` §11.2.

---

## 1. Problem

Two markdown files describe chunk-pipeline state, both hand-edited:

- `docs/CHUNK_BACKLOG.md` — forward-looking plan: which chunks exist, in what phase, with prereqs.
- `AGENTIC_RUN_LOG.md` (path drift — spec says `docs/AGENTIC_RUN_LOG.md`) — backward-looking ledger: one row per merged chunk.

Per-chunk artifacts also live in `chunks/<name>/` (`manifest.json`, `status.json`, `test-results.json`, `_pr_open_result.json`, `sandbox-tests/`, `sandbox-test-output/`) — accurate, machine-readable, but local-only.

GitHub itself (issues + PRs + labels) is the actual source of truth for "open / closed / merged". The two markdown files do not reflect GitHub state automatically.

### Observed drift on 2026-05-05

The following issues were closed but not reflected in `docs/CHUNK_BACKLOG.md` until a hand-edit on 2026-05-05 (commit `58963df`):

- #1 (Trusted Publisher OIDC) — closed off-pipeline 2026-05-04, listed as open in chunk 9.
- #14 (logger cleanup) — merged via PR #88 off-pipeline 2026-05-04, listed as todo in Phase 1 chunk 4.
- #83, #85, #86, #90 — off-pipeline closures, never reflected because they weren't in the original backlog.

### Additional findings

- `scripts/agentic/run_log.py` exposes `append_chunk_row()`, but **no chunks-CLI subcommand calls it**. The five rows in `AGENTIC_RUN_LOG.md` were written by hand. Off-pipeline rows for #14 and #83 were also hand-typed.
- `AGENTIC_RUN_LOG.md` is at the repo root; spec §8 step 5 and handbook §11.2 specify `docs/AGENTIC_RUN_LOG.md`. The writer in `scripts/agentic/run_log.py` accepts a path argument so this is purely a convention drift, not a code bug.

---

## 2. Goal

Make GitHub the source of truth for issue/PR state. The two markdown files become **rebuilt artifacts** that always reflect current GitHub reality. Drift becomes impossible (or detectable) without operator intervention.

Non-goals:

- Replace the markdown files with GitHub Projects boards. (Heavier, ties workflow to the GitHub UI; can be revisited later.)
- Auto-edit issues from local artifacts. The flow is one-way: GitHub → markdown.
- Restructure `chunks/<name>/` per-chunk artifacts. Those are already accurate; they're just local. A future follow-up could push a status summary back to GitHub but is out of scope here.

---

## 3. Design

Four parts. Each can land independently; later parts depend on earlier parts only via the YAML schema.

### 3.1 Chunk plan as structured data

Move chunk metadata out of `docs/CHUNK_BACKLOG.md` into `docs/chunks-backlog.yaml`. The YAML holds **only facts the operator maintains** — never status that GitHub already knows.

Schema (proposal):

```yaml
schema_version: 1
phases:
  - id: 1
    title: HTTP foundation (architecture)
    description: |
      Lowest-risk, highest-leverage. Every later chunk benefits...
    chunks:
      - name: http-session-and-request
        issues: [3, 4]
        risk: med
        prereqs: []
        audit: clean
        notes: |
          **Recommended pilot.** #4 hard-depends on #3...
blocked:
  - issue: 29
    reason: |
      Audit conflict on whether DELETE endpoint exists...
```

`docs/CHUNK_BACKLOG.md` is deleted from version control or kept as a static stub that links to the rebuilt copy. (Open question — see §6.)

### 3.2 Backlog renderer

New CLI: `scripts/agentic/chunks render-backlog [--check]`.

Behavior:

1. Read `docs/chunks-backlog.yaml`.
2. For each issue number in the YAML, query `gh issue view <n> --json state,closedAt,title` (batch via `gh issue list` where possible to limit API calls).
3. For each chunk, derive status from the joined data:
   - **merged** — every issue in the chunk is `CLOSED` AND a matching PR is merged. PR discovery: `gh pr list --search "in:title chunk: <name>" --state merged --json number,title,mergedAt`.
   - **partial** — some issues `CLOSED`, others `OPEN`.
   - **in-flight** — `chunks/<name>/status.json` exists with non-terminal stage.
   - **planned** — none of the above.
4. Render `docs/CHUNK_BACKLOG.md` from a Jinja2 (or string-template) template with a `Status` column populated.
5. With `--check`: do not write; exit 1 if the rendered output would differ from the on-disk file. Suitable for a pre-commit hook or CI gate.

The template lives at `scripts/agentic/templates/chunks-backlog.md.j2` (or similar). Its output preserves the human prose that currently lives in `notes` fields verbatim.

### 3.3 Auto-write run-log on chunk completion

Wire `scripts/agentic/chunks complete <name>` to call `scripts/agentic/run_log.append_chunk_row()` instead of expecting the operator to hand-edit `AGENTIC_RUN_LOG.md`.

Inputs to gather inside `complete`:

- `chunk_name` — the CLI arg.
- `issue_numbers` — from `chunks/<name>/manifest.json`.
- `attempts_used` — from `chunks/<name>/status.json` (if tracked there) or empty dict if not.
- `test_outcomes` — from `chunks/<name>/test-results.json`.
- `time_total_seconds` — from `status.json` timestamps if tracked, else 0 (matches current hand-typed rows).
- `pr_url` — from `--pr-url` flag (already accepted by `complete`) or `chunks/<name>/_pr_open_result.json`.

Path: `docs/AGENTIC_RUN_LOG.md` (move the existing file there in the same change — one-line move, history preserved via `git mv`).

Off-pipeline closures (issues closed without a chunk run) are not auto-logged. They show up in the rendered `CHUNK_BACKLOG.md` because of §3.2; that is sufficient. The run-log is for chunk runs only, per its existing semantics.

### 3.4 Drift checker

New CLI: `scripts/agentic/chunks reconcile`.

Behavior:

1. Run the equivalent of `render-backlog --check` and capture any diff.
2. Diff `AGENTIC_RUN_LOG.md` against `gh pr list --state merged` joined with chunks listed in the YAML — warn about merged chunk PRs missing from the run-log.
3. Print a human-readable report. Exit 0 on clean state, 1 on any drift.

Suitable for:

- Manual operator hygiene check at session start (could be added to the CLAUDE.md session-start protocol after Claude has confirmed it works).
- CI on `main` to alert when external state has moved (issue closed via the GitHub UI, etc.).

---

## 4. Acceptance criteria

- [ ] `docs/chunks-backlog.yaml` exists with the current backlog content (translated from the live `docs/CHUNK_BACKLOG.md`).
- [ ] `scripts/agentic/chunks render-backlog` produces a `docs/CHUNK_BACKLOG.md` byte-identical (modulo timestamp header) to a hand-curated reference fixture for the current state.
- [ ] `scripts/agentic/chunks render-backlog --check` exits 1 when the on-disk markdown is stale, exits 0 when fresh.
- [ ] `scripts/agentic/chunks complete <name> --pr-url <url>` appends a row to `docs/AGENTIC_RUN_LOG.md` in the format already emitted by `scripts/agentic/run_log.append_chunk_row`.
- [ ] `AGENTIC_RUN_LOG.md` (root) is moved to `docs/AGENTIC_RUN_LOG.md` via `git mv`.
- [ ] `scripts/agentic/chunks reconcile` reports current state (will currently be clean if the YAML is freshly translated, dirty otherwise) and exits accordingly.
- [ ] Unit tests under `tests/agentic/`:
    - render output matches a fixture for a known YAML + mocked `gh` responses.
    - `--check` mode returns the right exit codes.
    - `reconcile` detects a synthesized drift case.
- [ ] CLAUDE.md session-start protocol references the new flow (operator runs `chunks reconcile` if drift suspected).

---

## 5. Out of scope

- GitHub Projects integration.
- Pushing per-chunk status from `chunks/<name>/status.json` back to a GitHub label/comment on the issues.
- Replacing `AGENTIC_RUN_LOG.md` with anything other than markdown (CSV/SQLite/etc.).
- Auto-running the renderer in pre-commit. Could be a follow-up but is not required by this spec.
- Reconciling the three overlapping planning docs (`docs/superpowers/specs/2026-05-03-…`, `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md`, `docs/CHUNK_PLAYBOOK.md`). Separate cleanup.

---

## 6. Open questions

1. **Keep `docs/CHUNK_BACKLOG.md` in version control as a generated artifact, or git-ignore it and treat the YAML as canonical?**
   - Keeping it: easy to diff in PRs, readable on GitHub web. Cost: noisy diffs every time `render-backlog` runs.
   - Ignoring it: cleaner history. Cost: GitHub web view of the repo no longer surfaces the backlog.
   - **Tentative recommendation:** keep it; add `--check` to a CI step so PRs that touch the YAML must also include the regenerated markdown.

2. **`gh` API call budget.**
   - The current backlog references ~80 issues. `gh issue view <n>` per issue is wasteful; use `gh issue list --search "is:issue repo:hagaybar/AlmaAPITK"` once and join client-side.
   - Worth caching results in `.cache/gh-state.json` with a short TTL? Probably overkill for now.

3. **Should `complete` also auto-update the YAML?**
   - E.g., when chunk `errors-mapping` completes, set its `status_override: merged` (or similar) in the YAML.
   - **Tentative recommendation:** no. The PR-merged state in GitHub is sufficient; adding a derived field to the YAML re-introduces drift.

---

## 7. Implementation phases

Pickable as one chunk or three depending on size preference.

| Phase | Scope | Effort |
|---|---|---|
| A | YAML translation + renderer + `--check` mode + tests | M |
| B | Wire `complete` → `run_log` + move `AGENTIC_RUN_LOG.md` to `docs/` | S |
| C | `reconcile` command + CLAUDE.md update | S |

Phase A is the highest-leverage step (eliminates the drift class entirely for backlog state). B fills a surprising gap (the writer existed but wasn't called). C is hygiene.

Recommend bundling A+B+C into one chunk named `chunk-pipeline-docs-coupling` since they share a small surface area (`scripts/agentic/chunks` + `scripts/agentic/run_log.py` + a new template + a YAML file).

---

## 8. References

- `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md` §8 step 5 (run-log append requirement)
- `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md` §11.2 (run-log location and schema)
- `scripts/agentic/run_log.py` (existing writer, currently unused by the CLI)
- Commit `58963df` (the manual reconciliation that motivated this spec)
- Issues #85, #86, #90 (precedent: chunk-pipeline correctness tickets)
