# R10 regression tests

This directory is the canonical home for bug-driven regression tests filed
under CLAUDE.md hard rule **R10**. When a real-world bug is discovered (in
production, by an operator, or by a chunk's SANDBOX testing), the failing
test that reproduces it lands here as one file per bug — named after the
GitHub issue (`test_issue_<N>.py`) or, when no issue exists, after the
date the bug surfaced (`test_bug_found_at_<YYYY-MM-DD>.py`). Each test
stays in the suite forever so the bug can never silently regress. The
cumulative regression suite is exactly `pytest tests/unit/regressions/` —
no further intersection logic. Chunks `sandbox-tests/` smokes are a
separate testing pattern (live-API verification) and do not count as the
R10 test.
