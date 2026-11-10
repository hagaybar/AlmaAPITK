"""Structural guard: domain classes reach Alma only through the client.

Issue #183: ``AlmaAPIClient._request`` is the single HTTP chokepoint, and
``raw_request`` is its public front door. Every domain call must go through
it to inherit auth, region, session pooling, redaction and the typed error
taxonomy. This walks the AST of every module under
``src/almaapitk/domains/`` and fails on:

* importing an HTTP transport (``urllib``, ``urllib3``, ``http.client``,
  ``httpx``, ``aiohttp``), or ``from requests import <anything but
  exceptions>``;
* calling ``requests.<verb>`` / ``requests.request`` / ``requests.Session``;
* a string literal that hand-builds an ``apikey`` auth header.

``import requests`` itself is allowed, because domains catch
``requests.exceptions.*``.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

DOMAINS = Path(__file__).resolve().parents[2] / "src" / "almaapitk" / "domains"

_BANNED_MODULES = ("urllib", "urllib3", "http.client", "httpx", "aiohttp")
_BANNED_REQUESTS_ATTRS = {
    "get", "post", "put", "delete", "patch", "head", "options",
    "request", "Session", "session",
}


def _offences(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_BANNED_MODULES):
                    found.append(f"{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith(_BANNED_MODULES):
                found.append(f"{node.lineno}: from {mod} import ...")
            elif mod == "requests" and any(
                a.name != "exceptions" for a in node.names
            ):
                found.append(f"{node.lineno}: from requests import ...")
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "requests"
            and node.attr in _BANNED_REQUESTS_ATTRS
        ):
            found.append(f"{node.lineno}: requests.{node.attr}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "apikey " in node.value.lower()
        ):
            found.append(f"{node.lineno}: hand-built apikey header")
    return found


@pytest.mark.parametrize(
    "path", sorted(DOMAINS.glob("*.py")), ids=lambda p: p.name
)
def test_domain_routes_only_through_client(path):
    assert _offences(path) == []


def test_guard_catches_a_direct_call(tmp_path):
    """The guard is not vacuous."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import requests\n"
        "from urllib.request import urlopen\n"
        "requests.get('https://x')\n"
        "h = {'Authorization': 'apikey ' + k}\n"
    )
    assert len(_offences(bad)) == 3


def test_guard_allows_exception_catching(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text(
        "import requests\n"
        "from requests import exceptions\n"
        "try:\n    pass\n"
        "except requests.exceptions.RequestException:\n    pass\n"
    )
    assert _offences(ok) == []
