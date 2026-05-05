# Chunks Orchestration Redesign — Slash-Command Entry Point — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/chunk-run-impl <name>` and `/chunk-run-test <name>` slash commands that drive the existing babysitter pipeline to completion or breakpoint inside a single Claude Code turn, eliminating the "babysitting the babysitter" problem where shell-invoked `chunks run-impl` left runs stalled at `RUN_CREATED`.

**Architecture:** Two new project-level slash commands at `.claude/commands/`. Slash command bodies are saved prompts that tell Claude to (1) run the existing bash setup that creates the babysitter run, (2) drive `babysitter run:iterate` directly in the same turn, executing shell effects via Bash and delegating agent effects to fresh subagents via the Agent tool, surfacing breakpoints in chat. Bash subcommands stay as fallback. The `.a5c/processes/*.js` files are unchanged.

**Tech Stack:** Bash, Python 3.12 + pytest, Markdown, Babysitter SDK (existing).

**Spec:** `docs/superpowers/specs/2026-05-05-chunks-orchestration-redesign-design.md` (committed in `446167b`).

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `.claude/commands/chunk-run-impl.md` | Create | Slash-command body — saved prompt that drives chunk-impl loop |
| `.claude/commands/chunk-run-test.md` | Create | Slash-command body — saved prompt that drives chunk-test loop |
| `scripts/agentic/chunks` | Modify | Capture runId from `babysitter run:create --json`, persist as `implRunId` / `testRunId` in status.json, print operator hint |
| `tests/agentic/test_chunk_slash_commands.py` | Create | Marker assertions on slash-command files |
| `tests/agentic/test_chunks_cli_runid.py` | Create | Integration test: stubbed `babysitter` binary verifies `run-impl` writes `implRunId` to status.json |
| `docs/CHUNK_PLAYBOOK.md` | Modify | Recommend slash commands as primary; document manual-driving fallback |
| `CLAUDE.md` | Modify | Add slash commands to CLI cheat sheet |
| `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md` | Modify | One paragraph in §11 noting chunk runs are driven via slash commands |

---

## Task 1: Slash command file — `chunk-run-impl`

**Files:**
- Create: `.claude/commands/chunk-run-impl.md`
- Test: `tests/agentic/test_chunk_slash_commands.py`

- [ ] **Step 1: Write the failing test**

Create `tests/agentic/test_chunk_slash_commands.py`:

```python
"""Tests for project-level slash commands that drive chunk runs."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS = REPO_ROOT / ".claude" / "commands"


def test_chunk_run_impl_exists():
    p = COMMANDS / "chunk-run-impl.md"
    assert p.exists(), f"missing slash-command file: {p}"


def test_chunk_run_impl_body_has_required_markers():
    body = (COMMANDS / "chunk-run-impl.md").read_text()
    # Argument substitution
    assert "$ARGUMENTS" in body, "slash command must use $ARGUMENTS"
    # Bash setup
    assert "scripts/agentic/chunks run-impl" in body
    # Iterate-loop driving
    assert "babysitter run:iterate" in body
    assert "task:post" in body
    # Subagent isolation for kind:agent effects
    assert "Agent tool" in body
    # Resume protocol
    assert "implRunId" in body
    # R8 reminder
    assert "ALMA_PROD_API_KEY" in body
```

- [ ] **Step 2: Run test to verify it fails**

```
poetry run pytest tests/agentic/test_chunk_slash_commands.py::test_chunk_run_impl_exists -v
```

Expected: FAIL with `missing slash-command file`.

- [ ] **Step 3: Create the slash-command file**

Create `.claude/commands/chunk-run-impl.md`:

```markdown
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
the question and any relevant context. Wait for the operator's reply.
When the operator replies, write
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

- This bypasses the babysit skill's "STOP between iterations" rule
  because no babysitter stop-hook is configured in this repo. Agent
  isolation is preserved by spawning fresh subagents for `kind:agent`
  effects via the Agent tool.
- If the conversation is interrupted mid-loop, re-running this slash
  command resumes from the journal — `run:iterate` is idempotent
  against already-resolved effects.
- Do not chain multiple chunks in one turn. One slash command = one
  chunk impl run.
```

- [ ] **Step 4: Run tests to verify they pass**

```
poetry run pytest tests/agentic/test_chunk_slash_commands.py -v
```

Expected: both `test_chunk_run_impl_exists` and
`test_chunk_run_impl_body_has_required_markers` PASS.

- [ ] **Step 5: Commit**

```
git add tests/agentic/test_chunk_slash_commands.py .claude/commands/chunk-run-impl.md
git commit -m "$(cat <<'EOF'
feat(chunks): add /chunk-run-impl slash command

Saved prompt that drives the existing chunk-impl babysitter pipeline
to completion or breakpoint inside one Claude Code turn. Operator
types the slash command in chat instead of running the bash entry
from a terminal, eliminating the RUN_CREATED stall.

Refs the chunks-orchestration-redesign spec.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Slash command file — `chunk-run-test`

**Files:**
- Create: `.claude/commands/chunk-run-test.md`
- Test: extend `tests/agentic/test_chunk_slash_commands.py`

- [ ] **Step 1: Add failing tests for chunk-run-test**

Append to `tests/agentic/test_chunk_slash_commands.py`:

```python
def test_chunk_run_test_exists():
    p = COMMANDS / "chunk-run-test.md"
    assert p.exists(), f"missing slash-command file: {p}"


def test_chunk_run_test_body_has_required_markers():
    body = (COMMANDS / "chunk-run-test.md").read_text()
    assert "$ARGUMENTS" in body
    assert "scripts/agentic/chunks run-test" in body
    assert "babysitter run:iterate" in body
    assert "task:post" in body
    assert "Agent tool" in body
    assert "testRunId" in body
    assert "ALMA_PROD_API_KEY" in body
    # The fixture interview is the headline breakpoint of run-test
    assert "fixture" in body.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```
poetry run pytest tests/agentic/test_chunk_slash_commands.py::test_chunk_run_test_exists -v
```

Expected: FAIL with `missing slash-command file`.

- [ ] **Step 3: Create the slash-command file**

Create `.claude/commands/chunk-run-test.md`:

```markdown
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
listing the keys; ask the operator for values. When the operator
replies, build the JSON `{<key>: <value>, ...}` from their reply,
write to `tasks/<effectId>/output.json` as
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
- Bypasses the babysit skill's "STOP between iterations" rule for
  the same reasons documented in `/chunk-run-impl`.
- Do not auto-open a PR. PR creation is a separate operator action.
```

- [ ] **Step 4: Run tests to verify they pass**

```
poetry run pytest tests/agentic/test_chunk_slash_commands.py -v
```

Expected: all four tests PASS.

- [ ] **Step 5: Commit**

```
git add tests/agentic/test_chunk_slash_commands.py .claude/commands/chunk-run-test.md
git commit -m "$(cat <<'EOF'
feat(chunks): add /chunk-run-test slash command

Symmetric to /chunk-run-impl: drives the existing chunk-test
babysitter pipeline (fixture interview → SANDBOX tests → results)
to completion or breakpoint inside one Claude Code turn.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Bash entry — persist `implRunId` in `run-impl`

**Files:**
- Modify: `scripts/agentic/chunks` (lines 167–195)
- Test: `tests/agentic/test_chunks_cli_runid.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/agentic/test_chunks_cli_runid.py`:

```python
"""Integration tests: chunks CLI must persist runId fields to status.json."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "agentic" / "chunks"


def _make_chunk(chunks_dir: Path, name: str, issue_number: int = 1) -> Path:
    """Create a minimally-valid chunk directory (manifest + status.json)."""
    chunk_dir = chunks_dir / name
    chunk_dir.mkdir(parents=True)
    manifest = {
        "chunk": name,
        "issues": [{"number": issue_number, "title": "test", "body_raw": ""}],
    }
    (chunk_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Bootstrap status.json via init_status helper
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.agentic.chunk_status import init_status
    init_status(chunk_dir, chunk_name=name, issues=[issue_number])
    return chunk_dir


def _stub_babysitter(bin_dir: Path, run_id: str) -> Path:
    """Drop a fake `babysitter` script that prints {"runId": "<id>"} for any args."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "babysitter"
    stub.write_text(
        f'#!/usr/bin/env bash\n'
        f'echo \'{{"runId": "{run_id}"}}\'\n'
    )
    stub.chmod(0o755)
    return stub


def _git_repo(repo_path: Path, branch: str) -> None:
    """Initialize a git repo and create the chunk integration branch."""
    subprocess.run(["git", "init", "-q"], cwd=str(repo_path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo_path), check=True)
    (repo_path / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=str(repo_path), check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=str(repo_path), check=True)
    subprocess.run(["git", "checkout", "-q", "-b", branch], cwd=str(repo_path), check=True)


def test_run_impl_persists_implRunId(tmp_path):
    """run-impl must capture the runId from babysitter and write it to status.json."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_repo(repo, "chunk/test-chunk")
    chunks = repo / "chunks"
    _make_chunk(chunks, "test-chunk")
    _stub_babysitter(tmp_path / "bin", "test-run-12345")

    env = os.environ.copy()
    env.pop("ALMA_PROD_API_KEY", None)
    env["CHUNKS_DIR"] = str(chunks)
    env["REPO_ROOT"] = str(repo)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"

    r = subprocess.run(
        [str(CLI), "run-impl", "test-chunk"],
        capture_output=True, text=True, env=env, cwd=str(repo),
    )
    assert r.returncode == 0, f"chunks run-impl failed: {r.stderr}"
    status = json.loads((chunks / "test-chunk" / "status.json").read_text())
    assert status.get("implRunId") == "test-run-12345", (
        f"expected implRunId=test-run-12345 in status.json, got {status}"
    )


def test_run_test_persists_testRunId(tmp_path):
    """run-test must capture the runId from babysitter and write it to status.json."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_repo(repo, "chunk/test-chunk")
    chunks = repo / "chunks"
    _make_chunk(chunks, "test-chunk")
    # run-test peeks at test-recommendation.json and test-data.json to decide
    # headless mode. Provide neither so it picks the interactive path.
    _stub_babysitter(tmp_path / "bin", "test-run-67890")

    env = os.environ.copy()
    env.pop("ALMA_PROD_API_KEY", None)
    env["CHUNKS_DIR"] = str(chunks)
    env["REPO_ROOT"] = str(repo)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"

    r = subprocess.run(
        [str(CLI), "run-test", "test-chunk"],
        capture_output=True, text=True, env=env, cwd=str(repo),
    )
    assert r.returncode == 0, f"chunks run-test failed: {r.stderr}"
    status = json.loads((chunks / "test-chunk" / "status.json").read_text())
    assert status.get("testRunId") == "test-run-67890", (
        f"expected testRunId=test-run-67890 in status.json, got {status}"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```
poetry run pytest tests/agentic/test_chunks_cli_runid.py -v
```

Expected: both tests FAIL — current bash entry does not capture the
runId or pass it to `transition()`. The status.json has no
`implRunId` / `testRunId` field.

- [ ] **Step 3: Modify `scripts/agentic/chunks` `run-impl` block**

Replace lines 167–195 (the `run-impl` case branch) with:

```bash
  run-impl)
    name="${1:?run-impl: chunk name required}"
    cd "$REPO_ROOT"
    # Ensure the integration branch exists
    if ! git rev-parse --verify "chunk/$name" >/dev/null 2>&1; then
      git checkout main
      git checkout -b "chunk/$name"
    fi
    git checkout "chunk/$name"
    inputs="$(mktemp --suffix=.json)"
    cat > "$inputs" <<EOF
{"chunkName": "$name", "repoRoot": "$REPO_ROOT", "maxAttempts": 3}
EOF
    run_create_output="$(babysitter run:create \
      --process-id "chunk-impl-$name" \
      --entry "$REPO_ROOT/.a5c/processes/chunk-template-impl.js#process" \
      --inputs "$inputs" \
      --prompt "Implement chunk $name on integration branch" \
      --harness claude-code \
      --json)"
    echo "$run_create_output"
    run_id="$("$PY" -c 'import json,sys; print(json.load(sys.stdin)["runId"])' <<<"$run_create_output")"
    "$PY" - "$CHUNKS_DIR" "$name" "$run_id" <<'PYEOF'
import sys
from pathlib import Path
from scripts.agentic.chunk_status import transition
transition(Path(sys.argv[1]) / sys.argv[2], "impl-running",
           "implementation babysitter run created",
           "drive via /chunk-run-impl in chat, or babysitter run:iterate manually",
           implRunId=sys.argv[3])
PYEOF
    cat >&2 <<EOF

Run created. To drive it from a Claude Code session, type in chat:
    /chunk-run-impl $name
Driving manually requires babysitter run:iterate calls; see
docs/CHUNK_PLAYBOOK.md "manual driving fallback".
EOF
    ;;
```

- [ ] **Step 4: Run tests to verify run-impl test passes**

```
poetry run pytest tests/agentic/test_chunks_cli_runid.py::test_run_impl_persists_implRunId -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add tests/agentic/test_chunks_cli_runid.py scripts/agentic/chunks
git commit -m "$(cat <<'EOF'
feat(chunks): persist implRunId from run-impl to status.json

Capture the runId from babysitter run:create and write it to
chunks/<name>/status.json so /chunk-run-impl can resume an existing
run instead of creating a new one when re-typed mid-flight.

Also prints an operator hint pointing at the slash command.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Bash entry — persist `testRunId` in `run-test`

**Files:**
- Modify: `scripts/agentic/chunks` (lines 197–266)

- [ ] **Step 1: Verify the run-test test fails**

```
poetry run pytest tests/agentic/test_chunks_cli_runid.py::test_run_test_persists_testRunId -v
```

Expected: FAIL — run-test bash block does not capture runId yet.

- [ ] **Step 2: Modify `scripts/agentic/chunks` `run-test` block**

Replace lines 197–266 (the `run-test` case branch) with:

```bash
  run-test)
    name="${1:?run-test: chunk name required}"
    cd "$REPO_ROOT"

    # Issue #86: when test-data.json is pre-populated with every fixture key
    # required by test-recommendation.json, skip the --harness claude-code
    # binding so the run can proceed headless from any terminal.
    headless=0
    if "$PY" - "$CHUNKS_DIR" "$name" <<'PYEOF'
import json, sys
from pathlib import Path
try:
    chunk_dir = Path(sys.argv[1]) / sys.argv[2]
    rec_path = chunk_dir / "test-recommendation.json"
    data_path = chunk_dir / "test-data.json"
    if not rec_path.exists() or not data_path.exists():
        sys.exit(1)
    rec = json.loads(rec_path.read_text())
    data = json.loads(data_path.read_text())
    required = {
        f["key"]
        for issue in rec.get("issues", [])
        for t in issue.get("tests", [])
        for f in t.get("needsHumanInput", [])
    }
    sys.exit(0 if required.issubset(set(data.keys())) else 1)
except Exception:
    sys.exit(1)
PYEOF
    then
      headless=1
      echo "chunks: test-data.json is complete; launching headless run-test (no Claude Code session bound)"
    fi

    inputs="$(mktemp --suffix=.json)"
    cat > "$inputs" <<EOF
{"chunkName": "$name", "repoRoot": "$REPO_ROOT"}
EOF
    if [[ "$headless" -eq 1 ]]; then
      run_create_output="$(babysitter run:create \
        --process-id "chunk-test-$name" \
        --entry "$REPO_ROOT/.a5c/processes/chunk-test.js#process" \
        --inputs "$inputs" \
        --prompt "Run SANDBOX tests for chunk $name" \
        --json)"
    else
      run_create_output="$(babysitter run:create \
        --process-id "chunk-test-$name" \
        --entry "$REPO_ROOT/.a5c/processes/chunk-test.js#process" \
        --inputs "$inputs" \
        --prompt "Run SANDBOX tests for chunk $name" \
        --harness claude-code \
        --json)"
    fi
    echo "$run_create_output"
    run_id="$("$PY" -c 'import json,sys; print(json.load(sys.stdin)["runId"])' <<<"$run_create_output")"
    "$PY" - "$CHUNKS_DIR" "$name" "$headless" "$run_id" <<'PYEOF'
import sys
from pathlib import Path
from scripts.agentic.chunk_status import transition
headless = sys.argv[3] == "1"
if headless:
    last_event = "test process started (headless: pre-supplied test-data.json)"
    next_action = "drive via /chunk-run-test or babysitter run:iterate"
else:
    last_event = "test process started; awaiting fixture interview"
    next_action = "drive via /chunk-run-test in chat to answer fixture interview"
transition(Path(sys.argv[1]) / sys.argv[2], "test-data-pending",
           last_event, next_action,
           testRunId=sys.argv[4])
PYEOF
    cat >&2 <<EOF

Run created. To drive it from a Claude Code session, type in chat:
    /chunk-run-test $name
Driving manually requires babysitter run:iterate calls; see
docs/CHUNK_PLAYBOOK.md "manual driving fallback".
EOF
    ;;
```

- [ ] **Step 3: Run tests to verify both runId tests pass**

```
poetry run pytest tests/agentic/test_chunks_cli_runid.py -v
```

Expected: both tests PASS.

- [ ] **Step 4: Run the full chunks-CLI test suite to verify no regression**

```
poetry run pytest tests/agentic/ -v
```

Expected: all tests PASS (existing `test_chunks_cli.py` tests untouched).

- [ ] **Step 5: Commit**

```
git add scripts/agentic/chunks
git commit -m "$(cat <<'EOF'
feat(chunks): persist testRunId from run-test to status.json

Symmetric change to run-impl: capture runId from babysitter
run:create and write to chunks/<name>/status.json so
/chunk-run-test can resume mid-flight. Operator hint added.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Update `docs/CHUNK_PLAYBOOK.md`

**Files:**
- Modify: `docs/CHUNK_PLAYBOOK.md`

- [ ] **Step 1: Read current playbook to find the relevant section**

```
grep -n "run-impl\|run-test\|chunks run" docs/CHUNK_PLAYBOOK.md | head -20
```

Note the line numbers of:
- The "Run the implementation" section header (around line 44)
- The "Run the tests" section (around line 80)

- [ ] **Step 2: Modify the playbook**

For the implementation section, change the "Trigger the run" code block from:

```bash
scripts/agentic/chunks run-impl http-foundation
```

to:

````markdown
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
````

Apply the equivalent change to the "Run the tests" section: primary
path is `/chunk-run-test http-foundation`; fallback is the bash
subcommand.

Add a new subsection at the end of the playbook titled **"Manual driving
fallback"** with:

````markdown
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
````

- [ ] **Step 3: Commit**

```
git add docs/CHUNK_PLAYBOOK.md
git commit -m "$(cat <<'EOF'
docs(playbook): recommend slash commands as primary chunk-run path

Updates the run-impl and run-test sections to recommend
/chunk-run-impl and /chunk-run-test (which drive the iterate loop
to completion or breakpoint) as the primary path. Bash subcommands
are demoted to "fallback when not in Claude Code".

Adds a "Manual driving fallback" subsection documenting how to drive
a run by hand for chunks with only shell effects.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Update `CLAUDE.md` CLI cheat sheet

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Modify the CLI cheat sheet**

In `CLAUDE.md`, find the "CLI cheat sheet" block (lines 16–24).
Replace the lines for `run-impl` and `run-test`:

From:
```markdown
- `run-impl <name>` — trigger per-chunk implementation babysitter run
- `run-test <name>` — trigger generic interactive testing process
```

To:
```markdown
- `run-impl <name>` — bash entry that creates an impl babysitter run (does NOT drive iteration; type `/chunk-run-impl <name>` in chat for the driven path)
- `run-test <name>` — bash entry that creates a test babysitter run (does NOT drive iteration; type `/chunk-run-test <name>` in chat for the driven path)
```

Add a new section under the cheat sheet:

```markdown
**Slash commands** (chat-driven, recommended):
- `/chunk-run-impl <name>` — drive the impl pipeline for a chunk to completion or breakpoint
- `/chunk-run-test <name>` — drive the SANDBOX-test pipeline for a chunk to completion or breakpoint
```

- [ ] **Step 2: Commit**

```
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(claude-md): document /chunk-run-impl and /chunk-run-test slash commands

Adds the slash commands to the CLI cheat sheet and clarifies that
the bash run-impl/run-test subcommands only create the babysitter
run; driving requires either the slash command or manual iteration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Update `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md`

**Files:**
- Modify: `docs/AGENTIC_ORCHESTRATION_HANDBOOK.md` (§11 = "Operational setup", around line 540)

- [ ] **Step 1: Locate §11**

```
grep -n "^## 11\|^# 11\|## 11\." docs/AGENTIC_ORCHESTRATION_HANDBOOK.md | head -5
```

- [ ] **Step 2: Add a paragraph at the end of §11**

Insert at the end of the §11 section (just before §12 starts):

```markdown
### 11.x — Driving chunk runs

Chunk runs are created by `scripts/agentic/chunks run-impl <name>`
(impl phase) or `scripts/agentic/chunks run-test <name>` (SANDBOX-test
phase). The bash entries call `babysitter run:create` and exit; they
do NOT drive `run:iterate`. Driving is done via two project-level
slash commands:

- `/chunk-run-impl <name>` — saved prompt that loops on `run:iterate`,
  executes shell effects via Bash, delegates `kind:agent` effects to
  fresh subagents via the Agent tool, and surfaces breakpoints in
  chat. Runs entirely in one Claude Code turn.
- `/chunk-run-test <name>` — symmetric for the test phase. The
  fixture-interview breakpoint is surfaced in chat; the operator
  replies with values for each fixture key.

Both slash commands resume an existing run if `chunks/<name>/status.json`
already has an `implRunId` / `testRunId` set, by reading the journal
under `.a5c/runs/<runId>/`. Re-typing the slash command after an
interrupt is idempotent.

The `babysit` skill's "STOP between iterations" rule is intentionally
bypassed because no babysitter-specific Claude Code stop-hook is
configured in this repo. Agent isolation is preserved by spawning
fresh subagents for `kind:agent` effects.
```

- [ ] **Step 3: Commit**

```
git add docs/AGENTIC_ORCHESTRATION_HANDBOOK.md
git commit -m "$(cat <<'EOF'
docs(handbook): document slash-command driving for chunk runs

Adds §11.x explaining that chunk runs are driven via
/chunk-run-impl and /chunk-run-test slash commands, including the
deliberate bypass of the babysit skill's STOP-between-iterations
rule and how agent isolation is preserved.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Manual end-to-end validation on `chunk-pipeline-docs-coupling`

**Files:** none (validation activity)

This is the empirical check from spec §5. The chunk
`chunk-pipeline-docs-coupling` was already defined and is sitting at
stage `impl-running` (run `01KQV9WSPT9FGF5JHWK231D8JN`). It has one
issue (#93). It is the smallest viable test surface.

- [ ] **Step 1: Decide whether to abort and re-run, or resume**

Run:
```
scripts/agentic/chunks status chunk-pipeline-docs-coupling
```

The current `status.json` does NOT have `implRunId` set (the
persistence change landed in Task 3 but the run was created before
that). Two options:

- **Abort and re-create.** Cleaner test of the new flow:
  ```
  scripts/agentic/chunks abort chunk-pipeline-docs-coupling
  rm -rf chunks/chunk-pipeline-docs-coupling
  scripts/agentic/chunks define --name chunk-pipeline-docs-coupling --issues 93
  ```
  Then validate from a clean start.

- **Resume the existing run manually.** Add `implRunId:
  "01KQV9WSPT9FGF5JHWK231D8JN"` to the existing status.json, then
  run `/chunk-run-impl chunk-pipeline-docs-coupling`. Tests resume
  semantics specifically.

Default: **abort and re-create**, unless the operator wants to
exercise the resume path.

- [ ] **Step 2: Operator types the slash command in chat**

```
/chunk-run-impl chunk-pipeline-docs-coupling
```

The assistant should:
1. Run the bash setup, capture runId.
2. Loop on `run:iterate`, executing shell effects, posting results,
   delegating to subagents for the `implement` task.
3. Surface any breakpoint in chat.
4. Report final outcome.

- [ ] **Step 3: Record findings**

Write a short note to
`docs/superpowers/specs/2026-05-05-chunks-orchestration-redesign-design.md`
under a new "## 10. Validation findings" section. Cover:

- Did the slash command body work as a prompt? (Y/N)
- Did the iterate loop drive without operator pings between effects?
  (Y/N)
- Did the subagent for `implement` produce valid output? (Y/N)
- Did any breakpoint fire? If yes, did the chat-based reply protocol
  work? (Y/N)
- Final stage reached. Was it `impl-done`?
- Token usage observation (was the conversation tight or did it
  approach context limits?)
- Anything surprising.

- [ ] **Step 4: Commit findings**

```
git add docs/superpowers/specs/2026-05-05-chunks-orchestration-redesign-design.md
git commit -m "$(cat <<'EOF'
docs(specs): record validation findings for chunks orchestration redesign

Outcome of the end-to-end validation run on chunk-pipeline-docs-
coupling. <PASS/FAIL>; <one-line summary>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Decide on rollout based on findings**

If **PASS** → proceed with normal chunk runs using the slash commands.
The implementation is complete.

If **FAIL** → revert as documented in spec §5 "Rollback", then
revisit either Approach A+hook (configure a project-level Stop hook)
or Approach B (drop babysitter). Update the spec with what was
learned.

---

## Self-Review

**Spec coverage check (against
`docs/superpowers/specs/2026-05-05-chunks-orchestration-redesign-design.md`):**

| Spec requirement | Implemented in |
|---|---|
| §4.1 architecture: slash commands → bash → babysit-driven loop | Tasks 1–4 |
| §4.2 operator flow: type one slash command per phase | Tasks 1, 2 |
| §4.3 slash command body for chunk-run-impl | Task 1 |
| §4.3 slash command body for chunk-run-test | Task 2 |
| §4.4 bash entry persists runId | Tasks 3, 4 |
| §4.4 bash entry prints operator hint | Tasks 3, 4 |
| §4.5 doc updates (playbook, CLAUDE.md, handbook) | Tasks 5, 6, 7 |
| §4.6 tests: marker assertions on slash commands | Task 1 (extended in 2) |
| §4.6 tests: runId persistence | Task 3 (extended in 4) |
| §5 validation plan on chunk-pipeline-docs-coupling | Task 8 |

All spec sections are covered.

**Placeholder scan:** none. Every step has exact file paths, exact
commands, and complete code where applicable.

**Type consistency:** the slash-command bodies reference `implRunId`
(Task 1, 3) and `testRunId` (Task 2, 4) consistently. The
`transition()` calls use these as `**extra` kwargs, matching the
existing signature in `scripts/agentic/chunk_status.py`.

---

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-05-05-chunks-orchestration-redesign.md`.
Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per
   task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using
   executing-plans, batch execution with checkpoints.

Which approach?
