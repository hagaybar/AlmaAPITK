/**
 * @process almaapitk-documentation
 * @description Comprehensive documentation generation for AlmaAPITK Python library
 * @inputs { outputDir: string, includeAlmaApiReference: boolean }
 * @outputs { success: boolean, documentationPath: string, sections: array, qualityScore: number, artifacts: array }
 *
 * @skill python-dev-expert
 * @agent technical-writer
 * @agent api-docs-specialist
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

export async function process(inputs, ctx) {
  const {
    outputDir = 'docs',
    includeAlmaApiReference = true,
    targetAudience = 'library-developers'
  } = inputs;

  const startTime = ctx.now();
  const artifacts = [];

  ctx.log('info', 'Starting AlmaAPITK Documentation Generation');
  ctx.log('info', `Output directory: ${outputDir}`);

  // ============================================================================
  // PHASE 1: CODEBASE ANALYSIS
  // ============================================================================

  ctx.log('info', 'Phase 1: Analyzing AlmaAPITK codebase');

  const codebaseAnalysis = await ctx.task(codebaseAnalysisTask, {
    outputDir
  });

  if (codebaseAnalysis.artifacts && Array.isArray(codebaseAnalysis.artifacts)) {
    artifacts.push(...codebaseAnalysis.artifacts);
  }

  if (!codebaseAnalysis.success) {
    return {
      success: false,
      error: 'Failed to analyze codebase',
      details: codebaseAnalysis
    };
  }

  // ============================================================================
  // PHASE 2: GETTING STARTED GUIDE
  // ============================================================================

  ctx.log('info', 'Phase 2: Creating Getting Started guide');

  const gettingStarted = await ctx.task(gettingStartedTask, {
    codebaseInfo: codebaseAnalysis,
    outputDir
  });

  if (gettingStarted.artifacts && Array.isArray(gettingStarted.artifacts)) {
    artifacts.push(...gettingStarted.artifacts);
  }

  // ============================================================================
  // PHASE 3: API REFERENCE DOCUMENTATION
  // ============================================================================

  ctx.log('info', 'Phase 3: Creating API Reference documentation');

  const apiReference = await ctx.task(apiReferenceTask, {
    codebaseInfo: codebaseAnalysis,
    outputDir
  });

  if (apiReference.artifacts && Array.isArray(apiReference.artifacts)) {
    artifacts.push(...apiReference.artifacts);
  }

  // ============================================================================
  // PHASE 4: DOMAIN GUIDES (PARALLEL)
  // ============================================================================

  ctx.log('info', 'Phase 4: Creating Domain guides in parallel');

  const domainGuideTasks = [
    () => ctx.task(domainGuideTask, {
      domainName: 'Acquisitions',
      domainFile: 'src/almaapitk/domains/acquisition.py',
      outputDir,
      includeAlmaApiReference
    }),
    () => ctx.task(domainGuideTask, {
      domainName: 'Users',
      domainFile: 'src/almaapitk/domains/users.py',
      outputDir,
      includeAlmaApiReference
    }),
    () => ctx.task(domainGuideTask, {
      domainName: 'BibliographicRecords',
      domainFile: 'src/almaapitk/domains/bibs.py',
      outputDir,
      includeAlmaApiReference
    }),
    () => ctx.task(domainGuideTask, {
      domainName: 'Admin',
      domainFile: 'src/almaapitk/domains/admin.py',
      outputDir,
      includeAlmaApiReference
    }),
    () => ctx.task(domainGuideTask, {
      domainName: 'ResourceSharing',
      domainFile: 'src/almaapitk/domains/resource_sharing.py',
      outputDir,
      includeAlmaApiReference
    })
  ];

  const domainGuides = await ctx.parallel.all(domainGuideTasks);

  domainGuides.forEach(g => {
    if (g.artifacts && Array.isArray(g.artifacts)) {
      artifacts.push(...g.artifacts);
    }
  });

  // Breakpoint: Review domain guides
  await ctx.breakpoint({
    question: `Generated ${domainGuides.length} domain guides. Review before continuing?`,
    title: 'Domain Guides Review',
    context: {
      runId: ctx.runId,
      domains: domainGuides.map(g => g.domainName),
      files: domainGuides.flatMap(g => g.artifacts.map(a => ({
        path: a.path,
        format: 'markdown'
      })))
    }
  });

  // ============================================================================
  // PHASE 5: CODE EXAMPLES AND WORKFLOWS
  // ============================================================================

  ctx.log('info', 'Phase 5: Creating code examples and common workflows');

  const codeExamples = await ctx.task(codeExamplesTask, {
    codebaseInfo: codebaseAnalysis,
    domainGuides,
    outputDir
  });

  if (codeExamples.artifacts && Array.isArray(codeExamples.artifacts)) {
    artifacts.push(...codeExamples.artifacts);
  }

  // ============================================================================
  // PHASE 6: ERROR HANDLING GUIDE
  // ============================================================================

  ctx.log('info', 'Phase 6: Creating error handling guide');

  const errorHandling = await ctx.task(errorHandlingGuideTask, {
    codebaseInfo: codebaseAnalysis,
    includeAlmaApiReference,
    outputDir
  });

  if (errorHandling.artifacts && Array.isArray(errorHandling.artifacts)) {
    artifacts.push(...errorHandling.artifacts);
  }

  // ============================================================================
  // PHASE 7: LOGGING CONFIGURATION GUIDE
  // ============================================================================

  ctx.log('info', 'Phase 7: Creating logging configuration guide');

  const loggingGuide = await ctx.task(loggingGuideTask, {
    codebaseInfo: codebaseAnalysis,
    outputDir
  });

  if (loggingGuide.artifacts && Array.isArray(loggingGuide.artifacts)) {
    artifacts.push(...loggingGuide.artifacts);
  }

  // ============================================================================
  // PHASE 8: QUALITY VALIDATION
  // ============================================================================

  ctx.log('info', 'Phase 8: Validating documentation quality');

  const qualityValidation = await ctx.task(qualityValidationTask, {
    artifacts,
    outputDir
  });

  if (qualityValidation.artifacts && Array.isArray(qualityValidation.artifacts)) {
    artifacts.push(...qualityValidation.artifacts);
  }

  const qualityMet = qualityValidation.overallScore >= 80;

  // Breakpoint: Review quality validation
  await ctx.breakpoint({
    question: `Documentation quality score: ${qualityValidation.overallScore}/100. ${qualityMet ? 'Quality meets standards!' : 'Quality may need improvement.'} Review and finalize?`,
    title: 'Quality Validation Review',
    context: {
      runId: ctx.runId,
      qualityScore: qualityValidation.overallScore,
      componentScores: qualityValidation.componentScores,
      recommendations: qualityValidation.recommendations
    }
  });

  // ============================================================================
  // PHASE 9: DOCUMENTATION INDEX AND NAVIGATION
  // ============================================================================

  ctx.log('info', 'Phase 9: Creating documentation index and navigation');

  const docIndex = await ctx.task(documentationIndexTask, {
    artifacts,
    outputDir
  });

  if (docIndex.artifacts && Array.isArray(docIndex.artifacts)) {
    artifacts.push(...docIndex.artifacts);
  }

  const endTime = ctx.now();
  const duration = endTime - startTime;

  return {
    success: true,
    documentationPath: outputDir,
    sections: [
      'Getting Started',
      'API Reference',
      'Domain Guides (5)',
      'Code Examples',
      'Error Handling',
      'Logging Configuration'
    ],
    qualityScore: qualityValidation.overallScore,
    statistics: {
      totalFiles: artifacts.length,
      domainGuides: domainGuides.length,
      codeExamples: codeExamples.exampleCount
    },
    artifacts,
    duration,
    metadata: {
      processId: 'almaapitk-documentation',
      timestamp: startTime,
      outputDir
    }
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

// Task 1: Codebase Analysis
export const codebaseAnalysisTask = defineTask('codebase-analysis', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Analyze AlmaAPITK codebase structure',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python library documentation analyst',
      task: 'Analyze the AlmaAPITK codebase to understand its structure, public API, and documentation needs',
      context: {
        ...args,
        repoPath: '/home/hagaybar/projects/AlmaAPITK',
        packagePath: 'src/almaapitk'
      },
      instructions: [
        'Read and analyze the following key files:',
        '  - src/almaapitk/__init__.py (public API exports)',
        '  - src/almaapitk/client/AlmaAPIClient.py (main client class)',
        '  - src/almaapitk/domains/*.py (all domain classes)',
        '  - README.md (existing package description)',
        '  - pyproject.toml (package metadata)',
        '  - CLAUDE.md (project guidelines)',
        'Extract:',
        '  - All public API classes and their methods',
        '  - Constructor signatures and parameters',
        '  - Environment variables required',
        '  - Domain class responsibilities',
        '  - Existing documentation in docs/',
        'Create structured analysis report with:',
        '  - Package structure overview',
        '  - Public API symbols list',
        '  - Domain classes and their key methods',
        '  - Configuration requirements',
        '  - Dependencies',
        'Save analysis to docs/analysis/ directory'
      ],
      outputFormat: 'JSON with success (boolean), packageInfo (object), publicApi (array), domains (array), configuration (object), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'packageInfo', 'publicApi', 'domains', 'artifacts'],
      properties: {
        success: { type: 'boolean' },
        packageInfo: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            version: { type: 'string' },
            description: { type: 'string' },
            pythonVersion: { type: 'string' }
          }
        },
        publicApi: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              type: { type: 'string' },
              description: { type: 'string' }
            }
          }
        },
        domains: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              file: { type: 'string' },
              methods: { type: 'array' },
              description: { type: 'string' }
            }
          }
        },
        configuration: {
          type: 'object',
          properties: {
            envVars: { type: 'array' },
            dependencies: { type: 'array' }
          }
        },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'analysis']
}));

// Task 2: Getting Started Guide
export const gettingStartedTask = defineTask('getting-started-guide', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create Getting Started guide',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Technical documentation writer specializing in Python libraries',
      task: 'Create comprehensive Getting Started guide for AlmaAPITK',
      context: args,
      instructions: [
        'Create docs/getting-started.md with:',
        '',
        '## Prerequisites',
        '- Python version requirements (3.12+)',
        '- Alma API keys (SANDBOX and PRODUCTION)',
        '- How to obtain API keys from Ex Libris Developer Network',
        '',
        '## Installation',
        '- pip install (from PyPI when published)',
        '- poetry add',
        '- Install from GitHub',
        '',
        '## Configuration',
        '- Setting environment variables:',
        '  - ALMA_SB_API_KEY for Sandbox',
        '  - ALMA_PROD_API_KEY for Production',
        '- Alternative configuration methods',
        '',
        '## Quick Start (5-minute tutorial)',
        '- Initialize AlmaAPIClient',
        '- Make first API call (list libraries)',
        '- Handle the response',
        '- Complete working example',
        '',
        '## Next Steps',
        '- Links to domain guides',
        '- Links to API reference',
        '',
        'Use actual code from the package for examples',
        'Include expected output for examples',
        'Save to docs/getting-started.md'
      ],
      outputFormat: 'JSON with success (boolean), filePath (string), sections (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filePath', 'artifacts'],
      properties: {
        success: { type: 'boolean' },
        filePath: { type: 'string' },
        sections: { type: 'array', items: { type: 'string' } },
        estimatedReadTime: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'getting-started']
}));

// Task 3: API Reference
export const apiReferenceTask = defineTask('api-reference', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create API Reference documentation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python API documentation specialist',
      task: 'Create comprehensive API Reference documentation for AlmaAPITK public classes',
      context: args,
      instructions: [
        'Create docs/api-reference.md with detailed documentation for:',
        '',
        '## AlmaAPIClient',
        '- Constructor parameters (environment)',
        '- Methods: get(), post(), put(), delete()',
        '- Environment handling (SANDBOX vs PRODUCTION)',
        '- Authentication details',
        '',
        '## AlmaResponse',
        '- Properties: .data, .success, .status_code',
        '- Methods: .json(), .text()',
        '- Usage examples',
        '',
        '## Exceptions',
        '- AlmaAPIError: attributes, when raised',
        '- AlmaValidationError: attributes, when raised',
        '',
        '## Domain Classes (Overview)',
        '- Brief description of each domain class',
        '- Link to detailed domain guides',
        '',
        '## Utilities',
        '- TSVGenerator class',
        '- CitationMetadataError',
        '',
        'Read actual source code for accurate documentation',
        'Include type hints and parameter descriptions',
        'Show code examples for each class/method',
        'Save to docs/api-reference.md'
      ],
      outputFormat: 'JSON with success (boolean), filePath (string), classesDocumented (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filePath', 'classesDocumented', 'artifacts'],
      properties: {
        success: { type: 'boolean' },
        filePath: { type: 'string' },
        classesDocumented: { type: 'array', items: { type: 'string' } },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'api-reference']
}));

// Task 4: Domain Guide (template for each domain)
export const domainGuideTask = defineTask('domain-guide', (args, taskCtx) => ({
  kind: 'agent',
  title: `Create ${args.domainName} domain guide`,
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python library documentation specialist with Alma ILS API expertise',
      task: `Create comprehensive guide for the ${args.domainName} domain class`,
      context: {
        ...args,
        almaApiSkillPath: '/home/hagaybar/projects/AlmaAPITK/.claude/skills/alma-api-expert',
        almaDocsUrl: 'https://developers.exlibrisgroup.com/alma/apis/'
      },
      instructions: [
        `Read the source file: ${args.domainFile}`,
        'Also read the alma-api-expert skill for Alma API knowledge',
        '',
        `Create docs/domains/${args.domainName.toLowerCase()}.md with:`,
        '',
        '## Overview',
        '- What this domain handles',
        '- When to use it',
        '- Key concepts',
        '',
        '## Initialization',
        '- How to create an instance',
        '- Required AlmaAPIClient dependency',
        '',
        '## Methods Reference',
        'For EACH public method:',
        '- Method signature with type hints',
        '- Description of what it does',
        '- Parameters explained',
        '- Return value explained',
        '- Code example showing usage',
        '- Common errors and how to handle them',
        '',
        '## Common Workflows',
        '- End-to-end workflow examples',
        '- Best practices',
        '- Tips and gotchas',
        '',
        '## Alma API Reference',
        'If includeAlmaApiReference is true:',
        '- Link to relevant Alma API endpoints',
        '- Note any API quirks or gotchas from alma-api-expert skill',
        '',
        'Read actual source code for accuracy',
        'Use real Alma API terminology',
        `Save to docs/domains/${args.domainName.toLowerCase()}.md`
      ],
      outputFormat: 'JSON with success (boolean), domainName (string), filePath (string), methodsDocumented (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'domainName', 'filePath', 'methodsDocumented', 'artifacts'],
      properties: {
        success: { type: 'boolean' },
        domainName: { type: 'string' },
        filePath: { type: 'string' },
        methodsDocumented: { type: 'array', items: { type: 'string' } },
        workflowsIncluded: { type: 'number' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'domain-guide', args.domainName]
}));

// Task 5: Code Examples
export const codeExamplesTask = defineTask('code-examples', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create code examples and workflow documentation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python developer and technical writer',
      task: 'Create comprehensive code examples document showing common workflows',
      context: args,
      instructions: [
        'Create docs/examples.md with runnable code examples:',
        '',
        '## Basic Operations',
        '- Initialize client and test connection',
        '- Make simple GET request',
        '- Handle responses and errors',
        '',
        '## Acquisitions Workflows',
        '- Get POL information',
        '- Create and pay invoice',
        '- Receive items',
        '',
        '## User Operations',
        '- Get user by ID',
        '- Update user email',
        '- Search users',
        '',
        '## Bibliographic Records',
        '- Get bib record',
        '- Get holdings and items',
        '- Scan-in operations',
        '',
        '## Resource Sharing',
        '- Create lending request',
        '- Get partner information',
        '',
        '## Admin Operations',
        '- Work with sets (BIB_MMS, USER)',
        '',
        'Each example should:',
        '- Be complete and runnable',
        '- Include proper imports',
        '- Show error handling',
        '- Include expected output/results',
        '',
        'Save to docs/examples.md'
      ],
      outputFormat: 'JSON with success (boolean), filePath (string), exampleCount (number), categories (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filePath', 'exampleCount', 'artifacts'],
      properties: {
        success: { type: 'boolean' },
        filePath: { type: 'string' },
        exampleCount: { type: 'number' },
        categories: { type: 'array', items: { type: 'string' } },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'code-examples']
}));

// Task 6: Error Handling Guide
export const errorHandlingGuideTask = defineTask('error-handling-guide', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create error handling guide',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python API library documentation specialist',
      task: 'Create comprehensive error handling guide for AlmaAPITK',
      context: {
        ...args,
        almaApiSkillPath: '/home/hagaybar/projects/AlmaAPITK/.claude/skills/alma-api-expert/references/error_codes_and_solutions.md'
      },
      instructions: [
        'Read AlmaAPIClient.py to understand exception classes',
        'Read alma-api-expert skill error_codes_and_solutions.md for Alma errors',
        '',
        'Create docs/error-handling.md with:',
        '',
        '## Exception Hierarchy',
        '- AlmaAPIError (base exception)',
        '- AlmaValidationError',
        '- Properties and attributes of each',
        '',
        '## HTTP Status Codes',
        '- Common HTTP errors (400, 401, 403, 404, 429, 500)',
        '- What causes each',
        '- How to handle each',
        '',
        '## Alma-Specific Error Codes',
        'Include from alma-api-expert skill:',
        '- Error 402459 (Invoice not approved)',
        '- Error 40166411 (Invalid parameter)',
        '- Error 401875 (Department not found)',
        '- Error 401871 (PO Line not found)',
        '- Other common errors',
        '',
        '## Error Handling Patterns',
        '- Basic try/except pattern',
        '- Handling specific error types',
        '- Retry logic for rate limits',
        '- Logging errors properly',
        '',
        '## Debugging Tips',
        '- Using response data for debugging',
        '- Common mistakes and solutions',
        '- When to check SANDBOX vs PRODUCTION',
        '',
        'Include code examples for each pattern',
        'Save to docs/error-handling.md'
      ],
      outputFormat: 'JSON with success (boolean), filePath (string), errorCodesDocumented (number), patterns (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filePath', 'errorCodesDocumented', 'artifacts'],
      properties: {
        success: { type: 'boolean' },
        filePath: { type: 'string' },
        errorCodesDocumented: { type: 'number' },
        patterns: { type: 'array', items: { type: 'string' } },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'error-handling']
}));

// Task 7: Logging Configuration Guide
export const loggingGuideTask = defineTask('logging-guide', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create logging configuration guide',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python logging and documentation specialist',
      task: 'Create comprehensive logging configuration guide for AlmaAPITK',
      context: args,
      instructions: [
        'Read src/almaapitk/alma_logging/ directory structure',
        'Read CLAUDE.md logging section for requirements',
        '',
        'Create docs/logging.md with:',
        '',
        '## Logging Overview',
        '- What gets logged',
        '- Automatic API key redaction',
        '- Log file locations',
        '',
        '## Using the Logger',
        '- Import and initialize: get_logger()',
        '- In domain classes',
        '- In scripts',
        '',
        '## Log Levels',
        '- DEBUG, INFO, WARNING, ERROR, CRITICAL',
        '- When to use each',
        '- Examples',
        '',
        '## What to Log',
        '- Method entry with key parameters',
        '- Successful operations',
        '- API errors with context',
        '- Validation failures',
        '',
        '## Log File Structure',
        '- Directory layout',
        '- Log rotation',
        '- Domain-specific logs',
        '',
        '## Configuration',
        '- Default configuration',
        '- Custom configuration',
        '- Example config file',
        '',
        '## Security Notes',
        '- What gets redacted automatically',
        '- Never commit logs to git',
        '- Log review best practices',
        '',
        'Include code examples',
        'Save to docs/logging.md'
      ],
      outputFormat: 'JSON with success (boolean), filePath (string), sectionsCreated (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filePath', 'sectionsCreated', 'artifacts'],
      properties: {
        success: { type: 'boolean' },
        filePath: { type: 'string' },
        sectionsCreated: { type: 'array', items: { type: 'string' } },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'logging']
}));

// Task 8: Quality Validation
export const qualityValidationTask = defineTask('quality-validation', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Validate documentation quality',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Documentation quality assurance specialist',
      task: 'Validate documentation quality, completeness, and consistency',
      context: args,
      instructions: [
        'Review all generated documentation files',
        '',
        'Evaluate Completeness (30%):',
        '- All public API symbols documented',
        '- All domain classes covered',
        '- Getting started guide complete',
        '- Error handling covered',
        '- Logging covered',
        '',
        'Evaluate Code Examples (25%):',
        '- Examples are complete and runnable',
        '- Proper imports included',
        '- Error handling shown',
        '- Expected output documented',
        '',
        'Evaluate Clarity (25%):',
        '- Clear language appropriate for developers',
        '- Good structure and formatting',
        '- Consistent terminology',
        '',
        'Evaluate Technical Accuracy (20%):',
        '- Parameter names match code',
        '- Return types accurate',
        '- Method signatures correct',
        '',
        'Generate quality report with:',
        '- Overall score (0-100)',
        '- Component scores',
        '- Gaps identified',
        '- Recommendations for improvement',
        '',
        'Save report to docs/quality-report.md'
      ],
      outputFormat: 'JSON with overallScore (number 0-100), componentScores (object), gaps (array), recommendations (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['overallScore', 'componentScores', 'recommendations', 'artifacts'],
      properties: {
        overallScore: { type: 'number', minimum: 0, maximum: 100 },
        componentScores: {
          type: 'object',
          properties: {
            completeness: { type: 'number' },
            codeExamples: { type: 'number' },
            clarity: { type: 'number' },
            accuracy: { type: 'number' }
          }
        },
        gaps: { type: 'array', items: { type: 'string' } },
        recommendations: { type: 'array', items: { type: 'string' } },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'quality-validation']
}));

// Task 9: Documentation Index
export const documentationIndexTask = defineTask('documentation-index', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create documentation index and navigation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Documentation platform specialist',
      task: 'Create documentation index page with navigation',
      context: args,
      instructions: [
        'Create docs/index.md as the documentation home page:',
        '',
        '## AlmaAPITK Documentation',
        '- Brief description of the package',
        '- Version and Python requirements',
        '',
        '## Quick Links',
        '- [Getting Started](getting-started.md)',
        '- [API Reference](api-reference.md)',
        '',
        '## Domain Guides',
        '- [Acquisitions](domains/acquisitions.md)',
        '- [Users](domains/users.md)',
        '- [BibliographicRecords](domains/bibliographicrecords.md)',
        '- [Admin](domains/admin.md)',
        '- [ResourceSharing](domains/resourcesharing.md)',
        '',
        '## Additional Resources',
        '- [Code Examples](examples.md)',
        '- [Error Handling](error-handling.md)',
        '- [Logging Configuration](logging.md)',
        '',
        '## External Links',
        '- GitHub Repository',
        '- PyPI Package (when published)',
        '- Alma API Documentation',
        '',
        'Save to docs/index.md',
        'Also verify all internal links work'
      ],
      outputFormat: 'JSON with success (boolean), indexPath (string), sections (array), brokenLinks (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'indexPath', 'sections', 'artifacts'],
      properties: {
        success: { type: 'boolean' },
        indexPath: { type: 'string' },
        sections: { type: 'array', items: { type: 'string' } },
        brokenLinks: { type: 'array', items: { type: 'string' } },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  },
  labels: ['agent', 'documentation', 'index']
}));
