"""Assemble an ``AlmaAPIClient`` wired for smoke testing.

See issue #156 / the harness spec. The read-only guard is installed LAST so
it wraps the dry-run recorder too — a write in dry-run is still a violation.
"""
from __future__ import annotations

from typing import Optional

from almaapitk import AlmaAPIClient

from .guards import install_readonly_guard
from .transport import CannedResponse, RecordingTransport


def build_smoke_client(
    environment: str,
    *,
    readonly: bool,
    dry_run: bool,
    api_key: Optional[str] = None,
    canned_response_factory: Optional[CannedResponse] = None,
) -> "tuple[AlmaAPIClient, Optional[RecordingTransport]]":
    """Return ``(client, transport)`` wired for a workflow smoke.

    In dry-run a :class:`RecordingTransport` is installed (no network) and
    returned; otherwise ``None`` is returned for the transport. When
    ``readonly`` is set the client's session refuses any non-GET request.
    """
    client = AlmaAPIClient(environment, api_key=api_key)

    transport: Optional[RecordingTransport] = None
    if dry_run:
        transport = RecordingTransport(canned_response_factory=canned_response_factory)
        transport.install(client._session)

    if readonly:
        install_readonly_guard(client._session)

    return client, transport
