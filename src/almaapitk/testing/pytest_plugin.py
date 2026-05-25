"""pytest plugin exposing the ``alma`` fixture for workflow smokes.

Registered as a ``pytest11`` entry point so it loads automatically once
``almaapitk[smoke]`` is installed — no conftest needed. See issue #156.

Live vs dry-run is selected by the ``ALMA_SMOKE_LIVE`` env var (set by
``make smoke-live``). A live check whose environment credentials are absent
is skipped, not failed (R-H3).
"""
from __future__ import annotations

import os

import pytest

from .client import build_smoke_client

_ENV_KEYS = {"SANDBOX": "ALMA_SB_API_KEY", "PRODUCTION": "ALMA_PROD_API_KEY"}


def _live_mode() -> bool:
    return os.getenv("ALMA_SMOKE_LIVE", "").strip().lower() in ("1", "true", "yes")


@pytest.fixture
def alma(request):
    """Yield a smoke client configured from the test's ``@workflow`` marker."""
    meta = getattr(request.function, "__alma_workflow__", None)
    if meta is None:
        pytest.fail(
            "a test using the `alma` fixture must be decorated with "
            "@workflow(name=..., environment=..., readonly=...)"
        )

    env = meta["environment"]
    readonly = meta["readonly"]
    live = _live_mode()

    if live and not os.getenv(_ENV_KEYS[env]):
        pytest.skip(f"live smoke needs {_ENV_KEYS[env]}; not set")

    # Dry-run sends nothing, so it must never require real credentials
    # (R-H3: runnable anywhere, including credential-free CI). Hand the
    # client a placeholder key in dry-run; in live mode pass None so the
    # client resolves the real key from the environment.
    client, transport = build_smoke_client(
        environment=env,
        readonly=readonly,
        dry_run=not live,
        api_key=None if live else "dry-run-no-network",
    )
    # Stash run context so the workflow body can branch dry-run vs live and
    # inspect recorded requests.
    request.node.alma_transport = transport
    request.node.alma_live = live
    try:
        yield client
    finally:
        client.close()
