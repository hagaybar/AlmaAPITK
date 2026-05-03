"""Open a draft PR for a chunk integration branch.

Enforces spec R1 (never to prod) and R2 (always draft).
Wraps `gh pr create`.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def format_body(
    chunk_name: str,
    issue_numbers: list[int],
    impl_summary: str,
    test_summary: str,
) -> str:
    closes = "\n".join(f"Closes #{n}" for n in issue_numbers)
    return f"""## Chunk: `{chunk_name}`

{closes}

## Implementation summary

{impl_summary}

## SANDBOX test summary

{test_summary}

## Verification done in the loop

- [x] py_compile on changed files
- [x] smoke_import.py
- [x] tests/test_public_api_contract.py
- [x] scope-check (files-to-touch) per R7
- [x] Per-issue unit tests
- [x] SANDBOX integration tests (see test-results.json in chunks/{chunk_name}/)

## Pending

- [ ] Human PR review
- [ ] Manual merge to `main` (R2 — never auto-merged)
- [ ] (Later) Manual `prod` promotion via test release + soak (R1 — out of pipeline scope)
"""


def build_pr_args(
    head_branch: str,
    title: str,
    body: str,
    base: str = "main",
    body_file: Path | None = None,
) -> list[str]:
    if base != "main":
        raise ValueError(f"base must be 'main' per R1; got {base!r}")
    if head_branch == "prod":
        raise ValueError("head must not be 'prod' per R1")
    if head_branch == "main":
        raise ValueError("head cannot be 'main'; PR must come from a chunk branch")

    args = ["gh", "pr", "create", "--draft", "--base", base, "--head", head_branch,
            "--title", title]
    if body_file is not None:
        args += ["--body-file", str(body_file)]
    else:
        args += ["--body", body]
    return args


def open_pr(
    head_branch: str,
    chunk_name: str,
    issue_numbers: list[int],
    impl_summary: str,
    test_summary: str,
    repo_root: Path,
) -> str:
    """Create the draft PR. Returns the PR URL on success."""
    body = format_body(chunk_name, issue_numbers, impl_summary, test_summary)
    title = f"chunk: {chunk_name} (#{', #'.join(str(n) for n in issue_numbers)})"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir=repo_root
    ) as tf:
        tf.write(body)
        body_file = Path(tf.name)
    try:
        args = build_pr_args(head_branch, title, body=body, body_file=body_file)
        result = subprocess.run(args, cwd=repo_root, capture_output=True, text=True,
                                check=True)
        return result.stdout.strip()
    finally:
        body_file.unlink(missing_ok=True)


def main() -> int:
    import json
    import sys

    payload = json.load(sys.stdin)
    url = open_pr(
        head_branch=payload["head_branch"],
        chunk_name=payload["chunk_name"],
        issue_numbers=payload["issue_numbers"],
        impl_summary=payload["impl_summary"],
        test_summary=payload["test_summary"],
        repo_root=Path(payload.get("repo_root", ".")),
    )
    json.dump({"pr_url": url}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
