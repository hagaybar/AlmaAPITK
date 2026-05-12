"""R10 regression test for issue #114.

Before commit 2d20ab3 (``fix(configuration): send XML body for
update_letter``), ``Configuration.update_letter`` passed the caller's
dict to ``self.client.put`` as a JSON body. Alma's letters PUT
endpoint rejects JSON with error code ``60105 "JSON is not supported
for this API."`` — letters require an XML payload (the swagger note on
``PUT /conf/letters/{code}`` is ``"Note: JSON is not supported"``).

This test pins the wire-shape symptom: the request MUST carry an XML
body with ``Content-Type: application/xml``. The assertions are
intentionally tight so that any regression back to a JSON body
(e.g. ``data=letter_data`` without serialisation, or
``json=letter_data``) fails this test loudly.

This file is the migrated home for the test originally added in
commit ``cb9cbc0`` under
``tests/unit/domains/test_configuration.py::TestUpdateLetter::test_update_letter_sends_xml_body_regression_114``;
it now lives here per CLAUDE.md hard rule R10 (canonical home
``tests/unit/regressions/test_issue_<N>.py``).

Pattern source: ``tests/unit/domains/test_configuration.py`` —
identical ``MockAlmaAPIClient`` / ``MockAlmaResponse`` wiring,
trimmed to the surface this single test needs.
"""

import json as _json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock


class MockAlmaResponse:
    """Lightweight stand-in for ``almaapitk.AlmaResponse``.

    Mirrors the shape used in
    ``tests/unit/domains/test_configuration.py`` — only the bits this
    test needs (``status_code``, ``success``, ``data``, ``json()``).
    """

    def __init__(
        self,
        body: Optional[Dict[str, Any]] = None,
        status_code: int = 200,
        success: bool = True,
    ):
        self._body = body if body is not None else {}
        self.status_code = status_code
        self.success = success

    def json(self) -> Dict[str, Any]:
        return self._body

    @property
    def data(self) -> Dict[str, Any]:
        return self._body


class MockAlmaAPIClient:
    """Mock ``AlmaAPIClient`` recording PUT calls for assertion.

    Only the ``put`` verb (and the ``environment`` / ``logger`` /
    ``test_connection`` surface the Configuration constructor touches)
    is implemented — this test only needs to inspect a single PUT.
    """

    def __init__(self, environment: str = "SANDBOX") -> None:
        self.environment = environment
        self.logger = MagicMock()
        self.put_response: MockAlmaResponse = MockAlmaResponse()
        self.calls: Dict[str, list] = {"put": []}

    def get_environment(self) -> str:
        return self.environment

    def test_connection(self) -> bool:
        return True

    def put(
        self,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        self.calls["put"].append(
            {
                "endpoint": endpoint,
                "data": data,
                "params": params,
                "content_type": content_type,
                "custom_headers": custom_headers,
            }
        )
        return self.put_response


def _valid_payload() -> Dict[str, Any]:
    # PUT replaces the entire letter — payload mirrors what
    # ``get_letter`` returns, including subject + XSL body.
    return {
        "code": "OverdueAndLostLoanLetter",
        "letter_name": "Overdue and Lost Loan Letter",
        "description": "Sent on overdue / lost loans.",
        "enabled": {"value": "true"},
        "subject": "Your loan is overdue",
        "body": "<xsl:stylesheet>...</xsl:stylesheet>",
        "letter_template_xsl": "<xsl:stylesheet>...</xsl:stylesheet>",
    }


def test_update_letter_sends_xml_body_regression_114() -> None:
    """R10 regression for issue #114.

    Asserts that ``Configuration.update_letter`` serialises its payload
    to XML and sends ``Content-Type: application/xml``. Any regression
    that flips back to a JSON body trips one of the pins below.
    """
    from almaapitk.domains.configuration import Configuration

    mock_client = MockAlmaAPIClient()
    mock_client.put_response = MockAlmaResponse(
        body={"code": "OverdueAndLostLoanLetter"}
    )
    config = Configuration(mock_client)

    payload = _valid_payload()
    config.update_letter("OverdueAndLostLoanLetter", payload)

    # Exactly one PUT was issued.
    assert len(mock_client.calls["put"]) == 1
    call = mock_client.calls["put"][0]

    # --- Content-Type pin -------------------------------------
    # Must be application/xml. Any regression to the project-wide
    # JSON default (None, "application/json", or unset) fails here.
    assert call["content_type"] == "application/xml", (
        "update_letter must send Content-Type: application/xml — "
        "Alma error 60105 'JSON is not supported for this API.' "
        "regresses if this flips back to JSON (issue #114)."
    )

    # --- Body shape pin ---------------------------------------
    body = call["data"]
    # The body must be a string (the serialised XML), NOT the raw
    # dict that the caller passed in. A regression like
    # ``self.client.put(..., data=letter_data)`` would leave a dict
    # here.
    assert isinstance(body, str), (
        f"update_letter must serialise the payload to a string; "
        f"got {type(body).__name__}. A regression that passes the "
        f"caller's dict straight through (issue #114) trips here."
    )

    # The body must NOT be a JSON-encoded string. ``json.dumps`` of
    # a dict starts with ``{`` — any string that round-trips through
    # ``json.loads`` to the original dict is the regressed shape.
    assert not body.lstrip().startswith("{"), (
        "update_letter body looks like JSON, not XML — issue #114 "
        "regression (Alma error 60105 'JSON is not supported')."
    )
    try:
        decoded = _json.loads(body)
    except (ValueError, TypeError):
        decoded = None
    assert decoded != payload, (
        "update_letter body is JSON-encoded form of the caller's "
        "dict — issue #114 regression."
    )

    # --- XML structural pin -----------------------------------
    # The body must look like XML and must carry the letter code so
    # the Alma backend can identify the target.
    assert body.startswith("<"), (
        "update_letter body must be XML and start with '<'."
    )
    assert "<letter>" in body and "</letter>" in body, (
        "update_letter body must wrap the payload in a <letter> "
        "element."
    )
    assert "<code>OverdueAndLostLoanLetter</code>" in body, (
        "update_letter body must carry the letter code as XML."
    )
