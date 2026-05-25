"""Read-only rail: a guarded session refuses non-GET requests.

A workflow targeting PRODUCTION is handed a client whose session is guarded
so it can only ever read — a write attempt raises immediately, before any
I/O. This makes the "PRODUCTION is read-only, always" invariant enforceable
rather than aspirational. See issue #156 / the harness spec.
"""
from __future__ import annotations

import requests


class ReadOnlyViolation(RuntimeError):
    """Raised when a read-only (e.g. PRODUCTION) smoke attempts a write."""


def install_readonly_guard(session: requests.Session) -> None:
    """Wrap ``session.request`` so any non-GET verb raises ReadOnlyViolation."""
    inner = session.request

    def _guarded(method, url, **kwargs):
        if str(method).upper() != "GET":
            raise ReadOnlyViolation(
                f"Read-only smoke attempted a {method} to {url}. "
                "PRODUCTION-targeted workflows may only read."
            )
        return inner(method, url, **kwargs)

    session.request = _guarded  # type: ignore[assignment]
