"""Render docs/CHUNK_BACKLOG.md from docs/chunks-backlog.yaml + GitHub state.

Issue #93: GitHub is the source of truth for issue/PR state. The YAML holds the
operator-maintained chunk plan (name, issues, phase, prereqs, notes); status is
*never* stored — it's derived per render.

The renderer is structured around two seams that tests inject fixtures into:

- ``load_backlog`` — reads & parses the YAML.
- ``GHFetcher`` — protocol that returns ``{issue_number: state}`` and a list of
  merged-PR titles. The default implementation shells out to ``gh``; tests pass
  a stub.

This module never makes live HTTP calls during unit tests.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import string
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Minimal YAML loader for our controlled schema
# ---------------------------------------------------------------------------
#
# PyYAML is not a project dependency. The chunks-backlog.yaml schema is small
# and entirely under our control: only mappings, sequences (block + flow for
# integer lists), scalar strings, integers, the empty literal ``""``, and
# multi-line block scalars introduced with ``|``. This loader handles exactly
# that subset and rejects anything outside it. A general-purpose YAML library
# is overkill for the shape we control.


class YAMLParseError(ValueError):
    """Raised when the controlled-schema loader sees something it cannot parse."""


def _strip_comment(line: str) -> str:
    """Strip a trailing ``#`` comment from a line, ignoring ``#`` inside quotes."""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i].rstrip()
    return line.rstrip()


def _coerce_scalar(raw: str) -> Any:
    """Coerce a YAML scalar to a Python value (int, str, or empty string)."""
    s = raw.strip()
    if s == "" or s == '""' or s == "''":
        return ""
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        return s[1:-1]
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1]
    # Integer?
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _parse_flow_list(raw: str) -> list[Any]:
    """Parse a flow-style list ``[a, b, c]`` of scalars."""
    inner = raw.strip()
    if not (inner.startswith("[") and inner.endswith("]")):
        raise YAMLParseError(f"expected flow list, got: {raw!r}")
    inner = inner[1:-1].strip()
    if not inner:
        return []
    parts = [p.strip() for p in inner.split(",")]
    return [_coerce_scalar(p) for p in parts]


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def loads_yaml(text: str) -> dict[str, Any]:
    """Parse YAML text limited to the chunks-backlog.yaml schema.

    Args:
        text: Raw YAML text.

    Returns:
        A nested ``dict`` / ``list`` / scalar structure.

    Raises:
        YAMLParseError: when the input strays outside the supported subset.
    """
    # Preserve all lines verbatim. We deliberately do NOT pre-strip
    # standalone ``#`` comment lines because block scalars (introduced by
    # ``|``) often start their content with ``#`` (e.g., ``#3, #4``), and
    # an early strip would silently delete those rows. Inline ``#`` after
    # a scalar value is handled by ``_strip_comment`` during scalar parsing.
    lines = list(text.splitlines())

    # Drop trailing empty lines.
    while lines and lines[-1].strip() == "":
        lines.pop()

    pos = [0]

    def peek() -> str | None:
        if pos[0] >= len(lines):
            return None
        return lines[pos[0]]

    def advance() -> None:
        pos[0] += 1

    def parse_block_scalar(indent_min: int) -> str:
        """Parse a ``|`` block scalar starting on the next line."""
        collected: list[str] = []
        block_indent: int | None = None
        while pos[0] < len(lines):
            ln = lines[pos[0]]
            if ln.strip() == "":
                # Blank line preserved as empty string within scalar.
                collected.append("")
                advance()
                continue
            ind = _indent_of(ln)
            if ind <= indent_min:
                break
            if block_indent is None:
                block_indent = ind
            collected.append(ln[block_indent:])
            advance()
        # Trim trailing blank lines (clip mode default)
        while collected and collected[-1] == "":
            collected.pop()
        return "\n".join(collected) + "\n"

    def parse_value(indent: int, raw_value: str) -> Any:
        v = raw_value.strip()
        if v == "|":
            return parse_block_scalar(indent)
        if v.startswith("["):
            return _parse_flow_list(v)
        if v == "":
            # Nested block: either a mapping or a list at indent > current.
            nxt = peek()
            if nxt is None:
                return ""
            ind_nxt = _indent_of(nxt)
            if ind_nxt <= indent:
                return ""
            stripped = nxt.lstrip()
            if stripped.startswith("- "):
                return parse_list(ind_nxt)
            return parse_mapping(ind_nxt)
        return _coerce_scalar(v)

    def parse_mapping(indent: int) -> dict[str, Any]:
        out: dict[str, Any] = {}
        while pos[0] < len(lines):
            ln = lines[pos[0]]
            if ln.strip() == "":
                advance()
                continue
            ind = _indent_of(ln)
            if ind < indent:
                break
            if ind > indent:
                raise YAMLParseError(
                    f"unexpected indent {ind} (expected {indent}) at line "
                    f"{pos[0] + 1}: {ln!r}"
                )
            stripped = ln.lstrip()
            if stripped.startswith("- "):
                # End of mapping; caller will pick up.
                break
            # key: value
            colon = stripped.find(":")
            if colon < 0:
                raise YAMLParseError(
                    f"expected 'key:' at line {pos[0] + 1}: {ln!r}"
                )
            key = stripped[:colon].strip()
            after = stripped[colon + 1:]
            after_clean = _strip_comment(after)
            advance()
            out[key] = parse_value(indent, after_clean)
        return out

    def parse_list(indent: int) -> list[Any]:
        out: list[Any] = []
        while pos[0] < len(lines):
            ln = lines[pos[0]]
            if ln.strip() == "":
                advance()
                continue
            ind = _indent_of(ln)
            if ind < indent:
                break
            if ind > indent:
                raise YAMLParseError(
                    f"unexpected indent {ind} at line {pos[0] + 1}: {ln!r}"
                )
            stripped = ln.lstrip()
            if not stripped.startswith("- "):
                break
            after_dash = stripped[2:]
            # Replace the line so the "- " is consumed and the rest looks like
            # a mapping or scalar starting at indent + 2.
            inner_indent = indent + 2
            lines[pos[0]] = " " * inner_indent + after_dash
            # If the after-dash is "key: value", treat as a mapping at inner_indent.
            after_clean = _strip_comment(after_dash)
            if ":" in after_clean and not after_clean.lstrip().startswith("["):
                out.append(parse_mapping(inner_indent))
            else:
                # Scalar list item.
                advance()
                out.append(_coerce_scalar(after_clean))
        return out

    # Top level.
    return parse_mapping(0)


# ---------------------------------------------------------------------------
# Backlog loading
# ---------------------------------------------------------------------------


def load_backlog(yaml_path: Path) -> dict[str, Any]:
    """Load and validate ``docs/chunks-backlog.yaml``.

    Args:
        yaml_path: Path to the YAML file.

    Returns:
        The parsed backlog as nested dict/list. Top-level keys include
        ``schema_version``, ``phases``, ``blocked``.

    Raises:
        YAMLParseError: if the YAML cannot be parsed.
        ValueError: if the schema version is unsupported.
    """
    text = yaml_path.read_text()
    data = loads_yaml(text)
    if data.get("schema_version") != 1:
        raise ValueError(
            f"unsupported schema_version {data.get('schema_version')!r}; "
            f"expected 1"
        )
    return data


# ---------------------------------------------------------------------------
# GitHub state fetcher
# ---------------------------------------------------------------------------


class GHFetcher:
    """Fetch GitHub state via ``gh`` CLI.

    Tests inject a fake by passing a different fetcher into ``render_backlog``.
    The default implementation shells out via ``subprocess.run`` and parses JSON.
    Constructing a real one is cheap; calling ``fetch_*`` is what costs API budget.

    Args:
        runner: Optional override for ``subprocess.run`` (used in tests).
    """

    def __init__(
        self,
        runner: Callable[..., subprocess.CompletedProcess] | None = None,
    ) -> None:
        self._runner = runner or subprocess.run

    def _run(self, cmd: list[str]) -> str:
        result = self._runner(
            cmd, capture_output=True, text=True, check=True
        )
        return result.stdout

    def fetch_issues(self, numbers: Iterable[int]) -> dict[int, str]:
        """Return ``{issue_number: state}`` for the requested issues.

        Uses a single bulk ``gh issue list`` call (per design notes) rather
        than per-issue ``gh issue view``. ``state`` is one of ``OPEN``,
        ``CLOSED``, or ``UNKNOWN`` for issues not returned by the bulk query.

        Args:
            numbers: Issue numbers to look up.

        Returns:
            Dict mapping issue number to its GitHub state.
        """
        wanted = sorted(set(int(n) for n in numbers))
        if not wanted:
            return {}
        # gh issue list --state all --limit N --json number,state
        # We pull a batch big enough to cover the backlog and join client-side.
        raw = self._run([
            "gh", "issue", "list",
            "--state", "all",
            "--limit", "500",
            "--json", "number,state",
        ])
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"gh issue list returned non-JSON output: {raw[:200]!r}"
            ) from exc
        by_number = {int(item["number"]): item["state"] for item in payload}
        return {n: by_number.get(n, "UNKNOWN") for n in wanted}

    def fetch_merged_prs(self) -> list[dict[str, Any]]:
        """Return merged PRs as a list of ``{number, title, mergedAt}`` dicts.

        Returns:
            List of merged-PR records; empty if none.
        """
        raw = self._run([
            "gh", "pr", "list",
            "--state", "merged",
            "--limit", "500",
            "--json", "number,title,mergedAt,url",
        ])
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"gh pr list returned non-JSON output: {raw[:200]!r}"
            ) from exc


# Type alias for the fetcher protocol used by render_backlog.
GHFetcherLike = Any  # any object with fetch_issues + fetch_merged_prs methods.


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


def derive_chunk_status(
    chunk: dict[str, Any],
    issue_states: dict[int, str],
    merged_prs: list[dict[str, Any]],
    chunk_status_dir: Path | None,
) -> str:
    """Derive a single chunk's status label from joined GitHub data.

    Per design §3.2:

    - ``merged`` — every issue closed AND a chunk PR is merged.
    - ``partial`` — some issues closed, others open.
    - ``in-flight`` — ``chunks/<name>/status.json`` exists, non-terminal stage.
    - ``planned`` — none of the above.

    Args:
        chunk: Single chunk dict from the YAML (has ``name``, ``issues``).
        issue_states: GitHub state per issue number.
        merged_prs: List of merged-PR records from ``gh pr list``.
        chunk_status_dir: Path to ``chunks/<name>/`` if it exists; ``None``
            if the chunk has no on-disk status.

    Returns:
        One of ``"merged"``, ``"partial"``, ``"in-flight"``, ``"planned"``.
    """
    name = chunk["name"]
    issues = chunk.get("issues", []) or []
    states = [issue_states.get(int(n), "UNKNOWN") for n in issues]
    all_closed = bool(states) and all(s == "CLOSED" for s in states)
    any_closed = any(s == "CLOSED" for s in states)

    pr_for_chunk = _find_chunk_pr(name, merged_prs)
    if all_closed and pr_for_chunk is not None:
        return "merged"

    # On-disk in-flight check — only honored when we don't already have a
    # merged signal. Reading status.json is best-effort.
    if chunk_status_dir is not None:
        status_file = chunk_status_dir / "status.json"
        if status_file.exists():
            try:
                status = json.loads(status_file.read_text())
                stage = status.get("stage", "")
                if stage and stage not in {"merged", "aborted"}:
                    return "in-flight"
            except (OSError, json.JSONDecodeError):
                logger.warning(
                    "could not read status.json for chunk %s; treating as planned",
                    name,
                )

    if all_closed:
        # Issues all closed but no merged PR found — closed off-pipeline.
        return "merged"
    if any_closed:
        return "partial"
    return "planned"


def _find_chunk_pr(
    chunk_name: str,
    merged_prs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find a merged PR whose title references the chunk name."""
    needles = (
        f"chunk: {chunk_name}",
        f"chunk:{chunk_name}",
        f"chunk/{chunk_name}",
        chunk_name,
    )
    for pr in merged_prs:
        title = (pr.get("title") or "").lower()
        for needle in needles:
            if needle.lower() in title:
                return pr
    return None


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


_RISK_COL_HEADER = "Risk"

# Status emoji prefixes — kept ASCII-friendly for diff readability.
_STATUS_LABELS = {
    "merged": "✅ merged",
    "partial": "⚠ partial",
    "in-flight": "▶ in-flight",
    "planned": "· planned",
}


def _format_issues(issues: list[int]) -> str:
    return ", ".join(f"#{n}" for n in issues) if issues else "—"


def _format_prereqs(prereqs: list[int]) -> str:
    if not prereqs:
        return "none"
    return ", ".join(f"#{n}" for n in prereqs)


def _format_audit(audit: Any) -> str:
    if not audit or audit == "clean":
        return "clean"
    return str(audit)


def _format_notes(notes: str | None) -> str:
    if not notes:
        return ""
    # Collapse newlines to a single line for the table cell.
    return " ".join(line.strip() for line in notes.strip().splitlines() if line.strip())


def _render_phase(phase: dict[str, Any], chunk_lines: list[str]) -> list[str]:
    out: list[str] = []
    out.append(f"## Phase {phase['id']} — {phase['title']}")
    out.append("")
    desc = phase.get("description") or ""
    if desc.strip():
        out.append(desc.rstrip())
        out.append("")
    out.append(
        "| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |"
    )
    out.append(
        "|---|---|---|---|---|---|---|---|"
    )
    out.extend(chunk_lines)
    out.append("")
    return out


def render_markdown(
    backlog: dict[str, Any],
    issue_states: dict[int, str],
    merged_prs: list[dict[str, Any]],
    chunks_root: Path | None = None,
    *,
    template_path: Path | None = None,
    timestamp: str | None = None,
) -> str:
    """Render the backlog into Markdown.

    Args:
        backlog: Parsed YAML structure from :func:`load_backlog`.
        issue_states: ``{issue_number: state}`` from GitHub.
        merged_prs: Merged-PR records from GitHub.
        chunks_root: ``chunks/`` directory; used to detect in-flight chunks.
        template_path: Path to the ``.j2`` template (string-template;
            ``$body`` and ``$timestamp`` are substituted).
        timestamp: Override timestamp line for tests; otherwise UTC ``now``.

    Returns:
        The full Markdown document as a string.
    """
    body_lines: list[str] = []
    counter = 1
    for phase in backlog.get("phases", []) or []:
        chunk_lines: list[str] = []
        for chunk in phase.get("chunks", []) or []:
            chunk_dir = chunks_root / chunk["name"] if chunks_root else None
            status = derive_chunk_status(chunk, issue_states, merged_prs, chunk_dir)
            label = _STATUS_LABELS.get(status, status)
            chunk_lines.append(
                f"| {counter} "
                f"| {label} "
                f"| `{chunk['name']}` "
                f"| {_format_issues(chunk.get('issues') or [])} "
                f"| {chunk.get('risk', '')} "
                f"| {_format_prereqs(chunk.get('prereqs') or [])} "
                f"| {_format_audit(chunk.get('audit'))} "
                f"| {_format_notes(chunk.get('notes'))} |"
            )
            counter += 1
        body_lines.extend(_render_phase(phase, chunk_lines))

    # Blocked section
    blocked = backlog.get("blocked", []) or []
    if blocked:
        body_lines.append("## Blocked — resolve before chunking")
        body_lines.append("")
        body_lines.append("| Issue | Title | Blocker |")
        body_lines.append("|---|---|---|")
        for entry in blocked:
            reason = _format_notes(entry.get("reason"))
            title = entry.get("title", "")
            body_lines.append(
                f"| #{entry['issue']} | {title} | {reason} |"
            )
        body_lines.append("")

    # Footer
    footer = backlog.get("footer") or ""
    if footer.strip():
        body_lines.append(footer.rstrip())
        body_lines.append("")

    body = "\n".join(body_lines).rstrip() + "\n"

    timestamp_line = timestamp or _utc_timestamp()
    intro = backlog.get("intro") or ""
    how_to_read = backlog.get("how_to_read") or ""

    if template_path is None:
        template_path = (
            Path(__file__).parent / "templates" / "chunks-backlog.md.j2"
        )
    template_text = template_path.read_text()
    template = string.Template(template_text)
    rendered = template.safe_substitute(
        timestamp=timestamp_line,
        total_chunks=str(backlog.get("total_chunks", "")),
        total_issues=str(backlog.get("total_issues", "")),
        intro=intro.rstrip(),
        how_to_read=how_to_read.rstrip(),
        body=body.rstrip(),
    )
    if not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def _utc_timestamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(r"^_Last rendered: .*_$", re.MULTILINE)


def _strip_timestamp(text: str) -> str:
    """Replace the timestamp marker with a stable placeholder."""
    return _TIMESTAMP_RE.sub("_Last rendered: <timestamp>_", text)


def diff_against_disk(rendered: str, on_disk_path: Path) -> bool:
    """Return ``True`` if rendered output matches the on-disk file (ignoring timestamp).

    Args:
        rendered: Newly rendered Markdown.
        on_disk_path: Path to the existing ``docs/CHUNK_BACKLOG.md``.

    Returns:
        ``True`` if equal modulo the timestamp line; ``False`` otherwise.
    """
    if not on_disk_path.exists():
        return False
    existing = on_disk_path.read_text()
    return _strip_timestamp(existing) == _strip_timestamp(rendered)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def render_backlog(
    yaml_path: Path,
    output_path: Path,
    *,
    chunks_root: Path | None = None,
    fetcher: GHFetcherLike | None = None,
    template_path: Path | None = None,
    check: bool = False,
    timestamp: str | None = None,
) -> int:
    """Render the chunk backlog and either write it or compare to disk.

    Args:
        yaml_path: Source YAML.
        output_path: Markdown destination.
        chunks_root: ``chunks/`` directory for in-flight detection.
        fetcher: Object exposing ``fetch_issues`` + ``fetch_merged_prs``;
            defaults to a real :class:`GHFetcher`.
        template_path: Override template path; defaults to
            ``scripts/agentic/templates/chunks-backlog.md.j2``.
        check: If ``True``, do not write; return ``1`` when stale, ``0``
            when fresh.
        timestamp: Optional fixed timestamp (used in ``--check`` to keep the
            comparison stable; in normal renders uses UTC ``now``).

    Returns:
        Exit code: ``0`` on success or fresh, ``1`` if ``--check`` and stale.
    """
    backlog = load_backlog(yaml_path)
    issue_numbers: list[int] = []
    for phase in backlog.get("phases", []) or []:
        for chunk in phase.get("chunks", []) or []:
            for n in chunk.get("issues", []) or []:
                issue_numbers.append(int(n))
    for entry in backlog.get("blocked", []) or []:
        issue_numbers.append(int(entry["issue"]))

    fetcher = fetcher or GHFetcher()
    issue_states = fetcher.fetch_issues(issue_numbers)
    merged_prs = fetcher.fetch_merged_prs()

    rendered = render_markdown(
        backlog,
        issue_states,
        merged_prs,
        chunks_root=chunks_root,
        template_path=template_path,
        timestamp=timestamp,
    )

    if check:
        if diff_against_disk(rendered, output_path):
            logger.info("CHUNK_BACKLOG.md is fresh.")
            return 0
        logger.warning(
            "CHUNK_BACKLOG.md is stale; run `chunks render-backlog` to refresh."
        )
        return 1

    output_path.write_text(rendered)
    return 0


# ---------------------------------------------------------------------------
# CLI entry point (called from scripts/agentic/chunks)
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m scripts.agentic.render_backlog [--check]``.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Render docs/CHUNK_BACKLOG.md from YAML + GitHub state",
    )
    parser.add_argument(
        "--yaml",
        default="docs/chunks-backlog.yaml",
        help="Path to the YAML source",
    )
    parser.add_argument(
        "--output",
        default="docs/CHUNK_BACKLOG.md",
        help="Path to the rendered Markdown",
    )
    parser.add_argument(
        "--chunks-root",
        default="chunks",
        help="Directory containing chunks/<name>/status.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 if the on-disk file is stale",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return render_backlog(
        yaml_path=Path(args.yaml),
        output_path=Path(args.output),
        chunks_root=Path(args.chunks_root),
        check=args.check,
    )


if __name__ == "__main__":  # pragma: no cover - thin entry point
    raise SystemExit(main())
