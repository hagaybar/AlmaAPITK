# Regression-test coverage audit — 2026-06-03

Audit of R10 bug-driven regression coverage: do all fixed bugs have a test, and
is the **canonical cumulative suite** (`pytest tests/unit/regressions/`, run by
`scripts/agentic/chunks regression-smoke`) actually complete?

**Verdict: coverage is strong.** Every closed `bug`-labelled issue (#142–#177)
has a `tests/unit/regressions/test_issue_<N>.py`, plus extras. Only **one** fix
had no test anywhere — now backfilled. Three older bugs are tested, but **outside**
the canonical regressions dir, so the release-smoke gate doesn't run them.

## Backfilled this pass

| Bug | What it is | New test |
|---|---|---|
| **#133 / F-003** | `Acquisitions.receive_item` used a bare `except:` around `response.json()` (swallowed `KeyboardInterrupt`/`SystemExit` and masked real errors); narrowed to `except ValueError:`. | `tests/unit/regressions/test_issue_133.py` — pins (1) the XML fallback still works and (2) a non-`ValueError` propagates. **Proven to bite**: fails when the `except` is widened back to bare. |

## Already covered in the canonical suite

`tests/unit/regressions/`: `test_issue_114, 119, 142, 143, 144, 154, 162, 163,
164, 165, 166, 167, 168, 177`, plus `test_bug_found_at_2026-05-27.py`
(a SANDBOX-discovered bug with no issue#) and `test_issue_119_user_note_write_shape.py`.
All 74 pass.

## Gap to decide on: bugs tested OUTSIDE the canonical suite

These bugs **are** tested — but in their domain suites, so `pytest
tests/unit/regressions/` (the release-smoke gate) does **not** exercise them.
They're still caught by the full `pytest` run in CI, so practical risk is low,
but per R10's "the cumulative regression suite is exactly
`pytest tests/unit/regressions/`" they arguably belong there too.

| Bug | Severity / why it matters | Currently tested in |
|---|---|---|
| **#130** — `__version__` hardcoded & drifted | **Caused the 0.4.2 PyPI YANK** — highest-stakes of the three | `tests/test_version.py` + `tests/meta/test_*` |
| **#2** — Python 3.12 `taskName` leaked into every log line | Logging hygiene | `tests/unit/test_formatters.py` |
| **#138** — `switch_environment()` after `close()` should raise a clear error | Client robustness | `tests/unit/client/test_context_manager.py` |

**Recommendation:** mirror at least **#130** into `tests/unit/regressions/`
(a yank-causing bug should be in the release-smoke gate). #2 and #138 are
lower-stakes — mirror them for canon-completeness, or accept full-suite
coverage. Left as a decision rather than done unilaterally, since it touches
the R10 convention you own. (Not urgent; CI's full run covers all three today.)

## Not worth a test

- `fix(client): import sys to fix NameError in __main__ block` (commit
  `0064536`) — CLI `__main__` only; no library-behaviour regression to guard.
- The 0.4.x review's `Users.__init__` "writes `sb_log_file.log` to CWD" concern
  is **already fixed** (no such handler remains in `users.py`; covered by the
  #142 logging overhaul).

## Method

Cross-referenced: closed `bug` issues (GitHub), every `### Fixed` / `### Security`
CHANGELOG section (0.3.1 → 0.4.6 + Unreleased), and `git log --grep=fix`
(80 commits), against `tests/unit/regressions/` and the wider `tests/` tree.
