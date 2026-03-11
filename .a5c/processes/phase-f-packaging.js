/**
 * @process phase-f-packaging
 * @description Phase F: Make AlmaAPITK a properly installable Python package named `almaapitk`
 * @inputs { prompt: string }
 * @outputs { success: boolean, commits: array, testResults: object }
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

/**
 * Phase F Packaging Process
 *
 * Makes AlmaAPITK installable as `almaapitk` so downstream projects can depend on it
 * without PYTHONPATH workarounds.
 *
 * @param {Object} inputs - Process inputs
 * @param {string} inputs.prompt - Original user prompt
 * @param {Object} ctx - Process context
 * @returns {Promise<Object>} Process result
 */
export async function process(inputs, ctx) {
  const { prompt } = inputs;

  // ============================================================================
  // PHASE F1: Package AlmaAPITK
  // ============================================================================

  // Step 1: Create feature branch
  const branchResult = await ctx.task(createBranchTask, {
    repoPath: '/home/hagaybar/projects/AlmaAPITK',
    branchName: 'phase-f-packaging'
  });

  // Step 2: Fix pyproject.toml for proper packaging
  const packagingResult = await ctx.task(fixPackagingTask, {
    repoPath: '/home/hagaybar/projects/AlmaAPITK',
    packageName: 'almaapitk'
  });

  // Step 3: Validate local install works
  const installValidation = await ctx.task(validateInstallTask, {
    repoPath: '/home/hagaybar/projects/AlmaAPITK'
  });

  // Step 4: Add import tests
  const testResult = await ctx.task(addImportTestsTask, {
    repoPath: '/home/hagaybar/projects/AlmaAPITK'
  });

  // Step 5: Run tests and build
  const buildResult = await ctx.task(buildAndTestTask, {
    repoPath: '/home/hagaybar/projects/AlmaAPITK'
  });

  // ============================================================================
  // PHASE F2: Update Downstream Consumer
  // ============================================================================

  // Step 6: Update standalone repo dependency
  const consumerResult = await ctx.task(updateConsumerTask, {
    consumerPath: '/home/hagaybar/projects/Alma-update-expired-users-emails',
    almaApitkPath: '/home/hagaybar/projects/AlmaAPITK'
  });

  // Step 7: End-to-end validation (dry-run test)
  const e2eResult = await ctx.task(e2eValidationTask, {
    consumerPath: '/home/hagaybar/projects/Alma-update-expired-users-emails'
  });

  // ============================================================================
  // PHASE F3: Documentation and Commit
  // ============================================================================

  // Step 8: Update documentation
  const docsResult = await ctx.task(updateDocsTask, {
    almaApitkPath: '/home/hagaybar/projects/AlmaAPITK',
    consumerPath: '/home/hagaybar/projects/Alma-update-expired-users-emails'
  });

  // Step 9: Commit and push
  const commitResult = await ctx.task(commitAndPushTask, {
    almaApitkPath: '/home/hagaybar/projects/AlmaAPITK',
    consumerPath: '/home/hagaybar/projects/Alma-update-expired-users-emails'
  });

  // Final breakpoint for review before completion
  await ctx.breakpoint({
    question: 'Phase F complete. Review commits and test results before finalizing?',
    title: 'Phase F Review',
    context: {
      runId: ctx.runId,
      commits: commitResult.commits || [],
      testsPassed: buildResult.success && e2eResult.success
    }
  });

  return {
    success: buildResult.success && e2eResult.success && commitResult.success,
    commits: commitResult.commits || [],
    testResults: {
      build: buildResult,
      e2e: e2eResult,
      install: installValidation
    },
    summary: {
      almaApitkBranch: branchResult.branch,
      packagesFixed: packagingResult.success,
      testsAdded: testResult.success,
      buildPassed: buildResult.success,
      e2ePassed: e2eResult.success,
      documentationUpdated: docsResult.success
    },
    rollback: 'git switch main && git branch -D phase-f-packaging'
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const createBranchTask = defineTask('create-branch', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create feature branch for Phase F',
  description: `Create phase-f-packaging branch in ${args.repoPath}`,

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'git operations specialist',
      task: `Create a new branch for Phase F packaging work in AlmaAPITK`,
      context: {
        repoPath: args.repoPath,
        branchName: args.branchName
      },
      instructions: [
        `Navigate to ${args.repoPath}`,
        'Check current git status and branch',
        `If branch ${args.branchName} already exists, switch to it`,
        `Otherwise create and switch to ${args.branchName}`,
        'Return the current branch name and status'
      ],
      outputFormat: 'JSON with branch, status, isNew fields'
    },
    outputSchema: {
      type: 'object',
      required: ['branch', 'status'],
      properties: {
        branch: { type: 'string' },
        status: { type: 'string' },
        isNew: { type: 'boolean' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['git', 'setup']
}));

export const fixPackagingTask = defineTask('fix-packaging', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Fix pyproject.toml for proper packaging',
  description: 'Update pyproject.toml to correctly declare almaapitk package',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python packaging specialist',
      task: 'Fix pyproject.toml to properly package AlmaAPITK as almaapitk',
      context: {
        repoPath: args.repoPath,
        packageName: args.packageName,
        existingPackage: 'src/almaapitk/ already exists with __init__.py and _internal/'
      },
      instructions: [
        `Read current ${args.repoPath}/pyproject.toml`,
        'The current name is "src" which is wrong - it should be "almaapitk"',
        'Update the [project] section: name = "almaapitk"',
        'Ensure build-system uses poetry-core',
        'Add [tool.poetry] section if needed with: packages = [{ include = "almaapitk", from = "src" }]',
        'Preserve all existing dependencies',
        'Do NOT change runtime logic - only packaging metadata',
        'Verify the src/almaapitk/__init__.py exists and exports the public API'
      ],
      outputFormat: 'JSON with success, changes array'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        changes: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['packaging', 'pyproject']
}));

export const validateInstallTask = defineTask('validate-install', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Validate local install works',
  description: 'Run poetry install and verify imports work without PYTHONPATH',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python packaging validator',
      task: 'Validate that almaapitk can be installed and imported correctly',
      context: {
        repoPath: args.repoPath
      },
      instructions: [
        `Navigate to ${args.repoPath}`,
        'Run: poetry install',
        'Run: poetry run python -c "from almaapitk import AlmaAPIClient, Admin, Users; print(\'OK\')"',
        'If the import fails, diagnose the issue and report it',
        'Verify that __version__ is accessible',
        'Return success status and any output/errors'
      ],
      outputFormat: 'JSON with success, output, errors fields'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        output: { type: 'string' },
        errors: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['validation', 'install']
}));

export const addImportTestsTask = defineTask('add-import-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Add public API import tests',
  description: 'Create tests/test_public_api_imports.py to verify all exports',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python test developer',
      task: 'Add offline tests verifying public API imports for almaapitk',
      context: {
        repoPath: args.repoPath,
        publicApiSymbols: [
          '__version__',
          'AlmaAPIClient',
          'AlmaResponse',
          'AlmaAPIError',
          'AlmaValidationError',
          'Admin',
          'Users',
          'BibliographicRecords',
          'Acquisitions',
          'ResourceSharing'
        ]
      },
      instructions: [
        `Create ${args.repoPath}/tests/test_public_api_imports.py`,
        'Test that "import almaapitk" works',
        'Test that each symbol in publicApiSymbols is importable from almaapitk',
        'Test that __version__ is a string starting with a digit',
        'Tests must be OFFLINE - no network calls',
        'Use pytest style with descriptive test function names',
        'Ensure tests directory has __init__.py if needed'
      ],
      outputFormat: 'JSON with success, testFile, testCount fields'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        testFile: { type: 'string' },
        testCount: { type: 'number' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['testing', 'import']
}));

export const buildAndTestTask = defineTask('build-and-test', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Build package and run tests',
  description: 'Run poetry build and pytest to verify packaging',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python build and test runner',
      task: 'Build the almaapitk package and run all tests',
      context: {
        repoPath: args.repoPath
      },
      instructions: [
        `Navigate to ${args.repoPath}`,
        'Run: poetry build',
        'Verify wheel and sdist are created in dist/',
        'Run: poetry run pytest tests/test_public_api_imports.py -v',
        'Report test results',
        'If tests fail, report the failure details'
      ],
      outputFormat: 'JSON with success, buildOutput, testOutput, artifacts fields'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        buildOutput: { type: 'string' },
        testOutput: { type: 'string' },
        artifacts: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['build', 'test']
}));

export const updateConsumerTask = defineTask('update-consumer', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update standalone repo dependency',
  description: 'Add almaapitk as a local path dependency in the consumer repo',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python dependency manager',
      task: 'Update Alma-update-expired-users-emails to depend on almaapitk',
      context: {
        consumerPath: args.consumerPath,
        almaApitkPath: args.almaApitkPath
      },
      instructions: [
        `Read ${args.consumerPath}/pyproject.toml`,
        'Add almaapitk as a path dependency: almaapitk = { path = "../AlmaAPITK", develop = true }',
        'Remove redundant dependencies that almaapitk provides (requests, pandas, openpyxl, boto3, pypdf2)',
        'Run: poetry lock',
        'Run: poetry install',
        'Verify: poetry run python -c "from almaapitk import AlmaAPIClient; print(\'OK\')"',
        'Remove any PYTHONPATH workarounds from the repo'
      ],
      outputFormat: 'JSON with success, changes, lockUpdated fields'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        changes: { type: 'array', items: { type: 'string' } },
        lockUpdated: { type: 'boolean' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['dependency', 'consumer']
}));

export const e2eValidationTask = defineTask('e2e-validation', (args, taskCtx) => ({
  kind: 'agent',
  title: 'End-to-end dry-run validation',
  description: 'Run the update_expired_user_emails.py script in dry-run mode without PYTHONPATH',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Integration tester',
      task: 'Validate the standalone repo works without PYTHONPATH by running a dry-run',
      context: {
        consumerPath: args.consumerPath
      },
      instructions: [
        `Navigate to ${args.consumerPath}`,
        'Ensure PYTHONPATH is NOT set (or unset it)',
        'Run: poetry run python update_expired_user_emails.py --config config/email_update_config.json --dry-run',
        'The command should succeed without import errors',
        'Capture the output and verify it reaches summary/completion',
        'Report success/failure and any errors'
      ],
      outputFormat: 'JSON with success, output, importErrors fields'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        output: { type: 'string' },
        importErrors: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['e2e', 'validation']
}));

export const updateDocsTask = defineTask('update-docs', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update documentation',
  description: 'Update READMEs to remove PYTHONPATH instructions',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Documentation updater',
      task: 'Update README files to reflect proper package installation',
      context: {
        almaApitkPath: args.almaApitkPath,
        consumerPath: args.consumerPath
      },
      instructions: [
        `Read ${args.almaApitkPath}/README.md`,
        'Add/update installation section: poetry add almaapitk OR pip install -e .',
        'Add usage example: from almaapitk import AlmaAPIClient, Admin, Users',
        `Read ${args.consumerPath}/README.md`,
        'Remove any PYTHONPATH instructions',
        'Update to show: poetry install (which pulls almaapitk as dependency)',
        'Keep changes minimal - only update what is necessary'
      ],
      outputFormat: 'JSON with success, filesUpdated fields'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        filesUpdated: { type: 'array', items: { type: 'string' } }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['documentation']
}));

export const commitAndPushTask = defineTask('commit-and-push', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Commit and push changes',
  description: 'Commit all changes to both repos and push to GitHub',

  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git operations specialist',
      task: 'Commit and push changes for Phase F packaging',
      context: {
        almaApitkPath: args.almaApitkPath,
        consumerPath: args.consumerPath
      },
      instructions: [
        `In ${args.almaApitkPath}:`,
        '  - git add pyproject.toml tests/',
        '  - git commit with message: "Phase F: Make almaapitk properly installable Python package"',
        '  - Include Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>',
        '  - git push -u origin phase-f-packaging',
        `In ${args.consumerPath}:`,
        '  - git add pyproject.toml poetry.lock README.md',
        '  - git commit with message: "Update to depend on almaapitk package (Phase F)"',
        '  - Include Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>',
        '  - git push',
        'Return the commit hashes for both repos'
      ],
      outputFormat: 'JSON with success, commits array, pushStatus fields'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        commits: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              repo: { type: 'string' },
              hash: { type: 'string' },
              message: { type: 'string' }
            }
          }
        },
        pushStatus: { type: 'string' }
      }
    }
  },

  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  },

  labels: ['git', 'commit', 'push']
}));
