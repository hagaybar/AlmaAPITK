"""R10 regression test for issue #179 — structure-driven bib creation.

Issue #179 added a higher-level way to create a bib without hand-building
Alma's non-namespaced MARCXML:

- ``build_alma_bib_xml(spec)`` — pure builder over a native JSON field spec.
- ``create_record_from_fields(spec)`` — builder → ``create_record``.
- ``create_record_from_pymarc(record)`` — optional pymarc adapter → spec →
  builder → ``create_record``; ``pymarc`` is an optional extra imported lazily,
  and calling the adapter without it installed must raise a clear, actionable
  error.

These tests lock in the load-bearing guarantees so the behavior can never
silently regress:

1. Alma non-namespaced ``<bib><record>`` shape (NOT slim-MARCXML namespace).
2. Repeated fields and repeated subfields are preserved in order.
3. Special characters are escaped exactly once (no double-escaping — the whole
   reason the builder bypasses the old ``_sanitize_xml_text`` + ET path).
4. The pymarc adapter raises a clear ImportError when pymarc is missing.
"""
import importlib.util
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from almaapitk.domains.bibs import BibliographicRecords

_HAS_PYMARC = importlib.util.find_spec("pymarc") is not None


def _bibs():
    client = MagicMock()
    return BibliographicRecords(client), client


def test_non_namespaced_shape_and_content_type():
    bibs, client = _bibs()
    spec = {"fields": [{"tag": "245", "ind1": "1", "ind2": "0",
                        "subfields": [["a", "Data Reduction Methods"]]}]}

    bibs.create_record_from_fields(spec)

    body = client.post.call_args.kwargs["data"]
    assert client.post.call_args.kwargs["content_type"] == "application/xml"
    root = ET.fromstring(body)
    assert root.tag == "bib" and root[0].tag == "record"
    assert "{" not in body  # no XML namespace ever


def test_repeated_fields_and_subfields_preserved():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [
            {"tag": "650", "ind2": "0", "subfields": [["a", "Data reduction"]]},
            {"tag": "650", "ind2": "0", "subfields": [["a", "Data science"]]},
        ],
    })
    values = [sf.text for df in ET.fromstring(xml).findall(".//datafield[@tag='650']")
              for sf in df.findall("subfield")]
    assert values == ["Data reduction", "Data science"]


def test_no_double_escaping():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "245", "subfields": [["a", "R&D <notes>"]]}],
    })
    assert "&amp;amp;" not in xml and "&amp;lt;" not in xml
    assert ET.fromstring(xml).find(".//subfield").text == "R&D <notes>"


@pytest.mark.skipif(_HAS_PYMARC, reason="pymarc installed; guard path not exercised")
def test_pymarc_adapter_raises_clear_error_when_missing():
    bibs, _ = _bibs()
    with pytest.raises(ImportError) as exc:
        bibs.create_record_from_pymarc(object())
    msg = str(exc.value).lower()
    assert "pymarc" in msg
    assert "almaapitk[pymarc]" in str(exc.value)


@pytest.mark.skipif(not _HAS_PYMARC, reason="pymarc not installed")
def test_pymarc_adapter_builds_and_posts_when_available():
    import pymarc

    bibs, client = _bibs()
    record = pymarc.Record()
    record.add_field(pymarc.Field(tag="008", data="230101s2023    xxu"))
    record.add_field(pymarc.Field(
        tag="245", indicators=["1", "0"],
        subfields=[pymarc.Subfield(code="a", value="A title /")],
    ))

    bibs.create_record_from_pymarc(record)

    body = client.post.call_args.kwargs["data"]
    assert client.post.call_args.kwargs["content_type"] == "application/xml"
    root = ET.fromstring(body)
    assert root.find("./record/controlfield[@tag='008']").text.startswith("230101")
    two45 = root.find("./record/datafield[@tag='245']")
    assert two45.get("ind1") == "1" and two45.get("ind2") == "0"
    assert two45.find("subfield[@code='a']").text == "A title /"
