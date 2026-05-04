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
