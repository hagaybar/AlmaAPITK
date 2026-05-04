"""Re-run every chunk's SANDBOX smoke tests against current HEAD.

Discovers `chunks/<name>/sandbox-tests/test_*.py` for every chunk in the repo
and runs them with pytest. Each test file is responsible for loading its
fixtures (from `chunks/<name>/test-data.json` or env vars) and skipping
cleanly when the operator hasn't supplied them.

Why this exists: each chunk's smoke tests are written ONCE, when the chunk
lands. Without re-running them periodically, drift creeps in: chunk #N's
change can break chunk #M's behaviour without anyone noticing until prod.
This script lets the operator run all retained smoke tests in one command,
typically before cutting a test release.

Usage::

    python -m scripts.agentic.regression_smoke
    python -m scripts.agentic.regression_smoke --chunks-dir /path/to/chunks
    python -m scripts.agentic.regression_smoke --json

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


def discover_chunks(chunks_dir: Path) -> list[Path]:
    """Return chunk dirs that have a sandbox-tests/ subdir, sorted by name."""
    if not chunks_dir.exists():
        return []
    out: list[Path] = []
    for child in sorted(chunks_dir.iterdir()):
        if not child.is_dir():
            continue
        st = child / "sandbox-tests"
        if st.exists() and any(st.glob("test_*.py")):
            out.append(child)
    return out


def run_chunk_smoke(chunk_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Run pytest for one chunk's sandbox-tests/. Returns a result dict."""
    sandbox_tests = chunk_dir / "sandbox-tests"
    cmd = [
        "poetry", "run", "pytest", str(sandbox_tests),
        "-v", "--tb=short", "--no-header", "-q",
    ]
    result = subprocess.run(
        cmd, cwd=repo_root, capture_output=True, text=True, timeout=300,
    )
    return {
        "chunk": chunk_dir.name,
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
        "--chunks-dir", default="chunks",
        help="Directory under repo root containing chunk subdirs (default: chunks)",
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
    chunks_dir = (repo_root / args.chunks_dir).resolve()

    chunks = discover_chunks(chunks_dir)
    if not chunks:
        msg = f"no chunks with sandbox-tests/ found under {chunks_dir}"
        if args.json:
            print(json.dumps({"chunks": [], "summary": {"total": 0}}, indent=2))
        else:
            print(msg)
        return 0

    results = [run_chunk_smoke(c, repo_root) for c in chunks]

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
        print(json.dumps({"chunks": results, "summary": summary}, indent=2))
    else:
        for r in results:
            if r["exitCode"] == 0:
                tag = "PASS"
            elif r["exitCode"] == 5:
                tag = "SKIP (no fixtures — populate test-data.json or set env vars)"
            else:
                tag = f"FAIL (exit {r['exitCode']})"
            print(f"[{tag}] {r['chunk']}")
            if r["exitCode"] not in (0, 5):
                print(f"  stdout (tail):\n    " + r["stdout_tail"].replace("\n", "\n    "))
                if r["stderr_tail"].strip():
                    print(f"  stderr (tail):\n    " + r["stderr_tail"].replace("\n", "\n    "))
        print(f"\nsummary: {passed}/{summary['total']} passed, {skipped} skipped, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
