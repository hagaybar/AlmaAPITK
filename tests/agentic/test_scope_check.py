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


def test_cli_pass_via_stdin():
    """CLI: diff_files passed inline → exit 0, JSON pass=true."""
    import json, subprocess
    payload = json.dumps({
        "diff_files": ["a.py"],
        "files_to_touch": ["a.py"],
    })
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.scope_check"],
        input=payload, capture_output=True, text=True,
    )
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["pass"] is True


def test_cli_fail_via_stdin():
    """CLI: out-of-scope file → exit 2, JSON pass=false."""
    import json, subprocess
    payload = json.dumps({
        "diff_files": ["b.py"],
        "files_to_touch": ["a.py"],
    })
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.scope_check"],
        input=payload, capture_output=True, text=True,
    )
    assert result.returncode == 2
    out = json.loads(result.stdout)
    assert out["pass"] is False
    assert "b.py" in out["out_of_scope"]


def test_cli_bad_payload_returns_structured_error():
    """CLI: missing files_to_touch → exit 3, JSON error=bad_payload."""
    import json, subprocess
    payload = json.dumps({"diff_files": []})  # missing files_to_touch
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.scope_check"],
        input=payload, capture_output=True, text=True,
    )
    assert result.returncode == 3
    out = json.loads(result.stdout)
    assert out["pass"] is False
    assert out["error"] == "bad_payload"
