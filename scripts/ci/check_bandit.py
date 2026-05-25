#!/usr/bin/env python3
"""Fail the build on any HIGH-severity bandit finding (issue #151).

Reads a bandit JSON report (default ``bandit.json``) and exits non-zero if
it contains one or more findings whose ``issue_severity`` is ``HIGH``.
Medium/Low findings are reported for visibility but never block — the
baseline at adoption is zero HIGH findings, so enforcement starts clean.

Stdlib only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    report = Path(sys.argv[1] if len(sys.argv) > 1 else "bandit.json")
    if not report.exists():
        print(f"ERROR: bandit report not found: {report}")
        return 1

    results = json.loads(report.read_text()).get("results", [])
    by_severity = Counter(r.get("issue_severity", "UNDEFINED") for r in results)
    print(f"bandit: {len(results)} finding(s) "
          f"(HIGH={by_severity['HIGH']}, MEDIUM={by_severity['MEDIUM']}, "
          f"LOW={by_severity['LOW']})")

    high = [r for r in results if r.get("issue_severity") == "HIGH"]
    for r in high:
        print(f"  HIGH {r.get('test_id')} "
              f"{r.get('filename')}:{r.get('line_number')} "
              f"-- {r.get('issue_text')}")
    if high:
        print(f"\n{len(high)} HIGH-severity finding(s). Fix them, or "
              "suppress a confirmed false positive with `# nosec <test_id>`.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
