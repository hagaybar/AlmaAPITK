"""Smoke tests for .a5c/processes/chunk-test.js."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESS = REPO_ROOT / ".a5c" / "processes" / "chunk-test.js"


def test_chunk_test_js_exists():
    assert PROCESS.exists(), f"missing {PROCESS}"


def test_chunk_test_js_passes_node_check():
    # node --check parses but doesn't run; catches syntax errors
    r = subprocess.run(
        ["node", "--check", str(PROCESS)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"syntax error:\n{r.stderr}"


def test_chunk_test_js_exports_process():
    # Use a tiny dynamic-import script to confirm shape
    script = (
        "import('" + str(PROCESS) + "').then(m => {"
        "if (typeof m.process !== 'function') process.exit(1);"
        "console.log('ok')});"
    )
    r = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"import failed:\n{r.stderr}"


def test_append_run_log_writes_to_docs_path():
    """R10 regression test for #95.

    The chunk-test process's appendRunLogTask must emit a `log_path`
    pointing at `docs/AGENTIC_RUN_LOG.md` (the post-#93 canonical path),
    not at the repo root. Pre-#93 the run log lived at the repo root;
    #93 moved it via `git mv` to `docs/AGENTIC_RUN_LOG.md`. The
    chunk-test JS still hardcoded the old path until this fix landed —
    every chunk-test run silently re-created an untracked stray
    `AGENTIC_RUN_LOG.md` at the repo root.
    """
    src = PROCESS.read_text()
    # appendRunLogTask must build its log_path from repoRoot + the docs/ path
    assert "${args.repoRoot}/docs/AGENTIC_RUN_LOG.md" in src, (
        "appendRunLogTask must reference ${args.repoRoot}/docs/AGENTIC_RUN_LOG.md "
        "(post-#93 canonical); #95 regression"
    )
    # And must NOT reference the obsolete root-path form
    assert "${args.repoRoot}/AGENTIC_RUN_LOG.md" not in src, (
        "appendRunLogTask still references obsolete repo-root path; "
        "#95 regression: must use docs/AGENTIC_RUN_LOG.md"
    )


def test_generate_pytest_prompt_requires_runtime_fixture_loading():
    """R10 regression for #101.

    `generatePytestFilesTask`'s agent prompt must explicitly require
    loading fixtures from `test-data.json` at RUNTIME, not baking
    operator-supplied values into the source. Sandbox-test files are
    committed to the public repo (precedent: commits 9221f66, 32a0435);
    inlined fixture values are an R9 (PII redaction) violation.

    Surfaced by the chunk-test agent during the `client-ergonomics`
    run on 2026-05-05: the agent did the right thing only because
    the operator explicitly instructed it. Default behavior must be
    runtime loading — the prompt is the only place to put that default.
    """
    src = PROCESS.read_text()
    assert "generatePytestFilesTask" in src
    # Isolate the generatePytestFilesTask prompt block (everything from
    # the export statement up to the next exported task).
    start = src.index("generatePytestFilesTask")
    end = src.index("runPytestTask", start)
    prompt_block = src[start:end]
    lower = prompt_block.lower()
    # The prompt must reference test-data.json and runtime loading.
    assert "test-data.json" in prompt_block
    assert "runtime" in lower, (
        "generate-pytest prompt must specify runtime fixture loading "
        "(not generation-time substitution); R9 + #101"
    )
    # And must explicitly forbid inlining operator-supplied values.
    forbids_inlining = (
        "never bake" in lower
        or "never inline" in lower
        or "do not inline" in lower
        or "must not inline" in lower
    )
    assert forbids_inlining, (
        "generate-pytest prompt must explicitly forbid baking/inlining "
        "fixture values into source; R9 + #101"
    )
