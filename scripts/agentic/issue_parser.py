"""Parse GitHub issue bodies into structured dicts for the chunk pipeline.

Input shape: the JSON object returned by `gh issue view <N> --json
number,title,url,labels,body`.

Output shape: a flat dict with keys consumed by chunk-template-impl.js and
the prereq checker. See spec §4 (stage 1 — chunk definition).
"""
from __future__ import annotations

import re
from typing import Any


# Header regexes accept BOTH bare and bold-markdown forms:
#   "Domain: Users"        (synthetic fixture)
#   "**Domain:** Users"    (real issues #22-#79)
# Capture is line-bounded; trailing whitespace is stripped after capture.
_DOMAIN_RE = re.compile(r"^\**Domain:?\**\s*:?\s*(.+?)\s*$", re.MULTILINE)
_PRIORITY_RE = re.compile(r"^\**Priority:?\**\s*:?\s*(.+?)\s*$", re.MULTILINE)
_EFFORT_RE = re.compile(r"^\**Effort:?\**\s*:?\s*(.+?)\s*$", re.MULTILINE)


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
    """Return (hard, soft) issue-number lists from a Prerequisites section.

    Supports two formats:

    1. Synthetic per-bullet format::

           - Hard: #3 (persistent Session)
           - Soft: #14 (logger)

    2. Real-issue subsection format with bold headers::

           **Hard blockers — must merge before this issue is ready to start:**
           - #66 — Electronic domain class bootstrap

           **Recommended (would simplify or improve this work, but not strictly blocking):**
           - #3 — Persistent requests.Session
           - #4 — Consolidate HTTP verbs into _request()

       HTML comment markers (``<!-- prereqs:auto:begin -->``) are skipped.
    """
    hard: list[int] = []
    soft: list[int] = []
    if not section_body:
        return hard, soft

    mode: str | None = None  # current subsection mode for real-issue format
    for line in section_body.splitlines():
        s = line.strip()
        if not s or s.startswith("<!--"):
            continue
        # Bold subsection headers switch the current mode for the real-issue format.
        if s.startswith("**Hard"):
            mode = "hard"
            continue
        if s.startswith("**Recommended"):
            mode = "soft"
            continue
        if not s.startswith("-"):
            continue
        # Per-bullet override (synthetic format): "- Hard: #3" / "- Soft: #14".
        low = s.lower()
        if "hard:" in low:
            bullet_mode: str | None = "hard"
        elif "soft:" in low:
            bullet_mode = "soft"
        else:
            bullet_mode = mode
        for num_str in re.findall(r"#(\d+)", s):
            num = int(num_str)
            if bullet_mode == "hard":
                hard.append(num)
            elif bullet_mode == "soft":
                soft.append(num)
    return hard, soft


def _parse_ac(section_body: str | None) -> list[str]:
    """Parse acceptance-criteria bullets.

    Accepts both checkbox bullets (``- [ ] AC-1: ...``, synthetic) and bare
    bullets (``- ...``, real issues).
    """
    if not section_body:
        return []
    out: list[str] = []
    for line in section_body.splitlines():
        s = line.strip()
        if s.startswith("- [ ]") or s.startswith("- [x]"):
            out.append(s[5:].strip())
        elif s.startswith("- "):
            out.append(s[2:].strip())
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
        missing = [
            name
            for name, match in (
                ("Domain", domain_m),
                ("Priority", priority_m),
                ("Effort", effort_m),
            )
            if not match
        ]
        raise ValueError(
            f"issue #{out['number']} missing Domain/Priority/Effort header lines"
            f" (missing: {', '.join(missing)})"
        )

    # Strip trailing markdown bold markers and surrounding whitespace.
    def _clean(value: str) -> str:
        return value.strip().rstrip("*").strip()

    out["domain"] = _clean(domain_m.group(1))
    out["priority"] = _clean(priority_m.group(1)).lower()
    # Effort may include a trailing parenthetical like "S (≤½ day)" — keep only
    # the leading alpha token (S/M/L), uppercased.
    effort_raw = _clean(effort_m.group(1))
    effort_token = re.match(r"^([A-Za-z]+)", effort_raw)
    out["effort"] = effort_token.group(1).upper() if effort_token else effort_raw.upper()

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
