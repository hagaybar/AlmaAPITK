/**
 * @process phase-b1-public-api
 * @description Phase B1: Define stable public API contract for almaapitk package
 * @inputs { currentInit: string, constraints: array }
 * @outputs { success: boolean, filesModified: array, prTitle: string, prDescription: string }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

export async function process(inputs, ctx) {
  const { currentInit, constraints } = inputs;

  const startTime = ctx.now();
  const artifacts = [];

  ctx.log('info', 'Phase B1: Starting public API contract definition');
  ctx.log('info', `Constraints: ${JSON.stringify(constraints)}`);

  // ============================================================================
  // PHASE 1: ANALYZE CURRENT STRUCTURE AND PROPOSE PUBLIC API
  // ============================================================================

  ctx.log('info', 'Phase 1: Analyzing current module structure');

  const analysis = await ctx.task(analyzeStructureTask, {
    currentInit,
    constraints
  });

  if (!analysis.success) {
    return {
      success: false,
      error: 'Failed to analyze module structure',
      details: analysis
    };
  }

  ctx.log('info', `Proposed ${analysis.proposedExports.length} public exports`);
  artifacts.push(...(analysis.artifacts || []));

  // ============================================================================
  // PHASE 2: UPDATE __init__.py
  // ============================================================================

  ctx.log('info', 'Phase 2: Updating src/almaapitk/__init__.py');

  const initUpdate = await ctx.task(updateInitTask, {
    proposedExports: analysis.proposedExports,
    constraints
  });

  if (!initUpdate.success) {
    return {
      success: false,
      error: 'Failed to update __init__.py',
      details: initUpdate
    };
  }

  artifacts.push(...(initUpdate.artifacts || []));

  // ============================================================================
  // PHASE 3: CREATE API_CONTRACT.md
  // ============================================================================

  ctx.log('info', 'Phase 3: Creating docs/API_CONTRACT.md');

  const contractDoc = await ctx.task(createApiContractTask, {
    proposedExports: analysis.proposedExports
  });

  if (!contractDoc.success) {
    return {
      success: false,
      error: 'Failed to create API_CONTRACT.md',
      details: contractDoc
    };
  }

  artifacts.push(...(contractDoc.artifacts || []));

  // ============================================================================
  // PHASE 4: UPDATE SMOKE TEST
  // ============================================================================

  ctx.log('info', 'Phase 4: Updating scripts/smoke_import.py');

  const smokeUpdate = await ctx.task(updateSmokeTestTask, {
    proposedExports: analysis.proposedExports
  });

  if (!smokeUpdate.success) {
    return {
      success: false,
      error: 'Failed to update smoke test',
      details: smokeUpdate
    };
  }

  artifacts.push(...(smokeUpdate.artifacts || []));

  // ============================================================================
  // PHASE 5: LOCAL VALIDATION
  // ============================================================================

  ctx.log('info', 'Phase 5: Running local validation');

  const validation = await ctx.task(validateLocallyTask, {});

  if (!validation.success) {
    return {
      success: false,
      error: 'Local validation failed',
      details: validation
    };
  }

  artifacts.push(...(validation.artifacts || []));

  // ============================================================================
  // PHASE 6: COMMIT AND PUSH
  // ============================================================================

  ctx.log('info', 'Phase 6: Committing and pushing to main');

  const commit = await ctx.task(commitAndPushTask, {
    filesModified: [
      'src/almaapitk/__init__.py',
      'docs/API_CONTRACT.md',
      'scripts/smoke_import.py'
    ]
  });

  if (!commit.success) {
    return {
      success: false,
      error: 'Failed to commit and push',
      details: commit
    };
  }

  artifacts.push(...(commit.artifacts || []));

  const endTime = ctx.now();
  const duration = endTime - startTime;

  return {
    success: true,
    filesModified: [
      'src/almaapitk/__init__.py',
      'docs/API_CONTRACT.md',
      'scripts/smoke_import.py'
    ],
    proposedExports: analysis.proposedExports,
    commitHash: commit.commitHash,
    prTitle: 'Define stable public API contract for almaapitk package',
    prDescription: [
      '## Summary',
      '- Update src/almaapitk/__init__.py with explicit __all__ exports',
      '- Create docs/API_CONTRACT.md documenting public API contract',
      '- Update scripts/smoke_import.py to validate only public API',
      '',
      '## Migration Notes',
      'If you currently import from internal modules (client.*, utils.*, domains.*),',
      'please switch to importing from `almaapitk` instead.',
      '',
      '## Test Plan',
      '- [x] Local validation passed',
      '- [ ] Smoke test on Production DevSandbox'
    ].join('\n'),
    artifacts,
    duration,
    metadata: {
      processId: 'phase-b1-public-api',
      timestamp: startTime
    }
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const analyzeStructureTask = defineTask('analyze-structure', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Analyze current module structure and propose public API',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python package maintainer',
      task: 'Analyze existing almaapitk structure and propose minimal public API',
      context: {
        currentInit: args.currentInit,
        constraints: args.constraints
      },
      instructions: [
        'Read and analyze src/almaapitk/__init__.py to understand current exports',
        'Read src/client/AlmaAPIClient.py to identify exportable symbols (classes, exceptions)',
        'Identify the core client class (AlmaAPIClient) and base exceptions to export',
        'Keep exports minimal: target 5-10 symbols max',
        'Must include: AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError, __version__',
        'Do NOT include domain classes (Admin, Users, Bibs, etc.) or workflow logic',
        'Do NOT include logging infrastructure',
        'Return the proposed __all__ list with source locations for each symbol',
        'Explain rationale for each export'
      ],
      outputFormat: 'JSON with proposedExports (array of {symbol, source, description}), rationale (string), success (boolean)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'proposedExports', 'rationale'],
      properties: {
        success: { type: 'boolean' },
        proposedExports: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              symbol: { type: 'string' },
              source: { type: 'string' },
              description: { type: 'string' }
            }
          }
        },
        rationale: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const updateInitTask = defineTask('update-init', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update src/almaapitk/__init__.py with explicit __all__',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python package maintainer',
      task: 'Update __init__.py with explicit __all__ and clean docstring',
      context: {
        proposedExports: args.proposedExports,
        constraints: args.constraints
      },
      instructions: [
        'Edit src/almaapitk/__init__.py using the Edit tool',
        'Keep __version__ = "0.1.0"',
        'Update __all__ to list exactly the public symbols: __version__, AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError',
        'Keep the existing lazy import mechanism (it works and avoids circular imports)',
        'Update the module docstring to clearly explain:',
        '  - This is the ONLY supported public API surface',
        '  - What symbols are exported',
        '  - What is NOT exported (domain classes, logging, utils)',
        '  - A migration note for users of internal imports',
        'Do NOT add any side effects (no env reads, no file I/O, no network calls)',
        'Do NOT change the lazy import implementation logic',
        'Return the file path and summary of changes'
      ],
      outputFormat: 'JSON with success (boolean), filePath (string), changes (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filePath'],
      properties: {
        success: { type: 'boolean' },
        filePath: { type: 'string' },
        changes: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const createApiContractTask = defineTask('create-api-contract', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create docs/API_CONTRACT.md',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Technical documentation writer',
      task: 'Create API_CONTRACT.md documenting the public API contract',
      context: {
        proposedExports: args.proposedExports
      },
      instructions: [
        'Create the file docs/API_CONTRACT.md using the Write tool',
        'Document the public API contract with these sections:',
        '  1. Overview - what almaapitk provides',
        '  2. Supported Imports - only from almaapitk package',
        '  3. Public API Symbols - list each exported symbol with description',
        '  4. Internal/Unsupported - list internal modules (client.*, utils.*, domains.*, alma_logging.*)',
        '  5. Migration Guide - how to migrate from internal imports to almaapitk',
        '  6. Version - current version (0.1.0)',
        'Keep it short and practical (under 100 lines)',
        'Use clear markdown formatting',
        'Include code examples for correct imports'
      ],
      outputFormat: 'JSON with success (boolean), filePath (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filePath'],
      properties: {
        success: { type: 'boolean' },
        filePath: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const updateSmokeTestTask = defineTask('update-smoke-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update scripts/smoke_import.py to validate only public API',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer',
      task: 'Update smoke test to validate ONLY the public API',
      context: {
        proposedExports: args.proposedExports
      },
      instructions: [
        'Edit scripts/smoke_import.py using the Edit tool',
        'The smoke test should:',
        '  1. Import almaapitk package',
        '  2. Verify __version__ is accessible',
        '  3. Verify __all__ contains expected symbols',
        '  4. Access each public symbol (AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError)',
        '  5. Print version and class references (no network calls)',
        '  6. Check stdlib logging is not shadowed: import logging; assert hasattr(logging, "Formatter")',
        '  7. Check requests can be imported: import requests',
        'Remove backward compatibility checks for internal modules (client, utils)',
        'Do NOT make any network calls',
        'Keep the script simple and focused',
        'Print clear pass/fail status'
      ],
      outputFormat: 'JSON with success (boolean), filePath (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filePath'],
      properties: {
        success: { type: 'boolean' },
        filePath: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const validateLocallyTask = defineTask('validate-locally', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Run local validation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer',
      task: 'Run local validation commands to verify the changes work',
      context: {},
      instructions: [
        'Run the following commands using the Bash tool:',
        '1. cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python -c "import almaapitk; print(almaapitk.__version__)"',
        '2. cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python scripts/smoke_import.py',
        'Report the output of each command',
        'Mark success=true only if both commands succeed',
        'Do NOT make any network calls'
      ],
      outputFormat: 'JSON with success (boolean), versionCheck (string), smokeTest (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'versionCheck', 'smokeTest'],
      properties: {
        success: { type: 'boolean' },
        versionCheck: { type: 'string' },
        smokeTest: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const commitAndPushTask = defineTask('commit-and-push', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Commit and push to main',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git workflow expert',
      task: 'Commit changes and push to main branch',
      context: {
        filesModified: args.filesModified
      },
      instructions: [
        'Stage the modified files using git add:',
        '  - src/almaapitk/__init__.py',
        '  - docs/API_CONTRACT.md',
        '  - scripts/smoke_import.py',
        'Create a commit with a detailed message using HEREDOC format:',
        '  Title: "Define stable public API contract for almaapitk package"',
        '  Body: List the changes made',
        '  Include: Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>',
        'Push to origin main',
        'Return the commit hash and push status'
      ],
      outputFormat: 'JSON with success (boolean), commitHash (string), pushStatus (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'commitHash'],
      properties: {
        success: { type: 'boolean' },
        commitHash: { type: 'string' },
        pushStatus: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));
