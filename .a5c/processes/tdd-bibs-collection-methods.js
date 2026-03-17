/**
 * @process almaapitk/tdd-bibs-collection-methods
 * @description TDD process for adding collection methods to BibliographicRecords domain
 * @skill python-dev-expert
 * @skill alma-api-expert
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * TDD Process for Adding Collection Methods to bibs.py
 *
 * Methods to implement:
 * 1. get_collection_members(collection_id, limit, offset) - GET /bibs/collections/{pid}/bibs
 * 2. add_to_collection(collection_id, mms_id) - POST /bibs/collections/{pid}/bibs
 * 3. remove_from_collection(collection_id, mms_id) - DELETE /bibs/collections/{pid}/bibs/{mms_id}
 *
 * TDD Workflow:
 * - Phase 1: Write integration tests first
 * - Phase 2: Implement methods to pass tests
 * - Phase 3: Refactor and verify
 */
export async function process(inputs, ctx) {
  const {
    targetFile = 'src/almaapitk/domains/bibs.py',
    testFile = 'tests/integration/domains/test_bibs_collections.py',
    sandboxCollectionId = null, // Will be provided by user at breakpoint
    methods = [
      {
        name: 'get_collection_members',
        endpoint: 'GET /bibs/collections/{collection_id}/bibs',
        params: ['collection_id', 'limit', 'offset'],
        returns: 'AlmaResponse with list of bibs'
      },
      {
        name: 'add_to_collection',
        endpoint: 'POST /bibs/collections/{collection_id}/bibs',
        params: ['collection_id', 'mms_id'],
        returns: 'AlmaResponse with added bib'
      },
      {
        name: 'remove_from_collection',
        endpoint: 'DELETE /bibs/collections/{collection_id}/bibs/{mms_id}',
        params: ['collection_id', 'mms_id'],
        returns: 'AlmaResponse (empty on success)'
      }
    ]
  } = inputs;

  // ============================================================================
  // PHASE 1: WRITE INTEGRATION TESTS FIRST (RED)
  // ============================================================================

  const testWriteResult = await ctx.task(writeIntegrationTestsTask, {
    testFile,
    methods,
    targetFile
  });

  // Run tests - they should fail (no implementation yet)
  const initialTestResult = await ctx.task(runPytestTask, {
    testFile,
    expectFailure: true
  });

  // ============================================================================
  // PHASE 2: IMPLEMENT METHODS (GREEN)
  // ============================================================================

  const implementationResult = await ctx.task(implementMethodsTask, {
    targetFile,
    methods,
    testFile,
    existingTests: testWriteResult
  });

  // Run tests again - should pass now
  const greenTestResult = await ctx.task(runPytestTask, {
    testFile,
    expectFailure: false
  });

  // ============================================================================
  // PHASE 3: REFACTOR AND VERIFY
  // ============================================================================

  // Check code quality
  const qualityResult = await ctx.task(codeQualityCheckTask, {
    targetFile,
    testFile
  });

  // Final integration test with real API (breakpoint for collection ID)
  await ctx.breakpoint({
    question: 'Provide a Sandbox collection ID for integration testing, or approve to skip live API tests',
    title: 'Integration Test Setup',
    context: {
      note: 'If you have a test collection in Alma Sandbox, provide its ID. Otherwise, skip.'
    }
  });

  // Final verification
  const finalResult = await ctx.task(finalVerificationTask, {
    targetFile,
    testFile,
    methods
  });

  return {
    success: true,
    methodsImplemented: methods.map(m => m.name),
    testFile,
    targetFile,
    testResults: {
      initial: initialTestResult,
      green: greenTestResult
    },
    quality: qualityResult,
    final: finalResult
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

/**
 * Write integration tests for collection methods
 */
export const writeIntegrationTestsTask = defineTask('write-integration-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Write integration tests for collection methods',
  description: 'Create pytest test file with tests for all collection methods',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer specializing in TDD and API testing',
      task: `Create an integration test file for the collection methods in BibliographicRecords domain.

Target test file: ${args.testFile}
Target implementation: ${args.targetFile}

Methods to test:
${JSON.stringify(args.methods, null, 2)}

Instructions:
1. Read the existing bibs.py to understand the patterns used
2. Read existing tests in tests/ to follow the same testing patterns
3. Create test file with:
   - Imports and fixtures (using AlmaAPIClient with SANDBOX environment)
   - Test class TestBibsCollections
   - test_get_collection_members() - test listing bibs in a collection
   - test_add_to_collection() - test adding a bib to collection
   - test_remove_from_collection() - test removing a bib from collection
   - test_get_collection_members_pagination() - test limit/offset params
   - Error case tests (invalid collection_id, invalid mms_id)
4. Use pytest fixtures for client setup
5. Use @pytest.mark.integration for tests that need API
6. Write the actual test file using the Write tool

Return a JSON summary of what was created.`,
      outputFormat: 'JSON with testFile (string), testsCreated (array of test names), imports (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['testFile', 'testsCreated'],
      properties: {
        testFile: { type: 'string' },
        testsCreated: { type: 'array', items: { type: 'string' } },
        imports: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

/**
 * Run pytest on the test file
 */
export const runPytestTask = defineTask('run-pytest', (args, taskCtx) => ({
  kind: 'shell',
  title: args.expectFailure ? 'Run tests (expect failures)' : 'Run tests (expect pass)',
  description: `Run pytest on ${args.testFile}`,

  shell: {
    command: `cd /home/hagaybar/projects/AlmaAPITK && poetry run pytest ${args.testFile} -v --tb=short 2>&1 || true`,
    timeout: 60000
  },

  io: {
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

/**
 * Implement the collection methods in bibs.py
 */
export const implementMethodsTask = defineTask('implement-methods', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement collection methods in bibs.py',
  description: 'Add the collection management methods to BibliographicRecords class',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer implementing Alma API client methods',
      task: `Implement the collection methods in the BibliographicRecords class.

Target file: ${args.targetFile}
Test file: ${args.testFile}

Methods to implement:
${JSON.stringify(args.methods, null, 2)}

Instructions:
1. Read the existing bibs.py to understand the patterns (get_record, create_record, etc.)
2. Read the test file to understand what's being tested
3. Add the three collection methods to the BibliographicRecords class:

   def get_collection_members(self, collection_id: str, limit: int = 100, offset: int = 0) -> AlmaResponse:
       """Get bibliographic records in a collection."""
       # GET /bibs/collections/{collection_id}/bibs

   def add_to_collection(self, collection_id: str, mms_id: str) -> AlmaResponse:
       """Add a bibliographic record to a collection."""
       # POST /bibs/collections/{collection_id}/bibs with mms_id in body

   def remove_from_collection(self, collection_id: str, mms_id: str) -> AlmaResponse:
       """Remove a bibliographic record from a collection."""
       # DELETE /bibs/collections/{collection_id}/bibs/{mms_id}

4. Follow existing patterns:
   - Use AlmaValidationError for input validation
   - Use self.client.get/post/delete methods
   - Add logging with self.logger.info
   - Return AlmaResponse
5. Use the Edit tool to add methods to bibs.py

Return a JSON summary of what was implemented.`,
      outputFormat: 'JSON with methodsAdded (array), linesAdded (number), file (string)'
    },
    outputSchema: {
      type: 'object',
      required: ['methodsAdded', 'file'],
      properties: {
        methodsAdded: { type: 'array', items: { type: 'string' } },
        linesAdded: { type: 'number' },
        file: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

/**
 * Code quality check
 */
export const codeQualityCheckTask = defineTask('code-quality-check', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Check code quality',
  description: 'Review implementation for quality and consistency',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python code reviewer',
      task: `Review the implemented collection methods for code quality.

Target file: ${args.targetFile}
Test file: ${args.testFile}

Check for:
1. Consistent coding style with existing methods
2. Proper error handling and validation
3. Complete docstrings
4. Appropriate logging
5. Type hints
6. Test coverage

If any issues are found, fix them using the Edit tool.

Return a JSON quality report.`,
      outputFormat: 'JSON with score (number 0-100), issues (array), fixes (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['score', 'issues'],
      properties: {
        score: { type: 'number' },
        issues: { type: 'array', items: { type: 'string' } },
        fixes: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

/**
 * Final verification
 */
export const finalVerificationTask = defineTask('final-verification', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Final verification',
  description: 'Verify all methods are properly implemented and tested',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA Engineer verifying implementation',
      task: `Perform final verification of the collection methods implementation.

Target file: ${args.targetFile}
Test file: ${args.testFile}
Methods: ${JSON.stringify(args.methods.map(m => m.name))}

Verify:
1. All three methods exist in bibs.py
2. All methods have proper signatures
3. All methods have docstrings
4. Test file exists and has tests for all methods
5. Run the smoke import test to ensure package still imports

Run: poetry run python scripts/smoke_import.py

Return verification status.`,
      outputFormat: 'JSON with verified (boolean), checks (object), smokeTestPassed (boolean)'
    },
    outputSchema: {
      type: 'object',
      required: ['verified', 'checks'],
      properties: {
        verified: { type: 'boolean' },
        checks: { type: 'object' },
        smokeTestPassed: { type: 'boolean' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));
