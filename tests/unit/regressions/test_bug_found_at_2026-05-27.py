"""R10 regression test for the chunk-pipeline guardrail gap found 2026-05-27.

A merged chunk's run artifacts (manifest.json, status.json, test-results.json,
sandbox-tests/) are expected to be committed to git to record the run (see
docs/CHUNK_PLAYBOOK.md). But ``chunks complete`` never commits them — that is a
manual operator step (R3, human-paced) — and ``chunks reconcile`` only checked
backlog freshness and run-log coverage. So when an operator forgot to commit a
merged chunk's artifacts (``chunks/electronic-bootstrap/`` was left untracked
after PR #152 merged), nothing in the pipeline flagged it: the directory sat
untracked indefinitely with no warning.

This locks in the new reconcile guardrail: a *merged* chunk that still has
untracked, non-gitignored artifacts on disk is drift, populates
``ReconcileReport.untracked_artifact_chunks``, and makes ``chunks reconcile``
exit non-zero. The git query (``untracked_fn``) is injected so the test never
shells out to git.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.agentic.reconcile import (
    ReconcileReport,
    check_untracked_chunk_artifacts,
)


def _make_chunk(chunks_root: Path, name: str, stage: str) -> Path:
    """Create chunks/<name>/ with a status.json at the given lifecycle stage."""
    chunk_dir = chunks_root / name
    chunk_dir.mkdir(parents=True)
    (chunk_dir / "status.json").write_text(
        json.dumps({"chunk": name, "stage": stage}) + "\n"
    )
    (chunk_dir / "manifest.json").write_text(json.dumps({"issues": []}) + "\n")
    return chunk_dir


def test_merged_chunk_with_untracked_artifacts_is_flagged(tmp_path):
    """The exact electronic-bootstrap failure mode: merged + untracked dir."""
    chunks_root = tmp_path / "chunks"
    _make_chunk(chunks_root, "ghost", stage="merged")
    untracked = lambda root: ["ghost/manifest.json", "ghost/status.json"]
    assert check_untracked_chunk_artifacts(
        chunks_root, untracked_fn=untracked
    ) == ["ghost"]


def test_fully_committed_merged_chunk_not_flagged(tmp_path):
    """A merged chunk whose artifacts are all tracked is clean."""
    chunks_root = tmp_path / "chunks"
    _make_chunk(chunks_root, "clean", stage="merged")
    assert check_untracked_chunk_artifacts(
        chunks_root, untracked_fn=lambda root: []
    ) == []


def test_in_flight_chunk_with_untracked_artifacts_not_flagged(tmp_path):
    """Active (non-merged) chunks legitimately carry uncommitted work."""
    chunks_root = tmp_path / "chunks"
    _make_chunk(chunks_root, "wip", stage="implementing")
    untracked = lambda root: ["wip/manifest.json"]
    assert check_untracked_chunk_artifacts(
        chunks_root, untracked_fn=untracked
    ) == []


def test_only_merged_chunks_flagged_when_several_are_untracked(tmp_path):
    """Mixed stages: flag the merged one, ignore the in-flight one."""
    chunks_root = tmp_path / "chunks"
    _make_chunk(chunks_root, "done", stage="merged")
    _make_chunk(chunks_root, "wip", stage="testing")
    untracked = lambda root: ["done/status.json", "wip/status.json"]
    assert check_untracked_chunk_artifacts(
        chunks_root, untracked_fn=untracked
    ) == ["done"]


def test_missing_chunks_root_is_clean(tmp_path):
    """A non-existent chunks/ directory is not drift."""
    assert check_untracked_chunk_artifacts(
        tmp_path / "nope", untracked_fn=lambda root: []
    ) == []


def test_report_with_untracked_artifacts_is_not_clean():
    """The reconcile report surfaces the gap and is no longer clean."""
    report = ReconcileReport(untracked_artifact_chunks=["ghost"])
    assert report.is_clean is False
    text = report.to_text().lower()
    assert "ghost" in text
    assert "untracked" in text
