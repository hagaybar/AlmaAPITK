"""Tests for scripts/agentic/chunks (Bash CLI)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "agentic" / "chunks"


def run_cli(*args: str, env_overrides: dict | None = None, cwd: Path | None = None):
    import os
    env = os.environ.copy()
    # Strip ALMA_PROD_API_KEY from inherited env so R8 only fires when a test
    # explicitly sets it via env_overrides. Without this, any developer with
    # prod credentials in their shell would trip R8 on every run.
    env.pop("ALMA_PROD_API_KEY", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(CLI), *args],
        capture_output=True, text=True,
        env=env, cwd=str(cwd or REPO_ROOT),
    )


def test_help_shows_subcommands():
    r = run_cli("help")
    assert r.returncode == 0
    out = r.stdout + r.stderr
    for cmd in ["list", "status", "next", "define", "run-impl", "run-test", "abort"]:
        assert cmd in out


def test_list_empty_chunks_dir(tmp_path):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    r = run_cli("list", env_overrides={"CHUNKS_DIR": str(chunks)})
    assert r.returncode == 0
    assert "no active chunks" in r.stdout.lower() or r.stdout.strip() == ""


def test_refuses_when_prod_key_set(tmp_path):
    """R8 — agent must not run with ALMA_PROD_API_KEY in env."""
    r = run_cli(
        "list",
        env_overrides={
            "CHUNKS_DIR": str(tmp_path / "chunks"),
            "ALMA_PROD_API_KEY": "fake-prod-key",
        },
    )
    assert r.returncode != 0
    assert "ALMA_PROD_API_KEY" in (r.stdout + r.stderr)


def test_unknown_subcommand_errors():
    r = run_cli("frobnicate")
    assert r.returncode != 0


# ---- R10 regression for #99 Layer 1: warn at define time on empty files_to_touch ----

def test_define_warns_when_issue_lacks_files_to_touch_section(tmp_path):
    """Integration test: `chunks define` must print a stderr WARNING when
    any defined issue's parsed `files_to_touch` is empty. See #99 Layer 1.

    Reproduces the `client-ergonomics` (#13, #16) stall pattern: issue body
    has Complexity/Benefit headers (parser requirement) but no
    '## Files to touch' section, so the parser returns `files_to_touch: []`
    and the chunk is silently defined with a manifest that's guaranteed
    to fail R7 scope-check on every implement attempt.
    """
    import os
    chunks = tmp_path / "chunks"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    # Stub `gh` so it returns an issue body with NO Files-to-touch section.
    stub = bin_dir / "gh"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        # When invoked as `gh issue view N --json ...`, return a synthetic
        # JSON payload. Any other invocation (none expected here) prints
        # nothing and exits non-zero so failures are loud.
        "if [[ \"$1\" == 'issue' && \"$2\" == 'view' ]]; then\n"
        "  cat <<'JSON_EOF'\n"
        "{\n"
        "  \"number\": 13,\n"
        "  \"title\": \"test arch issue without Files-to-touch\",\n"
        "  \"url\": \"https://example.com/13\",\n"
        "  \"labels\": [],\n"
        "  \"body\": \"**Complexity:** S\\n**Benefit:** Medium\\n\\n## Acceptance criteria\\n- [ ] thing\\n\"\n"
        "}\n"
        "JSON_EOF\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n"
    )
    stub.chmod(0o755)

    env = os.environ.copy()
    env.pop("ALMA_PROD_API_KEY", None)
    env["CHUNKS_DIR"] = str(chunks)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    # Prepend real REPO_ROOT to PYTHONPATH so the bash script's Python
    # heredoc can import scripts.agentic.* (same workaround as
    # test_chunks_cli_runid.py).
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_ROOT}:{pp}" if pp else str(REPO_ROOT)

    r = subprocess.run(
        [str(CLI), "define", "--name", "test-empty-scope", "--issues", "13"],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )
    assert r.returncode == 0, f"chunks define failed unexpectedly:\n{r.stderr}"
    # The warning must appear on stderr listing the offending issue
    # number and pointing at the recovery options.
    assert "WARNING" in r.stderr, (
        f"expected scope-check warning on stderr; got:\n{r.stderr}"
    )
    assert "#13" in r.stderr
    assert "files_to_touch" in r.stderr
    assert "scope-check" in r.stderr
