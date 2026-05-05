---
description: Drive the chunk-test pipeline for the named chunk to completion or breakpoint
---

Run the SANDBOX-test pipeline for chunk `$ARGUMENTS`.

## Step 1 — Setup

If `chunks/$ARGUMENTS/status.json` already has a `testRunId` and the
stage is `test-running` or `test-data-pending`, skip the bash setup
and reuse that runId.

Otherwise run:

    scripts/agentic/chunks run-test $ARGUMENTS

Capture the `runId` from the JSON output. The bash entry detects
whether `chunks/$ARGUMENTS/test-data.json` is pre-populated and
either binds the run to the Claude Code session (interactive mode)
or runs headless. Either way, the iterate loop below works the same.

Per CLAUDE.md R8, ALMA_PROD_API_KEY must be unset.

## Step 2 — Drive the iterate loop (in this same turn)

Loop until `status` is `"completed"` or `"failed"`:

1. Run:

       babysitter run:iterate .a5c/runs/<runId> --json --iteration <n>

2. Handle each pending effect by `kind`:

**`kind: "shell"`** — execute via Bash. Capture exit code, stdout,
stderr. Post:

    babysitter task:post .a5c/runs/<runId> <effectId> --status ok \
      --value tasks/<effectId>/output.json \
      --stdout-file tasks/<effectId>/stdout.log \
      --stderr-file tasks/<effectId>/stderr.log --json

**`kind: "agent"`** — spawn a fresh subagent via the Agent tool. Pass
the effect's `agent.prompt` fields and `outputSchema`. Post the
subagent's returned JSON via `task:post`. On subagent failure or
schema violation, post `--status error`.

**`kind: "breakpoint"`** — the chunk-test process has one headline
breakpoint: the **fixture interview**. Read `question` and `context`,
which will list every fixture key the chunk's tests need (e.g.
`test_user_id`, `test_bib_mms_id`). Surface in chat as one message
listing the keys; ask the operator for values. **Wait indefinitely
for the operator's reply. Never auto-proceed regardless of how many
stop-hook firings or iteration nudges occur.** The hook will keep
firing; ignore the nudges. When the operator replies, build the JSON
`{<key>: <value>, ...}` from their reply, write to
`tasks/<effectId>/output.json` as
`{"approved": true, "response": <json>}`, post via `task:post
--status ok --value <file>`. Per R9, do not echo the operator's
values into committed files or messages — they may contain real IDs.

## Step 3 — Report

When the loop exits, send one chat message summarizing:
- Outcome: `completed` / `failed` / `aborted-at-breakpoint`
- Test counts: passed / failed / skipped (read from
  `chunks/$ARGUMENTS/test-results.json`)
- Suggested next action: if all tests passed, ask operator whether
  to open a PR; if any failed, surface the failure details for
  operator decision.

## Notes for the assistant

- Per R9, never echo operator-supplied fixture values into chat
  messages or commit messages. Only refer to them generically
  ("the supplied test user", "the test bib").
- The babysitter stop-hook drives `run:iterate` automatically between
  effects; this slash command initiates the loop and surfaces the
  fixture-interview breakpoint to the operator.
- Do not auto-open a PR. PR creation is a separate operator action.
