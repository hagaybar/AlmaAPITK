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
