"""Tests for scripts.agentic.guardrails (Phase 1 of the guardrails registry)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_load_guardrails_returns_parsed_dict(tmp_path: Path):
    from scripts.agentic.guardrails import load_guardrails

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({
        "version": 1,
        "enforced": {"deny_paths": [".github/"]},
        "instructed": {"implement": [], "critique": []},
    }))

    data = load_guardrails(registry)
    assert data["version"] == 1
    assert data["enforced"]["deny_paths"] == [".github/"]


def test_load_guardrails_rejects_missing_version(tmp_path: Path):
    from scripts.agentic.guardrails import GuardrailsSchemaError, load_guardrails

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({"enforced": {"deny_paths": []}, "instructed": {}}))

    with pytest.raises(GuardrailsSchemaError) as exc_info:
        load_guardrails(registry)
    assert "version" in str(exc_info.value)


def test_load_guardrails_rejects_unknown_version(tmp_path: Path):
    from scripts.agentic.guardrails import GuardrailsSchemaError, load_guardrails

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({
        "version": 99,
        "enforced": {"deny_paths": []},
        "instructed": {},
    }))

    with pytest.raises(GuardrailsSchemaError) as exc_info:
        load_guardrails(registry)
    assert "version" in str(exc_info.value)


def test_match_deny_paths_returns_empty_when_no_violations():
    from scripts.agentic.guardrails import match_deny_paths

    diff_files = [
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
        "CLAUDE.md",
    ]
    deny_paths = [".github/", "secrets/"]
    violations = match_deny_paths(diff_files, deny_paths)
    assert violations == []


def test_match_deny_paths_flags_prefix_match():
    from scripts.agentic.guardrails import match_deny_paths

    diff_files = [
        "src/almaapitk/domains/configuration.py",
        ".github/workflows/release.yml",
        "secrets/api-keys.env",
    ]
    deny_paths = [".github/", "secrets/"]
    violations = match_deny_paths(diff_files, deny_paths)
    assert sorted(violations) == [".github/workflows/release.yml", "secrets/api-keys.env"]


def test_match_deny_paths_does_not_match_partial_segments():
    """Deny-path '.github/' must NOT match '.github_old/something' or 'foo.github/x'."""
    from scripts.agentic.guardrails import match_deny_paths

    diff_files = [
        ".github_old/notes.md",
        "foo.github/bar.py",
    ]
    deny_paths = [".github/"]
    violations = match_deny_paths(diff_files, deny_paths)
    assert violations == []


def test_match_deny_paths_handles_empty_inputs():
    from scripts.agentic.guardrails import match_deny_paths

    assert match_deny_paths([], [".github/"]) == []
    assert match_deny_paths(["src/foo.py"], []) == []


def test_cli_pass_via_stdin(tmp_path: Path):
    """CLI: deny-paths receives diff_files via stdin, exits 0 when nothing matches."""
    import subprocess

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({
        "version": 1,
        "enforced": {"deny_paths": [".github/", "secrets/"]},
        "instructed": {"implement": [], "critique": []},
    }))

    payload = json.dumps({"diff_files": ["src/foo.py", "tests/test_foo.py"]})
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.guardrails", "deny-paths",
         "--registry", str(registry)],
        input=payload, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["pass"] is True
    assert out["violations"] == []


def test_cli_fail_via_stdin(tmp_path: Path):
    """CLI: deny-paths exits 2 with violations listed when any path matches."""
    import subprocess

    registry = tmp_path / "guardrails.json"
    registry.write_text(json.dumps({
        "version": 1,
        "enforced": {"deny_paths": [".github/"]},
        "instructed": {"implement": [], "critique": []},
    }))

    payload = json.dumps({"diff_files": ["src/foo.py", ".github/workflows/release.yml"]})
    result = subprocess.run(
        ["python", "-m", "scripts.agentic.guardrails", "deny-paths",
         "--registry", str(registry)],
        input=payload, capture_output=True, text=True,
    )
    assert result.returncode == 2
    out = json.loads(result.stdout)
    assert out["pass"] is False
    assert ".github/workflows/release.yml" in out["violations"]
