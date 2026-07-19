"""R10 regression test for issue #179 — structure-driven bib creation.

``build_alma_bib_xml`` replaced the hand-rolled ``_sanitize_xml_text`` + ET
path, whose bug was **double-escaping**: it turned ``&`` into ``&amp;`` in the
text *and then* let ElementTree escape the ``&`` again, yielding
``&amp;amp;``. The builder must instead assign raw values to ``.text`` and let
ElementTree escape exactly once, while still emitting Alma's non-namespaced
``<bib><record>`` shape and preserving repeated fields/subfields.

These tests pin that behaviour so it can never silently regress:

- ``&`` and ``<`` are escaped exactly once (round-trip back to the literal).
- Output is the non-namespaced ``<bib><record>`` shape (no ``xmlns``).
- Repeated fields (two ``650``) and repeated subfields are preserved in order.
- ``create_record_from_fields`` funnels the built XML into ``create_record``,
  POSTing ``almaws/v1/bibs`` with ``content_type=application/xml``.
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from almaapitk import AlmaValidationError, build_alma_bib_xml
from almaapitk.domains.bibs import BibliographicRecords


def test_ampersand_is_not_double_escaped():
    """The original bug: ``&`` serialised as ``&amp;amp;``."""
    xml = build_alma_bib_xml(
        {"fields": [{"tag": "245", "subfields": [["a", "R & D"]]}]}
    )

    assert "&amp;amp;" not in xml
    assert xml.count("&amp;") == 1
    # Round-trips back to the exact literal — proof of single escaping.
    value = ET.fromstring(xml).find("record").find("datafield").find(
        "subfield"
    ).text
    assert value == "R & D"


def test_angle_bracket_is_not_double_escaped():
    xml = build_alma_bib_xml(
        {"fields": [{"tag": "520", "subfields": [["a", "x < y"]]}]}
    )

    assert "&lt;lt;" not in xml
    value = ET.fromstring(xml).find("record").find("datafield").find(
        "subfield"
    ).text
    assert value == "x < y"


def test_non_namespaced_bib_record_shape():
    xml = build_alma_bib_xml(
        {"fields": [{"tag": "245", "subfields": [["a", "Title"]]}]}
    )
    root = ET.fromstring(xml)

    assert root.tag == "bib"  # not the pymarc slim-MARCXML namespace
    assert "xmlns" not in xml
    assert root.find("record") is not None


def test_repeated_fields_and_subfields_preserved():
    spec = {
        "fields": [
            {"tag": "650", "ind1": " ", "ind2": "0",
             "subfields": [["a", "Data reduction"], ["x", "Methods"]]},
            {"tag": "650", "ind1": " ", "ind2": "0",
             "subfields": [["a", "Data science"]]},
        ]
    }

    record = ET.fromstring(build_alma_bib_xml(spec)).find("record")
    datafields = record.findall("datafield")

    assert [df.get("tag") for df in datafields] == ["650", "650"]
    first = [(sf.get("code"), sf.text) for sf in datafields[0].findall("subfield")]
    assert first == [("a", "Data reduction"), ("x", "Methods")]
    assert datafields[1].find("subfield").text == "Data science"


class _RecordingClient:
    """Minimal client that records the POST it receives."""

    def __init__(self) -> None:
        self.logger = MagicMock()
        self.environment = "SANDBOX"
        self.last_post: Optional[Dict[str, Any]] = None

    def get_environment(self) -> str:
        return self.environment

    def post(self, endpoint, data=None, params=None, content_type=None,
             custom_headers=None):
        self.last_post = {
            "endpoint": endpoint,
            "data": data,
            "params": params,
            "content_type": content_type,
        }
        return MagicMock(success=True)


def test_create_record_from_fields_funnels_into_create_record_as_xml():
    client = _RecordingClient()
    bibs = BibliographicRecords(client)

    bibs.create_record_from_fields(
        {"fields": [{"tag": "245", "ind1": "1", "ind2": "0",
                     "subfields": [["a", "Data Reduction Methods"]]}]}
    )

    assert client.last_post is not None
    assert client.last_post["endpoint"] == "almaws/v1/bibs"
    assert client.last_post["content_type"] == "application/xml"
    assert "Data Reduction Methods" in client.last_post["data"]


def test_malformed_spec_raises_validation_error():
    with pytest.raises(AlmaValidationError):
        build_alma_bib_xml({"fields": [{"tag": "245"}]})
