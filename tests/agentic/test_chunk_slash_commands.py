"""Tests for project-level slash commands that drive chunk runs."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS = REPO_ROOT / ".claude" / "commands"


def test_chunk_run_impl_exists():
    p = COMMANDS / "chunk-run-impl.md"
    assert p.exists(), f"missing slash-command file: {p}"


def test_chunk_run_impl_body_has_required_markers():
    body = (COMMANDS / "chunk-run-impl.md").read_text()
    # Argument substitution
    assert "$ARGUMENTS" in body, "slash command must use $ARGUMENTS"
    # Bash setup
    assert "scripts/agentic/chunks run-impl" in body
    # Iterate-loop driving
    assert "babysitter run:iterate" in body
    assert "task:post" in body
    # Subagent isolation for kind:agent effects
    assert "Agent tool" in body
    # Resume protocol
    assert "implRunId" in body
    # R8 reminder
    assert "ALMA_PROD_API_KEY" in body


def test_chunk_run_test_exists():
    p = COMMANDS / "chunk-run-test.md"
    assert p.exists(), f"missing slash-command file: {p}"


def test_chunk_run_test_body_has_required_markers():
    body = (COMMANDS / "chunk-run-test.md").read_text()
    assert "$ARGUMENTS" in body
    assert "scripts/agentic/chunks run-test" in body
    assert "babysitter run:iterate" in body
    assert "task:post" in body
    assert "Agent tool" in body
    assert "testRunId" in body
    assert "ALMA_PROD_API_KEY" in body
    # The fixture interview is the headline breakpoint of run-test
    assert "fixture" in body.lower()
