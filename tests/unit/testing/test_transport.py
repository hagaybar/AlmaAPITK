import requests

from almaapitk.testing.transport import RecordingTransport


def test_records_request_and_sends_nothing():
    transport = RecordingTransport()
    session = requests.Session()
    transport.install(session)

    resp = session.request(
        "GET", "https://example.test/almaws/v1/foo", params={"q": "x"}
    )

    assert resp.status_code == 200
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call.method == "GET"
    assert call.url.endswith("/almaws/v1/foo")
    assert call.params == {"q": "x"}


def test_canned_response_factory_used():
    transport = RecordingTransport(
        canned_response_factory=lambda req: (200, b"<rows/>", "application/xml")
    )
    session = requests.Session()
    transport.install(session)

    resp = session.request("GET", "https://example.test/x")

    assert resp.content == b"<rows/>"
    assert resp.headers["Content-Type"] == "application/xml"
