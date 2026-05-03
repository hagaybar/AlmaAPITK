/**
 * @process chunk-test
 * @description Generic interactive testing process for any chunk. Reads
 *   chunks/<name>/test-recommendation.json, interviews the human for fixtures
 *   via a single breakpoint, runs SANDBOX tests, writes test-results.json.
 *   Implements stages 5-6 of spec §7.
 * @inputs { chunkName: string, repoRoot: string }
 * @outputs { resultsPath: string, summary: object }
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
# Repo must be on the chunk integration branch
cd "${args.repoRoot}"
git rev-parse --abbrev-ref HEAD
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

// ---------- main ----------

export async function process(inputs, ctx) {
  const { chunkName, repoRoot } = inputs;
  if (!chunkName) throw new Error('chunkName is required');
  if (!repoRoot) throw new Error('repoRoot is required');

  ctx.log(`chunk-test for ${chunkName}: stage 5-6`);

  await ctx.task(validateEnvTask, { repoRoot });

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
    const answers = await ctx.breakpoint({
      title: `Test fixtures for chunk "${chunkName}"`,
      message: 'Provide values for these fixtures (must already exist in SANDBOX):',
      fields: Array.from(fixtures.values()).map(f => ({
        key: f.key,
        label: f.description,
        placeholder: f.example || '',
      })),
    });
    if (!answers.approved) {
      throw new Error('operator declined to provide fixtures; aborting test run');
    }
    testData = answers.values || {};
  }

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

  return {
    resultsPath: `${repoRoot}/chunks/${chunkName}/test-results.json`,
    summary: results,
  };
}
