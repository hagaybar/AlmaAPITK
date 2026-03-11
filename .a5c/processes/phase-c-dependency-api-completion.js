/**
 * @process phase-c-dependency-api-completion
 * @description Phase C: Dependency-driven API completion - scan projects for imports and extend public API
 * @inputs { safetyConstraints: array }
 * @outputs { success: boolean, inventoryReport: object, apiAdditions: array, migrationMap: object }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

export async function process(inputs, ctx) {
  const { safetyConstraints } = inputs;

  const startTime = ctx.now();
  const artifacts = [];

  ctx.log('info', 'Phase C: Dependency-driven API completion starting');

  // ============================================================================
  // PHASE 1: INVENTORY - Scan all projects for imports
  // ============================================================================

  ctx.log('info', 'Phase 1: Scanning projects for import statements');

  const inventory = await ctx.task(scanProjectImportsTask, {
    projectsDir: 'src/projects',
    safetyConstraints
  });

  if (!inventory.success) {
    return {
      success: false,
      error: 'Failed to scan project imports',
      details: inventory
    };
  }

  artifacts.push(...(inventory.artifacts || []));

  // ============================================================================
  // PHASE 2: ANALYZE - Derive candidate public API symbols
  // ============================================================================

  ctx.log('info', 'Phase 2: Analyzing imports to derive candidate API symbols');

  const analysis = await ctx.task(analyzeImportsTask, {
    inventoryReport: inventory.report,
    safetyConstraints
  });

  if (!analysis.success) {
    return {
      success: false,
      error: 'Failed to analyze imports',
      details: analysis
    };
  }

  artifacts.push(...(analysis.artifacts || []));

  // ============================================================================
  // PHASE 3: DESIGN - Propose minimal public API additions
  // ============================================================================

  ctx.log('info', 'Phase 3: Designing minimal public API additions');

  const design = await ctx.task(designPublicApiTask, {
    candidateSymbols: analysis.candidateSymbols,
    currentApi: analysis.currentApi,
    safetyConstraints
  });

  if (!design.success) {
    return {
      success: false,
      error: 'Failed to design public API',
      details: design
    };
  }

  artifacts.push(...(design.artifacts || []));

  // ============================================================================
  // PHASE 4: IMPLEMENT - Create/extend _internal bridge modules
  // ============================================================================

  ctx.log('info', 'Phase 4: Implementing _internal bridge modules');

  const implementation = await ctx.task(implementInternalBridgeTask, {
    apiDesign: design.apiDesign,
    safetyConstraints
  });

  if (!implementation.success) {
    return {
      success: false,
      error: 'Failed to implement _internal bridge',
      details: implementation
    };
  }

  artifacts.push(...(implementation.artifacts || []));

  // ============================================================================
  // PHASE 5: UPDATE PUBLIC FACADE
  // ============================================================================

  ctx.log('info', 'Phase 5: Updating almaapitk/__init__.py public facade');

  const facade = await ctx.task(updatePublicFacadeTask, {
    apiDesign: design.apiDesign,
    safetyConstraints
  });

  if (!facade.success) {
    return {
      success: false,
      error: 'Failed to update public facade',
      details: facade
    };
  }

  artifacts.push(...(facade.artifacts || []));

  // ============================================================================
  // PHASE 6: CREATE/EXTEND TESTS
  // ============================================================================

  ctx.log('info', 'Phase 6: Creating/extending tests for new API surface');

  const tests = await ctx.task(createTestsForNewApiTask, {
    apiDesign: design.apiDesign,
    safetyConstraints
  });

  if (!tests.success) {
    return {
      success: false,
      error: 'Failed to create tests',
      details: tests
    };
  }

  artifacts.push(...(tests.artifacts || []));

  // ============================================================================
  // PHASE 7: RUN TESTS
  // ============================================================================

  ctx.log('info', 'Phase 7: Running tests to validate changes');

  const testRun = await ctx.task(runAllTestsTask, {
    phase: 'validation'
  });

  if (!testRun.success) {
    return {
      success: false,
      error: 'Tests failed after implementation',
      details: testRun
    };
  }

  artifacts.push(...(testRun.artifacts || []));

  // ============================================================================
  // PHASE 8: RUN SMOKE TEST
  // ============================================================================

  ctx.log('info', 'Phase 8: Running smoke_import.py validation');

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
  // PHASE 9: CREATE MIGRATION MAP DOCUMENTATION
  // ============================================================================

  ctx.log('info', 'Phase 9: Creating migration map documentation');

  const migrationDoc = await ctx.task(createMigrationMapTask, {
    inventoryReport: inventory.report,
    apiDesign: design.apiDesign
  });

  if (!migrationDoc.success) {
    return {
      success: false,
      error: 'Failed to create migration map',
      details: migrationDoc
    };
  }

  artifacts.push(...(migrationDoc.artifacts || []));

  // ============================================================================
  // PHASE 10: COMMIT AND PUSH
  // ============================================================================

  ctx.log('info', 'Phase 10: Committing and pushing to main');

  const commit = await ctx.task(commitAndPushTask, {
    filesModified: [
      ...implementation.filesCreated || [],
      ...implementation.filesModified || [],
      ...facade.filesModified || [],
      ...tests.filesCreated || [],
      ...migrationDoc.filesCreated || []
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
    inventoryReport: inventory.report,
    apiDesign: design.apiDesign,
    apiAdditions: design.additions,
    migrationMap: migrationDoc.migrationMap,
    commitHash: commit.commitHash,
    artifacts,
    duration,
    metadata: {
      processId: 'phase-c-dependency-api-completion',
      timestamp: startTime
    }
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const scanProjectImportsTask = defineTask('scan-project-imports', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Scan all projects for import statements',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python library engineer performing static analysis',
      task: 'Scan ALL Python files under src/projects/ and extract import statements, producing a categorized report',
      context: {
        projectsDir: args.projectsDir,
        safetyConstraints: args.safetyConstraints
      },
      instructions: [
        'Walk all Python files under src/projects/ using Glob tool to find them',
        'For each Python file, read it and extract all import statements (import X, from X import Y)',
        '',
        'Categorize each import as:',
        '  a) already_almaapitk: imports from almaapitk',
        '  b) legacy_internal: imports from src.*, client.*, domains.*, utils.*, alma_logging.*',
        '  c) external_lib: standard library and third-party packages',
        '',
        'Produce a JSON report with structure:',
        '{',
        '  "projects": {',
        '    "<project_name>": {',
        '      "files": ["<file_path>", ...],',
        '      "imports": {',
        '        "already_almaapitk": ["<import_line>", ...],',
        '        "legacy_internal": ["<import_line>", ...],',
        '        "external_lib": ["<import_line>", ...]',
        '      }',
        '    }',
        '  },',
        '  "summary": {',
        '    "total_projects": <n>,',
        '    "total_files": <n>,',
        '    "legacy_imports_count": <n>,',
        '    "unique_legacy_symbols": ["symbol1", "symbol2", ...]',
        '  }',
        '}',
        '',
        'Return this report in the result'
      ],
      outputFormat: 'JSON with success (boolean), report (object), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'report'],
      properties: {
        success: { type: 'boolean' },
        report: { type: 'object' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const analyzeImportsTask = defineTask('analyze-imports', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Analyze imports to derive candidate API symbols',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python API designer',
      task: 'Analyze the inventory report and derive candidate public API symbols needed for migration',
      context: {
        inventoryReport: args.inventoryReport,
        safetyConstraints: args.safetyConstraints
      },
      instructions: [
        'Analyze the legacy_internal imports from all projects',
        '',
        'Read the current public API from src/almaapitk/__init__.py',
        '',
        'Group candidate symbols into categories:',
        '  - Core client + session/request handling',
        '  - Response models',
        '  - Exceptions/error types',
        '  - Configuration helpers',
        '  - Utilities (pagination, retries, logging helpers)',
        '  - Domain endpoint wrappers (ONLY if widely reused and toolkit-level)',
        '',
        'For each symbol, track:',
        '  - symbol name',
        '  - current source module (legacy location)',
        '  - which projects use it (frequency)',
        '',
        'Identify duplicates or inconsistent imports across projects',
        '',
        'Return candidateSymbols grouped by category and currentApi listing what is already exported'
      ],
      outputFormat: 'JSON with success (boolean), candidateSymbols (object), currentApi (array), duplicates (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'candidateSymbols', 'currentApi'],
      properties: {
        success: { type: 'boolean' },
        candidateSymbols: { type: 'object' },
        currentApi: { type: 'array' },
        duplicates: { type: 'array' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const designPublicApiTask = defineTask('design-public-api', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Design minimal migration-ready public API',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python API designer with focus on minimal, stable APIs',
      task: 'Design a minimal public API list (aim: 10-30 symbols) sufficient for project migration',
      context: {
        candidateSymbols: args.candidateSymbols,
        currentApi: args.currentApi,
        safetyConstraints: args.safetyConstraints
      },
      instructions: [
        'Review the candidate symbols from the analysis',
        '',
        'Design a public API that:',
        '  - Covers the most frequently used symbols across projects',
        '  - Stays SMALL and curated (10-30 symbols, not hundreds)',
        '  - Focuses on core toolkit functionality, not project-specific code',
        '  - Keeps backwards compatibility with current exports',
        '',
        'For each symbol to ADD (not already in currentApi), specify:',
        '  - intended_public_name: How it should be exported',
        '  - source_module: Current legacy location (e.g., src.domains.users.Users)',
        '  - rationale: Which projects use it, how frequently',
        '  - internal_module: Which _internal module it belongs to',
        '',
        'Explicitly mark what will NOT be public (project-level code)',
        '',
        'IMPORTANT: Only add symbols that are truly toolkit-level.',
        '  - Domain classes (Users, Bibs, Admin, Acquisitions) are toolkit-level',
        '  - Project-specific scripts are NOT toolkit-level',
        '',
        'Return apiDesign with: additions (array of symbols to add), exclusions (array of symbols to keep project-level), currentApi (unchanged)'
      ],
      outputFormat: 'JSON with success (boolean), apiDesign (object with additions, exclusions, currentApi), additions (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'apiDesign', 'additions'],
      properties: {
        success: { type: 'boolean' },
        apiDesign: { type: 'object' },
        additions: { type: 'array' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const implementInternalBridgeTask = defineTask('implement-internal-bridge', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement _internal bridge modules for new API symbols',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python package maintainer',
      task: 'Create or extend modules under src/almaapitk/_internal/ to re-export the new API symbols',
      context: {
        apiDesign: args.apiDesign,
        safetyConstraints: args.safetyConstraints
      },
      instructions: [
        'First read the existing _internal modules to understand current structure:',
        '  - src/almaapitk/_internal/__init__.py',
        '  - src/almaapitk/_internal/client.py',
        '  - src/almaapitk/_internal/response.py',
        '  - src/almaapitk/_internal/exceptions.py',
        '',
        'For each symbol in apiDesign.additions:',
        '  1. Determine which _internal module it belongs to based on internal_module field',
        '  2. Create or update the appropriate _internal module to import and re-export the symbol',
        '  3. Update _internal/__init__.py to export the new symbols',
        '',
        'Structure by concern:',
        '  - _internal/client.py - AlmaAPIClient',
        '  - _internal/response.py - AlmaResponse',
        '  - _internal/exceptions.py - AlmaAPIError, AlmaValidationError, AlmaRateLimitError',
        '  - _internal/domains.py - Domain classes (Users, Bibs, Admin, Acquisitions, Analytics, ResourceSharing)',
        '  - _internal/utils.py - Utility functions if needed',
        '',
        'CRITICAL RULES:',
        '  - DO NOT modify any legacy modules under src/client/, src/domains/, etc.',
        '  - Each _internal module must only import and re-export - NO side effects',
        '  - Use full import paths: from src.domains.users import Users',
        '  - Avoid circular imports',
        '',
        'Use Read tool to check existing files, then Write or Edit tool to create/update _internal modules',
        '',
        'Return filesCreated and filesModified arrays'
      ],
      outputFormat: 'JSON with success (boolean), filesCreated (array), filesModified (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        filesCreated: { type: 'array' },
        filesModified: { type: 'array' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const updatePublicFacadeTask = defineTask('update-public-facade', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update almaapitk/__init__.py public facade',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python package maintainer',
      task: 'Update src/almaapitk/__init__.py to re-export the new curated public API from _internal',
      context: {
        apiDesign: args.apiDesign,
        safetyConstraints: args.safetyConstraints
      },
      instructions: [
        'Read the current src/almaapitk/__init__.py',
        '',
        'For each symbol in apiDesign.additions, add it to:',
        '  1. __all__ list',
        '  2. _lazy_imports dictionary mapping to almaapitk._internal',
        '',
        'Keep the existing lazy import mechanism unchanged',
        'Keep __version__ in place',
        '',
        'Update the module docstring to document the new symbols',
        '',
        'CRITICAL: No import-time side effects',
        '  - No env validation',
        '  - No config reading',
        '  - No file I/O',
        '  - No network calls',
        '',
        'Use Edit tool to update the file',
        '',
        'Return filesModified array'
      ],
      outputFormat: 'JSON with success (boolean), filesModified (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        filesModified: { type: 'array' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const createTestsForNewApiTask = defineTask('create-tests-for-new-api', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create/extend tests for new API surface',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python TDD developer',
      task: 'Extend tests/test_public_api_contract.py to cover the new API symbols',
      context: {
        apiDesign: args.apiDesign,
        safetyConstraints: args.safetyConstraints
      },
      instructions: [
        'Read the existing tests/test_public_api_contract.py',
        '',
        'Add tests for:',
        '  1. Each new symbol in apiDesign.additions is accessible from almaapitk',
        '  2. Each new symbol in __all__ exists and is importable',
        '  3. Type checks where appropriate (e.g., AlmaRateLimitError is an Exception subclass)',
        '',
        'Also add a migration target test (can be skipped for now):',
        '  - Test that attempts to import update_expired_users_emails project',
        '  - This test documents what the project needs and will pass after migration',
        '  - Mark with @unittest.skip("Migration target - enable after project migration")',
        '',
        'Keep tests simple and focused',
        'Do NOT make any network calls in tests',
        '',
        'Use Edit tool to update the test file',
        '',
        'Return filesCreated array with the test file path'
      ],
      outputFormat: 'JSON with success (boolean), filesCreated (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        filesCreated: { type: 'array' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const runAllTestsTask = defineTask('run-all-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: `Run all unit tests (${args.phase})`,
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
        'Mark success=true only if all tests pass (skipped tests are OK)',
        'Report the test results summary'
      ],
      outputFormat: 'JSON with success (boolean), testOutput (string), testsRun (number), testsPassed (number), testsSkipped (number), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'testOutput'],
      properties: {
        success: { type: 'boolean' },
        testOutput: { type: 'string' },
        testsRun: { type: 'number' },
        testsPassed: { type: 'number' },
        testsSkipped: { type: 'number' },
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

export const createMigrationMapTask = defineTask('create-migration-map', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create docs/MIGRATION_MAP.md documentation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Technical documentation writer',
      task: 'Create docs/MIGRATION_MAP.md documenting legacy imports and recommended replacements',
      context: {
        inventoryReport: args.inventoryReport,
        apiDesign: args.apiDesign
      },
      instructions: [
        'Create docs/MIGRATION_MAP.md with the following structure:',
        '',
        '# Migration Map',
        '',
        '## Overview',
        'Brief description of the migration from legacy imports to almaapitk',
        '',
        '## Current Public API',
        'List all symbols exported by almaapitk',
        '',
        '## Per-Project Migration Guide',
        '',
        'For each project in inventoryReport:',
        '  ### <Project Name>',
        '  **Files:** list of files',
        '  **Legacy imports used:**',
        '    - `from src.X import Y` -> `from almaapitk import Y`',
        '  **Recommended replacements:**',
        '    - concrete examples',
        '',
        '## Pilot Project: update_expired_users_emails',
        'Detailed migration example for the pilot project',
        'Show before/after import statements',
        '',
        '## Symbols NOT in Public API',
        'List of symbols that remain project-level and should not be imported from almaapitk',
        '',
        'Create the file using Write tool',
        '',
        'Return filesCreated array and migrationMap object'
      ],
      outputFormat: 'JSON with success (boolean), filesCreated (array), migrationMap (object), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        filesCreated: { type: 'array' },
        migrationMap: { type: 'object' },
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
      task: 'Commit Phase C changes and push to main branch',
      context: {
        filesModified: args.filesModified
      },
      instructions: [
        'First run git status to see all changes',
        '',
        'Stage the relevant files using git add:',
        '  - src/almaapitk/_internal/ (all files)',
        '  - src/almaapitk/__init__.py',
        '  - tests/test_public_api_contract.py',
        '  - docs/MIGRATION_MAP.md',
        '  - .a5c/processes/phase-c-dependency-api-completion.js',
        '',
        'Also include any run artifacts under .a5c/runs/',
        '',
        'Create a commit with a detailed message using HEREDOC format:',
        '  Title: "Extend public API for project migration (Phase C)"',
        '  Body:',
        '    - Scan projects for legacy imports and analyze dependencies',
        '    - Add domain classes to public API (Users, Bibs, Admin, etc.)',
        '    - Extend _internal bridge modules for new symbols',
        '    - Update tests for new API surface',
        '    - Create docs/MIGRATION_MAP.md with per-project guidance',
        '  Include: Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>',
        '',
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
