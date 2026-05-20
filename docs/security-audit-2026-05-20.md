# Security audit findings — 2026-05-20

**Issue:** #154 (Security audit: sensitive data leaks to terminal or files)
**Scope:** `src/`, `scripts/`, `tests/`, `docs/`, `config/`. Dependency
behavior and git-history rewrites are out of scope per the issue.
**Auditor:** Claude Code session, 2026-05-20.
**Method:** Worked through the checklist in `docs/security-audit-issue.md`
sections 1–7. No code changes were applied during the audit per the
issue's instruction ("produce the findings report first").

## Executive summary

The library's HTTP path is clean: `AlmaAPIClient._request` routes
request/response logging through the structured `alma_logging` layer,
and `redact_sensitive_data()` walks dicts recursively, redacting any
field whose key matches `apikey | api_key | password | token | secret |
authorization` (case-insensitive). The companion text-formatter leak
that was found earlier (issue #142) has a regression test in place
(`tests/unit/regressions/test_issue_142.py`), and the fix still holds.

The remaining surface falls into four buckets:

| Bucket | Risk | Count |
|---|---|---|
| Real leak in a tracked file | HIGH | 1 |
| f-string interpolation of `response.text` into log messages (bypasses redactor) | MEDIUM | 2 |
| `__main__` demo blocks under `src/almaapitk/` that write PII to disk or talk to stdout | MEDIUM-LOW | 1 PII write, 4 demo `print()` clusters |
| Cosmetic / informational (`print()` in CLI scripts; safe MMS IDs in doc fixtures) | LOW | several |

**Recommended order to address:**
1. F-001 (real partial-key leak in `scripts/investigations/alma_client_repro.py`)
2. F-002 / F-003 (`response.text` in f-string log messages)
3. F-004 (gitignore the `user_set_*.txt` artifact produced by admin.py's demo block)
4. F-005..F-008 (lower-priority cleanups; can be deferred or batched into a
   `print()`-removal sweep for issue #14)

---

## Findings

### F-001 — Partial API key printed to stdout — HIGH

- **File:** `scripts/investigations/alma_client_repro.py`
- **Lines:** 29, 33
- **What:**
  ```python
  if sb_key:
      print(f"  Partial key: {sb_key[:10]}...")
  ...
  if prod_key:
      print(f"  Partial key: {prod_key[:10]}...")
  ```
- **Why sensitive:** Alma API keys are not long. The first 10
  characters are a substantial fraction of the secret and are quoted
  into stdout, which gets snapshotted by Claude Code / Codex history
  (`~/.claude/file-history/`, `~/.codex/shell_snapshots/`), terminal
  scrollback, and tmux/screen logs. Exactly the leak vector the issue
  was filed against.
- **Severity:** Real leak. The script is described as a debug
  reproducer and is the kind of thing an operator runs ad-hoc when
  diagnosing client setup, so it does fire.
- **Proposed fix:** Replace value-bearing output with a length/hash
  digest:
  ```python
  print(f"ALMA_SB_API_KEY: {'set, len=' + str(len(sb_key)) if sb_key else 'NOT SET'}")
  ```
  Or, if a fingerprint is needed:
  `f"  sha256[0:12]={hashlib.sha256(sb_key.encode()).hexdigest()[:12]}"`.
  Either avoids leaking any byte of the actual key.

### F-002 — `response.text` interpolated into error log message — MEDIUM

- **File:** `src/almaapitk/client/AlmaAPIClient.py`
- **Line:** 1115 (inside `test_connection`)
- **What:**
  ```python
  self.logger.error(
      f"Connection failed: {response.status_code} - {response.text}"
  )
  ```
- **Why sensitive:** `redact_sensitive_data()` walks structured
  `extra=` kwargs but does NOT touch the `message` string. Anything
  Alma returns in the response body — including, in some error
  responses, the failing URL with query string — is written verbatim
  into the log message and never redacted.
- **Severity:** Medium. The current request flow on `test_connection`
  sends only a `Authorization: apikey ...` header (key not in the
  URL), so the leak surface today is bounded to whatever Alma chooses
  to put in the body of a 4xx/5xx. The pattern is the dangerous one,
  though — any future code that ever sends a credential in a URL or
  body and hits this path will leak it.
- **Proposed fix:** Move the body to a structured kwarg so the
  redactor can scrub it, and truncate by default:
  ```python
  self.logger.error(
      "Connection failed",
      status_code=response.status_code,
      body_preview=response.text[:200],
  )
  ```
  Bonus: this aligns with the structured-logging style the rest of the
  codebase uses.

### F-003 — `str(exception)` in log message can carry URL/host detail — MEDIUM

- **File:** `src/almaapitk/client/AlmaAPIClient.py`
- **Line:** 1119
- **What:**
  ```python
  self.logger.exception(f"Connection error: {e}")
  ```
  And the equivalent `self.logger.exception(f"... {str(e)}")` pattern
  appears throughout `src/almaapitk/domains/acquisition.py` (lines
  857, 898, 959, 1007, 1117, 1172, 1391, 1479, 1555, 1602, …).
- **Why sensitive:** `requests.exceptions.*` `__str__` includes the
  request URL on many failure paths. Alma URLs do not embed
  credentials, so this is **not** an active leak today. But the
  pattern of stringifying the exception into the message defeats the
  redactor, so any future exception class whose `__str__` returns a
  credential-bearing string would leak.
- **Severity:** Medium (latent). Not a present-day data exposure;
  noted because of the systemic pattern.
- **Proposed fix:** Use the structured-exception path instead:
  ```python
  self.logger.exception("Connection error", error=str(e))
  ```
  Or rely on `logger.exception()`'s built-in `exc_info` capture and
  drop the `{e}` interpolation from the message — the traceback
  already carries the exception text.

### F-004 — Demo block writes user PII to an un-gitignored file — MEDIUM-LOW

- **File:** `src/almaapitk/domains/admin.py`
- **Lines:** 1044–1116 (inside `if __name__ == "__main__":`, line 986)
- **What:** Interactive demo asks for a user-set ID, then writes
  `user_set_<id>_<timestamp>.txt` containing `user_id`, `first_name`,
  `last_name`, `full_name`, `status` for every user in the set.
- **Why sensitive:** Real user PII. The file name pattern
  (`user_set_*.txt`) is not in `.gitignore`. A demo run leaves a file
  behind that could be accidentally `git add`-ed.
- **Severity:** Medium-low. The block requires interactive
  confirmation (`(y/n)` prompt at line 1031) before writing, so it
  doesn't fire in CI or library use. Worst case is an operator
  running the demo, then `git add .` later. Note also: the surrounding
  `__main__` block is demo code that arguably should not ship with
  the library at all.
- **Proposed fixes (pick one):**
  - **Preferred:** delete the `__main__` block from `admin.py`. Demo
    code belongs in `scripts/` or in a notebook, not in importable
    library source.
  - **Lower-effort:** add `user_set_*.txt` to `.gitignore`.
  - **Defensive add-on:** the demo could write into `logs/` (already
    gitignored) instead of CWD.

### F-005 — `print()` clusters in `src/almaapitk/` `__main__` demo blocks — LOW

- **Files / line ranges:**
  - `src/almaapitk/utils/tsv_generator.py:413–452` (inside `__main__`
    guard at 398)
  - `src/almaapitk/domains/acquisition.py:2402–2459` (inside
    `__main__` guard at 2382)
  - `src/almaapitk/client/AlmaAPIClient.py:1292–1309` (inside
    `__main__` guard at 1272)
  - `src/almaapitk/domains/admin.py:1021..` (inside `__main__` guard
    at 986; broader than F-004's file-write scope)
- **What:** Demo / smoke-test scaffolding that uses `print()` to talk
  to the operator. No credentials are interpolated — outputs are
  invoice IDs, library names, status messages, and prompts to set the
  `ALMA_SB_API_KEY` env var (placeholder text only, never the value).
- **Severity:** Low. These are CLI demos for operators, not library
  code paths. They are guarded by `if __name__ == "__main__":` and
  never run when the package is imported. Project policy (issue #14 +
  CLAUDE.md) is to "no print() in library code"; treating the
  `__main__` blocks as code that ships with the package means they
  technically violate the policy, but they don't leak.
- **Proposed fix:** Either accept these as approved demos (and add a
  one-line comment to that effect), or — better — move them into
  `scripts/demos/` so the library source is print-free. Bundle into
  the `print()`-removal sweep tracked by issue #14.

### F-006 — `traceback.print_exc()` in investigation script — LOW

- **File:** `scripts/investigations/extract_items_repro.py`
- **Line:** 125
- **What:** Broad `except Exception` → `traceback.print_exc()` →
  `sys.exit(1)`.
- **Why sensitive:** Tracebacks from `requests.*` exceptions can
  include the failing URL. Alma URLs don't embed credentials, so this
  is informational only.
- **Severity:** Low.
- **Proposed fix:** None required for security. Could be tightened to
  `logger.exception(...)` for consistency with the rest of the
  codebase.

### F-007 — `print()` in operator scripts under `scripts/` — LOW

- **Files:** `scripts/update_prereqs.py`,
  `scripts/post_publish/02_get_bib.py`, `scripts/error_codes/*.py`,
  `scripts/agentic/*.py`.
- **What:** Status reporting, structured JSON output to stdout
  (`json.dump(..., sys.stdout, ...)`). These are the standard
  "operator CLI tool talking to a human or to a pipeline" pattern.
- **Why sensitive:** Inputs to these scripts are GitHub issue payloads
  and configuration files, not credential material.
- **Severity:** Low / not in scope. These are operator tools, not
  library code.
- **Proposed fix:** None.

### F-008 — Real-looking MMS IDs in `docs/examples/*.json` — INFORMATIONAL

- **Files:** `docs/examples/lending_request_example.json`,
  `docs/examples/doi_enriched_request_example.json`,
  `docs/examples/pmid_enriched_request_example.json`.
- **What:** Example JSON includes Alma MMS IDs (e.g.,
  `990022394090204146`). No emails, no `user_primary_id`, no auth
  headers.
- **Why sensitive:** MMS IDs are bibliographic record identifiers
  that resolve to catalog entries — these are typically public via
  the institution's discovery layer. R9 in `CLAUDE.md` flags
  operator-supplied identifiers; bib MMS IDs in catalog records do
  not fall into that category, though using fully synthetic IDs
  (e.g., `99XXXXXXXXX0204146`) would be a small additional hygiene
  win.
- **Severity:** Informational. No proposed fix unless we choose to
  enforce "synthetic IDs everywhere" as a policy.

---

## Negative findings (checked, nothing to report)

- **`__repr__` / `__str__` methods in `src/`:** none defined. The
  `AlmaResponse` / `AlmaAPIError` classes inherit the defaults, which
  do not expose secret fields.
- **`response.headers` logged anywhere:** `log_response` only logs
  `status_code` and `duration_ms`. No response headers are emitted.
- **Test fixtures:** all use synthetic strings (`'test-sandbox-key'`,
  `'test-prod-key'`). No real keys in `tests/`.
- **`.env` files in repo:** none. `.env`, `.env.*`, and `*.env` are
  gitignored at lines 97–99.
- **`chunks/*/test-data.json`:** gitignored at line 206; CLAUDE.md R9
  explicitly forbids inlined identifiers in these files.
- **`logs/`:** gitignored at lines 66–67 and 168.
- **`docs/AGENTIC_RUN_LOG.md` and similar markdown:** spot-checked for
  identifiers; clean.
- **JSON dumps to stdout in scripts:** the data being dumped is GitHub
  issue payloads / agentic-pipeline state, not credential material.
- **`pprint` / `rich.print`:** zero occurrences.

## Git history

Per the issue's scope note, git-history rewrites are out of scope. The
audit did not search history for ever-committed credentials. If the
project wants that done, it should be tracked as a separate task
(BFG repo-cleaner or `git filter-repo` is the standard tooling).

## Patterns worth remembering

These are the systemic things the audit surfaced — worth folding into
future code review and CLAUDE.md / `python-dev-expert` guidance:

1. **`logger.error(f"... {response.text}")` defeats redaction.** The
   redactor only walks structured `extra=` kwargs. Anything formatted
   into the `message` string bypasses it. Rule of thumb: response
   bodies and exception strings belong as `body=`, `error=`, or
   similar kwargs, not interpolated into the message.
2. **`logger.exception(f"foo: {e}")` is doubly redundant.**
   `logger.exception` already attaches the full traceback via
   `exc_info`. The `f"... {e}"` interpolation adds nothing the
   traceback doesn't already carry, and it opens the redaction-bypass
   above.
3. **The redactor matches credential *field names* only, not PII.**
   `email`, `first_name`, `user_primary_id`, etc. pass through
   untouched. If we want PII redaction (a different threat model),
   that needs an explicit pattern set or an allow-list approach.
4. **`__main__` demo blocks living inside `src/`** make it harder to
   reason about "what does the library do" vs. "what does the demo
   do." Worth deciding whether to keep them or move to `scripts/demos/`
   uniformly; consistency would help both audits and the issue #14
   `print()`-removal effort.
5. **Partial-key prints are not safe.** Even 10 leading characters of
   an API key is too much. The hash-fingerprint pattern (`sha256[:12]`)
   exists in CLAUDE.md's secret-handling rules — adopt it consistently.

## Suggested next step

This report satisfies the audit phase. Decisions about which fixes to
apply (and when) should be made before any code changes land. My
recommendation is:

- **Apply now:** F-001 (real leak, one-line fix).
- **Apply soon (one PR):** F-002 + F-003 (structured-logging migration
  in the few code paths that interpolate response/exception into log
  messages).
- **Track on issue #14:** F-005 (demo `print()` cleanup).
- **Track separately:** F-004 (decide between deleting the
  `admin.py:986+` demo block or gitignoring its artifact).
- **Close as informational:** F-006, F-007, F-008.

Once the user picks the cut, I'll open a dedicated PR per fix bucket
and update issue #154 with the summary comment the acceptance criteria
require.

---

## Resolution (applied 2026-05-20)

The user approved fixing F-001..F-004 and dismissing F-005..F-008.
All four were addressed in a single change.

**Additional bug surfaced while writing the F-003 regression test:**
`AlmaLogger` had no `exception()` method, so every
`self.logger.exception(...)` call in the codebase (~21 sites in
`acquisition.py`, plus `AlmaAPIClient.test_connection`, plus
`tsv_generator.py`) was an `AttributeError` waiting to fire. Those
error-handler branches were not just leaky — they were structurally
broken. Fixed by adding `AlmaLogger.exception(message, **kwargs)`
that mirrors stdlib `logging.Logger.exception`: ERROR level,
`exc_info=True` for the traceback, redactable kwargs in `extra`.

| Finding | Files changed | Approach |
|---|---|---|
| F-001 | `scripts/investigations/alma_client_repro.py` | Replaced `sb_key[:10]` slice prints with length-only status. |
| F-002 | `src/almaapitk/client/AlmaAPIClient.py:test_connection` error path | Pass `status_code` and `body_preview` as structured kwargs so the redactor can scrub them. |
| F-003 | `src/almaapitk/alma_logging/logger.py`, `src/almaapitk/client/AlmaAPIClient.py`, `src/almaapitk/utils/tsv_generator.py`, `src/almaapitk/domains/acquisition.py` (~20 sites) | Added `AlmaLogger.exception()`; rewrote every `self.logger.exception(f"...{e}")` to use a clean message + structured kwargs. `logger.log_error()` also de-leaked. |
| F-004 | `src/almaapitk/domains/admin.py` | Deleted the 174-line `__main__` demo block (lines 985–1159) and the now-unused `datetime` / `Users` imports. |

**Regression tests:** `tests/unit/regressions/test_issue_154.py` pins
all three behaviors. Test suite: 814 unit tests pass, smoke import
passes, logging tests pass.

**Patterns confirmed for future code review:**
- Never `print()` partial credentials. Use length / sha256[:12] only.
- Never interpolate `response.text` or `str(exception)` into a log
  message string. Pass them as structured kwargs so the recursive
  redactor can scrub credential-shaped fields.
- `logger.exception()` captures the traceback automatically via
  `exc_info=True` — the `{e}` interpolation is redundant and
  bypasses redaction.
- Demo / interactive blocks belong in `scripts/`, not in importable
  library source under `src/almaapitk/`.
