/**
 * @process pypi-publish-0.3.0
 * @description First PyPI publish of almaapitk 0.3.0 — orchestrates the spec/plan at
 *   docs/superpowers/specs/2026-04-27-pypi-publishing-design.md and
 *   docs/superpowers/plans/2026-04-27-pypi-publishing.md. Five phases: audit,
 *   pre-flight, TestPyPI dry run, PyPI publish (with explicit deploy gate per user
 *   profile alwaysBreakOn=[deploy,external-api-cost]), housekeeping. Each plan task
 *   maps to an agent or shell effect; user breakpoints retained at audit triage,
 *   TestPyPI verification, pre-PyPI deploy authorization, PyPI verification, and
 *   token rotation.
 * @inputs { planPath: string, repoRoot: string, version: string }
 * @outputs { success: boolean, version: string, pypiUrl: string, releaseUrl: string, followupIssueUrl: string }
 * @skill general-purpose
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

const PROJECT_ROOT = '/home/hagaybar/projects/AlmaAPITK';

export async function process(inputs, ctx) {
  const {
    planPath = `${PROJECT_ROOT}/docs/superpowers/plans/2026-04-27-pypi-publishing.md`,
    repoRoot = PROJECT_ROOT,
    version = '0.3.0'
  } = inputs;

  const startTime = ctx.now();
  ctx.log('info', `Starting PyPI first-publish orchestration: almaapitk ${version}`);
  ctx.log('info', `Plan: ${planPath}`);

  // ---------------------------------------------------------------------------
  // Pre-flight verification (Plan task P.1)
  // Fails fast if prereqs P1-P8 not met or env not consistent.
  // ---------------------------------------------------------------------------
  ctx.log('info', 'Pre-flight: verifying prerequisites P1-P8');
  const preflight = await ctx.task(preflightTask, { planPath, repoRoot });
  if (!preflight.allPassed) {
    throw new Error(`Pre-flight failed: ${preflight.failureReason}`);
  }

  // ---------------------------------------------------------------------------
  // Phase 0 — Audit (Plan tasks 0.1-0.9)
  // ---------------------------------------------------------------------------
  ctx.log('info', 'Phase 0: running pre-publish audit');
  const auditResults = await ctx.task(runAuditTask, { planPath, repoRoot });
  const auditReport = await ctx.task(compileAuditReportTask, {
    planPath,
    repoRoot,
    auditOutputs: auditResults.outputPaths
  });

  // BP1: User triages findings (Plan task 0.8)
  const triage = await ctx.breakpoint({
    question: `Audit complete. Findings written to ${auditReport.reportPath}. Reply with which 🔴 / 🟡 / 🟢 items to fix vs defer.`,
    title: 'Phase 0 — Audit Triage',
    context: {
      runId: ctx.runId,
      reportPath: auditReport.reportPath,
      counts: auditResults.counts,
      files: [{ path: auditReport.reportPath, format: 'markdown' }]
    },
    expert: 'owner',
    tags: ['audit-gate', 'critical-decision']
  });
  if (!triage.approved) {
    throw new Error(`Audit triage rejected: ${triage.response || 'no reason given'}`);
  }

  // Apply fixes (or skip if user said none / clean) (Plan task 0.9)
  if (triage.response && /fix|address|patch|🔴|🟡/i.test(triage.response)) {
    await ctx.task(applyAuditFixesTask, {
      planPath,
      repoRoot,
      userTriage: triage.response,
      auditReportPath: auditReport.reportPath
    });
  } else {
    ctx.log('info', 'Phase 0.9 skipped: user triage indicates no fixes required');
  }

  // ---------------------------------------------------------------------------
  // Phase 1 — Pre-flight / packaging hygiene (Plan tasks 1.1-1.9)
  // ---------------------------------------------------------------------------
  ctx.log('info', 'Phase 1: pre-flight packaging hygiene');

  await ctx.task(verifyPypiNameAvailableTask, { repoRoot });
  await ctx.task(bumpVersionTask, { planPath, repoRoot, version });
  await ctx.task(configureInclusionListTask, { planPath, repoRoot, version });
  await ctx.task(writeReleaseNotesTask, { planPath, repoRoot, version });
  await ctx.task(buildArtifactsTask, { repoRoot });
  await ctx.task(inspectArtifactsTask, { planPath, repoRoot, version });
  await ctx.task(twineCheckTask, { repoRoot });
  await ctx.task(createSmokeScriptsTask, { planPath, repoRoot });

  // ---------------------------------------------------------------------------
  // Phase 2 — TestPyPI dry run (Plan tasks 2.1-2.7)
  // ---------------------------------------------------------------------------
  ctx.log('info', 'Phase 2: TestPyPI dry run');

  await ctx.task(uploadTestPypiTask, { repoRoot });

  // BP2: TestPyPI visual verification (Plan task 2.2)
  const testpypiOk = await ctx.breakpoint({
    question: `TestPyPI upload succeeded. Open https://test.pypi.org/project/almaapitk/${version}/ — does the page render correctly (README, classifiers, version, license, project URLs)?`,
    title: 'Phase 2.2 — TestPyPI Visual Verification',
    context: {
      runId: ctx.runId,
      url: `https://test.pypi.org/project/almaapitk/${version}/`,
      checklist: [
        'README renders correctly',
        'Classifiers in sidebar (Beta, MIT, Python 3.12+)',
        'Project URLs clickable',
        `Version shows ${version}`,
        'License is MIT'
      ]
    },
    expert: 'owner',
    tags: ['testpypi-verification']
  });
  if (!testpypiOk.approved) {
    throw new Error(`TestPyPI verification rejected: ${testpypiOk.response || 'defect reported'}. Fix and re-run from Phase 1.`);
  }

  await ctx.task(runTestPypiSmokeTask, { planPath, repoRoot, version });

  // ---------------------------------------------------------------------------
  // Phase 3 — PyPI publish (Plan tasks 3.1-3.7)
  // ---------------------------------------------------------------------------
  ctx.log('info', 'Phase 3: pre-PyPI authorization gate');

  // BP3: Mandatory deploy gate (per user profile alwaysBreakOn = [deploy, external-api-cost]).
  // PyPI uploads are immutable; this is the last reversible moment.
  const okToPypi = await ctx.breakpoint({
    question: `Ready to publish almaapitk ${version} to real PyPI? **PyPI uploads are immutable** — once ${version} is on PyPI it stays forever (you can yank, but the file persists). TestPyPI smoke passed. Approve to proceed.`,
    title: 'Phase 3 — Deploy Authorization (IRREVERSIBLE)',
    context: {
      runId: ctx.runId,
      action: 'twine upload dist/* (real PyPI)',
      irreversible: true,
      testpypiVerified: true
    },
    expert: 'owner',
    tags: ['deploy', 'external-api-cost', 'irreversible']
  });
  if (!okToPypi.approved) {
    throw new Error(`User aborted before PyPI publish: ${okToPypi.response || 'no reason given'}`);
  }

  await ctx.task(uploadPypiTask, { repoRoot, version });

  // BP4: PyPI visual verification (Plan task 3.2)
  const pypiOk = await ctx.breakpoint({
    question: `PyPI upload succeeded. Open https://pypi.org/project/almaapitk/${version}/ — does the page render correctly? Reply OK to proceed to final smoke test, or describe defect (which means we plan a ${version.replace(/\.\d+$/, m => '.'+(parseInt(m.slice(1))+1))} release separately).`,
    title: 'Phase 3.2 — PyPI Visual Verification',
    context: {
      runId: ctx.runId,
      url: `https://pypi.org/project/almaapitk/${version}/`,
      immutable: true
    },
    expert: 'owner',
    tags: ['pypi-verification']
  });
  if (!pypiOk.approved) {
    ctx.log('warn', `PyPI verification reported defect: ${pypiOk.response}. Continuing to smoke test for diagnostics; ${version} stays on PyPI but a follow-up release will be needed.`);
  }

  await ctx.task(runPypiSmokeTask, { planPath, repoRoot, version });

  // ---------------------------------------------------------------------------
  // Phase 4 — Repo housekeeping (Plan tasks 4.1-4.6)
  // ---------------------------------------------------------------------------
  ctx.log('info', 'Phase 4: repo housekeeping');

  const tagAndRelease = await ctx.task(tagAndReleaseTask, { planPath, repoRoot, version });
  await ctx.task(verifyReadmeInstallTask, { repoRoot });
  await ctx.task(writeHowToReleaseTask, { planPath, repoRoot, version });

  // BP5: Token rotation (Plan task 4.5) — manual web UI work
  const rotated = await ctx.breakpoint({
    question: `Now that almaapitk ${version} is on PyPI and TestPyPI, rotate both broad-scope API tokens to project-scoped tokens (visit https://pypi.org/manage/account/token/ and https://test.pypi.org/manage/account/token/, revoke the broad tokens, generate project-scoped ones, paste into ~/.pypirc). Reply OK once both are rotated, or "skip" to defer.`,
    title: 'Phase 4.5 — Token Rotation (manual web UI)',
    context: {
      runId: ctx.runId,
      pypiTokenUrl: 'https://pypi.org/manage/account/token/',
      testpypiTokenUrl: 'https://test.pypi.org/manage/account/token/'
    },
    expert: 'owner',
    tags: ['security', 'manual-web-ui']
  });
  if (!rotated.approved) {
    ctx.log('warn', `Token rotation deferred: ${rotated.response}. Reminder: broad tokens should be rotated before next release.`);
  }

  const followup = await ctx.task(openFollowupIssueTask, { planPath, repoRoot, version });

  return {
    success: true,
    version,
    pypiUrl: `https://pypi.org/project/almaapitk/${version}/`,
    releaseUrl: tagAndRelease.releaseUrl,
    followupIssueUrl: followup.issueUrl,
    duration: ctx.now() - startTime,
    metadata: { processId: 'pypi-publish-0.3.0', timestamp: startTime }
  };
}

// ---------------------------------------------------------------------------
// Task definitions
// ---------------------------------------------------------------------------

const sharedAgentBoilerplate = (args, taskCtx, role, planSection, instructions) => ({
  kind: 'agent',
  agent: {
    name: 'general-purpose',
    prompt: {
      role,
      task: `Execute ${planSection} of the implementation plan at ${args.planPath}, in repo root ${args.repoRoot}.`,
      context: {
        ...args,
        absolute_plan_path: args.planPath,
        repo_root: args.repoRoot
      },
      instructions: [
        `1. Read the plan file at ${args.planPath} and locate ${planSection}.`,
        '2. Execute every Step in that section in order, using the exact commands shown.',
        '3. After each command, verify the output matches the "Expected:" line. If a command halts the plan ("HALT — ..."), stop and surface that condition to the orchestrator via the JSON output.',
        '4. Use the Bash tool for shell commands. Use Read/Edit/Write for file operations.',
        '5. Do NOT skip any verification step. Do NOT add extra steps not in the plan.',
        '6. If a command fails or output is unexpected, capture the actual output and decide: matches a documented HALT condition (set status=halt) vs. truly unexpected (set status=error).',
        ...instructions
      ],
      outputFormat: 'JSON matching the outputSchema'
    },
    outputSchema: {
      type: 'object',
      required: ['status', 'completedSteps'],
      properties: {
        status: { type: 'string', enum: ['ok', 'halt', 'error'] },
        completedSteps: { type: 'array', items: { type: 'string' } },
        haltReason: { type: 'string' },
        commitsMade: { type: 'array', items: { type: 'string' } },
        artifactPaths: { type: 'array', items: { type: 'string' } },
        notes: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
});

// Pre-flight P.1
export const preflightTask = defineTask('preflight', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'PyPI release engineer (pre-flight checks)', 'Task P.1 (Pre-flight Verification)', [
    '7. Steps 1-7 are all read-only verifications. Do not modify any files.',
    '8. Return status="halt" with a clear haltReason if ANY of P1-P8 prereqs are missing.',
    '9. Set allPassed=true only if all 7 steps pass. Include the actual outputs of each verification in notes.'
  ]),
  title: 'Pre-flight: verify P1-P8 prerequisites',
  agent: {
    ...sharedAgentBoilerplate(args, taskCtx, 'PyPI release engineer (pre-flight checks)', 'Task P.1', []).agent,
    outputSchema: {
      type: 'object',
      required: ['status', 'allPassed'],
      properties: {
        status: { type: 'string', enum: ['ok', 'halt', 'error'] },
        allPassed: { type: 'boolean' },
        failureReason: { type: 'string' },
        notes: { type: 'string' }
      }
    }
  }
}));

// Phase 0.1-0.6 — run all audit tools, save outputs to /tmp/audit-*.txt
export const runAuditTask = defineTask('run-audit', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Pre-publish audit engineer', 'Tasks 0.1, 0.2, 0.3, 0.4, 0.5, and 0.6 (Phase 0 audit tool runs and manual public-API review)', [
    '7. Install ruff/bandit/vulture in /tmp/almaapitk-audit-venv as Task 0.1 specifies.',
    '8. Run each tool in sequence; capture output to /tmp/audit-ruff.txt, /tmp/audit-bandit.txt, /tmp/audit-vulture.txt.',
    '9. Run grep sweeps to /tmp/audit-todo.txt, /tmp/audit-print.txt, /tmp/audit-identifying.txt.',
    '10. Perform manual public-API review of src/almaapitk/__init__.py and each domain class. Capture findings as bullet points in /tmp/audit-manual.txt.',
    '11. Return outputPaths (the seven /tmp/audit-*.txt paths) and counts (how many findings per category).'
  ]),
  title: 'Phase 0 audit: run ruff/bandit/vulture/grep + manual review',
  agent: {
    ...sharedAgentBoilerplate(args, taskCtx, 'Pre-publish audit engineer', 'Phase 0.1-0.6', []).agent,
    outputSchema: {
      type: 'object',
      required: ['status', 'outputPaths', 'counts'],
      properties: {
        status: { type: 'string', enum: ['ok', 'halt', 'error'] },
        outputPaths: { type: 'array', items: { type: 'string' } },
        counts: {
          type: 'object',
          properties: {
            ruffFindings: { type: 'number' },
            banditFindings: { type: 'number' },
            vultureFindings: { type: 'number' },
            todoLines: { type: 'number' },
            printLines: { type: 'number' },
            identifyingLines: { type: 'number' }
          }
        },
        notes: { type: 'string' }
      }
    }
  }
}));

// Phase 0.7 — compile audit findings markdown report
export const compileAuditReportTask = defineTask('compile-audit-report', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Audit report compiler', 'Task 0.7 (compile audit findings report)', [
    '7. Read /tmp/audit-*.txt files (paths in args.auditOutputs).',
    '8. Synthesize findings into the markdown template shown in plan Task 0.7 Step 1.',
    '9. Categorize each finding as 🔴 (block publish), 🟡 (should fix), or 🟢 (FYI).',
    '10. If a category has no findings, write "None found." (do not omit the heading).',
    '11. Substitute today\'s actual date for [YYYY-MM-DD].',
    '12. Write the file to docs/superpowers/specs/2026-04-27-pypi-publishing-audit-findings.md.',
    '13. Commit per Task 0.7 Step 2.',
    '14. Return reportPath = the absolute path of the created file.'
  ]),
  title: 'Phase 0.7: compile audit findings markdown',
  agent: {
    ...sharedAgentBoilerplate(args, taskCtx, 'Audit report compiler', 'Task 0.7', []).agent,
    outputSchema: {
      type: 'object',
      required: ['status', 'reportPath'],
      properties: {
        status: { type: 'string', enum: ['ok', 'halt', 'error'] },
        reportPath: { type: 'string' },
        commitSha: { type: 'string' },
        notes: { type: 'string' }
      }
    }
  }
}));

// Phase 0.9 — apply fixes the user agreed to
export const applyAuditFixesTask = defineTask('apply-audit-fixes', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Audit fix implementer', 'Task 0.9 (apply agreed audit fixes)', [
    '7. Read the user triage decision from args.userTriage.',
    '8. For each fix the user agreed to, edit the file, run `poetry run pytest tests/ -x` to confirm no regression, then `poetry run python scripts/smoke_import.py`, then commit with message `fix(audit): <one-line>`.',
    '9. After all fixes: re-verify `find src/almaapitk -type f ! -name "*.py" ! -path "*/__pycache__/*"` returns empty.',
    '10. Return list of commits made (SHAs or messages).'
  ]),
  title: 'Phase 0.9: apply user-agreed audit fixes'
}));

// Phase 1.1 — verify PyPI name availability
export const verifyPypiNameAvailableTask = defineTask('verify-pypi-name', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Phase 1.1: check PyPI name availability for almaapitk',
  shell: {
    command: `cd ${args.repoRoot} && HTTP=$(curl -s -o /dev/null -w '%{http_code}' https://pypi.org/pypi/almaapitk/json); echo "http=$HTTP"; if [ "$HTTP" = "404" ]; then echo "RESULT=FREE"; exit 0; elif [ "$HTTP" = "200" ]; then echo "RESULT=TAKEN"; exit 1; else echo "RESULT=ERROR"; exit 2; fi`,
    timeout: 30000
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` }
}));

// Phase 1.2 — bump version
export const bumpVersionTask = defineTask('bump-version', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Version bumper', `Task 1.2 (bump version to ${args.version})`, [
    `7. Edit pyproject.toml: change version line to "${args.version}".`,
    '8. Verify the change with grep.',
    `9. Commit per Task 1.2 Step 3 with message "Bump version to ${args.version} for first PyPI release".`
  ]),
  title: `Phase 1.2: bump version to ${args.version}`
}));

// Phase 1.3 — configure inclusion list
export const configureInclusionListTask = defineTask('configure-inclusion-list', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Packaging configuration engineer', `Task 1.3 (configure inclusion list for ${args.version})`, [
    '7. Edit pyproject.toml: insert the include and exclude blocks AFTER the existing `packages = [...]` line within the `[tool.poetry]` section. The release-notes path in `include` must be `docs/releases/0.3.0.md`.',
    '8. Validate TOML syntax via the Python tomllib check.',
    '9. Commit per Task 1.3 Step 3.',
    '10. Note: Per spec §17, Poetry 2.x include/exclude semantics are fiddly. If Phase 1.7 inspection later shows the sdist is wrong, the orchestrator will return here.'
  ]),
  title: `Phase 1.3: configure pyproject.toml inclusion list for ${args.version}`
}));

// Phase 1.4 — release notes
export const writeReleaseNotesTask = defineTask('write-release-notes', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Release-notes writer', `Task 1.4 (release notes for ${args.version})`, [
    `7. Create directory docs/releases/ if missing.`,
    `8. Write docs/releases/${args.version}.md with the full template content shown in Task 1.4 Step 2 of the plan.`,
    '9. Substitute today\'s actual date for [YYYY-MM-DD] in the "Release date:" line.',
    '10. Commit per Task 1.4 Step 3.'
  ]),
  title: `Phase 1.4: write release notes ${args.version}.md`
}));

// Phase 1.5 — build artifacts
export const buildArtifactsTask = defineTask('build-artifacts', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Phase 1.5: poetry build (clean dist + build wheel and sdist)',
  shell: {
    command: `cd ${args.repoRoot} && rm -rf dist/ && poetry build && ls -la dist/`,
    timeout: 120000
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` }
}));

// Phase 1.6 + 1.7 — inspect both wheel and sdist contents
export const inspectArtifactsTask = defineTask('inspect-artifacts', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Build artifact inspector', `Tasks 1.6 and 1.7 (inspect wheel and sdist for ${args.version})`, [
    '7. Run unzip -l dist/almaapitk-0.3.0-py3-none-any.whl and the awk-grep verification from Task 1.6 Step 2.',
    '8. Run tar -tzf dist/almaapitk-0.3.0.tar.gz and the grep verification from Task 1.7 Step 3.',
    '9. If either shows unexpected content, return status=halt with haltReason describing what slipped in. Do NOT silently fix the pyproject.toml — surface the issue and let the orchestrator decide.',
    '10. Successful pass requires BOTH "OK: clean wheel" AND "OK: clean sdist".'
  ]),
  title: `Phase 1.6/1.7: inspect ${args.version} wheel and sdist contents`
}));

// Phase 1.8 — twine check
export const twineCheckTask = defineTask('twine-check', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Phase 1.8: twine check (validate metadata and README rendering)',
  shell: {
    command: `cd ${args.repoRoot} && pipx run twine check dist/*`,
    timeout: 90000
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` }
}));

// Phase 1.9 — create smoke scripts + example config + .gitignore
export const createSmokeScriptsTask = defineTask('create-smoke-scripts', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Smoke-script author', 'Task 1.9 (create scripts/post_publish/ smoke tests)', [
    '7. Create the four files exactly as shown in Task 1.9 Steps 1-5: 01_test_connection.py, 02_get_bib.py, 03_analytics_headers.py, smoke_config.example.json, .gitignore.',
    '8. Verify scripts/post_publish/smoke_config.json (already created locally on 2026-04-27 with sandbox MMS 990025559030204146 and the URL-encoded analytics report path) is gitignored.',
    '9. Run all three smoke scripts locally via `poetry run python ...` to confirm they work BEFORE the publish (Task 1.9 Step 7). Each must print exactly one OK line.',
    '10. Stage only the four committed files and commit per Task 1.9 Step 8. Confirm git log -1 --stat does NOT list smoke_config.json.'
  ]),
  title: 'Phase 1.9: create smoke scripts and gitignore-protect smoke_config.json'
}));

// Phase 2.1 — TestPyPI upload
export const uploadTestPypiTask = defineTask('upload-testpypi', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Phase 2.1: twine upload to TestPyPI',
  shell: {
    command: `cd ${args.repoRoot} && pipx run twine upload --repository testpypi dist/*`,
    timeout: 180000
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` }
}));

// Phase 2.3-2.7 — TestPyPI smoke (fresh venv + install + 3 scripts + cleanup)
export const runTestPypiSmokeTask = defineTask('testpypi-smoke', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Post-publish smoke tester (TestPyPI)', 'Tasks 2.3, 2.4, 2.5, 2.6, 2.7 (TestPyPI fresh-venv smoke test)', [
    '7. Create fresh venv at /tmp/almaapitk-smoke-testpypi/ (rm -rf first).',
    '8. Install almaapitk==0.3.0 from TestPyPI with --extra-index-url for real-PyPI deps (per Task 2.3 Step 2).',
    '9. Confirm pip show reports Name: almaapitk and Version: 0.3.0.',
    '10. Run all three smoke scripts via /tmp/almaapitk-smoke-testpypi/bin/python scripts/post_publish/0X_*.py. Each must print exactly one OK line.',
    '11. Cleanup: rm -rf /tmp/almaapitk-smoke-testpypi.',
    '12. Return status=halt with a clear haltReason if ANY script fails — packaging is wrong somehow.'
  ]),
  title: `Phase 2.3-2.7: TestPyPI install + smoke test for ${args.version}`
}));

// Phase 3.1 — PyPI upload
export const uploadPypiTask = defineTask('upload-pypi', (args, taskCtx) => ({
  kind: 'shell',
  title: `Phase 3.1: twine upload to real PyPI (DEPLOY ${args.version})`,
  shell: {
    command: `cd ${args.repoRoot} && pipx run twine upload dist/*`,
    timeout: 180000
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` }
}));

// Phase 3.3-3.7 — PyPI smoke
export const runPypiSmokeTask = defineTask('pypi-smoke', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Post-publish smoke tester (PyPI)', 'Tasks 3.3, 3.4, 3.5, 3.6, 3.7 (PyPI fresh-venv smoke test)', [
    '7. Create SECOND fresh venv at /tmp/almaapitk-smoke-pypi/.',
    '8. Install almaapitk==0.3.0 from real PyPI (no -i flag).',
    '9. Confirm pip show reports Name: almaapitk and Version: 0.3.0.',
    '10. Run all three smoke scripts. Each must print exactly one OK line.',
    '11. Cleanup: rm -rf /tmp/almaapitk-smoke-pypi.'
  ]),
  title: `Phase 3.3-3.7: PyPI install + smoke test for ${args.version}`
}));

// Phase 4.1 + 4.2 — tag and GitHub Release
export const tagAndReleaseTask = defineTask('tag-and-release', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Release tag/notes engineer', `Tasks 4.1 and 4.2 (tag v${args.version}, push, create GitHub Release)`, [
    `7. Create annotated tag v${args.version} per Task 4.1 Step 1.`,
    `8. Push tag per Task 4.1 Step 2.`,
    `9. Create GitHub Release using gh per Task 4.2 Step 1, with notes-file docs/releases/${args.version}.md and --latest.`,
    '10. Capture the release URL from gh output and return as releaseUrl.'
  ]),
  title: `Phase 4.1-4.2: tag v${args.version} + GitHub Release`,
  agent: {
    ...sharedAgentBoilerplate(args, taskCtx, 'Release tag/notes engineer', `Tasks 4.1 and 4.2`, []).agent,
    outputSchema: {
      type: 'object',
      required: ['status', 'releaseUrl'],
      properties: {
        status: { type: 'string', enum: ['ok', 'halt', 'error'] },
        releaseUrl: { type: 'string' },
        notes: { type: 'string' }
      }
    }
  }
}));

// Phase 4.3 — verify README
export const verifyReadmeInstallTask = defineTask('verify-readme-install', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Phase 4.3: confirm README has pip install almaapitk',
  shell: {
    command: `cd ${args.repoRoot} && grep -n "pip install almaapitk" README.md`,
    timeout: 10000
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` }
}));

// Phase 4.4 — write HOW_TO_RELEASE.md
export const writeHowToReleaseTask = defineTask('write-how-to-release', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Release-recipe writer', 'Task 4.4 (write HOW_TO_RELEASE.md)', [
    '7. Write docs/releases/HOW_TO_RELEASE.md with the full content from Task 4.4 Step 1.',
    '8. Commit and push per Task 4.4 Step 2.'
  ]),
  title: 'Phase 4.4: write HOW_TO_RELEASE.md'
}));

// Phase 4.6 — open follow-up issue for Approach 3
export const openFollowupIssueTask = defineTask('open-followup-issue', (args, taskCtx) => ({
  ...sharedAgentBoilerplate(args, taskCtx, 'Issue opener', 'Task 4.6 (open follow-up issue for Approach 3)', [
    '7. Write the issue body to /tmp/approach3-issue.md per Task 4.6 Step 1.',
    '8. Run gh issue create per Task 4.6 Step 2. If --label fails, retry without --label.',
    '9. Capture the issue URL from gh output as issueUrl.',
    '10. Cleanup /tmp/approach3-issue.md.'
  ]),
  title: 'Phase 4.6: open follow-up issue for Approach 3 (Trusted Publisher / OIDC)',
  agent: {
    ...sharedAgentBoilerplate(args, taskCtx, 'Issue opener', 'Task 4.6', []).agent,
    outputSchema: {
      type: 'object',
      required: ['status', 'issueUrl'],
      properties: {
        status: { type: 'string', enum: ['ok', 'halt', 'error'] },
        issueUrl: { type: 'string' },
        notes: { type: 'string' }
      }
    }
  }
}));
