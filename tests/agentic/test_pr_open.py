"""Tests for scripts.agentic.pr_open."""
from __future__ import annotations

import subprocess as sp

import pytest


def test_build_pr_args_is_draft_to_main():
    from scripts.agentic.pr_open import build_pr_args

    args = build_pr_args(
        head_branch="chunk/http-foundation",
        title="chunk: HTTP foundation (#3, #4)",
        body="Body content",
    )
    assert "--draft" in args
    assert "--base" in args and args[args.index("--base") + 1] == "main"
    assert "--head" in args and args[args.index("--head") + 1] == "chunk/http-foundation"
    assert "--title" in args
    # Non-empty body lands as a body file or arg
    assert "--body-file" in args or "--body" in args


def test_refuses_base_other_than_main():
    from scripts.agentic.pr_open import build_pr_args

    with pytest.raises(ValueError, match="base must be 'main'"):
        build_pr_args(
            head_branch="chunk/x",
            title="x",
            body="x",
            base="prod",
        )


def test_refuses_head_pointing_at_prod():
    from scripts.agentic.pr_open import build_pr_args

    with pytest.raises(ValueError, match="protected branch"):
        build_pr_args(head_branch="prod", title="x", body="x")


def test_format_body_includes_closes_lines():
    from scripts.agentic.pr_open import format_body

    body = format_body(
        chunk_name="http-foundation",
        issue_numbers=[3, 4],
        impl_summary="Built session pooling and consolidated _request().",
        test_summary="3 SANDBOX tests passed, 0 failed.",
    )
    assert "Closes #3" in body
    assert "Closes #4" in body
    assert "http-foundation" in body
    assert "SANDBOX" in body


def test_refuses_prod_variants():
    from scripts.agentic.pr_open import build_pr_args

    for variant in [
        "Prod",
        "PROD",
        "prod\n",
        " prod ",
        "origin/prod",
        "refs/heads/prod",
    ]:
        with pytest.raises(ValueError):
            build_pr_args(head_branch=variant, title="x", body="x")


def test_refuses_main_as_head():
    from scripts.agentic.pr_open import build_pr_args

    for variant in ["main", "Main", "origin/main", "refs/heads/main"]:
        with pytest.raises(ValueError):
            build_pr_args(head_branch=variant, title="x", body="x")


def test_refuses_empty_or_none_head():
    from scripts.agentic.pr_open import build_pr_args

    for bad in [None, "", "   "]:
        with pytest.raises(ValueError, match="non-empty"):
            build_pr_args(head_branch=bad, title="x", body="x")


def test_refuses_base_variants():
    from scripts.agentic.pr_open import build_pr_args

    # Note: "Main" alone is NOT rejected since _norm("Main") == "main"
    # — this test focuses on non-main bases.
    for variant in ["prod", "PROD", "develop", "  ", "Main\n"]:
        # "Main\n" normalizes to "main" so it would NOT be rejected. We exclude
        # it here by asserting only the truly non-main variants raise.
        if variant.strip().lower() == "main":
            continue
        with pytest.raises(ValueError, match="base must be 'main'"):
            build_pr_args(head_branch="chunk/x", title="x", body="x", base=variant)


def test_open_pr_creates_tempfile_and_calls_gh(tmp_path, monkeypatch):
    """open_pr writes tempfile, calls gh, cleans up."""
    from scripts.agentic import pr_open

    captured_args = []

    def fake_run(args, **kwargs):
        captured_args.append(args)
        # Verify body_file arg was passed and the file exists at call time
        assert "--body-file" in args, f"missing --body-file: {args}"
        body_file_path = args[args.index("--body-file") + 1]
        from pathlib import Path

        assert Path(body_file_path).exists(), "body file should exist during gh call"

        class R:
            stdout = "https://github.com/o/r/pull/42\n"

        return R()

    monkeypatch.setattr(pr_open.subprocess, "run", fake_run)
    url = pr_open.open_pr(
        head_branch="chunk/test",
        chunk_name="test",
        issue_numbers=[1, 2],
        impl_summary="x",
        test_summary="y",
        repo_root=tmp_path,
    )
    assert url == "https://github.com/o/r/pull/42"
    assert len(captured_args) == 1
    args = captured_args[0]
    assert "--draft" in args
    assert "--base" in args and args[args.index("--base") + 1] == "main"
    # After call, tempfile should be cleaned up (no .md files left in tmp_path)
    leftover = list(tmp_path.glob("*.md"))
    assert leftover == [], f"tempfile not cleaned: {leftover}"


def test_open_pr_cleans_tempfile_on_subprocess_failure(tmp_path, monkeypatch):
    """Even if gh fails, the tempfile must be removed."""
    from scripts.agentic import pr_open

    def fake_run(args, **kwargs):
        raise sp.CalledProcessError(1, args, stderr="gh failed")

    monkeypatch.setattr(pr_open.subprocess, "run", fake_run)
    with pytest.raises(sp.CalledProcessError):
        pr_open.open_pr(
            head_branch="chunk/test",
            chunk_name="test",
            issue_numbers=[1],
            impl_summary="x",
            test_summary="y",
            repo_root=tmp_path,
        )
    leftover = list(tmp_path.glob("*.md"))
    assert leftover == [], f"tempfile not cleaned on failure: {leftover}"
