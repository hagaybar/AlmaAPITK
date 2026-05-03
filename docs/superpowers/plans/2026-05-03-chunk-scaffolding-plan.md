# Chunk-Driven Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the orchestration scaffolding described in `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md` — two babysitter processes, a CLI helper, supporting Python utilities, prompt templates, and operator playbook — so that real GitHub issues can later be implemented in human-paced chunks with SANDBOX-tested PRs.

**Architecture:** Python utilities under `scripts/agentic/` (issue parser, prereq checker, scope-check, PR opener, run-log appender, status-helpers); a thin Bash CLI `scripts/agentic/chunks` that wraps them; two Node/Babysitter process files under `.a5c/processes/` (a per-chunk implementation generator and a generic interactive testing process); versioned prompt templates as Markdown; an operator playbook. All components are unit-testable against a synthetic "issue #999" fixture before any real ticket touches them.

**Tech Stack:** Python 3.12+ (Poetry), pytest, Node.js (existing `.a5c/node_modules/@a5c-ai/babysitter-sdk@0.0.182`), Bash, `gh` CLI, `git`, `jq`.

---

## Spec invariants (R1–R8) — referenced by tasks

- **R1** Never push/merge to `prod`
- **R2** Never auto-merge to `main` (PRs always draft)
- **R3** No autonomous loop spans implementation→testing
- **R4** Auto-close only on perfect-green
- **R5** Cleanup mandatory on every state-changing test
- **R6** 3-attempt cap on refinement
- **R7** Scope-check enforces files-to-touch
- **R8** SANDBOX-only credentials in orchestration env

Every script and process below either enforces one of these or is plumbing for one that does.

---

## File map

**New files (creating):**

```
scripts/agentic/
  __init__.py                                 # marks the package
  issue_parser.py                             # Phase 1
  prereq_check.py                             # Phase 2
  scope_check.py                              # Phase 3
  pr_open.py                                  # Phase 4
  run_log.py                                  # Phase 5
  chunk_status.py                             # Phase 6
  chunks                                      # Phase 7 (Bash CLI, executable)
  prompts/
    implement.v1.md                           # Phase 10
    test-recommendation.v1.md                 # Phase 10
    summary-triage.v1.md                      # Phase 10

.a5c/processes/
  chunk-test.js                               # Phase 8
  chunk-template-impl.js                      # Phase 9
  chunk-test-inputs.example.json              # Phase 8

tests/agentic/
  __init__.py
  fixtures/
    issue-999.json                            # synthetic issue (Phase 0)
    issue-999-body.md                         # raw markdown body for fallback parsing
    issue-998-bad.json                        # malformed-on-purpose for parser tests
  test_issue_parser.py                        # Phase 1
  test_prereq_check.py                        # Phase 2
  test_scope_check.py                         # Phase 3
  test_pr_open.py                             # Phase 4
  test_run_log.py                             # Phase 5
  test_chunk_status.py                        # Phase 6
  test_chunks_cli.py                          # Phase 7
  test_chunk_test_process.py                  # Phase 8 (smoke only — JS file lints cleanly)
  test_chunk_template_impl.py                 # Phase 9 (smoke only)
  test_e2e_smoke.py                           # Phase 12

docs/
  CHUNK_PLAYBOOK.md                           # Phase 11

chunks/
  .gitkeep                                    # Phase 0
```

**Existing files (modifying):**

- `.gitignore` — append `chunks/<name>/sandbox-test-output/` to gitignore raw pytest logs (kept locally only); keep `chunks/<name>/*.json` and `*.md` tracked. (Phase 0)
- `pyproject.toml` — add `scripts/agentic/` to package paths if linters need it; nothing else. (Phase 0)

---

## Phase 0 — Foundation: directories, synthetic fixtures, test bootstrap

### Task 0.1: Create directory skeleton

**Files:**
- Create: `scripts/agentic/__init__.py`
- Create: `scripts/agentic/prompts/.gitkeep`
- Create: `tests/agentic/__init__.py`
- Create: `tests/agentic/fixtures/.gitkeep`
- Create: `chunks/.gitkeep`

- [ ] **Step 1: Create directories and empty markers**

```bash
cd /home/hagaybar/projects/AlmaAPITK
mkdir -p scripts/agentic/prompts tests/agentic/fixtures chunks
touch scripts/agentic/__init__.py
touch scripts/agentic/prompts/.gitkeep
touch tests/agentic/__init__.py
touch tests/agentic/fixtures/.gitkeep
touch chunks/.gitkeep
```

- [ ] **Step 2: Verify**

```bash
ls scripts/agentic tests/agentic chunks
```

Expected: directories exist with the marker files.

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic tests/agentic chunks
git commit -m "chore(agentic): create directory skeleton for chunk scaffolding"
```

### Task 0.2: Update `.gitignore` for chunk outputs

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append rules**

Append exactly these lines to `.gitignore`:

```
# Chunk-driven scaffolding (per spec §9): keep manifests + status, drop raw logs
chunks/*/sandbox-test-output/
chunks/*/sandbox-tests/
```

- [ ] **Step 2: Verify**

```bash
git check-ignore chunks/foo/sandbox-test-output/x.log
```

Expected: prints the ignored path.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore(agentic): ignore raw pytest logs from chunk runs"
```

### Task 0.3: Create synthetic issue #999 fixture

This stand-in lets us test every parser/checker/process without hitting GitHub.

**Files:**
- Create: `tests/agentic/fixtures/issue-999.json`
- Create: `tests/agentic/fixtures/issue-999-body.md`
- Create: `tests/agentic/fixtures/issue-998-bad.json`

- [ ] **Step 1: Write the well-formed fixture**

`tests/agentic/fixtures/issue-999.json`:

```json
{
  "number": 999,
  "title": "Synthetic test fixture: Users: get_user (smoke)",
  "url": "https://example.invalid/issue/999",
  "labels": [
    {"name": "api-coverage"},
    {"name": "priority:medium"}
  ],
  "body": "Domain: Users\nPriority: medium\nEffort: S\n\n## API endpoints touched\n- GET /almaws/v1/users/{user_id}\n\n## Methods to add\n```python\nclass Users:\n    def get_user(self, user_id: str) -> AlmaResponse: ...\n```\n\n## Files to touch\n- src/almaapitk/domains/users.py\n- tests/unit/domains/test_users.py\n\n## References\n- https://developers.exlibrisgroup.com/alma/apis/users/\n\n## Prerequisites\n- Hard: #3 (persistent Session)\n- Soft: #14 (logger)\n\n## Acceptance criteria\n- [ ] AC-1: get_user returns AlmaResponse with .success == True for a valid user_id\n- [ ] AC-2: get_user raises AlmaValidationError when user_id is empty\n\n## Notes for the implementing agent\n- Mirror Acquisitions.get_invoice as the pattern source.\n"
}
```

- [ ] **Step 2: Write the raw-body fallback fixture**

`tests/agentic/fixtures/issue-999-body.md` — copy the `body` field above, decoded (so the markdown is readable directly).

```markdown
Domain: Users
Priority: medium
Effort: S

## API endpoints touched
- GET /almaws/v1/users/{user_id}

## Methods to add
```python
class Users:
    def get_user(self, user_id: str) -> AlmaResponse: ...
```

## Files to touch
- src/almaapitk/domains/users.py
- tests/unit/domains/test_users.py

## References
- https://developers.exlibrisgroup.com/alma/apis/users/

## Prerequisites
- Hard: #3 (persistent Session)
- Soft: #14 (logger)

## Acceptance criteria
- [ ] AC-1: get_user returns AlmaResponse with .success == True for a valid user_id
- [ ] AC-2: get_user raises AlmaValidationError when user_id is empty

## Notes for the implementing agent
- Mirror Acquisitions.get_invoice as the pattern source.
```

- [ ] **Step 3: Write the malformed fixture (for negative tests)**

`tests/agentic/fixtures/issue-998-bad.json`:

```json
{
  "number": 998,
  "title": "Bad fixture (missing structured fields)",
  "url": "https://example.invalid/issue/998",
  "labels": [],
  "body": "This issue body has no structured fields. It should make the parser fail clearly."
}
```

- [ ] **Step 4: Verify JSON is valid**

```bash
python -c "import json; json.load(open('tests/agentic/fixtures/issue-999.json'))"
python -c "import json; json.load(open('tests/agentic/fixtures/issue-998-bad.json'))"
```

Expected: no output, exit 0 for both.

- [ ] **Step 5: Commit**

```bash
git add tests/agentic/fixtures
git commit -m "test(agentic): add synthetic issue #999 fixtures for scaffold tests"
```

---

## Phase 1 — Issue parser (`scripts/agentic/issue_parser.py`)

Parses an issue's body into the structured JSON shape the rest of the pipeline consumes. Reads from either `gh issue view --json` output (real issues) or a local fixture (tests).

### Task 1.1: Write the failing parser test (happy path)

**Files:**
- Create: `tests/agentic/test_issue_parser.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for scripts.agentic.issue_parser."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_well_formed_issue_999():
    from scripts.agentic.issue_parser import parse_issue

    raw = json.loads((FIXTURES / "issue-999.json").read_text())
    parsed = parse_issue(raw)

    assert parsed["number"] == 999
    assert parsed["title"] == "Synthetic test fixture: Users: get_user (smoke)"
    assert parsed["domain"] == "Users"
    assert parsed["priority"] == "medium"
    assert parsed["effort"] == "S"
    assert parsed["endpoints"] == ["GET /almaws/v1/users/{user_id}"]
    assert "src/almaapitk/domains/users.py" in parsed["files_to_touch"]
    assert "tests/unit/domains/test_users.py" in parsed["files_to_touch"]
    assert parsed["hard_prereqs"] == [3]
    assert parsed["soft_prereqs"] == [14]
    assert len(parsed["acceptance_criteria"]) == 2
    assert "AC-1" in parsed["acceptance_criteria"][0]
    assert parsed["labels"] == ["api-coverage", "priority:medium"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/hagaybar/projects/AlmaAPITK
poetry run pytest tests/agentic/test_issue_parser.py::test_parse_well_formed_issue_999 -v
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.agentic.issue_parser`.

### Task 1.2: Implement minimal parser to pass the happy-path test

**Files:**
- Create: `scripts/agentic/issue_parser.py`

- [ ] **Step 1: Write the parser**

`scripts/agentic/issue_parser.py`:

```python
"""Parse GitHub issue bodies into structured dicts for the chunk pipeline.

Input shape: the JSON object returned by `gh issue view <N> --json
number,title,url,labels,body`.

Output shape: a flat dict with keys consumed by chunk-template-impl.js and
the prereq checker. See spec §4 (stage 1 — chunk definition).
"""
from __future__ import annotations

import re
from typing import Any


_DOMAIN_RE = re.compile(r"^Domain:\s*(\S+)", re.MULTILINE)
_PRIORITY_RE = re.compile(r"^Priority:\s*(\S+)", re.MULTILINE)
_EFFORT_RE = re.compile(r"^Effort:\s*(\S+)", re.MULTILINE)


def _section(body: str, header: str) -> str | None:
    """Return the markdown body of `## <header>` up to the next `## ` or EOF."""
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def _bullet_lines(section_body: str | None) -> list[str]:
    if not section_body:
        return []
    return [
        line[2:].strip()
        for line in section_body.splitlines()
        if line.startswith("- ") or line.startswith("* ")
    ]


def _parse_prereqs(section_body: str | None) -> tuple[list[int], list[int]]:
    """Return (hard, soft) issue-number lists from a Prerequisites section."""
    hard: list[int] = []
    soft: list[int] = []
    if not section_body:
        return hard, soft
    for line in section_body.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        is_hard = "hard:" in line.lower()
        is_soft = "soft:" in line.lower()
        for num_str in re.findall(r"#(\d+)", line):
            num = int(num_str)
            if is_hard:
                hard.append(num)
            elif is_soft:
                soft.append(num)
    return hard, soft


def _parse_ac(section_body: str | None) -> list[str]:
    if not section_body:
        return []
    out: list[str] = []
    for line in section_body.splitlines():
        s = line.strip()
        if s.startswith("- [ ]") or s.startswith("- [x]"):
            out.append(s[5:].strip())
    return out


def parse_issue(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse one issue JSON object into a structured dict.

    Required input keys: number, title, url, labels (list of {name}), body.

    Raises ValueError if any structured field is missing.
    """
    for key in ("number", "title", "body"):
        if key not in raw:
            raise ValueError(f"issue JSON missing required key: {key}")

    body = raw["body"] or ""
    out: dict[str, Any] = {
        "number": int(raw["number"]),
        "title": raw["title"],
        "url": raw.get("url", ""),
        "labels": [lbl["name"] for lbl in raw.get("labels", [])],
        "body_raw": body,
    }

    domain_m = _DOMAIN_RE.search(body)
    priority_m = _PRIORITY_RE.search(body)
    effort_m = _EFFORT_RE.search(body)
    if not (domain_m and priority_m and effort_m):
        raise ValueError(
            f"issue #{out['number']} missing Domain/Priority/Effort header lines"
        )
    out["domain"] = domain_m.group(1)
    out["priority"] = priority_m.group(1).lower()
    out["effort"] = effort_m.group(1).upper()

    out["endpoints"] = _bullet_lines(_section(body, "API endpoints touched"))
    out["files_to_touch"] = _bullet_lines(_section(body, "Files to touch"))
    out["references"] = _bullet_lines(_section(body, "References"))
    hard, soft = _parse_prereqs(_section(body, "Prerequisites"))
    out["hard_prereqs"] = hard
    out["soft_prereqs"] = soft
    out["acceptance_criteria"] = _parse_ac(_section(body, "Acceptance criteria"))

    return out


def main() -> int:
    """CLI entry: read JSON from stdin, write structured JSON to stdout."""
    import json
    import sys

    raw = json.load(sys.stdin)
    parsed = parse_issue(raw)
    json.dump(parsed, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run test to verify it passes**

```bash
poetry run pytest tests/agentic/test_issue_parser.py::test_parse_well_formed_issue_999 -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/issue_parser.py tests/agentic/test_issue_parser.py
git commit -m "feat(agentic): issue body parser with happy-path test"
```

### Task 1.3: Add negative-path tests (malformed fixture)

**Files:**
- Modify: `tests/agentic/test_issue_parser.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/agentic/test_issue_parser.py`:

```python
def test_parse_rejects_missing_structured_headers():
    from scripts.agentic.issue_parser import parse_issue

    raw = json.loads((FIXTURES / "issue-998-bad.json").read_text())
    with pytest.raises(ValueError, match="missing Domain/Priority/Effort"):
        parse_issue(raw)


def test_parse_rejects_missing_top_level_keys():
    from scripts.agentic.issue_parser import parse_issue

    with pytest.raises(ValueError, match="missing required key"):
        parse_issue({"number": 1, "title": "no body"})
```

- [ ] **Step 2: Run tests**

```bash
poetry run pytest tests/agentic/test_issue_parser.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/agentic/test_issue_parser.py
git commit -m "test(agentic): negative-path coverage for issue parser"
```

### Task 1.4: Add CLI smoke test

**Files:**
- Modify: `tests/agentic/test_issue_parser.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_cli_round_trip(tmp_path):
    """Run the parser as a CLI: stdin → stdout."""
    import subprocess

    fixture = (FIXTURES / "issue-999.json").read_text()
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.issue_parser"],
        input=fixture,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["number"] == 999
    assert parsed["domain"] == "Users"
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_issue_parser.py::test_cli_round_trip -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/agentic/test_issue_parser.py
git commit -m "test(agentic): CLI round-trip for issue parser"
```

---

## Phase 2 — Code-level prereq checker (`scripts/agentic/prereq_check.py`)

Per handbook §13 anti-pattern: "trusting the Prerequisites block more than the actual code." This script verifies that each hard prereq has actually landed in `main` by grepping for the symbol it introduces — not just that the issue is closed.

### Task 2.1: Write the failing test

**Files:**
- Create: `tests/agentic/test_prereq_check.py`

- [ ] **Step 1: Write the test**

```python
"""Tests for scripts.agentic.prereq_check."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_returns_no_violations_when_all_symbols_present(tmp_path):
    """Symbols all exist in the search root → no violations."""
    from scripts.agentic.prereq_check import check_prereqs

    src = tmp_path / "src"
    src.mkdir()
    (src / "client.py").write_text("class AlmaAPIClient:\n    def _request(self): pass\n")

    result = check_prereqs(
        prereqs=[
            {"issue": 3, "symbol": "AlmaAPIClient", "where": "src/"},
            {"issue": 4, "symbol": "_request", "where": "src/"},
        ],
        repo_root=tmp_path,
    )
    assert result["all_merged"] is True
    assert result["missing"] == []


def test_returns_violations_when_symbol_missing(tmp_path):
    from scripts.agentic.prereq_check import check_prereqs

    src = tmp_path / "src"
    src.mkdir()
    (src / "client.py").write_text("class AlmaAPIClient: pass\n")

    result = check_prereqs(
        prereqs=[
            {"issue": 4, "symbol": "_request", "where": "src/"},
        ],
        repo_root=tmp_path,
    )
    assert result["all_merged"] is False
    assert len(result["missing"]) == 1
    assert result["missing"][0]["issue"] == 4
    assert "_request" in result["missing"][0]["why"]


def test_empty_prereq_list_is_ok(tmp_path):
    from scripts.agentic.prereq_check import check_prereqs

    result = check_prereqs(prereqs=[], repo_root=tmp_path)
    assert result["all_merged"] is True
    assert result["missing"] == []
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_prereq_check.py -v
```

Expected: 3 failures (ModuleNotFoundError).

### Task 2.2: Implement the prereq checker

**Files:**
- Create: `scripts/agentic/prereq_check.py`

- [ ] **Step 1: Write the implementation**

`scripts/agentic/prereq_check.py`:

```python
"""Verify hard prereqs at the code level, not the issue-state level.

Per handbook §13: a prereq issue can be closed in name but its functionality
may not be wired in. This helper greps the working tree for the symbol each
prereq is supposed to introduce.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


def _symbol_present(symbol: str, search_root: Path) -> bool:
    """Word-boundary search for `symbol` under `search_root`. Returns True on hit."""
    if not search_root.exists():
        return False
    try:
        # ripgrep is preferred but not guaranteed; fall back to grep -r
        cmd = ["rg", "-l", "-w", symbol, str(search_root)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return bool(result.stdout.strip())
        if result.returncode == 1:
            return False
        # rg not installed or other error → fall through to grep
    except FileNotFoundError:
        pass
    cmd = ["grep", "-rlw", "--include=*.py", symbol, str(search_root)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def check_prereqs(prereqs: list[dict[str, Any]], repo_root: Path) -> dict[str, Any]:
    """Check each prereq's symbol is present somewhere under its `where` path.

    Args:
        prereqs: list of {"issue": int, "symbol": str, "where": "src/" relative path}
        repo_root: absolute path to repo root

    Returns: {"all_merged": bool, "missing": [{issue, symbol, where, why}, ...]}
    """
    missing: list[dict[str, Any]] = []
    for p in prereqs:
        where = repo_root / p.get("where", ".")
        if not _symbol_present(p["symbol"], where):
            missing.append({
                "issue": p["issue"],
                "symbol": p["symbol"],
                "where": p.get("where", "."),
                "why": f"symbol '{p['symbol']}' not found under {where}",
            })
    return {"all_merged": not missing, "missing": missing}


def main() -> int:
    """CLI: read prereq list JSON from stdin, write check result JSON to stdout."""
    import json
    import sys

    payload = json.load(sys.stdin)
    repo_root = Path(payload.get("repo_root", "."))
    prereqs = payload["prereqs"]
    result = check_prereqs(prereqs, repo_root)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_prereq_check.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/prereq_check.py tests/agentic/test_prereq_check.py
git commit -m "feat(agentic): code-level prereq checker (handbook §13 anti-pattern)"
```

---

## Phase 3 — Scope-check linter (`scripts/agentic/scope_check.py`)

Enforces R7. Compares files actually changed on a branch against the issue's `Files to touch` list.

### Task 3.1: Write the failing test

**Files:**
- Create: `tests/agentic/test_scope_check.py`

- [ ] **Step 1: Write the test**

```python
"""Tests for scripts.agentic.scope_check (enforces spec R7)."""
from __future__ import annotations


def test_passes_when_diff_is_subset_of_files_to_touch():
    from scripts.agentic.scope_check import check_scope

    diff_files = ["src/almaapitk/domains/users.py"]
    files_to_touch = [
        "src/almaapitk/domains/users.py",
        "tests/unit/domains/test_users.py",
    ]
    result = check_scope(diff_files=diff_files, files_to_touch=files_to_touch)
    assert result["pass"] is True
    assert result["out_of_scope"] == []


def test_fails_when_diff_includes_off_scope_file():
    from scripts.agentic.scope_check import check_scope

    diff_files = [
        "src/almaapitk/domains/users.py",
        "src/almaapitk/client/AlmaAPIClient.py",  # not in scope
    ]
    files_to_touch = ["src/almaapitk/domains/users.py"]
    result = check_scope(diff_files=diff_files, files_to_touch=files_to_touch)
    assert result["pass"] is False
    assert "src/almaapitk/client/AlmaAPIClient.py" in result["out_of_scope"]


def test_passes_when_diff_is_empty():
    from scripts.agentic.scope_check import check_scope

    result = check_scope(diff_files=[], files_to_touch=["any"])
    assert result["pass"] is True
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_scope_check.py -v
```

Expected: 3 failures.

### Task 3.2: Implement scope-check

**Files:**
- Create: `scripts/agentic/scope_check.py`

- [ ] **Step 1: Write the implementation**

`scripts/agentic/scope_check.py`:

```python
"""Compare a branch's diff to an issue's Files-to-touch list (spec R7).

Supports two invocation modes:
1. Pure-data: pass diff_files + files_to_touch as Python lists.
2. CLI: stdin JSON {"branch": "...", "base": "...", "files_to_touch": [...]} -
   computes diff_files via `git diff --name-only base...branch` and emits result.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def check_scope(diff_files: list[str], files_to_touch: list[str]) -> dict[str, Any]:
    allowed = set(files_to_touch)
    out_of_scope = sorted(f for f in diff_files if f not in allowed)
    return {"pass": not out_of_scope, "out_of_scope": out_of_scope}


def diff_files_for_branch(base: str, branch: str, repo_root: Path) -> list[str]:
    cmd = ["git", "-C", str(repo_root), "diff", "--name-only", f"{base}...{branch}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    import json
    import sys

    payload = json.load(sys.stdin)
    if "diff_files" in payload:
        diff_files = payload["diff_files"]
    else:
        diff_files = diff_files_for_branch(
            base=payload["base"],
            branch=payload["branch"],
            repo_root=Path(payload.get("repo_root", ".")),
        )
    result = check_scope(diff_files, payload["files_to_touch"])
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_scope_check.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/scope_check.py tests/agentic/test_scope_check.py
git commit -m "feat(agentic): scope-check linter enforcing R7 (files-to-touch)"
```

---

## Phase 4 — PR opener (`scripts/agentic/pr_open.py`)

Always opens PRs as **draft** targeting `main`. Refuses to open against `prod` (R1) or non-draft (R2).

### Task 4.1: Write the failing test

**Files:**
- Create: `tests/agentic/test_pr_open.py`

- [ ] **Step 1: Write the test**

```python
"""Tests for scripts.agentic.pr_open."""
from __future__ import annotations

from unittest.mock import patch

import pytest


def test_build_pr_args_is_draft_to_main():
    from scripts.agentic.pr_open import build_pr_args

    args = build_pr_args(
        head_branch="chunk/http-foundation",
        title="chunk: HTTP foundation (#3, #4)",
        body="Body content",
    )
    assert "--draft" in args
    assert "--base" in args and args[args.index("--base") + 1] == "main"
    assert "--head" in args and args[args.index("--head") + 1] == "chunk/http-foundation"
    assert "--title" in args
    # Non-empty body lands as a body file or arg
    assert "--body-file" in args or "--body" in args


def test_refuses_base_other_than_main():
    from scripts.agentic.pr_open import build_pr_args

    with pytest.raises(ValueError, match="base must be 'main'"):
        build_pr_args(
            head_branch="chunk/x",
            title="x",
            body="x",
            base="prod",
        )


def test_refuses_head_pointing_at_prod():
    from scripts.agentic.pr_open import build_pr_args

    with pytest.raises(ValueError, match="head must not be 'prod'"):
        build_pr_args(
            head_branch="prod",
            title="x",
            body="x",
        )


def test_format_body_includes_closes_lines():
    from scripts.agentic.pr_open import format_body

    body = format_body(
        chunk_name="http-foundation",
        issue_numbers=[3, 4],
        impl_summary="Built session pooling and consolidated _request().",
        test_summary="3 SANDBOX tests passed, 0 failed.",
    )
    assert "Closes #3" in body
    assert "Closes #4" in body
    assert "http-foundation" in body
    assert "SANDBOX" in body
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_pr_open.py -v
```

Expected: 4 failures (module not found).

### Task 4.2: Implement PR opener

**Files:**
- Create: `scripts/agentic/pr_open.py`

- [ ] **Step 1: Write the implementation**

`scripts/agentic/pr_open.py`:

```python
"""Open a draft PR for a chunk integration branch.

Enforces spec R1 (never to prod) and R2 (always draft).
Wraps `gh pr create`.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def format_body(
    chunk_name: str,
    issue_numbers: list[int],
    impl_summary: str,
    test_summary: str,
) -> str:
    closes = "\n".join(f"Closes #{n}" for n in issue_numbers)
    return f"""## Chunk: `{chunk_name}`

{closes}

## Implementation summary

{impl_summary}

## SANDBOX test summary

{test_summary}

## Verification done in the loop

- [x] py_compile on changed files
- [x] smoke_import.py
- [x] tests/test_public_api_contract.py
- [x] scope-check (files-to-touch) per R7
- [x] Per-issue unit tests
- [x] SANDBOX integration tests (see test-results.json in chunks/{chunk_name}/)

## Pending

- [ ] Human PR review
- [ ] Manual merge to `main` (R2 — never auto-merged)
- [ ] (Later) Manual `prod` promotion via test release + soak (R1 — out of pipeline scope)
"""


def build_pr_args(
    head_branch: str,
    title: str,
    body: str,
    base: str = "main",
    body_file: Path | None = None,
) -> list[str]:
    if base != "main":
        raise ValueError(f"base must be 'main' per R1; got {base!r}")
    if head_branch == "prod":
        raise ValueError("head must not be 'prod' per R1")
    if head_branch == "main":
        raise ValueError("head cannot be 'main'; PR must come from a chunk branch")

    args = ["gh", "pr", "create", "--draft", "--base", base, "--head", head_branch,
            "--title", title]
    if body_file is not None:
        args += ["--body-file", str(body_file)]
    else:
        args += ["--body", body]
    return args


def open_pr(
    head_branch: str,
    chunk_name: str,
    issue_numbers: list[int],
    impl_summary: str,
    test_summary: str,
    repo_root: Path,
) -> str:
    """Create the draft PR. Returns the PR URL on success."""
    body = format_body(chunk_name, issue_numbers, impl_summary, test_summary)
    title = f"chunk: {chunk_name} (#{', #'.join(str(n) for n in issue_numbers)})"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir=repo_root
    ) as tf:
        tf.write(body)
        body_file = Path(tf.name)
    try:
        args = build_pr_args(head_branch, title, body=body, body_file=body_file)
        result = subprocess.run(args, cwd=repo_root, capture_output=True, text=True,
                                check=True)
        return result.stdout.strip()
    finally:
        body_file.unlink(missing_ok=True)


def main() -> int:
    import json
    import sys

    payload = json.load(sys.stdin)
    url = open_pr(
        head_branch=payload["head_branch"],
        chunk_name=payload["chunk_name"],
        issue_numbers=payload["issue_numbers"],
        impl_summary=payload["impl_summary"],
        test_summary=payload["test_summary"],
        repo_root=Path(payload.get("repo_root", ".")),
    )
    json.dump({"pr_url": url}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run tests**

```bash
poetry run pytest tests/agentic/test_pr_open.py -v
```

Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/pr_open.py tests/agentic/test_pr_open.py
git commit -m "feat(agentic): PR opener with R1/R2 enforcement (always draft, never to prod)"
```

---

## Phase 5 — Run-log appender (`scripts/agentic/run_log.py`)

Maintains `docs/AGENTIC_RUN_LOG.md` per handbook §11.2.

### Task 5.1: Write the failing test

**Files:**
- Create: `tests/agentic/test_run_log.py`

- [ ] **Step 1: Write the test**

```python
"""Tests for scripts.agentic.run_log."""
from __future__ import annotations

from pathlib import Path


def test_appends_first_row_to_empty_log(tmp_path):
    from scripts.agentic.run_log import append_chunk_row

    log = tmp_path / "AGENTIC_RUN_LOG.md"
    append_chunk_row(
        log_path=log,
        chunk_name="http-foundation",
        issue_numbers=[3, 4],
        attempts_used={3: 1, 4: 2},
        test_outcomes={"passed": 4, "failed": 0, "skipped": 0},
        time_total_seconds=712,
        pr_url="https://github.com/o/r/pull/100",
    )
    text = log.read_text()
    assert "http-foundation" in text
    assert "#3, #4" in text
    assert "100" in text
    assert text.count("|") >= 8  # markdown table row


def test_preserves_existing_rows(tmp_path):
    from scripts.agentic.run_log import append_chunk_row

    log = tmp_path / "AGENTIC_RUN_LOG.md"
    append_chunk_row(log, "first", [1], {1: 1},
                    {"passed": 1, "failed": 0, "skipped": 0}, 60, "url-1")
    append_chunk_row(log, "second", [2], {2: 1},
                    {"passed": 1, "failed": 0, "skipped": 0}, 60, "url-2")
    text = log.read_text()
    assert "first" in text
    assert "second" in text
    # Header appears exactly once
    assert text.count("| chunk_name |") == 1
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_run_log.py -v
```

Expected: 2 failures.

### Task 5.2: Implement the run-log appender

**Files:**
- Create: `scripts/agentic/run_log.py`

- [ ] **Step 1: Write the implementation**

`scripts/agentic/run_log.py`:

```python
"""Append-only chunk log per handbook §11.2 + spec §8 step 5."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

_HEADER = (
    "# AGENTIC RUN LOG\n\n"
    "Append-only log of chunk runs. One row per finished chunk.\n\n"
    "| chunk_name | date | issues | attempts | passed | failed | skipped"
    " | time_s | pr_url |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def append_chunk_row(
    log_path: Path,
    chunk_name: str,
    issue_numbers: list[int],
    attempts_used: dict[int, int],
    test_outcomes: dict[str, int],
    time_total_seconds: int,
    pr_url: str,
) -> None:
    issues_str = ", ".join(f"#{n}" for n in issue_numbers)
    attempts_str = ", ".join(f"#{n}:{a}" for n, a in sorted(attempts_used.items()))
    date = dt.datetime.utcnow().date().isoformat()
    row = (
        f"| {chunk_name} | {date} | {issues_str} | {attempts_str}"
        f" | {test_outcomes.get('passed', 0)}"
        f" | {test_outcomes.get('failed', 0)}"
        f" | {test_outcomes.get('skipped', 0)}"
        f" | {time_total_seconds}"
        f" | {pr_url} |\n"
    )
    if not log_path.exists():
        log_path.write_text(_HEADER + row)
    else:
        existing = log_path.read_text()
        if "| chunk_name |" not in existing:
            log_path.write_text(_HEADER + row)
        else:
            with log_path.open("a") as f:
                f.write(row)


def main() -> int:
    import json
    import sys

    payload = json.load(sys.stdin)
    append_chunk_row(
        log_path=Path(payload["log_path"]),
        chunk_name=payload["chunk_name"],
        issue_numbers=payload["issue_numbers"],
        attempts_used={int(k): int(v) for k, v in payload["attempts_used"].items()},
        test_outcomes=payload["test_outcomes"],
        time_total_seconds=int(payload["time_total_seconds"]),
        pr_url=payload["pr_url"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_run_log.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/run_log.py tests/agentic/test_run_log.py
git commit -m "feat(agentic): chunk run log appender (handbook §11.2)"
```

---

## Phase 6 — Status helper (`scripts/agentic/chunk_status.py`)

Owns the read/write of `chunks/<name>/status.json` per spec §8.5.

### Task 6.1: Write the failing test

**Files:**
- Create: `tests/agentic/test_chunk_status.py`

- [ ] **Step 1: Write the test**

```python
"""Tests for scripts.agentic.chunk_status (spec §8.5)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_init_status_writes_required_fields(tmp_path):
    from scripts.agentic.chunk_status import init_status

    chunk_dir = tmp_path / "chunks" / "http-foundation"
    chunk_dir.mkdir(parents=True)
    init_status(chunk_dir, chunk_name="http-foundation", issues=[3, 4])

    status = json.loads((chunk_dir / "status.json").read_text())
    assert status["chunk"] == "http-foundation"
    assert status["issues"] == [3, 4]
    assert status["stage"] == "defined"
    assert status["branch"] == "chunk/http-foundation"
    assert "createdAt" in status
    assert "updatedAt" in status
    assert status["lastEvent"]
    assert status["nextAction"]


def test_transition_updates_stage_and_event(tmp_path):
    from scripts.agentic.chunk_status import init_status, transition

    chunk_dir = tmp_path / "chunks" / "x"
    chunk_dir.mkdir(parents=True)
    init_status(chunk_dir, chunk_name="x", issues=[1])

    transition(
        chunk_dir,
        new_stage="impl-running",
        last_event="kicked off implementation",
        next_action="wait for completion",
    )
    status = json.loads((chunk_dir / "status.json").read_text())
    assert status["stage"] == "impl-running"
    assert status["lastEvent"] == "kicked off implementation"
    assert status["nextAction"] == "wait for completion"


def test_invalid_stage_rejected(tmp_path):
    from scripts.agentic.chunk_status import init_status, transition

    chunk_dir = tmp_path / "chunks" / "x"
    chunk_dir.mkdir(parents=True)
    init_status(chunk_dir, chunk_name="x", issues=[1])

    with pytest.raises(ValueError, match="invalid stage"):
        transition(chunk_dir, new_stage="bogus", last_event="...", next_action="...")


def test_list_active_excludes_terminal_states(tmp_path):
    from scripts.agentic.chunk_status import init_status, transition, list_active

    for name, terminal in [("a", False), ("b", True), ("c", True)]:
        d = tmp_path / "chunks" / name
        d.mkdir(parents=True)
        init_status(d, chunk_name=name, issues=[1])
        if terminal:
            stage = "merged" if name == "b" else "aborted"
            transition(d, new_stage=stage, last_event="done", next_action="none")

    active = list_active(chunks_root=tmp_path / "chunks")
    names = [s["chunk"] for s in active]
    assert "a" in names
    assert "b" not in names
    assert "c" not in names
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_chunk_status.py -v
```

Expected: 4 failures.

### Task 6.2: Implement status helper

**Files:**
- Create: `scripts/agentic/chunk_status.py`

- [ ] **Step 1: Write the implementation**

`scripts/agentic/chunk_status.py`:

```python
"""Read/write chunks/<name>/status.json per spec §8.5.

The status file is the source of truth for chunk lifecycle. Stages are
discrete; transitions are explicit.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

VALID_STAGES = (
    "defined",
    "impl-running",
    "impl-done",
    "test-data-pending",
    "test-running",
    "test-done",
    "pr-opened",
    "merged",
    "aborted",
)
TERMINAL_STAGES = {"merged", "aborted"}


def _now() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def init_status(chunk_dir: Path, chunk_name: str, issues: list[int]) -> None:
    """Create the initial status.json for a new chunk (stage: defined)."""
    chunk_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "chunk": chunk_name,
        "issues": list(issues),
        "stage": "defined",
        "branch": f"chunk/{chunk_name}",
        "createdAt": _now(),
        "updatedAt": _now(),
        "lastEvent": "Chunk defined; awaiting implementation trigger.",
        "nextAction": f"chunks run-impl {chunk_name}",
        "openBreakpoints": [],
        "implRunId": None,
        "testRunId": None,
        "prUrl": None,
    }
    (chunk_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")


def read_status(chunk_dir: Path) -> dict[str, Any]:
    return json.loads((chunk_dir / "status.json").read_text())


def transition(
    chunk_dir: Path,
    new_stage: str,
    last_event: str,
    next_action: str,
    **extra: Any,
) -> None:
    """Update stage and metadata. `extra` keys overwrite top-level fields."""
    if new_stage not in VALID_STAGES:
        raise ValueError(
            f"invalid stage {new_stage!r}; must be one of {VALID_STAGES}"
        )
    status = read_status(chunk_dir)
    status["stage"] = new_stage
    status["lastEvent"] = last_event
    status["nextAction"] = next_action
    status["updatedAt"] = _now()
    for k, v in extra.items():
        status[k] = v
    (chunk_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")


def list_active(chunks_root: Path) -> list[dict[str, Any]]:
    """Return status objects for all non-terminal chunks, newest first."""
    out: list[dict[str, Any]] = []
    if not chunks_root.exists():
        return out
    for child in chunks_root.iterdir():
        sf = child / "status.json"
        if not sf.exists():
            continue
        status = json.loads(sf.read_text())
        if status["stage"] in TERMINAL_STAGES:
            continue
        out.append(status)
    out.sort(key=lambda s: s.get("updatedAt", ""), reverse=True)
    return out


def list_all(chunks_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not chunks_root.exists():
        return out
    for child in chunks_root.iterdir():
        sf = child / "status.json"
        if sf.exists():
            out.append(json.loads(sf.read_text()))
    out.sort(key=lambda s: s.get("updatedAt", ""), reverse=True)
    return out
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_chunk_status.py -v
```

Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/chunk_status.py tests/agentic/test_chunk_status.py
git commit -m "feat(agentic): chunk status helper (spec §8.5 source of truth)"
```

---

## Phase 7 — `chunks` Bash CLI (`scripts/agentic/chunks`)

Thin wrapper that exposes the Python helpers as subcommands. The agent and human both call this. Per spec §8.5.

### Task 7.1: Write the failing CLI test

**Files:**
- Create: `tests/agentic/test_chunks_cli.py`

- [ ] **Step 1: Write the test**

```python
"""Tests for scripts/agentic/chunks (Bash CLI)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "agentic" / "chunks"


def run_cli(*args: str, env_overrides: dict | None = None, cwd: Path | None = None):
    import os
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(CLI), *args],
        capture_output=True, text=True,
        env=env, cwd=str(cwd or REPO_ROOT),
    )


def test_help_shows_subcommands():
    r = run_cli("help")
    assert r.returncode == 0
    out = r.stdout + r.stderr
    for cmd in ["list", "status", "next", "define", "run-impl", "run-test", "abort"]:
        assert cmd in out


def test_list_empty_chunks_dir(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    r = run_cli("list", env_overrides={"CHUNKS_DIR": str(chunks)})
    assert r.returncode == 0
    assert "no active chunks" in r.stdout.lower() or r.stdout.strip() == ""


def test_refuses_when_prod_key_set(tmp_path):
    """R8 — agent must not run with ALMA_PROD_API_KEY in env."""
    r = run_cli(
        "list",
        env_overrides={
            "CHUNKS_DIR": str(tmp_path / "chunks"),
            "ALMA_PROD_API_KEY": "fake-prod-key",
        },
    )
    assert r.returncode != 0
    assert "ALMA_PROD_API_KEY" in (r.stdout + r.stderr)


def test_unknown_subcommand_errors():
    r = run_cli("frobnicate")
    assert r.returncode != 0
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_chunks_cli.py -v
```

Expected: 4 failures (CLI doesn't exist).

### Task 7.2: Implement the `chunks` CLI

**Files:**
- Create: `scripts/agentic/chunks` (Bash, executable)

- [ ] **Step 1: Write the CLI**

`scripts/agentic/chunks`:

```bash
#!/usr/bin/env bash
# chunks — operator CLI for chunk-driven scaffolding (spec §8.5)
# Subcommands: list | status <name> | next | define ... | run-impl <name>
#              | run-test <name> | abort <name> | help

set -euo pipefail

# R8 — refuse to run with prod credentials in environment
if [[ -n "${ALMA_PROD_API_KEY:-}" ]]; then
  echo "ERROR: ALMA_PROD_API_KEY is set in this environment." >&2
  echo "R8: orchestration env must be SANDBOX-only. Unset it before running." >&2
  exit 2
fi

REPO_ROOT="${REPO_ROOT:-$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || pwd)}"
CHUNKS_DIR="${CHUNKS_DIR:-$REPO_ROOT/chunks}"
PY="${PYTHON:-python}"
SCRIPTS="$REPO_ROOT/scripts/agentic"

usage() {
  cat <<EOF
chunks — operator CLI for chunk-driven scaffolding

Subcommands:
  list                          one-line summary of every active chunk
  status <name>                 full status block for one chunk
  next                          recommended next actions across all chunks
  define --name N --issues 3,4  create new chunk: manifest + status.json
  run-impl <name>               trigger the per-chunk implementation babysitter run
  run-test <name>               trigger the generic chunk-test process
  abort <name>                  mark chunk aborted; leave branches in place
  help                          show this message

Env:
  CHUNKS_DIR     defaults to \$REPO_ROOT/chunks
  REPO_ROOT      defaults to git toplevel of \$0
  PYTHON         python executable for helper invocation (default: python)

Hard rules enforced here:
  R8 — refuses to run if ALMA_PROD_API_KEY is set
EOF
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  help|-h|--help)
    usage
    ;;

  list)
    "$PY" - "$CHUNKS_DIR" <<'PYEOF'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("$REPO_ROOT")))
from scripts.agentic.chunk_status import list_active
chunks = list_active(Path(sys.argv[1]))
if not chunks:
    print("no active chunks")
    sys.exit(0)
for s in chunks:
    print(f"{s['chunk']:<32} {s['stage']:<22} → {s['nextAction']}")
PYEOF
    ;;

  status)
    name="${1:?status: chunk name required}"
    "$PY" - "$CHUNKS_DIR" "$name" <<'PYEOF'
import json, sys
from pathlib import Path
from scripts.agentic.chunk_status import read_status
chunk_dir = Path(sys.argv[1]) / sys.argv[2]
print(json.dumps(read_status(chunk_dir), indent=2))
PYEOF
    ;;

  next)
    "$PY" - "$CHUNKS_DIR" <<'PYEOF'
import sys
from pathlib import Path
from scripts.agentic.chunk_status import list_active
for s in list_active(Path(sys.argv[1])):
    print(f"- {s['chunk']:<32} {s['stage']:<22} → {s['nextAction']}")
    print(f"    last: {s['lastEvent']}")
PYEOF
    ;;

  define)
    # define --name <n> --issues 3,4,14
    name=""
    issues_csv=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --name) name="$2"; shift 2;;
        --issues) issues_csv="$2"; shift 2;;
        *) echo "unknown flag: $1" >&2; exit 2;;
      esac
    done
    [[ -n "$name" && -n "$issues_csv" ]] || { echo "define: --name and --issues required" >&2; exit 2; }
    "$PY" - "$CHUNKS_DIR" "$name" "$issues_csv" <<'PYEOF'
import json, subprocess, sys
from pathlib import Path
from scripts.agentic.chunk_status import init_status
from scripts.agentic.issue_parser import parse_issue
from scripts.agentic.prereq_check import check_prereqs

chunks_dir = Path(sys.argv[1])
name = sys.argv[2]
issue_numbers = [int(x) for x in sys.argv[3].split(",")]
chunk_dir = chunks_dir / name
chunk_dir.mkdir(parents=True, exist_ok=True)

manifest = {"chunk": name, "issues": []}
for n in issue_numbers:
    raw = subprocess.run(
        ["gh", "issue", "view", str(n), "--json",
         "number,title,url,labels,body"],
        capture_output=True, text=True, check=True,
    )
    issue = parse_issue(json.loads(raw.stdout))
    manifest["issues"].append(issue)

# Code-level prereq check (handbook §13)
hard_prereqs = []
for issue in manifest["issues"]:
    for pn in issue.get("hard_prereqs", []):
        # we use a simple convention: prereq's symbol is its issue's title's
        # primary token. Actual symbol resolution requires per-issue heuristics
        # — for now, record the prereq issue number; user resolves manually.
        hard_prereqs.append({"issue": pn, "symbol": "", "where": "src/"})

(chunk_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
init_status(chunk_dir, chunk_name=name, issues=issue_numbers)
print(f"defined chunk '{name}' with issues {issue_numbers}")
print(f"manifest: {chunk_dir / 'manifest.json'}")
print(f"status:   {chunk_dir / 'status.json'}")
print(f"next:     chunks run-impl {name}")
PYEOF
    ;;

  run-impl)
    name="${1:?run-impl: chunk name required}"
    echo "TODO: trigger chunk-<name>-impl.js via babysitter run:create" >&2
    echo "(implementation in Phase 9)" >&2
    exit 1
    ;;

  run-test)
    name="${1:?run-test: chunk name required}"
    echo "TODO: trigger chunk-test.js with chunkName=$name via babysitter run:create" >&2
    echo "(implementation in Phase 8)" >&2
    exit 1
    ;;

  abort)
    name="${1:?abort: chunk name required}"
    "$PY" - "$CHUNKS_DIR" "$name" <<'PYEOF'
import sys
from pathlib import Path
from scripts.agentic.chunk_status import transition
chunk_dir = Path(sys.argv[1]) / sys.argv[2]
transition(chunk_dir, new_stage="aborted",
           last_event="aborted by operator",
           next_action="inspect branches and clean up manually")
print(f"chunk '{sys.argv[2]}' marked aborted")
PYEOF
    ;;

  *)
    echo "unknown subcommand: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/agentic/chunks
```

- [ ] **Step 3: Run tests**

```bash
poetry run pytest tests/agentic/test_chunks_cli.py -v
```

Expected: 4 passed.

- [ ] **Step 4: Manual smoke**

```bash
scripts/agentic/chunks help
```

Expected: usage text including all subcommands.

- [ ] **Step 5: Commit**

```bash
git add scripts/agentic/chunks tests/agentic/test_chunks_cli.py
git commit -m "feat(agentic): chunks CLI (list/status/next/define/abort), R8 enforcement"
```

> **Note on `run-impl` / `run-test`:** these subcommands stub out with exit 1 here. They get filled in Phase 8 (test process) and Phase 9 (impl process generator) once those exist.

---

## Phase 8 — Generic test process (`.a5c/processes/chunk-test.js`)

Stages 5–6 per spec. Reads `test-recommendation.json`, interviews the human via breakpoint, runs SANDBOX tests, captures results.

### Task 8.1: Write a JS lint smoke test

**Files:**
- Create: `tests/agentic/test_chunk_test_process.py`

- [ ] **Step 1: Write the test**

```python
"""Smoke tests for .a5c/processes/chunk-test.js."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESS = REPO_ROOT / ".a5c" / "processes" / "chunk-test.js"


def test_chunk_test_js_exists():
    assert PROCESS.exists(), f"missing {PROCESS}"


def test_chunk_test_js_passes_node_check():
    # node --check parses but doesn't run; catches syntax errors
    r = subprocess.run(
        ["node", "--check", str(PROCESS)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"syntax error:\n{r.stderr}"


def test_chunk_test_js_exports_process():
    # Use a tiny dynamic-import script to confirm shape
    script = (
        "import('" + str(PROCESS) + "').then(m => {"
        "if (typeof m.process !== 'function') process.exit(1);"
        "console.log('ok')});"
    )
    r = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"import failed:\n{r.stderr}"
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_chunk_test_process.py -v
```

Expected: 3 failures (file missing).

### Task 8.2: Write `chunk-test.js`

**Files:**
- Create: `.a5c/processes/chunk-test.js`

- [ ] **Step 1: Write the file**

`.a5c/processes/chunk-test.js`:

```js
/**
 * @process chunk-test
 * @description Generic interactive testing process for any chunk. Reads
 *   chunks/<name>/test-recommendation.json, interviews the human for fixtures
 *   via a single breakpoint, runs SANDBOX tests, writes test-results.json.
 *   Implements stages 5-6 of spec §7.
 * @inputs { chunkName: string, repoRoot: string }
 * @outputs { resultsPath: string, summary: object }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

// ---------- shell tasks ----------

export const validateEnvTask = defineTask('validate-env', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Validate test environment (R8: SANDBOX-only credentials)',
  shell: {
    command: `set -e
# R8: refuse if prod key is set
if [ -n "$ALMA_PROD_API_KEY" ]; then
  echo "R8 violation: ALMA_PROD_API_KEY must not be set" >&2
  exit 2
fi
# Sandbox key must be present for tests to run
if [ -z "$ALMA_SB_API_KEY" ]; then
  echo "ALMA_SB_API_KEY not set — required to run SANDBOX tests" >&2
  exit 2
fi
# Repo must be on the chunk integration branch
cd "${args.repoRoot}"
git rev-parse --abbrev-ref HEAD
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const readTestRecTask = defineTask('read-test-rec', (args, taskCtx) => ({
  kind: 'shell',
  title: `Read test-recommendation.json for chunk ${args.chunkName}`,
  shell: {
    command: `cat "${args.repoRoot}/chunks/${args.chunkName}/test-recommendation.json"`,
    timeout: 5000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const writeTestDataTask = defineTask('write-test-data', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Write test-data.json from operator interview answers',
  shell: {
    command: `cat > "${args.repoRoot}/chunks/${args.chunkName}/test-data.json" <<'EOF'
${JSON.stringify(args.testData, null, 2)}
EOF
echo "wrote test-data.json"`,
    timeout: 5000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const checkoutBranchTask = defineTask('checkout-branch', (args, taskCtx) => ({
  kind: 'shell',
  title: `Checkout chunk integration branch chunk/${args.chunkName}`,
  shell: {
    command: `cd "${args.repoRoot}" && git fetch origin && git checkout chunk/${args.chunkName} && git status --short`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// ---------- agent tasks ----------

export const generatePytestFilesTask = defineTask('generate-pytest', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Generate pytest files from test-recommendation + test-data',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python test engineer',
      task: `For chunk "${args.chunkName}", read:
- ${args.repoRoot}/chunks/${args.chunkName}/test-recommendation.json
- ${args.repoRoot}/chunks/${args.chunkName}/test-data.json

For each test in the recommendation, generate a pytest file at:
  ${args.repoRoot}/chunks/${args.chunkName}/sandbox-tests/test_<test.id>.py

Each pytest file:
  1. Imports AlmaAPIClient and the relevant domain class.
  2. Substitutes \${var} placeholders in pythonCalls from test-data.json.
  3. Runs each pythonCall and asserts every passCriterion.
  4. If stateChanging is true, runs cleanup in a try/finally — failure to clean is a FAIL.
  5. Uses ALMA_SB_API_KEY (never PROD).

Return JSON: { "filesWritten": [...], "tests": [{id, path, stateChanging, hasCleanup}] }`,
      outputFormat: 'JSON',
    },
    outputSchema: { type: 'object', required: ['filesWritten', 'tests'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const runPytestTask = defineTask('run-pytest', (args, taskCtx) => ({
  kind: 'shell',
  title: `Run SANDBOX test ${args.testId}`,
  shell: {
    command: `cd "${args.repoRoot}" && \
      poetry run pytest "${args.testFile}" -v --tb=short \
      > "chunks/${args.chunkName}/sandbox-test-output/${args.testId}.log" 2>&1
echo $?`,
    timeout: 300000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const aggregateResultsTask = defineTask('aggregate-results', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Aggregate per-test outcomes into test-results.json',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Test results aggregator',
      task: `Read every log file under ${args.repoRoot}/chunks/${args.chunkName}/sandbox-test-output/.
For each, determine pass/fail/skipped and extract the assertion details.
Aggregate into a single JSON written to ${args.repoRoot}/chunks/${args.chunkName}/test-results.json with shape:

{
  "chunk": "${args.chunkName}",
  "testRunStartedAt": "...",
  "testRunFinishedAt": "...",
  "perTest": [{"id": "t-3-1", "outcome": "passed|failed|skipped", "issueNumber": 3, "stateChanging": false, "cleanupStatus": "n/a|ok|failed", "details": "..."}],
  "perIssue": [{"number": 3, "everyAcMapped": true, "everyTestPassed": true, "anySkips": false, "autoCloseEligible": true}]
}

Return the same JSON.`,
      outputFormat: 'JSON',
    },
    outputSchema: { type: 'object', required: ['chunk', 'perTest', 'perIssue'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// ---------- main ----------

export async function process(inputs, ctx) {
  const { chunkName, repoRoot } = inputs;
  if (!chunkName) throw new Error('chunkName is required');
  if (!repoRoot) throw new Error('repoRoot is required');

  ctx.log(`chunk-test for ${chunkName}: stage 5-6`);

  await ctx.task(validateEnvTask, { repoRoot });

  const testRec = await ctx.task(readTestRecTask, { chunkName, repoRoot });

  // Aggregate every needsHumanInput.key across all tests for one breakpoint
  const fixtures = new Map();
  for (const issue of testRec.issues || []) {
    for (const t of issue.tests || []) {
      for (const f of t.needsHumanInput || []) {
        if (!fixtures.has(f.key)) fixtures.set(f.key, f);
      }
    }
  }

  let testData = {};
  if (fixtures.size > 0) {
    const answers = await ctx.breakpoint({
      title: `Test fixtures for chunk "${chunkName}"`,
      message: 'Provide values for these fixtures (must already exist in SANDBOX):',
      fields: Array.from(fixtures.values()).map(f => ({
        key: f.key,
        label: f.description,
        placeholder: f.example || '',
      })),
    });
    if (!answers.approved) {
      throw new Error('operator declined to provide fixtures; aborting test run');
    }
    testData = answers.values || {};
  }

  await ctx.task(writeTestDataTask, { chunkName, repoRoot, testData });
  await ctx.task(checkoutBranchTask, { chunkName, repoRoot });
  const generated = await ctx.task(generatePytestFilesTask, { chunkName, repoRoot });

  for (const t of generated.tests) {
    await ctx.task(runPytestTask, {
      chunkName, repoRoot,
      testId: t.id, testFile: t.path,
    });
  }

  const results = await ctx.task(aggregateResultsTask, { chunkName, repoRoot });

  return {
    resultsPath: `${repoRoot}/chunks/${chunkName}/test-results.json`,
    summary: results,
  };
}
```

- [ ] **Step 2: Run lint tests**

```bash
poetry run pytest tests/agentic/test_chunk_test_process.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Wire `chunks run-test` to actually invoke this**

Modify `scripts/agentic/chunks` — replace the `run-test)` block with:

```bash
  run-test)
    name="${1:?run-test: chunk name required}"
    cd "$REPO_ROOT"
    inputs="$(mktemp --suffix=.json)"
    cat > "$inputs" <<EOF
{"chunkName": "$name", "repoRoot": "$REPO_ROOT"}
EOF
    babysitter run:create \
      --process-id "chunk-test-$name" \
      --entry "$REPO_ROOT/.a5c/processes/chunk-test.js#process" \
      --inputs "$inputs" \
      --prompt "Run SANDBOX tests for chunk $name" \
      --harness claude-code \
      --json
    "$PY" - "$CHUNKS_DIR" "$name" <<'PYEOF'
import sys
from pathlib import Path
from scripts.agentic.chunk_status import transition
transition(Path(sys.argv[1]) / sys.argv[2], "test-data-pending",
           "test process started; awaiting fixture interview",
           "answer the data interview when prompted")
PYEOF
    ;;
```

- [ ] **Step 4: Re-run CLI tests to confirm nothing broke**

```bash
poetry run pytest tests/agentic/test_chunks_cli.py tests/agentic/test_chunk_test_process.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add .a5c/processes/chunk-test.js scripts/agentic/chunks tests/agentic/test_chunk_test_process.py
git commit -m "feat(agentic): chunk-test.js generic interactive SANDBOX test process"
```

---

## Phase 9 — Per-chunk implementation generator (`.a5c/processes/chunk-template-impl.js`)

Stages 2–3 per spec. Reads `chunks/<name>/manifest.json` and emits a tailored `.a5c/processes/chunk-<name>-impl.js` (or executes inline — see Step 1 below).

### Task 9.1: Write JS lint smoke test

**Files:**
- Create: `tests/agentic/test_chunk_template_impl.py`

- [ ] **Step 1: Write the test**

```python
"""Smoke tests for .a5c/processes/chunk-template-impl.js."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESS = REPO_ROOT / ".a5c" / "processes" / "chunk-template-impl.js"


def test_template_impl_exists():
    assert PROCESS.exists()


def test_template_impl_passes_node_check():
    r = subprocess.run(["node", "--check", str(PROCESS)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_template_impl_exports_process_and_named_tasks():
    script = (
        "import('" + str(PROCESS) + "').then(m => {"
        "['process','validateEnvTask','implementTask','staticGatesTask',"
        "'scopeCheckTask','unitTestsTask','contractTestTask','mergeIntoIntegrationTask']"
        ".forEach(n => { if (!(n in m)) { console.error('missing: ' + n); process.exit(1); } });"
        "console.log('ok')});"
    )
    r = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_chunk_template_impl.py -v
```

Expected: 3 failures.

### Task 9.2: Write the implementation process file

**Files:**
- Create: `.a5c/processes/chunk-template-impl.js`

- [ ] **Step 1: Write the file**

`.a5c/processes/chunk-template-impl.js`:

```js
/**
 * @process chunk-template-impl
 * @description Per-chunk implementation runner. Reads chunks/<name>/manifest.json
 *   and processes each issue on its own sub-branch with a 3-attempt refinement
 *   loop, then merges into the integration branch. Implements stages 2-3 of
 *   spec §5.
 * @inputs { chunkName: string, repoRoot: string, maxAttempts?: number }
 * @outputs { mergedSubBranches: string[], testRecommendationPath: string }
 */
import pkg from '@a5c-ai/babysitter-sdk';
import { readFileSync } from 'node:fs';
const { defineTask } = pkg;

// ---------- shell tasks ----------

export const validateEnvTask = defineTask('validate-env', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Validate baseline (clean tree, on integration branch, smoke passes)',
  shell: {
    command: `set -e
if [ -n "$ALMA_PROD_API_KEY" ]; then
  echo "R8 violation: ALMA_PROD_API_KEY must not be set" >&2
  exit 2
fi
cd "${args.repoRoot}"
git diff --quiet || (echo "tree dirty" >&2; exit 2)
HEAD_BRANCH="$(git symbolic-ref --short HEAD)"
[ "$HEAD_BRANCH" = "chunk/${args.chunkName}" ] || (echo "expected on chunk/${args.chunkName}, on $HEAD_BRANCH" >&2; exit 2)
poetry run python scripts/smoke_import.py
`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const createSubBranchTask = defineTask('create-sub-branch', (args, taskCtx) => ({
  kind: 'shell',
  title: `Create sub-branch feat/${args.issueNumber}-${args.slug}`,
  shell: {
    command: `cd "${args.repoRoot}" && \
      git checkout chunk/${args.chunkName} && \
      git checkout -b feat/${args.issueNumber}-${args.slug}`,
    timeout: 15000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const staticGatesTask = defineTask('static-gates', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Static gates: py_compile + smoke_import',
  shell: {
    command: `cd "${args.repoRoot}" && \
      python -m py_compile $(git diff --name-only chunk/${args.chunkName}...HEAD | grep '\\.py$' || true) && \
      poetry run python scripts/smoke_import.py`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const scopeCheckTask = defineTask('scope-check', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Scope-check (R7): every changed file is in Files-to-touch',
  shell: {
    command: `cd "${args.repoRoot}" && \
      python -c "
import json, sys, subprocess
from scripts.agentic.scope_check import check_scope
diff = subprocess.run(['git','diff','--name-only','chunk/${args.chunkName}...HEAD'],
                     capture_output=True,text=True,check=True).stdout.split()
files = ${JSON.stringify(args.filesToTouch)}
result = check_scope([f for f in diff if f.strip()], files)
print(json.dumps(result))
sys.exit(0 if result['pass'] else 2)
"`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const unitTestsTask = defineTask('unit-tests', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Unit tests for changed files',
  shell: {
    command: `cd "${args.repoRoot}" && poetry run pytest tests/unit/ -v --tb=short`,
    timeout: 300000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const contractTestTask = defineTask('contract-test', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Public API contract test',
  shell: {
    command: `cd "${args.repoRoot}" && poetry run pytest tests/test_public_api_contract.py -v`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const mergeIntoIntegrationTask = defineTask('merge-integration', (args, taskCtx) => ({
  kind: 'shell',
  title: `Merge feat/${args.issueNumber}-${args.slug} into integration branch`,
  shell: {
    command: `cd "${args.repoRoot}" && \
      git checkout chunk/${args.chunkName} && \
      git merge --no-ff feat/${args.issueNumber}-${args.slug} \
        -m "merge feat/${args.issueNumber}-${args.slug} into chunk/${args.chunkName}"`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// ---------- agent tasks ----------

export const implementTask = defineTask('implement', (args, taskCtx) => ({
  kind: 'agent',
  title: `Implement issue #${args.issueNumber} (attempt ${args.attempt || 1})`,
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer maintaining the almaapitk package',
      task: `Implement GitHub issue #${args.issueNumber} on branch feat/${args.issueNumber}-${args.slug}.`,
      context: {
        issueBody: args.issueBody,
        filesToTouch: args.filesToTouch,
        feedback: args.feedback || null,
        attemptNumber: args.attempt || 1,
        promptTemplatePath: 'scripts/agentic/prompts/implement.v1.md',
      },
      instructions: [
        'Read scripts/agentic/prompts/implement.v1.md and follow it strictly.',
        'Use AlmaAPIClient for HTTP. Validate inputs with AlmaValidationError.',
        'Use self.logger; never print.',
        'Type hints + Google-style docstrings on all public methods.',
        'Implement ONLY what the issue says.',
        'Do not modify any file not in Files to touch.',
        'Add unit tests under tests/unit/domains/ with mocked HTTP (responses or requests-mock).',
        'When done, list every file you changed.',
      ],
      outputFormat: 'JSON: { filesChanged: string[], summary: string, testsAdded: string[] }',
    },
    outputSchema: { type: 'object', required: ['filesChanged', 'summary'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const buildTestRecTask = defineTask('build-test-rec', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Build test-recommendation.json from chunk manifest + diff',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Test plan author',
      task: `Read:
- ${args.repoRoot}/chunks/${args.chunkName}/manifest.json (issues, ACs, endpoints, files)
- The diff: git diff main...chunk/${args.chunkName} (run via shell)
- ${args.repoRoot}/scripts/agentic/prompts/test-recommendation.v1.md (the rules)

Produce ${args.repoRoot}/chunks/${args.chunkName}/test-recommendation.json conforming to the schema in spec §6.1.

For each issue, every AC in the issue body must map to at least one test.id in acceptanceMapping. ACs that genuinely cannot be exercised against SANDBOX go in unmappable[] with a clear reason.

Return: { path, summary }`,
      outputFormat: 'JSON',
    },
    outputSchema: { type: 'object', required: ['path'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// ---------- main ----------

export async function process(inputs, ctx) {
  const { chunkName, repoRoot } = inputs;
  const maxAttempts = inputs.maxAttempts || 3; // R6
  if (!chunkName) throw new Error('chunkName is required');
  if (!repoRoot) throw new Error('repoRoot is required');

  ctx.log(`chunk-impl for ${chunkName} (max ${maxAttempts} attempts per issue)`);

  // Read manifest
  const manifest = JSON.parse(
    readFileSync(`${repoRoot}/chunks/${chunkName}/manifest.json`, 'utf8')
  );

  await ctx.task(validateEnvTask, { repoRoot, chunkName });

  const merged = [];
  for (const issue of manifest.issues) {
    const slug = (issue.title || '').toLowerCase()
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 30);
    const subBranch = `feat/${issue.number}-${slug}`;

    await ctx.task(createSubBranchTask, {
      repoRoot, chunkName, issueNumber: issue.number, slug,
    });

    let feedback = null;
    let success = false;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      await ctx.task(implementTask, {
        repoRoot, issueNumber: issue.number, slug,
        issueBody: issue.body_raw,
        filesToTouch: issue.files_to_touch,
        feedback, attempt,
      });

      let stage = 'static';
      try {
        await ctx.task(staticGatesTask, { repoRoot, chunkName });
        stage = 'scope';
        await ctx.task(scopeCheckTask, {
          repoRoot, chunkName, filesToTouch: issue.files_to_touch,
        });
        stage = 'unit';
        await ctx.task(unitTestsTask, { repoRoot });
        stage = 'contract';
        await ctx.task(contractTestTask, { repoRoot });
        success = true;
        break;
      } catch (e) {
        feedback = `attempt ${attempt} failed at ${stage}-gate: ${e.message || e}`;
        ctx.log(feedback);
      }
    }

    if (!success) {
      const decision = await ctx.breakpoint({
        title: `Issue #${issue.number} exhausted ${maxAttempts} attempts`,
        options: [
          { value: 'manual', label: 'I will take over manually; resume from merge' },
          { value: 'drop', label: 'Drop this issue from the chunk; continue with next' },
          { value: 'abort', label: 'Abort the entire chunk' },
        ],
      });
      if (decision.value === 'abort') {
        throw new Error(`chunk aborted by operator at issue #${issue.number}`);
      }
      if (decision.value === 'drop') {
        ctx.log(`dropped issue #${issue.number}`);
        continue;
      }
      // manual fall-through to merge
    }

    await ctx.task(mergeIntoIntegrationTask, {
      repoRoot, chunkName, issueNumber: issue.number, slug,
    });
    merged.push(subBranch);
  }

  const testRec = await ctx.task(buildTestRecTask, { repoRoot, chunkName });

  return {
    mergedSubBranches: merged,
    testRecommendationPath: testRec.path,
  };
}
```

- [ ] **Step 2: Run smoke tests**

```bash
poetry run pytest tests/agentic/test_chunk_template_impl.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Wire `chunks run-impl`**

In `scripts/agentic/chunks`, replace the `run-impl)` block with:

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
    babysitter run:create \
      --process-id "chunk-impl-$name" \
      --entry "$REPO_ROOT/.a5c/processes/chunk-template-impl.js#process" \
      --inputs "$inputs" \
      --prompt "Implement chunk $name on integration branch" \
      --harness claude-code \
      --json
    "$PY" - "$CHUNKS_DIR" "$name" <<'PYEOF'
import sys
from pathlib import Path
from scripts.agentic.chunk_status import transition
transition(Path(sys.argv[1]) / sys.argv[2], "impl-running",
           "implementation babysitter run created",
           "monitor babysitter run; resume CLI when done")
PYEOF
    ;;
```

- [ ] **Step 4: Run all tests**

```bash
poetry run pytest tests/agentic/ -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add .a5c/processes/chunk-template-impl.js scripts/agentic/chunks tests/agentic/test_chunk_template_impl.py
git commit -m "feat(agentic): chunk-template-impl.js with R6 (3-attempt cap) and R7 (scope-check)"
```

---

## Phase 10 — Versioned prompt templates

Per spec §5.3 and handbook §6 — keep prompts as versioned Markdown so changes are traceable.

### Task 10.1: Author `implement.v1.md`

**Files:**
- Create: `scripts/agentic/prompts/implement.v1.md`

- [ ] **Step 1: Write the prompt template**

`scripts/agentic/prompts/implement.v1.md`:

```markdown
# Implementation Prompt — v1

You are a senior Python developer maintaining the `almaapitk` package. Mirror the existing project style exactly.

## Inputs the runner provides

- `issueBody` — the full GitHub issue body (parsed but verbatim).
- `filesToTouch` — list of file paths you may modify. **Do not modify any other file.**
- `feedback` — non-null on retries; previous attempt's failure summary.
- `attemptNumber` — 1, 2, or 3.

## Inviolable rules

1. **R7:** Modify only files in `filesToTouch`. The scope-check gate will reject the attempt otherwise.
2. **No `print` calls.** Always `self.logger`.
3. **Type hints + Google-style docstrings** on every public method.
4. **Validate inputs** at method top via `AlmaValidationError`.
5. **No bare `except:`.**
6. **Use `responses` or `requests-mock`** for HTTP in unit tests. Do NOT write integration tests in this PR — those live in the testing process.
7. **Cite a pattern source** in your code comment when adding a method: which existing method's shape you mirrored.

## When `feedback` is non-null

The previous attempt failed. The feedback string names the gate that failed (`static`, `scope`, `unit`, `contract`) and the relevant output. Address that root cause; do not also refactor unrelated code.

## Output

Return strict JSON:

```json
{
  "filesChanged": ["path/1.py", "tests/unit/path/2.py"],
  "summary": "3-bullet PR-body-style summary",
  "testsAdded": ["test_x_returns_response", "test_x_raises_on_empty_id"]
}
```

## Anti-patterns (do not do these)

- Implement the issue "however you see fit" — produces inconsistent style.
- Improve the package while you're at it — scope creep.
- Re-implement an existing method — read the issue's `DO NOT re-implement` block first.
- Invent endpoints — use only those listed in `API endpoints touched`.
- Write a test that just calls the method without asserting on the response shape.
```

- [ ] **Step 2: Verify the file is readable**

```bash
test -s scripts/agentic/prompts/implement.v1.md && echo OK
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add scripts/agentic/prompts/implement.v1.md
git commit -m "docs(agentic): implementation prompt template v1"
```

### Task 10.2: Author `test-recommendation.v1.md`

**Files:**
- Create: `scripts/agentic/prompts/test-recommendation.v1.md`

- [ ] **Step 1: Write**

`scripts/agentic/prompts/test-recommendation.v1.md`:

```markdown
# Test-Recommendation Prompt — v1

You produce `chunks/<name>/test-recommendation.json` for one chunk. The schema is in spec §6.1.

## Construction rules

1. Read every AC line from each issue body literally.
2. Assign **at least one test.id per AC** in `acceptanceMapping`. If you cannot, list the AC under `unmappable[]` with a concrete reason.
3. Default `kind` to `smoke` (one read call) when in doubt. Only escalate to `round-trip` when the AC genuinely requires CRUD verification.
4. Every test with `stateChanging: true` MUST have a non-null `cleanup` block. **No exceptions** (R5).
5. Every fixture the test needs goes in `needsHumanInput[]` with: `key`, `description`, `example`. Be specific (`"existing user_primary_id with at least one active loan"` beats `"a user"`).
6. `pythonCalls` are exact Python statements. Use `${var}` for fixtures.
7. `passCriteria` are plain English; the test runner will turn each into a pytest assertion.
8. `endpoints` lists only the endpoints actually touched by `pythonCalls` (no aspirational "we should also test...").

## What to never do

- Invent tests for ACs you can't actually verify against SANDBOX. Use `unmappable[]` instead.
- Mark a test `stateChanging: false` to skip cleanup — the runner cross-checks endpoints; lying here is a hard breakpoint.
- Reuse a fixture key with a different description across tests. Fixtures are aggregated by `key`; conflicting descriptions confuse the operator.
- Suggest tests against PROD. Only SANDBOX (R8).

## Output

Write the JSON file. Return: `{ "path": "chunks/<name>/test-recommendation.json", "summary": "<brief>" }`.
```

- [ ] **Step 2: Commit**

```bash
git add scripts/agentic/prompts/test-recommendation.v1.md
git commit -m "docs(agentic): test-recommendation prompt template v1"
```

### Task 10.3: Author `summary-triage.v1.md`

**Files:**
- Create: `scripts/agentic/prompts/summary-triage.v1.md`

- [ ] **Step 1: Write**

`scripts/agentic/prompts/summary-triage.v1.md`:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add scripts/agentic/prompts/summary-triage.v1.md
git commit -m "docs(agentic): summary-and-triage prompt template v1"
```

---

## Phase 11 — Operator playbook (`docs/CHUNK_PLAYBOOK.md`)

Per spec §8.5 — the cheat sheet that captures the session-start convention and walks the operator through a chunk lifecycle.

### Task 11.1: Author the playbook

**Files:**
- Create: `docs/CHUNK_PLAYBOOK.md`

- [ ] **Step 1: Write**

`docs/CHUNK_PLAYBOOK.md`:

```markdown
# Chunk Playbook — Operator's Cheat Sheet

This is your reference for running chunks day-to-day. Design context lives in `docs/superpowers/specs/2026-05-03-chunk-driven-implementation-design.md`. This document is operational, not architectural.

## Session-start convention (for the agent)

When a Claude Code session opens in this repo and `chunks/` contains active chunks (any chunk whose `stage` is not `merged` or `aborted`), the agent's first message MUST include a one-paragraph dashboard built from `scripts/agentic/chunks list`:

> *"You have N active chunks. **`<name>`** (#X, #Y): `<stage>`, last event `<lastEvent>`, next `<nextAction>`. ..."*

The agent then asks what you want to do (drill into one, define a new one, no-op).

## Inviolable rules (R1–R8 from the spec)

| Rule | Plain English |
|---|---|
| R1 | Never push or merge to `prod`. The agent never touches `prod`. |
| R2 | No PR is auto-merged. PRs always open as drafts. You merge. |
| R3 | Implementation and testing are separate runs. You trigger each. |
| R4 | Auto-close only when every AC has a passing SANDBOX test. |
| R5 | Every state-changing test has a cleanup. Cleanup failure is a hard stop. |
| R6 | 3-attempt cap on implementation refinement. After that, you decide. |
| R7 | Agents don't edit files outside the issue's Files-to-touch list. |
| R8 | Orchestration env is SANDBOX-only. `ALMA_PROD_API_KEY` must not be set. |

## End-to-end walkthrough

### 1. Define a chunk

Pick 1–5 related issues. Name the chunk something short and specific.

```bash
scripts/agentic/chunks define --name http-foundation --issues 3,4
```

What this does:
- Calls `gh issue view` for each number; parses Domain, Priority, Effort, Files-to-touch, Prereqs, ACs.
- Code-checks every hard prereq against `main` (per handbook §13).
- Writes `chunks/http-foundation/manifest.json` + `status.json` (stage: `defined`).

If a hard prereq is missing in code, the CLI exits 2 and you must merge that prereq first.

### 2. Trigger implementation

```bash
scripts/agentic/chunks run-impl http-foundation
```

What this does:
- Creates the integration branch `chunk/http-foundation` off `main` if it doesn't exist.
- Creates a babysitter run using `.a5c/processes/chunk-template-impl.js`.
- Updates status to `impl-running`.

The babysitter run will:
- For each issue, create `feat/<N>-<slug>`, run the implementation agent (max 3 attempts), run static-gates → scope-check (R7) → unit tests → contract tests, then merge into the integration branch with `--no-ff`.
- After all issues, generate `chunks/http-foundation/test-recommendation.json`.
- Set status to `impl-done`.

If any issue exhausts 3 attempts: the run breakpoints. Pick `manual` (you fix it), `drop` (skip this issue, continue), or `abort`.

### 3. Inspect the implementation

```bash
scripts/agentic/chunks status http-foundation
git log --oneline main..chunk/http-foundation
cat chunks/http-foundation/test-recommendation.json | jq .
cat chunks/http-foundation/implementation-summary.md
```

Edit the test-recommendation.json if you want to drop a test or add a fixture. The testing process reads it as-is.

### 4. Trigger testing

When you're ready to put fixtures together:

```bash
scripts/agentic/chunks run-test http-foundation
```

What this does:
- Creates a babysitter run using `.a5c/processes/chunk-test.js`.
- The run will breakpoint on a single fixture interview — you'll see one form-style prompt asking for every fixture key the chunk's tests need.
- After you answer, the run executes each test against SANDBOX, captures pass/fail, runs cleanups, and writes `chunks/http-foundation/test-results.json`.
- Status moves through `test-data-pending` → `test-running` → `test-done`.

### 5. PR and triage

After tests complete, the run:
- Opens a draft PR `chunk/http-foundation` → `main` (R2 enforced — always draft).
- Per issue: auto-closes if perfect-green (R4), else applies a label.
- Appends to `docs/AGENTIC_RUN_LOG.md`.

Status moves to `pr-opened`.

### 6. Manual merge (your call, your hands)

Open the PR. Review the diff. Flip ready. Merge to `main`.

Status: still `pr-opened` (the agent doesn't auto-update on merge — `gh pr merge` is yours). Optionally:

```bash
scripts/agentic/chunks status http-foundation  # to refresh after manual update if you wire that
```

You can manually transition the chunk to `merged`:

```bash
python -c "from scripts.agentic.chunk_status import transition; from pathlib import Path; transition(Path('chunks/http-foundation'), 'merged', 'merged via gh', 'soak before prod release')"
```

### 7. Prod promotion (entirely outside this pipeline — R1)

When you're ready, your manual flow:
1. Cut a GitHub test release from `main`.
2. Soak it.
3. `git checkout prod && git merge main && git push origin prod`.

The agent never participates in step 1, 2, or 3. R1 is hard.

## Common things you'll do

### See what's active

```bash
scripts/agentic/chunks list
```

### See what to do next

```bash
scripts/agentic/chunks next
```

### Drill into one chunk

```bash
scripts/agentic/chunks status <name>
```

### Abort

```bash
scripts/agentic/chunks abort <name>
```

This marks the chunk aborted but **leaves all branches alive** so you can inspect.

## Failure recipes

### "A hard prereq isn't merged"

Two options: merge it first, OR drop the dependent issue from the chunk and try again.

### "Implementation failed 3 attempts on issue #X"

You'll get a breakpoint. Pick `manual` and:
1. Check out `feat/X-<slug>`.
2. Fix it by hand.
3. Run `python -m py_compile` + `pytest tests/unit/` to confirm green.
4. Approve the breakpoint with `manual`; the run merges your work into integration.

### "SANDBOX cleanup failed"

Hard breakpoint. Note the entity that wasn't cleaned (POL, invoice, user attachment, etc.) from the breakpoint message; remove it manually via Alma UI or a one-off script. Resume the run.

### "Test interview asks for a fixture I don't have"

Either provision the fixture in SANDBOX (create a test vendor, etc.) or edit `test-recommendation.json` to drop the test that needs it. Re-run `chunks run-test`.

## Notes

- `chunks/<name>/` is checked into git per the user-memory rule "always include `.a5c/` artifacts in commits". `sandbox-test-output/` and `sandbox-tests/` are gitignored (raw logs, not historical truth).
- Prompt templates are versioned (`scripts/agentic/prompts/implement.v1.md`, etc.). When you change one, bump to `v2.md`. Existing chunk artifacts are not re-generated retroactively.
- The run log (`docs/AGENTIC_RUN_LOG.md`) is your calibration data. After every wave of chunks, look at attempts/passes/review-time and tune the prompt.
```

- [ ] **Step 2: Verify**

```bash
wc -l docs/CHUNK_PLAYBOOK.md
test $(wc -l < docs/CHUNK_PLAYBOOK.md) -gt 100
```

Expected: > 100 lines (the playbook is substantive).

- [ ] **Step 3: Commit**

```bash
git add docs/CHUNK_PLAYBOOK.md
git commit -m "docs(agentic): operator playbook for chunk lifecycle"
```

---

## Phase 12 — End-to-end smoke test

Verify the whole scaffolding works together against the synthetic issue #999 fixture.

### Task 12.1: Write the smoke test

**Files:**
- Create: `tests/agentic/test_e2e_smoke.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end smoke: parse → manifest → status → CLI → no babysitter run.

This test does NOT spawn a real babysitter run (those are integration-tested
manually). It verifies that the Python+CLI pipeline can:

1. Parse the synthetic issue fixture.
2. Write a manifest containing the parsed issue.
3. Initialize chunks/<name>/status.json correctly.
4. The chunks CLI can list/status/abort the chunk.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


def test_e2e_pipeline_round_trip(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    chunk_dir = chunks_dir / "synthetic"
    chunk_dir.mkdir()

    # Step 1: parse synthetic issue
    from scripts.agentic.issue_parser import parse_issue
    raw = json.loads((FIXTURES / "issue-999.json").read_text())
    parsed = parse_issue(raw)
    assert parsed["number"] == 999

    # Step 2: write manifest
    manifest = {"chunk": "synthetic", "issues": [parsed]}
    (chunk_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Step 3: init status
    from scripts.agentic.chunk_status import init_status, list_active
    init_status(chunk_dir, chunk_name="synthetic", issues=[999])
    assert (chunk_dir / "status.json").exists()
    active = list_active(chunks_root=chunks_dir)
    assert len(active) == 1
    assert active[0]["chunk"] == "synthetic"

    # Step 4: CLI list shows the chunk
    env = os.environ.copy()
    env["CHUNKS_DIR"] = str(chunks_dir)
    env.pop("ALMA_PROD_API_KEY", None)
    cli = REPO_ROOT / "scripts" / "agentic" / "chunks"
    r = subprocess.run([str(cli), "list"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "synthetic" in r.stdout

    # Step 5: CLI abort moves it to terminal state
    r = subprocess.run([str(cli), "abort", "synthetic"], env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    final = json.loads((chunk_dir / "status.json").read_text())
    assert final["stage"] == "aborted"

    # Step 6: list now shows no active chunks
    r = subprocess.run([str(cli), "list"], env=env, capture_output=True, text=True)
    assert "synthetic" not in r.stdout or "no active" in r.stdout.lower()
```

- [ ] **Step 2: Run**

```bash
poetry run pytest tests/agentic/test_e2e_smoke.py -v
```

Expected: PASS.

- [ ] **Step 3: Run the full agentic suite**

```bash
poetry run pytest tests/agentic/ -v
```

Expected: every test green.

- [ ] **Step 4: Commit**

```bash
git add tests/agentic/test_e2e_smoke.py
git commit -m "test(agentic): end-to-end smoke for parse→manifest→status→CLI"
```

---

## Self-review (run before declaring done)

- [ ] **Step 1: Spec coverage check**

Walk through each section of the spec and confirm a task implements it:

| Spec section | Implemented in |
|---|---|
| §2 R1 (no prod push) | `pr_open.py` (refuses base != main, head == prod), `chunks` CLI (no prod commands) |
| §2 R2 (no auto-merge) | `pr_open.py` always emits `--draft` |
| §2 R3 (no autonomous loop) | Two separate processes; `chunks` exposes `run-impl` and `run-test` as separate user actions |
| §2 R4 (auto-close perfect-green only) | `summary-triage.v1.md` rules; `unmappable[]` field |
| §2 R5 (cleanup mandatory) | `test-recommendation.v1.md` rules; `chunk-test.js` cleanup step |
| §2 R6 (3-attempt cap) | `chunk-template-impl.js` for-loop bound + breakpoint |
| §2 R7 (scope-check) | `scope_check.py` + `scope-check` task in impl process |
| §2 R8 (SANDBOX-only) | `chunks` CLI guard, `validate-env` in both processes |
| §4 chunk definition | `chunks define` subcommand |
| §5 sub-branch model | `chunk-template-impl.js` createSubBranchTask + mergeIntoIntegrationTask |
| §6 test-rec schema | `test-recommendation.v1.md` + buildTestRecTask |
| §7 testing process | `chunk-test.js` |
| §8 stage 7 (PR + triage) | `pr_open.py` + `summary-triage.v1.md` |
| §8.5 operator UX | `chunk_status.py` + `chunks` CLI + CHUNK_PLAYBOOK.md |
| §9 file layout | All paths used match the spec |
| §11 cuts | No suggest, no cross-chunk dep check, no broad cleanup, no auto-merge — confirmed not implemented |

- [ ] **Step 2: Placeholder scan**

```bash
grep -rE "TODO|TBD|FIXME|XXX|NotImplemented" scripts/agentic .a5c/processes docs/CHUNK_PLAYBOOK.md
```

Expected: only legitimate TODO comments inside `chunks` CLI's `run-impl`/`run-test` stubs (which Phases 8/9 explicitly replace). After Phase 9 wires `run-impl`, no other matches should remain.

- [ ] **Step 3: Type/name consistency check**

Check that names are consistent across files:
- `chunkName` (camelCase) in JS — both processes, same key
- `chunk_name` (snake_case) in Python — `chunk_status.py`, `pr_open.py`, `run_log.py`
- `chunks/<name>/status.json` field names match across `chunk_status.py` and `chunk-test.js`/`chunk-template-impl.js`

```bash
grep -E "chunkName|chunk_name" scripts/agentic/*.py .a5c/processes/*.js | head -20
```

Expected: clear separation — Python uses snake_case, JS uses camelCase, no mixing within a single language.

- [ ] **Step 4: Final test sweep**

```bash
poetry run pytest tests/agentic/ -v
```

Expected: every test passes.

---

## Out of scope for this plan

- **Pilot chunk implementation** — Phase C in the spec. Once this scaffolding lands, the first real chunk (recommended: `http-foundation` covering #3, #4) is its own plan.
- **Wave-level orchestration** — running multiple chunks in parallel. The spec leaves parallelism = 1 during scaffolding/pilot.
- **Cross-chunk dependency tracking** — explicitly punted (spec §11).
- **Chunk-suggest helper** — explicitly punted (spec §13 future work).
- **Soak/test-release tooling** — entirely outside this design (R1).

---

*End of plan.*
