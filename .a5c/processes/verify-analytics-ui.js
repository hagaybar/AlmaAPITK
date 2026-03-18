/**
 * @process verify-analytics-ui
 * @description Verify Fetch_Alma_Analytics_Reports UI integration before completing task 8
 *
 * This process verifies:
 * 1. Branch comparison between main and new_ui
 * 2. UI components are properly integrated in main
 * 3. Backend and frontend work together
 * 4. Dashboard is accessible and functional
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

// =============================================================================
// TASK DEFINITIONS
// =============================================================================

const analyzeBranchesTask = defineTask('analyze-branches', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Analyze branch differences between main and new_ui',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git branch analyst',
      task: 'Compare branches and determine UI integration status',
      context: {
        repoPath: args.repoPath,
        branches: ['main', 'new_ui', 'origin/prod']
      },
      instructions: [
        'Run git log comparison between main and new_ui branches',
        'Run git diff main..new_ui --stat -- frontend/ backend/ to see changes',
        'Check if new_ui has features not in main',
        'Identify frontend/backend differences',
        'Determine which branch has the most recent UI updates',
        'Check commit messages for context',
        'Document findings in structured JSON output'
      ],
      outputFormat: 'JSON with fields: mainHasLatestUI (boolean), mergeNeeded (boolean), uiDifferences (array of strings describing changes), recommendation (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['mainHasLatestUI', 'mergeNeeded', 'recommendation'],
      properties: {
        mainHasLatestUI: { type: 'boolean' },
        mergeNeeded: { type: 'boolean' },
        uiDifferences: { type: 'array', items: { type: 'string' } },
        recommendation: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const mergeNewUITask = defineTask('merge-new-ui', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Merge new_ui branch into main',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git merge specialist',
      task: 'Merge new_ui branch into main in Fetch_Alma_Analytics_Reports',
      context: {
        repoPath: args.repoPath,
        sourceBranch: 'new_ui',
        targetBranch: 'main'
      },
      instructions: [
        'cd to the repo directory',
        'Checkout main branch',
        'Merge new_ui into main',
        'If conflicts, prefer new_ui changes for frontend/ files',
        'Commit the merge with message: "Merge new_ui into main - UI improvements"',
        'Push to origin main',
        'Report merge status'
      ],
      outputFormat: 'JSON with fields: merged (boolean), conflictsResolved (array of filenames), commitHash (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['merged'],
      properties: {
        merged: { type: 'boolean' },
        conflictsResolved: { type: 'array', items: { type: 'string' } },
        commitHash: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const verifyBackendTask = defineTask('verify-backend', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify backend API is functional',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Backend verification specialist',
      task: 'Verify the FastAPI backend starts and responds correctly',
      context: {
        repoPath: args.repoPath,
        backendPath: 'backend/',
        configFile: 'reports_config.json',
        sampleConfig: 'reports_config.sample.json'
      },
      instructions: [
        'cd to the repo directory',
        'Check if reports_config.json exists, if not copy from sample',
        'Install backend dependencies: pip install -r backend/requirements.txt',
        'Start the backend: uvicorn backend.main:app --host 127.0.0.1 --port 8000 (in background)',
        'Wait a few seconds for startup',
        'Test root endpoint: curl http://127.0.0.1:8000/',
        'Test tasks endpoint: curl http://127.0.0.1:8000/api/v1/tasks',
        'Stop the backend process',
        'Report API status'
      ],
      outputFormat: 'JSON with fields: backendStarts (boolean), apiResponds (boolean), endpoints (object with endpoint names as keys and status codes as values)'
    },
    outputSchema: {
      type: 'object',
      required: ['backendStarts', 'apiResponds'],
      properties: {
        backendStarts: { type: 'boolean' },
        apiResponds: { type: 'boolean' },
        endpoints: { type: 'object' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const verifyFrontendTask = defineTask('verify-frontend', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify frontend builds and serves correctly',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Frontend verification specialist',
      task: 'Verify the React frontend builds and displays correctly',
      context: {
        repoPath: args.repoPath,
        frontendPath: 'frontend/'
      },
      instructions: [
        'cd to repo/frontend directory',
        'Run npm install to ensure dependencies',
        'Run npm run build to verify TypeScript compiles',
        'Start dev server: npm run dev (in background)',
        'Wait for server to be ready',
        'Use curl or browser to check http://localhost:5173 responds',
        'Check for build errors in the output',
        'Stop the dev server',
        'Report frontend status'
      ],
      outputFormat: 'JSON with fields: buildSucceeds (boolean), devServerStarts (boolean), dashboardAccessible (boolean), errors (array of error messages)'
    },
    outputSchema: {
      type: 'object',
      required: ['buildSucceeds', 'devServerStarts', 'dashboardAccessible'],
      properties: {
        buildSucceeds: { type: 'boolean' },
        devServerStarts: { type: 'boolean' },
        dashboardAccessible: { type: 'boolean' },
        errors: { type: 'array', items: { type: 'string' } }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const integrationTestTask = defineTask('integration-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Test full stack integration (frontend + backend)',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Integration test specialist',
      task: 'Verify frontend can communicate with backend and display data',
      context: {
        repoPath: args.repoPath,
        backendPort: 8000,
        frontendPort: 5173
      },
      instructions: [
        'Start backend on port 8000 (in background)',
        'Start frontend on port 5173 (in background)',
        'Wait for both to be ready',
        'Use Playwright browser tools to:',
        '  - Navigate to http://localhost:5173',
        '  - Take a snapshot of Dashboard page',
        '  - Click on Tasks in navigation',
        '  - Take a snapshot of Tasks page',
        '  - Check for any error messages displayed',
        'Stop both servers',
        'Report integration status with screenshots if possible'
      ],
      outputFormat: 'JSON with fields: fullyIntegrated (boolean), pagesWorking (array of page names), issues (array of issues found)'
    },
    outputSchema: {
      type: 'object',
      required: ['fullyIntegrated'],
      properties: {
        fullyIntegrated: { type: 'boolean' },
        pagesWorking: { type: 'array', items: { type: 'string' } },
        issues: { type: 'array', items: { type: 'string' } }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

const generateReportTask = defineTask('generate-report', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Generate final verification report',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Report generator',
      task: 'Generate a summary report of UI verification',
      context: {
        taskResults: args.taskResults
      },
      instructions: [
        'Review all previous task results',
        'Summarize branch status',
        'Summarize backend verification',
        'Summarize frontend verification',
        'Summarize integration test results',
        'List any outstanding issues',
        'Provide recommendation for task 8 completion'
      ],
      outputFormat: 'JSON with fields: summary (string), allPassed (boolean), issues (array), recommendation (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['summary', 'allPassed', 'recommendation'],
      properties: {
        summary: { type: 'string' },
        allPassed: { type: 'boolean' },
        issues: { type: 'array', items: { type: 'string' } },
        recommendation: { type: 'string' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

// =============================================================================
// PROCESS FUNCTION
// =============================================================================

export async function process(inputs, ctx) {
  const {
    repoPath = '/home/hagaybar/projects/Fetch_Alma_Analytics_Reports',
    targetBranch = 'main',
    comparisonBranch = 'new_ui'
  } = inputs;

  const taskResults = {};

  // ============================================================================
  // PHASE 1: BRANCH ANALYSIS
  // ============================================================================

  const branchAnalysis = await ctx.task(analyzeBranchesTask, { repoPath });
  taskResults.branchAnalysis = branchAnalysis;

  // BREAKPOINT: User decides on merge strategy
  const mergeDecision = await ctx.breakpoint({
    question: `Branch analysis complete.

**Findings:**
- Main has latest UI: ${branchAnalysis.mainHasLatestUI}
- Merge needed: ${branchAnalysis.mergeNeeded}
- Recommendation: ${branchAnalysis.recommendation}

**UI Differences from new_ui:**
${(branchAnalysis.uiDifferences || []).map(d => `• ${d}`).join('\n')}

Should we merge new_ui into main before testing?`,
    options: [
      { label: 'Merge new_ui into main', value: 'merge' },
      { label: 'Test main as-is', value: 'skip' },
      { label: 'Investigate further', value: 'investigate' }
    ]
  });

  // ============================================================================
  // PHASE 2: MERGE (CONDITIONAL)
  // ============================================================================

  if (mergeDecision.approved && mergeDecision.response === 'merge') {
    const mergeResult = await ctx.task(mergeNewUITask, { repoPath });
    taskResults.merge = mergeResult;
  } else if (mergeDecision.response === 'investigate') {
    // Return early for investigation
    return {
      status: 'investigation_needed',
      branchAnalysis,
      message: 'User requested further investigation before proceeding.'
    };
  }

  // ============================================================================
  // PHASE 3: BACKEND VERIFICATION
  // ============================================================================

  const backendResult = await ctx.task(verifyBackendTask, { repoPath });
  taskResults.backend = backendResult;

  // ============================================================================
  // PHASE 4: FRONTEND VERIFICATION
  // ============================================================================

  const frontendResult = await ctx.task(verifyFrontendTask, { repoPath });
  taskResults.frontend = frontendResult;

  // ============================================================================
  // PHASE 5: INTEGRATION TESTING
  // ============================================================================

  const integrationResult = await ctx.task(integrationTestTask, { repoPath });
  taskResults.integration = integrationResult;

  // ============================================================================
  // PHASE 6: FINAL VERIFICATION
  // ============================================================================

  // BREAKPOINT: Review results
  const finalDecision = await ctx.breakpoint({
    question: `UI integration testing complete.

**Backend:** ${backendResult.backendStarts ? '✓' : '✗'} Starts, ${backendResult.apiResponds ? '✓' : '✗'} API responds
**Frontend:** ${frontendResult.buildSucceeds ? '✓' : '✗'} Builds, ${frontendResult.devServerStarts ? '✓' : '✗'} Dev server
**Integration:** ${integrationResult.fullyIntegrated ? '✓ Fully integrated' : '✗ Issues found'}

${integrationResult.issues?.length ? `**Issues:**\n${integrationResult.issues.map(i => `• ${i}`).join('\n')}` : ''}

What would you like to do?`,
    options: [
      { label: 'Mark task 8 complete', value: 'complete' },
      { label: 'Fix issues first', value: 'fix' },
      { label: 'Need more testing', value: 'retest' }
    ]
  });

  // Generate final report
  const report = await ctx.task(generateReportTask, { taskResults });

  return {
    status: finalDecision.response === 'complete' ? 'completed' : 'pending',
    taskResults,
    report,
    recommendation: report.recommendation
  };
}
