# Run-History Insights — AlmaAPITK babysitter cleanup snapshot

_Generated 2026-05-12 by cleanup-runs process 01KRDT0JFKX7NTWTVK6H8SXW3B. Source: 68-run classification at `.a5c/runs/01KRDT0JFKX7NTWTVK6H8SXW3B/tasks/01KRDT0XMXVGAGDWBBA7NB5QF9/`._

## Snapshot

| Metric | Count |
| --- | --- |
| Total runs scanned | 68 |
| Completed | 47 |
| Failed | 1 |
| Active (no terminal event) | 20 |
| Disk footprint | 26 MB |
| Terminal runs >30 days (aggregated below) | 9 |
| Process files | 21 |
| Orphaned process files | 1 (`chunk-template-impl.js`) |

The scan threshold is `keepRecentDays = 30`. Only terminal-and-aged runs feed
the aggregation below; everything else (the 20 active runs and the 38 terminal
runs <30 days) is retained as-is until they age out.

## Run-history summary (terminal runs >30 days)

| processId | runId | Age (days) | Outcome | Notes |
| --- | --- | --- | --- | --- |
| `phase-b1-public-api` | `01KKEH3YD7PHHCNA51ZT140V7A` | 61 | completed | Defined first stable `almaapitk` public surface (`__version__`, `AlmaAPIClient`, `AlmaResponse`, `AlmaAPIError`, `AlmaValidationError`); wrote `docs/API_CONTRACT.md` and re-pointed `scripts/smoke_import.py` to the public API. Commit `ef7402c`. |
| `phase-b2-internal-namespace` | `01KKEHZTVJ4CNHREVVJ04YMXTT` | 61 | completed | Moved client/response/exceptions under `almaapitk/_internal/` and added `tests/test_public_api_contract.py` as the gatekeeper. Commit `cd07459`. |
| `phase-d-pilot-migration` | `01KKENAC5KCHNHQ6FC4CCTPGTK` | 61 | completed | Pilot-migrated the `update_expired_users_emails` workflow on top of the new public API; wrote `docs/MIGRATION_MAP.md` and `tests/test_pilot_migration.py`. Commit `8eedc7a`. |
| `phase-e-project-extraction` | `01KKEPBGGG8PR059QRCA62D1JG` | 61 | completed | Extracted the email-expiry project into its own repo (`Alma-update-expired-users-emails`, commit `161efec6`). First proof that core-library / consumer-project separation works. |
| `phase-f-packaging` | `01KKER7G9EGJNSJBWFCND4BHBD` | 61 | completed | Made `almaapitk` properly installable (wheel + sdist for `0.2.0`); flipped the extracted project to depend on the published package. 25 unit tests passing, end-to-end script works without `PYTHONPATH`. |
| `phase-g-rs-extraction` | `01KKHR2NJJ48TKBEZSSK5A47MF` | 60 | completed | Extracted the Resource Sharing lending automation into `Alma-RS-lending-request-automation` (commit `f7a6755d`). Second consumer-project extraction, repeating the Phase E pattern cleanly. |
| `almaapitk-documentation` | `01KKVY44G4S9V112TPYSAZM9KB` | 56 | completed | Authored the documentation set under `docs/` (12 markdown files): Getting Started, API Reference, five domain guides, examples, error handling, logging, quality report, index. Self-scored quality 88/100. |
| `tdd-bibs-collection-methods` | `01KKXW30BPSV0ZE197N34JZNB4` | 55 | completed | TDD added `get_collection_members`, `add_to_collection`, `remove_from_collection` on `BibliographicRecords`. RED→GREEN cycle worked, 16/18 integration tests passed (2 fail on Alma collection-type restrictions). Quality 95/100. |
| `tdd-analytics-domain` | `01KM02J19MWZMMH8YZH50RA2Z1` | 54 | completed | TDD added the `Analytics` domain (`get_report_headers`, `fetch_report_rows`) with unit + integration suites. Critique pass added negative-input validation and `Raises:` docstring sections. Quality 92/100. |

No `failed` runs fall in the >30-day window. The single failed run in the
scan is recent (<30 days) and stays out of this aggregation.

## Key decisions & insights

- **The "public-surface first, then migrate, then extract" cadence works.** Phases B1 → B2 → D → E → F → G ran on consecutive days, each one consuming the artifact the previous phase produced (public surface → internal namespace → pilot script → extracted repo → installable wheel → second extracted repo). The `docs/API_CONTRACT.md` and `tests/test_public_api_contract.py` files are direct outputs of this cadence and still anchor the package today.
- **`tests/test_public_api_contract.py` was introduced in Phase B2 and is still the load-bearing guard** against accidentally re-exporting internals or breaking the public surface. It earned its keep on day one and remains worth running on every PR.
- **Consumer projects must live outside this repo.** Phase E and Phase G demonstrated that extracting a project (`Alma-update-expired-users-emails`, `Alma-RS-lending-request-automation`) and re-pointing it at the installed `almaapitk` is a low-friction operation. The list of extracted repos in `CLAUDE.md` is a direct descendant of these two runs.
- **TDD as a babysitter pattern is repeatable.** The `tdd-bibs-collection-methods` and `tdd-analytics-domain` runs both followed the RED→GREEN→quality-critique loop. Quality scores (95 and 92) and the explicit list of fixes the critique pass added (type hints, `Raises:` docstring sections, negative-input validation) are a useful template for future TDD chunks.
- **Integration tests that depend on real sandbox IDs become "expected failures."** The bibs-collection run flagged 4 tests as failing only because `TEST_COLLECTION_ID` was a placeholder; the implementation itself was correct. Lesson: surface "needs real sandbox fixture" as a first-class status in test reports rather than counting it as a regression.
- **The Phase F wheel build (`almaapitk-0.2.0`) is the direct ancestor of today's `0.4.x` PyPI releases.** All subsequent release work assumes the package is `pip install`-able, which only became true in this run.
- **Documentation can be generated in one babysitter run.** `almaapitk-documentation` produced 12 markdown files in a single run with an 88/100 self-score. The output is still the spine of `docs/`. Worth repeating when a major domain lands.

## What worked

- **Sequential single-purpose phases.** Each Phase B1/B2/D/E/F/G run had one concrete deliverable; final-state JSONs are tiny (<2 KB) and unambiguous. Easy to audit afterwards.
- **Commit-hash-in-output.** Every phase output records its commit hash, making it trivial to walk back from the run to the change.
- **TDD outputs explicitly track RED and GREEN phases.** Both TDD runs distinguished "expected failure" (RED) from "real failure," and recorded fix lists from the critique pass. That's the format future chunk-test runs should aim for.
- **Cross-repo coordination is recorded in the output.** Phase F's `commits` array names both repos (`AlmaAPITK` and `Alma-update-expired-users-emails`), making the two-repo change visible from one run.

## What didn't work / what we learned

- **No failed terminal runs in the aged window — but the active list is doing the failing for us.** 20 runs are stuck in "active" because they never wrote a `RUN_COMPLETED` / `RUN_FAILED` journal event. Some have real output (`verify-analytics-ui` `01KM0EM31GTX6B3Y2RERZTCC59` has a full `output.json` and a "Task 8 COMPLETE" recommendation) but the orchestrator never closed the lifecycle. Treat orphaned-active runs as the new "failed" signal until journal finalization is more reliable.
- **`phase-c-dependency-api-completion` (`01KKEM9XSF7619QXAKYB18NE66`) stalled after one resolved effect.** Only one invocation (`scan-project-imports`) resolved; the run never produced an `output.json`. It is the only Phase B–G phase that didn't ship, and that gap is why Phase D had to pilot-migrate manually instead of consuming a "completion" artifact.
- **`tdd-bibs-collection-methods` left 2 tests failing because Alma rejects the operation on that collection type.** The babysitter still flagged the run "complete" with `verified: true`. Future TDD runs should either pre-validate collection type or carve those tests into a separate "API-restriction" bucket so they don't pollute the suite.
- **`almaapitk-documentation`'s 88/100 self-score is generous.** The output has no list of items it scored *down* on, so we can't act on the gap. Future doc runs should record per-section deductions, not just an aggregate.
- **Orphan process file: `chunk-template-impl.js`** is in the processes directory but referenced by zero runs. Likely a leftover template; Phase 3 will reap it.

## Recommendations for future runs

- **Force a terminal journal event.** Whatever causes runs to stay "active" with no final event (see the 20 stuck runs) needs an explicit `RUN_FAILED` fallback when the orchestrator crashes or the operator walks away. Without it, the active list grows monotonically and skews every future scan.
- **Standardize the `output.json` shape across processes.** The aged runs already converge on `{success, filesModified, commitHash, testResults?, quality?}`. Codify that shape so the next cleanup pass can aggregate without re-reading every file. (See the dashboard fields cited in `CLAUDE.md` session-start protocol.)
- **Make "needs sandbox fixture" a first-class test outcome.** Both TDD runs in the aged window hit this; future runs should emit it as a discrete status rather than `failed`.
- **Always write the commit hashes for *all* repos a run touches** (Phase F does this; most others record only the AlmaAPITK hash). When a single run spans `almaapitk` and a consumer repo, both hashes belong in the output.
- **Capture the prompt** in each run's `state.json` so future audits don't see a wall of `"prompt": "null"`. All 9 aged terminal runs have a null prompt in the scan — we have to reconstruct intent from `processId` and the commit message.
- **Reap the orphan process file (`chunk-template-impl.js`)** in Phase 3, and at the same time decide whether the active "stuck" runs should be force-completed or aborted before the next cleanup window.

## Active-but-stale runs

20 runs in the scan have no terminal journal event. The cleanup process only
removes terminal runs, so all 20 are retained. Patterns worth noting:

- **Half are pre-chunks-workflow leftovers (ages 54–61 days).** Five runs from
  March 2026 sit in the active list because the orchestrator crashed,
  the operator pivoted, or no `RUN_COMPLETED` journal event was ever
  written. Examples: `phase-c-dependency-api-completion`
  (`01KKEM9XSF7619QXAKYB18NE66`), `acquisitions-extraction`
  (`01KKS37FFXN2SD1CN9K5XDEJG7` — has a complete `output.json` reading
  "Acquisitions projects extracted successfully" but never finalized),
  `verify-analytics-ui` (`01KM0EM31GTX6B3Y2RERZTCC59` — has a full
  PASS report with screenshot notes). These are de-facto complete;
  only the journal closure is missing.
- **One null-`processId` orphan** (`01KKEPAGSM23BM0PXXYZXKT4GJ`) from 61 days
  ago has neither a process binding nor any task. Pure noise.
- **The chunks pipeline produces "duplicate" active runs.** The chunk-impl /
  chunk-test families show clusters of multiple runs for the same chunk
  (`chunk-impl-config-bootstrap` × 4, `chunk-impl-http-session-and-request` ×
  4) because each `/chunk-run-impl` invocation creates a fresh run even when
  the previous one didn't finalize. Most of these have `taskCount: 0` and
  were almost certainly aborted by the operator at the planning breakpoint
  (R3: pipeline is human-paced). They are harmless but noisy.
- **In-flight runs.** A handful are genuinely mid-flight as of this scan
  (`release-0.4.0` `01KR8TT8P59NG56HQJDVK19BGC` with 10 tasks, the current
  `cleanup-runs` run itself, the `release-0.4.x-review` retro). These are
  expected to finalize on their own.

Bottom line: when the active list keeps growing without runs going terminal,
the chunks-CLI dashboard (`scripts/agentic/chunks list`) becomes noisy. A
future hygiene pass should either (a) backfill `RUN_COMPLETED` events for
de-facto-complete runs from March 2026, or (b) introduce a "stale" state
distinct from "active" so the cleanup process can age them out.
