"""Alma Lab result normalisation and path resolution (issue #230)."""
import datetime

import pytest

from almaapitk.lab.normalize import normalize_result, resolve, xml_to_tree

MARC = (
    "<bib><mms_id>990000000000001</mms_id><record>"
    '<controlfield tag="001">990000000000001</controlfield>'
    '<datafield tag="245" ind1="1" ind2="0"><subfield code="a">Sample title</subfield></datafield>'
    '<datafield tag="505" ind1="0" ind2="0"><subfield code="a">Part one -- Part two</subfield></datafield>'
    "</record></bib>"
)


def test_marc_path_filter():
    tree = xml_to_tree(MARC)
    assert resolve(tree, "bib.record.datafield[tag=505].subfield[code=a]") == "Part one -- Part two"
    assert resolve(tree, "record.datafield[tag=245].subfield[code=a]") == "Sample title"


def test_xml_inside_json_is_parsed_lazily():
    data = {"mms_id": "990000000000001", "anies": [MARC]}
    assert resolve(data, "anies[0].record.datafield[tag=505].subfield[code=a]") == "Part one -- Part two"


def test_nested_payment_path():
    data = {"payment": {"payment_status": {"value": "PAID", "desc": "Paid"}}, "invoice_lines": [{"id": "1"}, {"id": "2"}]}
    assert resolve(data, "payment.payment_status.value") == "PAID"
    assert resolve(data, "invoice_lines[1].id") == "2"
    assert resolve(data, "invoice_lines[id=2].id") == "2"


def test_missing_segment_names_it():
    with pytest.raises(KeyError, match="payment_status"):
        resolve({"payment": {}}, "payment.payment_status.value")


def test_generator_is_capped():
    data, capped = normalize_result((i for i in range(5000)), cap=1000)
    assert len(data) == 1000 and capped is True
    data, capped = normalize_result(iter(range(3)), cap=1000)
    assert data == [0, 1, 2] and capped is False


def test_alma_response_becomes_its_json(lab_client):
    lab_client.http.answers = [{"body": {"title": "Sample title"}}]
    data, capped = normalize_result(lab_client.get("almaws/v1/bibs/1"))
    assert data == {"title": "Sample title"} and capped is False


def test_unserialisable_values_become_text():
    data, _ = normalize_result({"when": datetime.date(2026, 11, 10), "obj": object()})
    assert data["when"] == "2026-11-10"
    assert data["obj"].startswith("<object object")
