"""Alma Lab request capture and per-write gate (issue #230)."""
import pytest
import requests

from almaapitk.lab.capture import Recorder, WriteCancelled, make_lab_client
from tests.unit.lab.conftest import TEST_KEY


def test_capture_masks_key(lab_client):
    lab_client.http.answers = [{"body": {"mms_id": "990000000000001"}}]
    rec = Recorder(lab_client, gate=None)
    rec.install()
    rec.start()
    lab_client.get("almaws/v1/bibs/990000000000001", params={"view": "full"})
    [req] = rec.requests
    assert req.method == "GET" and req.status == 200 and req.sent
    assert "view=full" in req.url
    assert req.headers["Authorization"] == "apikey ***"
    assert TEST_KEY not in repr(req)
    assert '"mms_id"' in req.response_body


def test_capture_records_non_json_body(lab_client):
    lab_client.http.answers = [
        {"status": 200, "body": b"<bib><mms_id>1</mms_id></bib>", "content_type": "application/xml"},
        {"status": 204, "body": b"", "content_type": "text/plain"},
    ]
    rec = Recorder(lab_client, gate=lambda m, u, b: True)
    rec.install()
    rec.start()
    lab_client.get("almaws/v1/bibs/1")
    lab_client.delete("almaws/v1/bibs/1")
    assert rec.requests[0].response_body.startswith("<bib>")
    assert rec.requests[1].status == 204 and rec.requests[1].response_body == ""


def test_tracking_id_from_error_list(lab_client):
    body = {"errorsExist": True, "errorList": {"error": [{"errorCode": "402459", "trackingId": "E01-TRACK-1"}]}}
    lab_client.http.answers = [{"status": 400, "body": body}]
    rec = Recorder(lab_client, gate=None)
    rec.install()
    rec.start()
    with pytest.raises(Exception):
        lab_client.get("almaws/v1/acq/invoices/1")
    assert rec.requests[0].tracking_id == "E01-TRACK-1"


def test_write_without_gate_is_cancelled_and_not_sent(lab_client):
    rec = Recorder(lab_client, gate=None)
    rec.install()
    rec.start()
    with pytest.raises(WriteCancelled):
        lab_client.post("almaws/v1/bibs", data={"x": 1})
    assert lab_client.http.calls == []
    [req] = rec.requests
    assert req.method == "POST" and req.sent is False and req.status is None


def test_gate_approves_write_and_sees_body(lab_client):
    seen = []
    rec = Recorder(lab_client, gate=lambda m, u, b: seen.append((m, u, b)) or True)
    rec.install()
    rec.start()
    lab_client.put("almaws/v1/bibs/1", data={"title": "x"})
    assert seen and seen[0][0] == "PUT" and '"title"' in seen[0][2]
    assert rec.requests[0].sent is True and len(lab_client.http.calls) == 1


def test_install_is_idempotent(lab_client):
    lab_client.http.answers = [{}]
    rec = Recorder(lab_client, gate=None)
    rec.install()
    rec.install()
    rec.start()
    lab_client.get("almaws/v1/bibs/1")
    assert len(rec.requests) == 1


def test_records_exception_then_reraises(lab_client):
    lab_client.http.answers = [requests.exceptions.ConnectionError("boom")]
    rec = Recorder(lab_client, gate=None)
    rec.install()
    rec.start()
    with pytest.raises(requests.exceptions.ConnectionError):
        lab_client.get("almaws/v1/bibs/1")
    assert rec.requests[0].error.startswith("ConnectionError")
    assert rec.requests[0].sent is True


def test_lab_client_retries_get_only(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", TEST_KEY)
    monkeypatch.delenv("ALMA_PROD_API_KEY", raising=False)
    client = make_lab_client("SANDBOX")
    try:
        adapters = list(client._session.adapters.values())
        assert adapters
        forcelists = [set(a.max_retries.status_forcelist) for a in adapters]
        for a in adapters:
            assert set(a.max_retries.allowed_methods) == {"GET"}
        assert {429, 503} <= forcelists[0]
        assert any(500 not in f for f in forcelists)  # analytics adapter kept its own list (#208)
    finally:
        client.close()
