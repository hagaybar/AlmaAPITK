/**
 * @process chunk-template-impl
 * @description Per-chunk implementation runner. Reads chunks/<name>/manifest.json
 *   and processes each issue on its own sub-branch with a 3-attempt refinement
 *   loop, then merges into the integration branch. Implements stages 2-3 of
 *   spec §5.
 * @inputs { chunkName: string, repoRoot: string, maxAttempts?: number }
 * @outputs { mergedSubBranches: string[], testRecommendationPath: string }
 */
import pkg from '@a5c-ai/babysitter-sdk';
import { readFileSync } from 'node:fs';
const { defineTask } = pkg;

// ---------- shell tasks ----------

export const validateEnvTask = defineTask('validate-env', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Validate baseline (clean tree, on integration branch, smoke passes)',
  shell: {
    command: `set -e
if [ -n "$ALMA_PROD_API_KEY" ]; then
  echo "R8 violation: ALMA_PROD_API_KEY must not be set" >&2
  exit 2
fi
cd "${args.repoRoot}"
git diff --quiet || (echo "tree dirty" >&2; exit 2)
HEAD_BRANCH="$(git symbolic-ref --short HEAD)"
[ "$HEAD_BRANCH" = "chunk/${args.chunkName}" ] || (echo "expected on chunk/${args.chunkName}, on $HEAD_BRANCH" >&2; exit 2)
poetry run python scripts/smoke_import.py
`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const createSubBranchTask = defineTask('create-sub-branch', (args, taskCtx) => ({
  kind: 'shell',
  title: `Create sub-branch feat/${args.issueNumber}-${args.slug}`,
  shell: {
    command: `cd "${args.repoRoot}" && \
      git checkout chunk/${args.chunkName} && \
      git checkout -b feat/${args.issueNumber}-${args.slug}`,
    timeout: 15000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const staticGatesTask = defineTask('static-gates', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Static gates: py_compile + smoke_import',
  shell: {
    // Skip py_compile if no .py files changed; an empty `python -m py_compile`
    // call exits non-zero, which would falsely fail this gate for doc-only
    // commits.
    command: `cd "${args.repoRoot}" && \
      files=$(git diff --name-only chunk/${args.chunkName}...HEAD | grep '\\.py$' || true) && \
      if [ -n "$files" ]; then python -m py_compile $files; fi && \
      poetry run python scripts/smoke_import.py`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const scopeCheckTask = defineTask('scope-check', (args, taskCtx) => {
  // Write the files-to-touch list to a temp JSON file and pipe a payload
  // into `scope_check.py`'s CLI so we don't have to embed JSON inside a
  // `python -c "..."` shell-double-quoted string (where embedded `"` would
  // terminate the outer quote and break the shell).
  const filesPath = `${args.repoRoot}/chunks/${args.chunkName}/_files_to_touch_${args.issueNumber}.json`;
  return {
    kind: 'shell',
    title: 'Scope-check (R7): every changed file is in Files-to-touch',
    shell: {
      command: `set -e
mkdir -p "$(dirname "${filesPath}")"
cat > "${filesPath}" <<'JSON_EOF'
${JSON.stringify(args.filesToTouch, null, 2)}
JSON_EOF
cd "${args.repoRoot}"
DIFF_FILES_JSON="$(git diff --name-only chunk/${args.chunkName}...HEAD | python -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')"
FILES_TO_TOUCH_JSON="$(cat "${filesPath}")"
set +e
python -m scripts.agentic.scope_check <<PAYLOAD_EOF
{"diff_files": $DIFF_FILES_JSON, "files_to_touch": $FILES_TO_TOUCH_JSON}
PAYLOAD_EOF
RC=$?
rm -f "${filesPath}"
exit $RC
`,
      timeout: 30000,
    },
    io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  };
});

export const unitTestsTask = defineTask('unit-tests', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Unit tests for changed files',
  shell: {
    command: `cd "${args.repoRoot}" && poetry run pytest tests/unit/ --ignore=tests/unit/acquisition/test_extract_items.py -v --tb=short`,
    timeout: 300000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const contractTestTask = defineTask('contract-test', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Public API contract test',
  shell: {
    command: `cd "${args.repoRoot}" && poetry run pytest tests/test_public_api_contract.py -v`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const mergeIntoIntegrationTask = defineTask('merge-integration', (args, taskCtx) => ({
  kind: 'shell',
  title: `Merge feat/${args.issueNumber}-${args.slug} into integration branch`,
  shell: {
    command: `cd "${args.repoRoot}" && \
      git checkout chunk/${args.chunkName} && \
      git merge --no-ff feat/${args.issueNumber}-${args.slug} \
        -m "merge feat/${args.issueNumber}-${args.slug} into chunk/${args.chunkName}"`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// Lifecycle status transition. Shell-only so it stays cheap and deterministic.
// Heredoc keeps quoting safe even when lastEvent / nextAction contain spaces or
// punctuation.
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

// ---------- agent tasks ----------

export const implementTask = defineTask('implement', (args, taskCtx) => ({
  kind: 'agent',
  title: `Implement issue #${args.issueNumber} (attempt ${args.attempt || 1})`,
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer maintaining the almaapitk package',
      task: `Implement GitHub issue #${args.issueNumber} on branch feat/${args.issueNumber}-${args.slug}.`,
      context: {
        issueBody: args.issueBody,
        filesToTouch: args.filesToTouch,
        feedback: args.feedback || null,
        attemptNumber: args.attempt || 1,
        promptTemplatePath: 'scripts/agentic/prompts/implement.v1.md',
      },
      instructions: [
        'Read scripts/agentic/prompts/implement.v1.md and follow it strictly.',
        'Use AlmaAPIClient for HTTP. Validate inputs with AlmaValidationError.',
        'Use self.logger; never print.',
        'Type hints + Google-style docstrings on all public methods.',
        'Implement ONLY what the issue says.',
        'Do not modify any file not in Files to touch.',
        'Add unit tests under tests/unit/domains/ with mocked HTTP (responses or requests-mock).',
        'When done, list every file you changed.',
      ],
      outputFormat: 'JSON: { filesChanged: string[], summary: string, testsAdded: string[] }',
    },
    outputSchema: { type: 'object', required: ['filesChanged', 'summary'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const buildTestRecTask = defineTask('build-test-rec', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Build test-recommendation.json from chunk manifest + diff',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Test plan author',
      task: `Read:
- ${args.repoRoot}/chunks/${args.chunkName}/manifest.json (issues, ACs, endpoints, files)
- The diff: git diff main...chunk/${args.chunkName} (run via shell)
- ${args.repoRoot}/scripts/agentic/prompts/test-recommendation.v1.md (the rules)

Produce ${args.repoRoot}/chunks/${args.chunkName}/test-recommendation.json conforming to the schema in spec §6.1.

For each issue, every AC in the issue body must map to at least one test.id in acceptanceMapping. ACs that genuinely cannot be exercised against SANDBOX go in unmappable[] with a clear reason.

Return: { path, summary }`,
      outputFormat: 'JSON',
    },
    outputSchema: { type: 'object', required: ['path'] },
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

// ---------- main ----------

export async function process(inputs, ctx) {
  const { chunkName, repoRoot } = inputs;
  const maxAttempts = inputs.maxAttempts || 3; // R6
  if (!chunkName) throw new Error('chunkName is required');
  if (!repoRoot) throw new Error('repoRoot is required');

  ctx.log(`chunk-impl for ${chunkName} (max ${maxAttempts} attempts per issue)`);

  // Read manifest
  const manifest = JSON.parse(
    readFileSync(`${repoRoot}/chunks/${chunkName}/manifest.json`, 'utf8')
  );

  await ctx.task(validateEnvTask, { repoRoot, chunkName });

  const merged = [];
  for (const issue of manifest.issues) {
    const slug = (issue.title || '').toLowerCase()
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 30);
    const subBranch = `feat/${issue.number}-${slug}`;

    await ctx.task(createSubBranchTask, {
      repoRoot, chunkName, issueNumber: issue.number, slug,
    });

    let feedback = null;
    let success = false;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      await ctx.task(implementTask, {
        repoRoot, issueNumber: issue.number, slug,
        issueBody: issue.body_raw,
        filesToTouch: issue.files_to_touch,
        feedback, attempt,
      });

      // Run gates as plain awaits with explicit pass-checking on each
      // resolved result. We DO NOT wrap individual awaits in try/catch —
      // the SDK's pending-effect signal interferes with that pattern and
      // causes spurious "gate failed" branches when an effect is simply
      // not yet resolved.
      //
      // Convention: each shell task's posted output.json includes
      // {"exitCode": N}. exitCode === 0 means pass; anything else is a
      // gate failure that should drive the next refinement attempt.
      const gateChain = [
        ['static', staticGatesTask, { repoRoot, chunkName }],
        ['scope', scopeCheckTask, {
          repoRoot, chunkName,
          issueNumber: issue.number,
          filesToTouch: issue.files_to_touch,
        }],
        ['unit', unitTestsTask, { repoRoot }],
        ['contract', contractTestTask, { repoRoot }],
      ];
      let firstFailedGate = null;
      let firstFailedExit = 0;
      for (const [gateName, gateTask, gateArgs] of gateChain) {
        const result = await ctx.task(gateTask, gateArgs);
        const exitCode = (result && typeof result === 'object'
          ? (result.exitCode ?? 0)
          : 0);
        if (exitCode !== 0) {
          firstFailedGate = gateName;
          firstFailedExit = exitCode;
          break;
        }
      }
      if (firstFailedGate === null) {
        success = true;
        break;
      }
      feedback = `attempt ${attempt} failed at ${firstFailedGate}-gate (exit=${firstFailedExit})`;
      ctx.log(feedback);
    }

    if (!success) {
      // Convention across this repo's processes is question/title/context with
      // an `approved` + `response` reply (see pypi-publish-0.3.0.js,
      // verify-analytics-ui.js).
      const decision = await ctx.breakpoint({
        question: `Issue #${issue.number} exhausted ${maxAttempts} attempts. Reply with one of: "manual" (operator will take over and resume from merge), "drop" (skip this issue, continue), "abort" (stop the entire chunk).`,
        title: `Issue #${issue.number} — refinement loop exhausted`,
        context: {
          chunk: chunkName,
          issueNumber: issue.number,
          maxAttempts,
          lastFeedback: feedback,
        },
        tags: ['chunk-impl', 'r6-exhausted'],
      });
      const reply = String(decision.response || '').trim().toLowerCase();
      if (reply === 'abort') {
        throw new Error(`chunk aborted by operator at issue #${issue.number}`);
      }
      if (reply === 'drop') {
        ctx.log(`dropped issue #${issue.number}`);
        continue;
      }
      // anything else (including "manual") → fall through to merge
    }

    await ctx.task(mergeIntoIntegrationTask, {
      repoRoot, chunkName, issueNumber: issue.number, slug,
    });
    merged.push(subBranch);
  }

  const testRec = await ctx.task(buildTestRecTask, { repoRoot, chunkName });

  // Lifecycle: implementation done; the chunk is ready for the test process.
  await ctx.task(transitionStatusTask, {
    repoRoot, chunkName,
    newStage: 'impl-done',
    lastEvent: 'implementation complete; test-recommendation.json written',
    nextAction: `trigger \`chunks run-test ${chunkName}\` when ready`,
  });

  return {
    mergedSubBranches: merged,
    testRecommendationPath: testRec.path,
  };
}
