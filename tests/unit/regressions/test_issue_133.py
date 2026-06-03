"""R10 regression test: issue #133 / finding F-003.

`Acquisitions.receive_item` posts to the receive endpoint and then tries to
parse the response as JSON, falling back to XML parsing when Alma returns an
XML body. The original code used a **bare** ``except:`` around the
``response.json()`` call, which swallowed *everything* — including
``KeyboardInterrupt`` / ``SystemExit`` and any unexpected programming error —
and silently dropped into the XML path, masking real failures.

The fix narrowed it to ``except ValueError:`` (``requests``' JSON decode error
is a ``ValueError`` subclass). This test pins both halves of the contract:

1. A non-JSON (XML) success body still falls back to XML parsing and returns a
   dict (the documented behaviour for this endpoint).
2. A non-``ValueError`` raised while reading the body **propagates** instead of
   being swallowed by the fallback — if anyone widens the ``except`` back to a
   bare clause, this goes red.

Runs with no creds and no network via the dry-run smoke harness. R9: all
identifiers are synthetic placeholders.
"""
from __future__ import annotations

import pytest

from almaapitk import Acquisitions
from almaapitk.client.AlmaAPIClient import AlmaResponse
from almaapitk.testing import build_smoke_client

_POL_ID = "POL-CONTRACT-0001"
_ITEM_ID = "23000000000000000000"


def _acq_for(status: int, body: bytes, content_type: str):
    """Real AlmaAPIClient + Acquisitions wired to return one canned response
    (SANDBOX, writable so the receive POST is allowed; dry-run records it)."""
    client, _ = build_smoke_client(
        environment="SANDBOX",
        readonly=False,
        dry_run=True,
        api_key="contract-test",
        canned_response_factory=lambda req: (status, body, content_type),
    )
    return Acquisitions(client), client


def test_receive_item_falls_back_to_xml_when_body_is_not_json():
    # Alma returns XML for this endpoint; response.json() raises ValueError,
    # and the method must fall back to XML parsing and return a dict.
    xml_body = (
        b"<item><item_id>23000000000000000000</item_id>"
        b"<status>received</status></item>"
    )
    acq, client = _acq_for(200, xml_body, "application/xml")
    try:
        result = acq.receive_item(_POL_ID, _ITEM_ID)
    finally:
        client.close()
    assert isinstance(result, dict)
    assert result["item_id"] == _ITEM_ID
    assert result["status"] == "received"


def test_receive_item_does_not_swallow_non_valueerror(monkeypatch):
    # The F-003 guard: a non-ValueError raised while parsing the body must
    # propagate. Under the old bare `except:` it was swallowed and the code
    # silently fell into XML parsing of an empty <item/> (returning {}).
    acq, client = _acq_for(200, b"<item/>", "application/xml")

    sentinel = RuntimeError("body read blew up — must not be swallowed")

    def _boom(self):
        raise sentinel

    # Patch the JSON accessor the fallback guards; only receive_item's parse
    # path calls it on this 200 response. (Object form, not the dotted-string
    # form — AlmaResponse is a class, not a module.)
    monkeypatch.setattr(AlmaResponse, "json", _boom)
    try:
        with pytest.raises(RuntimeError, match="must not be swallowed"):
            acq.receive_item(_POL_ID, _ITEM_ID)
    finally:
        client.close()
