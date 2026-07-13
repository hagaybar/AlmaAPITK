"""R10 regression test for issue #185 — repeated MARC subfield codes lost.

Bug: the editing path (``BibliographicRecords._add_datafield``, reached via
``update_marc_field``) typed ``subfields`` as ``Dict[str, str]`` and iterated
``.items()``. A ``dict`` cannot hold two entries with the same key, so a
repeated subfield code was impossible to represent — the second value silently
overwrote the first at dict-construction time. That is silent data loss: valid
MARC could never round-trip.

MARC rule: subfield codes repeat routinely and legitimately, e.g.
``650 _0 $a Science $x History $x 20th century`` (two ``$x``) and
``700 ... $e author $e editor`` (two ``$e``). Every subfield may repeat unless
R/NR precludes it.

Fix (#185): the editing path accepts an ordered list of ``[code, value]`` pairs
(mirroring the creation builder ``build_alma_bib_xml``), preserving order AND
repetition. A ``dict`` is still accepted for the non-repeating,
backward-compatible case.

These tests pin the *symptom*: the captured PUT body must carry every subfield —
including the repeated codes — in order. They fail against the pre-fix code
(a list is not a dict → ``AttributeError`` on ``.items()``; and a dict cannot
express a repeat) and pass once ordered pairs are supported.

Pattern source: ``tests/unit/regressions/test_issue_184.py`` — same
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


# A record shaped like Alma's ``anies[0]``: a bare <record> with a 650 and a
# 700, each carrying a single subfield we will re-write with repeated codes.
_BASE_MARC = (
    "<record>"
    "<leader>00000nam a2200000 a 4500</leader>"
    '<controlfield tag="001">99123456789</controlfield>'
    '<datafield tag="245" ind1="1" ind2="0">'
    '<subfield code="a">A test title</subfield>'
    "</datafield>"
    '<datafield tag="650" ind1=" " ind2="0">'
    '<subfield code="a">Science</subfield>'
    "</datafield>"
    '<datafield tag="700" ind1="1" ind2=" ">'
    '<subfield code="a">Smith, John</subfield>'
    "</datafield>"
    "</record>"
)


def _make_bib(marc_xml: str) -> Dict[str, Any]:
    """Return a minimal bib-record dict with the MARC XML in ``anies``."""
    return {"mms_id": "99123456789", "anies": [marc_xml]}


def _captured_put_record(client: MockAlmaAPIClient) -> ET.Element:
    """Parse the MARC XML that was PUT back to Alma and return <record>."""
    assert len(client.calls["put"]) == 1, "expected exactly one PUT call"
    put_body = client.calls["put"][0]["data"]
    assert isinstance(put_body, str), "PUT body must be the MARC XML string"
    root = ET.fromstring(put_body)
    # update_record wraps the record as <bib><record>...</record></bib>.
    record = root.find("record") if root.tag == "bib" else root
    assert record is not None, "PUT body must contain a <record> element"
    return record


def _ordered_subfields(record: ET.Element, tag: str) -> List[Tuple[str, str]]:
    """All ``(code, value)`` subfield pairs for a tag, in document order.

    Returns pairs across every occurrence of ``tag`` (there is one in these
    fixtures) so a repeated code shows up as multiple entries.
    """
    pairs: List[Tuple[str, str]] = []
    for df in record.findall(f"datafield[@tag='{tag}']"):
        for sf in df.findall("subfield"):
            pairs.append((sf.get("code"), sf.text))
    return pairs


def test_repeated_x_subfields_survive_regression_185() -> None:
    """R10: two ``$x`` on a 650 must both round-trip, in order.

    ``650 _0 $a Science $x History $x 20th century`` is valid MARC (``$x`` is
    Repeatable). Pre-fix, the dict-typed path could not even accept this shape —
    the second ``$x`` was impossible to express, so one heading was silently
    lost.
    """
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field(
        "99123456789",
        "650",
        [["a", "Science"], ["x", "History"], ["x", "20th century"]],
    )

    record = _captured_put_record(client)
    pairs = _ordered_subfields(record, "650")

    assert pairs == [
        ("a", "Science"),
        ("x", "History"),
        ("x", "20th century"),
    ], f"repeated $x subfields must round-trip in order, got {pairs!r}"

    # Explicitly assert BOTH repeated codes survived (the core of the bug).
    x_values = [value for code, value in pairs if code == "x"]
    assert x_values == ["History", "20th century"], (
        f"expected two distinct $x values, got {x_values!r}"
    )


def test_repeated_relator_e_subfields_on_700_regression_185() -> None:
    """R10: a 700 with two ``$e`` (author, editor) must keep both."""
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field(
        "99123456789",
        "700",
        [["a", "Smith, John"], ["e", "author"], ["e", "editor"]],
        ind1="1",
        ind2=" ",
    )

    record = _captured_put_record(client)
    pairs = _ordered_subfields(record, "700")

    assert pairs == [
        ("a", "Smith, John"),
        ("e", "author"),
        ("e", "editor"),
    ], f"repeated $e relator subfields must round-trip, got {pairs!r}"


def test_dict_subfields_still_accepted_regression_185() -> None:
    """Backward compatibility: a ``dict`` (non-repeating) still works.

    Existing callers pass ``{"a": "..."}``; that shape must keep working and
    preserve insertion order.
    """
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field(
        "99123456789", "650", {"a": "Physics", "x": "History"}
    )

    record = _captured_put_record(client)
    pairs = _ordered_subfields(record, "650")

    assert pairs == [("a", "Physics"), ("x", "History")], (
        f"dict subfields must still round-trip in insertion order, got {pairs!r}"
    )


def test_pair_order_is_preserved_regression_185() -> None:
    """Ordered pairs must be emitted in the given order (order is significant)."""
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field(
        "99123456789",
        "650",
        [["a", "Science"], ["x", "History"], ["x", "20th century"], ["z", "USA"]],
    )

    record = _captured_put_record(client)
    codes = [code for code, _ in _ordered_subfields(record, "650")]
    assert codes == ["a", "x", "x", "z"], f"subfield order lost, got {codes!r}"


def test_malformed_pair_raises_validation_error_regression_185() -> None:
    """A pair that is not exactly ``[code, value]`` must fail fast, no PUT."""
    from almaapitk.client.AlmaAPIClient import AlmaValidationError
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_BASE_MARC))
    bibs = BibliographicRecords(client)

    with pytest.raises(AlmaValidationError):
        bibs.update_marc_field(
            "99123456789",
            "650",
            [["a", "Science"], ["x"]],  # second pair is malformed
        )
    assert client.calls["put"] == [], "no PUT should occur on invalid subfields"
