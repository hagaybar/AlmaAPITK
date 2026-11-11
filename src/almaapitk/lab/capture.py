"""Capture every HTTP request an operation makes, and gate each write.

The recorder wraps the client's ``_session.request``: every ``AlmaAPIClient``
verb goes through it, so what is recorded is what was actually sent and
received, not a reconstruction. Writes (anything but GET) are shown to a gate
before they leave; a refused or missing gate cancels the write.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from almaapitk import AlmaAPIClient, AlmaOperationCancelled

WriteGate = Callable[[str, str, Optional[str]], bool]
"""(method, url, body) → True to send the write, False to cancel it."""

MASKED_AUTH = "apikey ***"
_SECRET_PARAMS = {"apikey", "api_key", "access_token", "token", "password"}
SECRET_MASK = "***"
_TRACKING_JSON = re.compile(r'"trackingId"\s*:\s*"([^"]+)"')
_TRACKING_XML = re.compile(r"<trackingId>([^<]+)</trackingId>")


class WriteCancelled(AlmaOperationCancelled):
    """A write was not approved, so it was not sent."""


@dataclass
class CapturedRequest:
    """One HTTP request as sent, and its response."""

    method: str
    url: str
    headers: dict[str, str]
    body: Optional[str]
    status: Optional[int] = None
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: Optional[str] = None
    duration_ms: int = 0
    tracking_id: Optional[str] = None
    attempts: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    sent: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class Recorder:
    """Wraps a client's HTTP layer; collects ``CapturedRequest`` objects."""

    def __init__(self, client: AlmaAPIClient, gate: Optional[WriteGate]):
        self.client = client
        self.gate = gate
        self.requests: list[CapturedRequest] = []

    def install(self) -> None:
        session = self.client._session
        if getattr(session.request, "_lab_recorder", None) is self:
            return
        inner = session.request

        def recording_request(method: str, url: str, **kwargs: Any) -> requests.Response:
            return self._send(inner, method, url, kwargs)

        recording_request._lab_recorder = self  # type: ignore[attr-defined]
        session.request = recording_request

    def start(self) -> None:
        self.requests = []

    def _send(self, inner: Callable, method: str, url: str, kwargs: dict) -> requests.Response:
        method = method.upper()
        captured = CapturedRequest(
            method=method,
            url=_safe_url(url, kwargs.get("params")),
            headers=_mask_headers({**self.client._session.headers, **(kwargs.get("headers") or {})}),
            body=_body_text(kwargs),
        )
        self.requests.append(captured)
        if method != "GET" and not (self.gate and self.gate(method, captured.url, captured.body)):
            captured.sent = False
            raise WriteCancelled(f"{method} {captured.url} was not approved, so it was not sent")
        started = time.monotonic()
        try:
            response = inner(method, url, **kwargs)
        except Exception as exc:
            captured.duration_ms = int((time.monotonic() - started) * 1000)
            captured.error = f"{type(exc).__name__}: {exc}"
            raise
        captured.duration_ms = int((time.monotonic() - started) * 1000)
        _fill_response(captured, response)
        return response


def make_lab_client(environment: str, api_key: Optional[str] = None) -> AlmaAPIClient:
    """A client whose transport retries GET only (writes are never retried)."""
    client = AlmaAPIClient(environment, api_key=api_key)
    for adapter in client._session.adapters.values():
        retry = getattr(adapter, "max_retries", None)
        if retry is not None and hasattr(retry, "new"):
            adapter.max_retries = retry.new(allowed_methods=frozenset({"GET"}))
    return client


def _fill_response(captured: CapturedRequest, response: requests.Response) -> None:
    captured.status = response.status_code
    captured.response_headers = dict(response.headers)
    captured.response_body = response.text if response.content else ""
    prepared = getattr(response, "request", None)
    if prepared is not None:  # what requests actually put on the wire
        if prepared.url:
            captured.url = _safe_url(prepared.url, None)
        if prepared.headers:
            captured.headers = _mask_headers(dict(prepared.headers))
        if prepared.body is not None:
            body = prepared.body
            captured.body = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    match = _TRACKING_JSON.search(captured.response_body) or _TRACKING_XML.search(captured.response_body)
    captured.tracking_id = match.group(1) if match else None
    retries = getattr(getattr(response, "raw", None), "retries", None)
    for item in getattr(retries, "history", ()) or ():
        captured.attempts.append({
            "status": getattr(item, "status", None),
            "error": repr(item.error) if getattr(item, "error", None) else None,
        })


def _mask_headers(headers: dict) -> dict[str, str]:
    masked = {}
    for name, value in headers.items():
        masked[str(name)] = MASKED_AUTH if str(name).lower() == "authorization" else str(value)
    return masked


def _safe_url(url: str, params: Any) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in _SECRET_PARAMS]
    if params:
        items = params.items() if isinstance(params, dict) else params
        query += [(str(k), str(v)) for k, v in items
                  if v is not None and str(k).lower() not in _SECRET_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(query)))


def is_secret_param(name: str) -> bool:
    """A query parameter whose value is a credential (case-insensitive)."""
    return str(name).strip().lower() in _SECRET_PARAMS


def mask_secret_params(query: dict) -> dict:
    """A copy of ``query`` with credential values replaced by ``SECRET_MASK``."""
    return {k: (SECRET_MASK if is_secret_param(k) else v) for k, v in query.items()}


def _body_text(kwargs: dict) -> Optional[str]:
    if kwargs.get("json") is not None:
        return json.dumps(kwargs["json"], ensure_ascii=False)
    data = kwargs.get("data")
    if data is None:
        return None
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    if isinstance(data, (dict, list)):
        return json.dumps(data, ensure_ascii=False)
    return str(data)
