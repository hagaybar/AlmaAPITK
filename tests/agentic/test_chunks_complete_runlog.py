"""Tests: ``chunks complete`` must append a row to docs/AGENTIC_RUN_LOG.md.

Issue #93 wires the existing ``run_log.append_chunk_row`` writer into the
``complete`` subcommand. These tests exercise the bash CLI end-to-end against
a temp repo.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "agentic" / "chunks"


def _make_chunk(chunks_dir: Path, name: str, issue_number: int = 1) -> Path:
    """Create a minimally-valid chunk directory (manifest + status.json)."""
    chunk_dir = chunks_dir / name
    chunk_dir.mkdir(parents=True)
    manifest = {
        "chunk": name,
        "issues": [{"number": issue_number, "title": "test", "body_raw": ""}],
    }
    (chunk_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.agentic.chunk_status import init_status
    init_status(chunk_dir, chunk_name=name, issues=[issue_number])
    # The complete subcommand expects pr-opened or similar; transition to
    # pr-opened so that "merged" is a valid follow-up.
    from scripts.agentic.chunk_status import transition
    transition(chunk_dir, "pr-opened", "PR opened", "merge it")
    return chunk_dir


def _seed_repo(tmp_path: Path) -> Path:
    """Bootstrap a temp git repo so ``cd $REPO_ROOT`` succeeds in the CLI."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=str(repo), check=True)
    (repo / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=str(repo), check=True)
    return repo


def _build_env(repo: Path, chunks: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("ALMA_PROD_API_KEY", None)
    env["CHUNKS_DIR"] = str(chunks)
    env["REPO_ROOT"] = str(repo)
    # The bash CLI exports PYTHONPATH=$REPO_ROOT; our scripts.agentic.* live
    # in the real repo root, so prepend it.
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_ROOT}:{existing}" if existing else str(REPO_ROOT)
    return env


def test_complete_appends_runlog_row(tmp_path):
    """``chunks complete`` writes a row to docs/AGENTIC_RUN_LOG.md."""
    repo = _seed_repo(tmp_path)
    chunks = repo / "chunks"
    _make_chunk(chunks, "alpha", issue_number=42)

    env = _build_env(repo, chunks)
    r = subprocess.run(
        [str(CLI), "complete", "alpha", "--pr-url", "https://example.com/pr/9"],
        capture_output=True, text=True, env=env, cwd=str(repo),
    )
    assert r.returncode == 0, f"complete failed: {r.stderr}"

    log_path = repo / "docs" / "AGENTIC_RUN_LOG.md"
    assert log_path.exists(), "expected docs/AGENTIC_RUN_LOG.md to be created"
    text = log_path.read_text()
    assert "| alpha |" in text
    assert "#42" in text
    assert "https://example.com/pr/9" in text


def test_complete_marks_status_merged(tmp_path):
    """``chunks complete`` still updates status.json to merged."""
    repo = _seed_repo(tmp_path)
    chunks = repo / "chunks"
    _make_chunk(chunks, "alpha")
    env = _build_env(repo, chunks)
    r = subprocess.run(
        [str(CLI), "complete", "alpha", "--pr-url", "url"],
        capture_output=True, text=True, env=env, cwd=str(repo),
    )
    assert r.returncode == 0, f"complete failed: {r.stderr}"
    status = json.loads((chunks / "alpha" / "status.json").read_text())
    assert status["stage"] == "merged"
    assert status.get("prUrl") == "url"


def test_complete_handles_missing_test_results(tmp_path):
    """When test-results.json is missing, the row uses defaults (zeros)."""
    repo = _seed_repo(tmp_path)
    chunks = repo / "chunks"
    _make_chunk(chunks, "alpha", issue_number=5)
    env = _build_env(repo, chunks)
    r = subprocess.run(
        [str(CLI), "complete", "alpha"],
        capture_output=True, text=True, env=env, cwd=str(repo),
    )
    assert r.returncode == 0, f"complete failed: {r.stderr}"
    log_path = repo / "docs" / "AGENTIC_RUN_LOG.md"
    text = log_path.read_text()
    # Row exists with the chunk name and zero counts.
    assert "| alpha |" in text
    assert "#5" in text
