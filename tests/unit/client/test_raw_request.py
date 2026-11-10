"""Tests for ``AlmaAPIClient.raw_request`` (issue #183).

``raw_request`` is the public pass-through for Alma endpoints almaapitk does
not wrap yet. It must be a pure delegate to ``_request``: same auth, region,
session, redaction and typed-error behaviour as the typed verbs, and no
transport logic of its own. ``requests.Session.request`` is patched, so no
network is used.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from almaapitk import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaRateLimitError,
    AlmaResourceNotFoundError,
    AlmaResponse,
    AlmaServerError,
    AlmaValidationError,
)
from almaapitk.client.AlmaAPIClient import REGION_HOSTS

_FAKE_KEY = "fake-raw-request-key-0000"
_SESSION_REQUEST = "requests.Session.request"


def _response(status=200, body=None, content_type="application/json", text=""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.ok = status < 400
    resp.headers = {"content-type": content_type}
    resp.text = text
    resp.json.return_value = {} if body is None else body
    return resp


def _error_body(code, message="synthetic error", tracking="E01-TEST-TRACKING"):
    return {
        "errorsExist": True,
        "errorList": {"error": [{
            "errorCode": code, "errorMessage": message, "trackingId": tracking,
        }]},
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", _FAKE_KEY)
    monkeypatch.delenv("ALMA_PROD_API_KEY", raising=False)
    with AlmaAPIClient("SANDBOX") as c:
        yield c


def _sent(mock_request):
    """(method, url, kwargs) of the single Session.request call."""
    assert mock_request.call_count == 1
    args, kwargs = mock_request.call_args
    return args[0], args[1], kwargs


# --- dispatch and routing --------------------------------------------------


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
def test_dispatches_each_verb(client, method):
    with patch(_SESSION_REQUEST, return_value=_response()) as req:
        result = client.raw_request(method, "almaws/v1/courses")
    sent_method, url, _ = _sent(req)
    assert sent_method == method
    assert url == f"{client.base_url}/almaws/v1/courses"
    assert isinstance(result, AlmaResponse)


def test_method_is_case_insensitive(client):
    with patch(_SESSION_REQUEST, return_value=_response()) as req:
        client.raw_request("get", "almaws/v1/courses")
    assert _sent(req)[0] == "GET"


@pytest.mark.parametrize("method", ["PATCH", "HEAD", "OPTIONS", "", None, 1])
def test_rejects_unsupported_method_without_sending(client, method):
    with patch(_SESSION_REQUEST) as req:
        with pytest.raises(AlmaValidationError):
            client.raw_request(method, "almaws/v1/courses")
    req.assert_not_called()


@pytest.mark.parametrize("endpoint", [
    "", None, "https://elsewhere.example/almaws/v1/courses",
    "http://elsewhere.example/x", 42,
])
def test_rejects_bad_endpoint_without_sending(client, endpoint):
    with patch(_SESSION_REQUEST) as req:
        with pytest.raises(AlmaValidationError):
            client.raw_request("GET", endpoint)
    req.assert_not_called()


def test_dict_body_goes_as_json(client):
    body = {"code": {"value": "PLACEHOLDER-101"}}
    with patch(_SESSION_REQUEST, return_value=_response()) as req:
        client.raw_request("POST", "almaws/v1/courses", data=body)
    _, _, kwargs = _sent(req)
    assert kwargs["json"] == body
    assert "data" not in kwargs


def test_xml_body_goes_as_data_with_xml_accept(client):
    xml = "<course><code>PLACEHOLDER</code></course>"
    with patch(_SESSION_REQUEST, return_value=_response(
        content_type="application/xml", text="<course/>"
    )) as req:
        result = client.raw_request(
            "POST", "almaws/v1/courses", data=xml,
            content_type="application/xml",
        )
    _, _, kwargs = _sent(req)
    assert kwargs["data"] == xml
    assert kwargs["headers"]["Content-Type"] == "application/xml"
    assert kwargs["headers"]["Accept"] == "application/xml"
    assert result.text() == "<course/>"


def test_params_headers_timeout_pass_through(client):
    with patch(_SESSION_REQUEST, return_value=_response()) as req:
        client.raw_request(
            "GET", "almaws/v1/courses",
            params={"limit": 50, "q": "code~PLACEHOLDER"},
            custom_headers={"X-Test": "1"},
            timeout=12.5,
        )
    _, _, kwargs = _sent(req)
    assert kwargs["params"] == {"limit": 50, "q": "code~PLACEHOLDER"}
    assert kwargs["headers"]["X-Test"] == "1"
    assert kwargs["timeout"] == 12.5


def test_delegates_to_request(client):
    """Pure delegate: no transport logic of its own."""
    sentinel = object()
    with patch.object(client, "_request", return_value=sentinel) as inner:
        out = client.raw_request(
            "put", "/almaws/v1/courses/X", data={"a": 1},
            params={"p": 1}, content_type=None,
            custom_headers={"H": "v"}, timeout=3,
        )
    assert out is sentinel
    inner.assert_called_once_with(
        "PUT", "/almaws/v1/courses/X", data={"a": 1}, params={"p": 1},
        content_type=None, custom_headers={"H": "v"}, timeout=3,
    )


# --- auth, region, redaction ----------------------------------------------


def test_injects_apikey_header(client):
    with patch(_SESSION_REQUEST, return_value=_response()) as req:
        client.raw_request("GET", "almaws/v1/courses")
    _, _, kwargs = _sent(req)
    assert kwargs["headers"]["Authorization"] == f"apikey {_FAKE_KEY}"


def test_key_absent_from_logs(client, caplog):
    caplog.set_level(logging.DEBUG)
    with patch(_SESSION_REQUEST, return_value=_response(
        404, _error_body("401861")
    )):
        with pytest.raises(AlmaAPIError) as excinfo:
            client.raw_request("GET", "almaws/v1/courses/MISSING")
    assert _FAKE_KEY not in caplog.text
    assert _FAKE_KEY not in str(excinfo.value)


@pytest.mark.parametrize("region", sorted(REGION_HOSTS))
def test_region_resolution(monkeypatch, region):
    monkeypatch.setenv("ALMA_SB_API_KEY", _FAKE_KEY)
    with AlmaAPIClient("SANDBOX", region=region) as c:
        with patch(_SESSION_REQUEST, return_value=_response()) as req:
            c.raw_request("GET", "almaws/v1/courses")
    assert _sent(req)[1].startswith(REGION_HOSTS[region] + "/")


def test_closed_client_refuses(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", _FAKE_KEY)
    c = AlmaAPIClient("SANDBOX")
    c.close()
    with pytest.raises(AlmaAPIError, match="closed"):
        c.raw_request("GET", "almaws/v1/courses")


# --- typed errors, same as the typed verbs ---------------------------------


@pytest.mark.parametrize("status,body,expected", [
    (400, _error_body("401861"), AlmaResourceNotFoundError),
    (404, {}, AlmaResourceNotFoundError),
    (429, _error_body("401890"), AlmaRateLimitError),
    (500, {}, AlmaServerError),
    (400, _error_body("999999"), AlmaAPIError),
])
def test_errors_match_typed_get(client, status, body, expected):
    with patch(_SESSION_REQUEST, return_value=_response(status, body)):
        with pytest.raises(AlmaAPIError) as raw_exc:
            client.raw_request("GET", "almaws/v1/courses/X")
    with patch(_SESSION_REQUEST, return_value=_response(status, body)):
        with pytest.raises(AlmaAPIError) as get_exc:
            client.get("almaws/v1/courses/X")
    assert type(raw_exc.value) is type(get_exc.value)
    assert isinstance(raw_exc.value, expected)
    assert raw_exc.value.status_code == status
    assert raw_exc.value.alma_code == get_exc.value.alma_code
    assert raw_exc.value.tracking_id == get_exc.value.tracking_id


def test_unwrapped_endpoint_and_iter_paged_same_path(client):
    """Acceptance: reach an endpoint with no typed wrapper, then page it."""
    page = {"course": [{"code": {"value": "C1"}}], "total_record_count": 1}
    with patch(_SESSION_REQUEST, return_value=_response(body=page)):
        resp = client.raw_request("GET", "almaws/v1/courses")
        assert resp.data["course"][0]["code"]["value"] == "C1"
        walked = list(client.iter_paged("almaws/v1/courses", record_key="course"))
    assert [c["code"]["value"] for c in walked] == ["C1"]
