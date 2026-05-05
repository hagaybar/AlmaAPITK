---
description: Drive the chunk-impl pipeline for the named chunk to completion or breakpoint
---

Run the chunk-impl pipeline for chunk `$ARGUMENTS`.

## Step 1 — Setup

If `chunks/$ARGUMENTS/status.json` already has an `implRunId` and the
stage is `impl-running`, skip the bash setup and reuse that runId
(resume the existing run from its journal).

Otherwise: run via Bash:

    scripts/agentic/chunks run-impl $ARGUMENTS

Capture the `runId` from the JSON output. If the script exits non-zero
(R8 violation, dirty tree, branch mismatch, etc.), stop and report the
error. Per CLAUDE.md R8, ALMA_PROD_API_KEY must be unset before running;
the bash entry validates this.

## Step 2 — Drive the iterate loop (in this same turn)

Loop until `status` is `"completed"` or `"failed"`:

1. Run:

       babysitter run:iterate .a5c/runs/<runId> --json --iteration <n>

   where `<n>` increments by 1 per call (start at 1).

2. Inspect the response:
   - `"status": "completed"` → exit the loop. Capture the `completionProof`.
   - `"status": "failed"` → exit the loop. Read the journal for the failure cause.
   - `"status": "waiting"` with `nextActions` → handle each effect by `kind`, then loop.

### Handling each effect kind

**`kind: "shell"`** — execute the shell command via Bash. Capture
stdout, stderr, and exit code. Write `tasks/<effectId>/output.json`
containing at least `{"exitCode": N}`. Save stdout/stderr to
`tasks/<effectId>/stdout.log` and `stderr.log` respectively. Then post:

    babysitter task:post .a5c/runs/<runId> <effectId> --status ok \
      --value tasks/<effectId>/output.json \
      --stdout-file tasks/<effectId>/stdout.log \
      --stderr-file tasks/<effectId>/stderr.log --json

**`kind: "agent"`** — spawn a fresh subagent via the Agent tool. Pass
the effect's `agent.prompt` fields (role, task, context, instructions,
outputFormat) and the `outputSchema`. Use `subagent_type:
"general-purpose"` unless the task names a specific agent. Wait for
the subagent to return its result, then post the returned JSON via
`task:post --status ok --value <file>`. If the subagent fails or
returns invalid JSON that violates `outputSchema`, post `--status
error` with an error payload describing what went wrong.

**`kind: "breakpoint"`** — read the `question` and `context` from the
effect. Surface to the operator in chat: post one message containing
the question and any relevant context. **Wait indefinitely for the
operator's reply. Never auto-proceed past a breakpoint regardless of
how many stop-hook firings or iteration nudges occur.** The hook will
repeatedly fire while you wait; ignore the nudges. Resolve the
breakpoint only when the operator explicitly replies in chat with
their decision. When the operator replies, write
`{"approved": true, "response": "<verbatim operator text>"}` to
`tasks/<effectId>/output.json` and post via `task:post --status ok
--value <file>`. Always use `--status ok` for both approve and reject;
the process .js logic interprets the response text.

## Step 3 — Report

When the loop exits, send one chat message summarizing:
- Outcome: `completed` / `failed` / `aborted-at-breakpoint`
- Number of issues merged into the integration branch (read from journal)
- Path to `chunks/$ARGUMENTS/test-recommendation.json` if completed
- Suggested next command: `/chunk-run-test $ARGUMENTS`

## Notes for the assistant

- The babysitter stop-hook drives `run:iterate` automatically between
  effects; this slash command initiates the loop and surfaces
  breakpoints to the operator. Agent isolation is preserved because
  `kind:agent` effects are dispatched via the Agent tool, which spawns
  a fresh subagent each time.
- If the conversation is interrupted mid-loop, re-running this slash
  command resumes from the journal — `run:iterate` is idempotent
  against already-resolved effects.
- Do not chain multiple chunks in one turn. One slash command = one
  chunk impl run.
