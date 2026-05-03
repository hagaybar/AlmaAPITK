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
