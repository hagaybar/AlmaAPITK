/**
 * @process chunk-test
 * @description Generic interactive testing process for any chunk. Reads
 *   chunks/<name>/test-recommendation.json, interviews the human for fixtures
 *   via a single breakpoint, runs SANDBOX tests, writes test-results.json,
 *   triages outcomes, opens a draft PR, and appends to AGENTIC_RUN_LOG.md.
 *   Implements stages 5-7 of spec §7.
 * @inputs { chunkName: string, repoRoot: string }
 * @outputs { resultsPath: string, summary: object, prUrl: string|null }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

// ---------- shell tasks ----------

export const validateEnvTask = defineTask('validate-env', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Validate test environment (R8: SANDBOX-only credentials)',
  shell: {
    command: `set -e
# R8: refuse if prod key is set
if [ -n "$ALMA_PROD_API_KEY" ]; then
  echo "R8 violation: ALMA_PROD_API_KEY must not be set" >&2
  exit 2
fi
# Sandbox key must be present for tests to run
if [ -z "$ALMA_SB_API_KEY" ]; then
  echo "ALMA_SB_API_KEY not set — required to run SANDBOX tests" >&2
  exit 2
fi
cd "${args.repoRoot}"
git diff --quiet || (echo "tree dirty — refusing to test against unknown state" >&2; exit 2)
HEAD_BRANCH="$(git symbolic-ref --short HEAD)"
[ "$HEAD_BRANCH" = "chunk/${args.chunkName}" ] || (echo "expected on chunk/${args.chunkName}, on $HEAD_BRANCH" >&2; exit 2)
echo "validate-env OK"
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const readTestRecTask = defineTask('read-test-rec', (args, taskCtx) => ({
  kind: 'shell',
  title: `Read test-recommendation.json for chunk ${args.chunkName}`,
  shell: {
    command: `cat "${args.repoRoot}/chunks/${args.chunkName}/test-recommendation.json"`,
    timeout: 5000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const writeTestDataTask = defineTask('write-test-data', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Write test-data.json from operator interview answers',
  shell: {
    command: `cat > "${args.repoRoot}/chunks/${args.chunkName}/test-data.json" <<'EOF'
${JSON.stringify(args.testData, null, 2)}
EOF
echo "wrote test-data.json"`,
    timeout: 5000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const checkoutBranchTask = defineTask('checkout-branch', (args, taskCtx) => ({
  kind: 'shell',
  title: `Checkout chunk integration branch chunk/${args.chunkName}`,
  shell: {
    command: `cd "${args.repoRoot}" && git fetch origin && git checkout chunk/${args.chunkName} && git status --short`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// Lifecycle status transition. Same shape as in chunk-template-impl.js but
// duplicated locally so each process file remains independently importable.
export const transitionStatusTask = defineTask('transition-status', (args, taskCtx) => ({
  kind: 'shell',
  title: `chunk_status.transition → ${args.newStage}`,
  shell: {
    command: `cd "${args.repoRoot}" && python <<'PYEOF'
from pathlib import Path
from scripts.agentic.chunk_status import transition
transition(
    Path(${JSON.stringify(`${args.repoRoot}/chunks/${args.chunkName}`)}),
    ${JSON.stringify(args.newStage)},
    ${JSON.stringify(args.lastEvent)},
    ${JSON.stringify(args.nextAction)},
)
PYEOF
`,
    timeout: 15000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// Stage 7a fallout: open the draft PR via the existing pr_open helper.
export const openPrTask = defineTask('open-pr', (args, taskCtx) => ({
  kind: 'shell',
  title: `Open draft PR for chunk/${args.chunkName}`,
  shell: {
    command: `cd "${args.repoRoot}" && python -m scripts.agentic.pr_open <<'PAYLOAD_EOF'
${JSON.stringify({
  head_branch: `chunk/${args.chunkName}`,
  chunk_name: args.chunkName,
  issue_numbers: args.issueNumbers,
  impl_summary: args.implSummary,
  test_summary: args.testSummary,
  repo_root: args.repoRoot,
}, null, 2)}
PAYLOAD_EOF
`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// Stage 7c: append a row to AGENTIC_RUN_LOG.md.
export const appendRunLogTask = defineTask('append-run-log', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Append chunk run row to AGENTIC_RUN_LOG.md',
  shell: {
    command: `cd "${args.repoRoot}" && python -m scripts.agentic.run_log <<'PAYLOAD_EOF'
${JSON.stringify({
  log_path: `${args.repoRoot}/AGENTIC_RUN_LOG.md`,
  chunk_name: args.chunkName,
  issue_numbers: args.issueNumbers,
  attempts_used: args.attemptsUsed || {},
  test_outcomes: args.testOutcomes || { passed: 0, failed: 0, skipped: 0 },
  time_total_seconds: args.timeTotalSeconds || 0,
  pr_url: args.prUrl || '',
}, null, 2)}
PAYLOAD_EOF
`,
    timeout: 15000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// ---------- agent tasks ----------

export const generatePytestFilesTask = defineTask('generate-pytest', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Generate pytest files from test-recommendation + test-data',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python test engineer',
      task: `For chunk "${args.chunkName}", read:
- ${args.repoRoot}/chunks/${args.chunkName}/test-recommendation.json
- ${args.repoRoot}/chunks/${args.chunkName}/test-data.json

For each test in the recommendation, generate a pytest file at:
  ${args.repoRoot}/chunks/${args.chunkName}/sandbox-tests/test_<test.id>.py

Each pytest file:
  1. Imports AlmaAPIClient and the relevant domain class.
  2. Substitutes \${var} placeholders in pythonCalls from test-data.json.
  3. Runs each pythonCall and asserts every passCriterion.
  4. If stateChanging is true, runs cleanup in a try/finally — failure to clean is a FAIL.
  5. Uses ALMA_SB_API_KEY (never PROD).

Return JSON: { "filesWritten": [...], "tests": [{id, path, stateChanging, hasCleanup}] }`,
      outputFormat: 'JSON',
    },
    outputSchema: { type: 'object', required: ['filesWritten', 'tests'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const runPytestTask = defineTask('run-pytest', (args, taskCtx) => ({
  kind: 'shell',
  title: `Run SANDBOX test ${args.testId}`,
  shell: {
    command: `cd "${args.repoRoot}" && \
      poetry run pytest "${args.testFile}" -v --tb=short \
      > "chunks/${args.chunkName}/sandbox-test-output/${args.testId}.log" 2>&1
echo $?`,
    timeout: 300000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const aggregateResultsTask = defineTask('aggregate-results', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Aggregate per-test outcomes into test-results.json',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Test results aggregator',
      task: `Read every log file under ${args.repoRoot}/chunks/${args.chunkName}/sandbox-test-output/.
For each, determine pass/fail/skipped and extract the assertion details.
Aggregate into a single JSON written to ${args.repoRoot}/chunks/${args.chunkName}/test-results.json with shape:

{
  "chunk": "${args.chunkName}",
  "testRunStartedAt": "...",
  "testRunFinishedAt": "...",
  "perTest": [{"id": "t-3-1", "outcome": "passed|failed|skipped", "issueNumber": 3, "stateChanging": false, "cleanupStatus": "n/a|ok|failed", "details": "..."}],
  "perIssue": [{"number": 3, "everyAcMapped": true, "everyTestPassed": true, "anySkips": false, "autoCloseEligible": true}]
}

Return the same JSON.`,
      outputFormat: 'JSON',
    },
    outputSchema: { type: 'object', required: ['chunk', 'perTest', 'perIssue'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// Stage 7a: triage per-issue outcomes against the spec rules in
// scripts/agentic/prompts/summary-triage.v1.md and apply gh actions
// (labels, optional auto-close) directly inside the agent action.
export const summaryTriageTask = defineTask('summary-triage', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Triage per-issue outcomes; apply gh labels/closures',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Chunk triage operator',
      task: `Read:
- ${args.repoRoot}/chunks/${args.chunkName}/manifest.json
- ${args.repoRoot}/chunks/${args.chunkName}/test-results.json
- ${args.repoRoot}/scripts/agentic/prompts/summary-triage.v1.md (the rules)

For each issue, decide auto-close eligibility per the prompt's rules and apply
the corresponding gh actions (labels, comments, optional close). Capture every
gh invocation you ran in actionsApplied.

Return JSON:
{
  "perIssue": [
    {"number": <int>, "outcome": "passed|failed|skipped|blocked",
     "actionsApplied": ["<gh cmd or short note>", ...]}
  ],
  "logRow": {
    "chunk_name": "${args.chunkName}",
    "issue_numbers": <list[int]>,
    "passed": <int>, "failed": <int>, "skipped": <int>
  },
  "implSummary": "<one-paragraph impl summary>",
  "testSummary": "<one-paragraph test summary>"
}`,
      outputFormat: 'JSON',
    },
    outputSchema: { type: 'object', required: ['perIssue', 'logRow'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// ---------- main ----------

export async function process(inputs, ctx) {
  const { chunkName, repoRoot } = inputs;
  if (!chunkName) throw new Error('chunkName is required');
  if (!repoRoot) throw new Error('repoRoot is required');

  const startedAt = Date.now();
  ctx.log(`chunk-test for ${chunkName}: stage 5-7`);

  await ctx.task(validateEnvTask, { repoRoot, chunkName });

  const testRec = await ctx.task(readTestRecTask, { chunkName, repoRoot });

  // Aggregate every needsHumanInput.key across all tests for one breakpoint
  const fixtures = new Map();
  for (const issue of testRec.issues || []) {
    for (const t of issue.tests || []) {
      for (const f of t.needsHumanInput || []) {
        if (!fixtures.has(f.key)) fixtures.set(f.key, f);
      }
    }
  }

  let testData = {};
  if (fixtures.size > 0) {
    // The repo's existing breakpoint convention is question/title/context with
    // an `approved` + `response` reply. We render the fixture list inside the
    // question text and ask the operator to paste back a JSON object.
    const fixtureLines = Array.from(fixtures.values())
      .map(f => `  - ${f.key}: ${f.description || ''}${f.example ? ` (e.g. ${f.example})` : ''}`)
      .join('\n');
    const answers = await ctx.breakpoint({
      question: `Test fixtures for chunk "${chunkName}". Provide values (must already exist in SANDBOX) by replying with a JSON object whose keys match these fixture names:\n${fixtureLines}\n\nExample: {"user_primary_id": "demo-user", "mms_id": "9912345"}`,
      title: `Chunk "${chunkName}" — fixture interview`,
      context: {
        chunk: chunkName,
        fixtures: Array.from(fixtures.values()),
      },
      tags: ['chunk-test', 'fixtures'],
    });
    if (!answers.approved) {
      throw new Error('operator declined to provide fixtures; aborting test run');
    }
    // Operator replied with a JSON blob in `response` (per repo convention).
    // Parse defensively: if the response isn't valid JSON, fall through with
    // an empty testData so the agent task can surface a clearer error.
    if (typeof answers.values === 'object' && answers.values !== null) {
      testData = answers.values;
    } else if (typeof answers.response === 'string') {
      try {
        testData = JSON.parse(answers.response);
      } catch (e) {
        ctx.log(`warn: failed to parse fixture response as JSON: ${e.message || e}`);
        testData = {};
      }
    }
  }

  // Lifecycle: fixtures collected; tests are about to run.
  await ctx.task(transitionStatusTask, {
    repoRoot, chunkName,
    newStage: 'test-running',
    lastEvent: 'fixtures collected, running tests',
    nextAction: 'wait for results',
  });

  await ctx.task(writeTestDataTask, { chunkName, repoRoot, testData });
  await ctx.task(checkoutBranchTask, { chunkName, repoRoot });
  const generated = await ctx.task(generatePytestFilesTask, { chunkName, repoRoot });

  for (const t of generated.tests) {
    await ctx.task(runPytestTask, {
      chunkName, repoRoot,
      testId: t.id, testFile: t.path,
    });
  }

  const results = await ctx.task(aggregateResultsTask, { chunkName, repoRoot });

  // Lifecycle: tests complete; ready for triage + PR.
  await ctx.task(transitionStatusTask, {
    repoRoot, chunkName,
    newStage: 'test-done',
    lastEvent: 'tests complete',
    nextAction: 'triage and PR',
  });

  // Stage 7a: triage outcomes and apply gh actions.
  const triage = await ctx.task(summaryTriageTask, { repoRoot, chunkName });

  // Pull issue numbers from triage.logRow (authoritative) or fall back to
  // results.perIssue.
  const issueNumbers =
    (triage.logRow && triage.logRow.issue_numbers) ||
    (results.perIssue || []).map(p => p.number);

  // Stage 7b: open the draft PR.
  const prResult = await ctx.task(openPrTask, {
    repoRoot, chunkName,
    issueNumbers,
    implSummary: triage.implSummary || '(see commits)',
    testSummary: triage.testSummary || '(see chunks/<name>/test-results.json)',
  });
  // pr_open emits {ok, pr_url} JSON on stdout, captured into output.json.
  const prUrl = (prResult && prResult.pr_url) || null;

  // Stage 7c: append the run-log row.
  const timeTotalSeconds = Math.round((Date.now() - startedAt) / 1000);
  await ctx.task(appendRunLogTask, {
    repoRoot, chunkName,
    issueNumbers,
    attemptsUsed: triage.attemptsUsed || {},
    testOutcomes: {
      passed: (triage.logRow && triage.logRow.passed) || 0,
      failed: (triage.logRow && triage.logRow.failed) || 0,
      skipped: (triage.logRow && triage.logRow.skipped) || 0,
    },
    timeTotalSeconds,
    prUrl: prUrl || '',
  });

  // Lifecycle: PR opened; ready for human review and merge.
  await ctx.task(transitionStatusTask, {
    repoRoot, chunkName,
    newStage: 'pr-opened',
    lastEvent: prUrl ? `draft PR opened: ${prUrl}` : 'draft PR opened',
    nextAction: 'review and merge manually',
  });

  return {
    resultsPath: `${repoRoot}/chunks/${chunkName}/test-results.json`,
    summary: results,
    prUrl,
  };
}
