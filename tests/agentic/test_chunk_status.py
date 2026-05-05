"""Tests for scripts.agentic.chunk_status (spec §8.5)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_init_status_writes_required_fields(tmp_path):
    from scripts.agentic.chunk_status import init_status

    chunk_dir = tmp_path / "chunks" / "http-foundation"
    chunk_dir.mkdir(parents=True)
    init_status(chunk_dir, chunk_name="http-foundation", issues=[3, 4])

    status = json.loads((chunk_dir / "status.json").read_text())
    assert status["chunk"] == "http-foundation"
    assert status["issues"] == [3, 4]
    assert status["stage"] == "defined"
    assert status["branch"] == "chunk/http-foundation"
    assert "createdAt" in status
    assert "updatedAt" in status
    assert status["lastEvent"]
    assert status["nextAction"]


def test_transition_updates_stage_and_event(tmp_path):
    from scripts.agentic.chunk_status import init_status, transition

    chunk_dir = tmp_path / "chunks" / "x"
    chunk_dir.mkdir(parents=True)
    init_status(chunk_dir, chunk_name="x", issues=[1])

    transition(
        chunk_dir,
        new_stage="impl-running",
        last_event="kicked off implementation",
        next_action="wait for completion",
    )
    status = json.loads((chunk_dir / "status.json").read_text())
    assert status["stage"] == "impl-running"
    assert status["lastEvent"] == "kicked off implementation"
    assert status["nextAction"] == "wait for completion"


def test_invalid_stage_rejected(tmp_path):
    from scripts.agentic.chunk_status import init_status, transition

    chunk_dir = tmp_path / "chunks" / "x"
    chunk_dir.mkdir(parents=True)
    init_status(chunk_dir, chunk_name="x", issues=[1])

    with pytest.raises(ValueError, match="invalid stage"):
        transition(chunk_dir, new_stage="bogus", last_event="...", next_action="...")


def test_list_active_excludes_terminal_states(tmp_path):
    from scripts.agentic.chunk_status import init_status, transition, list_active

    for name, terminal in [("a", False), ("b", True), ("c", True)]:
        d = tmp_path / "chunks" / name
        d.mkdir(parents=True)
        init_status(d, chunk_name=name, issues=[1])
        if terminal:
            stage = "merged" if name == "b" else "aborted"
            transition(d, new_stage=stage, last_event="done", next_action="none")

    active = list_active(chunks_root=tmp_path / "chunks")
    names = [s["chunk"] for s in active]
    assert "a" in names
    assert "b" not in names
    assert "c" not in names


# ---- R10 regression for #99 Layer 1: warn at define time on empty files_to_touch ----

def test_compute_empty_scope_warning_returns_none_when_all_have_files():
    from scripts.agentic.chunk_status import compute_empty_scope_warning

    manifest = {"chunk": "x", "issues": [
        {"number": 13, "files_to_touch": ["src/foo.py"]},
        {"number": 16, "files_to_touch": ["src/bar.py"]},
    ]}
    assert compute_empty_scope_warning(manifest, "x") is None


def test_compute_empty_scope_warning_lists_empty_issues():
    """R10 regression for #99 Layer 1.

    Issues #13 and #16 (architectural cleanups) had no '## Files to touch'
    section in their bodies, so the parser returned `files_to_touch: []`
    and the chunk-define step silently produced a manifest that was guaranteed
    to fail R7 scope-check on every impl attempt. The warning must surface
    every offending issue and tell the operator how to recover.
    """
    from scripts.agentic.chunk_status import compute_empty_scope_warning

    manifest = {"chunk": "client-ergonomics", "issues": [
        {"number": 13, "files_to_touch": []},
        {"number": 16, "files_to_touch": []},
    ]}
    warning = compute_empty_scope_warning(manifest, "client-ergonomics")
    assert warning is not None
    assert "WARNING" in warning
    assert "#13" in warning
    assert "#16" in warning
    assert "files_to_touch" in warning
    assert "chunks/client-ergonomics/manifest.json" in warning
    assert "scope-check" in warning


def test_compute_empty_scope_warning_handles_missing_field():
    """If `files_to_touch` is absent (not just empty), still treat as empty."""
    from scripts.agentic.chunk_status import compute_empty_scope_warning

    manifest = {"chunk": "x", "issues": [
        {"number": 13},  # no files_to_touch key at all
    ]}
    warning = compute_empty_scope_warning(manifest, "x")
    assert warning is not None
    assert "#13" in warning


def test_compute_empty_scope_warning_partial_only_lists_empty():
    """Mix of populated and empty: only the empty ones appear in the warning."""
    from scripts.agentic.chunk_status import compute_empty_scope_warning

    manifest = {"chunk": "x", "issues": [
        {"number": 13, "files_to_touch": ["src/foo.py"]},
        {"number": 16, "files_to_touch": []},
        {"number": 99, "files_to_touch": ["docs/y.md"]},
    ]}
    warning = compute_empty_scope_warning(manifest, "x")
    assert warning is not None
    assert "#16" in warning
    assert "#13" not in warning
    assert "#99" not in warning
