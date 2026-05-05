"""Integration tests: chunks CLI must persist runId fields to status.json."""
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
    # Bootstrap status.json via init_status helper
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.agentic.chunk_status import init_status
    init_status(chunk_dir, chunk_name=name, issues=[issue_number])
    return chunk_dir


def _stub_babysitter(bin_dir: Path, run_id: str) -> Path:
    """Drop a fake `babysitter` script that prints {"runId": "<id>"} for any args."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "babysitter"
    stub.write_text(
        f'#!/usr/bin/env bash\n'
        f'echo \'{{"runId": "{run_id}"}}\'\n'
    )
    stub.chmod(0o755)
    return stub


def _git_repo(repo_path: Path, branch: str) -> None:
    """Initialize a git repo and create the chunk integration branch."""
    subprocess.run(["git", "init", "-q"], cwd=str(repo_path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo_path), check=True)
    (repo_path / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=str(repo_path), check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=str(repo_path), check=True)
    subprocess.run(["git", "checkout", "-q", "-b", branch], cwd=str(repo_path), check=True)


def test_run_impl_persists_implRunId(tmp_path):
    """run-impl must capture the runId from babysitter and write it to status.json."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_repo(repo, "chunk/test-chunk")
    chunks = repo / "chunks"
    _make_chunk(chunks, "test-chunk")
    _stub_babysitter(tmp_path / "bin", "test-run-12345")

    env = os.environ.copy()
    env.pop("ALMA_PROD_API_KEY", None)
    env["CHUNKS_DIR"] = str(chunks)
    env["REPO_ROOT"] = str(repo)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    # The bash CLI exports PYTHONPATH=$REPO_ROOT, but REPO_ROOT is the tmp dir.
    # We must ensure the real repo root is on PYTHONPATH so scripts.agentic.* is found.
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_ROOT}:{existing_pythonpath}" if existing_pythonpath else str(REPO_ROOT)

    r = subprocess.run(
        [str(CLI), "run-impl", "test-chunk"],
        capture_output=True, text=True, env=env, cwd=str(repo),
    )
    assert r.returncode == 0, f"chunks run-impl failed: {r.stderr}"
    status = json.loads((chunks / "test-chunk" / "status.json").read_text())
    assert status.get("implRunId") == "test-run-12345", (
        f"expected implRunId=test-run-12345 in status.json, got {status}"
    )


def test_run_test_persists_testRunId(tmp_path):
    """run-test must capture the runId from babysitter and write it to status.json."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_repo(repo, "chunk/test-chunk")
    chunks = repo / "chunks"
    _make_chunk(chunks, "test-chunk")
    # run-test peeks at test-recommendation.json and test-data.json to decide
    # headless mode. Provide neither so it picks the interactive path.
    _stub_babysitter(tmp_path / "bin", "test-run-67890")

    env = os.environ.copy()
    env.pop("ALMA_PROD_API_KEY", None)
    env["CHUNKS_DIR"] = str(chunks)
    env["REPO_ROOT"] = str(repo)
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    # The bash CLI exports PYTHONPATH=$REPO_ROOT, but REPO_ROOT is the tmp dir.
    # We must ensure the real repo root is on PYTHONPATH so scripts.agentic.* is found.
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_ROOT}:{existing_pythonpath}" if existing_pythonpath else str(REPO_ROOT)

    r = subprocess.run(
        [str(CLI), "run-test", "test-chunk"],
        capture_output=True, text=True, env=env, cwd=str(repo),
    )
    assert r.returncode == 0, f"chunks run-test failed: {r.stderr}"
    status = json.loads((chunks / "test-chunk" / "status.json").read_text())
    assert status.get("testRunId") == "test-run-67890", (
        f"expected testRunId=test-run-67890 in status.json, got {status}"
    )
