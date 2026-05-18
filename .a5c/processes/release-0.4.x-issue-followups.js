/**
 * @process release-0.4.x-issue-followups
 * @description Execute the 14-task plan at
 *   docs/superpowers/plans/2026-05-12-release-0.4.x-issue-followups-plan.md.
 *   Posts 3 comments on existing GitHub issues (#9, #11, #131), creates 8
 *   new issues (clusters A–H), updates the spec with the assigned issue
 *   numbers, and commits. Every step is idempotent: comment posts use
 *   HTML-comment markers, new-issue creation uses exact-title match. The
 *   captured GitHub issue numbers land in .a5c/issue-numbers/<letter>.txt
 *   so a re-run picks them up without re-creating issues.
 * @inputs { repoRoot: string }
 * @outputs { success: boolean, assigned: object, commitSha: string|null }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

const REPO = (args) => `cd "${args.repoRoot}"\nset -e`;

// ---------------------------------------------------------------------------
// Task 1 — preflight
// ---------------------------------------------------------------------------
export const preflightTask = defineTask('preflight', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Preflight: gh auth, target issues exist, on main, clean tree',
  shell: {
    command: `${REPO(args)}
unset ALMA_PROD_API_KEY
gh auth status >/dev/null
gh issue view 9 --json number >/dev/null
gh issue view 11 --json number >/dev/null
gh issue view 131 --json number >/dev/null
gh label list --limit 100 | grep -qE '^enhancement\\b'
gh label list --limit 100 | grep -qE '^priority:high\\b'
gh label list --limit 100 | grep -qE '^priority:medium\\b'
gh label list --limit 100 | grep -qE '^priority:low\\b'
HEAD_BRANCH="$(git symbolic-ref --short HEAD)"
[ "$HEAD_BRANCH" = "main" ] || { echo "preflight FAIL: not on main, on $HEAD_BRANCH" >&2; exit 2; }
git diff --quiet || { echo "preflight FAIL: dirty tree" >&2; git status -s >&2; exit 2; }
SPEC="${args.repoRoot}/docs/superpowers/specs/2026-05-12-release-0.4.x-issue-followups-design.md"
test -f "$SPEC" || { echo "preflight FAIL: spec missing at $SPEC" >&2; exit 2; }
mkdir -p "${args.repoRoot}/.a5c/issue-numbers"
echo "preflight OK"
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['followup', 'preflight'],
}));

// ---------------------------------------------------------------------------
// Task 2 — comment on #131
// ---------------------------------------------------------------------------
export const comment131Task = defineTask('comment-131', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Comment on #131 (widen scope to meta-tests trio)',
  shell: {
    command: `${REPO(args)}
MARKER='<!-- release-0.4.x-review-followup:131 -->'
if gh issue view 131 --json comments --jq '.comments[].body' | grep -qF "$MARKER"; then
  echo "skip: comment on #131 already present"
  exit 0
fi
gh issue comment 131 --body "$(cat <<'EOF'
<!-- release-0.4.x-review-followup:131 -->
The 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`) widens the scope this issue should cover. The single \`__version__\` check this issue was opened for is necessary but not sufficient — the 0.4.x cycle's four-bump pattern was driven by two parallel gaps, both of which the validation suite missed.

Proposed scope expansion — a meta-tests trio under \`tests/meta/\`, all wired into the \`RELEASE_CHECKLIST.md\` Phase F pytest line:

1. **\`tests/meta/test_no_hardcoded_version.py\`** (the original scope) — \`ast.walk\` \`src/almaapitk/\` and fail on any \`Assign(targets=[Name(id='__version__')], value=Constant(value=<str>))\`. The existing \`tests/test_version.py\` covers the runtime symptom but not the source-tree cause.
2. **\`tests/meta/test_top_level_docs_match_all.py\`** — parse \`__all__\` from \`src/almaapitk/__init__.py\` and assert every symbol appears in \`README.md\` (both the bullet list *and* the API-reference table), \`docs/index.md\`, and \`docs/getting-started.md\`. This covers the 0.4.1 → 0.4.2 bump cause (Configuration / typed errors missing from README table).
3. **\`tests/meta/test_docs_version_matches_pyproject.py\`** — scan \`docs/**/*.md\` for \`Version: X.Y.Z\` headings and assert they match \`pyproject.toml\`. Covers the still-stale \`docs/index.md:8\` and \`docs/getting-started.md:3\` showing \`Version: 0.2.0\`.

Also extend \`RELEASE_CHECKLIST.md\` Phase F pytest line to include \`tests/agentic/\` and \`tests/meta/\` (it currently lists only \`tests/unit/\`, \`tests/logging/\`, \`tests/integration/client/\`).

Closes findings F-001, F-002, F-007, F-016, F-020 from the 2026-05-12 review.
EOF
)"
gh issue view 131 --json comments --jq '.comments[].body' | grep -qF "$MARKER" && echo "verified" || { echo "verify FAIL: marker missing on #131" >&2; exit 2; }
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['followup', 'comment'],
}));

// ---------------------------------------------------------------------------
// Task 3 — comment on #11
// ---------------------------------------------------------------------------
export const comment11Task = defineTask('comment-11', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Comment on #11 (iter_paged sub-tasks F-008, F-018)',
  shell: {
    command: `${REPO(args)}
MARKER='<!-- release-0.4.x-review-followup:11 -->'
if gh issue view 11 --json comments --jq '.comments[].body' | grep -qF "$MARKER"; then
  echo "skip: comment on #11 already present"
  exit 0
fi
gh issue comment 11 --body "$(cat <<'EOF'
<!-- release-0.4.x-review-followup:11 -->
The 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`) surfaced two concrete sub-tasks that fit under this issue.

1. **F-008 — malformed-page handling.** \`iter_paged\` at \`src/almaapitk/client/AlmaAPIClient.py:1073\` calls \`.json()\` on every page response; if a page returns non-JSON (e.g., HTML error page, empty body), \`body.get()\` raises \`AttributeError\`, which is not in the Raises section of the docstring (lines 1016-1021 declare only \`AlmaValidationError\`, \`AlmaAPIError\`). Fix: wrap the parse in \`try: ... except (ValueError, JSONDecodeError) as e: raise AlmaAPIError(..., page_index=i) from e\`, and add a unit test that mocks page 3 returning \`text/plain\`.

2. **F-018 — non-JSON content-type caching.** \`AlmaResponse._safe_body()\` (\`AlmaAPIClient.py:140-144\`) deliberately does not cache when the parse returns \`None\`. The reasoning is sound for malformed-JSON (we want a later \`.json()\` to still raise) but unnecessarily skips caching the cheap "content-type is not JSON" sentinel — callers iterating \`.data\` in a loop re-traverse headers each time. Either cache the rejection sentinel separately, or document the deliberate non-caching in the \`.data\` property docstring.
EOF
)"
gh issue view 11 --json comments --jq '.comments[].body' | grep -qF "$MARKER" && echo "verified" || { echo "verify FAIL: marker missing on #11" >&2; exit 2; }
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['followup', 'comment'],
}));

// ---------------------------------------------------------------------------
// Task 4 — comment on #9
// ---------------------------------------------------------------------------
export const comment9Task = defineTask('comment-9', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Comment on #9 (typed-error cleanups F-011, F-015)',
  shell: {
    command: `${REPO(args)}
MARKER='<!-- release-0.4.x-review-followup:9 -->'
if gh issue view 9 --json comments --jq '.comments[].body' | grep -qF "$MARKER"; then
  echo "skip: comment on #9 already present"
  exit 0
fi
gh issue comment 9 --body "$(cat <<'EOF'
<!-- release-0.4.x-review-followup:9 -->
The 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`) surfaced two concrete cleanups that follow from the typed-error hierarchy this issue introduced.

1. **F-011 — Configuration boilerplate.** \`src/almaapitk/domains/configuration.py\` has a \`try / except AlmaAPIError as e: self.logger.error(...); raise\` pattern repeated across ~35 methods (~500 lines total). Since \`AlmaAPIClient._handle_response\` already logs the failure with \`alma_code\` / \`tracking_id\` / \`status_code\`, the per-method log adds no information. Either delete the per-method \`try/except\` blocks, or factor into a \`@log_alma_error('operation_name')\` decorator. ~500 lines deleted, no behavior change.

2. **F-015 — \`AlmaAPIClient.test_connection\` broad except.** \`AlmaAPIClient.py:1108-1120\` swallows everything via \`except Exception as e: ... return False\`. With the typed hierarchy now available, this should narrow to \`(requests.exceptions.RequestException, AlmaAPIError)\` so that callers can distinguish a missing API key (\`AlmaValidationError\`/\`AlmaAuthenticationError\`) from a real network outage.

Consider either as part of the closing-out PR for this issue, or as separate follow-ups linked here.
EOF
)"
gh issue view 9 --json comments --jq '.comments[].body' | grep -qF "$MARKER" && echo "verified" || { echo "verify FAIL: marker missing on #9" >&2; exit 2; }
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['followup', 'comment'],
}));

// ---------------------------------------------------------------------------
// Helper: defineTask for a "create new issue" task (clusters A-H).
// args: repoRoot, letter, title, priority, body.
// ---------------------------------------------------------------------------
function createIssueTask(idSuffix, opts) {
  return defineTask(`create-issue-${idSuffix}`, (args, taskCtx) => ({
    kind: 'shell',
    title: `Create new issue ${opts.letter} (${opts.priority}) — ${opts.title.substring(0, 60)}`,
    shell: {
      command: `${REPO(args)}
ND="${args.repoRoot}/.a5c/issue-numbers"
mkdir -p "$ND"
TITLE='${opts.title.replace(/'/g, "'\\''")}'
EXISTING=$(gh issue list --state all --limit 500 --json number,title --jq ".[] | select(.title == \\"$TITLE\\") | .number" | head -1)
if [ -n "$EXISTING" ]; then
  echo "skip: issue ${opts.letter} already exists as #$EXISTING"
  echo "$EXISTING" > "$ND/${opts.letter}.txt"
  exit 0
fi
URL=$(gh issue create \\
  --title "$TITLE" \\
  --label enhancement --label priority:${opts.priority} \\
  --body "$(cat <<'BODY_EOF'
${opts.body}
BODY_EOF
)")
echo "$URL"
NUM=$(echo "$URL" | grep -oE '/issues/[0-9]+$' | grep -oE '[0-9]+$')
echo "$NUM" > "$ND/${opts.letter}.txt"
gh issue view "$NUM" --json title,labels --jq '{n: '"$NUM"', title, labels: [.labels[].name]}'
echo "captured ${opts.letter}=#$NUM"
`,
      timeout: 60000,
    },
    io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
    labels: ['followup', 'create-issue', `cluster:${opts.letter}`],
  }));
}

// ---------------------------------------------------------------------------
// Task 5 — Issue A — Users.__init__ refactor (HIGH)
// ---------------------------------------------------------------------------
export const issueATask = createIssueTask('A', {
  letter: 'A',
  priority: 'high',
  title: 'Refactor Users.__init__ to use alma_logging.get_logger; drop CWD log files and dead sys.path.append',
  body: `<!-- release-0.4.x-review-followup:issue-A -->
**Domain:** code-quality / logging
**Priority:** high
**Effort:** S
**Source:** 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`), findings F-004, F-010

## Problem

\`Users.__init__\` re-creates its own console+file logger and writes \`sb_log_file.log\` / \`prod_log_file.log\` into the operator's current working directory on every instantiation. This bypasses the \`alma_logging\` framework and the no-stdout-during-request policy established in issues #2 / #14. Every domain method shipped in the 0.4.x cycle reinforces the regression. Additionally, \`src/almaapitk/domains/users.py:11-19\` contains a dead \`sys.path.append(...)\` followed by an absolute import that makes the path manipulation a no-op; this is the only domain file that does so.

## Files to touch

- \`src/almaapitk/domains/users.py:41-45\` — replace \`_setup_enhanced_logger\` call with \`self.logger = get_logger('users', environment=client.get_environment())\`.
- \`src/almaapitk/domains/users.py:51-92\` — delete \`_setup_enhanced_logger\` helper.
- \`src/almaapitk/domains/users.py:11-19\` — delete \`import sys\`, \`import os\`, the \`sys.path.append(...)\`, and any other now-unused imports (verify with \`grep\`).
- \`tests/unit/domains/test_users_init.py\` — new file with a no-stdout / no-CWD-file regression test.

## Prerequisites

None. Pre-existing pattern; refactor is self-contained.

## Acceptance criteria

- \`Users(client_stub).logger.name\` matches what \`alma_logging.get_logger('users', ...)\` returns.
- Instantiating \`Users\` does NOT create \`sb_log_file.log\` or \`prod_log_file.log\` in the test's working directory.
- No INFO-or-higher records appear on \`sys.stdout\` when \`Users\` is instantiated.
- \`grep -n 'sys.path.append' src/almaapitk/domains/users.py\` returns nothing.
- Existing tests (\`pytest tests/unit/domains/test_users.py\`) still pass unchanged.

## Notes for the implementing agent

- Use the \`alma-api-expert\` and \`python-dev-expert\` skills.
- The stub client in the new test should expose \`.get_environment()\` returning \`'SANDBOX'\`; no real HTTP needed.
- Check whether any chunk's sandbox-test relied on the \`sb_log_file.log\` side effect; if so, migrate that chunk to use \`caplog\` instead. The chunks affected: #36, #37, #39, #40, #41, #44, #45 (all instantiated \`Users\`).`,
});

// ---------------------------------------------------------------------------
// Task 6 — Issue B — bare except + ast guard (HIGH)
// ---------------------------------------------------------------------------
export const issueBTask = createIssueTask('B', {
  letter: 'B',
  priority: 'high',
  title: 'Narrow bare except: at acquisition.py:1814 and add tests/meta guard against bare-except recurrence',
  body: `<!-- release-0.4.x-review-followup:issue-B -->
**Domain:** code-quality
**Priority:** high
**Effort:** S
**Source:** 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`), finding F-003

## Problem

A bare \`except:\` clause survived in \`src/almaapitk/domains/acquisition.py:1814\` (the \`receive_item\` XML fallback path), even though the \`client-ergonomics\` chunk's acceptance criteria killed every bare \`except:\` in \`src/almaapitk/client/\`. The scope was narrow to \`client/\` and the rest of \`domains/\` was not inspected. Bare \`except:\` silently swallows \`KeyboardInterrupt\` and \`SystemExit\` and obscures real failures.

## Files to touch

- \`src/almaapitk/domains/acquisition.py:1812-1828\` — narrow the \`except:\` to \`except (ValueError, requests.exceptions.JSONDecodeError):\` (or the specific exceptions actually raised by the JSON fallback path; verify with a targeted test).
- \`tests/meta/test_logging_policy.py\` — extend with an \`ast.ExceptHandler\` walker that recursively scans \`src/almaapitk/\` and asserts \`node.type is not None\` for every handler.

## Prerequisites

None.

## Acceptance criteria

- The narrowed \`except\` in \`acquisition.py:1814\` still passes existing \`receive_item\` tests.
- The new ast guard test passes on the current tree (after the fix).
- The new ast guard test FAILS if a bare \`except:\` is reintroduced anywhere under \`src/almaapitk/\`.
- The existing \`tests/meta/test_logging_policy.py\` pattern is followed (same imports, same parametrize style).

## Notes for the implementing agent

- The existing \`tests/meta/test_logging_policy.py\` provides the pattern for an ast walker.
- This is a single ast walker, ~30 lines, runs in milliseconds.
- Use the \`python-dev-expert\` skill for the ast pattern.`,
});

// ---------------------------------------------------------------------------
// Task 7 — Issue C — R10 backfill for #114 (HIGH)
// ---------------------------------------------------------------------------
export const issueCTask = createIssueTask('C', {
  letter: 'C',
  priority: 'high',
  title: 'R10 backfill: regression test for update_letter XML-body bug (#114)',
  body: `<!-- release-0.4.x-review-followup:issue-C -->
**Domain:** test-coverage
**Priority:** high
**Effort:** S
**Source:** 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`), finding F-005

## Problem

The bug-fix for issue #114 (\`update_letter\` was sending a JSON body where Alma's letters API requires XML, producing Alma error \`60105 "JSON is not supported for this API."\`) landed in commit \`2d20ab3\` (\`fix(configuration): send XML body for update_letter (Fixes #114)\`). The existing unit test at \`tests/unit/domains/test_configuration.py:2843\` confirms the *current* (fixed) behavior but does not assert the failure mode the bug exhibited — so if a future refactor regresses to a JSON body, the test would silently keep passing only if its assertions happen to cover the symptom.

R10 (CLAUDE.md hard rule) requires a failing-test-first commit for any production bug. This is an R10 backfill.

## Files to touch

- \`tests/unit/domains/test_configuration.py\` (or \`tests/unit/regressions/test_issue_114.py\` — see issue D for the canonical home decision).

## Prerequisites

- Issue D (canonical R10 test home) should land first if we choose \`tests/unit/regressions/\`. Otherwise, file under \`tests/unit/domains/test_configuration.py\` and migrate later.

## Acceptance criteria

- New test named \`test_update_letter_sends_xml_body_regression_114\` (or in a per-issue file under \`tests/unit/regressions/\`).
- Docstring quotes the Alma \`60105 "JSON is not supported for this API."\` error and references issue #114.
- Assertions: the captured request's content-type header equals \`application/xml\`; the body is a \`str\` (not a \`dict\` or \`json.dumps\`-encoded string with a JSON content-type).
- The test FAILS on \`git revert 2d20ab3\` and PASSES on the current \`main\`.

## Notes for the implementing agent

- Reverting \`2d20ab3\` locally is the cheapest way to verify the test reproduces the bug.
- Use the \`alma-api-expert\` skill for the request-format detail.`,
});

// ---------------------------------------------------------------------------
// Task 8 — Issue D — canonical R10 home (MEDIUM)
// ---------------------------------------------------------------------------
export const issueDTask = createIssueTask('D', {
  letter: 'D',
  priority: 'medium',
  title: 'Establish tests/unit/regressions/test_issue_<N>.py as the canonical R10 home; document in CLAUDE.md',
  body: `<!-- release-0.4.x-review-followup:issue-D -->
**Domain:** test-coverage / process
**Priority:** medium
**Effort:** S
**Source:** 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`), findings F-017, F-014

## Problem

R10 (CLAUDE.md hard rule) requires every real-world bug to ship with a failing-test-first commit, but does not specify *where* the test lives. As a result, some R10 tests are filed under \`tests/unit/\` and some under \`chunks/<name>/sandbox-tests/\`. The chunks-based tests are at risk of going stale when a chunk is aborted or its directory is later pruned, breaking the monotonic "regression suite only grows" property.

Separately (F-014), the t-41-3 sandbox test prints operator-supplied IDs in its cleanup-failure banner — fine for operator-only stdout but a leak risk if a CI uploads logs as artifacts.

## Files to touch

- \`tests/unit/regressions/__init__.py\` — new, empty file.
- \`tests/unit/regressions/test_issue_<N>.py\` — convention (one file per bug-driven test, named after the GitHub issue or "bug-found-at-<date>" if no issue).
- \`CLAUDE.md\` (R10 section) — add one paragraph: "R10 tests live at \`tests/unit/regressions/test_issue_<N>.py\`; chunks SANDBOX smokes are a separate testing pattern (live-API verification) and do not count as the R10 test."
- \`chunks/users-requests/sandbox-tests/test_t-41-3.py\` (top of file) — add comment: \`# operator-only output; do not redirect to CI artifacts unless redaction is applied.\`

## Prerequisites

None.

## Acceptance criteria

- \`tests/unit/regressions/\` exists as a directory with an \`__init__.py\`.
- \`CLAUDE.md\` R10 section names the canonical home.
- The cumulative regression suite is \`pytest tests/unit/regressions/\` (no further intersection logic).
- The t-41-3 comment exists at the top of the file.

## Notes for the implementing agent

- Issue C may migrate \`test_update_letter_sends_xml_body_regression_114\` here once this lands.
- No code in \`src/\` changes.`,
});

// ---------------------------------------------------------------------------
// Task 9 — Issue E — create_user_request docstring (MEDIUM)
// ---------------------------------------------------------------------------
export const issueETask = createIssueTask('E', {
  letter: 'E',
  priority: 'medium',
  title: 'Document 401129 availability-cache race in Users.create_user_request docstring',
  body: `<!-- release-0.4.x-review-followup:issue-E -->
**Domain:** api-risk / documentation
**Priority:** medium
**Effort:** S
**Source:** 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`), finding F-006

## Problem

The SANDBOX test \`chunks/users-requests/sandbox-tests/test_t-41-3.py\` contains an inline 5-attempt / 2-second retry loop for Alma error \`401129 "No items can fulfill"\`, which surfaces because Alma's availability cache lags the holdings update by a few seconds. The fix lives only in the test — the wrapper method \`Users.create_user_request\` does not mention the race in its docstring, so non-test callers will hit the same surprise without knowing why.

## Files to touch

- \`src/almaapitk/domains/users.py\` — \`create_user_request\` docstring (around the method definition).

## Prerequisites

None.

## Acceptance criteria

- The docstring has a "Known caveat" section that names Alma error \`401129\` and explains the cache lag.
- The docstring recommends a caller-side retry with a brief sleep (link to t-41-3 as a worked example).
- Existing tests still pass (this is doc-only).

## Notes for the implementing agent

- Lowest-risk option per the review. If multiple operators later report the same surprise, consider a follow-up issue to expose \`retry_on_availability_race=True\` as a wrapper kwarg.
- Use the \`alma-api-expert\` skill for the Alma error reference.`,
});

// ---------------------------------------------------------------------------
// Task 10 — Issue F — gitignore swagger caches (MEDIUM)
// ---------------------------------------------------------------------------
export const issueFTask = createIssueTask('F', {
  letter: 'F',
  priority: 'medium',
  title: 'Gitignore chunks/*/_swagger_errors_*.json and remove committed copies (~1.2 MB cruft)',
  body: `<!-- release-0.4.x-review-followup:issue-F -->
**Domain:** release-hygiene / repo-hygiene
**Priority:** medium
**Effort:** S
**Source:** 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`), finding F-009

## Problem

The chunk pipeline regenerates per-chunk swagger-error caches on every \`fetch-swagger-codes\` step, but the resulting \`chunks/*/_swagger_errors_*.json\` files are not in \`.gitignore\`. As a result, 20 such files (~1.2 MB total) have been committed across the 0.4.x cycle and pollute the diff for unrelated PRs. The wider \`scripts/error_codes/swagger_cache/\` cache IS gitignored (\`.gitignore:210-212\`); the per-chunk variant was missed.

## Files to touch

- \`.gitignore\` — add \`chunks/*/_swagger_errors_*.json\` alongside the existing \`chunks/*/sandbox-test-output/\`, \`chunks/*/test-data.json\`, \`chunks/*/_pr_open_result.json\` entries (around \`.gitignore:202-207\`).
- \`git rm --cached chunks/*/_swagger_errors_*.json\` — remove the ~20 committed files from the index without deleting them on disk.

## Prerequisites

None.

## Acceptance criteria

- \`git status\` after the cleanup commit shows zero \`chunks/*/_swagger_errors_*.json\` files tracked.
- \`find chunks -name '_swagger_errors_*.json'\` still lists them on disk (regeneratable artifacts).
- A second invocation of any chunk's fetch-swagger-codes step regenerates the file without surfacing it in \`git status\`.

## Notes for the implementing agent

- Verify none of the committed copies contain secrets via \`grep -E 'API_KEY|primary_id|tau[0-9]' chunks/*/_swagger_errors_*.json\` before removing — these are Alma error-code metadata, so should be safe, but verify.`,
});

// ---------------------------------------------------------------------------
// Task 11 — Issue G — close-then-switch_environment (LOW)
// ---------------------------------------------------------------------------
export const issueGTask = createIssueTask('G', {
  letter: 'G',
  priority: 'low',
  title: 'Define behavior for AlmaAPIClient.close()-then-switch_environment() and add a unit test',
  body: `<!-- release-0.4.x-review-followup:issue-G -->
**Domain:** api-risk / test-coverage
**Priority:** low
**Effort:** S
**Source:** 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`), finding F-012

## Problem

\`AlmaAPIClient.switch_environment\` uses \`hasattr(self, '_session') and self._session is not None\` defensively (lines 1137, 1145) so the codepath does not crash if \`close()\` was called first. However, \`switch_environment\` does not call \`_setup_session\` either, so after a \`close()\` the client stays in a "no session" state and the very next \`client.get(...)\` will fail in an undocumented way. No unit test exercises this path. The existing \`tests/unit/client/test_context_manager.py\` covers the \`with\`-block case only.

## Files to touch

- \`tests/unit/client/test_context_manager.py\` (or a new \`test_close_then_switch.py\`) — add a unit test asserting either (a) \`close()\` then \`switch_environment()\` reinitialises the session, or (b) it raises a clear \`AlmaAPIError\`.
- Optionally: \`src/almaapitk/client/AlmaAPIClient.py\` \`switch_environment\` — re-call \`_setup_session()\` after env switch if session is None.

## Prerequisites

None.

## Acceptance criteria

- A unit test deterministically asserts the close-then-switch outcome.
- If the chosen outcome is "re-init session", a follow-up \`client.get(...)\` succeeds in the test (with a mocked session).
- If the chosen outcome is "raise clear error", the docstring of \`switch_environment\` documents it.

## Notes for the implementing agent

- Lowest-priority finding from the review; can fold into the next ergonomics PR rather than its own.`,
});

// ---------------------------------------------------------------------------
// Task 12 — Issue H — Configuration int/str params (LOW)
// ---------------------------------------------------------------------------
export const issueHTask = createIssueTask('H', {
  letter: 'H',
  priority: 'low',
  title: 'Pass int (not str) for limit/offset in Configuration.list_* methods; or migrate to iter_paged',
  body: `<!-- release-0.4.x-review-followup:issue-H -->
**Domain:** code-quality
**Priority:** low
**Effort:** S
**Source:** 2026-05-12 release-0.4.x review (\`docs/reviews/2026-05-12-release-0.4.x-review.md\`), finding F-019

## Problem

\`Configuration.list_libraries\` and many sibling \`list_*\` methods pass \`params={'limit': '100', 'offset': '0'}\` as strings. The rest of the codebase, including \`iter_paged\`, uses ints (\`AlmaAPIClient.py:1068-1072\`). Alma's API accepts both, so this is cosmetic — but it breaks \`grep\` consistency and a maintainer scanning for \`limit=100\` (int) misses these call sites.

## Files to touch

- \`src/almaapitk/domains/configuration.py\` — replace \`'100'\`/\`'0'\` strings in \`params\` dicts with ints. ~10+ call sites.

## Prerequisites

None. Soft prereq: issue #11 (\`iter_paged\`) is already merged, so the alternative "migrate to \`iter_paged\`" path is available.

## Acceptance criteria

- \`grep -n "'limit': '" src/almaapitk/domains/configuration.py\` returns no matches.
- Existing tests (\`pytest tests/unit/domains/test_configuration.py\`) still pass.
- If the migration-to-\`iter_paged\` option is taken instead, behavior for callers stays identical (small lists still return materialised lists, no pagination break).

## Notes for the implementing agent

- The defensive read: if an institution has 101 libraries, the current code silently truncates. \`iter_paged\` with \`max_records=100\` makes the truncation explicit.
- Lowest-priority code-quality finding; consider folding into the next Configuration PR rather than as a standalone.`,
});

// ---------------------------------------------------------------------------
// Task 13 — update the spec with assigned issue numbers
// ---------------------------------------------------------------------------
export const updateSpecTask = defineTask('update-spec', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Append Assigned Issue Numbers section to spec',
  shell: {
    command: `${REPO(args)}
SPEC="${args.repoRoot}/docs/superpowers/specs/2026-05-12-release-0.4.x-issue-followups-design.md"
ND="${args.repoRoot}/.a5c/issue-numbers"
for L in A B C D E F G H; do
  test -f "$ND/$L.txt" || { echo "missing: $ND/$L.txt" >&2; exit 2; }
done
A=$(cat $ND/A.txt); B=$(cat $ND/B.txt); C=$(cat $ND/C.txt); D=$(cat $ND/D.txt)
E=$(cat $ND/E.txt); F=$(cat $ND/F.txt); G=$(cat $ND/G.txt); H=$(cat $ND/H.txt)
echo "captured: A=$A B=$B C=$C D=$D E=$E F=$F G=$G H=$H"

# Strip any pre-existing Assigned section first (re-run safety)
python3 - <<PY
import re, pathlib
p = pathlib.Path("$SPEC")
s = p.read_text()
s = re.sub(r"\\n## Assigned issue numbers\\n.*?(?=\\n## |\\Z)", "", s, flags=re.S)
p.write_text(s.rstrip() + "\\n")
PY

cat >> "$SPEC" <<EOF

## Assigned issue numbers

Filed on 2026-05-12 via the babysitter-orchestrated execution of this plan.

| Cluster | Finding(s) | Severity | GitHub issue |
|---------|------------|----------|--------------|
| A | F-004, F-010 | HIGH | #$A |
| B | F-003 | HIGH | #$B |
| C | F-005 | HIGH | #$C |
| D | F-017, F-014 | MEDIUM | #$D |
| E | F-006 | MEDIUM | #$E |
| F | F-009 | MEDIUM | #$F |
| G | F-012 | LOW | #$G |
| H | F-019 | LOW | #$H |

Comments posted on existing issues: #9 (F-011, F-015), #11 (F-008, F-018), #131 (F-001, F-002, F-007, F-016, F-020).

Findings dropped from the issue batch: F-013 (CHANGELOG cross-reference — bundle into next docs PR).
EOF

grep -q "^## Assigned issue numbers\\$" "$SPEC" || { echo "verify FAIL: section missing after append" >&2; exit 2; }
for L in A B C D E F G H; do
  N=$(cat $ND/$L.txt)
  grep -qF "| #$N |" "$SPEC" || { echo "verify FAIL: $L=#$N not in spec" >&2; exit 2; }
done
echo "spec updated and verified"
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['followup', 'spec-update'],
}));

// ---------------------------------------------------------------------------
// Task 14 — commit the spec update
// ---------------------------------------------------------------------------
export const commitTask = defineTask('commit', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Commit spec update with assigned issue numbers',
  shell: {
    command: `${REPO(args)}
if git diff --quiet docs/superpowers/specs/2026-05-12-release-0.4.x-issue-followups-design.md; then
  echo "no-op: spec already committed"
  echo '{"sha": null, "skipped": true}' > /tmp/commit-info.json
  exit 0
fi
git add docs/superpowers/specs/2026-05-12-release-0.4.x-issue-followups-design.md
ND="${args.repoRoot}/.a5c/issue-numbers"
A=$(cat $ND/A.txt); B=$(cat $ND/B.txt); C=$(cat $ND/C.txt); D=$(cat $ND/D.txt)
E=$(cat $ND/E.txt); F=$(cat $ND/F.txt); G=$(cat $ND/G.txt); H=$(cat $ND/H.txt)
git commit -m "$(cat <<INNER_EOF
docs(spec): record assigned issue numbers for release-0.4.x review followups

Filed via babysitter:

- A: #$A (Users.__init__ refactor)
- B: #$B (bare except + ast guard)
- C: #$C (R10 backfill for #114)
- D: #$D (canonical R10 test home)
- E: #$E (create_user_request docstring)
- F: #$F (gitignore swagger-error caches)
- G: #$G (close-then-switch test/document)
- H: #$H (Configuration int/str params)

Comments posted on #9, #11, #131.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
INNER_EOF
)"
SHA=$(git rev-parse HEAD)
git log --oneline -1
echo "{\\"sha\\": \\"$SHA\\", \\"skipped\\": false}" > /tmp/commit-info.json
git status --short
git diff --quiet && echo "tree clean"
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['followup', 'commit'],
}));

// ---------------------------------------------------------------------------
// Main process
// ---------------------------------------------------------------------------
export async function process(inputs, ctx) {
  const { repoRoot } = inputs;
  const args = { repoRoot };

  ctx.log('Starting release-0.4.x issue-followups execution', { repoRoot });

  // Phase 1 — preflight
  await ctx.task(preflightTask, args);

  // Phase 2 — comments on existing issues
  await ctx.task(comment131Task, args);
  await ctx.task(comment11Task, args);
  await ctx.task(comment9Task, args);

  // Phase 3 — create new issues
  await ctx.task(issueATask, args);
  await ctx.task(issueBTask, args);
  await ctx.task(issueCTask, args);
  await ctx.task(issueDTask, args);
  await ctx.task(issueETask, args);
  await ctx.task(issueFTask, args);
  await ctx.task(issueGTask, args);
  await ctx.task(issueHTask, args);

  // Phase 4 — update spec + commit
  await ctx.task(updateSpecTask, args);
  await ctx.task(commitTask, args);

  // Final operator gate
  const approval = await ctx.breakpoint({
    question:
      'All 11 GitHub actions complete (3 comments, 8 new issues) and spec committed. Acknowledge to close the run.',
    title: 'Release 0.4.x Follow-Ups — Done',
    options: ['Acknowledge — close run', 'Reject — needs rework'],
    expert: 'owner',
    tags: ['followup-complete'],
    context: {
      runId: ctx.runId,
    },
  });

  return {
    success: !!approval.approved,
    metadata: {
      processId: 'release-0.4.x-issue-followups',
      timestamp: ctx.now(),
    },
  };
}
