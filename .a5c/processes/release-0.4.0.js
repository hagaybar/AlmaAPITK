/**
 * @process release-0.4.0
 * @description Cut and publish almaapitk 0.4.0 to PyPI per the plan at
 *   docs/superpowers/plans/2026-05-10-release-0.4.0-implementation.md.
 *   Linear pipeline with three operator breakpoints: (1) before TestPyPI
 *   publish, (2) before opening release PR, (3) before real PyPI publish
 *   (IRREVERSIBLE). All tasks are shell or agent — no node kind.
 * @inputs { repoRoot: string, version: string, prevVersion: string }
 * @outputs { success: boolean, prUrl: string|null, releaseUrl: string|null }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

// ---------------------------------------------------------------------------
// Task 1 — preflight: confirm clean tree, on main, users-requests merged
// ---------------------------------------------------------------------------
export const preflightTask = defineTask('preflight', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Preflight: clean tree, on main, users-requests merged',
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
HEAD_BRANCH="$(git symbolic-ref --short HEAD)"
[ "$HEAD_BRANCH" = "main" ] || (echo "preflight FAIL: expected main, on $HEAD_BRANCH" >&2; exit 2)
git fetch origin
git diff --quiet || (echo "preflight FAIL: working tree dirty" >&2; git status -s >&2; exit 2)
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})
[ "$LOCAL" = "$REMOTE" ] || (echo "preflight FAIL: local main not synced with origin/main" >&2; exit 2)
git log --oneline -10 main | grep -q "Refs #41" || (echo "preflight FAIL: users-requests (#41) commit not found in last 10 commits on main" >&2; exit 2)
echo "preflight OK on main, clean, synced, users-requests present"
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'preflight'],
}));

// ---------------------------------------------------------------------------
// Task 2 — open release/0.4.0 branch
// ---------------------------------------------------------------------------
export const openReleaseBranchTask = defineTask('open-release-branch', (args, taskCtx) => ({
  kind: 'shell',
  title: `Open release branch release/${args.version}`,
  shell: {
    command: `set -e
cd "${args.repoRoot}"
git checkout main && git pull
git checkout -b release/${args.version} 2>&1 || git checkout release/${args.version}
git branch --show-current | grep -q "^release/${args.version}$" || (echo "branch checkout failed" >&2; exit 2)
echo "on release/${args.version}"
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'git'],
}));

// ---------------------------------------------------------------------------
// Task 3 — update CHANGELOG.md (agent — multi-step text edits)
// ---------------------------------------------------------------------------
export const updateChangelogTask = defineTask('update-changelog', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update CHANGELOG.md for 0.4.0 release',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Release engineer editing CHANGELOG.md',
      task: 'Apply Task 2 of the release plan exactly as specified',
      context: { ...args, planPath: 'docs/superpowers/plans/2026-05-10-release-0.4.0-implementation.md' },
      instructions: [
        `Read the release plan at ${args.repoRoot}/docs/superpowers/plans/2026-05-10-release-0.4.0-implementation.md and follow Task 2 sub-steps 2.1 through 2.8 EXACTLY.`,
        `Open ${args.repoRoot}/CHANGELOG.md.`,
        `Step 2.1: Append 9 new bullets to the existing ### Added section under ## [Unreleased]. Use the EXACT bullet text from the plan (Admin.Sets, Configuration org/locations, code-tables, letters, Users.list/search, Users.create/delete, Users grab-bag, Users loans, Users requests).`,
        `Step 2.2: Append 1 bullet to existing ### Fixed section: Configuration.update_letter XML body fix (issue #114).`,
        `Step 2.3: Append 1 bullet to existing ### Removed section: BibliographicRecords.search_records removed (commit 72b0d93).`,
        `Step 2.4: Rename ## [Unreleased] heading to ## [0.4.0] — 2026-05-10.`,
        `Step 2.5: Insert a fresh empty ## [Unreleased] heading above the renamed [0.4.0] heading.`,
        `Step 2.6: Update link references at bottom of file. Add [0.4.0]: ...releases/tag/v0.4.0 and change [Unreleased]: ...compare/v0.3.1...HEAD to .../compare/v0.4.0...HEAD.`,
        `Step 2.7: Sanity check by running: awk '/^## \\[/' CHANGELOG.md — output should be in order: ## [Unreleased], ## [0.4.0] — 2026-05-10, ## [0.3.1] — 2026-04-27.`,
        `Step 2.8: Stage and commit with the exact commit message from the plan.`,
        `R9 reminder: do NOT include any operator-supplied identifiers in the commit message or changelog content.`,
        `After committing, return JSON describing what you did.`,
      ],
      outputFormat: 'JSON',
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'commitSha'],
      properties: {
        success: { type: 'boolean' },
        commitSha: { type: 'string' },
        bulletsAdded: { type: 'object' },
        notes: { type: 'string' },
      },
    },
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`,
  },
  labels: ['release', 'changelog'],
}));

// ---------------------------------------------------------------------------
// Task 4 — bump version in pyproject.toml
// ---------------------------------------------------------------------------
export const bumpVersionTask = defineTask('bump-version', (args, taskCtx) => ({
  kind: 'shell',
  title: `Bump version ${args.prevVersion} → ${args.version}`,
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
COUNT=$(grep -c '0\\.3\\.1' pyproject.toml)
[ "$COUNT" = "1" ] || (echo "expected 1 occurrence of 0.3.1 in pyproject.toml, found $COUNT" >&2; exit 2)
sed -i 's/^version = "${args.prevVersion}"$/version = "${args.version}"/' pyproject.toml
grep -q '^version = "${args.version}"$' pyproject.toml || (echo "version bump failed" >&2; exit 2)
git add pyproject.toml
git commit -m "chore(release): bump version to ${args.version}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git log -1 --oneline
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'version-bump'],
}));

// ---------------------------------------------------------------------------
// Task 5 — validation suite (poetry install, smoke, contract, units, regression)
// ---------------------------------------------------------------------------
export const validationSuiteTask = defineTask('validation-suite', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Run full validation suite (smoke + units + regression-smoke)',
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
echo "=== 5.1 poetry install --sync ==="
poetry install --sync
echo "=== 5.2 smoke import ==="
poetry run python scripts/smoke_import.py
echo "=== 5.3 public API contract ==="
poetry run pytest tests/test_public_api_contract.py -v
echo "=== 5.4 unit + logging + client integration suites ==="
poetry run pytest tests/unit/ tests/logging/ tests/integration/client/ -v
echo "=== 5.5 R10 regression-smoke ==="
scripts/agentic/chunks regression-smoke
echo "=== validation-suite OK ==="
`,
    timeout: 1800000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'validation'],
}));

// ---------------------------------------------------------------------------
// Task 6 — build wheel and inspect contents
// ---------------------------------------------------------------------------
export const buildAndInspectTask = defineTask('build-and-inspect-wheel', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Build wheel and verify exclude-list is respected',
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
rm -rf dist/
poetry build
ls dist/
[ -f "dist/almaapitk-${args.version}-py3-none-any.whl" ] || (echo "wheel not found" >&2; exit 2)
[ -f "dist/almaapitk-${args.version}.tar.gz" ] || (echo "tarball not found" >&2; exit 2)
echo "=== wheel contents ==="
unzip -l dist/almaapitk-${args.version}-py3-none-any.whl
echo "=== verify exclude list ==="
LEAKED=""
for path in tests/ scripts/ \\.a5c/ logs/ config/ CLAUDE.md AGENTS.md; do
  if unzip -l dist/almaapitk-${args.version}-py3-none-any.whl | grep -qE "(^| )$path"; then
    LEAKED="$LEAKED $path"
  fi
done
if [ -n "$LEAKED" ]; then
  echo "wheel leaked paths:$LEAKED" >&2
  exit 2
fi
# docs/ is leaked into dist-info as expected (docs/releases/0.3.1.md per pyproject) — that's OK, just warn
if unzip -l dist/almaapitk-${args.version}-py3-none-any.whl | grep -qE "almaapitk-${args.version}.dist-info/.*docs"; then
  echo "(note: docs entry in dist-info is expected per pyproject include list)"
fi
echo "=== build-and-inspect OK ==="
`,
    timeout: 120000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'build'],
}));

// ---------------------------------------------------------------------------
// Task 7 — TestPyPI publish (after BREAKPOINT 1)
// ---------------------------------------------------------------------------
export const testpypiPublishTask = defineTask('testpypi-publish', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Publish to TestPyPI',
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
poetry publish -r testpypi
echo "=== testpypi-publish OK ==="
echo "verify at: https://test.pypi.org/project/almaapitk/${args.version}/"
`,
    timeout: 300000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'testpypi', 'deploy'],
}));

// ---------------------------------------------------------------------------
// Task 8 — TestPyPI install + smoke in a throwaway venv
// ---------------------------------------------------------------------------
export const testpypiSmokeTask = defineTask('testpypi-install-smoke', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Install from TestPyPI in throwaway venv and smoke-import',
  shell: {
    command: `set -e
cd "${args.repoRoot}"
TMPVENV=$(mktemp -d)/venv
python3.12 -m venv "$TMPVENV"
. "$TMPVENV/bin/activate"
pip install --upgrade pip
# Wait briefly for TestPyPI to index
sleep 30
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ almaapitk==${args.version}
python -c "from almaapitk import AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError, Admin, Users, BibliographicRecords, Acquisitions, ResourceSharing, Analytics, Configuration, TSVGenerator, CitationMetadataError; print('TESTPYPI IMPORT OK ${args.version}')"
deactivate
rm -rf "$(dirname "$TMPVENV")"
echo "=== testpypi-install-smoke OK ==="
`,
    timeout: 300000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'testpypi', 'smoke'],
}));

// ---------------------------------------------------------------------------
// Task 9 — push release branch, open and merge release PR
// ---------------------------------------------------------------------------
export const openAndMergePrTask = defineTask('open-and-merge-release-pr', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Push release branch, open PR, squash-merge',
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
git push -u origin release/${args.version}
PR_BODY=$(cat <<'PR_BODY_EOF'
## Summary
- CHANGELOG finalized for ${args.version} (architecture/infra issues #2-#22 plus Sets, Configuration concretes, Users coverage push)
- Version bumped from ${args.prevVersion} to ${args.version} in pyproject.toml

## Test plan
- [x] TestPyPI dry-run uploaded and installed in throwaway venv
- [x] Public API smoke + contract test pass
- [x] Full unit + logging + client integration suites pass
- [x] R10 regression-smoke passes
- [x] Wheel inspection confirms only almaapitk/ ships

## Post-merge actions
- Manual poetry publish to real PyPI
- git tag -a v${args.version} && git push --tags
- gh release create v${args.version}

🤖 Generated with [Claude Code](https://claude.com/claude-code)
PR_BODY_EOF
)
PR_URL=$(gh pr create --title "Release ${args.version}" --body "$PR_BODY" --base main --head release/${args.version})
echo "PR opened: $PR_URL"
gh pr merge "$PR_URL" --squash --delete-branch
git checkout main
git pull
git log --oneline -3
echo "=== open-and-merge-release-pr OK ==="
`,
    timeout: 180000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'github'],
}));

// ---------------------------------------------------------------------------
// Task 10 — rebuild on main to confirm artifacts match merged code
// ---------------------------------------------------------------------------
export const rebuildOnMainTask = defineTask('rebuild-on-main', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Rebuild wheel on main',
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
HEAD_BRANCH="$(git symbolic-ref --short HEAD)"
[ "$HEAD_BRANCH" = "main" ] || (echo "expected main, on $HEAD_BRANCH" >&2; exit 2)
rm -rf dist/
poetry build
ls dist/
[ -f "dist/almaapitk-${args.version}-py3-none-any.whl" ] || (echo "wheel not found" >&2; exit 2)
echo "=== rebuild-on-main OK ==="
`,
    timeout: 120000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'build'],
}));

// ---------------------------------------------------------------------------
// Task 11 — publish to real PyPI (IRREVERSIBLE)
// ---------------------------------------------------------------------------
export const publishToPypiTask = defineTask('publish-to-pypi', (args, taskCtx) => ({
  kind: 'shell',
  title: `IRREVERSIBLE: publish ${args.version} to real PyPI`,
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
poetry publish
echo "=== PyPI publish complete: https://pypi.org/project/almaapitk/${args.version}/ ==="
`,
    timeout: 300000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'pypi', 'deploy', 'irreversible'],
}));

// ---------------------------------------------------------------------------
// Task 12 — tag and push
// ---------------------------------------------------------------------------
export const tagAndPushTask = defineTask('tag-and-push', (args, taskCtx) => ({
  kind: 'shell',
  title: `Create and push tag v${args.version}`,
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
git checkout main && git pull
git tag -a v${args.version} -m "Release ${args.version}"
git push origin v${args.version}
git tag --list "v0.*" --sort=-creatordate | head -3
echo "=== tag-and-push OK ==="
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'git'],
}));

// ---------------------------------------------------------------------------
// Task 13 — create GitHub Release with changelog excerpt
// ---------------------------------------------------------------------------
export const createGithubReleaseTask = defineTask('create-github-release', (args, taskCtx) => ({
  kind: 'shell',
  title: `Create GitHub Release for v${args.version}`,
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
NOTES_FILE=/tmp/release-${args.version}-notes.md
awk '/^## \\[${args.version}\\]/,/^## \\[${args.prevVersion}\\]/' CHANGELOG.md | head -n -1 > "$NOTES_FILE"
wc -l "$NOTES_FILE"
head -3 "$NOTES_FILE"
gh release create v${args.version} --title "v${args.version}" --notes-file "$NOTES_FILE"
echo "=== create-github-release OK ==="
`,
    timeout: 60000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'github'],
}));

// ---------------------------------------------------------------------------
// Task 14 — post-release smoke install from real PyPI
// ---------------------------------------------------------------------------
export const postReleaseSmokeTask = defineTask('post-release-smoke', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Post-release: install from real PyPI in throwaway venv',
  shell: {
    command: `set -e
cd "${args.repoRoot}"
TMPVENV=$(mktemp -d)/venv
python3.12 -m venv "$TMPVENV"
. "$TMPVENV/bin/activate"
pip install --upgrade pip
# Wait briefly for PyPI to index
sleep 60
pip install almaapitk==${args.version}
python -c "from almaapitk import AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError, Admin, Users, BibliographicRecords, Acquisitions, ResourceSharing, Analytics, Configuration, TSVGenerator, CitationMetadataError; print('PYPI IMPORT OK ${args.version}')"
deactivate
rm -rf "$(dirname "$TMPVENV")"
echo "=== post-release-smoke OK ==="
`,
    timeout: 300000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'smoke'],
}));

// ---------------------------------------------------------------------------
// Task 15 — file follow-up issue for GitHub Actions publish workflow
// ---------------------------------------------------------------------------
export const fileFollowupIssueTask = defineTask('file-follow-up-issue', (args, taskCtx) => ({
  kind: 'shell',
  title: 'File follow-up: GitHub Actions publish workflow',
  shell: {
    command: `set -e
unset ALMA_PROD_API_KEY
cd "${args.repoRoot}"
ISSUE_BODY=$(cat <<'ISSUE_BODY_EOF'
## Background

${args.version} was published manually with poetry build + poetry publish, matching ${args.prevVersion}'s flow. Future releases should automate the publish step.

## Proposal

Add a .github/workflows/release.yml that:

- Triggers on push of any v* tag.
- Runs the standard validation suite (smoke import, public API contract, unit + logging + client integration suites).
- Builds the wheel + sdist.
- Publishes to PyPI via Trusted Publishing using OIDC — no token in repo secrets.

## Prerequisites

1. Configure the PyPI project as a Trusted Publisher pointing at this repository + workflow + tag environment.
2. (Optional) Create a separate "release" environment in GitHub repo settings for additional approval gates.

## Out of scope

- Migrating to a different build tool.
- Auto-bumping the version (manual bump remains the trigger).

## Acceptance

- Pushing a v* tag triggers the workflow, runs validation, and publishes to PyPI without manual poetry publish.
- Documented in docs/superpowers/specs/ once implemented.
ISSUE_BODY_EOF
)
ISSUE_URL=$(gh issue create --title "Add GitHub Actions publish workflow (PyPI Trusted Publishing on tag push)" --body "$ISSUE_BODY" --label enhancement)
echo "follow-up issue: $ISSUE_URL"
echo "=== file-follow-up-issue OK ==="
`,
    timeout: 30000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
  labels: ['release', 'follow-up'],
}));

// ===========================================================================
// PROCESS — orchestrates the 15 tasks with 3 breakpoints
// ===========================================================================
export async function process(inputs, ctx) {
  const args = {
    repoRoot: inputs.repoRoot,
    version: inputs.version,
    prevVersion: inputs.prevVersion,
  };

  ctx.log('info', `Starting release ${args.version} (prev ${args.prevVersion})`);

  // Phase A: prep (no external state changes)
  await ctx.task(preflightTask, args);
  await ctx.task(openReleaseBranchTask, args);
  await ctx.task(updateChangelogTask, args);
  await ctx.task(bumpVersionTask, args);
  await ctx.task(validationSuiteTask, args);
  await ctx.task(buildAndInspectTask, args);

  // Breakpoint 1: TestPyPI go-ahead (token entry + first external upload)
  let bp1Feedback = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    const bp1 = await ctx.breakpoint({
      question: `Validation suite passed and wheel inspected. Ready to publish ${args.version} to TestPyPI? Make sure the TestPyPI token is set: poetry config pypi-token.testpypi <TOKEN>. Approve to upload to test.pypi.org.`,
      title: 'Breakpoint 1: TestPyPI publish go-ahead',
      options: ['Approve TestPyPI publish', 'Stop here'],
      expert: 'owner',
      tags: ['approval-gate', 'deploy', 'testpypi'],
      previousFeedback: bp1Feedback || undefined,
      attempt: attempt > 0 ? attempt + 1 : undefined,
    });
    if (bp1.approved) break;
    bp1Feedback = bp1.response || bp1.feedback || 'Changes requested';
    if (attempt === 2) {
      ctx.log('error', 'Breakpoint 1 rejected three times; aborting release');
      return { success: false, abortedAt: 'BP-1', reason: bp1Feedback };
    }
  }

  // Phase B: TestPyPI dry-run
  await ctx.task(testpypiPublishTask, args);
  await ctx.task(testpypiSmokeTask, args);

  // Breakpoint 2: open and merge release PR
  let bp2Feedback = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    const bp2 = await ctx.breakpoint({
      question: `TestPyPI install + smoke import passed for ${args.version}. Ready to push release/${args.version}, open PR to main, and squash-merge?`,
      title: 'Breakpoint 2: open + merge release PR',
      options: ['Approve PR open + merge', 'Stop here'],
      expert: 'owner',
      tags: ['approval-gate', 'github'],
      previousFeedback: bp2Feedback || undefined,
      attempt: attempt > 0 ? attempt + 1 : undefined,
    });
    if (bp2.approved) break;
    bp2Feedback = bp2.response || bp2.feedback || 'Changes requested';
    if (attempt === 2) {
      ctx.log('error', 'Breakpoint 2 rejected three times; aborting release');
      return { success: false, abortedAt: 'BP-2', reason: bp2Feedback };
    }
  }

  // Phase C: merge release PR
  await ctx.task(openAndMergePrTask, args);
  await ctx.task(rebuildOnMainTask, args);

  // Breakpoint 3: REAL PyPI publish — IRREVERSIBLE
  let bp3Feedback = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    const bp3 = await ctx.breakpoint({
      question: `IRREVERSIBLE: about to publish ${args.version} to real PyPI. Once this runs, ${args.version} cannot be re-uploaded. Confirm: PyPI token is set (poetry config pypi-token.pypi <TOKEN>); release PR merged to main; rebuild on main produced clean dist/. Approve to run poetry publish.`,
      title: 'Breakpoint 3: REAL PyPI publish (IRREVERSIBLE)',
      options: ['Approve real PyPI publish', 'Stop here'],
      expert: 'owner',
      tags: ['approval-gate', 'deploy', 'pypi', 'irreversible'],
      previousFeedback: bp3Feedback || undefined,
      attempt: attempt > 0 ? attempt + 1 : undefined,
    });
    if (bp3.approved) break;
    bp3Feedback = bp3.response || bp3.feedback || 'Changes requested';
    if (attempt === 2) {
      ctx.log('error', 'Breakpoint 3 rejected three times; aborting release');
      return { success: false, abortedAt: 'BP-3', reason: bp3Feedback };
    }
  }

  // Phase D: real publish + tag + release + smoke + follow-up
  await ctx.task(publishToPypiTask, args);
  await ctx.task(tagAndPushTask, args);
  await ctx.task(createGithubReleaseTask, args);
  await ctx.task(postReleaseSmokeTask, args);
  await ctx.task(fileFollowupIssueTask, args);

  return {
    success: true,
    version: args.version,
    pypiUrl: `https://pypi.org/project/almaapitk/${args.version}/`,
    githubReleaseUrl: `https://github.com/hagaybar/AlmaAPITK/releases/tag/v${args.version}`,
  };
}
