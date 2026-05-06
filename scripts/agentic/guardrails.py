"""Guardrails registry — Phase 1.

Loads `guardrails.json` (a small structured rule set) and provides matchers
the chunk pipeline can call as gates. Phase 1 populates `enforced.deny_paths`
only; `instructed` is stubbed for forward compatibility (Phases 2-4 will
render it into agent prompts).

Schema (version 1):

    {
      "version": 1,
      "enforced": {
        "deny_paths": ["prefix1/", "prefix2/"]   # path prefixes
      },
      "instructed": {
        "implement": [],   # list of {id, severity, text} dicts (Phase 2+)
        "critique": []
      }
    }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_VERSIONS = {1}


class GuardrailsSchemaError(ValueError):
    """Raised when guardrails.json is malformed or has an unsupported version."""


def load_guardrails(path: Path | str) -> dict[str, Any]:
    """Load and validate the guardrails registry.

    Raises GuardrailsSchemaError with a message naming the bad field if the
    schema is invalid. Otherwise returns the parsed dict.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GuardrailsSchemaError("guardrails.json: top level must be an object")

    version = raw.get("version")
    if version is None:
        raise GuardrailsSchemaError("guardrails.json: missing required field 'version'")
    if version not in SUPPORTED_VERSIONS:
        raise GuardrailsSchemaError(
            f"guardrails.json: unsupported version {version!r} "
            f"(supported: {sorted(SUPPORTED_VERSIONS)})"
        )

    enforced = raw.get("enforced") or {}
    if not isinstance(enforced, dict):
        raise GuardrailsSchemaError("guardrails.json: 'enforced' must be an object")
    deny_paths = enforced.get("deny_paths", [])
    if not isinstance(deny_paths, list) or not all(isinstance(p, str) for p in deny_paths):
        raise GuardrailsSchemaError(
            "guardrails.json: 'enforced.deny_paths' must be a list of strings"
        )

    instructed = raw.get("instructed") or {}
    if not isinstance(instructed, dict):
        raise GuardrailsSchemaError("guardrails.json: 'instructed' must be an object")

    return raw


def match_deny_paths(diff_files: list[str], deny_paths: list[str]) -> list[str]:
    """Return diff_files entries that match any deny_paths prefix.

    A deny_paths entry ending in '/' matches any path whose first segments
    equal the prefix. So '.github/' matches '.github/workflows/release.yml'
    but NOT '.github_old/notes.md' (which would be a different top-level
    directory). Entries without a trailing '/' are treated as exact-file
    deny rules.
    """
    violations: list[str] = []
    for path in diff_files:
        for prefix in deny_paths:
            if prefix.endswith("/"):
                if path == prefix.rstrip("/") or path.startswith(prefix):
                    violations.append(path)
                    break
            else:
                if path == prefix:
                    violations.append(path)
                    break
    return violations


def _cli_deny_paths(registry_path: str) -> int:
    import sys

    payload = json.loads(sys.stdin.read())
    if "diff_files" not in payload:
        json.dump(
            {"pass": False, "error": "bad_payload", "missing_key": "diff_files"},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
        return 3

    try:
        registry = load_guardrails(registry_path)
    except (GuardrailsSchemaError, FileNotFoundError) as exc:
        json.dump(
            {"pass": False, "error": "registry_invalid", "detail": str(exc)},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
        return 3

    deny_paths = registry["enforced"].get("deny_paths", [])
    violations = match_deny_paths(payload["diff_files"], deny_paths)
    result = {"pass": not violations, "violations": violations}
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if not violations else 2


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="scripts.agentic.guardrails")
    sub = parser.add_subparsers(dest="cmd", required=True)
    deny = sub.add_parser("deny-paths")
    deny.add_argument("--registry", default="guardrails.json")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd == "deny-paths":
        return _cli_deny_paths(args.registry)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
