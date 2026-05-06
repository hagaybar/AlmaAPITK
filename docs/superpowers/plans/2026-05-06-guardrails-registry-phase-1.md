# Guardrails Registry — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the brittle `files_to_touch` + R7 scope-check gate with a small structured guardrails registry so chunk #22 (and future foundation chunks) can be re-run without false-positive scope-gate failures, and so future rule additions have a single home.

**Architecture:** A new `guardrails.json` at repo root holds two top-level sections — `enforced` (mechanical rules the harness enforces as gates) and `instructed` (text rendered into agent prompts at the right stage). Phase 1 populates `enforced.deny_paths` only; `instructed` is stubbed for forward compatibility but not yet read by the runtime. A new module `scripts/agentic/guardrails.py` loads/validates the registry and provides `match_deny_paths(diff_files)`. The chunk-impl process replaces `scopeCheckTask` with a `denyPathsTask` that calls the new module. `files_to_touch` stays in issue bodies and `manifest.json` as informational input to the implement agent — no longer mechanically enforced. `scope_check.py` and its tests remain in the tree (not deleted) so any external scripts importing it keep working; removal is deferred to Phase 5.

**Tech Stack:** Python 3.12 + pytest, JS process file (`.a5c/processes/chunk-template-impl.js`), Markdown prompt template, JSON for the registry.

---

## Phase 1 Scope (this plan)

- New `guardrails.json` with `enforced.deny_paths` populated, `instructed` section stubbed.
- New `scripts/agentic/guardrails.py` with loader + deny-path matcher.
- Replace `scopeCheckTask` with `denyPathsTask` in the chunk-impl process.
- Soften R7 wording in `scripts/agentic/prompts/implement.v1.md` (filesToTouch becomes informational guidance, not a hard gate).
- Update `CLAUDE.md`, `docs/CHUNK_PLAYBOOK.md`, and `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md` so the R7 references match reality.

## Phase 1 Out of Scope (deferred to follow-up plans)

- **Phase 2:** diff-size budget gate; commit-message regex (Refs vs Closes/Fixes/Resolves).
- **Phase 3:** mechanical R9 redaction patterns (regex over commit messages, PR bodies, issue comments).
- **Phase 4:** post-implement critique-pass agent that reads diff vs. AC.
- **Phase 5:** remove `files_to_touch` from `manifest.json` and from issue bodies; delete `scope_check.py` and its tests.

## Risk Mitigation (the "no new blockers" constraint)

- **`scope_check.py` and `tests/agentic/test_scope_check.py` are NOT deleted.** Removing them risks breaking imports we haven't catalogued. Phase 5 will retire them once the new system has shipped a few real chunks.
- **`files_to_touch` is NOT removed from the manifest or issue bodies.** It stays as guidance the implement agent can read. Phase 5 retires it once the critique stage replaces its review-aid function.
- **`enforced.deny_paths` starts deliberately narrow:** `.github/` and `secrets/` only. Anything broader (e.g., `pyproject.toml`) would block legitimate Poetry version bumps and dep changes — out of scope here.
- **Schema validates on load.** Malformed `guardrails.json` raises with a clear error message naming the bad field, not a stack trace from json.load.
- **Pipeline-level smoke test before merge.** Run `scripts/agentic/chunks define --name guardrails-smoke --issues 22 --dry-run` (or its closest equivalent) and verify the new gate is in the journal flow without errors.
- **Don't change journal/effect schemas.** `denyPathsTask` posts the same `{"exitCode": N}` shape as every other shell task. Existing run logs and replay logic are unaffected.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `guardrails.json` | CREATE (repo root) | Single source of truth for mechanical rules + stage-routed instructions. Phase 1 populates `enforced.deny_paths`; the `instructed` section is stubbed for forward compatibility. |
| `scripts/agentic/guardrails.py` | CREATE | Pure-Python loader + matcher. No I/O beyond reading the JSON. Importable as `from scripts.agentic.guardrails import load_guardrails, match_deny_paths`. CLI entrypoint: `python -m scripts.agentic.guardrails deny-paths` reads `{"diff_files": [...]}` from stdin and emits a pass/fail JSON. |
| `tests/agentic/test_guardrails.py` | CREATE | Unit tests for the loader (valid + malformed schema), matcher (positive + negative cases), and CLI (pass + fail + bad-payload). |
| `.a5c/processes/chunk-template-impl.js` | MODIFY (~30 lines) | Replace `scopeCheckTask` definition with `denyPathsTask`. Update gate chain in main loop to use the new task. |
| `scripts/agentic/prompts/implement.v1.md` | MODIFY (~5 lines) | Soften R7 in the "Inviolable rules" list: filesToTouch becomes guidance, not a hard rule. Add a pointer to `guardrails.json` for the canonical rule list. |
| `CLAUDE.md` | MODIFY (~10 lines) | Replace R7 description with the new mechanism (deny-paths gate, files_to_touch as guidance). |
| `docs/CHUNK_PLAYBOOK.md` | MODIFY (~3 lines) | Update R7 row in the rules table. Update gate-chain description. |
| `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md` | MODIFY (~5 lines) | Note that R7 has been superseded by the guardrails registry; link to this plan and the new design spec. |
| `scripts/agentic/scope_check.py` | UNCHANGED | Stays in tree; mark deprecated in module docstring only. |
| `tests/agentic/test_scope_check.py` | UNCHANGED | Tests still pass; kept so the deprecation can be reverted if needed. |

---

## Tasks

### Task 0: Create the feature branch

**Files:** none modified; this sets up the working branch.

- [ ] **Step 1: Verify clean tree on `main`**

Run: `git status`

Expected: `On branch main`, `nothing to commit, working tree clean` (untracked files in `chunks/config-bootstrap/` are fine — those are pre-existing).

- [ ] **Step 2: Create and switch to the feature branch**

Run: `git checkout -b feat/guardrails-registry-phase-1`

Expected: `Switched to a new branch 'feat/guardrails-registry-phase-1'`.

(No commit — branch creation is metadata only.)

---

### Task 1: Create the `guardrails.json` registry skeleton

**Files:**
- Create: `guardrails.json`

- [ ] **Step 1: Write the registry**

Create `guardrails.json` at repo root with exactly this content:

```json
{
  "version": 1,
  "enforced": {
    "deny_paths": [
      ".github/",
      "secrets/"
    ]
  },
  "instructed": {
    "implement": [],
    "critique": []
  }
}
```

- [ ] **Step 2: Verify it parses**

Run: `python -c "import json; print(json.load(open('guardrails.json'))['version'])"`

Expected output: `1`

- [ ] **Step 3: Commit**

```bash
git add guardrails.json
git commit -m "feat(agentic): introduce guardrails.json registry (Phase 1 skeleton)"
```

---

### Task 2: Write failing tests for `load_guardrails`

**Files:**
- Test: `tests/agentic/test_guardrails.py`

- [ ] **Step 1: Create the test file with three loader tests**

```python
"""Tests for scripts.agentic.guardrails (Phase 1 of the guardrails registry)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_load_guardrails_returns_parsed_dict(tmp_path: Path):
    from scripts.agentic.guardrails import load_guardrails

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({
        "version": 1,
        "enforced": {"deny_paths": [".github/"]},
        "instructed": {"implement": [], "critique": []},
    }))

    data = load_guardrails(registry)
    assert data["version"] == 1
    assert data["enforced"]["deny_paths"] == [".github/"]


def test_load_guardrails_rejects_missing_version(tmp_path: Path):
    from scripts.agentic.guardrails import GuardrailsSchemaError, load_guardrails

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({"enforced": {"deny_paths": []}, "instructed": {}}))

    with pytest.raises(GuardrailsSchemaError) as exc_info:
        load_guardrails(registry)
    assert "version" in str(exc_info.value)


def test_load_guardrails_rejects_unknown_version(tmp_path: Path):
    from scripts.agentic.guardrails import GuardrailsSchemaError, load_guardrails

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({
        "version": 99,
        "enforced": {"deny_paths": []},
        "instructed": {},
    }))

    with pytest.raises(GuardrailsSchemaError) as exc_info:
        load_guardrails(registry)
    assert "version" in str(exc_info.value)
```

- [ ] **Step 2: Run tests, verify they fail with ModuleNotFoundError**

Run: `poetry run pytest tests/agentic/test_guardrails.py -v`

Expected: 3 errors with `ModuleNotFoundError: No module named 'scripts.agentic.guardrails'`.

---

### Task 3: Implement `load_guardrails` to make Task 2 tests pass

**Files:**
- Create: `scripts/agentic/guardrails.py`

- [ ] **Step 1: Write the loader**

Create `scripts/agentic/guardrails.py`:

```python
"""Guardrails registry — Phase 1.

Loads `guardrails.json` (a small structured rule set) and provides matchers
the chunk pipeline can call as gates. Phase 1 populates `enforced.deny_paths`
only; `instructed` is stubbed for forward compatibility (Phases 2-4 will
render it into agent prompts).

Schema (version 1):

    {
      "version": 1,
      "enforced": {
        "deny_paths": ["prefix1/", "prefix2/"]   # path prefixes
      },
      "instructed": {
        "implement": [],   # list of {id, severity, text} dicts (Phase 2+)
        "critique": []
      }
    }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_VERSIONS = {1}


class GuardrailsSchemaError(ValueError):
    """Raised when guardrails.json is malformed or has an unsupported version."""


def load_guardrails(path: Path | str) -> dict[str, Any]:
    """Load and validate the guardrails registry.

    Raises GuardrailsSchemaError with a message naming the bad field if the
    schema is invalid. Otherwise returns the parsed dict.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GuardrailsSchemaError("guardrails.json: top level must be an object")

    version = raw.get("version")
    if version is None:
        raise GuardrailsSchemaError("guardrails.json: missing required field 'version'")
    if version not in SUPPORTED_VERSIONS:
        raise GuardrailsSchemaError(
            f"guardrails.json: unsupported version {version!r} "
            f"(supported: {sorted(SUPPORTED_VERSIONS)})"
        )

    enforced = raw.get("enforced") or {}
    if not isinstance(enforced, dict):
        raise GuardrailsSchemaError("guardrails.json: 'enforced' must be an object")
    deny_paths = enforced.get("deny_paths", [])
    if not isinstance(deny_paths, list) or not all(isinstance(p, str) for p in deny_paths):
        raise GuardrailsSchemaError(
            "guardrails.json: 'enforced.deny_paths' must be a list of strings"
        )

    instructed = raw.get("instructed") or {}
    if not isinstance(instructed, dict):
        raise GuardrailsSchemaError("guardrails.json: 'instructed' must be an object")

    return raw
```

- [ ] **Step 2: Run tests, verify they pass**

Run: `poetry run pytest tests/agentic/test_guardrails.py -v`

Expected: 3 passed.

---

### Task 4: Write failing tests for `match_deny_paths`

**Files:**
- Modify: `tests/agentic/test_guardrails.py`

- [ ] **Step 1: Append matcher tests to the test file**

Add to the bottom of `tests/agentic/test_guardrails.py`:

```python
def test_match_deny_paths_returns_empty_when_no_violations():
    from scripts.agentic.guardrails import match_deny_paths

    diff_files = [
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
        "CLAUDE.md",
    ]
    deny_paths = [".github/", "secrets/"]
    violations = match_deny_paths(diff_files, deny_paths)
    assert violations == []


def test_match_deny_paths_flags_prefix_match():
    from scripts.agentic.guardrails import match_deny_paths

    diff_files = [
        "src/almaapitk/domains/configuration.py",
        ".github/workflows/release.yml",
        "secrets/api-keys.env",
    ]
    deny_paths = [".github/", "secrets/"]
    violations = match_deny_paths(diff_files, deny_paths)
    assert sorted(violations) == [".github/workflows/release.yml", "secrets/api-keys.env"]


def test_match_deny_paths_does_not_match_partial_segments():
    """Deny-path '.github/' must NOT match '.github_old/something' or 'foo.github/x'."""
    from scripts.agentic.guardrails import match_deny_paths

    diff_files = [
        ".github_old/notes.md",
        "foo.github/bar.py",
    ]
    deny_paths = [".github/"]
    violations = match_deny_paths(diff_files, deny_paths)
    assert violations == []


def test_match_deny_paths_handles_empty_inputs():
    from scripts.agentic.guardrails import match_deny_paths

    assert match_deny_paths([], [".github/"]) == []
    assert match_deny_paths(["src/foo.py"], []) == []
```

- [ ] **Step 2: Run tests, verify the new ones fail**

Run: `poetry run pytest tests/agentic/test_guardrails.py -v`

Expected: 3 passed (loader tests from Task 3) + 4 errors (`AttributeError: module 'scripts.agentic.guardrails' has no attribute 'match_deny_paths'`).

---

### Task 5: Implement `match_deny_paths` to make Task 4 tests pass

**Files:**
- Modify: `scripts/agentic/guardrails.py`

- [ ] **Step 1: Append the matcher to the module**

Add at the end of `scripts/agentic/guardrails.py`:

```python
def match_deny_paths(diff_files: list[str], deny_paths: list[str]) -> list[str]:
    """Return diff_files entries that match any deny_paths prefix.

    A deny_paths entry ending in '/' matches any path whose first segments
    equal the prefix. So '.github/' matches '.github/workflows/release.yml'
    but NOT '.github_old/notes.md' (which would be a different top-level
    directory). Entries without a trailing '/' are treated as exact-file
    deny rules.
    """
    violations: list[str] = []
    for path in diff_files:
        for prefix in deny_paths:
            if prefix.endswith("/"):
                if path == prefix.rstrip("/") or path.startswith(prefix):
                    violations.append(path)
                    break
            else:
                if path == prefix:
                    violations.append(path)
                    break
    return violations
```

- [ ] **Step 2: Run tests, verify all pass**

Run: `poetry run pytest tests/agentic/test_guardrails.py -v`

Expected: 7 passed.

---

### Task 6: Add CLI entrypoint to `guardrails.py`

**Files:**
- Modify: `scripts/agentic/guardrails.py`
- Modify: `tests/agentic/test_guardrails.py`

- [ ] **Step 1: Append CLI tests to the test file**

Add to the bottom of `tests/agentic/test_guardrails.py`:

```python
def test_cli_pass_via_stdin(tmp_path: Path):
    """CLI: deny-paths receives diff_files via stdin, exits 0 when nothing matches."""
    import subprocess

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({
        "version": 1,
        "enforced": {"deny_paths": [".github/", "secrets/"]},
        "instructed": {"implement": [], "critique": []},
    }))

    payload = json.dumps({"diff_files": ["src/foo.py", "tests/test_foo.py"]})
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.guardrails", "deny-paths",
         "--registry", str(registry)],
        input=payload, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["pass"] is True
    assert out["violations"] == []


def test_cli_fail_via_stdin(tmp_path: Path):
    """CLI: deny-paths exits 2 with violations listed when any path matches."""
    import subprocess

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({
        "version": 1,
        "enforced": {"deny_paths": [".github/"]},
        "instructed": {"implement": [], "critique": []},
    }))

    payload = json.dumps({"diff_files": ["src/foo.py", ".github/workflows/release.yml"]})
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.guardrails", "deny-paths",
         "--registry", str(registry)],
        input=payload, capture_output=True, text=True,
    )
    assert result.returncode == 2
    out = json.loads(result.stdout)
    assert out["pass"] is False
    assert ".github/workflows/release.yml" in out["violations"]
```

- [ ] **Step 2: Run tests, verify the new ones fail**

Run: `poetry run pytest tests/agentic/test_guardrails.py -v`

Expected: 7 passed + 2 errors (CLI module has no `__main__` entry yet).

- [ ] **Step 3: Append CLI entrypoint to `scripts/agentic/guardrails.py`**

Add at the end of `scripts/agentic/guardrails.py`:

```python
def _cli_deny_paths(registry_path: str) -> int:
    import sys

    payload = json.loads(sys.stdin.read())
    if "diff_files" not in payload:
        json.dump(
            {"pass": False, "error": "bad_payload", "missing_key": "diff_files"},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
        return 3

    try:
        registry = load_guardrails(registry_path)
    except (GuardrailsSchemaError, FileNotFoundError) as exc:
        json.dump(
            {"pass": False, "error": "registry_invalid", "detail": str(exc)},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
        return 3

    deny_paths = registry["enforced"].get("deny_paths", [])
    violations = match_deny_paths(payload["diff_files"], deny_paths)
    result = {"pass": not violations, "violations": violations}
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if not violations else 2


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="scripts.agentic.guardrails")
    sub = parser.add_subparsers(dest="cmd", required=True)
    deny = sub.add_parser("deny-paths")
    deny.add_argument("--registry", default="guardrails.json")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd == "deny-paths":
        return _cli_deny_paths(args.registry)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests, verify all 9 pass**

Run: `poetry run pytest tests/agentic/test_guardrails.py -v`

Expected: 9 passed.

- [ ] **Step 5: Commit Tasks 2-6 together**

```bash
git add scripts/agentic/guardrails.py tests/agentic/test_guardrails.py
git commit -m "feat(agentic): add guardrails loader + deny-path matcher (Phase 1)"
```

---

### Task 7: Replace `scopeCheckTask` with `denyPathsTask` in the chunk-impl process

**Files:**
- Modify: `.a5c/processes/chunk-template-impl.js` (lines 125-156, 342-346)

- [ ] **Step 1: Read the current `scopeCheckTask` definition to confirm line numbers**

Run: `grep -n "scopeCheckTask\|scope-check" .a5c/processes/chunk-template-impl.js`

Expected: matches at approximately lines 44, 125, 144, 342.

- [ ] **Step 2: Replace the `scopeCheckTask` definition (around lines 125-156)**

Locate the `export const scopeCheckTask = defineTask('scope-check', ...)` block and replace it entirely with:

```js
export const denyPathsTask = defineTask('deny-paths', (args, taskCtx) => {
  // Phase 1 of the guardrails registry: instead of an allow-list scope-check,
  // we run a tiny deny-list against the diff. The deny-list lives in
  // guardrails.json (enforced.deny_paths). See
  // docs/superpowers/plans/2026-05-06-guardrails-registry-phase-1.md.
  return {
    kind: 'shell',
    title: 'Deny-paths gate (guardrails.json enforced.deny_paths)',
    shell: {
      command: `set -e
cd "${args.repoRoot}"
DIFF_FILES_JSON="$(git diff --name-only chunk/${args.chunkName}...HEAD | python -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')"
set +e
python -m scripts.agentic.guardrails deny-paths --registry guardrails.json <<PAYLOAD_EOF
{"diff_files": $DIFF_FILES_JSON}
PAYLOAD_EOF
exit $?
`,
      timeout: 30000,
    },
    io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  };
});
```

- [ ] **Step 3: Update the gate-chain reference (around line 342)**

Locate the `gateChain` array in the main loop and replace:

```js
        ['scope', scopeCheckTask, {
          repoRoot, chunkName,
          issueNumber: issue.number,
          filesToTouch: issue.files_to_touch,
        }],
```

with:

```js
        ['deny-paths', denyPathsTask, { repoRoot, chunkName }],
```

- [ ] **Step 4: Update the comment on line ~44 that references `scopeCheckTask`**

Find the comment "The shell pattern mirrors `scopeCheckTask`" and update it to "The shell pattern mirrors `denyPathsTask`".

- [ ] **Step 5: Verify the JS still parses**

Run: `node --check .a5c/processes/chunk-template-impl.js`

Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add .a5c/processes/chunk-template-impl.js
git commit -m "feat(agentic): replace scopeCheckTask with denyPathsTask (Phase 1)"
```

---

### Task 8: Soften R7 in `implement.v1.md`

**Files:**
- Modify: `scripts/agentic/prompts/implement.v1.md`

- [ ] **Step 1: Replace the R7 line**

Find this line in `scripts/agentic/prompts/implement.v1.md`:

```
1. **R7:** Modify only files in `filesToTouch`. The scope-check gate will reject the attempt otherwise.
```

Replace with:

```
1. **Stay in scope.** The issue's `Files to touch` is guidance — the primary files you're expected to touch. You may also touch closely-related files (matching unit-test file, public-API plumbing, CLAUDE.md updates required by AC) when the issue's acceptance criteria require it. Do NOT refactor unrelated code, fix unrelated bugs, or expand scope. The deny-paths gate will reject any change to `.github/` or `secrets/`; broader scope is enforced by review.
```

- [ ] **Step 2: Update the `feedback` section reference (line ~25)**

Find:

```
The previous attempt failed. The feedback string names the gate that failed (`static`, `scope`, `unit`, `contract`) and the relevant output. Address that root cause; do not also refactor unrelated code.
```

Replace `scope` with `deny-paths`:

```
The previous attempt failed. The feedback string names the gate that failed (`static`, `deny-paths`, `unit`, `contract`) and the relevant output. Address that root cause; do not also refactor unrelated code.
```

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/prompts/implement.v1.md
git commit -m "feat(agentic): soften R7 in implement prompt; reference deny-paths gate (Phase 1)"
```

---

### Task 9: End-to-end smoke against the #22 chunk diff

This task verifies the new gate would have passed the diff that the old scope-check rejected.

**Files:** none modified; this is a verification-only task.

- [ ] **Step 1: Confirm the aborted chunk's sub-branch still exists**

Run: `git rev-parse --verify feat/22-coverage-configuration-bootstr 2>&1`

Expected: a commit hash (the aborted attempt-1 commit).

If the branch is gone, skip this task entirely — the gate-chain replacement was tested by Task 5 and Task 6.

- [ ] **Step 2: Compute the diff and check the new gate**

Run from the repo root:

```bash
DIFF_FILES_JSON="$(git diff --name-only main...feat/22-coverage-configuration-bootstr | python -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')"
echo "{\"diff_files\": $DIFF_FILES_JSON}" | python -m scripts.agentic.guardrails deny-paths --registry guardrails.json
```

Expected: JSON with `"pass": true`, `"violations": []`. Exit 0.

This proves the new gate accepts the diff that the old scope-check (incorrectly) rejected.

- [ ] **Step 3: Sanity-check the deny-list works by simulating a violating diff**

Run:

```bash
echo '{"diff_files": ["src/foo.py", ".github/workflows/release.yml"]}' \
  | python -m scripts.agentic.guardrails deny-paths --registry guardrails.json
```

Expected: JSON with `"pass": false`, `"violations": [".github/workflows/release.yml"]`. Exit 2.

This proves the gate fires when it should.

(No commit — verification only.)

---

### Task 10: Update CLAUDE.md, CHUNK_PLAYBOOK.md, and the design spec

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/CHUNK_PLAYBOOK.md`
- Modify: `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md`

- [ ] **Step 1: Update `docs/CHUNK_PLAYBOOK.md` line 23**

Find:

```
| R7 | Agents don't edit files outside the issue's Files-to-touch list. |
```

Replace with:

```
| R7 | (Phase 1 of the guardrails registry, 2026-05-06) Replaced by the deny-paths gate (guardrails.json `enforced.deny_paths`). `Files to touch` is now informational guidance to the implement agent; out-of-scope edits are caught by review, not by a hard gate. |
```

- [ ] **Step 2: Update line ~71 of the same file**

Find:

```
- For each issue, create `feat/<N>-<slug>`, run the implementation agent (max 3 attempts), run static-gates → scope-check (R7) → unit tests → contract tests, then merge into the integration branch with `--no-ff`.
```

Replace `scope-check (R7)` with `deny-paths (R7, guardrails.json)`:

```
- For each issue, create `feat/<N>-<slug>`, run the implementation agent (max 3 attempts), run static-gates → deny-paths (R7, guardrails.json) → unit tests → contract tests, then merge into the integration branch with `--no-ff`.
```

- [ ] **Step 3: Update the design spec line 33**

Find in `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md`:

```
| **R7** | **No agent edits files outside the issue's `Files to touch` list.** Enforced by the `scope-check` gate (§5.2); if violated, the refinement attempt is rejected and feedback fed back to the agent. | Scope discipline; review economy. |
```

Replace with:

```
| **R7** | **Edits to deny-listed paths (`.github/`, `secrets/`) are blocked.** Enforced by the `deny-paths` gate (Phase 1 of the guardrails registry, see `docs/superpowers/plans/2026-05-06-guardrails-registry-phase-1.md`). The original allow-list scope-check (`scripts/agentic/scope_check.py`) is retained but no longer wired into the chunk-impl process. | Scope discipline (deny-list flavor); review-driven enforcement of broader scope; review economy. |
```

- [ ] **Step 4: Add a note in `CLAUDE.md` after the R8 hard-rule paragraph**

Find the line in CLAUDE.md that begins `**Hard rule R8:**`. After the R8 paragraph (and before R9), insert:

```markdown
**R7 (deny-paths):** As of 2026-05-06 (Phase 1 of the guardrails registry), R7 is enforced by `guardrails.json` `enforced.deny_paths` rather than a per-issue allow-list. The current deny-list is small (`.github/`, `secrets/`); broader scope discipline lives in the implement agent's prompt and (Phase 4) in the post-implement critique pass. See `docs/superpowers/plans/2026-05-06-guardrails-registry-phase-1.md`.

```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/CHUNK_PLAYBOOK.md docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md
git commit -m "docs(agentic): document deny-paths gate replacing R7 scope-check (Phase 1)"
```

---

### Task 11: Mark `scope_check.py` deprecated (kept in tree)

**Files:**
- Modify: `scripts/agentic/scope_check.py` (top of module)

- [ ] **Step 1: Update the module docstring**

Replace the existing module docstring at the top of `scripts/agentic/scope_check.py` with:

```python
"""Compare a branch's diff to an issue's Files-to-touch list (legacy R7).

DEPRECATED (2026-05-06): Phase 1 of the guardrails registry replaced this
allow-list scope-check with a deny-list `deny-paths` gate (see
`scripts.agentic.guardrails` and
`docs/superpowers/plans/2026-05-06-guardrails-registry-phase-1.md`).
This module is retained for back-compat with any out-of-tree scripts that
still import it; the chunk-impl process no longer calls it. Removal is
planned for Phase 5.

Supports two invocation modes:
1. Pure-data: pass diff_files + files_to_touch as Python lists.
2. CLI: stdin JSON {"branch": "...", "base": "...", "files_to_touch": [...]} -
   computes diff_files via `git diff --name-only base...branch` and emits result.
"""
```

- [ ] **Step 2: Run the existing scope-check tests to confirm they still pass**

Run: `poetry run pytest tests/agentic/test_scope_check.py -v`

Expected: all tests pass (the docstring change doesn't affect behavior).

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/scope_check.py
git commit -m "docs(agentic): mark scope_check.py deprecated (replaced by guardrails deny-paths)"
```

---

### Task 12: Final integration check

**Files:** none modified.

- [ ] **Step 1: Run the full agentic test suite**

Run: `poetry run pytest tests/agentic/ tests/test_public_api_contract.py -q`

Expected: all tests pass (134 existing + 9 new from this plan = 143).

- [ ] **Step 2: Run smoke import**

Run: `poetry run python scripts/smoke_import.py`

Expected: smoke test PASSED.

- [ ] **Step 3: Final JS lint**

Run: `node --check .a5c/processes/chunk-template-impl.js`

Expected: exit 0, no output.

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin feat/guardrails-registry-phase-1
gh pr create --title "feat(agentic): guardrails registry — Phase 1 (deny-paths gate replaces scope-check)" --body "$(cat <<'EOF'
## Summary
- Introduces `guardrails.json` at repo root: a structured rule registry with `enforced` (mechanical) and `instructed` (stage-targeted prompt text) sections.
- Replaces the brittle `scopeCheckTask` (allow-list, false-positive prone) with a `denyPathsTask` (small deny-list, currently `.github/` + `secrets/`).
- `files_to_touch` stays in issue bodies and `manifest.json` as guidance the implement agent reads — no longer mechanically enforced.
- `scope_check.py` is retained but marked deprecated; removal deferred to Phase 5.

## Why
Chunk #22 (config-bootstrap) was structurally blocked by the old scope-check on attempt 1 — the diff was correct, but the gate's allow-list comparison didn't account for inside-backtick annotations or process-mandated files (unit tests, CLAUDE.md updates). The pain has been false positives, not caught drift. The deny-list inverts the model: enumerate the few dangerous paths, trust everything else, catch broader scope creep at review time.

## Phasing
- **Phase 1 (this PR):** registry skeleton + deny-paths gate.
- Phase 2: diff-budget + commit-message regex.
- Phase 3: R9 redaction patterns.
- Phase 4: critique-pass stage reading diff vs. AC.
- Phase 5: remove `files_to_touch` and `scope_check.py`.

See `docs/superpowers/plans/2026-05-06-guardrails-registry-phase-1.md` for the full plan.

## Test plan
- [x] `pytest tests/agentic/test_guardrails.py -v` → 9 new tests pass
- [x] `pytest tests/agentic/ tests/test_public_api_contract.py -q` → no regressions
- [x] `python scripts/smoke_import.py` → passes
- [x] `node --check .a5c/processes/chunk-template-impl.js` → JS parses
- [x] End-to-end smoke: the deny-paths gate accepts the diff that the old scope-check rejected on chunk #22, and rejects a synthetic violating diff with `.github/workflows/release.yml`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 5: Wait for security check, then merge**

```bash
until [ "$(gh pr view --json statusCheckRollup --jq '.statusCheckRollup[0].status' 2>/dev/null)" = "COMPLETED" ]; do sleep 5; done
gh pr merge --merge --delete-branch
git checkout main && git pull --ff-only origin main
```

Expected: PR merged, local main up-to-date.

---

## Self-Review Checklist

After implementation, verify against this plan:

- [ ] Every task in this plan has a matching commit.
- [ ] No task introduced changes outside the file structure table.
- [ ] All 9 new guardrails tests pass.
- [ ] `node --check` on the JS process file succeeds.
- [ ] Smoke import passes.
- [ ] The `feat/22-coverage-configuration-bootstr` branch's diff passes the new deny-paths gate.
- [ ] `scope_check.py` is unchanged in behavior (its tests still pass).
- [ ] CLAUDE.md and the design spec reflect the R7 replacement.

## Post-Phase-1: Re-Run Chunk #22

After this PR merges, the operator can:

1. `scripts/agentic/chunks abort config-bootstrap` (already done).
2. `scripts/agentic/chunks define --name config-bootstrap --issues 22`.
3. `/chunk-run-impl config-bootstrap`.

The implement agent will produce the same diff as attempt 1 of the aborted run (clean Configuration class skeleton + tests + CLAUDE.md update). The new deny-paths gate will pass it. The pipeline proceeds to unit tests, contract tests, merge.

If anything in this plan turns out to introduce a NEW blocker, revert with:

```bash
git revert <merge-commit-sha>
git push origin main
```

`scope_check.py` and the old `scopeCheckTask` are preserved in the prior commit, so a revert returns the system to its pre-Phase-1 state cleanly.
