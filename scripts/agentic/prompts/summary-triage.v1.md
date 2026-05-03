# Summary-and-Triage Prompt — v1

You aggregate one chunk's test results into the per-issue triage outcomes per spec §8.

## Inputs

- `chunks/<name>/test-recommendation.json` — the plan
- `chunks/<name>/test-results.json` — what actually happened
- `chunks/<name>/manifest.json` — issue list

## For each issue in the chunk, decide

| Outcome | Conditions (all must hold) |
|---|---|
| **Auto-close** | Every AC is in `acceptanceMapping`; every mapped test passed; `unmappable[]` is empty for this issue; no test was `skipped`; no warnings recorded. |
| `tested:passing-needs-review` | All tests for this issue passed, BUT some AC is in `unmappable[]` OR a test was skipped/warned. |
| `tested:failing` | Any test for this issue failed OR cleanup failed on a state-changing test. |

## Actions per outcome

- **Auto-close:** comment `## Test summary (chunk <name>)` with results, link to PR, then `gh issue close <N>`.
- **passing-needs-review:** comment same summary, `gh issue edit <N> --add-label "tested:passing-needs-review"`. Do NOT close.
- **failing:** comment summary + failure details, `gh issue edit <N> --add-label "tested:failing"`. Do NOT close.

## Inviolable rules

- **R2:** never `gh pr merge`. The PR stays draft.
- **R4:** auto-close only on the strict conditions above. Anything ambiguous → labeled, not closed.
- **R1:** never push to or interact with `prod`.

## Output

Return JSON:

```json
{
  "perIssue": [{"number": 3, "outcome": "auto-close|needs-review|failing", "actionsApplied": ["..."]}],
  "prUrl": "https://...",
  "logRow": {"chunk_name": "...", "issue_numbers": [3, 4], "passed": 4, "failed": 0}
}
```
