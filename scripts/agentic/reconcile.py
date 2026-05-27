"""Reconcile chunk-pipeline docs against GitHub state.

Issue #93: detect drift between the YAML/Markdown world and what GitHub thinks
is open, closed, or merged. Suitable for an operator hygiene check or a CI
gate. Exits non-zero on any drift.

Three checks:

1. **Backlog freshness** — runs the equivalent of ``render-backlog --check``.
2. **Run-log coverage** — flags chunk PRs that are merged on GitHub but have
   no row in ``docs/AGENTIC_RUN_LOG.md``.
3. **Untracked artifacts** — flags *merged* chunks whose run artifacts were
   never committed to git (the gap that left ``chunks/electronic-bootstrap/``
   untracked after PR #152 merged; added 2026-05-27).

The data fetcher and the git-untracked query are both injectable so unit
tests don't shell out to ``gh`` or ``git``.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from scripts.agentic.render_backlog import (
    GHFetcher,
    GHFetcherLike,
    _find_chunk_pr,
    diff_against_disk,
    load_backlog,
    render_markdown,
)

logger = logging.getLogger(__name__)


@dataclass
class ReconcileReport:
    """Result of a reconcile run.

    Attributes:
        backlog_stale: ``True`` if ``CHUNK_BACKLOG.md`` no longer matches the
            joined YAML + GitHub state.
        missing_run_log_rows: Names of chunks whose PR is merged on GitHub but
            absent from the run-log.
        unreferenced_merged_prs: Numbers of merged PRs whose titles look like
            chunk PRs but don't match any YAML chunk.
        untracked_artifact_chunks: Names of merged chunks whose run artifacts
            are still untracked (non-gitignored) on disk, i.e. were never
            committed to record the run.
        notes: Free-form human-readable notes appended by the various checks.
    """

    backlog_stale: bool = False
    missing_run_log_rows: list[str] = field(default_factory=list)
    unreferenced_merged_prs: list[int] = field(default_factory=list)
    untracked_artifact_chunks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """Return ``True`` when no drift was detected."""
        return (
            not self.backlog_stale
            and not self.missing_run_log_rows
            and not self.unreferenced_merged_prs
            and not self.untracked_artifact_chunks
        )

    def to_text(self) -> str:
        """Render the report as a human-readable string."""
        lines: list[str] = ["chunks reconcile report", "=" * 27, ""]
        if self.is_clean:
            lines.append("CLEAN — no drift detected.")
        else:
            lines.append("DRIFT detected:")
            if self.backlog_stale:
                lines.append(
                    "  - docs/CHUNK_BACKLOG.md is stale; "
                    "run `chunks render-backlog` to refresh."
                )
            for chunk in self.missing_run_log_rows:
                lines.append(
                    f"  - chunk {chunk!r} appears merged on GitHub but has "
                    f"no row in docs/AGENTIC_RUN_LOG.md."
                )
            for pr in self.unreferenced_merged_prs:
                lines.append(
                    f"  - merged PR #{pr} looks chunk-shaped but matches no "
                    f"chunk in docs/chunks-backlog.yaml."
                )
            for chunk in self.untracked_artifact_chunks:
                lines.append(
                    f"  - merged chunk {chunk!r} has untracked artifacts on "
                    f"disk; run `git add chunks/{chunk}/ && git commit` to "
                    f"record the run (see docs/CHUNK_PLAYBOOK.md)."
                )
        for note in self.notes:
            lines.append(f"  note: {note}")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


_CHUNK_TITLE_RE = re.compile(
    r"chunk[:/\s]\s*([a-z0-9][a-z0-9\-]*)", re.IGNORECASE
)


def _run_log_chunk_names(run_log_path: Path) -> set[str]:
    """Extract chunk names from the run-log markdown table."""
    if not run_log_path.exists():
        return set()
    names: set[str] = set()
    for line in run_log_path.read_text().splitlines():
        # Skip header / divider rows.
        if not line.startswith("|") or line.startswith("| chunk_name") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3:
            continue
        # cells[0] is empty (leading "|"), cells[1] is chunk_name.
        chunk_name = cells[1]
        if chunk_name and chunk_name != "chunk_name":
            # Drop any " (off-pipeline)" suffix etc.
            base = chunk_name.split()[0] if chunk_name else ""
            if base:
                names.add(base)
    return names


def _yaml_chunk_names(backlog: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for phase in backlog.get("phases", []) or []:
        for chunk in phase.get("chunks", []) or []:
            out.add(chunk["name"])
    return out


def check_backlog_freshness(
    backlog: dict[str, Any],
    issue_states: dict[int, str],
    merged_prs: list[dict[str, Any]],
    backlog_md_path: Path,
    chunks_root: Path | None,
    template_path: Path | None,
) -> bool:
    """Return ``True`` if the rendered output matches the on-disk backlog.

    Args:
        backlog: Parsed YAML.
        issue_states: GitHub issue states.
        merged_prs: Merged-PR records from GitHub.
        backlog_md_path: ``docs/CHUNK_BACKLOG.md``.
        chunks_root: Optional ``chunks/`` directory.
        template_path: Optional template override.

    Returns:
        ``True`` when fresh, ``False`` when stale.
    """
    rendered = render_markdown(
        backlog,
        issue_states,
        merged_prs,
        chunks_root=chunks_root,
        template_path=template_path,
    )
    return diff_against_disk(rendered, backlog_md_path)


def check_run_log_coverage(
    backlog: dict[str, Any],
    merged_prs: list[dict[str, Any]],
    run_log_path: Path,
) -> tuple[list[str], list[int]]:
    """Find chunks merged on GitHub but missing from the run-log, and orphans.

    Args:
        backlog: Parsed YAML.
        merged_prs: Merged-PR records from GitHub.
        run_log_path: Path to ``docs/AGENTIC_RUN_LOG.md``.

    Returns:
        Tuple ``(missing_run_log_rows, unreferenced_merged_prs)`` where:

        - ``missing_run_log_rows`` is a list of YAML chunk names whose PR is
          merged on GitHub but absent from the run-log.
        - ``unreferenced_merged_prs`` is a list of merged PR numbers whose
          titles look chunk-shaped but match no YAML chunk.
    """
    log_names = _run_log_chunk_names(run_log_path)
    yaml_names = _yaml_chunk_names(backlog)

    missing: list[str] = []
    for name in sorted(yaml_names):
        pr = _find_chunk_pr(name, merged_prs)
        if pr is not None and name not in log_names:
            missing.append(name)

    orphans: list[int] = []
    for pr in merged_prs:
        title = (pr.get("title") or "").lower()
        m = _CHUNK_TITLE_RE.search(title)
        if not m:
            continue
        chunk_token = m.group(1)
        if chunk_token in yaml_names:
            continue
        # Skip rows already in the run-log (off-pipeline cleanup that the
        # operator logged manually).
        if chunk_token in log_names:
            continue
        orphans.append(int(pr.get("number", 0)))
    return missing, sorted(orphans)


def _git_untracked_under(chunks_root: Path) -> list[str]:
    """Return untracked, non-gitignored paths under ``chunks_root``.

    Shells out to ``git ls-files --others --exclude-standard`` with the chunks
    directory as the working dir, so returned paths are relative to it (the
    first path segment is the chunk name) and ``.gitignore`` is honoured
    (test-data.json, sandbox-test-output/, __pycache__/, etc. are excluded).
    Returns an empty list when git is unavailable or the directory is outside
    a repo, so the check degrades to "no drift" rather than crashing reconcile.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(chunks_root), "ls-files",
             "--others", "--exclude-standard", "."],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):  # git missing / bad path
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def check_untracked_chunk_artifacts(
    chunks_root: Path | None,
    *,
    untracked_fn: Callable[[Path], Iterable[str]] | None = None,
) -> list[str]:
    """Find *merged* chunks whose run artifacts are still untracked on disk.

    A merged chunk's run artifacts (manifest.json, status.json, test-results
    .json, sandbox-tests/) are expected to be committed to record the run
    (docs/CHUNK_PLAYBOOK.md). ``chunks complete`` does not commit them — that
    is a manual operator step (R3) — so a forgotten commit leaves the directory
    untracked with no other warning (the gap that left
    ``chunks/electronic-bootstrap/`` untracked after PR #152 merged). This
    surfaces that drift. In-flight (non-merged) chunks are ignored because
    uncommitted work-in-progress there is expected.

    Args:
        chunks_root: The ``chunks/`` directory, or ``None``.
        untracked_fn: Injectable query returning untracked (non-gitignored)
            paths relative to ``chunks_root`` (first path segment = chunk
            name). Defaults to a ``git ls-files --others`` shell-out; injected
            in tests so they never touch real git.

    Returns:
        Sorted names of chunks whose ``status.json`` stage is ``"merged"`` and
        which own at least one untracked artifact path.
    """
    if chunks_root is None or not chunks_root.is_dir():
        return []
    query = untracked_fn or _git_untracked_under
    candidates: set[str] = set()
    for rel in query(chunks_root):
        parts = Path(rel).parts
        if parts:
            candidates.add(parts[0])

    flagged: list[str] = []
    for name in sorted(candidates):
        status_path = chunks_root / name / "status.json"
        if not status_path.exists():
            continue
        try:
            stage = json.loads(status_path.read_text()).get("stage")
        except (OSError, json.JSONDecodeError):
            continue
        if stage == "merged":
            flagged.append(name)
    return flagged


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def reconcile(
    yaml_path: Path,
    backlog_md_path: Path,
    run_log_path: Path,
    *,
    chunks_root: Path | None = None,
    fetcher: GHFetcherLike | None = None,
    template_path: Path | None = None,
    untracked_fn: Callable[[Path], Iterable[str]] | None = None,
) -> ReconcileReport:
    """Run all reconcile checks and return a structured report.

    Args:
        yaml_path: ``docs/chunks-backlog.yaml``.
        backlog_md_path: ``docs/CHUNK_BACKLOG.md``.
        run_log_path: ``docs/AGENTIC_RUN_LOG.md``.
        chunks_root: ``chunks/`` directory (for in-flight detection).
        fetcher: Object with ``fetch_issues`` + ``fetch_merged_prs`` methods.
        template_path: Optional template override.

    Returns:
        A :class:`ReconcileReport` with all detected drift.
    """
    backlog = load_backlog(yaml_path)
    fetcher = fetcher or GHFetcher()
    issue_numbers: list[int] = []
    for phase in backlog.get("phases", []) or []:
        for chunk in phase.get("chunks", []) or []:
            for n in chunk.get("issues", []) or []:
                issue_numbers.append(int(n))
    for entry in backlog.get("blocked", []) or []:
        issue_numbers.append(int(entry["issue"]))

    issue_states = fetcher.fetch_issues(issue_numbers)
    merged_prs = fetcher.fetch_merged_prs()

    fresh = check_backlog_freshness(
        backlog,
        issue_states,
        merged_prs,
        backlog_md_path,
        chunks_root=chunks_root,
        template_path=template_path,
    )
    missing, orphans = check_run_log_coverage(
        backlog, merged_prs, run_log_path
    )
    report = ReconcileReport(
        backlog_stale=not fresh,
        missing_run_log_rows=missing,
        unreferenced_merged_prs=orphans,
        untracked_artifact_chunks=check_untracked_chunk_artifacts(
            chunks_root, untracked_fn=untracked_fn
        ),
    )
    if not run_log_path.exists():
        report.notes.append(
            f"run-log not found at {run_log_path}; coverage check skipped."
        )
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m scripts.agentic.reconcile``.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        ``0`` on clean state, ``1`` on any drift.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Reconcile chunk-pipeline docs against GitHub state",
    )
    parser.add_argument("--yaml", default="docs/chunks-backlog.yaml")
    parser.add_argument("--backlog-md", default="docs/CHUNK_BACKLOG.md")
    parser.add_argument("--run-log", default="docs/AGENTIC_RUN_LOG.md")
    parser.add_argument("--chunks-root", default="chunks")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    report = reconcile(
        yaml_path=Path(args.yaml),
        backlog_md_path=Path(args.backlog_md),
        run_log_path=Path(args.run_log),
        chunks_root=Path(args.chunks_root),
    )
    print(report.to_text(), end="")
    return 0 if report.is_clean else 1


if __name__ == "__main__":  # pragma: no cover - thin entry point
    raise SystemExit(main())
