/**
 * @process coverage-finishing-prereqs
 * @description Apply Prerequisites section to all 77 coverage+architecture issues, then 100% verify
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

const REPO = '/home/hagaybar/projects/AlmaAPITK';

export const applyPrereqsTask = defineTask('apply-prereqs', (args, taskCtx) => ({
  kind: 'shell',
  title: 'Apply Prerequisites section to all 77 issues (idempotent)',
  shell: {
    command: `cd ${REPO} && python3 scripts/update_prereqs.py apply 2>&1`,
    timeout: 600000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export const verifyPrereqsTask = defineTask('verify-prereqs', (args, taskCtx) => ({
  kind: 'shell',
  title: '100% verify gate: every issue has the Prerequisites section',
  shell: {
    command: `cd ${REPO} && python3 scripts/update_prereqs.py verify 2>&1`,
    timeout: 600000,
  },
  io: { outputJsonPath: `tasks/${taskCtx.effectId}/output.json` },
}));

export async function process(inputs, ctx) {
  ctx.log('info', 'Phase 1: apply Prerequisites section to all 77 issues');
  const applyResult = await ctx.task(applyPrereqsTask, {});

  ctx.log('info', 'Phase 2: 100% verify gate');
  const verifyResult = await ctx.task(verifyPrereqsTask, {});

  return {
    success: true,
    applyResult,
    verifyResult,
  };
}
