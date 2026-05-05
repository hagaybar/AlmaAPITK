"""Tests for scripts.agentic.render_backlog (issue #93).

These tests exercise the YAML loader, status derivation, and the render +
``--check`` exit-code paths. The ``gh`` CLI is never invoked: tests inject a
fake fetcher.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from scripts.agentic.render_backlog import (
    YAMLParseError,
    derive_chunk_status,
    diff_against_disk,
    load_backlog,
    loads_yaml,
    render_backlog,
    render_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FakeFetcher:
    """In-memory ``GHFetcher`` replacement for tests.

    Args:
        issue_states: Pre-baked ``{number: state}`` map.
        merged_prs: List of merged-PR dicts to return.
    """

    issue_states: dict[int, str] = field(default_factory=dict)
    merged_prs: list[dict] = field(default_factory=list)

    def fetch_issues(self, numbers):
        return {int(n): self.issue_states.get(int(n), "UNKNOWN") for n in numbers}

    def fetch_merged_prs(self):
        return list(self.merged_prs)


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


def test_yaml_loader_parses_minimal_schema():
    text = """schema_version: 1
phases:
  - id: 1
    title: Foo
    description: ""
    chunks:
      - name: alpha
        issues: [3, 4]
        risk: low
        prereqs: []
        audit: clean
        notes: |
          Multi-line note
          continues here.
"""
    data = loads_yaml(text)
    assert data["schema_version"] == 1
    assert len(data["phases"]) == 1
    phase = data["phases"][0]
    assert phase["title"] == "Foo"
    chunk = phase["chunks"][0]
    assert chunk["name"] == "alpha"
    assert chunk["issues"] == [3, 4]
    assert chunk["prereqs"] == []
    assert chunk["audit"] == "clean"
    assert "Multi-line" in chunk["notes"]
    assert "continues here" in chunk["notes"]


def test_yaml_loader_preserves_hash_at_start_of_block_scalar():
    """Block-scalar lines beginning with `#` (e.g. ``#3, #4``) must survive."""
    text = """schema_version: 1
phases:
  - id: 1
    title: T
    description: ""
    chunks:
      - name: a
        issues: [3]
        risk: low
        prereqs: []
        audit: clean
        notes: |
          #3 is the lead issue here.
"""
    data = loads_yaml(text)
    assert "#3" in data["phases"][0]["chunks"][0]["notes"]


def test_yaml_loader_rejects_unknown_schema_version(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 99\nphases: []\n")
    with pytest.raises(ValueError, match="schema_version"):
        load_backlog(bad)


def test_yaml_loader_real_backlog_loads():
    """The committed YAML file must round-trip cleanly."""
    backlog = load_backlog(REPO_ROOT / "docs" / "chunks-backlog.yaml")
    assert backlog["schema_version"] == 1
    # Every chunk has the required keys.
    for phase in backlog["phases"]:
        for chunk in phase["chunks"]:
            for required in ("name", "issues", "risk", "prereqs", "audit"):
                assert required in chunk, f"missing {required} on {chunk!r}"


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


def test_status_merged_when_all_issues_closed_and_pr_found(tmp_path):
    chunk = {"name": "alpha", "issues": [3, 4]}
    issue_states = {3: "CLOSED", 4: "CLOSED"}
    prs = [{"number": 81, "title": "feat: chunk: alpha", "mergedAt": "x"}]
    assert derive_chunk_status(chunk, issue_states, prs, None) == "merged"


def test_status_merged_when_all_closed_even_without_pr_match(tmp_path):
    """All issues closed off-pipeline still resolves as merged."""
    chunk = {"name": "alpha", "issues": [3]}
    issue_states = {3: "CLOSED"}
    assert derive_chunk_status(chunk, issue_states, [], None) == "merged"


def test_status_partial_when_some_closed_some_open():
    chunk = {"name": "beta", "issues": [1, 2]}
    issue_states = {1: "CLOSED", 2: "OPEN"}
    assert derive_chunk_status(chunk, issue_states, [], None) == "partial"


def test_status_in_flight_when_status_json_present(tmp_path):
    chunk_dir = tmp_path / "alpha"
    chunk_dir.mkdir()
    (chunk_dir / "status.json").write_text('{"stage": "impl-running"}')
    chunk = {"name": "alpha", "issues": [99]}
    issue_states = {99: "OPEN"}
    assert derive_chunk_status(chunk, issue_states, [], chunk_dir) == "in-flight"


def test_status_planned_when_nothing_closed_and_no_status_json(tmp_path):
    chunk = {"name": "alpha", "issues": [99]}
    issue_states = {99: "OPEN"}
    assert derive_chunk_status(chunk, issue_states, [], None) == "planned"


# ---------------------------------------------------------------------------
# Render output shape
# ---------------------------------------------------------------------------


def _minimal_backlog() -> dict:
    return {
        "schema_version": 1,
        "total_chunks": 2,
        "total_issues": 3,
        "intro": "Intro line.",
        "how_to_read": "Read carefully.",
        "phases": [
            {
                "id": 1,
                "title": "Foundations",
                "description": "Foo.",
                "chunks": [
                    {
                        "name": "alpha",
                        "issues": [3, 4],
                        "risk": "low",
                        "prereqs": [],
                        "audit": "clean",
                        "notes": "Pilot chunk.",
                    },
                    {
                        "name": "beta",
                        "issues": [5],
                        "risk": "med",
                        "prereqs": [3],
                        "audit": "clean",
                        "notes": "",
                    },
                ],
            }
        ],
        "blocked": [],
    }


def test_render_includes_status_column():
    backlog = _minimal_backlog()
    fetcher = FakeFetcher(
        issue_states={3: "CLOSED", 4: "CLOSED", 5: "OPEN"},
        merged_prs=[{"number": 1, "title": "feat: chunk: alpha", "mergedAt": "x"}],
    )
    out = render_markdown(
        backlog,
        fetcher.fetch_issues([3, 4, 5]),
        fetcher.fetch_merged_prs(),
        timestamp="FIXED",
    )
    assert "| Status |" in out
    assert "merged" in out  # alpha
    assert "planned" in out  # beta
    assert "FIXED" in out


def test_render_lists_blocked_section():
    backlog = _minimal_backlog()
    backlog["blocked"] = [
        {"issue": 29, "title": "Stuck thing", "reason": "Audit conflict."}
    ]
    out = render_markdown(
        backlog, {}, [], timestamp="FIXED"
    )
    assert "## Blocked" in out
    assert "#29" in out
    assert "Audit conflict" in out


def test_render_real_backlog_against_known_state():
    """Render with a known-state stub and check the expected statuses appear."""
    backlog = load_backlog(REPO_ROOT / "docs" / "chunks-backlog.yaml")
    closed = {3, 4, 5, 6, 7, 9, 10, 14, 1, 83, 85, 86, 90}
    issue_states = {}
    for phase in backlog["phases"]:
        for chunk in phase["chunks"]:
            for n in chunk.get("issues", []) or []:
                issue_states[n] = "CLOSED" if n in closed else "OPEN"
    issue_states[29] = "OPEN"
    prs = [
        {"number": 81, "title": "chunk: http-session-and-request", "mergedAt": "x"},
        {"number": 82, "title": "chunk: http-retry", "mergedAt": "x"},
        {"number": 84, "title": "chunk: http-timeout-and-region", "mergedAt": "x"},
        {"number": 88, "title": "chunk: logger-cleanup", "mergedAt": "x"},
        {"number": 89, "title": "chunk: errors-mapping", "mergedAt": "x"},
    ]
    out = render_markdown(
        backlog, issue_states, prs, timestamp="FIXED",
    )
    # Phase 1 chunks should all show merged.
    for name in (
        "http-session-and-request",
        "http-retry",
        "http-timeout-and-region",
        "logger-cleanup",
        "errors-mapping",
    ):
        # Find the row.
        for line in out.splitlines():
            if f"`{name}`" in line:
                assert "merged" in line, f"chunk {name} not merged in: {line}"
                break
        else:
            pytest.fail(f"chunk {name} not rendered")
    # pypi-publish-ready should be partial (1 closed, 17 open).
    for line in out.splitlines():
        if "`pypi-publish-ready`" in line:
            assert "partial" in line
            break
    else:
        pytest.fail("pypi-publish-ready not rendered")


# ---------------------------------------------------------------------------
# --check mode and exit codes
# ---------------------------------------------------------------------------


def test_check_returns_zero_when_fresh(tmp_path):
    yaml_path = tmp_path / "backlog.yaml"
    yaml_path.write_text(
        "schema_version: 1\n"
        "total_chunks: 1\n"
        "total_issues: 1\n"
        "phases:\n"
        "  - id: 1\n"
        "    title: T\n"
        "    description: \"\"\n"
        "    chunks:\n"
        "      - name: x\n"
        "        issues: [1]\n"
        "        risk: low\n"
        "        prereqs: []\n"
        "        audit: clean\n"
        "        notes: \"\"\n"
    )
    md_path = tmp_path / "BACKLOG.md"
    fetcher = FakeFetcher(issue_states={1: "OPEN"})
    # First write
    rc = render_backlog(yaml_path, md_path, fetcher=fetcher, timestamp="T1")
    assert rc == 0
    assert md_path.exists()
    # --check against the just-written file using a different timestamp:
    # the timestamp line must be ignored by the diff.
    rc_check = render_backlog(
        yaml_path, md_path, fetcher=fetcher, check=True, timestamp="T2"
    )
    assert rc_check == 0


def test_check_returns_one_when_stale(tmp_path):
    yaml_path = tmp_path / "backlog.yaml"
    yaml_path.write_text(
        "schema_version: 1\n"
        "total_chunks: 1\n"
        "total_issues: 1\n"
        "phases:\n"
        "  - id: 1\n"
        "    title: T\n"
        "    description: \"\"\n"
        "    chunks:\n"
        "      - name: x\n"
        "        issues: [1]\n"
        "        risk: low\n"
        "        prereqs: []\n"
        "        audit: clean\n"
        "        notes: \"\"\n"
    )
    md_path = tmp_path / "BACKLOG.md"
    md_path.write_text("# Stale content\n")
    fetcher = FakeFetcher(issue_states={1: "OPEN"})
    rc = render_backlog(yaml_path, md_path, fetcher=fetcher, check=True)
    assert rc == 1
    # --check must NOT overwrite the file.
    assert md_path.read_text() == "# Stale content\n"


def test_diff_against_disk_ignores_timestamp_line(tmp_path):
    md = tmp_path / "x.md"
    md.write_text(
        "# Doc\n\n_Last rendered: 2026-01-01T00:00:00Z_\n\nbody\n"
    )
    fresh = "# Doc\n\n_Last rendered: 2026-12-31T23:59:59Z_\n\nbody\n"
    assert diff_against_disk(fresh, md) is True


def test_diff_against_disk_detects_body_change(tmp_path):
    md = tmp_path / "x.md"
    md.write_text(
        "# Doc\n\n_Last rendered: 2026-01-01T00:00:00Z_\n\nbody A\n"
    )
    fresh = "# Doc\n\n_Last rendered: 2026-01-01T00:00:00Z_\n\nbody B\n"
    assert diff_against_disk(fresh, md) is False
