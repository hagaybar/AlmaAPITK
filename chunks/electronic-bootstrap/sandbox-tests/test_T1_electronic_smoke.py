"""SANDBOX test T1-electronic-smoke — Issue #66 (Electronic foundation).

Smoke test against the live SANDBOX tenant:

1. ``from almaapitk import AlmaAPIClient, Electronic`` succeeds — proves the
   lazy public-API wiring for ``Electronic`` is in place.
2. Instantiating ``Electronic(client)`` does not raise.
3. ``electronic.get_environment()`` returns the literal string ``'SANDBOX'``.
4. ``electronic.test_connection()`` returns ``True`` — the foundation
   delegates to ``AlmaAPIClient.test_connection`` (no Electronic-specific
   endpoints are wired up at this stage; sibling tickets #67/#68/#69 add
   them later).

This test is non-state-changing and needs no cleanup.

The test loads ``test-data.json`` at runtime for consistency with the rest
of the sandbox-tests suite, even though this chunk has no operator-supplied
fixture values (the file is intentionally ``{}``). This pattern keeps the
test file free of any inlined identifiers and complies with R9 (no real IDs
in publicly-visible content).
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

from almaapitk import AlmaAPIClient, Electronic

# Runtime-load fixture file for consistency with sibling sandbox-tests, even
# though no fixtures are required for the foundation smoke test.
_TEST_DATA = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "test-data.json").read_text()
)


def test_T1_electronic_smoke() -> None:
    """Verify Electronic foundation against the live SANDBOX tenant."""
    if not os.getenv("ALMA_SB_API_KEY"):
        pytest.skip("ALMA_SB_API_KEY not set; cannot run live SANDBOX test")

    client = AlmaAPIClient("SANDBOX")
    electronic = Electronic(client)

    env = electronic.get_environment()
    assert env == "SANDBOX", (
        f"electronic.get_environment() returned {env!r}, expected 'SANDBOX'"
    )

    ok = electronic.test_connection()
    assert ok is True, (
        f"electronic.test_connection() returned {ok!r}, expected True"
    )
