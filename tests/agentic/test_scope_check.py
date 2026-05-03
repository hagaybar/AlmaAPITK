"""Tests for scripts.agentic.scope_check (enforces spec R7)."""
from __future__ import annotations


def test_passes_when_diff_is_subset_of_files_to_touch():
    from scripts.agentic.scope_check import check_scope

    diff_files = ["src/almaapitk/domains/users.py"]
    files_to_touch = [
        "src/almaapitk/domains/users.py",
        "tests/unit/domains/test_users.py",
    ]
    result = check_scope(diff_files=diff_files, files_to_touch=files_to_touch)
    assert result["pass"] is True
    assert result["out_of_scope"] == []


def test_fails_when_diff_includes_off_scope_file():
    from scripts.agentic.scope_check import check_scope

    diff_files = [
        "src/almaapitk/domains/users.py",
        "src/almaapitk/client/AlmaAPIClient.py",  # not in scope
    ]
    files_to_touch = ["src/almaapitk/domains/users.py"]
    result = check_scope(diff_files=diff_files, files_to_touch=files_to_touch)
    assert result["pass"] is False
    assert "src/almaapitk/client/AlmaAPIClient.py" in result["out_of_scope"]


def test_passes_when_diff_is_empty():
    from scripts.agentic.scope_check import check_scope

    result = check_scope(diff_files=[], files_to_touch=["any"])
    assert result["pass"] is True
