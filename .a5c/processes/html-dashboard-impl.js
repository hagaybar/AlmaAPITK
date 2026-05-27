/**
 * @process almaapitk/html-dashboard-impl
 * @description Implement the pre-approved html-dashboard skill plan task-by-task
 * in a NEW ~/dotfiles git repo (TDD), then a shell quality gate with an agent
 * refine loop. The AlmaAPITK repo only holds the spec + plan docs; all skill
 * files live under ~/dotfiles and are symlinked into ~/.claude.
 * @inputs { planPath: string }
 * @outputs { success: boolean, sections: number, gate: object }
 * @skill html-dashboard (being built; not yet installed)
 */

import { defineTask } from "@a5c-ai/babysitter-sdk";

const PLAN = "docs/superpowers/plans/2026-05-27-html-dashboard-skill.md";

/**
 * Implement one section (one or more contiguous plan Tasks) end-to-end:
 * write the exact files from the plan, run the section's own verification
 * commands, and commit in ~/dotfiles. Delegated to a fresh general-purpose
 * subagent so each section gets clean context.
 */
export const implementSection = defineTask("implement-section", (args, taskCtx) => ({
  kind: "agent",
  title: `Implement ${args.title}`,
  description: `Implement plan section "${args.title}" exactly as written, verify, commit.`,
  execution: { model: "claude-sonnet-4-6" },
  agent: {
    name: "general-purpose",
    prompt: {
      role: "Senior engineer executing a pre-approved, fully-specified TDD plan",
      task: `Implement ${args.title} from the implementation plan, EXACTLY as written.`,
      context: {
        planPath: PLAN,
        section: args.title,
        planTasks: args.planTasks,
        targetRepo: "~/dotfiles (a NEW git repo; create it if Task 0 has not run yet)",
        notes: args.notes || "",
      },
      instructions: [
        `Open ${PLAN} (in the current AlmaAPITK working directory) and locate the section titled "${args.title}".`,
        "For every Step in that section: create/modify each file with the EXACT content shown in the plan's code blocks (byte-for-byte), and run every shell command shown.",
        "All skill files live under ~/dotfiles/claude/... — NEVER create or modify files inside the AlmaAPITK repo (it only holds the spec + plan).",
        "After writing files, RUN the verification commands in the plan steps and confirm the expected output (e.g. 'N passed', 'syntax OK', 'HTML OK'). If a command fails, fix the file to match the plan and re-run until it passes.",
        "Commit in the ~/dotfiles repo using the exact commit message given in that plan section's commit step.",
        "If the plan section says to download Mermaid and the network is unavailable, follow the plan's documented offline fallback (write the stub comment file) and continue.",
        "Return ONLY the JSON result described by the output schema — actual outcomes, not intentions.",
      ],
      outputFormat: "JSON",
    },
    outputSchema: {
      type: "object",
      required: ["done", "filesCreated", "verification", "committed"],
      properties: {
        done: { type: "boolean" },
        filesCreated: { type: "array", items: { type: "string" } },
        verification: { type: "string" },
        committed: { type: "boolean" },
        notes: { type: "string" },
      },
    },
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`,
  },
  labels: ["implement", args.slug],
}));

/**
 * Final verification gate (shell): the run-only checks from plan Task 10.
 * Exits non-zero on any failure; the orchestrator posts { passed, stdout }.
 */
export const finalGate = defineTask("final-gate", (args, taskCtx) => ({
  kind: "shell",
  title: "Final verification gate",
  description: "pytest passes, 12 patterns exist, both symlinks present.",
  shell: {
    command: `set -uo pipefail
SK="$HOME/dotfiles/claude/skills/html-dashboard"
cd "$SK" || { echo "skill dir missing: $SK"; exit 1; }
python3 -m pytest tests/test_engine.py -q || { echo "PYTEST FAILED"; exit 1; }
N=$(ls patterns/*.html 2>/dev/null | wc -l)
echo "patterns:$N"
[ "$N" -eq 12 ] || { echo "EXPECTED 12 patterns, got $N"; exit 1; }
test -L "$HOME/.claude/skills/html-dashboard" || { echo "skill symlink missing"; exit 1; }
test -L "$HOME/.claude/commands/dashboard.md" || { echo "command symlink missing"; exit 1; }
test -f "$HOME/.claude/skills/html-dashboard/SKILL.md" || { echo "SKILL.md not reachable via symlink"; exit 1; }
echo "GATE PASSED"`,
  },
  io: {
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`,
  },
  labels: ["quality-gate"],
}));

/**
 * Refine task (agent): the gate failed — diagnose against the plan and fix so
 * the gate passes, then commit.
 */
export const fixGate = defineTask("fix-gate", (args, taskCtx) => ({
  kind: "agent",
  title: `Fix failing verification (attempt ${args.attempt})`,
  description: "Diagnose the gate failure against the plan and fix it.",
  execution: { model: "claude-sonnet-4-6" },
  agent: {
    name: "general-purpose",
    prompt: {
      role: "Senior engineer fixing a failing verification gate",
      task: "The html-dashboard final verification gate failed. Diagnose and fix so it passes.",
      context: { planPath: PLAN, failure: args.feedback, attempt: args.attempt },
      instructions: [
        "Read the failure output in `failure`.",
        `Consult ${PLAN} for the intended file contents.`,
        "Fix files under ~/dotfiles/claude/skills/html-dashboard so that: pytest tests/test_engine.py passes; there are exactly 12 patterns/*.html; and both symlinks exist (run ~/dotfiles/claude/skills/html-dashboard/install.sh if the symlinks are missing).",
        "Re-run the failing checks yourself to confirm they pass before returning.",
        "Commit the fix in the ~/dotfiles repo.",
        "Return ONLY the JSON result.",
      ],
      outputFormat: "JSON",
    },
    outputSchema: {
      type: "object",
      required: ["fixed", "summary"],
      properties: {
        fixed: { type: "boolean" },
        summary: { type: "string" },
      },
    },
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`,
  },
  labels: ["refine"],
}));

function gatePassed(gate) {
  return !!(gate && gate.passed === true);
}

export async function process(inputs, ctx) {
  const sections = [
    { slug: "bootstrap", title: "Task 0: Bootstrap the dotfiles repo + skeleton", planTasks: [0] },
    { slug: "engine", title: "Task 1: Engine — generalized localhost server (TDD)", planTasks: [1] },
    { slug: "helpers-assets", title: "Task 2: Engine — watch + reply helper scripts", planTasks: [2, 3], notes: "Also implement Task 3 (Engine assets — comms.js, base.css, vendored Mermaid) in the same run." },
    { slug: "exemplars", title: "Task 4: Pattern library — INDEX + exemplar patterns", planTasks: [4] },
    { slug: "patterns", title: "Task 5: Pattern library — remaining patterns", planTasks: [5] },
    { slug: "docs-command", title: "Task 6: SKILL.md — triggers, modes, workflow", planTasks: [6, 7, 8], notes: "Also implement Task 7 (references/building-html.md) and Task 8 (the /dashboard slash command) in the same run." },
    { slug: "install", title: "Task 9: install.sh — symlink into ~/.claude, then run + verify", planTasks: [9] },
  ];

  const results = [];
  for (const s of sections) {
    results.push(await ctx.task(implementSection, s));
  }

  // Final quality gate with a bounded refine loop.
  let gate = await ctx.task(finalGate, {});
  let attempt = 0;
  while (!gatePassed(gate) && attempt < 3) {
    attempt++;
    await ctx.task(fixGate, {
      attempt,
      feedback: JSON.stringify(gate).slice(0, 6000),
    });
    gate = await ctx.task(finalGate, {});
  }

  return {
    success: gatePassed(gate),
    sections: results.length,
    gate,
    metadata: {
      processId: "almaapitk/html-dashboard-impl",
      timestamp: ctx.now(),
    },
  };
}
