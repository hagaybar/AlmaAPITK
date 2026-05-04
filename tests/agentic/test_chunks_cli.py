"""Tests for scripts/agentic/chunks (Bash CLI)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "agentic" / "chunks"


def run_cli(*args: str, env_overrides: dict | None = None, cwd: Path | None = None):
    import os
    env = os.environ.copy()
    # Strip ALMA_PROD_API_KEY from inherited env so R8 only fires when a test
    # explicitly sets it via env_overrides. Without this, any developer with
    # prod credentials in their shell would trip R8 on every run.
    env.pop("ALMA_PROD_API_KEY", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(CLI), *args],
        capture_output=True, text=True,
        env=env, cwd=str(cwd or REPO_ROOT),
    )


def test_help_shows_subcommands():
    r = run_cli("help")
    assert r.returncode == 0
    out = r.stdout + r.stderr
    for cmd in ["list", "status", "next", "define", "run-impl", "run-test", "abort"]:
        assert cmd in out


def test_list_empty_chunks_dir(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    r = run_cli("list", env_overrides={"CHUNKS_DIR": str(chunks)})
    assert r.returncode == 0
    assert "no active chunks" in r.stdout.lower() or r.stdout.strip() == ""


def test_refuses_when_prod_key_set(tmp_path):
    """R8 — agent must not run with ALMA_PROD_API_KEY in env."""
    r = run_cli(
        "list",
        env_overrides={
            "CHUNKS_DIR": str(tmp_path / "chunks"),
            "ALMA_PROD_API_KEY": "fake-prod-key",
        },
    )
    assert r.returncode != 0
    assert "ALMA_PROD_API_KEY" in (r.stdout + r.stderr)


def test_unknown_subcommand_errors():
    r = run_cli("frobnicate")
    assert r.returncode != 0
