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


# ---- R10-shaped regression for #97: breakpoint-wait discipline + STOP-rule note ----

def test_chunk_run_impl_has_explicit_indefinite_wait():
    """Issue #97 — during validation the assistant waited 6 hook firings then
    auto-proceeded with a recommended option. The breakpoint discipline must
    be explicit about waiting indefinitely and ignoring stop-hook nudges."""
    body = (COMMANDS / "chunk-run-impl.md").read_text()
    assert "Wait indefinitely" in body, (
        "breakpoint handler must explicitly say 'Wait indefinitely' so the "
        "assistant never auto-proceeds past a human gate"
    )
    assert "Never auto-proceed" in body, (
        "breakpoint handler must explicitly forbid auto-proceeding"
    )


def test_chunk_run_test_has_explicit_indefinite_wait():
    """Same #97 discipline for the chunk-test slash command."""
    body = (COMMANDS / "chunk-run-test.md").read_text()
    assert "Wait indefinitely" in body
    assert "Never auto-proceed" in body


def test_no_obsolete_no_stop_hook_claim_in_either_body():
    """Issue #97 — the validation run proved a babysitter stop-hook IS
    firing (`Babysitter iteration N/256` messages). The earlier disclaimer
    'no babysitter stop-hook is configured in this repo' was wrong and
    must be removed from both slash-command bodies."""
    impl_body = (COMMANDS / "chunk-run-impl.md").read_text()
    test_body = (COMMANDS / "chunk-run-test.md").read_text()
    obsolete = "no babysitter stop-hook is configured"
    assert obsolete not in impl_body, (
        "chunk-run-impl.md still claims 'no babysitter stop-hook is "
        "configured' — proven false by the 2026-05-05 validation run; "
        "rewrite to acknowledge the hook drives iteration."
    )
    assert obsolete not in test_body, (
        "chunk-run-test.md still claims 'no babysitter stop-hook is "
        "configured' — same as above."
    )
