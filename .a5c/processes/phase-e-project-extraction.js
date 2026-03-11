/**
 * @process phase-e-project-extraction
 * @description Phase E: Extract pilot project to standalone GitHub repository
 * @inputs { sourceDir: string, targetDir: string, remoteUrl: string }
 * @outputs { success: boolean, commitHash: string, repoUrl: string }
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

export async function process(inputs, ctx) {
  const { sourceDir, targetDir, remoteUrl } = inputs;

  const startTime = ctx.now();
  const artifacts = [];

  ctx.log('info', 'Phase E: Extract pilot project to standalone repository');

  // ============================================================================
  // TASK 1: Initialize repository
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
  // TASK 6: Create README
  // ============================================================================

  ctx.log('info', 'Task 6: Creating README.md');

  const createReadme = await ctx.task(createReadmeTask, {
    targetDir
  });

  if (!createReadme.success) {
    return {
      success: false,
      error: 'Failed to create README',
      details: createReadme
    };
  }

  artifacts.push(...(createReadme.artifacts || []));

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
      processId: 'phase-e-project-extraction',
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
      task: 'Create and initialize the new standalone repository',
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
        '4. Create comprehensive .gitignore file using Write tool at ' + args.targetDir + '/.gitignore:',
        '   Include: __pycache__/, *.py[cod], .env, .venv/, output/, logs/, *.log, .idea/, .vscode/',
        '   config/*_prod*.json, *.tsv (except examples/), .pytest_cache/, dist/, *.egg-info/',
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
  title: 'Copy project code and structure',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python code migration specialist',
      task: 'Copy the project code to the new repository with proper structure',
      context: {
        sourceDir: args.sourceDir,
        targetDir: args.targetDir
      },
      instructions: [
        'Copy project files from AlmaAPITK monorepo to standalone repo:',
        '',
        'Source location: /home/hagaybar/projects/AlmaAPITK/src/projects/update_expired_users_emails/',
        'Target location: ' + args.targetDir,
        '',
        '1. Read the main script file:',
        '   /home/hagaybar/projects/AlmaAPITK/src/projects/update_expired_users_emails/update_expired_user_emails.py',
        '',
        '2. Write it to target as the main module:',
        '   ' + args.targetDir + '/update_expired_user_emails.py',
        '   The script already uses almaapitk imports - verify this is true',
        '',
        '3. Read the config template file:',
        '   /home/hagaybar/projects/AlmaAPITK/src/projects/update_expired_users_emails/email_update_config.json',
        '',
        '4. Sanitize and write as config example:',
        '   ' + args.targetDir + '/config/email_update_config.example.json',
        '   - Remove any real set_id values (use placeholder like "12345678900004146")',
        '   - Keep all _comment and _note fields for documentation',
        '   - Ensure dry_run is true in the example',
        '',
        '5. Create examples/ directory with sample TSV:',
        '   ' + args.targetDir + '/examples/sample_users.tsv',
        '   Content: "# Example user IDs (one per line)\\n# 300512175\\n# 208517532"',
        '',
        '6. Verify imports in main script are only from almaapitk:',
        '   Grep for "from src." or "from client." or "from domains." - should find none',
        '   Grep for "from almaapitk import" - should find this',
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
      task: 'Create pyproject.toml with Poetry configuration',
      context: {
        targetDir: args.targetDir
      },
      instructions: [
        'Create pyproject.toml at ' + args.targetDir + '/pyproject.toml using Write tool:',
        '',
        '[tool.poetry]',
        'name = "alma-update-expired-users-emails"',
        'version = "1.0.0"',
        'description = "Script for updating email addresses of expired users in Alma ILS"',
        'authors = ["Hagay Bar-Or <hagaybar@gmail.com>"]',
        'readme = "README.md"',
        '',
        '[tool.poetry.dependencies]',
        'python = "^3.12"',
        'almaapitk = { git = "https://github.com/hagaybar/AlmaAPITK.git", branch = "prod" }',
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
      task: 'Create smoke test script and unit tests',
      context: {
        targetDir: args.targetDir
      },
      instructions: [
        'Create test infrastructure for the standalone project:',
        '',
        '1. Create scripts/ directory: mkdir -p ' + args.targetDir + '/scripts',
        '',
        '2. Create smoke test at ' + args.targetDir + '/scripts/smoke_project.py:',
        '   ```python',
        '   #!/usr/bin/env python3',
        '   """Smoke test - verifies imports work correctly."""',
        '   import sys',
        '   ',
        '   def main():',
        '       # Test almaapitk imports',
        '       from almaapitk import (',
        '           AlmaAPIClient,',
        '           AlmaAPIError,',
        '           AlmaValidationError,',
        '           Admin,',
        '           Users,',
        '       )',
        '       print("almaapitk imports: OK")',
        '       ',
        '       # Test project module import',
        '       from update_expired_user_emails import EmailUpdateScript',
        '       print("EmailUpdateScript import: OK")',
        '       ',
        '       print("All smoke tests passed!")',
        '       return 0',
        '   ',
        '   if __name__ == "__main__":',
        '       sys.exit(main())',
        '   ```',
        '',
        '3. Create tests/ directory: mkdir -p ' + args.targetDir + '/tests',
        '',
        '4. Create ' + args.targetDir + '/tests/__init__.py (empty file)',
        '',
        '5. Create unit test at ' + args.targetDir + '/tests/test_imports.py:',
        '   ```python',
        '   """Test that all imports work correctly."""',
        '   import unittest',
        '   ',
        '   class TestImports(unittest.TestCase):',
        '       def test_almaapitk_imports(self):',
        '           """Test almaapitk public API imports."""',
        '           from almaapitk import (',
        '               AlmaAPIClient,',
        '               AlmaAPIError,',
        '               AlmaValidationError,',
        '               Admin,',
        '               Users,',
        '           )',
        '           self.assertTrue(callable(AlmaAPIClient))',
        '           self.assertTrue(callable(Admin))',
        '           self.assertTrue(callable(Users))',
        '       ',
        '       def test_project_module_import(self):',
        '           """Test project main module imports."""',
        '           from update_expired_user_emails import EmailUpdateScript',
        '           self.assertTrue(callable(EmailUpdateScript))',
        '       ',
        '       def test_no_legacy_imports(self):',
        '           """Verify no legacy imports in main module."""',
        '           import re',
        '           from pathlib import Path',
        '           ',
        '           # Find the module file',
        '           module_path = Path(__file__).parent.parent / "update_expired_user_emails.py"',
        '           content = module_path.read_text()',
        '           ',
        '           # Check for forbidden imports',
        '           forbidden = [',
        '               r"from\\s+src\\.",',
        '               r"import\\s+src\\.",',
        '               r"from\\s+client\\.",',
        '               r"from\\s+domains\\.",',
        '               r"from\\s+utils\\.",',
        '           ]',
        '           for pattern in forbidden:',
        '               matches = re.findall(pattern, content)',
        '               self.assertEqual(len(matches), 0, f"Found forbidden import: {pattern}")',
        '   ',
        '   if __name__ == "__main__":',
        '       unittest.main()',
        '   ```',
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
        '   OR: cd ' + args.targetDir + ' && poetry run python -m unittest discover tests -v',
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

export const createReadmeTask = defineTask('create-readme', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Create README.md',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Technical documentation writer',
      task: 'Create comprehensive README.md for the project',
      context: {
        targetDir: args.targetDir
      },
      instructions: [
        'Create README.md at ' + args.targetDir + '/README.md with:',
        '',
        '# Alma Update Expired Users Emails',
        '',
        'Script for updating email addresses of expired users in Alma ILS.',
        '',
        '## What it does',
        '- Processes a set of users from Alma (via set ID or TSV file)',
        '- Identifies users expired for a configurable number of days',
        '- Updates their email addresses using a configurable pattern',
        '- Supports dry-run mode for testing',
        '',
        '## Prerequisites',
        '- Python 3.12+',
        '- Poetry',
        '- Alma API credentials (environment variables)',
        '',
        '## Installation',
        '```bash',
        'poetry install',
        '```',
        '',
        '## Configuration',
        'Create config/email_update_config.json based on the example:',
        '```bash',
        'cp config/email_update_config.example.json config/email_update_config.json',
        '# Edit with your settings',
        '```',
        '',
        '## Environment Variables',
        '- `ALMA_SB_API_KEY` - Sandbox API key',
        '- `ALMA_PROD_API_KEY` - Production API key',
        '',
        '**Note: Secrets are NOT committed to the repository.**',
        '',
        '## Usage',
        '',
        '### Dry Run (default, safe)',
        '```bash',
        'poetry run python update_expired_user_emails.py --config config/email_update_config.json',
        '```',
        '',
        '### Live Update',
        '```bash',
        'poetry run python update_expired_user_emails.py --config config/email_update_config.json --live',
        '```',
        '',
        '### With Set ID',
        '```bash',
        'poetry run python update_expired_user_emails.py --set-id 12345678900004146 --environment SANDBOX',
        '```',
        '',
        '### With TSV file',
        '```bash',
        'poetry run python update_expired_user_emails.py --tsv users.tsv --pattern "expired-{user_id}@example.edu"',
        '```',
        '',
        '## Output',
        '- Logs are written to `./output/` directory',
        '- Results CSV is generated with update details',
        '',
        '## Testing',
        '```bash',
        'poetry run python scripts/smoke_project.py',
        'poetry run python -m pytest tests/ -v',
        '```',
        '',
        'Return success=true and readmePath'
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
        '   These should find NO matches',
        '',
        '2. Check for potential secrets using Grep:',
        '   Pattern: API_KEY, api_key, password, token, secret',
        '   Review any matches - they should only be in comments/docs, not actual values',
        '',
        '3. Verify .gitignore exists and includes:',
        '   - .env, *.env',
        '   - config/*_prod*.json',
        '   - *.tsv (or input/*.tsv)',
        '',
        '4. Check no production config files exist:',
        '   ls -la ' + args.targetDir + '/config/',
        '   Should only have .example.json files',
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
        'Initial extraction from AlmaAPITK monorepo',
        '',
        '- Extract update_expired_users_emails project',
        '- Use almaapitk public API via git dependency',
        '- Add Poetry configuration',
        '- Add smoke tests and unit tests',
        '- Add README with usage instructions',
        '',
        'Extracted from: https://github.com/hagaybar/AlmaAPITK',
        '',
        'Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>',
        'EOF',
        ')"',
        '',
        '4. Push to origin main:',
        '   git push -u origin main',
        '   (Use main as the branch name)',
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
