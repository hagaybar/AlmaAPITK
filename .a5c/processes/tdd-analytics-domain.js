/**
 * @process almaapitk/tdd-analytics-domain
 * @description TDD process for creating Analytics domain in almaapitk
 * @skill python-dev-expert
 * @skill alma-api-expert
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * TDD Process for Creating Analytics Domain
 *
 * Methods to implement:
 * 1. get_report_headers(report_path) - GET /almaws/v1/analytics/reports (schema only)
 * 2. fetch_report_rows(report_path, limit, max_rows) - GET with pagination (ResumptionToken)
 *
 * Reference: /home/hagaybar/projects/Fetch_Alma_Analytics_Reports/fetch_reports_from_alma_analytics.py
 *
 * TDD Workflow:
 * - Phase 1: Write tests first (RED)
 * - Phase 2: Implement Analytics class (GREEN)
 * - Phase 3: Export from __init__.py and verify (REFACTOR)
 */
export async function process(inputs, ctx) {
  const {
    domainFile = 'src/almaapitk/domains/analytics.py',
    unitTestFile = 'tests/unit/domains/test_analytics.py',
    integrationTestFile = 'tests/integration/domains/test_analytics.py',
    initFile = 'src/almaapitk/__init__.py',
    referenceFile = '/home/hagaybar/projects/Fetch_Alma_Analytics_Reports/fetch_reports_from_alma_analytics.py',
    methods = [
      {
        name: 'get_report_headers',
        description: 'Get column headers/schema for an Analytics report',
        endpoint: 'GET /almaws/v1/analytics/reports',
        params: ['report_path'],
        returns: 'Dict mapping column names to headings'
      },
      {
        name: 'fetch_report_rows',
        description: 'Fetch rows from Analytics report with pagination',
        endpoint: 'GET /almaws/v1/analytics/reports',
        params: ['report_path', 'limit', 'max_rows'],
        returns: 'Generator yielding row dicts'
      }
    ]
  } = inputs;

  // ============================================================================
  // PHASE 1: WRITE TESTS FIRST (RED)
  // ============================================================================

  // Write unit tests
  const unitTestResult = await ctx.task(writeUnitTestsTask, {
    testFile: unitTestFile,
    domainFile,
    methods
  });

  // Write integration tests
  const integrationTestResult = await ctx.task(writeIntegrationTestsTask, {
    testFile: integrationTestFile,
    domainFile,
    methods
  });

  // Run tests - should fail (no implementation yet)
  const initialTestResult = await ctx.task(runPytestTask, {
    testFiles: [unitTestFile],
    expectFailure: true,
    phase: 'RED'
  });

  // ============================================================================
  // PHASE 2: IMPLEMENT ANALYTICS CLASS (GREEN)
  // ============================================================================

  const implementationResult = await ctx.task(implementAnalyticsTask, {
    domainFile,
    methods,
    referenceFile,
    unitTestFile
  });

  // Run unit tests - should pass now
  const greenTestResult = await ctx.task(runPytestTask, {
    testFiles: [unitTestFile],
    expectFailure: false,
    phase: 'GREEN'
  });

  // ============================================================================
  // PHASE 3: EXPORT AND VERIFY (REFACTOR)
  // ============================================================================

  // Update __init__.py to export Analytics
  const exportResult = await ctx.task(updateExportsTask, {
    initFile,
    className: 'Analytics'
  });

  // Code quality check
  const qualityResult = await ctx.task(codeQualityCheckTask, {
    domainFile,
    unitTestFile,
    integrationTestFile
  });

  // Final verification with smoke test
  const finalResult = await ctx.task(finalVerificationTask, {
    domainFile,
    methods,
    initFile
  });

  return {
    success: true,
    domainFile,
    testsCreated: {
      unit: unitTestFile,
      integration: integrationTestFile
    },
    methodsImplemented: methods.map(m => m.name),
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
 * Write unit tests for Analytics domain
 */
export const writeUnitTestsTask = defineTask('write-unit-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Write unit tests for Analytics domain',
  description: 'Create pytest unit tests with mocked responses',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer specializing in TDD and API testing',
      task: `Create unit tests for the Analytics domain class.

Target test file: ${args.testFile}
Target implementation: ${args.domainFile}

Methods to test:
${JSON.stringify(args.methods, null, 2)}

Instructions:
1. Read existing domain files (bibs.py, users.py) to understand patterns
2. Read existing unit tests to follow testing patterns
3. Create test file with:
   - Imports (pytest, unittest.mock, etc.)
   - MockAlmaAPIClient fixture
   - TestAnalytics class with:
     * test_init() - verify client and logger setup
     * test_get_report_headers_success() - mock XML response, verify parsing
     * test_get_report_headers_empty() - handle empty report
     * test_get_report_headers_invalid_path() - validation error
     * test_fetch_report_rows_single_page() - single page of results
     * test_fetch_report_rows_pagination() - multiple pages with ResumptionToken
     * test_fetch_report_rows_max_rows_limit() - respect max_rows param
     * test_fetch_report_rows_empty() - empty report

4. Mock the client.get() method to return test XML data
5. The XML structure uses:
   - Column schema in {http://www.w3.org/2001/XMLSchema}element with saw:columnHeading
   - Row data in {urn:schemas-microsoft-com:xml-analysis:rowset}Row with Column1, Column2, etc.
   - ResumptionToken for pagination
   - IsFinished flag

6. Write the actual test file using the Write tool

Return a JSON summary of what was created.`,
      outputFormat: 'JSON with testFile (string), testsCreated (array of test names)'
    },
    outputSchema: {
      type: 'object',
      required: ['testFile', 'testsCreated'],
      properties: {
        testFile: { type: 'string' },
        testsCreated: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

/**
 * Write integration tests for Analytics domain
 */
export const writeIntegrationTestsTask = defineTask('write-integration-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Write integration tests for Analytics domain',
  description: 'Create pytest integration tests for real API calls',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer specializing in API integration testing',
      task: `Create integration tests for the Analytics domain class.

Target test file: ${args.testFile}
Target implementation: ${args.domainFile}

Methods to test:
${JSON.stringify(args.methods, null, 2)}

Instructions:
1. Read existing integration tests in tests/integration/ for patterns
2. Create test file with:
   - Imports and fixtures (using AlmaAPIClient with PRODUCTION environment - Analytics requires production)
   - pytest.mark.integration markers
   - TestAnalyticsIntegration class with:
     * test_get_report_headers_real() - fetch real report headers
     * test_fetch_report_rows_real() - fetch real report rows (limited)
     * test_fetch_report_rows_pagination_real() - test pagination with real API
   - Use a known report path for testing (can be parameterized)

3. Add skip markers for when API is unavailable
4. Use small row limits to avoid long tests
5. Write the actual test file using the Write tool

Return a JSON summary of what was created.`,
      outputFormat: 'JSON with testFile (string), testsCreated (array of test names)'
    },
    outputSchema: {
      type: 'object',
      required: ['testFile', 'testsCreated'],
      properties: {
        testFile: { type: 'string' },
        testsCreated: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

/**
 * Run pytest on test files
 */
export const runPytestTask = defineTask('run-pytest', (args, taskCtx) => ({
  kind: 'shell',
  title: `Run tests (${args.phase})`,
  description: `Run pytest on ${args.testFiles.join(', ')}`,

  shell: {
    command: `cd /home/hagaybar/projects/AlmaAPITK && poetry run pytest ${args.testFiles.join(' ')} -v --tb=short 2>&1 || true`,
    timeout: 60000
  },

  io: {
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

/**
 * Implement the Analytics domain class
 */
export const implementAnalyticsTask = defineTask('implement-analytics', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Implement Analytics domain class',
  description: 'Create the Analytics class with all methods',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Senior Python developer implementing Alma API client methods',
      task: `Create the Analytics domain class for almaapitk.

Target file: ${args.domainFile}
Reference implementation: ${args.referenceFile}
Unit test file: ${args.unitTestFile}

Methods to implement:
${JSON.stringify(args.methods, null, 2)}

Instructions:
1. Read the reference implementation to understand the API behavior
2. Read the unit tests to understand expected behavior
3. Read existing domains (bibs.py, users.py) for patterns
4. Create ${args.domainFile} with:

\`\`\`python
"""
Analytics Domain Class for Alma API

Provides methods for fetching data from Alma Analytics reports.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Generator, Optional
from urllib.parse import unquote

from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError


class Analytics:
    """
    Analytics domain class for Alma API operations.

    Provides methods for:
    - Fetching report column headers/schema
    - Fetching report rows with pagination
    """

    def __init__(self, client: AlmaAPIClient):
        """Initialize the Analytics domain."""
        self.client = client
        self.logger = client.logger

    def get_report_headers(self, report_path: str) -> Dict[str, str]:
        """
        Get column headers/schema for an Analytics report.

        Args:
            report_path: Path to the Analytics report (URL encoded or plain)

        Returns:
            Dict mapping column names (Column0, Column1, etc.) to display headings

        Raises:
            AlmaValidationError: If report_path is empty
            AlmaAPIError: If API call fails
        """
        # Implementation here

    def fetch_report_rows(
        self,
        report_path: str,
        limit: int = 1000,
        max_rows: Optional[int] = None
    ) -> Generator[Dict[str, str], None, None]:
        """
        Fetch rows from an Analytics report with pagination.

        Args:
            report_path: Path to the Analytics report
            limit: Number of rows per API request (max 1000)
            max_rows: Maximum total rows to fetch (None for all)

        Yields:
            Dict for each row with column names as keys

        Raises:
            AlmaValidationError: If report_path is empty
            AlmaAPIError: If API call fails
        """
        # Implementation here - generator with ResumptionToken handling
\`\`\`

5. Implementation details:
   - API endpoint: almaws/v1/analytics/reports
   - Request params: path, limit, token (for pagination)
   - Response has "anies" field containing XML string
   - Parse XML for schema (xsd:element with saw:columnHeading)
   - Parse XML for rows (ns0:Row elements)
   - Handle ResumptionToken for pagination
   - Check IsFinished flag
   - Use self.client.get() with params dict

6. Use the Write tool to create the file

Return a JSON summary of what was implemented.`,
      outputFormat: 'JSON with domainFile (string), methodsImplemented (array), linesOfCode (number)'
    },
    outputSchema: {
      type: 'object',
      required: ['domainFile', 'methodsImplemented'],
      properties: {
        domainFile: { type: 'string' },
        methodsImplemented: { type: 'array', items: { type: 'string' } },
        linesOfCode: { type: 'number' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

/**
 * Update __init__.py to export Analytics
 */
export const updateExportsTask = defineTask('update-exports', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update package exports',
  description: 'Add Analytics to __init__.py exports',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer updating package exports',
      task: `Update ${args.initFile} to export the ${args.className} class.

Instructions:
1. Read the current __init__.py
2. Add import for Analytics from domains.analytics
3. Add Analytics to __all__ list
4. Use the Edit tool to make changes

Return confirmation of what was updated.`,
      outputFormat: 'JSON with initFile (string), classExported (string), success (boolean)'
    },
    outputSchema: {
      type: 'object',
      required: ['initFile', 'classExported', 'success'],
      properties: {
        initFile: { type: 'string' },
        classExported: { type: 'string' },
        success: { type: 'boolean' }
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
      task: `Review the Analytics domain implementation for code quality.

Files to review:
- ${args.domainFile}
- ${args.unitTestFile}
- ${args.integrationTestFile}

Check for:
1. Consistent coding style with existing domains
2. Proper error handling (AlmaValidationError, AlmaAPIError)
3. Complete docstrings with Args, Returns, Raises
4. Appropriate logging
5. Type hints on all methods
6. Test coverage for edge cases

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
  description: 'Verify Analytics domain is properly implemented and exported',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'QA Engineer verifying implementation',
      task: `Perform final verification of the Analytics domain implementation.

Domain file: ${args.domainFile}
Init file: ${args.initFile}
Methods: ${JSON.stringify(args.methods.map(m => m.name))}

Verify:
1. Analytics class exists in ${args.domainFile}
2. Both methods have proper signatures and docstrings
3. Analytics is exported from ${args.initFile}
4. Run smoke test: poetry run python scripts/smoke_import.py
5. Verify import works: python -c "from almaapitk import Analytics; print('OK')"

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
