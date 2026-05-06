"""Parse GitHub issue bodies into structured dicts for the chunk pipeline.

Input shape: the JSON object returned by `gh issue view <N> --json
number,title,url,labels,body`.

Output shape: a flat dict with keys consumed by chunk-template-impl.js and
the prereq checker. See spec §4 (stage 1 — chunk definition).
"""
from __future__ import annotations

import re
from typing import Any


# Header regexes accept BOTH bare and bold-markdown forms, AND aliased headers
# used by different issue templates in this repo:
#   "Domain: Users"           (synthetic fixture)
#   "**Domain:** Users"       (api-coverage issues #22-#79)
#   (Domain absent)            (architecture issues #1-#21 — cross-cutting)
#   "**Priority:** High"      (api-coverage issues)
#   "**Benefit:** High"       (architecture issues — alias for Priority)
#   "**Effort:** S"           (api-coverage issues)
#   "**Complexity:** S"       (architecture issues — alias for Effort)
# Capture is line-bounded; trailing whitespace is stripped after capture.
_DOMAIN_RE = re.compile(r"^\**Domain:?\**\s*:?\s*(.+?)\s*$", re.MULTILINE)
_PRIORITY_RE = re.compile(
    r"^\**(?:Priority|Benefit):?\**\s*:?\s*(.+?)\s*$", re.MULTILINE
)
_EFFORT_RE = re.compile(
    r"^\**(?:Effort|Complexity):?\**\s*:?\s*(.+?)\s*$", re.MULTILINE
)


def _section(body: str, header: str) -> str | None:
    """Return the markdown body of `## <header>` up to the next `## ` or EOF."""
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


_PATH_AT_START_RE = re.compile(r"^`([^`]+)`")
_ANNOTATION_RE = re.compile(r"^\s*\([^)]*\)")
_SEP_RE = re.compile(r"^\s*(?:,|→|and)\s+")
# Trailing " (annotation)" embedded INSIDE the backticks. Requires a leading
# whitespace before the open paren so a fully-parenthesized token like
# "(no endpoints — foundation only)" is preserved as-is.
_INNER_ANNOTATION_RE = re.compile(r"\s+\([^)]*\)\s*$")


def _bullet_lines(section_body: str | None) -> list[str]:
    """Extract list bullets, stripping markdown backticks and trailing parentheticals.

    Handles all of:
        - path                                  -> [path]
        - `path`                                -> [path]
        - `path` (comment about it)             -> [path]
        - `path (comment inside backticks)`     -> [path]
        - `path1`, `path2`                      -> [path1, path2]
        - `path1` (NEW), `path2` (NEW)          -> [path1, path2]
        - `path1` → `path2`                     -> [path1, path2]
        - `path1` and `path2`                   -> [path1, path2]
        - `path` — description with `code`      -> [path]
        - GET /api/v1/x                         -> [GET /api/v1/x]

    Multi-path support: when a bullet starts with a backtick-quoted token,
    consecutive backtick-quoted tokens separated by ``, ``, ``→`` (rename
    arrow), or ``and`` are all captured as paths. The scan stops at the first
    non-separator gap (e.g. an em-dash description), so backticked tokens in
    the description prose are not captured.
    """
    if not section_body:
        return []
    out: list[str] = []
    for line in section_body.splitlines():
        if not (line.startswith("- ") or line.startswith("* ")):
            continue
        text = line[2:].strip()
        if text.startswith("`"):
            # Walk leading backtick-quoted tokens separated by recognized
            # separators. Stop at the first gap that isn't a separator-then-
            # backtick — that's where description prose begins.
            while True:
                m = _PATH_AT_START_RE.match(text)
                if not m:
                    break
                path = _INNER_ANNOTATION_RE.sub("", m.group(1))
                if path:
                    out.append(path)
                text = text[m.end():]
                # Optional " (annotation)" describing the just-extracted path.
                ann_m = _ANNOTATION_RE.match(text)
                if ann_m:
                    text = text[ann_m.end():]
                # Optional separator, but only if followed by another path.
                sep_m = _SEP_RE.match(text)
                if sep_m and text[sep_m.end():sep_m.end() + 1] == "`":
                    text = text[sep_m.end():]
                    continue
                break
            continue
        # Bullet without leading backtick — strip trailing " (annotation)".
        paren_idx = text.find(" (")
        if paren_idx > 0:
            text = text[:paren_idx]
        text = text.strip()
        if text:
            out.append(text)
    return out


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


def infer_swagger_domains(issue: dict[str, Any]) -> list[str]:
    """Infer the Alma swagger domain(s) an issue's implementation would touch.

    Used by ``.a5c/processes/chunk-template-impl.js`` to decide which
    ``fetch_domain_codes.py <domain>`` invocations to run before the
    ``implement`` agent fires (issue #90).

    Inputs are matched against ``DOMAIN_ALIASES`` in the canonical map,
    which lives in ``scripts/error_codes/fetch_domain_codes.py`` to keep
    the swagger-domain knowledge in one place. Heuristics are deliberately
    conservative:

    1. ``files_to_touch`` paths under ``src/almaapitk/domains/<file>.py``
       — strongest signal; the file basename is the issue's primary domain.
    2. The issue's ``domain`` header value (``Users``, ``Acquisitions``, ...).
    3. ``endpoints`` URL prefixes — falls back to e.g. ``/almaws/v1/users``
       → ``users`` when the file list is empty (issue #1-#21 architecture
       tickets are cross-cutting and have no Files-to-touch).

    Returns a deduplicated, sorted list. Empty list = no swagger domain
    can be confidently inferred (the chunk-impl hook will skip the fetch
    step in that case rather than guess and pull noise).
    """
    # Lazy import to keep issue_parser usable without scripts.error_codes
    # on PYTHONPATH (e.g. older installs). The aliases table is small and
    # version-stable; the import is cheap.
    try:
        from scripts.error_codes.fetch_domain_codes import DOMAIN_ALIASES
    except Exception:  # pragma: no cover — defensive only
        DOMAIN_ALIASES = {}

    seen: set[str] = set()

    # 1. Files to touch — strongest signal.
    for path in issue.get("files_to_touch") or []:
        # Match src/almaapitk/domains/<basename>.py
        m = re.search(r"src/almaapitk/domains/([a-zA-Z_]+)\.py", path)
        if m:
            key = m.group(1).lower()
            mapped = DOMAIN_ALIASES.get(key)
            if mapped:
                seen.add(mapped)

    # 2. Issue domain header — hits the alias table directly when set.
    domain_header = (issue.get("domain") or "").strip().lower()
    if domain_header and domain_header != "architecture":
        # Strip trailing s for plurals not already in aliases ("Users" → "users")
        for variant in (domain_header, domain_header.rstrip("s")):
            mapped = DOMAIN_ALIASES.get(variant)
            if mapped:
                seen.add(mapped)
                break

    # 3. Endpoint prefixes — e.g. ``/almaws/v1/users/...`` → ``users``.
    for ep in issue.get("endpoints") or []:
        # ep is like "GET /almaws/v1/users/{user_id}". Find the prefix segment
        # AFTER ``/almaws/v1/``.
        m = re.search(r"/almaws/v\d+/([a-zA-Z_-]+)", ep)
        if m:
            key = m.group(1).lower()
            mapped = DOMAIN_ALIASES.get(key)
            if mapped:
                seen.add(mapped)

    return sorted(seen)


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
    # Domain is OPTIONAL — architecture issues (#1-#21) are cross-cutting and
    # carry no Domain header. Priority (or its alias Benefit) and Effort
    # (or its alias Complexity) are required.
    if not (priority_m and effort_m):
        missing = [
            name
            for name, match in (
                ("Priority/Benefit", priority_m),
                ("Effort/Complexity", effort_m),
            )
            if not match
        ]
        raise ValueError(
            f"issue #{out['number']} missing Priority/Benefit and/or Effort/Complexity"
            f" header lines (missing: {', '.join(missing)})"
        )

    # Strip trailing markdown bold markers and surrounding whitespace.
    def _clean(value: str) -> str:
        return value.strip().rstrip("*").strip()

    out["domain"] = _clean(domain_m.group(1)) if domain_m else "Architecture"
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
