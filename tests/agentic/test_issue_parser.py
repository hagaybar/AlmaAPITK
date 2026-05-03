"""Tests for scripts.agentic.issue_parser."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_well_formed_issue_999():
    from scripts.agentic.issue_parser import parse_issue

    raw = json.loads((FIXTURES / "issue-999.json").read_text())
    parsed = parse_issue(raw)

    assert parsed["number"] == 999
    assert parsed["title"] == "Synthetic test fixture: Users: get_user (smoke)"
    assert parsed["domain"] == "Users"
    assert parsed["priority"] == "medium"
    assert parsed["effort"] == "S"
    assert parsed["endpoints"] == ["GET /almaws/v1/users/{user_id}"]
    assert "src/almaapitk/domains/users.py" in parsed["files_to_touch"]
    assert "tests/unit/domains/test_users.py" in parsed["files_to_touch"]
    assert parsed["hard_prereqs"] == [3]
    assert parsed["soft_prereqs"] == [14]
    assert len(parsed["acceptance_criteria"]) == 2
    assert "AC-1" in parsed["acceptance_criteria"][0]
    assert parsed["labels"] == ["api-coverage", "priority:medium"]
