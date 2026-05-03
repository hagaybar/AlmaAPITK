"""Tests for scripts.agentic.run_log."""
from __future__ import annotations

from pathlib import Path


def test_appends_first_row_to_empty_log(tmp_path):
    from scripts.agentic.run_log import append_chunk_row

    log = tmp_path / "AGENTIC_RUN_LOG.md"
    append_chunk_row(
        log_path=log,
        chunk_name="http-foundation",
        issue_numbers=[3, 4],
        attempts_used={3: 1, 4: 2},
        test_outcomes={"passed": 4, "failed": 0, "skipped": 0},
        time_total_seconds=712,
        pr_url="https://github.com/o/r/pull/100",
    )
    text = log.read_text()
    assert "http-foundation" in text
    assert "#3, #4" in text
    assert "100" in text
    assert text.count("|") >= 8  # markdown table row


def test_preserves_existing_rows(tmp_path):
    from scripts.agentic.run_log import append_chunk_row

    log = tmp_path / "AGENTIC_RUN_LOG.md"
    append_chunk_row(log, "first", [1], {1: 1},
                    {"passed": 1, "failed": 0, "skipped": 0}, 60, "url-1")
    append_chunk_row(log, "second", [2], {2: 1},
                    {"passed": 1, "failed": 0, "skipped": 0}, 60, "url-2")
    text = log.read_text()
    assert "first" in text
    assert "second" in text
    # Header appears exactly once
    assert text.count("| chunk_name |") == 1
