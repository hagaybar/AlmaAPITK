/**
 * @process phase-b2-internal-namespace
 * @description Phase B2: Create internal namespace using TDD-first approach
 * @inputs { constraints: array }
 * @outputs { success: boolean, filesModified: array, testsCreated: array }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

export async function process(inputs, ctx) {
  const { constraints } = inputs;

  const startTime = ctx.now();
  const artifacts = [];

  ctx.log('info', 'Phase B2: Creating internal namespace with TDD-first approach');

  // ============================================================================
  // PHASE 1: CREATE TESTS FIRST (TDD)
  // ============================================================================

  ctx.log('info', 'Phase 1: Creating unit tests for public API contract');

  const testCreation = await ctx.task(createTestsTask, {
    constraints
  });

  if (!testCreation.success) {
    return {
      success: false,
      error: 'Failed to create tests',
      details: testCreation
    };
  }

  artifacts.push(...(testCreation.artifacts || []));

  // ============================================================================
  // PHASE 2: RUN TESTS (SHOULD PASS - validates current API)
  // ============================================================================

  ctx.log('info', 'Phase 2: Running tests to verify current API works');

  const initialTestRun = await ctx.task(runTestsTask, {
    phase: 'pre-implementation'
  });

  if (!initialTestRun.success) {
    return {
      success: false,
      error: 'Initial test run failed - current API may be broken',
      details: initialTestRun
    };
  }

  artifacts.push(...(initialTestRun.artifacts || []));

  // ============================================================================
  // PHASE 3: CREATE _internal NAMESPACE
  // ============================================================================

  ctx.log('info', 'Phase 3: Creating src/almaapitk/_internal/ re-export modules');

  const internalCreation = await ctx.task(createInternalNamespaceTask, {
    constraints
  });

  if (!internalCreation.success) {
    return {
      success: false,
      error: 'Failed to create _internal namespace',
      details: internalCreation
    };
  }

  artifacts.push(...(internalCreation.artifacts || []));

  // ============================================================================
  // PHASE 4: UPDATE __init__.py TO USE _internal
  // ============================================================================

  ctx.log('info', 'Phase 4: Updating __init__.py to import from _internal');

  const initUpdate = await ctx.task(updateInitToUseInternalTask, {
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
  // PHASE 5: RUN TESTS (SHOULD STILL PASS)
  // ============================================================================

  ctx.log('info', 'Phase 5: Running tests to verify changes work');

  const finalTestRun = await ctx.task(runTestsTask, {
    phase: 'post-implementation'
  });

  if (!finalTestRun.success) {
    return {
      success: false,
      error: 'Tests failed after implementation',
      details: finalTestRun
    };
  }

  artifacts.push(...(finalTestRun.artifacts || []));

  // ============================================================================
  // PHASE 6: RUN SMOKE TEST
  // ============================================================================

  ctx.log('info', 'Phase 6: Running smoke_import.py validation');

  const smokeTest = await ctx.task(runSmokeTestTask, {});

  if (!smokeTest.success) {
    return {
      success: false,
      error: 'Smoke test failed',
      details: smokeTest
    };
  }

  artifacts.push(...(smokeTest.artifacts || []));

  // ============================================================================
  // PHASE 7: COMMIT AND PUSH
  // ============================================================================

  ctx.log('info', 'Phase 7: Committing and pushing to main');

  const commit = await ctx.task(commitAndPushTask, {
    filesModified: [
      'tests/test_public_api_contract.py',
      'src/almaapitk/_internal/__init__.py',
      'src/almaapitk/_internal/client.py',
      'src/almaapitk/_internal/response.py',
      'src/almaapitk/_internal/exceptions.py',
      'src/almaapitk/__init__.py'
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
      'tests/test_public_api_contract.py',
      'src/almaapitk/_internal/__init__.py',
      'src/almaapitk/_internal/client.py',
      'src/almaapitk/_internal/response.py',
      'src/almaapitk/_internal/exceptions.py',
      'src/almaapitk/__init__.py'
    ],
    testsCreated: ['tests/test_public_api_contract.py'],
    commitHash: commit.commitHash,
    artifacts,
    duration,
    metadata: {
      processId: 'phase-b2-internal-namespace',
      timestamp: startTime
    }
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const createTestsTask = defineTask('create-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create unit tests for public API contract (TDD first)',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python TDD developer',
      task: 'Create unit tests for almaapitk public API contract BEFORE implementation',
      context: {
        constraints: args.constraints
      },
      instructions: [
        'Create the file tests/test_public_api_contract.py using the Write tool',
        'Use unittest (standard library) for the test framework',
        'Tests must verify:',
        '  1. import almaapitk works',
        '  2. almaapitk.__version__ exists and is a string',
        '  3. almaapitk.__all__ contains expected symbols',
        '  4. Each symbol in __all__ is accessible as an attribute',
        '  5. AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError are importable',
        '  6. (Optional) Check that imports eventually come from _internal (after Phase B2)',
        '  7. stdlib logging is not shadowed (import logging; assert hasattr(logging, "Formatter"))',
        'Make tests resilient - the _internal check should pass both before AND after B2',
        'Keep tests simple and focused on the public API contract',
        'Do NOT make any network calls',
        'Return success=true and the file path'
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

export const runTestsTask = defineTask('run-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: `Run unit tests (${args.phase})`,
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python test runner',
      task: `Run unit tests for phase: ${args.phase}`,
      context: {
        phase: args.phase
      },
      instructions: [
        'Run the following command using the Bash tool:',
        'cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python -m unittest tests.test_public_api_contract -v',
        'Capture the output',
        'Mark success=true only if all tests pass',
        'Report the test results summary'
      ],
      outputFormat: 'JSON with success (boolean), testOutput (string), testsRun (number), testsPassed (number), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'testOutput'],
      properties: {
        success: { type: 'boolean' },
        testOutput: { type: 'string' },
        testsRun: { type: 'number' },
        testsPassed: { type: 'number' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const createInternalNamespaceTask = defineTask('create-internal-namespace', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create src/almaapitk/_internal/ with re-export modules',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python package maintainer',
      task: 'Create _internal namespace with thin re-export modules',
      context: {
        constraints: args.constraints
      },
      instructions: [
        'Create the directory structure and files:',
        '',
        '1. Create src/almaapitk/_internal/__init__.py:',
        '   - Export all public symbols: AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError',
        '   - Import from sibling modules (.client, .response, .exceptions)',
        '   - Define __all__ with these symbols',
        '',
        '2. Create src/almaapitk/_internal/client.py:',
        '   - Import AlmaAPIClient from src.client.AlmaAPIClient',
        '   - Re-export it: __all__ = ["AlmaAPIClient"]',
        '',
        '3. Create src/almaapitk/_internal/response.py:',
        '   - Import AlmaResponse from src.client.AlmaAPIClient',
        '   - Re-export it: __all__ = ["AlmaResponse"]',
        '',
        '4. Create src/almaapitk/_internal/exceptions.py:',
        '   - Import AlmaAPIError, AlmaValidationError from src.client.AlmaAPIClient',
        '   - Re-export them: __all__ = ["AlmaAPIError", "AlmaValidationError"]',
        '',
        'CRITICAL: Each module must only import and re-export - no side effects',
        'CRITICAL: Use "from src.client.AlmaAPIClient import X" (the full path)',
        'Do NOT add __version__ to _internal - it stays in almaapitk/__init__.py',
        'Use the Write tool to create each file'
      ],
      outputFormat: 'JSON with success (boolean), filesCreated (array of strings), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filesCreated'],
      properties: {
        success: { type: 'boolean' },
        filesCreated: { type: 'array', items: { type: 'string' } },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const updateInitToUseInternalTask = defineTask('update-init-to-use-internal', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update __init__.py to import from _internal',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python package maintainer',
      task: 'Update almaapitk/__init__.py to import public symbols from _internal',
      context: {
        constraints: args.constraints
      },
      instructions: [
        'Read src/almaapitk/__init__.py using the Read tool',
        'Then use the Edit tool to update the lazy imports:',
        '',
        'Change the _lazy_imports dictionary to import from almaapitk._internal:',
        '  OLD: ("client.AlmaAPIClient", "AlmaAPIClient")',
        '  NEW: ("almaapitk._internal", "AlmaAPIClient")',
        '',
        'The new _lazy_imports should be:',
        '_lazy_imports = {',
        '    "AlmaAPIClient": ("almaapitk._internal", "AlmaAPIClient"),',
        '    "AlmaResponse": ("almaapitk._internal", "AlmaResponse"),',
        '    "AlmaAPIError": ("almaapitk._internal", "AlmaAPIError"),',
        '    "AlmaValidationError": ("almaapitk._internal", "AlmaValidationError"),',
        '}',
        '',
        'Keep __version__ in the module (do NOT import it from _internal)',
        'Keep __all__ unchanged',
        'Keep the lazy import __getattr__ mechanism unchanged',
        'Update the IMPLEMENTATION NOTE in the docstring to mention _internal',
        'Do NOT change the overall structure or add any side effects'
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

export const runSmokeTestTask = defineTask('run-smoke-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Run smoke_import.py validation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer',
      task: 'Run the smoke test to validate public API',
      context: {},
      instructions: [
        'Run the following commands using the Bash tool:',
        '1. cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python scripts/smoke_import.py',
        '2. cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python -c "import almaapitk; print(almaapitk.__version__); print(almaapitk.__all__)"',
        'Capture the output of each command',
        'Mark success=true only if both pass',
        'Report the results'
      ],
      outputFormat: 'JSON with success (boolean), smokeTestOutput (string), versionCheck (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'smokeTestOutput'],
      properties: {
        success: { type: 'boolean' },
        smokeTestOutput: { type: 'string' },
        versionCheck: { type: 'string' },
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
      task: 'Commit Phase B2 changes and push to main branch',
      context: {
        filesModified: args.filesModified
      },
      instructions: [
        'Stage the new and modified files using git add:',
        '  - tests/test_public_api_contract.py',
        '  - src/almaapitk/_internal/ (the entire directory)',
        '  - src/almaapitk/__init__.py',
        'Create a commit with a detailed message using HEREDOC format:',
        '  Title: "Add internal namespace and public API contract tests (Phase B2)"',
        '  Body:',
        '    - Create tests/test_public_api_contract.py for TDD validation',
        '    - Add src/almaapitk/_internal/ with thin re-export modules',
        '    - Update __init__.py to import from _internal namespace',
        '    - Decouples public API from internal implementation layout',
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
