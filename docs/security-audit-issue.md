# Security audit: sensitive data leaks to terminal or files

## Why this issue exists

This repository may write sensitive data — API keys, tokens, passwords,
personal information, internal URLs with embedded credentials, full HTTP
request/response bodies containing auth headers — to stdout, stderr, log
files, or other persistent locations. Even when the code looks safe,
real leaks have occurred via:

- Direct logging of credentials (`logger.info(f"key={api_key}")`)
- Indirect logging of objects that contain credentials (logging a
  response object whose headers include `Authorization`)
- Exception handlers that log full exception messages from HTTP
  libraries, which often include the failing URL with credentials in it
- `print()` statements left over from debugging
- Pretty-printers (`pprint`, `json.dumps`, `rich.print`) dumping dicts
  that contain secrets
- Configuration files or `.env` examples checked into the repo
- Test fixtures with real credentials
- Output files (CSV, JSON, logs) written during normal operation that
  echo back credential-bearing data

The downstream risk is that AI coding agents (Claude Code, Codex, etc.)
snapshot terminal output and shell history, preserving leaked
credentials in files like `~/.claude/file-history/` and
`~/.codex/shell_snapshots/` without the developer realizing.

This audit must confirm the repo is clean. Some past fixes may already
be in place — verify they hold.

## Scope

Audit this repository for any code path that could write sensitive data
to:

- Terminal (stdout, stderr) via `print`, `logging`, `pprint`, or any
  other mechanism
- Log files (rotating files, syslog, custom log writers)
- Output files (reports, exports, dumps, debug captures)
- Error reporting (uncaught exceptions, traceback dumps,
  Sentry/equivalent payloads)
- Anything else that persists data outside the running process

Sensitive data includes, but is not limited to:

- API keys, access tokens, refresh tokens, session IDs
- Passwords, password hashes, secret keys
- `Authorization` headers, `Cookie` headers, JWTs
- URLs containing credentials (`https://user:pass@host`,
  query-string keys like `?api_key=...`)
- Personally identifiable information (patron records, email
  addresses tied to identifiable individuals, ID numbers)
- Internal hostnames, paths, or identifiers that shouldn't be public
- Database connection strings with embedded credentials

## Audit checklist

Work through these systematically. Don't skip any — the goal is
confidence that nothing was missed.

### 1. Find every logging and output call

```bash
grep -rn --include='*.py' -E \
  '\b(print|pprint|logger|logging|log)\b' .
```

Also check for less common cases:
- `sys.stdout.write` / `sys.stderr.write`
- `rich.print`, `rich.console`
- `traceback.print_exc`, `traceback.format_exc`
- `warnings.warn`
- Custom logger wrappers in the repo

### 2. For each call, ask: could the value contain a secret?

Direct cases (easy to spot):
- f-strings or `%` formatting with variable names like `key`, `token`,
  `secret`, `password`, `auth`, `credential`, `api_key`

Indirect cases (the dangerous ones):
- Logging a whole `response` object, `request` object, or HTTP
  exception — these often contain the URL and headers
- Logging a config dict, environment dict, `locals()`, `vars(self)`,
  or any object whose `__repr__` exposes attributes
- Logging the result of an API call whose JSON response echoes back
  credentials (some APIs do this in error messages)
- Logging headers dicts directly
- Exception handlers that log `str(e)` from `requests` /
  `urllib` / `httpx` — the URL with auth often appears in the message

### 3. Find every file write

```bash
grep -rn --include='*.py' -E \
  '\b(open|Path\(.+\)\.write|to_csv|to_json|to_excel|dump|dumps)\b' .
```

For each one, check what's being written and whether the source data
could contain secrets.

### 4. Check configuration and fixtures

- `.env`, `.env.example`, `.env.local` — any real values?
- `config/`, `settings.py`, `*.yaml`, `*.toml`, `*.json` — hardcoded
  credentials?
- `tests/fixtures/`, `tests/data/` — real tokens used in tests?
- `docs/`, `README.md`, `examples/` — credentials in code samples?

### 5. Check log configuration

- Is the log level appropriate for production? `DEBUG` logging on a
  library that handles auth is a common leak source.
- Are there logging filters in place? If yes, do they actually scrub
  the patterns this repo uses?
- Where do logs go? File, stdout, both? Who reads them?

### 6. Check `__repr__` and `__str__` methods

Any custom classes whose string representation includes credential
fields will leak the moment they're logged or printed.

### 7. Check git history (lightweight)

```bash
git log --all -p -S 'api_key' -- '*.py' | head -100
git log --all -p -S 'token' -- '*.py' | head -100
```

If credentials *used to be* hardcoded and were removed in a later
commit, they still live in git history. Note any findings — git
history rewrites are out of scope for this issue but should be tracked
separately.

## What to do with findings

For each potential leak found, document:

1. **File and line number**
2. **What's being logged/written**
3. **Why it might be sensitive** (direct credential, indirect
   exposure, PII, etc.)
4. **Severity** — actual leak, possible leak, theoretical only
5. **Proposed fix** — one of:
   - Remove the log/print entirely (debug leftover, not needed)
   - Redact the value (replace with `***` or last-4-chars only)
   - Restructure to log only safe fields (e.g. log `len(response.text)`
     not `response.text`)
   - Change log level (move `DEBUG` to a guarded path)
   - Other

Don't make changes during the audit — produce the findings report
first. Decisions about which fixes to apply come after review.

## Acceptance criteria

This issue can be closed when:

- [ ] The audit checklist has been worked through completely
- [ ] All findings are documented (path, line, category, proposed fix)
- [ ] Proposed fixes have been reviewed and either applied or
      consciously deferred (with reason)
- [ ] A short summary comment is added to this issue stating: number of
      findings, number fixed, number deferred, and any patterns worth
      remembering for future code

## Out of scope

To prevent this issue from sprawling:

- Do not refactor the logging architecture broadly. Fix specific leaks.
- Do not add new features.
- Do not rewrite git history to remove past credentials. Track that
  separately if needed.
- Do not audit dependencies' logging behavior. Only this repo's code.

## Notes

If this repo previously had a fix for credential logging, re-verify it
holds. A passing test from six months ago doesn't prove current code
is clean — patterns may have regressed during unrelated changes.