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


def test_parse_rejects_missing_structured_headers():
    from scripts.agentic.issue_parser import parse_issue

    raw = json.loads((FIXTURES / "issue-998-bad.json").read_text())
    with pytest.raises(ValueError, match="Priority/Benefit"):
        parse_issue(raw)


def test_infer_swagger_domains_from_files_to_touch():
    """Files-to-touch under src/almaapitk/domains/<file>.py is the strongest signal."""
    from scripts.agentic.issue_parser import infer_swagger_domains

    # users.py → 'users' (alias same)
    assert infer_swagger_domains({
        "files_to_touch": ["src/almaapitk/domains/users.py", "tests/unit/domains/test_users.py"],
        "endpoints": [],
        "domain": "",
    }) == ["users"]

    # acquisition.py → 'acq' (alias differs)
    assert infer_swagger_domains({
        "files_to_touch": ["src/almaapitk/domains/acquisition.py"],
        "endpoints": [],
        "domain": "",
    }) == ["acq"]

    # admin.py → 'conf' (alias differs)
    assert infer_swagger_domains({
        "files_to_touch": ["src/almaapitk/domains/admin.py"],
        "endpoints": [],
        "domain": "",
    }) == ["conf"]


def test_infer_swagger_domains_from_endpoints_when_no_files():
    """Architecture issues (#1-#21) have no Files-to-touch; fall back to endpoints."""
    from scripts.agentic.issue_parser import infer_swagger_domains

    assert infer_swagger_domains({
        "files_to_touch": [],
        "endpoints": ["GET /almaws/v1/bibs/{mms_id}", "POST /almaws/v1/bibs"],
        "domain": "",
    }) == ["bibs"]


def test_infer_swagger_domains_dedups_and_sorts():
    """Multiple signals pointing at multiple domains return sorted, deduped."""
    from scripts.agentic.issue_parser import infer_swagger_domains

    assert infer_swagger_domains({
        "files_to_touch": [
            "src/almaapitk/domains/users.py",
            "src/almaapitk/domains/bibs.py",
            "src/almaapitk/domains/users.py",  # dup
        ],
        "endpoints": ["GET /almaws/v1/bibs/{mms_id}"],
        "domain": "",
    }) == ["bibs", "users"]


def test_infer_swagger_domains_returns_empty_when_no_signal():
    """No domain-bearing inputs → empty list. The chunk-impl hook then
    skips the swagger fetch rather than guess."""
    from scripts.agentic.issue_parser import infer_swagger_domains

    assert infer_swagger_domains({
        "files_to_touch": ["docs/CHANGELOG.md"],
        "endpoints": [],
        "domain": "Architecture",
    }) == []


def test_parse_rejects_missing_top_level_keys():
    from scripts.agentic.issue_parser import parse_issue

    with pytest.raises(ValueError, match="missing required key"):
        parse_issue({"number": 1, "title": "no body"})


def test_cli_round_trip(tmp_path):
    """Run the parser as a CLI: stdin → stdout."""
    import subprocess

    fixture = (FIXTURES / "issue-999.json").read_text()
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.issue_parser"],
        input=fixture,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["number"] == 999
    assert parsed["domain"] == "Users"


def test_parse_real_issue_67_format():
    """Real issue #67 uses bold markdown headers and structured prereq subsections."""
    from scripts.agentic.issue_parser import parse_issue

    raw = json.loads((FIXTURES / "issue-real-67.json").read_text())
    parsed = parse_issue(raw)

    assert parsed["number"] == 67
    assert parsed["domain"] == "Electronic"
    assert parsed["priority"] == "medium"
    assert parsed["effort"] == "M" or parsed["effort"] == "S"  # accept either; just must not be empty
    # Real issue prereqs: hard #66 (Electronic bootstrap), recommended set with #3, #4 etc.
    assert 66 in parsed["hard_prereqs"], f"expected #66 in hard prereqs; got {parsed['hard_prereqs']}"
    assert 3 in parsed["soft_prereqs"], f"expected #3 in soft prereqs; got {parsed['soft_prereqs']}"
    # ACs are bare-bullet; expect non-empty
    assert len(parsed["acceptance_criteria"]) >= 3, f"expected >= 3 ACs; got {parsed['acceptance_criteria']}"
    # Endpoints: backtick-quoted in bullets like - `GET /...` — confirm at least one is captured
    assert any("/almaws/" in e for e in parsed["endpoints"]), f"endpoints: {parsed['endpoints']}"


def test_synthetic_fixture_still_works():
    """Phase 1 baseline must still pass."""
    from scripts.agentic.issue_parser import parse_issue

    raw = json.loads((FIXTURES / "issue-999.json").read_text())
    parsed = parse_issue(raw)
    assert parsed["domain"] == "Users"
    assert parsed["hard_prereqs"] == [3]
    assert parsed["soft_prereqs"] == [14]
    assert len(parsed["acceptance_criteria"]) == 2


def test_parse_real_issue_3_arch_format():
    """Architecture issue #3 has Complexity/Benefit aliases and no Domain header."""
    from scripts.agentic.issue_parser import parse_issue

    raw = json.loads((FIXTURES / "issue-real-3.json").read_text())
    parsed = parse_issue(raw)

    assert parsed["number"] == 3
    # Architecture issues default Domain to "Architecture" since they have none
    assert parsed["domain"] == "Architecture"
    # **Benefit:** High → priority="high"
    assert parsed["priority"] == "high"
    # **Complexity:** S (≤½ day) → effort="S"
    assert parsed["effort"] == "S"
