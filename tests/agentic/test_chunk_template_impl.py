"""Smoke tests for .a5c/processes/chunk-template-impl.js."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESS = REPO_ROOT / ".a5c" / "processes" / "chunk-template-impl.js"


def test_template_impl_exists():
    assert PROCESS.exists()


def test_template_impl_passes_node_check():
    r = subprocess.run(["node", "--check", str(PROCESS)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_template_impl_exports_process_and_named_tasks():
    """The chunk-impl process exports `process` plus all gate-chain task definitions.

    NOTE: As of 2026-05-06 (Phase 1 of the guardrails registry), the legacy
    `scopeCheckTask` export was replaced with `denyPathsTask`. The old
    `scope_check.py` module remains in the tree but is no longer wired into
    the chunk-impl process. See
    `docs/superpowers/plans/2026-05-06-guardrails-registry-phase-1.md`.
    """
    script = (
        "import('" + str(PROCESS) + "').then(m => {"
        "['process','validateEnvTask','implementTask','staticGatesTask',"
        "'denyPathsTask','unitTestsTask','contractTestTask','mergeIntoIntegrationTask']"
        ".forEach(n => { if (!(n in m)) { console.error('missing: ' + n); process.exit(1); } });"
        "console.log('ok')});"
    )
    r = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, r.stderr
