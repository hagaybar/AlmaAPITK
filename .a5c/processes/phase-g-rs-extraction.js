/**
 * @process phase-g-rs-extraction
 * @description Phase G: Extract ResourceSharing project to standalone GitHub repository
 * @inputs { sourceDir: string, targetDir: string, remoteUrl: string }
 * @outputs { success: boolean, commitHash: string, repoUrl: string }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

export async function process(inputs, ctx) {
  const { sourceDir, targetDir, remoteUrl } = inputs;

  const startTime = ctx.now();
  const artifacts = [];

  ctx.log('info', 'Phase G: Extract ResourceSharing project to standalone repository');

  // ============================================================================
  // TASK 1: Initialize repository with .gitignore
  // ============================================================================

  ctx.log('info', 'Task 1: Creating and initializing new repository');

  const initRepo = await ctx.task(initRepoTask, {
    targetDir,
    remoteUrl
  });

  if (!initRepo.success) {
    return {
      success: false,
      error: 'Failed to initialize repository',
      details: initRepo
    };
  }

  artifacts.push(...(initRepo.artifacts || []));

  // ============================================================================
  // TASK 2: Copy code and create structure
  // ============================================================================

  ctx.log('info', 'Task 2: Copying code and creating project structure');

  const copyCode = await ctx.task(copyCodeTask, {
    sourceDir,
    targetDir
  });

  if (!copyCode.success) {
    return {
      success: false,
      error: 'Failed to copy code',
      details: copyCode
    };
  }

  artifacts.push(...(copyCode.artifacts || []));

  // ============================================================================
  // TASK 3: Create Poetry configuration
  // ============================================================================

  ctx.log('info', 'Task 3: Creating Poetry pyproject.toml');

  const createPoetry = await ctx.task(createPoetryTask, {
    targetDir
  });

  if (!createPoetry.success) {
    return {
      success: false,
      error: 'Failed to create Poetry configuration',
      details: createPoetry
    };
  }

  artifacts.push(...(createPoetry.artifacts || []));

  // ============================================================================
  // TASK 4: Create smoke tests and unit tests
  // ============================================================================

  ctx.log('info', 'Task 4: Creating smoke tests and unit tests');

  const createTests = await ctx.task(createTestsTask, {
    targetDir
  });

  if (!createTests.success) {
    return {
      success: false,
      error: 'Failed to create tests',
      details: createTests
    };
  }

  artifacts.push(...(createTests.artifacts || []));

  // ============================================================================
  // TASK 5: Run local validation
  // ============================================================================

  ctx.log('info', 'Task 5: Running local validation');

  const validate = await ctx.task(validateLocalTask, {
    targetDir
  });

  if (!validate.success) {
    return {
      success: false,
      error: 'Local validation failed',
      details: validate
    };
  }

  artifacts.push(...(validate.artifacts || []));

  // ============================================================================
  // TASK 6: Update README
  // ============================================================================

  ctx.log('info', 'Task 6: Updating README.md for standalone repo');

  const updateReadme = await ctx.task(updateReadmeTask, {
    targetDir,
    sourceDir
  });

  if (!updateReadme.success) {
    return {
      success: false,
      error: 'Failed to update README',
      details: updateReadme
    };
  }

  artifacts.push(...(updateReadme.artifacts || []));

  // ============================================================================
  // TASK 7: Security scan
  // ============================================================================

  ctx.log('info', 'Task 7: Security scan before commit');

  const securityScan = await ctx.task(securityScanTask, {
    targetDir
  });

  if (!securityScan.success && securityScan.issues && securityScan.issues.length > 0) {
    return {
      success: false,
      error: 'Security issues found',
      details: securityScan
    };
  }

  artifacts.push(...(securityScan.artifacts || []));

  // ============================================================================
  // TASK 8: Commit and push
  // ============================================================================

  ctx.log('info', 'Task 8: Committing and pushing to GitHub');

  const commitPush = await ctx.task(commitPushTask, {
    targetDir,
    remoteUrl
  });

  if (!commitPush.success) {
    return {
      success: false,
      error: 'Failed to commit and push',
      details: commitPush
    };
  }

  artifacts.push(...(commitPush.artifacts || []));

  const endTime = ctx.now();
  const duration = endTime - startTime;

  return {
    success: true,
    commitHash: commitPush.commitHash,
    repoUrl: remoteUrl.replace('.git', ''),
    targetDir,
    artifacts,
    duration,
    metadata: {
      processId: 'phase-g-rs-extraction',
      timestamp: startTime
    }
  };
}

// ============================================================================
// TASK DEFINITIONS
// ============================================================================

export const initRepoTask = defineTask('init-repo', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Initialize new repository',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git repository setup specialist',
      task: 'Create and initialize the new standalone repository for ResourceSharing',
      context: {
        targetDir: args.targetDir,
        remoteUrl: args.remoteUrl
      },
      instructions: [
        'Create and initialize a new git repository:',
        '',
        '1. Create target directory: ' + args.targetDir,
        '   Use Bash: mkdir -p ' + args.targetDir,
        '',
        '2. Initialize git repository:',
        '   Use Bash: cd ' + args.targetDir + ' && git init',
        '',
        '3. Add remote origin:',
        '   Use Bash: cd ' + args.targetDir + ' && git remote add origin ' + args.remoteUrl,
        '',
        '4. Create comprehensive .gitignore file using Write tool at ' + args.targetDir + '/.gitignore with content:',
        '```',
        '# Python',
        '__pycache__/',
        '*.py[cod]',
        '*$py.class',
        '*.egg-info/',
        '.eggs/',
        'dist/',
        'build/',
        '',
        '# Virtual environments',
        '.venv/',
        'venv/',
        'ENV/',
        '',
        '# IDE',
        '.idea/',
        '.vscode/',
        '*.swp',
        '*.swo',
        '',
        '# Secrets and production configs',
        '.env',
        '*.env',
        'config/*_prod*.json',
        'config/*_sandbox*.json',
        'config/test_config.json',
        '',
        '# Data files (user data, never commit)',
        'input/*.tsv',
        'processed/*.tsv',
        '',
        '# Output (logs and reports, never commit)',
        'output/logs/*.log',
        'output/reports/*.csv',
        '*.log',
        '',
        '# Keep directory structure',
        '!input/.gitkeep',
        '!processed/.gitkeep',
        '!output/.gitkeep',
        '!output/logs/.gitkeep',
        '!output/reports/.gitkeep',
        '',
        '# OS',
        '.DS_Store',
        'Thumbs.db',
        '',
        '# Testing',
        '.pytest_cache/',
        '.coverage',
        'htmlcov/',
        '```',
        '',
        '5. Verify: cd ' + args.targetDir + ' && git status && git remote -v',
        '',
        'Return success=true, repoPath, remoteConfigured'
      ],
      outputFormat: 'JSON with success (boolean), repoPath (string), remoteConfigured (boolean), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'repoPath', 'remoteConfigured'],
      properties: {
        success: { type: 'boolean' },
        repoPath: { type: 'string' },
        remoteConfigured: { type: 'boolean' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const copyCodeTask = defineTask('copy-code', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Copy ResourceSharing project code and structure',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python code migration specialist',
      task: 'Copy the ResourceSharing project code to the new repository with proper structure',
      context: {
        sourceDir: args.sourceDir,
        targetDir: args.targetDir
      },
      instructions: [
        'Copy ResourceSharing project files from AlmaAPITK monorepo to standalone repo:',
        '',
        'Source location: ' + args.sourceDir,
        'Target location: ' + args.targetDir,
        '',
        '1. Copy main Python scripts using Read then Write:',
        '   - ' + args.sourceDir + '/resource_sharing_forms_processor.py -> ' + args.targetDir + '/resource_sharing_forms_processor.py',
        '   - ' + args.sourceDir + '/test_user_retrieval.py -> ' + args.targetDir + '/test_user_retrieval.py',
        '',
        '2. Create directory structure:',
        '   - mkdir -p ' + args.targetDir + '/config',
        '   - mkdir -p ' + args.targetDir + '/docs',
        '   - mkdir -p ' + args.targetDir + '/batch',
        '   - mkdir -p ' + args.targetDir + '/input',
        '   - mkdir -p ' + args.targetDir + '/output/logs',
        '   - mkdir -p ' + args.targetDir + '/output/reports',
        '   - mkdir -p ' + args.targetDir + '/processed',
        '',
        '3. Copy config template (ONLY the example, NOT production configs):',
        '   - ' + args.sourceDir + '/config/rs_forms_config.example.json -> ' + args.targetDir + '/config/rs_forms_config.example.json',
        '',
        '4. Copy documentation:',
        '   - ' + args.sourceDir + '/docs/IDENTIFIER_DETECTION.md -> ' + args.targetDir + '/docs/IDENTIFIER_DETECTION.md',
        '',
        '5. Copy batch file (will be updated in later step):',
        '   - ' + args.sourceDir + '/batch/rs_forms_monitor_sandbox.bat -> ' + args.targetDir + '/batch/rs_forms_monitor_sandbox.bat',
        '',
        '6. Create .gitkeep files to preserve empty directories:',
        '   - echo "" > ' + args.targetDir + '/input/.gitkeep',
        '   - echo "" > ' + args.targetDir + '/output/.gitkeep',
        '   - echo "" > ' + args.targetDir + '/output/logs/.gitkeep',
        '   - echo "" > ' + args.targetDir + '/output/reports/.gitkeep',
        '   - echo "" > ' + args.targetDir + '/processed/.gitkeep',
        '',
        '7. Verify imports in main script are only from almaapitk:',
        '   Grep for "from src\\." or "from client\\." or "from domains\\." - should find none',
        '   Grep for "from almaapitk import" - should find this',
        '',
        'DO NOT copy: config/*_sandbox*.json, config/test_config.json, __pycache__/',
        '',
        'Return success=true, filesCopied array, importsVerified boolean'
      ],
      outputFormat: 'JSON with success (boolean), filesCopied (array), importsVerified (boolean), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'filesCopied', 'importsVerified'],
      properties: {
        success: { type: 'boolean' },
        filesCopied: { type: 'array' },
        importsVerified: { type: 'boolean' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const createPoetryTask = defineTask('create-poetry-config', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create Poetry pyproject.toml',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python packaging specialist',
      task: 'Create pyproject.toml with Poetry configuration for ResourceSharing project',
      context: {
        targetDir: args.targetDir
      },
      instructions: [
        'Create pyproject.toml at ' + args.targetDir + '/pyproject.toml using Write tool with content:',
        '',
        '[tool.poetry]',
        'name = "alma-rs-lending-request-automation"',
        'version = "1.0.0"',
        'description = "Automated processing of Resource Sharing lending requests from Microsoft Forms to Alma ILS"',
        'authors = ["Hagay Bar-Or <hagaybar@gmail.com>"]',
        'readme = "README.md"',
        'package-mode = false',
        '',
        '[tool.poetry.dependencies]',
        'python = "^3.12"',
        'almaapitk = { git = "https://github.com/hagaybar/AlmaAPITK.git", tag = "v0.2.2" }',
        '',
        '[tool.poetry.group.dev.dependencies]',
        'pytest = "^8.0"',
        '',
        '[build-system]',
        'requires = ["poetry-core"]',
        'build-backend = "poetry.core.masonry.api"',
        '',
        'Return success=true and pyprojectPath'
      ],
      outputFormat: 'JSON with success (boolean), pyprojectPath (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'pyprojectPath'],
      properties: {
        success: { type: 'boolean' },
        pyprojectPath: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const createTestsTask = defineTask('create-tests', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create smoke test and unit tests',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python test developer',
      task: 'Create smoke test script and unit tests for ResourceSharing project',
      context: {
        targetDir: args.targetDir
      },
      instructions: [
        'Create test infrastructure for the standalone ResourceSharing project:',
        '',
        '1. Create scripts/ directory: mkdir -p ' + args.targetDir + '/scripts',
        '',
        '2. Create smoke test at ' + args.targetDir + '/scripts/smoke_project.py with content:',
        '```python',
        '#!/usr/bin/env python3',
        '"""Smoke test - verifies almaapitk imports work correctly."""',
        'import sys',
        '',
        'def main():',
        '    print("Testing almaapitk imports...")',
        '    ',
        '    try:',
        '        from almaapitk import (',
        '            AlmaAPIClient,',
        '            AlmaAPIError,',
        '            ResourceSharing,',
        '            Users,',
        '            CitationMetadataError,',
        '        )',
        '        print("  AlmaAPIClient: OK")',
        '        print("  AlmaAPIError: OK")',
        '        print("  ResourceSharing: OK")',
        '        print("  Users: OK")',
        '        print("  CitationMetadataError: OK")',
        '    except ImportError as e:',
        '        print(f"  FAILED: {e}")',
        '        sys.exit(1)',
        '    ',
        '    print("\\nTesting main script import...")',
        '    try:',
        '        from resource_sharing_forms_processor import ResourceSharingFormsProcessor',
        '        print("  ResourceSharingFormsProcessor: OK")',
        '    except ImportError as e:',
        '        print(f"  FAILED: {e}")',
        '        sys.exit(1)',
        '    ',
        '    print("\\nAll imports OK!")',
        '    return 0',
        '',
        'if __name__ == "__main__":',
        '    sys.exit(main())',
        '```',
        '',
        '3. Create tests/ directory: mkdir -p ' + args.targetDir + '/tests',
        '',
        '4. Create ' + args.targetDir + '/tests/__init__.py (empty file)',
        '',
        '5. Create unit test at ' + args.targetDir + '/tests/test_imports.py with content:',
        '```python',
        '"""Test that all imports use almaapitk public API only."""',
        'import unittest',
        'import re',
        'from pathlib import Path',
        '',
        'class TestImports(unittest.TestCase):',
        '    """Verify import hygiene."""',
        '',
        '    def test_almaapitk_imports(self):',
        '        """Verify almaapitk public API imports work."""',
        '        from almaapitk import (',
        '            AlmaAPIClient,',
        '            AlmaAPIError,',
        '            ResourceSharing,',
        '            Users,',
        '            CitationMetadataError,',
        '        )',
        '        self.assertIsNotNone(AlmaAPIClient)',
        '        self.assertIsNotNone(ResourceSharing)',
        '',
        '    def test_no_legacy_imports(self):',
        '        """Ensure no forbidden legacy imports exist."""',
        '        forbidden_patterns = [',
        '            r"from\\s+src\\.",',
        '            r"import\\s+src\\.",',
        '            r"from\\s+client\\.",',
        '            r"from\\s+domains\\.",',
        '            r"from\\s+utils\\.",',
        '        ]',
        '',
        '        project_root = Path(__file__).parent.parent',
        '        python_files = list(project_root.glob("*.py"))',
        '',
        '        for py_file in python_files:',
        '            content = py_file.read_text()',
        '            for pattern in forbidden_patterns:',
        '                matches = re.findall(pattern, content)',
        '                self.assertEqual(',
        '                    len(matches), 0,',
        '                    f"Found forbidden import {pattern!r} in {py_file.name}"',
        '                )',
        '',
        'if __name__ == "__main__":',
        '    unittest.main()',
        '```',
        '',
        'Return success=true, smokeScriptPath, testPath'
      ],
      outputFormat: 'JSON with success (boolean), smokeScriptPath (string), testPath (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'smokeScriptPath', 'testPath'],
      properties: {
        success: { type: 'boolean' },
        smokeScriptPath: { type: 'string' },
        testPath: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const validateLocalTask = defineTask('validate-local', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Run local validation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python project validator',
      task: 'Run poetry install and tests locally',
      context: {
        targetDir: args.targetDir
      },
      instructions: [
        'Validate the project works locally:',
        '',
        '1. Change to target directory and run poetry install:',
        '   cd ' + args.targetDir + ' && poetry install',
        '   This will install almaapitk from GitHub',
        '',
        '2. Run smoke test:',
        '   cd ' + args.targetDir + ' && poetry run python scripts/smoke_project.py',
        '',
        '3. Run unit tests:',
        '   cd ' + args.targetDir + ' && poetry run python -m pytest tests/ -v',
        '',
        'If any step fails, report the error in detail',
        'Return success=true only if ALL steps pass'
      ],
      outputFormat: 'JSON with success (boolean), poetryInstall (object), smokeTest (object), unitTests (object), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        poetryInstall: { type: 'object' },
        smokeTest: { type: 'object' },
        unitTests: { type: 'object' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const updateReadmeTask = defineTask('update-readme', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Update README.md for standalone repo',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Technical documentation writer',
      task: 'Copy and update README.md for the standalone ResourceSharing project',
      context: {
        targetDir: args.targetDir,
        sourceDir: args.sourceDir
      },
      instructions: [
        'Update README for standalone repository:',
        '',
        '1. Read the source README at ' + args.sourceDir + '/docs/README.md',
        '',
        '2. Create updated README at ' + args.targetDir + '/README.md that:',
        '   - Updates Installation section to use Poetry (poetry install)',
        '   - Removes any references to AlmaAPITK internal paths',
        '   - Updates usage examples to NOT use PYTHONPATH',
        '   - Adds Prerequisites section: Python 3.12+, Poetry, ALMA_SB_API_KEY/ALMA_PROD_API_KEY env vars',
        '   - Keeps the core functionality documentation intact',
        '',
        '3. Update the batch file at ' + args.targetDir + '/batch/rs_forms_monitor_sandbox.bat to:',
        '   - Remove PYTHONPATH setting',
        '   - Use poetry run python resource_sharing_forms_processor.py',
        '   - Point to config in the local config/ directory',
        '',
        'Return success=true, readmePath'
      ],
      outputFormat: 'JSON with success (boolean), readmePath (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'readmePath'],
      properties: {
        success: { type: 'boolean' },
        readmePath: { type: 'string' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const securityScanTask = defineTask('security-scan', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Security scan before commit',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Security analyst',
      task: 'Scan the repository for security issues before commit',
      context: {
        targetDir: args.targetDir
      },
      instructions: [
        'Scan the repository for security issues:',
        '',
        '1. Check for forbidden imports using Grep tool:',
        '   Pattern: "from src\\." or "import src\\." in ' + args.targetDir,
        '   Pattern: "from client\\." or "from domains\\." or "from utils\\." in ' + args.targetDir,
        '   These should find NO matches in .py files',
        '',
        '2. Check for potential secrets using Grep:',
        '   Pattern: API_KEY, api_key, password, token, secret',
        '   Review any matches - they should only be in comments/docs, not actual values',
        '',
        '3. Verify .gitignore exists and includes:',
        '   - .env, *.env',
        '   - config/*_prod*.json, config/*_sandbox*.json',
        '   - *.tsv (or input/*.tsv)',
        '',
        '4. Check no production/sandbox config files exist:',
        '   ls -la ' + args.targetDir + '/config/',
        '   Should only have rs_forms_config.example.json',
        '',
        'Return success=true if no critical issues, issues array with any findings'
      ],
      outputFormat: 'JSON with success (boolean), issues (array), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'issues'],
      properties: {
        success: { type: 'boolean' },
        issues: { type: 'array' },
        artifacts: { type: 'array' }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/result.json`
  }
}));

export const commitPushTask = defineTask('commit-push', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Commit and push to GitHub',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git workflow specialist',
      task: 'Create clean commit and push to GitHub',
      context: {
        targetDir: args.targetDir,
        remoteUrl: args.remoteUrl
      },
      instructions: [
        'Commit and push to GitHub:',
        '',
        '1. Stage all files:',
        '   cd ' + args.targetDir + ' && git add .',
        '',
        '2. Check what will be committed:',
        '   git status',
        '',
        '3. Create commit using HEREDOC for message:',
        '   git commit -m "$(cat <<\'EOF\'',
        'Initial commit: Extract ResourceSharing from AlmaAPITK',
        '',
        '- Resource sharing forms processor for Alma lending requests',
        '- Citation metadata enrichment (PMID/DOI detection)',
        '- Watch mode for continuous folder monitoring',
        '- Depends on almaapitk v0.2.2',
        '',
        'Extracted from: https://github.com/hagaybar/AlmaAPITK',
        '',
        'Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>',
        'EOF',
        ')"',
        '',
        '4. Push to origin main:',
        '   git push -u origin main',
        '',
        '5. Get and return the commit hash:',
        '   git rev-parse HEAD',
        '',
        'Return success=true, commitHash, pushStatus'
      ],
      outputFormat: 'JSON with success (boolean), commitHash (string), pushStatus (string), artifacts (array)'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'commitHash', 'pushStatus'],
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
