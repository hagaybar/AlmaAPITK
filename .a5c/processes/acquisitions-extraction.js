/**
 * @process acquisitions-extraction
 * @description Extract Acquisitions and RialtoProduction projects into unified standalone repository
 */
import pkg from '@a5c-ai/babysitter-sdk';
const { defineTask } = pkg;

// Task definitions
const setupStructureTask = defineTask('setup-structure', (args, ctx) => ({
  kind: 'agent',
  title: 'Create repository directory structure',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Repository setup specialist',
      task: 'Create the Alma-Acquisitions-Automation repository structure',
      context: args,
      instructions: [
        'Create directory /home/hagaybar/projects/Alma-Acquisitions-Automation if not exists',
        'Create subdirectories: workflows/rialto/, workflows/invoices/, common/, config/, batch/, docs/, tests/, scripts/, input/, output/, processed/, failed/, logs/',
        'Initialize git: git init',
        'Add remote: git remote add origin https://github.com/hagaybar/Alma-Acquisitions-Automation.git',
        'Create .gitkeep files in input/, output/, processed/, failed/, logs/',
        'Return JSON summary of created paths'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const createPyprojectTask = defineTask('create-pyproject', (args, ctx) => ({
  kind: 'agent',
  title: 'Create pyproject.toml',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python packaging specialist',
      task: 'Create pyproject.toml for Alma-Acquisitions-Automation at /home/hagaybar/projects/Alma-Acquisitions-Automation/pyproject.toml',
      context: {
        name: 'alma-acquisitions-automation',
        version: '1.0.0',
        description: 'Automated Alma Acquisitions workflows: Rialto POL processing and invoice management',
        authors: ['Hagay Bar-Or <hagaybar@gmail.com>'],
        dependencies: {
          python: '^3.12',
          almaapitk: '{ git = "https://github.com/hagaybar/AlmaAPITK.git", tag = "v0.2.2" }',
          pandas: '^2.0',
          openpyxl: '^3.1',
          PyPDF2: '^3.0'
        },
        devDependencies: { pytest: '^8.0' }
      },
      instructions: [
        'Write pyproject.toml with Poetry format',
        'Set package-mode = false',
        'Return confirmation'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const createGitignoreTask = defineTask('create-gitignore', (args, ctx) => ({
  kind: 'agent',
  title: 'Create .gitignore',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git configuration specialist',
      task: 'Create .gitignore at /home/hagaybar/projects/Alma-Acquisitions-Automation/.gitignore',
      context: {
        patterns: ['__pycache__/', '*.py[cod]', '.venv/', 'venv/', '.idea/', '.vscode/', '.env', '*.env',
          'config/*_prod*.json', 'config/*_sandbox*.json', 'input/*.xlsx', 'input/*.tsv', 'input/*.csv',
          'processed/*.pdf', 'output/**', 'logs/**', '*.log', '!input/.gitkeep', '!output/.gitkeep',
          '!logs/.gitkeep', '!processed/.gitkeep', '!failed/.gitkeep', '.DS_Store', '.pytest_cache/', '.coverage']
      },
      instructions: ['Write comprehensive .gitignore with all patterns', 'Return confirmation'],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const copyRialtoScriptsTask = defineTask('copy-rialto-scripts', (args, ctx) => ({
  kind: 'agent',
  title: 'Copy and update Rialto Python scripts',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python migration specialist',
      task: 'Copy RialtoProduction scripts to new structure with updated imports',
      context: {
        sourceDir: '/home/hagaybar/projects/AlmaAPITK/src/projects/RialtoProduction',
        targetDir: '/home/hagaybar/projects/Alma-Acquisitions-Automation/workflows/rialto',
        mapping: {
          'rialto_pipeline.py': 'pipeline.py',
          'rialto_complete_workflow.py': 'workflow.py',
          'utility/extract_pol_list.py': 'pdf_extractor.py'
        },
        importUpdates: {
          'from .utility.extract_pol_list': 'from .pdf_extractor',
          'from .rialto_complete_workflow': 'from .workflow'
        }
      },
      instructions: [
        'Read each source file from RialtoProduction',
        'Update relative imports as specified',
        'Write to workflows/rialto/ with new filenames',
        'Create __init__.py that exports main classes',
        'Return list of copied files'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const copyRialtoConfigTask = defineTask('copy-rialto-config', (args, ctx) => ({
  kind: 'agent',
  title: 'Copy Rialto config and batch files',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Configuration migration specialist',
      task: 'Copy Rialto config templates and batch files with updated paths',
      context: {
        sourceDir: '/home/hagaybar/projects/AlmaAPITK/src/projects/RialtoProduction',
        targetDir: '/home/hagaybar/projects/Alma-Acquisitions-Automation',
        configFiles: ['config/rialto_pipeline_config.example.json', 'config/rialto_workflow_config.example.json'],
        batchFiles: ['batch/rialto_pipeline_sandbox.bat', 'batch/rialto_pipeline_sandbox_single.bat',
          'batch/rialto_pipeline_production.bat', 'batch/rialto_pipeline_mock_test.bat'],
        pathUpdates: {
          'src\\projects\\RialtoProduction\\rialto_pipeline.py': '-m workflows.rialto.pipeline',
          'AlmaAPITK': 'Alma-Acquisitions-Automation'
        }
      },
      instructions: [
        'Copy config example files to config/',
        'Copy batch files to batch/ and update paths',
        'Remove PYTHONPATH references',
        'Return list of copied files'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const copyRialtoDocsTask = defineTask('copy-rialto-docs', (args, ctx) => ({
  kind: 'agent',
  title: 'Copy Rialto documentation',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Documentation migration specialist',
      task: 'Copy and organize Rialto documentation files',
      context: {
        sourceDir: '/home/hagaybar/projects/AlmaAPITK/src/projects/RialtoProduction',
        targetDir: '/home/hagaybar/projects/Alma-Acquisitions-Automation',
        files: ['README.md', 'RIALTO_WORKFLOW_README.md', 'docs/POL-12347_TEST_SUMMARY.md',
          'docs/rialto_project_flow_findings.md', 'input/example_pols.tsv']
      },
      instructions: [
        'Copy README.md as docs/RIALTO_README.md',
        'Copy other docs to docs/',
        'Copy example TSV to input/',
        'Return list of files'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const copyAcquisitionsScriptsTask = defineTask('copy-acquisitions-scripts', (args, ctx) => ({
  kind: 'agent',
  title: 'Copy Acquisitions Python scripts',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python migration specialist',
      task: 'Copy Acquisitions scripts to new structure',
      context: {
        sourceDir: '/home/hagaybar/projects/AlmaAPITK/src/projects/Acquisitions',
        targetDir: '/home/hagaybar/projects/Alma-Acquisitions-Automation/workflows/invoices',
        mapping: {
          'scripts/bulk_invoice_processor.py': 'bulk_processor.py',
          'scripts/erp_integration/erp_to_alma_invoice.py': 'erp_integration.py'
        }
      },
      instructions: [
        'Copy scripts to workflows/invoices/',
        'Create __init__.py that exports main classes',
        'Return list of files'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const copyAcquisitionsConfigTask = defineTask('copy-acquisitions-config', (args, ctx) => ({
  kind: 'agent',
  title: 'Copy Acquisitions config files',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Configuration specialist',
      task: 'Copy Acquisitions config templates',
      context: {
        sourceDir: '/home/hagaybar/projects/AlmaAPITK/src/projects/Acquisitions',
        targetDir: '/home/hagaybar/projects/Alma-Acquisitions-Automation/config',
        mapping: { 'configs/sample_invoice_processor_config.json': 'invoice_processor.example.json' }
      },
      instructions: ['Copy sample config to config/ with new name', 'Return confirmation'],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const createWorkflowsInitTask = defineTask('create-workflows-init', (args, ctx) => ({
  kind: 'agent',
  title: 'Create workflows package __init__.py files',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python packaging specialist',
      task: 'Create __init__.py files for workflows package',
      context: { targetDir: '/home/hagaybar/projects/Alma-Acquisitions-Automation' },
      instructions: [
        'Create workflows/__init__.py that imports from rialto and invoices',
        'Create common/__init__.py as empty placeholder',
        'Return confirmation'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const createSmokeTestTask = defineTask('create-smoke-test', (args, ctx) => ({
  kind: 'agent',
  title: 'Create smoke test script',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python testing specialist',
      task: 'Create smoke test at /home/hagaybar/projects/Alma-Acquisitions-Automation/scripts/smoke_project.py',
      context: {
        imports: ['almaapitk.AlmaAPIClient', 'almaapitk.Acquisitions', 'almaapitk.BibliographicRecords',
          'workflows.rialto.pipeline', 'workflows.rialto.workflow', 'workflows.rialto.pdf_extractor',
          'workflows.invoices.bulk_processor', 'workflows.invoices.erp_integration']
      },
      instructions: [
        'Create smoke_project.py that tests all imports',
        'Add project root to sys.path',
        'Return exit code 0 on success, 1 on failure',
        'Return confirmation'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const createUnitTestsTask = defineTask('create-unit-tests', (args, ctx) => ({
  kind: 'agent',
  title: 'Create unit tests',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python testing specialist',
      task: 'Create tests at /home/hagaybar/projects/Alma-Acquisitions-Automation/tests/',
      context: {},
      instructions: [
        'Create tests/__init__.py (empty)',
        'Create tests/test_imports.py that verifies no legacy imports (from src.*, from client.*, from domains.*)',
        'Scan all Python files in project',
        'Use unittest framework',
        'Return confirmation'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const createReadmeTask = defineTask('create-readme', (args, ctx) => ({
  kind: 'agent',
  title: 'Create main README.md',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Documentation specialist',
      task: 'Create README.md at /home/hagaybar/projects/Alma-Acquisitions-Automation/README.md',
      context: {
        sections: ['Overview', 'Features', 'Installation', 'Usage', 'Configuration', 'Testing', 'Structure']
      },
      instructions: [
        'Create comprehensive README with all sections',
        'Include poetry install instructions',
        'Show usage examples for both Rialto and invoice workflows',
        'No emojis',
        'Return confirmation'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const runPoetryInstallTask = defineTask('run-poetry-install', (args, ctx) => ({
  kind: 'agent',
  title: 'Run poetry install',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python environment specialist',
      task: 'Install dependencies in /home/hagaybar/projects/Alma-Acquisitions-Automation',
      context: {},
      instructions: ['cd to project directory', 'Run poetry install', 'Report any errors', 'Return status'],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const runSmokeTestTask = defineTask('run-smoke-test', (args, ctx) => ({
  kind: 'agent',
  title: 'Run smoke test',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python testing specialist',
      task: 'Run smoke test in /home/hagaybar/projects/Alma-Acquisitions-Automation',
      context: {},
      instructions: ['cd to project', 'Run: poetry run python scripts/smoke_project.py', 'Return status'],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const runUnitTestsTask = defineTask('run-unit-tests', (args, ctx) => ({
  kind: 'agent',
  title: 'Run unit tests',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Python testing specialist',
      task: 'Run pytest in /home/hagaybar/projects/Alma-Acquisitions-Automation',
      context: {},
      instructions: ['cd to project', 'Run: poetry run python -m pytest tests/ -v', 'Return status'],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

const gitCommitPushTask = defineTask('git-commit-push', (args, ctx) => ({
  kind: 'agent',
  title: 'Commit and push to GitHub',
  agent: {
    name: 'general-purpose',
    prompt: {
      role: 'Git specialist',
      task: 'Commit all files and push to GitHub',
      context: {
        projectDir: '/home/hagaybar/projects/Alma-Acquisitions-Automation',
        commitMessage: `Initial commit: Extract Acquisitions projects from AlmaAPITK

- Rialto POL workflow: PDF monitoring, item receiving, invoice payment
- Invoice processing: bulk processor and ERP integration
- Depends on almaapitk v0.2.2

Extracted from: https://github.com/hagaybar/AlmaAPITK

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>`
      },
      instructions: [
        'cd to project directory',
        'Run git add .',
        'Run git status',
        'Create commit with HEREDOC message',
        'Push to origin main with -u flag',
        'Return commit hash'
      ],
      outputFormat: 'JSON'
    }
  },
  io: {
    inputJsonPath: `tasks/${ctx.effectId}/input.json`,
    outputJsonPath: `tasks/${ctx.effectId}/output.json`
  }
}));

// Main process function
export async function process(inputs, ctx) {
  // Phase 1: Repository Setup
  await ctx.task(setupStructureTask, {});
  await ctx.task(createPyprojectTask, {});
  await ctx.task(createGitignoreTask, {});

  // Phase 2: Copy Rialto files
  await ctx.task(copyRialtoScriptsTask, {});
  await ctx.task(copyRialtoConfigTask, {});
  await ctx.task(copyRialtoDocsTask, {});

  // Phase 3: Copy Acquisitions files
  await ctx.task(copyAcquisitionsScriptsTask, {});
  await ctx.task(copyAcquisitionsConfigTask, {});

  // Phase 4: Create utilities and tests
  await ctx.task(createWorkflowsInitTask, {});
  await ctx.task(createSmokeTestTask, {});
  await ctx.task(createUnitTestsTask, {});

  // Phase 5: Create README
  await ctx.task(createReadmeTask, {});

  // Phase 6: Validation
  await ctx.task(runPoetryInstallTask, {});
  await ctx.task(runSmokeTestTask, {});
  await ctx.task(runUnitTestsTask, {});

  // Phase 7: Commit and Push
  await ctx.task(gitCommitPushTask, {});

  return { status: 'completed', message: 'Acquisitions projects extracted successfully' };
}
