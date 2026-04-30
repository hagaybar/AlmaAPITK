#!/usr/bin/env python3
"""
Apply a "## Prerequisites" section to the 77 architecture + coverage issues.

Idempotent: if a Prerequisites section already exists with the exact content we
want, the issue is skipped. Otherwise the existing section is replaced.

Subcommands:
  build-plan   Print the prereq plan as JSON (no edits)
  apply        Edit each issue body to insert/refresh Prerequisites
  verify       Re-fetch every issue; assert Prerequisites section is present.
               Exits 0 only if 100% pass.
  status       Print current status of all 77 issues.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Issue inventory
# ---------------------------------------------------------------------------

ARCHITECTURE_ISSUES = list(range(3, 22))   # 3..21 inclusive
COVERAGE_ISSUES = list(range(22, 80))      # 22..79 inclusive
ALL_ISSUES = ARCHITECTURE_ISSUES + COVERAGE_ISSUES   # 77 total

# Foundation tickets: hard-block their dependent siblings.
FOUNDATION = {
    22: {"domain": "Configuration", "blocks": list(range(24, 36))},   # 24..35 (issue 23 extends Admin)
    66: {"domain": "Electronic", "blocks": [67, 68, 69]},
    70: {"domain": "TaskLists", "blocks": [71, 72, 73]},
    75: {"domain": "Courses", "blocks": [76, 77]},
}

# Architecture issue titles (for human-readable reasons)
ARCH_TITLES = {
    3:  "Persistent requests.Session",
    4:  "Consolidate HTTP verbs into _request()",
    5:  "Retry with exponential backoff for 429 / 5xx",
    6:  "Configurable timeout (60s default)",
    7:  "Configurable region / host",
    8:  "Client-side rolling-window rate limiting",
    9:  "Map Alma error codes to specific exception subclasses",
    10: "Propagate tracking_id and alma_code on errors",
    11: "iter_paged() generator at the client level",
    12: "Optional Pydantic response models",
    13: "Context-manager (with-statement) support",
    14: "Replace print() with logger; remove safe_request()",
    15: "Hierarchical accessors (client.acq.invoices...)",
    16: "Tighten exception handling and cache AlmaResponse.data",
    17: "LICENSE file + PyPI metadata",
    18: "Async / concurrent bulk-call primitive",
    19: "Dedicated MARC manipulation layer",
    20: "OpenAPI-driven request/response validation",
    21: "CSV/DataFrame BatchRunner with checkpointing",
    # Foundation bootstrap tickets (referenced as hard prereqs by their siblings)
    22: "Configuration domain class bootstrap",
    66: "Electronic domain class bootstrap",
    70: "TaskLists domain class bootstrap",
    75: "Courses domain class bootstrap",
}

# Architecture-issue prereqs (hand-curated dependency graph).
ARCH_PREREQS: dict[int, dict] = {
    3:  {"hard": [], "soft": []},
    4:  {"hard": [3], "soft": []},
    5:  {"hard": [3], "soft": []},
    6:  {"hard": [], "soft": [(4, "cleaner per-call timeout once verbs are consolidated")]},
    7:  {"hard": [], "soft": []},
    8:  {"hard": [3, 4], "soft": []},
    9:  {"hard": [], "soft": []},
    10: {"hard": [9], "soft": []},
    11: {"hard": [], "soft": [(4, "cleaner via the single _request() chokepoint")]},
    12: {"hard": [], "soft": [(20, "OpenAPI specs become the schema source for generated models")]},
    13: {"hard": [3], "soft": []},
    14: {"hard": [], "soft": []},
    15: {"hard": [], "soft": []},
    16: {"hard": [], "soft": [(4, "pairs naturally with verb consolidation")]},
    17: {"hard": [], "soft": []},
    18: {"hard": [3, 5], "soft": [(8, "share RPS cap config across sync and async paths")]},
    19: {"hard": [], "soft": []},
    20: {"hard": [], "soft": []},
    21: {"hard": [18], "soft": [(10, "error rows carry tracking IDs"),
                                (14, "BatchRunner must not print")]},
}

# Universal soft prereqs that apply to *every* coverage ticket.
# These are the architecture changes that materially improve any new HTTP method.
COVERAGE_UNIVERSAL_SOFT: list[tuple[int, str]] = [
    (3,  "every new HTTP call inherits connection pooling"),
    (4,  "every new method routes through one chokepoint"),
    (5,  "every new method gets 429/5xx resilience for free"),
    (9,  "new methods raise typed Alma errors instead of generic AlmaAPIError"),
    (10, "errors carry tracking_id for support escalation"),
    (14, "no print() statements in the new methods"),
]

# Issues whose Methods-to-Add includes a list/search method — they additionally
# benefit from the iter_paged() generator (#11).
COVERAGE_LIST_HEAVY: set[int] = {
    23,   # Sets list ops (extends Admin.list_sets)
    25, 26, 27,   # Configuration: locations / code tables / mapping tables (lists)
    28,           # jobs (list_jobs, list_instances)
    29, 30, 31, 32,   # integration profiles, deposit/import profiles, license terms (lists), open hours (read)
    33, 34,       # letters/printers, reminders (list)
    36,           # users list & search
    39,           # users attachments (list)
    40, 41, 42, 43, 44, 45,   # users loans/requests/RS/purchase/fees/deposits (all list)
    48,           # bib portfolios (list)
    49, 50,       # bib + item requests (list)
    51,           # loans (list)
    52,           # booking + request options (list of options)
    53,           # collections CRUD (list)
    54,           # bib e-collections (list)
    55,           # bib reminders (list)
    56,           # authorities (list)
    58, 59, 60, 61, 63, 64, 65,   # vendors / funds / fund-tx / POL list / licenses / lookups / purchase requests
    62,           # invoice attachments (list)
    67, 68, 69,   # electronic e-collections / e-services / portfolios (lists)
    71, 72, 73,   # tasklists requested-resources / lending workflow / printouts (lists)
    74,           # RS partners (list)
    76, 77,       # courses (list)
    78,           # RS directory members (list)
    79,           # analytics paths (list)
}

# Coverage tickets that *extend an existing* domain class instead of needing a
# foundation. Used to skip applying the foundation hard-prereq.
COVERAGE_EXTENDS_EXISTING: set[int] = {
    23,   # Sets CRUD extends Admin (NOT Configuration)
    74,   # RS partners extends ResourceSharing
    78,   # RS directory members extends ResourceSharing
    79,   # Analytics paths extends Analytics
    # Bibs/Acquisitions/Users issues all extend their existing domains.
}

# Build the inverse foundation map: dependent_issue -> foundation_issue
FOUNDATION_OF: dict[int, int] = {}
for foundation_num, info in FOUNDATION.items():
    for dependent in info["blocks"]:
        FOUNDATION_OF[dependent] = foundation_num


def coverage_prereqs(issue_num: int) -> dict:
    """Compute prereq plan for a coverage issue."""
    hard: list[int] = []
    soft: list[tuple[int, str]] = list(COVERAGE_UNIVERSAL_SOFT)

    # Hard: foundation ticket if applicable
    if issue_num in FOUNDATION_OF and issue_num not in COVERAGE_EXTENDS_EXISTING:
        hard.append(FOUNDATION_OF[issue_num])

    # Conditional soft: iter_paged for list-heavy tickets
    if issue_num in COVERAGE_LIST_HEAVY:
        soft.append((11, "list/search methods should use iter_paged() instead of manual offset loops"))

    # Foundation tickets themselves: skip the universal soft list
    # (they're foundation-only; methods come in sibling tickets)
    if issue_num in FOUNDATION:
        soft = [
            (4,  "ensures the new domain class uses the consolidated _request() once landed"),
            (14, "ensures no print() in the new domain"),
            (16, "narrow except + cached AlmaResponse for the new domain's methods"),
        ]

    return {"hard": hard, "soft": soft}


def prereqs_for(issue_num: int) -> dict:
    if issue_num in ARCH_PREREQS:
        return ARCH_PREREQS[issue_num]
    return coverage_prereqs(issue_num)


# ---------------------------------------------------------------------------
# Body editing
# ---------------------------------------------------------------------------

PREREQ_MARKER_BEGIN = "<!-- prereqs:auto:begin -->"
PREREQ_MARKER_END = "<!-- prereqs:auto:end -->"


def render_prereq_section(issue_num: int) -> str:
    plan = prereqs_for(issue_num)
    lines: list[str] = []
    lines.append(PREREQ_MARKER_BEGIN)
    lines.append("## Prerequisites")

    if not plan["hard"] and not plan["soft"]:
        lines.append("")
        lines.append("_None — this issue has no upstream dependencies and does not have recommended soft prereqs at the toolkit level._")
        lines.append("")
        lines.append(PREREQ_MARKER_END)
        return "\n".join(lines)

    if plan["hard"]:
        lines.append("")
        lines.append("**Hard blockers — must merge before this issue is ready to start:**")
        for h in plan["hard"]:
            title = ARCH_TITLES.get(h, "Foundation ticket")
            lines.append(f"- #{h} — {title}")

    if plan["soft"]:
        lines.append("")
        lines.append("**Recommended (would simplify or improve this work, but not strictly blocking):**")
        for num, reason in plan["soft"]:
            title = ARCH_TITLES.get(num, "")
            lines.append(f"- #{num} — {title} ({reason})")

    lines.append("")
    lines.append(PREREQ_MARKER_END)
    return "\n".join(lines)


def splice_prereqs(body: str, new_section: str) -> str:
    """Replace any existing auto-prereq block, OR insert before Acceptance Criteria.

    Architecture issues use heading "Acceptance criteria"; coverage issues use
    same heading. If neither exists, append.
    """
    # Replace existing auto block if present
    pattern = re.compile(
        re.escape(PREREQ_MARKER_BEGIN) + r".*?" + re.escape(PREREQ_MARKER_END),
        re.DOTALL,
    )
    if pattern.search(body):
        return pattern.sub(new_section, body)

    # Also strip any pre-existing manual "## Prerequisites" or "## Depends on" section
    # so we don't end up with duplicates.
    body = re.sub(
        r"\n## (Prerequisites|Depends on)\s*\n.*?(?=\n## |\Z)",
        "\n",
        body,
        flags=re.DOTALL,
    )

    # Insert before "## Acceptance criteria"
    if "## Acceptance criteria" in body:
        return body.replace(
            "## Acceptance criteria",
            new_section + "\n\n## Acceptance criteria",
            1,
        )

    # Fallback: append at end
    return body.rstrip() + "\n\n" + new_section + "\n"


# ---------------------------------------------------------------------------
# gh CLI helpers
# ---------------------------------------------------------------------------


def fetch_body(issue_num: int) -> Optional[str]:
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--json", "body", "--jq", ".body"],
            check=True, capture_output=True, text=True,
        )
        return result.stdout.rstrip("\n")
    except subprocess.CalledProcessError as e:
        print(f"  ERROR fetching #{issue_num}: {e.stderr.strip()}", file=sys.stderr)
        return None


def edit_body(issue_num: int, new_body: str) -> bool:
    try:
        subprocess.run(
            ["gh", "issue", "edit", str(issue_num), "--body", new_body],
            check=True, capture_output=True, text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR editing #{issue_num}: {e.stderr.strip()}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_build_plan(_args) -> int:
    plan = {n: prereqs_for(n) for n in ALL_ISSUES}
    print(json.dumps(plan, indent=2))
    return 0


def cmd_apply(args) -> int:
    targets = [int(s) for s in args.only.split(",")] if args.only else ALL_ISSUES
    updated = 0
    skipped_unchanged = 0
    failed: list[int] = []

    for n in targets:
        body = fetch_body(n)
        if body is None:
            failed.append(n)
            continue
        new_section = render_prereq_section(n)
        new_body = splice_prereqs(body, new_section)
        if new_body == body:
            print(f"[{n}] unchanged (already current)")
            skipped_unchanged += 1
            continue
        if args.dry_run:
            print(f"[{n}] WOULD UPDATE")
            updated += 1
            continue
        if edit_body(n, new_body):
            print(f"[{n}] updated")
            updated += 1
        else:
            failed.append(n)

    print()
    print(f"Updated:           {updated}")
    print(f"Already current:   {skipped_unchanged}")
    print(f"Failed:            {len(failed)}  {failed if failed else ''}")
    return 0 if not failed else 1


def cmd_verify(args) -> int:
    """100% quality gate: every issue must have the auto-prereq block."""
    targets = ALL_ISSUES
    missing: list[int] = []
    malformed: list[int] = []
    ok = 0

    for n in targets:
        body = fetch_body(n)
        if body is None:
            missing.append(n)
            continue
        if PREREQ_MARKER_BEGIN not in body or PREREQ_MARKER_END not in body:
            missing.append(n)
            continue
        # Confirm the section contains "## Prerequisites" between markers
        m = re.search(
            re.escape(PREREQ_MARKER_BEGIN) + r"(.*?)" + re.escape(PREREQ_MARKER_END),
            body, re.DOTALL,
        )
        if not m or "## Prerequisites" not in m.group(1):
            malformed.append(n)
            continue
        ok += 1

    total = len(targets)
    print(f"Verified:    {ok}/{total}")
    print(f"Missing:     {missing}")
    print(f"Malformed:   {malformed}")
    if ok == total:
        print("PASS — 100% quality gate met.")
        return 0
    print("FAIL — quality gate not met.")
    return 1


def cmd_status(_args) -> int:
    for n in ALL_ISSUES:
        body = fetch_body(n)
        if body is None:
            status = "ERR"
        elif PREREQ_MARKER_BEGIN in body and PREREQ_MARKER_END in body:
            status = "ok"
        else:
            status = "MISSING"
        print(f"#{n:3d}  {status}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build-plan", help="Print the prereq plan as JSON")

    apply_p = sub.add_parser("apply", help="Edit each issue body")
    apply_p.add_argument("--dry-run", action="store_true")
    apply_p.add_argument("--only", help="Comma-separated issue numbers")

    sub.add_parser("verify", help="Verify 100% quality gate")
    sub.add_parser("status", help="Print current status of all 77 issues")

    args = parser.parse_args()

    if args.cmd == "build-plan":
        return cmd_build_plan(args)
    if args.cmd == "apply":
        return cmd_apply(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    if args.cmd == "status":
        return cmd_status(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
