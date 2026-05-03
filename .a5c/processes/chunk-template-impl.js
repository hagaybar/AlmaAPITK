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
    command: `cd "${args.repoRoot}" && \
      python -m py_compile $(git diff --name-only chunk/${args.chunkName}...HEAD | grep '\\.py$' || true) && \
      poetry run python scripts/smoke_import.py`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const scopeCheckTask = defineTask('scope-check', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Scope-check (R7): every changed file is in Files-to-touch',
  shell: {
    command: `cd "${args.repoRoot}" && \
      python -c "
import json, sys, subprocess
from scripts.agentic.scope_check import check_scope
diff = subprocess.run(['git','diff','--name-only','chunk/${args.chunkName}...HEAD'],
                     capture_output=True,text=True,check=True).stdout.split()
files = ${JSON.stringify(args.filesToTouch)}
result = check_scope([f for f in diff if f.strip()], files)
print(json.dumps(result))
sys.exit(0 if result['pass'] else 2)
"`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const unitTestsTask = defineTask('unit-tests', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Unit tests for changed files',
  shell: {
    command: `cd "${args.repoRoot}" && poetry run pytest tests/unit/ -v --tb=short`,
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

      let stage = 'static';
      try {
        await ctx.task(staticGatesTask, { repoRoot, chunkName });
        stage = 'scope';
        await ctx.task(scopeCheckTask, {
          repoRoot, chunkName, filesToTouch: issue.files_to_touch,
        });
        stage = 'unit';
        await ctx.task(unitTestsTask, { repoRoot });
        stage = 'contract';
        await ctx.task(contractTestTask, { repoRoot });
        success = true;
        break;
      } catch (e) {
        feedback = `attempt ${attempt} failed at ${stage}-gate: ${e.message || e}`;
        ctx.log(feedback);
      }
    }

    if (!success) {
      const decision = await ctx.breakpoint({
        title: `Issue #${issue.number} exhausted ${maxAttempts} attempts`,
        options: [
          { value: 'manual', label: 'I will take over manually; resume from merge' },
          { value: 'drop', label: 'Drop this issue from the chunk; continue with next' },
          { value: 'abort', label: 'Abort the entire chunk' },
        ],
      });
      if (decision.value === 'abort') {
        throw new Error(`chunk aborted by operator at issue #${issue.number}`);
      }
      if (decision.value === 'drop') {
        ctx.log(`dropped issue #${issue.number}`);
        continue;
      }
      // manual fall-through to merge
    }

    await ctx.task(mergeIntoIntegrationTask, {
      repoRoot, chunkName, issueNumber: issue.number, slug,
    });
    merged.push(subBranch);
  }

  const testRec = await ctx.task(buildTestRecTask, { repoRoot, chunkName });

  return {
    mergedSubBranches: merged,
    testRecommendationPath: testRec.path,
  };
}
