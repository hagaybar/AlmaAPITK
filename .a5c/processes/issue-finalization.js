/**
 * @process issue-finalization
 * @description Finalize 79 open GitHub issues using two audit reports + Alma docs + repo code. Classify by `api-coverage` label, rank, edit/comment/label issues directly via gh, never close (only recommend closure in a comment).
 * @inputs { repoRoot: string, auditMd: string, auditCodexTxt: string, reportPath: string }
 * @outputs { success: boolean, summary: string, reportPath: string, perBatch: object[], aggregate: object }
 */

import { defineTask } from "@a5c-ai/babysitter-sdk";

// ─── Phase 1: Fetch issues + load audits ────────────────────────────────────────

const fetchIssues = defineTask("fetch-issues", (args) => ({
  kind: "shell",
  title: "Fetch open issues with comments",
  shell: {
    command: `set -euo pipefail
mkdir -p ${args.repoRoot}/.a5c/issue-finalization
cd ${args.repoRoot}
# Fetch all open issues with full body + comments
gh issue list --state open --limit 200 --json number,title,labels,body,url,comments > .a5c/issue-finalization/issues-with-comments.json
# Sanity counts
N=$(jq 'length' .a5c/issue-finalization/issues-with-comments.json)
echo "Fetched $N open issues"
test "$N" -ge 50 || { echo "Unexpected issue count: $N"; exit 1; }
# Confirm both audit files exist
test -f "${args.auditMd}" || { echo "Missing audit md: ${args.auditMd}"; exit 1; }
test -f "${args.auditCodexTxt}" || { echo "Missing codex audit: ${args.auditCodexTxt}"; exit 1; }
echo "OK"`
  }
}));

// ─── Phase 2: Per-batch classify-score-decide-apply ─────────────────────────────

const processBatch = defineTask("process-batch", (args, taskCtx) => ({
  kind: "agent",
  title: `Finalize issues #${args.startNumber}-#${args.endNumber}`,
  execution: { model: "claude-opus-4-7" },
  agent: {
    name: "general-purpose",
    prompt: {
      role: "Senior engineer + product-manager finalizing GitHub issues for an Alma API Python wrapper",
      task: `You are finalizing open GitHub issues #${args.startNumber}-#${args.endNumber} in the AlmaAPITK repo. Your job is to read each issue, the two pre-existing audit reports, and the relevant repo code, then classify, rank, decide, and APPLY changes via the gh CLI.

## Inputs you must read (in this order)

1. Issue data (already fetched): \`${args.repoRoot}/.a5c/issue-finalization/issues-with-comments.json\` — JSON array. Filter to numbers ${args.startNumber}-${args.endNumber}.
2. Structured audit (per-issue rows): \`${args.auditMd}\`
3. Codex direct audit (high-priority findings): \`${args.auditCodexTxt}\`
4. Repository code at \`${args.repoRoot}\` — relevant paths in \`src/almaapitk/domains/\`, \`src/almaapitk/client/\`.
5. Project guide: \`${args.repoRoot}/CLAUDE.md\` (especially the "Active Backlogs" section explaining issue templates).

## CRITICAL CLASSIFICATION RULE

For EACH issue in your batch:

- **If labels include \`api-coverage\`**: treat as documentation-alignment. Validate against \`https://developers.exlibrisgroup.com/alma/apis/\`. Use WebFetch ONLY if the structured audit row is silent or ambiguous on the field you need to verify; otherwise rely on the existing audit findings (don't re-do work). The structured audit at \`${args.auditMd}\` already has per-issue findings.
- **If labels do NOT include \`api-coverage\`**: treat as architecture/engineering. Evaluate against repo design and code. DO NOT mark "cannot verify against docs" — that's wrong for these. Read relevant code paths to confirm proposed change is well-scoped and feasible.

## SCORING (1-5 each)

- Documentation/technical accuracy
- Clarity
- Technical correctness
- Robustness of reasoning
- Implementation readiness
- Acceptance criteria quality
- Scope control
- Alignment with repo design
- Risk of misleading implementation

## DECISION RULES

- **Aligned issues (per audit) with good acceptance criteria**: leave unchanged. Comment only if you find a meaningful nit.
- **Partially aligned / Not aligned (api-coverage)**: REWRITE the body using the structured template below. Apply the audit's specific corrections (e.g., #76 missing \`op\`/\`user_ids\`/\`list_ids\`; #78 no body params). Add a short \`## Audit notes (2026-05-01)\` section at the bottom citing the audit findings.
- **General/architectural issues with vague scope or missing acceptance criteria**: edit body to add acceptance criteria + implementation notes. Do not invent requirements.
- **NEVER CLOSE ANY ISSUE.** If you believe an issue should be closed (truly invalid/duplicate/obsolete), instead post a comment titled \`## Closing recommendation\` with rationale and add label \`needs-decision\`. The human will decide.
- **NEVER add new labels you haven't verified exist.** Use existing labels: \`enhancement\`, \`api-coverage\`, \`priority:high\`, \`priority:medium\`, \`priority:low\`, \`bug\`. If you need a new label like \`needs-decision\` or \`audit:needs-rewrite\`, create it with \`gh label create <name> --color CCCCCC --description "..."\` (idempotent — check first with \`gh label list --search\`).

## REQUIRED ISSUE BODY STRUCTURE (when rewriting)

\`\`\`markdown
## Background
<short context — preserve original intent>

## Relevant Alma API documentation
<only for api-coverage issues — list verified URLs from the audit>

## Current wrapper behavior
<what exists today, with file paths>

## Expected wrapper behavior
<what should change — concrete method signatures>

## Implementation notes
<gotchas, query-vs-body, op values, required params, etc.>

## Acceptance criteria
- [ ] <testable criterion>
- [ ] <testable criterion>

## Open questions
<any ambiguities — only if real, do NOT invent>

## Audit notes (2026-05-01)
<reference to audit findings — quote the specific mismatch>
\`\`\`

PRESERVE the original "Domain", "Priority", "Effort", "Files to touch", "References", and "Prerequisites" headers if they appear in the original body — those are part of the project's standard template (see CLAUDE.md). Move them under the new structure where they fit (References → "Relevant Alma API documentation"; Files to touch → "Current wrapper behavior"; Prerequisites → "Open questions" or its own short section).

## ACTIONS — apply directly via gh CLI

For each issue you decide to edit:

\`\`\`bash
# Write the new body to a tempfile so heredoc + special chars don't bite you
cat > /tmp/issue-${args.startNumber}-N.md <<'BODY_EOF'
<your rewritten body here>
BODY_EOF
gh issue edit <N> --body-file /tmp/issue-${args.startNumber}-N.md
\`\`\`

For comments:

\`\`\`bash
cat > /tmp/comment-N.md <<'COMMENT_EOF'
<comment markdown>
COMMENT_EOF
gh issue comment <N> --body-file /tmp/comment-N.md
\`\`\`

For labels:

\`\`\`bash
gh issue edit <N> --add-label "needs-decision"
\`\`\`

## OUTPUT FORMAT

Return a single JSON object:

\`\`\`json
{
  "batch": "${args.startNumber}-${args.endNumber}",
  "perIssue": [
    {
      "number": 22,
      "title": "...",
      "classification": "api-coverage" | "general",
      "scores": {"docTech": 4, "clarity": 4, "tech": 4, "robust": 4, "ready": 4, "ac": 3, "scope": 4, "align": 5, "risk": 2},
      "overallStatus": "Ready / finalized" | "Needs minor edit" | "Needs major rewrite" | "Needs clarification" | "Should be split" | "Should be closed" | "Cannot safely finalize",
      "decision": "edited" | "commented" | "relabeled" | "edited+commented" | "unchanged" | "human review required",
      "actionsApplied": ["edited body", "added label needs-decision", "commented closing recommendation"],
      "reasoning": "1-3 sentences",
      "remainingConcerns": "anything unresolved"
    }
  ],
  "summary": {
    "total": ${args.endNumber - args.startNumber + 1},
    "edited": 0,
    "commented": 0,
    "relabeled": 0,
    "closingRecommended": 0,
    "unchanged": 0,
    "humanReview": 0
  }
}
\`\`\`

## CONSTRAINTS

- DO NOT close any issue. Closing recommendations go in comments + \`needs-decision\` label.
- DO NOT delete or overwrite existing useful context — preserve Domain/Priority/Effort/References/Prerequisites.
- DO NOT invent undocumented Alma behavior. If audit says "Cannot verify", leave it as-is and flag for human.
- DO NOT do cosmetic-only edits (e.g., reformatting whitespace). Every edit must add real value.
- WebFetch is allowed but use sparingly — the structured audit already has the verifications.
- For issues marked "Aligned" in the audit AND that already have acceptance criteria: do not edit. Move on.

Begin by reading all four input files. Then process issues in numeric order. Apply changes live via gh. Return the JSON when done.`,
      context: {
        startNumber: args.startNumber,
        endNumber: args.endNumber,
        repoRoot: args.repoRoot,
        auditMd: args.auditMd,
        auditCodexTxt: args.auditCodexTxt,
      },
      outputFormat: "JSON object as specified",
    },
    outputSchema: {
      type: "object",
      required: ["batch", "perIssue", "summary"],
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`,
  }
}));

// ─── Phase 3: Aggregate + write final report ────────────────────────────────────

const writeFinalReport = defineTask("write-final-report", (args, taskCtx) => ({
  kind: "agent",
  title: "Aggregate per-batch results and write final report",
  execution: { model: "claude-opus-4-7" },
  agent: {
    name: "general-purpose",
    prompt: {
      role: "Technical writer producing a final issue-finalization report",
      task: `Aggregate the five per-batch results below into a single final report and write it to \`${args.reportPath}\`.

Per-batch results (JSON array):
${JSON.stringify(args.perBatch, null, 2)}

The report must be markdown with this structure:

# Issue Finalization Report — 2026-05-01

## Summary
- Total issues reviewed: <n>
- Issues finalized (edited): <n>
- Issues edited (body rewrites): <n>
- Issues relabeled: <n>
- Issues commented: <n>
- Issues closed: 0 (closing decisions deferred to human via \`needs-decision\` label + comment)
- Issues requiring human review: <n>
- Unresolved documentation ambiguities: <n>
- Highest-risk issues: <list with #N and 1-line reason>
- Prioritized next actions: <numbered list, top 5-10>

## Per-issue detail

(For EACH of the 79 issues, in numeric order, emit the per-issue block from the input.)

### Issue #N: <title>

**Classification:** api-coverage / general
**Scores:** docTech X/5, clarity X/5, tech X/5, robust X/5, ready X/5, ac X/5, scope X/5, align X/5, risk X/5
**Overall status:** ...
**Final decision:** ...
**Changes made:** ...
**Reasoning:** ...
**Remaining concerns:** ...

(One blank line between issues.)

## Aggregate decisions by status

(Tally tables: by classification × decision, by overall status.)

After writing the file, return JSON:

\`\`\`json
{
  "reportPath": "${args.reportPath}",
  "totals": {
    "reviewed": 79,
    "edited": 0,
    "commented": 0,
    "relabeled": 0,
    "humanReview": 0,
    "closingRecommended": 0
  },
  "topRiskIssues": ["#52", "#57", "#72", "#76", "#78"],
  "summary": "1-2 sentence overall outcome"
}
\`\`\`

The file MUST be written to disk at \`${args.reportPath}\` before returning. Use the Write tool.`,
      context: {
        reportPath: args.reportPath,
        perBatch: args.perBatch,
      },
      outputFormat: "JSON",
    },
    outputSchema: {
      type: "object",
      required: ["reportPath", "totals", "summary"],
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`,
  }
}));

// ─── Main process ──────────────────────────────────────────────────────────────

export async function process(inputs, ctx) {
  const repoRoot = inputs.repoRoot || "/home/hagaybar/projects/AlmaAPITK";
  const auditMd = inputs.auditMd || `${repoRoot}/docs/issue-audit-2026-05-01.md`;
  const auditCodexTxt = inputs.auditCodexTxt || `${repoRoot}/docs/issue-audit-2026-05-01_codex_direct.txt`;
  const reportPath = inputs.reportPath || `${repoRoot}/docs/issue-finalization-report-2026-05-01.md`;

  // Phase 1
  ctx.log("Phase 1: Fetching open issues with comments...");
  await ctx.task(fetchIssues, { repoRoot, auditMd, auditCodexTxt });

  // Phase 2: 5 parallel batches of ~16 issues each
  ctx.log("Phase 2: Processing 5 parallel batches...");
  const batches = [
    { startNumber: 1,  endNumber: 16 },
    { startNumber: 17, endNumber: 32 },
    { startNumber: 33, endNumber: 48 },
    { startNumber: 49, endNumber: 64 },
    { startNumber: 65, endNumber: 79 },
  ];

  const perBatch = await Promise.all(
    batches.map((b) =>
      ctx.task(processBatch, {
        startNumber: b.startNumber,
        endNumber: b.endNumber,
        repoRoot,
        auditMd,
        auditCodexTxt,
      })
    )
  );

  // Phase 3
  ctx.log("Phase 3: Aggregating into final report...");
  const finalReport = await ctx.task(writeFinalReport, {
    perBatch,
    reportPath,
  });

  return {
    success: true,
    summary: `Finalized 79 issues across 5 parallel batches. Report at ${reportPath}.`,
    reportPath,
    perBatch,
    aggregate: finalReport,
  };
}
