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
