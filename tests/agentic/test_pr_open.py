"""Tests for scripts.agentic.pr_open."""
from __future__ import annotations

from unittest.mock import patch

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

    with pytest.raises(ValueError, match="head must not be 'prod'"):
        build_pr_args(
            head_branch="prod",
            title="x",
            body="x",
        )


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
