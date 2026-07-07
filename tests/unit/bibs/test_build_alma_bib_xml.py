"""Unit tests for the pure MARCXML builder + structure-driven bib creation.

Covers ``BibliographicRecords.build_alma_bib_xml`` (issue #179) and the two
create helpers that funnel into ``create_record``. The builder is pure (no
network), so it is exercised directly; the create helpers use a mocked client.
"""
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.bibs import DEFAULT_BIB_LEADER, BibliographicRecords


def _bibs():
    client = MagicMock()
    return BibliographicRecords(client), client


# --------------------------------------------------------------------------- #
# build_alma_bib_xml
# --------------------------------------------------------------------------- #

def test_non_namespaced_bib_record_shape():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "245", "ind1": "1", "ind2": "0",
                    "subfields": [["a", "A title"]]}],
    })
    root = ET.fromstring(xml)
    assert root.tag == "bib"                       # NOT slim-MARCXML namespace
    assert root[0].tag == "record"
    assert "{" not in xml                          # no namespace braces anywhere


def test_default_leader_used_when_omitted():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "245", "subfields": [["a", "x"]]}],
    })
    root = ET.fromstring(xml)
    assert root.find("./record/leader").text == DEFAULT_BIB_LEADER


def test_explicit_leader_preserved():
    leader = "01234nam a2200000 a 4500"
    xml = BibliographicRecords.build_alma_bib_xml({
        "leader": leader,
        "fields": [{"tag": "245", "subfields": [["a", "x"]]}],
    })
    assert ET.fromstring(xml).find("./record/leader").text == leader


def test_control_field_uses_data_not_subfields():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "008", "data": "230101s2023    xxu"}],
    })
    root = ET.fromstring(xml)
    cf = root.find("./record/controlfield")
    assert cf is not None
    assert cf.get("tag") == "008"
    assert cf.text == "230101s2023    xxu"
    assert root.find("./record/datafield") is None


def test_indicators_including_blank():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "650", "ind1": " ", "ind2": "0",
                    "subfields": [["a", "Data reduction"]]}],
    })
    df = ET.fromstring(xml).find("./record/datafield")
    assert df.get("ind1") == " "
    assert df.get("ind2") == "0"


def test_indicators_default_to_blank():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "245", "subfields": [["a", "x"]]}],
    })
    df = ET.fromstring(xml).find("./record/datafield")
    assert df.get("ind1") == " "
    assert df.get("ind2") == " "


def test_repeated_fields_and_repeated_subfields_preserved():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [
            {"tag": "650", "ind1": " ", "ind2": "0", "subfields": [["a", "Data reduction"]]},
            {"tag": "650", "ind1": " ", "ind2": "0", "subfields": [["a", "Data science"]]},
            {"tag": "245", "ind1": "1", "ind2": "0",
             "subfields": [["a", "Main /"], ["b", "sub"], ["a", "again"]]},
        ],
    })
    root = ET.fromstring(xml)
    sixfifties = root.findall("./record/datafield[@tag='650']")
    assert [sf.text for df in sixfifties for sf in df.findall("subfield")] == [
        "Data reduction", "Data science",
    ]
    two_four_five = root.find("./record/datafield[@tag='245']")
    assert [(sf.get("code"), sf.text) for sf in two_four_five.findall("subfield")] == [
        ("a", "Main /"), ("b", "sub"), ("a", "again"),
    ]


def test_field_order_preserved():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [
            {"tag": "008", "data": "d"},
            {"tag": "245", "subfields": [["a", "t"]]},
            {"tag": "100", "subfields": [["a", "author"]]},
        ],
    })
    root = ET.fromstring(xml)
    tags = [el.get("tag") for el in root.find("record") if el.tag != "leader"]
    assert tags == ["008", "245", "100"]


def test_special_chars_escaped_exactly_once():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "245", "subfields": [["a", "Cats & Dogs <or> \"pets\""]]}],
    })
    # Raw serialization must contain single-escaped entities, never double.
    assert "&amp;" in xml and "&amp;amp;" not in xml
    assert "&lt;" in xml and "&amp;lt;" not in xml
    # Round-trips back to the exact original text.
    sf = ET.fromstring(xml).find(".//subfield")
    assert sf.text == 'Cats & Dogs <or> "pets"'


def test_illegal_control_chars_stripped():
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "245", "subfields": [["a", "bad\x00\x07text\tok"]]}],
    })
    sf = ET.fromstring(xml).find(".//subfield")
    assert sf.text == "badtext\tok"


def test_explicit_subfields_on_00x_tag_forces_datafield():
    # An 00X tag with subfields is treated as a data field (edge-case override).
    xml = BibliographicRecords.build_alma_bib_xml({
        "fields": [{"tag": "007", "subfields": [["a", "cr"]]}],
    })
    root = ET.fromstring(xml)
    assert root.find("./record/datafield[@tag='007']") is not None


@pytest.mark.parametrize("spec", [
    None,
    "nope",
    {},
    {"fields": []},
    {"fields": "nope"},
    {"fields": [{"data": "no tag"}]},
    {"fields": [{"tag": "245", "subfields": [["a"]]}]},        # bad pair
    {"fields": [{"tag": "245", "subfields": "nope"}]},
    {"leader": 123, "fields": [{"tag": "245", "subfields": [["a", "x"]]}]},
])
def test_invalid_spec_raises(spec):
    with pytest.raises(AlmaValidationError):
        BibliographicRecords.build_alma_bib_xml(spec)


# --------------------------------------------------------------------------- #
# create_record_from_fields
# --------------------------------------------------------------------------- #

def test_create_record_from_fields_posts_xml():
    bibs, client = _bibs()
    spec = {"fields": [{"tag": "245", "ind1": "1", "ind2": "0",
                        "subfields": [["a", "Data Reduction Methods"]]}]}

    bibs.create_record_from_fields(spec)

    kwargs = client.post.call_args.kwargs
    assert kwargs.get("content_type") == "application/xml"
    body = kwargs["data"]
    assert body.startswith("<bib><record>")
    assert "Data Reduction Methods" in body


def test_create_record_from_fields_passes_flags():
    bibs, client = _bibs()
    spec = {"fields": [{"tag": "245", "subfields": [["a", "x"]]}]}

    bibs.create_record_from_fields(spec, validate=False, override_warning=True)

    params = client.post.call_args.kwargs["params"]
    assert params["validate"] == "false"
    assert params["override_warning"] == "true"
