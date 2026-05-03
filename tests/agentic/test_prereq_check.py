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
