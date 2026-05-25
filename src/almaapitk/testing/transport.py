"""Dry-run transport: record requests, send nothing.

Used by the workflow smoke harness so a workflow's wiring can be validated
with no network and no credentials. See issue #156 / the harness spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests


@dataclass
class RecordedCall:
    """One request a workflow attempted while running under dry-run."""

    method: str
    url: str
    params: Optional[dict] = None
    headers: Optional[dict] = None
    body: Any = None


# Returns (status_code, content_bytes, content_type) for the canned response.
CannedResponse = Callable[[Optional[requests.PreparedRequest]], "tuple[int, bytes, str]"]


class RecordingTransport:
    """Replaces ``Session.request`` with a recorder that performs no I/O.

    Every call is appended to :attr:`calls`; a canned :class:`requests.Response`
    is returned so the workflow's own code keeps running. By default the canned
    response is an empty HTTP 200 JSON body; pass ``canned_response_factory`` to
    supply a shape a particular workflow needs (e.g. minimal analytics XML).
    """

    def __init__(self, canned_response_factory: Optional[CannedResponse] = None):
        self.calls: list[RecordedCall] = []
        self._factory: CannedResponse = canned_response_factory or (
            lambda req: (200, b"{}", "application/json")
        )

    def install(self, session: requests.Session) -> None:
        def _record(method, url, **kwargs):
            self.calls.append(
                RecordedCall(
                    method=method,
                    url=url,
                    params=kwargs.get("params"),
                    headers=kwargs.get("headers"),
                    body=kwargs.get("json", kwargs.get("data")),
                )
            )
            status, content, content_type = self._factory(None)
            resp = requests.Response()
            resp.status_code = status
            resp._content = content
            resp.headers["Content-Type"] = content_type
            resp.url = url
            return resp

        session.request = _record  # type: ignore[assignment]
