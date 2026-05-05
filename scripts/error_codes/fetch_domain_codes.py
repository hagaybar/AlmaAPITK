"""Harvest documented Alma error codes from per-domain swagger JSON.

Ex Libris publishes machine-readable swagger per Alma API domain at::

    https://developers.exlibrisgroup.com/wp-content/uploads/alma/openapi/<domain>.json

Each documented endpoint's response shape carries the error codes it can
emit, embedded in the response ``description`` text in the form::

    402119 - 'General error.'
    401861 - 'Source institution user with given identifier not found.'

This script downloads the swagger (cached under
``scripts/error_codes/swagger_cache/``) and emits a structured JSON list
of (code, message, declaring endpoints) suitable for cross-checking
against ``ERROR_CODE_REGISTRY`` in ``AlmaAPIClient``.

CLI::

    python -m scripts.error_codes.fetch_domain_codes <domain> [--force]
        [--cache-dir DIR] [--output {json,summary}]

Domain names match Alma's swagger filenames (``users``, ``bibs``, ``acq``,
``conf``, etc.) — they are NOT always identical to ``src/almaapitk/domains/``
filenames; see ``DOMAIN_ALIASES`` for the small mapping table.

Pattern source: GitHub issue #90.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SWAGGER_URL_TEMPLATE = (
    "https://developers.exlibrisgroup.com/wp-content/uploads/alma/openapi/{domain}.json"
)

# Default cache directory lives next to this module so re-runs are reproducible
# across operators (the cache is checked into git via the README .gitkeep).
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "swagger_cache"

# The HTTP verbs OpenAPI 3.x recognises on a path object. Vendor extensions
# (keys starting with ``x-``) are ignored.
HTTP_METHODS = ("get", "post", "put", "delete", "patch")

# Error code lines look like ``402119 - 'General error.'`` inside an HTTP
# response's ``description`` field. The single quote is canonical in Alma's
# swagger but accept double quotes too for resilience. Codes are 4-8 digits
# in practice; widen if Alma changes that.
ERROR_LINE_PATTERN = re.compile(
    r"(\d{4,8})\s*-\s*['\"](.*?)['\"]",
    re.DOTALL,
)

# Map ``src/almaapitk/domains/<file>.py`` filenames (and a few hand-typed
# aliases) to Alma's swagger domain name. Used by ``infer_swagger_domains``
# below. Conservative on purpose — only entries we can verify against a
# live swagger URL.
DOMAIN_ALIASES = {
    "users": "users",
    "user": "users",
    "bibs": "bibs",
    "bib": "bibs",
    "bibliographic_records": "bibs",
    "bibliographicrecords": "bibs",
    "acquisition": "acq",
    "acquisitions": "acq",
    "acq": "acq",
    "admin": "conf",
    "configuration": "conf",
    "conf": "conf",
    "analytics": "analytics",
    "courses": "courses",
    "course": "courses",
    "electronic": "electronic",
    "tasklists": "task-lists",
    "task_lists": "task-lists",
    "resource_sharing": "partners",
    "resourcesharing": "partners",
    "partners": "partners",
}


def fetch_swagger(
    domain: str,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Return the parsed swagger document for one Alma API domain.

    Caches the raw JSON under ``cache_dir/<domain>.json`` and a sidecar
    ``cache_dir/<domain>.fetched.json`` carrying the URL + ISO fetch
    timestamp (JSON has no comment syntax, hence the sidecar — the cache
    file itself stays a plain swagger document for downstream tools).

    Args:
        domain: Alma swagger domain (``users``, ``bibs``, ``acq``, ...).
        cache_dir: Directory for cached files.
        force: Re-download even if a cache file is present.
        timeout: Request timeout in seconds.

    Raises:
        ValueError: ``domain`` is empty.
        urllib.error.URLError: Network / HTTP failure on first fetch.
    """
    if not domain:
        raise ValueError("domain is required")

    cache_path = cache_dir / f"{domain}.json"
    if cache_path.exists() and not force:
        return json.loads(cache_path.read_text(encoding="utf-8"))

    url = SWAGGER_URL_TEMPLATE.format(domain=domain)
    cache_dir.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 — trusted host
        body = resp.read().decode("utf-8")

    parsed = json.loads(body)
    cache_path.write_text(body, encoding="utf-8")
    sidecar = cache_dir / f"{domain}.fetched.json"
    sidecar.write_text(
        json.dumps(
            {
                "domain": domain,
                "url": url,
                "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return parsed


def extract_codes(swagger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return ``{code: {message, endpoints[]}}`` for every error code declared in ``swagger``.

    The first declaration wins for the canonical ``message``; subsequent
    occurrences are folded into ``endpoints[]`` with their per-endpoint
    message variant (which Alma sometimes phrases differently across
    paths — see #90's note about partial coverage tolerance).
    """
    codes: dict[str, dict[str, Any]] = {}
    for path, methods in (swagger.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method not in HTTP_METHODS or not isinstance(op, dict):
                continue
            for status, response in (op.get("responses") or {}).items():
                description = (
                    response.get("description", "")
                    if isinstance(response, dict) else ""
                )
                if not description:
                    continue
                for code, raw_msg in ERROR_LINE_PATTERN.findall(description):
                    msg = raw_msg.strip()
                    entry = codes.setdefault(
                        code, {"message": msg, "endpoints": []}
                    )
                    entry["endpoints"].append(
                        {
                            "method": method.upper(),
                            "path": path,
                            "httpStatus": str(status),
                            "messageVariant": msg,
                        }
                    )
    return codes


def build_report(
    domain: str, swagger: dict[str, Any], *, source_url: str | None = None
) -> dict[str, Any]:
    """Build the JSON report shape consumed by chunk-template-impl.js.

    Stable shape so downstream tooling can rely on it::

        {
          "domain": "users",
          "swaggerUrl": "https://...",
          "fetchedAt": "2026-05-05T04:30:00+00:00",
          "codeCount": 107,
          "codes": [
            {"code": "60100", "message": "...",
             "endpoints": [{"method": "GET", "path": "...",
                            "httpStatus": "400", "messageVariant": "..."}]},
            ...
          ]
        }
    """
    codes = extract_codes(swagger)
    return {
        "domain": domain,
        "swaggerUrl": source_url or SWAGGER_URL_TEMPLATE.format(domain=domain),
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "codeCount": len(codes),
        "codes": [
            {
                "code": code,
                "message": entry["message"],
                "endpoints": entry["endpoints"],
            }
            for code, entry in sorted(codes.items(), key=lambda kv: int(kv[0]))
        ],
    }


def _print_summary(report: dict[str, Any], *, limit: int = 20) -> None:
    """Print a human-readable summary of ``report`` to stdout."""
    print(f"{report['domain']}: {report['codeCount']} unique error codes")
    print(f"swagger: {report['swaggerUrl']}")
    print(f"fetched: {report['fetchedAt']}")
    print("---")
    for c in report["codes"][:limit]:
        first = c["endpoints"][0]
        print(
            f"  {c['code']:>8}  {c['message'][:80]:<80}  "
            f"({len(c['endpoints'])}×, e.g. {first['method']} {first['path']})"
        )
    if report["codeCount"] > limit:
        print(f"  ... ({report['codeCount'] - limit} more)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch_domain_codes",
        description=(
            "Harvest documented Alma error codes from a per-domain swagger. "
            "See module docstring for the swagger URL template and code "
            "extraction format."
        ),
    )
    parser.add_argument(
        "domain",
        help="Alma swagger domain name (users, bibs, acq, conf, ...).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"Directory for cached swagger (default: {DEFAULT_CACHE_DIR}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if a cache file is present.",
    )
    parser.add_argument(
        "--output",
        choices=("json", "summary"),
        default="json",
        help="Emit structured JSON (default) or a human summary.",
    )
    args = parser.parse_args(argv)

    try:
        swagger = fetch_swagger(
            args.domain, cache_dir=args.cache_dir, force=args.force
        )
    except urllib.error.URLError as exc:
        print(
            f"fetch_domain_codes: failed to fetch swagger for "
            f"domain={args.domain!r}: {exc}",
            file=sys.stderr,
        )
        return 2

    report = build_report(args.domain, swagger)

    if args.output == "summary":
        _print_summary(report)
    else:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
