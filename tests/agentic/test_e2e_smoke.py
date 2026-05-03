"""End-to-end smoke: parse → manifest → status → CLI → no babysitter run.

This test does NOT spawn a real babysitter run (those are integration-tested
manually). It verifies that the Python+CLI pipeline can:

1. Parse the synthetic issue fixture.
2. Write a manifest containing the parsed issue.
3. Initialize chunks/<name>/status.json correctly.
4. The chunks CLI can list/status/abort the chunk.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


def test_e2e_pipeline_round_trip(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    chunk_dir = chunks_dir / "synthetic"
    chunk_dir.mkdir()

    # Step 1: parse synthetic issue
    from scripts.agentic.issue_parser import parse_issue
    raw = json.loads((FIXTURES / "issue-999.json").read_text())
    parsed = parse_issue(raw)
    assert parsed["number"] == 999

    # Step 2: write manifest
    manifest = {"chunk": "synthetic", "issues": [parsed]}
    (chunk_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Step 3: init status
    from scripts.agentic.chunk_status import init_status, list_active
    init_status(chunk_dir, chunk_name="synthetic", issues=[999])
    assert (chunk_dir / "status.json").exists()
    active = list_active(chunks_root=chunks_dir)
    assert len(active) == 1
    assert active[0]["chunk"] == "synthetic"

    # Step 4: CLI list shows the chunk
    env = os.environ.copy()
    env["CHUNKS_DIR"] = str(chunks_dir)
    env.pop("ALMA_PROD_API_KEY", None)
    cli = REPO_ROOT / "scripts" / "agentic" / "chunks"
    r = subprocess.run([str(cli), "list"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "synthetic" in r.stdout

    # Step 5: CLI abort moves it to terminal state
    r = subprocess.run([str(cli), "abort", "synthetic"], env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    final = json.loads((chunk_dir / "status.json").read_text())
    assert final["stage"] == "aborted"

    # Step 6: list now shows no active chunks
    r = subprocess.run([str(cli), "list"], env=env, capture_output=True, text=True)
    assert "synthetic" not in r.stdout or "no active" in r.stdout.lower()
