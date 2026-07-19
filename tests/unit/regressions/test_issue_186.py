"""R10 regression test for issue #186 — double-escaping of XML special chars.

Bug: ``BibliographicRecords._sanitize_xml_text`` (reached via
``update_marc_field`` -> ``_build_updated_marc_xml`` -> ``_add_datafield``)
manually rewrote ``&`` -> ``&amp;``, ``<`` -> ``&lt;``, ``>`` -> ``&gt;``
(and ``"`` / ``'``) **and then** assigned the result to an ElementTree
``.text``. ``ET.tostring`` escapes ``.text`` a *second* time, so every special
character was escaped twice: updating a 245 to ``Law & order`` stored
``Law &amp; order`` in Alma — the literal ampersand was mangled (same for
``<`` / ``>``).

Root cause: the creation path (issue #179) already fixed this by stripping only
illegal XML control characters and letting ElementTree escape exactly once —
never pre-escaping. That fix was never applied to this *editing* path.

These tests pin the *symptom*: a value round-tripped through
``update_marc_field`` must come back as the exact literal, and the captured PUT
body must contain a single level of escaping (``&amp;`` but NOT ``&amp;amp;``).
They fail against the pre-fix code (double escaping) and pass once the manual
replacement is removed and only illegal control chars are stripped.

Pattern source: ``tests/unit/regressions/test_issue_185.py`` — same
``MockAlmaAPIClient`` / ``MockAlmaResponse`` shape (mocked ``get`` + ``put``).
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest


class MockAlmaResponse:
    """Minimal stand-in for ``almaapitk.AlmaResponse``."""

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
    """Mock ``AlmaAPIClient`` recording GET + PUT calls for assertion."""

    def __init__(self, environment: str = "SANDBOX") -> None:
        self.environment = environment
        self.logger = MagicMock()
        self.get_response: MockAlmaResponse = MockAlmaResponse()
        self.put_response: MockAlmaResponse = MockAlmaResponse()
        self.calls: Dict[str, list] = {"get": [], "put": []}

    def get_environment(self) -> str:
        return self.environment

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> MockAlmaResponse:
        self.calls["get"].append({"endpoint": endpoint, "params": params})
        return self.get_response

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


# A record shaped like Alma's ``anies[0]``: a bare <record> with a single 245.
_BASE_MARC = (
    "<record>"
    "<leader>00000nam a2200000 a 4500</leader>"
    '<controlfield tag="001">99123456789</controlfield>'
    '<datafield tag="245" ind1="1" ind2="0">'
    '<subfield code="a">Original title</subfield>'
    "</datafield>"
    "</record>"
)


def _make_bib(marc_xml: str) -> Dict[str, Any]:
    """Return a minimal bib-record dict with the MARC XML in ``anies``."""
    return {"mms_id": "99123456789", "anies": [marc_xml]}


def _captured_put_body(client: MockAlmaAPIClient) -> str:
    """Return the raw MARC XML string that was PUT back to Alma."""
    assert len(client.calls["put"]) == 1, "expected exactly one PUT call"
    put_body = client.calls["put"][0]["data"]
    assert isinstance(put_body, str), "PUT body must be the MARC XML string"
    return put_body


def _captured_put_record(client: MockAlmaAPIClient) -> ET.Element:
    """Parse the MARC XML that was PUT back to Alma and return <record>."""
    root = ET.fromstring(_captured_put_body(client))
    # update_record wraps the record as <bib><record>...</record></bib>.
    record = root.find("record") if root.tag == "bib" else root
    assert record is not None, "PUT body must contain a <record> element"
    return record


def _ordered_subfields(record: ET.Element, tag: str) -> List[Tuple[str, str]]:
    """All ``(code, value)`` subfield pairs for a tag, in document order."""
    pairs: List[Tuple[str, str]] = []
    for df in record.findall(f"datafield[@tag='{tag}']"):
        for sf in df.findall("subfield"):
            pairs.append((sf.get("code"), sf.text))
    return pairs


def test_ampersand_round_trips_unmangled_regression_186() -> None:
    """R10: ``Law & order`` must round-trip as ``Law & order`` (issue #186).

    Pre-fix, the ampersand was escaped manually to ``&amp;`` and then a second
    time by ElementTree, so Alma stored ``Law &amp; order`` — mangled content.
    """
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field("99123456789", "245", [["a", "Law & order"]],
                           ind1="1", ind2="0")

    # The re-parsed subfield text must be the exact literal we sent.
    record = _captured_put_record(client)
    pairs = _ordered_subfields(record, "245")
    assert pairs == [("a", "Law & order")], (
        f"245 $a must round-trip unmangled, got {pairs!r}"
    )

    # And the raw XML must carry a SINGLE level of escaping.
    put_body = _captured_put_body(client)
    assert "Law &amp; order" in put_body, (
        f"ampersand must be escaped exactly once, raw body: {put_body!r}"
    )
    assert "&amp;amp;" not in put_body, (
        f"double-escaping detected in raw PUT body: {put_body!r}"
    )


def test_angle_brackets_round_trip_unmangled_regression_186() -> None:
    """R10: ``<`` and ``>`` must round-trip literally, escaped exactly once."""
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    value = "a < b > c & d"
    bibs.update_marc_field("99123456789", "245", [["a", value]],
                           ind1="1", ind2="0")

    record = _captured_put_record(client)
    pairs = _ordered_subfields(record, "245")
    assert pairs == [("a", value)], (
        f"245 $a with </>/& must round-trip unmangled, got {pairs!r}"
    )

    put_body = _captured_put_body(client)
    # Single-level escaping only — no doubly-escaped entities.
    assert "&amp;amp;" not in put_body
    assert "&amp;lt;" not in put_body
    assert "&amp;gt;" not in put_body


def test_illegal_control_chars_stripped_regression_186() -> None:
    """R10: illegal C0 control chars are dropped; tab/newline/CR survive.

    The replacement for the manual-escaping helper must still strip characters
    that XML 1.0 forbids (otherwise ``ET.tostring`` would raise on e.g. a NUL),
    while leaving the whitelisted whitespace intact.
    """
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    # NUL and BELL are illegal in XML 1.0; the tab must be kept.
    bibs.update_marc_field(
        "99123456789", "245", [["a", "clean\x00up\x07\ttext"]],
        ind1="1", ind2="0",
    )

    record = _captured_put_record(client)
    pairs = _ordered_subfields(record, "245")
    assert pairs == [("a", "cleanup\ttext")], (
        f"illegal control chars must be stripped, tab kept, got {pairs!r}"
    )


def test_apostrophe_and_quote_not_pre_escaped_regression_186() -> None:
    """R10: ``'`` / ``"`` in text round-trip literally (no manual pre-escape).

    ElementTree does not escape quotes in element *text* (only in attribute
    values), so pre-escaping them produced literal ``&apos;`` / ``&quot;`` in
    the stored value. They must survive as plain characters.
    """
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    value = "O'Brien's \"quoted\" title"
    bibs.update_marc_field("99123456789", "245", [["a", value]],
                           ind1="1", ind2="0")

    record = _captured_put_record(client)
    pairs = _ordered_subfields(record, "245")
    assert pairs == [("a", value)], (
        f"quotes/apostrophes must round-trip literally, got {pairs!r}"
    )

    put_body = _captured_put_body(client)
    assert "&apos;" not in put_body, f"apostrophe pre-escaped: {put_body!r}"
    assert "&quot;" not in put_body, f"quote pre-escaped: {put_body!r}"
