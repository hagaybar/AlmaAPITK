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

// Issue #90: harvest documented Alma error codes for the swagger domains
// implied by this issue's Files-to-touch / endpoints, and write them to a
// per-issue sidecar file so the implement-agent prompt can read them as
// context.swaggerErrors. Failure to fetch (e.g. dev-network outage) is
// non-fatal — we write an empty result and exit 0 so the chunk continues;
// the new acceptance criterion ("swagger error codes accounted for") is
// then a degraded best-effort instead of a hard block.
//
// The shell pattern mirrors `denyPathsTask`: stage the issue context to a
// temp JSON file, then run a single-quoted Python heredoc that reads the
// staged file. This keeps the JS template literal simple and avoids
// quoting cliffs.
export const fetchSwaggerCodesTask = defineTask('fetch-swagger-codes', (args, taskCtx) => {
  const stagingPath = `${args.repoRoot}/chunks/${args.chunkName}/_swagger_input_${args.issueNumber}.json`;
  const sidecarPath = `${args.repoRoot}/chunks/${args.chunkName}/_swagger_errors_${args.issueNumber}.json`;
  return {
    kind: 'shell',
    title: `Harvest documented Alma error codes for issue #${args.issueNumber}`,
    shell: {
      command: `set -e
mkdir -p "$(dirname "${stagingPath}")"
cat > "${stagingPath}" <<'JSON_EOF'
${JSON.stringify({
  issueNumber: args.issueNumber,
  files_to_touch: args.filesToTouch || [],
  endpoints: args.endpoints || [],
  domain: args.domainHeader || '',
  sidecarPath,
}, null, 2)}
JSON_EOF
cd "${args.repoRoot}"
python <<'PYEOF'
import json
from pathlib import Path
from scripts.agentic.issue_parser import infer_swagger_domains
from scripts.error_codes.fetch_domain_codes import build_report, fetch_swagger

stage = json.loads(Path(${JSON.stringify(stagingPath)}).read_text())
domains = infer_swagger_domains({
    "files_to_touch": stage.get("files_to_touch") or [],
    "endpoints": stage.get("endpoints") or [],
    "domain": stage.get("domain") or "",
})
out = {"issueNumber": stage["issueNumber"], "domains": domains, "reports": []}
for d in domains:
    try:
        sw = fetch_swagger(d)
        out["reports"].append(build_report(d, sw))
    except Exception as exc:
        out["reports"].append({"domain": d, "error": str(exc), "codes": []})
Path(stage["sidecarPath"]).write_text(json.dumps(out, indent=2) + "\\n", encoding="utf-8")
print(f"swagger-codes: domains={domains} sidecar={stage['sidecarPath']}")
PYEOF
rm -f "${stagingPath}"
`,
      timeout: 60000,
    },
    io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  };
});

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

export const denyPathsTask = defineTask('deny-paths', (args, taskCtx) => {
  // Phase 1 of the guardrails registry: instead of an allow-list scope-check,
  // we run a tiny deny-list against the diff. The deny-list lives in
  // guardrails.json (enforced.deny_paths). See
  // docs/superpowers/plans/2026-05-06-guardrails-registry-phase-1.md.
  return {
    kind: 'shell',
    title: 'Deny-paths gate (guardrails.json enforced.deny_paths)',
    shell: {
      command: `set -e
cd "${args.repoRoot}"
DIFF_FILES_JSON="$(git diff --name-only chunk/${args.chunkName}...HEAD | python -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')"
set +e
python -m scripts.agentic.guardrails deny-paths --registry guardrails.json <<PAYLOAD_EOF
{"diff_files": $DIFF_FILES_JSON}
PAYLOAD_EOF
exit $?
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
    command: `cd "${args.repoRoot}" && poetry run pytest tests/unit/ --ignore=tests/unit/acquisition/test_extract_items.py --ignore=tests/unit/domains/test_admin.py --ignore=tests/unit/utils/test_tsv_generator.py -v --tb=short`,
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
        // Issue #90: per-issue swagger error-code harvest sidecar (path
        // relative to repoRoot). When the inferred swagger domain set was
        // empty or fetch failed, the file's `reports` array may be empty
        // — treat that as "no documented codes available", not a failure.
        swaggerErrorsPath: args.swaggerErrorsPath || null,
      },
      instructions: [
        'Read scripts/agentic/prompts/implement.v1.md and follow it strictly.',
        'Use AlmaAPIClient for HTTP. Validate inputs with AlmaValidationError.',
        'Use self.logger; never print.',
        'Type hints + Google-style docstrings on all public methods.',
        'Implement ONLY what the issue says.',
        'Do not modify any file not in Files to touch.',
        'Add unit tests under tests/unit/domains/ with mocked HTTP (responses or requests-mock).',
        'When you commit, reference the issue with "Refs #N" — NEVER use "Closes #N", "Fixes #N", or "Resolves #N". GitHub auto-closes from any merged commit body, which would bypass R4 (auto-close only on perfect-green / no unmappable ACs). Issue closure is a manual operator step.',
        'If context.swaggerErrorsPath is non-null, read that JSON file and cross-check ERROR_CODE_REGISTRY in src/almaapitk/client/AlmaAPIClient.py against the documented codes whose declaring endpoints overlap your "API endpoints touched". Map any code that carries enough semantics for a typed subclass; for codes you choose not to map, the bare AlmaAPIError fallback is acceptable.',
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

    // Issue #90: harvest documented Alma error codes for the swagger
    // domains this issue touches BEFORE the implement agent runs, so its
    // prompt can read the sidecar via context.swaggerErrorsPath. Runs once
    // per issue; the implement agent can then iterate attempts against the
    // same harvest. Failure inside the task is non-fatal — the sidecar may
    // contain an empty `reports` array.
    await ctx.task(fetchSwaggerCodesTask, {
      repoRoot, chunkName,
      issueNumber: issue.number,
      filesToTouch: issue.files_to_touch,
      endpoints: issue.endpoints,
      domainHeader: issue.domain || '',
    });
    const swaggerErrorsPath = `chunks/${chunkName}/_swagger_errors_${issue.number}.json`;

    let feedback = null;
    let success = false;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      await ctx.task(implementTask, {
        repoRoot, issueNumber: issue.number, slug,
        issueBody: issue.body_raw,
        filesToTouch: issue.files_to_touch,
        swaggerErrorsPath,
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
        ['deny-paths', denyPathsTask, { repoRoot, chunkName }],
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
