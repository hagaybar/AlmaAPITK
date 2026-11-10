"""Shared fakes for Alma Lab tests: a real AlmaAPIClient whose HTTP layer is scripted."""
import json

import pytest
import requests

TEST_KEY = "lab-test-key-0000"


def make_response(method, url, status=200, body=b"{}", content_type="application/json", headers=None, params=None):
    resp = requests.Response()
    resp.status_code = status
    resp._content = body if isinstance(body, bytes) else json.dumps(body).encode()
    resp.headers.update({"Content-Type": content_type, **(headers or {})})
    resp.url = url
    resp.request = requests.Request(method, url, params=params, headers={"Authorization": f"apikey {TEST_KEY}"}).prepare()
    resp.raw = None
    return resp


class ScriptedHTTP:
    """Replaces ``session.request``: answers from a script, records every call."""

    def __init__(self, answers=None):
        self.answers = list(answers or [])
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        answer = self.answers.pop(0) if self.answers else {}
        if isinstance(answer, Exception):
            raise answer
        return make_response(method, url, params=kwargs.get("params"), **answer)


@pytest.fixture
def lab_client(monkeypatch):
    """A Sandbox AlmaAPIClient with a scripted HTTP layer at ``client.http``."""
    from almaapitk import AlmaAPIClient

    monkeypatch.delenv("ALMA_PROD_API_KEY", raising=False)
    client = AlmaAPIClient("SANDBOX", api_key=TEST_KEY)
    client.http = ScriptedHTTP()
    client._session.request = client.http
    yield client
    client.close()


@pytest.fixture(autouse=True)
def _restore_almapi_log_level():
    """The CLI quiets the toolkit's loggers process-wide; don't leak that into other tests."""
    import logging

    logger = logging.getLogger("almapi")
    before = logger.level
    yield
    logger.setLevel(before)
