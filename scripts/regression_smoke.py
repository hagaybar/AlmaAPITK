"""Re-run every SANDBOX smoke suite against current HEAD.

Discovers `tests/sandbox/<suite>/test_*.py` for every suite in the repo
and runs each suite with pytest (one pytest process per suite, so each
suite's conftest stays isolated). Each test file is responsible for loading
its fixtures (from the gitignored `tests/sandbox/<suite>/test-data.json` or
env vars) and skipping cleanly when the operator hasn't supplied them.

These tests hit the live Alma SANDBOX API. They are NOT a release gate.

Why this exists: each suite's smoke tests are written ONCE, when the feature
lands. Without re-running them periodically, drift creeps in: change #N
can break feature #M's behaviour without anyone noticing until prod.
This script lets the operator run all retained smoke tests in one command,
typically before cutting a test release.

Usage::

    poetry run python -m scripts.regression_smoke
    poetry run python -m scripts.regression_smoke --sandbox-dir /path/to/tests/sandbox
    poetry run python -m scripts.regression_smoke --json

R8: refuses to run if ALMA_PROD_API_KEY is set in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def discover_suites(sandbox_dir: Path) -> list[Path]:
    """Return suite dirs under sandbox_dir that contain test_*.py, sorted by name."""
    if not sandbox_dir.exists():
        return []
    return [
        child for child in sorted(sandbox_dir.iterdir())
        if child.is_dir() and any(child.glob("test_*.py"))
    ]


def run_suite(suite_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Run pytest for one SANDBOX suite. Returns a result dict."""
    cmd = [
        "poetry", "run", "pytest", str(suite_dir),
        "-v", "--tb=short", "--no-header", "-q",
    ]
    result = subprocess.run(
        cmd, cwd=repo_root, capture_output=True, text=True, timeout=300,
    )
    return {
        "suite": suite_dir.name,
        "exitCode": result.returncode,
        "stdout_tail": "\n".join(result.stdout.splitlines()[-10:]),
        "stderr_tail": "\n".join(result.stderr.splitlines()[-5:]),
    }


def main() -> int:
    if os.environ.get("ALMA_PROD_API_KEY"):
        sys.stderr.write(
            "R8: ALMA_PROD_API_KEY must not be set; refusing to run.\n"
        )
        return 2

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--sandbox-dir", default="tests/sandbox",
        help="Directory under repo root containing suite subdirs (default: tests/sandbox)",
    )
    parser.add_argument(
        "--repo-root", default=".",
        help="Repo root (default: current working directory)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON summary on stdout",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    sandbox_dir = (repo_root / args.sandbox_dir).resolve()

    suites = discover_suites(sandbox_dir)
    if not suites:
        msg = f"no SANDBOX suites found under {sandbox_dir}"
        if args.json:
            print(json.dumps({"suites": [], "summary": {"total": 0}}, indent=2))
        else:
            print(msg)
        return 0

    results = [run_suite(s, repo_root) for s in suites]

    passed = sum(1 for r in results if r["exitCode"] == 0)
    skipped_or_failed = len(results) - passed
    summary = {"total": len(results), "passed": passed, "other": skipped_or_failed}

    # Pytest exit 5 = "no tests collected" — typically all tests skipped because
    # the operator didn't populate test-data.json or set env-var fixtures. Treat
    # as a separate "SKIP" state, not a hard fail.
    skipped = sum(1 for r in results if r["exitCode"] == 5)
    failed = sum(1 for r in results if r["exitCode"] not in (0, 5))
    summary = {"total": len(results), "passed": passed, "skipped": skipped, "failed": failed}

    if args.json:
        print(json.dumps({"suites": results, "summary": summary}, indent=2))
    else:
        for r in results:
            if r["exitCode"] == 0:
                tag = "PASS"
            elif r["exitCode"] == 5:
                tag = "SKIP (no fixtures — populate test-data.json or set env vars)"
            else:
                tag = f"FAIL (exit {r['exitCode']})"
            print(f"[{tag}] {r['suite']}")
            if r["exitCode"] not in (0, 5):
                print(f"  stdout (tail):\n    " + r["stdout_tail"].replace("\n", "\n    "))
                if r["stderr_tail"].strip():
                    print(f"  stderr (tail):\n    " + r["stderr_tail"].replace("\n", "\n    "))
        print(f"\nsummary: {passed}/{summary['total']} passed, {skipped} skipped, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
