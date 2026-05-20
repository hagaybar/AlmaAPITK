/**
 * @process security-audit-issue-rollout
 * @description Open a "Security audit: sensitive data leaks" issue in every
 * GitHub-backed project under a given projects root. Idempotent: skips a
 * repo if an open issue with the same title already exists. Body comes from
 * a local markdown file.
 * @inputs { projectsRoot: string, issueBodyPath: string, issueTitle: string }
 * @outputs { success: boolean, total: number, created: object[], skipped: object[], failed: object[], summary: string }
 */

import { defineTask } from "@a5c-ai/babysitter-sdk";

const discoverProjectsTask = defineTask("discover-github-projects", (args, taskCtx) => ({
  kind: "shell",
  title: "Discover projects with GitHub remotes",
  shell: {
    command: `set -euo pipefail
ROOT="${args.projectsRoot}"
OUT_FILE="$PWD/tasks/${taskCtx.effectId}/output.json"
mkdir -p "$(dirname "$OUT_FILE")"

# Sanity: body file exists
test -f "${args.issueBodyPath}" || { echo "Issue body file not found: ${args.issueBodyPath}" >&2; exit 1; }

echo "Scanning $ROOT for git repos with GitHub remotes..."
PROJECTS_JSON='[]'
for dir in "$ROOT"/*/; do
  base=$(basename "$dir")
  if [ -d "$dir/.git" ]; then
    remote=$(git -C "$dir" remote get-url origin 2>/dev/null || echo "")
    if [ -n "$remote" ] && echo "$remote" | grep -q "github.com"; then
      repo=$(echo "$remote" | sed -E 's|.*github\\.com[:/]([^/]+/[^/]+)\\.git$|\\1|; s|.*github\\.com[:/]([^/]+/[^/]+)$|\\1|; s|\\.git$||')
      PROJECTS_JSON=$(echo "$PROJECTS_JSON" | jq --arg dir "$base" --arg repo "$repo" --arg remote "$remote" '. + [{"dir": $dir, "repo": $repo, "remote": $remote}]')
    fi
  fi
done

TOTAL=$(echo "$PROJECTS_JSON" | jq 'length')
echo "Found $TOTAL projects with GitHub remotes"

jq -n --argjson projects "$PROJECTS_JSON" --arg root "$ROOT" --arg body "${args.issueBodyPath}" --arg title "${args.issueTitle}" \
  '{projects: $projects, projectsRoot: $root, issueBodyPath: $body, issueTitle: $title, total: ($projects | length)}' > "$OUT_FILE"

echo "Wrote $TOTAL projects to $OUT_FILE"
`
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },
  labels: ["discovery"]
}));

const fileIssueTask = defineTask("file-security-audit-issue", (args, taskCtx) => ({
  kind: "shell",
  title: `File issue in ${args.repo}`,
  shell: {
    command: `set -euo pipefail
OUT_FILE="tasks/${taskCtx.effectId}/output.json"
mkdir -p "$(dirname "$OUT_FILE")"

REPO='${args.repo}'
TITLE='${args.issueTitle}'
BODY_PATH='${args.issueBodyPath}'

# Idempotency: check if an OPEN issue with the same title already exists
EXISTING=$(gh issue list --repo "$REPO" --state open --search "$TITLE in:title" --json number,title,url 2>/dev/null | jq -r --arg t "$TITLE" '[.[] | select(.title == $t)] | first // empty')

if [ -n "$EXISTING" ]; then
  NUMBER=$(echo "$EXISTING" | jq -r '.number')
  URL=$(echo "$EXISTING" | jq -r '.url')
  echo "SKIPPED $REPO -- existing issue #$NUMBER: $URL"
  jq -n --arg repo "$REPO" --arg dir '${args.dir}' --arg status "skipped" --arg url "$URL" --argjson number "$NUMBER" --arg reason "Existing open issue with same title" \
    '{repo: $repo, dir: $dir, status: $status, number: $number, url: $url, reason: $reason}' > "$OUT_FILE"
  exit 0
fi

# Create the issue
set +e
ISSUE_URL=$(gh issue create --repo "$REPO" --title "$TITLE" --body-file "$BODY_PATH" 2>&1)
RC=$?
set -e

if [ "$RC" -ne 0 ]; then
  echo "FAILED $REPO: $ISSUE_URL"
  jq -n --arg repo "$REPO" --arg dir '${args.dir}' --arg status "failed" --arg error "$ISSUE_URL" \
    '{repo: $repo, dir: $dir, status: $status, error: $error}' > "$OUT_FILE"
  exit 0
fi

# extract issue number from URL (last path component)
NUMBER=$(echo "$ISSUE_URL" | sed -E 's|.*/||')

echo "CREATED $REPO -- $ISSUE_URL"
jq -n --arg repo "$REPO" --arg dir '${args.dir}' --arg status "created" --arg url "$ISSUE_URL" --argjson number "$NUMBER" \
  '{repo: $repo, dir: $dir, status: $status, number: $number, url: $url}' > "$OUT_FILE"
`
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },
  labels: ["github", "issue-creation"]
}));

/**
 * Main process: discover GitHub-backed projects and file the security audit
 * issue in each one (skipping any that already have it).
 *
 * @param {Object} inputs
 * @param {string} inputs.projectsRoot - Absolute path to projects root
 * @param {string} inputs.issueBodyPath - Absolute path to issue body markdown
 * @param {string} inputs.issueTitle - Title to use for the issue
 * @param {ProcessContext} ctx
 */
export async function process(inputs, ctx) {
  const { projectsRoot, issueBodyPath, issueTitle } = inputs;
  if (!projectsRoot) throw new Error("projectsRoot is required");
  if (!issueBodyPath) throw new Error("issueBodyPath is required");
  if (!issueTitle) throw new Error("issueTitle is required");

  ctx.log?.("info", `=== PHASE 1: Discover GitHub-backed projects under ${projectsRoot} ===`);

  const discovery = await ctx.task(discoverProjectsTask, {
    projectsRoot,
    issueBodyPath,
    issueTitle
  });

  const projects = discovery.projects || [];
  ctx.log?.("info", `Discovered ${projects.length} GitHub-backed projects`);

  if (projects.length === 0) {
    return {
      success: true,
      total: 0,
      created: [],
      skipped: [],
      failed: [],
      summary: "No GitHub-backed projects found under " + projectsRoot
    };
  }

  ctx.log?.("info", `=== PHASE 2: File security-audit issue in parallel across ${projects.length} repos ===`);

  const fileFns = projects.map((p) => () =>
    ctx.task(fileIssueTask, {
      repo: p.repo,
      dir: p.dir,
      issueBodyPath,
      issueTitle
    })
  );

  const results = await ctx.parallel.all(fileFns);

  const created = results.filter((r) => r && r.status === "created");
  const skipped = results.filter((r) => r && r.status === "skipped");
  const failed = results.filter((r) => r && r.status === "failed");

  const summary = `Filed ${created.length} new issues, skipped ${skipped.length} (already filed), failed ${failed.length}, out of ${projects.length} GitHub-backed projects.`;
  ctx.log?.("info", summary);

  return {
    success: failed.length === 0,
    total: projects.length,
    created,
    skipped,
    failed,
    summary
  };
}
