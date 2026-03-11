/**
 * @process phase-d-pilot-migration
 * @description Phase D: TDD-first migration of update_expired_users_emails to almaapitk public API
 * @inputs { pilotProject: string, safetyConstraints: array }
 * @outputs { success: boolean, filesChanged: array, testsPassed: boolean }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

export async function process(inputs, ctx) {
  const { pilotProject, safetyConstraints } = inputs;

  const startTime = ctx.now();
  const artifacts = [];

  ctx.log('info', 'Phase D: TDD-first pilot project migration starting');

  // ============================================================================
  // PHASE 1: ADD FAILING TEST (TDD - Red)
  // ============================================================================

  ctx.log('info', 'Phase 1: Creating migration guard test (should fail initially)');

  const testCreation = await ctx.task(createMigrationGuardTestTask, {
    pilotProject,
    safetyConstraints
  });

  if (!testCreation.success) {
    return {
      success: false,
      error: 'Failed to create migration guard test',
      details: testCreation
    };
  }

  artifacts.push(...(testCreation.artifacts || []));

  // ============================================================================
  // PHASE 2: VERIFY TEST FAILS (TDD - Confirm Red)
  // ============================================================================

  ctx.log('info', 'Phase 2: Verifying migration guard test fails before migration');

  const testFailsCheck = await ctx.task(verifyTestFailsTask, {
    testFile: testCreation.testFile
  });

  // We expect it to fail (return testFailed: true)
  if (!testFailsCheck.testFailed) {
    ctx.log('warn', 'Test unexpectedly passed - project may already be migrated');
  }

  artifacts.push(...(testFailsCheck.artifacts || []));

  // ============================================================================
  // PHASE 3: PERFORM MIGRATION (TDD - Green)
  // ============================================================================

  ctx.log('info', 'Phase 3: Migrating pilot project imports to almaapitk');

  const migration = await ctx.task(performMigrationTask, {
    pilotProject,
    safetyConstraints
  });

  if (!migration.success) {
    return {
      success: false,
      error: 'Failed to migrate pilot project',
      details: migration
    };
  }

  artifacts.push(...(migration.artifacts || []));

  // ============================================================================
  // PHASE 4: VERIFY TEST PASSES (TDD - Confirm Green)
  // ============================================================================

  ctx.log('info', 'Phase 4: Verifying migration guard test now passes');

  const testPassesCheck = await ctx.task(verifyTestPassesTask, {
    testFile: testCreation.testFile
  });

  if (!testPassesCheck.testPassed) {
    return {
      success: false,
      error: 'Migration guard test still failing after migration',
      details: testPassesCheck
    };
  }

  artifacts.push(...(testPassesCheck.artifacts || []));

  // ============================================================================
  // PHASE 5: RUN ALL VALIDATION
  // ============================================================================

  ctx.log('info', 'Phase 5: Running full validation suite');

  const validation = await ctx.task(runFullValidationTask, {
    pilotProject
  });

  if (!validation.success) {
    return {
      success: false,
      error: 'Validation failed',
      details: validation
    };
  }

  artifacts.push(...(validation.artifacts || []));

  // ============================================================================
  // PHASE 6: UPDATE DOCUMENTATION
  // ============================================================================

  ctx.log('info', 'Phase 6: Updating migration documentation');

  const docUpdate = await ctx.task(updateDocumentationTask, {
    pilotProject,
    migrationDetails: migration.details
  });

  artifacts.push(...(docUpdate.artifacts || []));

  // ============================================================================
  // PHASE 7: COMMIT AND PUSH
  // ============================================================================

  ctx.log('info', 'Phase 7: Committing and pushing to main');

  const commit = await ctx.task(commitAndPushTask, {
    filesChanged: [
      ...testCreation.filesCreated || [],
      ...migration.filesModified || [],
      ...docUpdate.filesModified || []
    ],
    pilotProject
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
    pilotProject,
    filesChanged: [
      ...testCreation.filesCreated || [],
      ...migration.filesModified || [],
      ...docUpdate.filesModified || []
    ],
    testsPassed: true,
    commitHash: commit.commitHash,
    artifacts,
    duration,
    metadata: {
      processId: 'phase-d-pilot-migration',
      timestamp: startTime
    }
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const createMigrationGuardTestTask = defineTask('create-migration-guard-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create migration guard test (TDD Red phase)',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python TDD developer',
      task: 'Create a migration guard test that verifies the pilot project uses only almaapitk imports',
      context: {
        pilotProject: args.pilotProject,
        safetyConstraints: args.safetyConstraints
      },
      instructions: [
        'Create tests/test_pilot_migration.py with a test class TestPilotMigration',
        '',
        'The test should:',
        '1. Read the source file(s) of the pilot project',
        '2. Parse import statements (can use simple string matching or AST)',
        '3. Assert that NO imports match patterns:',
        '   - "from src." or "import src."',
        '   - "from client." or "import client."',
        '   - "from domains." or "import domains."',
        '   - "from utils." or "import utils."',
        '4. Assert that imports from almaapitk ARE present',
        '',
        'File to check: src/projects/update_expired_users_emails/update_expired_user_emails.py',
        '',
        'Use simple string/regex matching for reliability:',
        '  - Read file content',
        '  - Check for forbidden patterns',
        '  - Check for required patterns',
        '',
        'Use Write tool to create the test file',
        '',
        'Return success=true, testFile path, and filesCreated array'
      ],
      outputFormat: 'JSON with success (boolean), testFile (string), filesCreated (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'testFile'],
      properties: {
        success: { type: 'boolean' },
        testFile: { type: 'string' },
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

export const verifyTestFailsTask = defineTask('verify-test-fails', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify migration guard test fails (TDD Red confirmation)',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python test runner',
      task: 'Run the migration guard test and confirm it fails (expected before migration)',
      context: {
        testFile: args.testFile
      },
      instructions: [
        'Run the migration guard test using Bash tool:',
        'cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python -m unittest tests.test_pilot_migration -v 2>&1',
        '',
        'Capture the output',
        'The test SHOULD FAIL at this point (before migration)',
        '',
        'Return testFailed=true if test failed (which is expected)',
        'Return testFailed=false if test passed (unexpected - already migrated?)'
      ],
      outputFormat: 'JSON with success (boolean), testFailed (boolean), testOutput (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'testFailed'],
      properties: {
        success: { type: 'boolean' },
        testFailed: { type: 'boolean' },
        testOutput: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const performMigrationTask = defineTask('perform-migration', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Migrate pilot project imports to almaapitk (TDD Green phase)',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python engineer performing import migration',
      task: 'Replace legacy imports in the pilot project with almaapitk public API imports',
      context: {
        pilotProject: args.pilotProject,
        safetyConstraints: args.safetyConstraints
      },
      instructions: [
        'Read the pilot project file:',
        '  src/projects/update_expired_users_emails/update_expired_user_emails.py',
        '',
        'Find all legacy import statements and replace them:',
        '',
        'BEFORE:',
        '  from src.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError, AlmaValidationError',
        '  from src.domains.admin import Admin',
        '  from src.domains.users import Users',
        '',
        'AFTER:',
        '  from almaapitk import (',
        '      AlmaAPIClient,',
        '      AlmaAPIError,',
        '      AlmaValidationError,',
        '      Admin,',
        '      Users,',
        '  )',
        '',
        'Use Edit tool to make the changes',
        '',
        'CRITICAL RULES:',
        '  - ONLY change import statements',
        '  - Do NOT change any other code',
        '  - Do NOT change behavior, CLI handling, or dry-run logic',
        '  - Keep the comment "# Import our domain classes" or update it to mention almaapitk',
        '',
        'Return success=true, filesModified array, and details object with before/after examples'
      ],
      outputFormat: 'JSON with success (boolean), filesModified (array), details (object with before/after), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filesModified'],
      properties: {
        success: { type: 'boolean' },
        filesModified: { type: 'array' },
        details: { type: 'object' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const verifyTestPassesTask = defineTask('verify-test-passes', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Verify migration guard test passes (TDD Green confirmation)',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python test runner',
      task: 'Run the migration guard test and confirm it now passes after migration',
      context: {
        testFile: args.testFile
      },
      instructions: [
        'Run the migration guard test using Bash tool:',
        'cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python -m unittest tests.test_pilot_migration -v 2>&1',
        '',
        'Capture the output',
        'The test SHOULD PASS at this point (after migration)',
        '',
        'Return testPassed=true if test passed',
        'Return testPassed=false if test failed (migration incomplete?)'
      ],
      outputFormat: 'JSON with success (boolean), testPassed (boolean), testOutput (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'testPassed'],
      properties: {
        success: { type: 'boolean' },
        testPassed: { type: 'boolean' },
        testOutput: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const runFullValidationTask = defineTask('run-full-validation', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Run full validation suite',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python QA engineer',
      task: 'Run complete validation to ensure migration did not break anything',
      context: {
        pilotProject: args.pilotProject
      },
      instructions: [
        'Run the following validations using Bash tool:',
        '',
        '1. Smoke test:',
        '   cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python scripts/smoke_import.py',
        '',
        '2. Public API contract tests:',
        '   cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python -m unittest tests.test_public_api_contract -v 2>&1 | tail -20',
        '',
        '3. Pilot project import check:',
        '   cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python -c "from src.projects.update_expired_users_emails.update_expired_user_emails import EmailUpdateScript; print(\'Import OK\')"',
        '',
        '4. Migration guard test:',
        '   cd /home/hagaybar/projects/AlmaAPITK && PYTHONPATH=./src python -m unittest tests.test_pilot_migration -v 2>&1',
        '',
        'Capture all outputs and verify all pass',
        'Return success=true only if ALL validations pass'
      ],
      outputFormat: 'JSON with success (boolean), smokeTestPassed (boolean), contractTestsPassed (boolean), importCheckPassed (boolean), migrationTestPassed (boolean), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        smokeTestPassed: { type: 'boolean' },
        contractTestsPassed: { type: 'boolean' },
        importCheckPassed: { type: 'boolean' },
        migrationTestPassed: { type: 'boolean' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const updateDocumentationTask = defineTask('update-documentation', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update migration documentation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Technical documentation writer',
      task: 'Update docs/MIGRATION_MAP.md to mark pilot project as migrated',
      context: {
        pilotProject: args.pilotProject,
        migrationDetails: args.migrationDetails
      },
      instructions: [
        'Read docs/MIGRATION_MAP.md',
        '',
        'Find the section for update_expired_users_emails',
        '',
        'Update its status from "Ready for migration (pilot candidate)" to "MIGRATED (Phase D)"',
        '',
        'Keep the change minimal - just update the status',
        '',
        'Use Edit tool to make the change',
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

export const commitAndPushTask = defineTask('commit-and-push', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Commit and push to main',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git workflow expert',
      task: 'Commit Phase D migration changes and push to main branch',
      context: {
        filesChanged: args.filesChanged,
        pilotProject: args.pilotProject
      },
      instructions: [
        'First run git status to see all changes',
        '',
        'Stage the relevant files using git add:',
        '  - tests/test_pilot_migration.py',
        '  - src/projects/update_expired_users_emails/update_expired_user_emails.py',
        '  - docs/MIGRATION_MAP.md',
        '  - .a5c/processes/phase-d-pilot-migration.js (the process file)',
        '',
        'Create a commit with message:',
        '  "Migrate update_expired_users_emails to almaapitk public API"',
        '',
        'Body should include:',
        '  - TDD approach: added migration guard test first',
        '  - Changed imports from src.* to almaapitk',
        '  - All validations pass',
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
