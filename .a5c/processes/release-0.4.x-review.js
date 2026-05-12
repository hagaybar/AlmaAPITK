/**
 * @process release-0.4.x-review
 * @description Review the full 0.4.x release cycle (range v0.3.1..HEAD) of
 *   the almaapitk PyPI package. v0.4.0 through v0.4.3 were one logical
 *   release split across four version bumps because of release-process
 *   mistakes; HEAD carries two cleanup commits (RELEASE_CHECKLIST.md add and
 *   the CHANGELOG YANKED note for 0.4.2). The process gathers the diff
 *   inventory, runs a structured code review covering quality, API risks,
 *   test coverage, release hygiene, and regressions, then composes a
 *   findings markdown report at docs/reviews/2026-05-12-release-0.4.x-review.md
 *   and pauses for operator review at the end. No code is modified.
 * @inputs { repoRoot: string, baseRef: string, headRef: string, reportPath: string }
 * @outputs { success: boolean, reportPath: string, findingsCount: number }
 * @skill superpowers:code-reviewer methodologies/superpowers/requesting-code-review.js
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

// ---------------------------------------------------------------------------
// Task 1 — gather diff context (shell, read-only)
// ---------------------------------------------------------------------------
export const gatherContextTask = defineTask('gather-context', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Gather diff context for v0.3.1..HEAD',
  shell: {
    command: `set -e
cd "${args.repoRoot}"
ART_DIR=".a5c/runs/$BABYSITTER_RUN_ID/artifacts/review"
mkdir -p "$ART_DIR"

# Commit list (oneline) with counts
git log --oneline ${args.baseRef}..${args.headRef} > "$ART_DIR/commits.txt"
COMMIT_COUNT=$(wc -l < "$ART_DIR/commits.txt" | tr -d ' ')

# Shortstat summary
git diff --shortstat ${args.baseRef}..${args.headRef} > "$ART_DIR/shortstat.txt"

# Per-file stat
git diff --stat=200 ${args.baseRef}..${args.headRef} > "$ART_DIR/diffstat.txt"

# Name + status (A/M/D/R)
git diff --name-status ${args.baseRef}..${args.headRef} > "$ART_DIR/name-status.txt"

# Full diff (cap context lines to keep it readable)
git diff -U3 ${args.baseRef}..${args.headRef} > "$ART_DIR/full.diff"
DIFF_BYTES=$(wc -c < "$ART_DIR/full.diff" | tr -d ' ')

# Tag dates inside the range (for release-hygiene context)
{
  echo "# Tags reachable from ${args.headRef} created after ${args.baseRef}:"
  for tag in $(git tag --list 'v0.4*' --sort=creatordate); do
    git log -1 --format="%H %ci %s" "$tag" | sed "s|^|$tag  |"
  done
} > "$ART_DIR/tags.txt"

# Recent commit messages on main since baseRef (full bodies, useful for hygiene narrative)
git log --format=fuller ${args.baseRef}..${args.headRef} > "$ART_DIR/log-fuller.txt"

# Summary JSON for orchestrator
cat > "$ART_DIR/context-summary.json" <<EOF
{
  "baseRef": "${args.baseRef}",
  "headRef": "${args.headRef}",
  "commitCount": $COMMIT_COUNT,
  "diffBytes": $DIFF_BYTES,
  "artifactsDir": "$ART_DIR"
}
EOF

echo "context gathered: $COMMIT_COUNT commits, $DIFF_BYTES diff bytes, artifacts at $ART_DIR"
`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['review', 'context'],
}));

// ---------------------------------------------------------------------------
// Task 2 — structured code review (agent: superpowers:code-reviewer)
// ---------------------------------------------------------------------------
export const codeReviewTask = defineTask('code-review', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Structured code review of v0.3.1..HEAD',
  agent: {
    name: 'superpowers:code-reviewer',
    prompt: {
      role: 'Senior Python library reviewer with deep familiarity with REST API clients and release engineering.',
      task: `Review the cumulative diff for the AlmaAPITK 0.4.x release cycle (range ${args.baseRef}..${args.headRef}). Treat all of v0.4.0/0.4.1/0.4.2/0.4.3 as one logical release split across four version bumps due to release-process mistakes. HEAD includes two post-0.4.3 cleanup commits (RELEASE_CHECKLIST.md add and CHANGELOG YANKED note for 0.4.2).`,
      context: {
        repoRoot: args.repoRoot,
        baseRef: args.baseRef,
        headRef: args.headRef,
        artifactsDir: args.artifactsDir,
        notes: [
          'Public PyPI package - operator-supplied identifiers must not appear in committed content (R9).',
          'R10: bugs are supposed to be fixed with a failing test first. Verify this discipline held across the four bumps.',
          'CLAUDE.md describes chunk-driven workflow; many commits are chunk PR merges.',
          '__version__ drifted in 0.4.2 — the fix in 0.4.3 reads version from importlib.metadata.',
        ],
      },
      instructions: [
        `Read context artifacts (commits.txt, shortstat.txt, diffstat.txt, name-status.txt, full.diff, tags.txt, log-fuller.txt) at .a5c/runs/$BABYSITTER_RUN_ID/artifacts/review/.`,
        'For anything ambiguous, inspect the actual file at the head ref using Read with the path from name-status.txt — do not invent details.',
        'Cover these dimensions and produce concrete, file:line-referenced findings:',
        '  1) Code quality: PEP 8, type hints, logging vs print, function size, dead code, duplication.',
        '  2) API/interface risk: backwards-compatibility of public almaapitk imports, response wrapping, exception hierarchy, paginator semantics.',
        '  3) Test coverage: were new domain methods + bug fixes accompanied by unit/integration tests? Any tests skipped or commented out? Was R10 honored?',
        '  4) Release hygiene: why did 0.4.0 → 0.4.1 → 0.4.2 → 0.4.3 happen? What checks were missing? Is the new RELEASE_CHECKLIST.md sufficient? Does CHANGELOG accurately reflect what shipped?',
        '  5) Security / R9: any operator-supplied identifiers, API keys, or PII committed? Inspect new test data, examples, prompt-template `example` fields.',
        '  6) Regressions and smells: anything that looks load-bearing-but-fragile, silent fallbacks, broad except, magic strings, environment-coupling.',
        'Severity rubric: CRITICAL (must fix before next release), HIGH (fix this cycle), MEDIUM (fix when convenient), LOW (informational).',
        'Each finding must include: id (F-001..), severity, dimension, summary, evidence (file:line or commit sha + path), recommendation.',
        'Also produce a top-level narrative: what worked well, what failed, what one process change would have prevented the four-bump pattern.',
        'Return JSON ONLY in the exact schema below. No markdown, no prose outside JSON.',
      ],
      outputFormat: 'JSON',
      outputSchema: {
        type: 'object',
        required: ['summary', 'overallSeverity', 'findings', 'narrative'],
        properties: {
          summary: { type: 'string', description: 'One-paragraph executive summary.' },
          overallSeverity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'NONE'] },
          findings: {
            type: 'array',
            items: {
              type: 'object',
              required: ['id', 'severity', 'dimension', 'summary', 'evidence', 'recommendation'],
              properties: {
                id: { type: 'string' },
                severity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] },
                dimension: { type: 'string', enum: ['code-quality', 'api-risk', 'test-coverage', 'release-hygiene', 'security', 'regression-smell'] },
                summary: { type: 'string' },
                evidence: { type: 'string' },
                recommendation: { type: 'string' },
              },
            },
          },
          narrative: {
            type: 'object',
            required: ['worked', 'failed', 'singleProcessChange'],
            properties: {
              worked: { type: 'array', items: { type: 'string' } },
              failed: { type: 'array', items: { type: 'string' } },
              singleProcessChange: { type: 'string' },
            },
          },
          stats: {
            type: 'object',
            properties: {
              commitsReviewed: { type: 'number' },
              filesReviewed: { type: 'number' },
              criticalCount: { type: 'number' },
              highCount: { type: 'number' },
              mediumCount: { type: 'number' },
              lowCount: { type: 'number' },
            },
          },
        },
      },
    },
  },
  execution: { model: 'claude-opus-4-7' },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`,
  },
  labels: ['review', 'code-review'],
}));

// ---------------------------------------------------------------------------
// Task 3 — compose markdown findings report (agent: general-purpose)
// ---------------------------------------------------------------------------
export const composeReportTask = defineTask('compose-report', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Compose findings report markdown',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Technical writer producing release-review reports for a Python library team.',
      task: `Compose a markdown findings report at ${args.reportPath} using the structured review JSON returned in input.json. The report must be self-contained and useful as a standalone artifact for the operator (no need to re-read raw review JSON).`,
      context: {
        reportPath: args.reportPath,
        repoRoot: args.repoRoot,
        baseRef: args.baseRef,
        headRef: args.headRef,
      },
      instructions: [
        'Read the review JSON from tasks/<effectId>/input.json (it contains the prior task output under the `review` key).',
        'Write a markdown document with the following sections, in this order:',
        '  # AlmaAPITK 0.4.x Release Review — 2026-05-12',
        '  Metadata block: range reviewed (baseRef..headRef), overall severity, counts, generation date.',
        '  ## Executive Summary — the `summary` field, lightly polished.',
        '  ## What Worked / What Failed / One Process Change — from `narrative`.',
        '  ## Findings — group by severity (CRITICAL first, then HIGH, MEDIUM, LOW). Within each, render each finding as: ### F-NNN — severity — dimension — summary; then **Evidence** and **Recommendation** as bold-prefixed paragraphs.',
        '  ## Recommended Follow-Up — bulleted, ordered by severity then by ease of fix.',
        '  ## Methodology — short paragraph explaining the review scope (range, dimensions, that v0.4.0/0.4.1/0.4.2/0.4.3 were one logical release).',
        'Use the Write tool to save the file at the absolute path in `reportPath`. Create parent dirs if missing.',
        'Redact any operator-supplied identifiers if you see them in evidence strings (R9). Replace with generic placeholders like `<user_primary_id>`.',
        'Do NOT add a Co-Authored-By footer. Do NOT add emojis.',
        'After writing the file, return JSON with the absolute file path, byte size, and finding counts.',
      ],
      outputFormat: 'JSON',
      outputSchema: {
        type: 'object',
        required: ['reportPath', 'bytes', 'findingsCount'],
        properties: {
          reportPath: { type: 'string' },
          bytes: { type: 'number' },
          findingsCount: { type: 'number' },
          severityBreakdown: { type: 'object' },
        },
      },
    },
  },
  execution: { model: 'claude-opus-4-7' },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`,
  },
  labels: ['review', 'compose'],
}));

// ---------------------------------------------------------------------------
// Task 4 — verify report file exists & is non-trivial (shell)
// ---------------------------------------------------------------------------
export const verifyReportTask = defineTask('verify-report', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Verify report file written & substantive',
  shell: {
    command: `set -e
cd "${args.repoRoot}"
[ -f "${args.reportPath}" ] || (echo "verify FAIL: report missing at ${args.reportPath}" >&2; exit 2)
BYTES=$(wc -c < "${args.reportPath}" | tr -d ' ')
LINES=$(wc -l < "${args.reportPath}" | tr -d ' ')
[ "$BYTES" -gt 800 ] || (echo "verify FAIL: report too small ($BYTES bytes)" >&2; exit 2)
grep -q "^## Findings" "${args.reportPath}" || (echo "verify FAIL: no Findings section" >&2; exit 2)
grep -q "^## Executive Summary" "${args.reportPath}" || (echo "verify FAIL: no Executive Summary section" >&2; exit 2)
echo "verify OK: $LINES lines, $BYTES bytes at ${args.reportPath}"
`,
    timeout: 15000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['review', 'verify'],
}));

// ---------------------------------------------------------------------------
// Main process
// ---------------------------------------------------------------------------
export async function process(inputs, ctx) {
  const {
    repoRoot,
    baseRef = 'v0.3.1',
    headRef = 'HEAD',
    reportPath,
  } = inputs;

  ctx.log('Starting release-0.4.x review', { baseRef, headRef, reportPath });

  // Step 1: gather context
  const context = await ctx.task(gatherContextTask, { repoRoot, baseRef, headRef });
  ctx.log('Context gathered', context);

  // Step 2: structured code review
  const review = await ctx.task(codeReviewTask, {
    repoRoot,
    baseRef,
    headRef,
    artifactsDir: context.artifactsDir,
  });
  ctx.log('Review complete', {
    overallSeverity: review.overallSeverity,
    findingsCount: (review.findings || []).length,
  });

  // Step 3: compose markdown report (pass review payload through)
  const report = await ctx.task(composeReportTask, {
    repoRoot,
    baseRef,
    headRef,
    reportPath,
    review,
  });
  ctx.log('Report composed', report);

  // Step 4: verify report file
  await ctx.task(verifyReportTask, { repoRoot, reportPath });

  // Step 5: final breakpoint for operator review
  const approval = await ctx.breakpoint({
    question: `Review report written to ${reportPath} (${(review.findings || []).length} findings, overall severity ${review.overallSeverity}). Open the file to read it. Acknowledge to close the run?`,
    title: 'Release 0.4.x Review — Findings Ready',
    options: ['Acknowledge — close run', 'Reject — needs rework'],
    expert: 'owner',
    tags: ['review-complete'],
    context: {
      runId: ctx.runId,
      files: [
        { path: reportPath, format: 'markdown', label: 'Findings report' },
      ],
    },
  });

  return {
    success: !!approval.approved,
    reportPath,
    findingsCount: (review.findings || []).length,
    overallSeverity: review.overallSeverity,
    metadata: {
      processId: 'release-0.4.x-review',
      baseRef,
      headRef,
      timestamp: ctx.now(),
    },
  };
}
