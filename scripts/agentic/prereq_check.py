"""Verify hard prereqs at the code level, not the issue-state level.

Per handbook §13: a prereq issue can be closed in name but its functionality
may not be wired in. This helper greps the working tree for the symbol each
prereq is supposed to introduce.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _symbol_present(symbol: str, search_root: Path, repo_root: Path) -> bool:
    """Word-boundary fixed-string search in tracked .py files under search_root."""
    if not search_root.exists():
        return False

    # Get tracked .py files under search_root (deterministic, .gitignore-aware)
    rel = search_root.resolve().relative_to(repo_root.resolve())
    ls = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--", f"{rel}/*.py" if str(rel) != "." else "*.py"],
        capture_output=True, text=True,
    )
    if ls.returncode != 0:
        # Not a git repo or git failed — fall back to filesystem walk
        files = [str(p) for p in search_root.rglob("*.py")]
    else:
        files = [str(repo_root / line) for line in ls.stdout.splitlines() if line.strip()]

    if not files:
        return False

    # Try rg first (fixed-string + word boundary), then grep
    try:
        result = subprocess.run(
            ["rg", "-lwF", symbol, *files],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return bool(result.stdout.strip())
        if result.returncode == 1:
            return False
        # rg returncode > 1 → real error; capture and try grep
        rg_err = result.stderr.strip()
    except FileNotFoundError:
        rg_err = "rg not installed"

    result = subprocess.run(
        ["grep", "-lwF", symbol, *files],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return bool(result.stdout.strip())
    if result.returncode == 1:
        return False
    # grep also failed
    raise RuntimeError(
        f"prereq scan for symbol {symbol!r} failed: rg: {rg_err}; grep: {result.stderr.strip()}"
    )


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
        if not _symbol_present(p["symbol"], where, repo_root):
            missing.append({
                "issue": p["issue"],
                "symbol": p["symbol"],
                "where": p.get("where", "."),
                "why": f"symbol {p['symbol']!r} not found in tracked .py files under {p.get('where', '.')!r}",
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
