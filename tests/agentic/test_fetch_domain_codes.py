"""Unit tests for scripts.error_codes.fetch_domain_codes.

Network-free: tests stub the swagger document inline and exercise
``extract_codes`` / ``build_report`` directly. The cache layer is tested
via the public ``fetch_swagger`` with ``force=False`` and a pre-seeded
cache file in ``tmp_path`` (no urllib involvement).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


SAMPLE_SWAGGER = {
    "openapi": "3.0.1",
    "paths": {
        "/almaws/v1/users": {
            "get": {
                "operationId": "getUsers",
                "responses": {
                    "200": {"description": "OK"},
                    "400": {
                        "description": (
                            "Bad Request\n\n"
                            "402119 - 'General error.'\n\n"
                            "401861 - 'Source institution user with given identifier not found.'\n\n"
                            "60224 - 'Organization institution not found.'"
                        ),
                    },
                },
            },
            "post": {
                "operationId": "createUser",
                "responses": {
                    "400": {
                        "description": (
                            "Bad Request\n\n"
                            "60224 - 'Organization institution not found.'"
                        ),
                    },
                },
            },
        },
        "/almaws/v1/users/{user_id}": {
            "delete": {
                "operationId": "deleteUser",
                "responses": {
                    "404": {"description": "User not found."},  # no error code
                },
            },
            # Vendor extension — must be ignored by the parser.
            "x-alma-private": {"foo": "bar"},
        },
    },
}


def test_extract_codes_finds_unique_codes():
    from scripts.error_codes.fetch_domain_codes import extract_codes

    codes = extract_codes(SAMPLE_SWAGGER)
    assert set(codes.keys()) == {"402119", "401861", "60224"}
    assert codes["402119"]["message"] == "General error."
    assert codes["401861"]["message"].startswith("Source institution user")


def test_extract_codes_aggregates_endpoints_per_code():
    """Code 60224 appears under both GET and POST /almaws/v1/users."""
    from scripts.error_codes.fetch_domain_codes import extract_codes

    codes = extract_codes(SAMPLE_SWAGGER)
    eps = codes["60224"]["endpoints"]
    assert len(eps) == 2
    methods = sorted(ep["method"] for ep in eps)
    assert methods == ["GET", "POST"]
    for ep in eps:
        assert ep["path"] == "/almaws/v1/users"
        assert ep["httpStatus"] == "400"


def test_extract_codes_ignores_vendor_extension_keys():
    """Path-object keys starting with ``x-`` (and non-method keys) are skipped."""
    from scripts.error_codes.fetch_domain_codes import extract_codes

    codes = extract_codes(SAMPLE_SWAGGER)
    # The x-alma-private vendor extension under /users/{user_id} must not
    # contribute any codes; the only registered codes come from /users.
    for entry in codes.values():
        for ep in entry["endpoints"]:
            assert ep["path"] == "/almaws/v1/users"


def test_extract_codes_handles_empty_swagger():
    from scripts.error_codes.fetch_domain_codes import extract_codes

    assert extract_codes({}) == {}
    assert extract_codes({"paths": {}}) == {}


def test_build_report_shape_is_stable():
    from scripts.error_codes.fetch_domain_codes import build_report

    report = build_report("users", SAMPLE_SWAGGER)
    assert report["domain"] == "users"
    assert report["swaggerUrl"].endswith("/users.json")
    assert "fetchedAt" in report
    assert report["codeCount"] == 3
    # Codes are sorted numerically (60224 < 401861 < 402119).
    assert [c["code"] for c in report["codes"]] == ["60224", "401861", "402119"]


def test_fetch_swagger_uses_cache_without_network(tmp_path: Path):
    """If the cache file exists, fetch_swagger returns its contents without
    touching the network. We verify by writing a hand-crafted cache file
    and asserting the loaded shape matches verbatim."""
    from scripts.error_codes.fetch_domain_codes import fetch_swagger

    cache_dir = tmp_path / "swagger_cache"
    cache_dir.mkdir()
    cached = {"paths": {"/x": {"get": {"responses": {}}}}}
    (cache_dir / "fakedom.json").write_text(json.dumps(cached))

    result = fetch_swagger("fakedom", cache_dir=cache_dir, force=False)
    assert result == cached


def test_fetch_swagger_rejects_empty_domain():
    from scripts.error_codes.fetch_domain_codes import fetch_swagger

    with pytest.raises(ValueError, match="domain is required"):
        fetch_swagger("")


def test_main_summary_output_writes_to_stdout(tmp_path: Path, capsys):
    """Smoke-test the CLI wrapper without touching the network."""
    from scripts.error_codes.fetch_domain_codes import main

    cache_dir = tmp_path / "swagger_cache"
    cache_dir.mkdir()
    (cache_dir / "fakedom.json").write_text(json.dumps(SAMPLE_SWAGGER))

    rc = main(["fakedom", "--cache-dir", str(cache_dir), "--output", "summary"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "fakedom: 3 unique error codes" in captured.out
    assert "60224" in captured.out
