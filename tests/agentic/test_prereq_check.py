"""Tests for scripts.agentic.prereq_check."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_returns_no_violations_when_all_symbols_present(tmp_path):
    """Symbols all exist in the search root → no violations."""
    from scripts.agentic.prereq_check import check_prereqs

    src = tmp_path / "src"
    src.mkdir()
    (src / "client.py").write_text("class AlmaAPIClient:\n    def _request(self): pass\n")

    result = check_prereqs(
        prereqs=[
            {"issue": 3, "symbol": "AlmaAPIClient", "where": "src/"},
            {"issue": 4, "symbol": "_request", "where": "src/"},
        ],
        repo_root=tmp_path,
    )
    assert result["all_merged"] is True
    assert result["missing"] == []


def test_returns_violations_when_symbol_missing(tmp_path):
    from scripts.agentic.prereq_check import check_prereqs

    src = tmp_path / "src"
    src.mkdir()
    (src / "client.py").write_text("class AlmaAPIClient: pass\n")

    result = check_prereqs(
        prereqs=[
            {"issue": 4, "symbol": "_request", "where": "src/"},
        ],
        repo_root=tmp_path,
    )
    assert result["all_merged"] is False
    assert len(result["missing"]) == 1
    assert result["missing"][0]["issue"] == 4
    assert "_request" in result["missing"][0]["why"]


def test_empty_prereq_list_is_ok(tmp_path):
    from scripts.agentic.prereq_check import check_prereqs

    result = check_prereqs(prereqs=[], repo_root=tmp_path)
    assert result["all_merged"] is True
    assert result["missing"] == []


def test_grep_fallback_used_when_rg_unavailable(tmp_path, monkeypatch):
    """If rg raises FileNotFoundError, the grep fallback must run and find the symbol."""
    from scripts.agentic import prereq_check

    src = tmp_path / "src"
    src.mkdir()
    (src / "client.py").write_text("class AlmaAPIClient: pass\n")
    # Make tmp_path a git repo so ls-files works
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=tmp_path, check=True,
    )

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "rg":
            raise FileNotFoundError("rg not found")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(prereq_check.subprocess, "run", fake_run)

    result = prereq_check.check_prereqs(
        prereqs=[{"issue": 3, "symbol": "AlmaAPIClient", "where": "src/"}],
        repo_root=tmp_path,
    )
    assert result["all_merged"] is True


def test_real_error_raises(tmp_path, monkeypatch):
    """If both rg and grep return >1, raise RuntimeError loudly."""
    from scripts.agentic import prereq_check

    src = tmp_path / "src"
    src.mkdir()
    (src / "client.py").write_text("anything\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=tmp_path, check=True,
    )

    class FakeResult:
        def __init__(self, rc, err=""):
            self.returncode = rc
            self.stdout = ""
            self.stderr = err

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] in ("rg", "grep"):
            return FakeResult(2, err=f"{cmd[0]} simulated failure")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(prereq_check.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="failed"):
        prereq_check.check_prereqs(
            prereqs=[{"issue": 3, "symbol": "X", "where": "src/"}],
            repo_root=tmp_path,
        )
