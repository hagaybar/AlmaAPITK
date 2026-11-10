"""R10 regression tests for issue #208.

Alma Analytics answers a nonexistent report path with HTTP 500. The client's
retry policy treated that 500 as transient, retried it, and once the retries
ran out the caller received a raw ``requests.exceptions.RetryError``: not an
``AlmaAPIError``, so ``except AlmaAPIError`` missed it, and with no status
code or tracking ID.

Covered here, against a real local HTTP server so the urllib3 retry adapter
actually runs:

* A 5xx that outlasts the retries surfaces as ``AlmaServerError`` (an
  ``AlmaAPIError``) carrying the status and Alma's tracking ID, on every
  surface.
* On the analytics surface a 500 is not retried at all; 502/503/504 and 429
  still are.
* Other surfaces still retry a 500 (GET), as before.
* A caller-supplied ``retry=`` policy that raises ``RetryError`` itself is
  still wrapped, so the error contract holds.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests
from urllib3.util import Retry

from almaapitk import AlmaAPIError
from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaServerError

_TRACKING_ID = "E01-0000000000-TEST-TRACKING"
_ANALYTICS = "almaws/v1/analytics/reports"
_BIBS = "almaws/v1/bibs/99000000000000000"


class _Server:
    """Local server that answers every GET with a scripted status."""

    def __init__(self, status: int):
        self.hits = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.hits += 1
                body = json.dumps({"errorsExist": True, "errorList": {
                    "error": [{"errorCode": "", "errorMessage": "boom",
                               "trackingId": _TRACKING_ID}]}}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server_factory(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", "test-sandbox-key")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    servers = []

    def make(status):
        servers.append(_Server(status))
        return servers[-1]

    yield make
    for s in servers:
        s.close()


def _client(server, **kw):
    kw.setdefault("backoff_factor", 0)
    return AlmaAPIClient("SANDBOX", host=server.url, **kw)


def test_analytics_500_is_alma_error_and_not_retried(server_factory):
    server = server_factory(500)

    with pytest.raises(AlmaAPIError) as excinfo:
        _client(server).get(_ANALYTICS, params={"path": "/no/such/report"})

    err = excinfo.value
    assert isinstance(err, AlmaServerError)
    assert err.status_code == 500
    assert err.tracking_id == _TRACKING_ID
    assert server.hits == 1


@pytest.mark.parametrize("status", [429, 503])
def test_analytics_still_retries_transient_statuses(server_factory, status):
    server = server_factory(status)

    with pytest.raises(AlmaAPIError):
        _client(server, max_retries=2).get(_ANALYTICS)

    assert server.hits == 3


def test_other_surfaces_still_retry_500_then_raise_alma_error(server_factory):
    server = server_factory(500)

    with pytest.raises(AlmaServerError) as excinfo:
        _client(server, max_retries=2).get(_BIBS)

    assert excinfo.value.status_code == 500
    assert excinfo.value.tracking_id == _TRACKING_ID
    assert server.hits == 3


def test_custom_retry_policy_retry_error_is_wrapped(server_factory):
    server = server_factory(500)
    retry = Retry(total=1, status_forcelist=[500], backoff_factor=0,
                  raise_on_status=True)

    with pytest.raises(AlmaServerError) as excinfo:
        _client(server, retry=retry).get(_BIBS)

    assert isinstance(excinfo.value.__cause__, requests.exceptions.RetryError)
