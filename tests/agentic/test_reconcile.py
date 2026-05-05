"""Tests for scripts.agentic.reconcile (issue #93)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scripts.agentic.reconcile import (
    ReconcileReport,
    check_run_log_coverage,
    reconcile,
)


@dataclass
class FakeFetcher:
    """In-memory ``GHFetcher`` replacement for tests."""

    issue_states: dict[int, str] = field(default_factory=dict)
    merged_prs: list[dict] = field(default_factory=list)

    def fetch_issues(self, numbers):
        return {int(n): self.issue_states.get(int(n), "UNKNOWN") for n in numbers}

    def fetch_merged_prs(self):
        return list(self.merged_prs)


def _write_yaml(tmp_path: Path) -> Path:
    """Write a tiny YAML backlog used by the reconcile tests."""
    p = tmp_path / "backlog.yaml"
    p.write_text(
        "schema_version: 1\n"
        "total_chunks: 2\n"
        "total_issues: 2\n"
        "phases:\n"
        "  - id: 1\n"
        "    title: T\n"
        "    description: \"\"\n"
        "    chunks:\n"
        "      - name: alpha\n"
        "        issues: [3]\n"
        "        risk: low\n"
        "        prereqs: []\n"
        "        audit: clean\n"
        "        notes: \"\"\n"
        "      - name: beta\n"
        "        issues: [4]\n"
        "        risk: low\n"
        "        prereqs: []\n"
        "        audit: clean\n"
        "        notes: \"\"\n"
    )
    return p


def _render(yaml_path: Path, fetcher: FakeFetcher) -> str:
    """Render the YAML using the canonical render_markdown call shape."""
    from scripts.agentic.render_backlog import load_backlog, render_markdown
    backlog = load_backlog(yaml_path)
    nums = []
    for phase in backlog["phases"]:
        for c in phase["chunks"]:
            nums.extend(c["issues"])
    out = render_markdown(
        backlog,
        fetcher.fetch_issues(nums),
        fetcher.fetch_merged_prs(),
        timestamp="T0",
    )
    return out


# ---------------------------------------------------------------------------
# Backlog-stale detection
# ---------------------------------------------------------------------------


def test_reconcile_clean_when_md_matches_state(tmp_path):
    yaml_path = _write_yaml(tmp_path)
    md_path = tmp_path / "BACKLOG.md"
    log_path = tmp_path / "RUN_LOG.md"
    log_path.write_text(
        "# AGENTIC RUN LOG\n\n"
        "| chunk_name | date | issues | attempts | passed | failed | skipped"
        " | time_s | pr_url |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    fetcher = FakeFetcher(issue_states={3: "OPEN", 4: "OPEN"})
    md_path.write_text(_render(yaml_path, fetcher))
    report = reconcile(
        yaml_path=yaml_path,
        backlog_md_path=md_path,
        run_log_path=log_path,
        fetcher=fetcher,
    )
    assert report.is_clean is True
    assert report.backlog_stale is False


def test_reconcile_flags_stale_backlog(tmp_path):
    yaml_path = _write_yaml(tmp_path)
    md_path = tmp_path / "BACKLOG.md"
    md_path.write_text("# stale\n")
    log_path = tmp_path / "RUN_LOG.md"
    log_path.write_text("\n")
    fetcher = FakeFetcher(issue_states={3: "OPEN", 4: "OPEN"})
    report = reconcile(
        yaml_path=yaml_path,
        backlog_md_path=md_path,
        run_log_path=log_path,
        fetcher=fetcher,
    )
    assert report.is_clean is False
    assert report.backlog_stale is True


# ---------------------------------------------------------------------------
# Run-log coverage
# ---------------------------------------------------------------------------


def test_run_log_coverage_flags_missing_chunk_row(tmp_path):
    """A chunk merged on GitHub but absent from the run-log is drift."""
    yaml_path = _write_yaml(tmp_path)
    log_path = tmp_path / "RUN_LOG.md"
    # Empty run-log
    log_path.write_text(
        "# AGENTIC RUN LOG\n\n"
        "| chunk_name | date | issues | attempts | passed | failed | skipped"
        " | time_s | pr_url |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    md_path = tmp_path / "BACKLOG.md"
    fetcher = FakeFetcher(
        issue_states={3: "CLOSED", 4: "OPEN"},
        merged_prs=[
            {"number": 100, "title": "feat: chunk: alpha", "mergedAt": "x"}
        ],
    )
    md_path.write_text(_render(yaml_path, fetcher))
    report = reconcile(
        yaml_path=yaml_path,
        backlog_md_path=md_path,
        run_log_path=log_path,
        fetcher=fetcher,
    )
    assert "alpha" in report.missing_run_log_rows
    assert report.is_clean is False


def test_run_log_coverage_clean_when_chunk_row_present(tmp_path):
    yaml_path = _write_yaml(tmp_path)
    log_path = tmp_path / "RUN_LOG.md"
    log_path.write_text(
        "# AGENTIC RUN LOG\n\n"
        "| chunk_name | date | issues | attempts | passed | failed | skipped"
        " | time_s | pr_url |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| alpha | 2026-05-05 | #3 |  | 1 | 0 | 0 | 0 | url |\n"
    )
    md_path = tmp_path / "BACKLOG.md"
    fetcher = FakeFetcher(
        issue_states={3: "CLOSED", 4: "OPEN"},
        merged_prs=[
            {"number": 100, "title": "feat: chunk: alpha", "mergedAt": "x"}
        ],
    )
    md_path.write_text(_render(yaml_path, fetcher))
    report = reconcile(
        yaml_path=yaml_path,
        backlog_md_path=md_path,
        run_log_path=log_path,
        fetcher=fetcher,
    )
    assert "alpha" not in report.missing_run_log_rows


def test_check_run_log_coverage_returns_orphans():
    """A merged PR whose title looks chunk-shaped but isn't in the YAML is an orphan."""
    backlog = {
        "schema_version": 1,
        "phases": [
            {
                "id": 1, "title": "T", "description": "", "chunks": [
                    {
                        "name": "alpha", "issues": [3],
                        "risk": "low", "prereqs": [], "audit": "clean",
                        "notes": "",
                    }
                ],
            }
        ],
    }
    merged = [
        {"number": 200, "title": "chunk: ghost-feature", "mergedAt": "x"},
    ]
    # No run-log entries.
    missing, orphans = check_run_log_coverage(
        backlog,
        merged,
        Path("/nonexistent/RUN_LOG.md"),
    )
    assert 200 in orphans
    assert missing == []  # alpha has no merged PR


def test_check_run_log_coverage_skips_off_pipeline_logged_orphans(tmp_path):
    """Off-pipeline chunks that the operator logged manually are not flagged."""
    backlog = {
        "schema_version": 1,
        "phases": [
            {
                "id": 1, "title": "T", "description": "", "chunks": [
                    {
                        "name": "alpha", "issues": [3],
                        "risk": "low", "prereqs": [], "audit": "clean",
                        "notes": "",
                    }
                ],
            }
        ],
    }
    log_path = tmp_path / "RUN_LOG.md"
    log_path.write_text(
        "# AGENTIC RUN LOG\n\n"
        "| chunk_name | date | issues | attempts | passed | failed | skipped"
        " | time_s | pr_url |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| ghost-feature | 2026-05-05 | #99 |  | 1 | 0 | 0 | 0 | url |\n"
    )
    merged = [
        {"number": 200, "title": "chunk: ghost-feature", "mergedAt": "x"},
    ]
    missing, orphans = check_run_log_coverage(backlog, merged, log_path)
    assert orphans == []  # logged manually, not drift


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def test_report_clean_text():
    report = ReconcileReport()
    text = report.to_text()
    assert "CLEAN" in text


def test_report_drift_text_lists_specifics():
    report = ReconcileReport(
        backlog_stale=True,
        missing_run_log_rows=["alpha"],
        unreferenced_merged_prs=[200],
    )
    text = report.to_text()
    assert "DRIFT" in text
    assert "stale" in text
    assert "alpha" in text
    assert "#200" in text
