"""Unit tests for the structure-driven bib creation API (issue #179).

Covers:

- ``build_alma_bib_xml`` — the pure, network-free MARCXML builder: repeated
  fields, repeated subfields, control fields, indicators (including blank),
  exactly-once escaping of ``&`` / ``<``, and leader present vs defaulted, plus
  malformed-spec validation.
- ``BibliographicRecords.create_record_from_fields`` — funnels through
  ``create_record``; asserts the POST endpoint, body and
  ``content_type=application/xml``.
- ``BibliographicRecords.create_record_from_pymarc`` — the optional pymarc
  adapter; the happy path is skipped when pymarc is absent, and the
  missing-extra error path is exercised when pymarc is not installed.

Pattern source: mirrors the ``MockAlmaAPIClient`` / ``MockAlmaResponse`` style
of ``tests/unit/domains/test_admin.py`` (no real HTTP), extended to also
record the ``content_type`` each verb receives.
"""

import importlib.util
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import pytest

from almaapitk import AlmaValidationError
from almaapitk.domains.bibs import (
    DEFAULT_LEADER,
    BibliographicRecords,
    build_alma_bib_xml,
)


# ---------------------------------------------------------------------------
# Mock scaffolding
# ---------------------------------------------------------------------------


class MockAlmaResponse:
    """Lightweight stand-in for ``almaapitk.AlmaResponse``."""

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
    """Mock AlmaAPIClient that records each POST it receives.

    Records the ``(endpoint, data, params, content_type)`` tuple per POST so
    tests can assert the request body and content type without an HTTP layer.
    """

    def __init__(self, environment: str = "SANDBOX"):
        self.environment = environment
        from unittest.mock import MagicMock

        self.logger = MagicMock()
        self.post_response: MockAlmaResponse = MockAlmaResponse()
        self.calls: Dict[str, list] = {"post": []}

    def get_environment(self) -> str:
        return self.environment

    def post(
        self,
        endpoint: str,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        self.calls["post"].append(
            {
                "endpoint": endpoint,
                "data": data,
                "params": params,
                "content_type": content_type,
            }
        )
        return self.post_response


# ---------------------------------------------------------------------------
# build_alma_bib_xml
# ---------------------------------------------------------------------------


class TestBuildAlmaBibXml:
    """Tests for the pure ``build_alma_bib_xml`` helper."""

    def test_emits_non_namespaced_bib_record_shape(self):
        spec = {"fields": [{"tag": "245", "subfields": [["a", "Title"]]}]}

        xml = build_alma_bib_xml(spec)
        root = ET.fromstring(xml)

        # Alma's non-namespaced shape: <bib><record>...</record></bib>, no xmlns.
        assert root.tag == "bib"
        assert "xmlns" not in xml
        assert "{" not in root.tag  # no namespace braces
        record = root.find("record")
        assert record is not None
        assert record.find("leader") is not None

    def test_repeated_fields_preserved_in_order(self):
        spec = {
            "fields": [
                {"tag": "650", "ind1": " ", "ind2": "0",
                 "subfields": [["a", "Data reduction"]]},
                {"tag": "650", "ind1": " ", "ind2": "0",
                 "subfields": [["a", "Data science"]]},
            ]
        }

        root = ET.fromstring(build_alma_bib_xml(spec))
        record = root.find("record")
        datafields = record.findall("datafield")

        assert [df.get("tag") for df in datafields] == ["650", "650"]
        values = [df.find("subfield").text for df in datafields]
        assert values == ["Data reduction", "Data science"]

    def test_repeated_subfields_within_a_field_preserved(self):
        spec = {
            "fields": [
                {
                    "tag": "650",
                    "ind1": " ",
                    "ind2": "0",
                    "subfields": [["a", "Topic"], ["x", "Sub1"], ["x", "Sub2"]],
                }
            ]
        }

        root = ET.fromstring(build_alma_bib_xml(spec))
        subfields = root.find("record").find("datafield").findall("subfield")

        assert [(sf.get("code"), sf.text) for sf in subfields] == [
            ("a", "Topic"),
            ("x", "Sub1"),
            ("x", "Sub2"),
        ]

    def test_control_field_emits_controlfield_element(self):
        spec = {"fields": [{"tag": "008", "data": "230101s2023    xx"}]}

        root = ET.fromstring(build_alma_bib_xml(spec))
        record = root.find("record")

        controlfield = record.find("controlfield")
        assert controlfield is not None
        assert controlfield.get("tag") == "008"
        assert controlfield.text == "230101s2023    xx"
        # A control field is not rendered as a datafield.
        assert record.find("datafield") is None

    def test_control_field_via_explicit_data_on_non_00x_tag(self):
        # Presence of 'data' makes a field a control field regardless of tag.
        spec = {"fields": [{"tag": "245", "data": "raw"}]}

        root = ET.fromstring(build_alma_bib_xml(spec))
        record = root.find("record")

        assert record.find("controlfield").get("tag") == "245"

    def test_blank_indicators_render_as_spaces(self):
        spec = {"fields": [{"tag": "650", "subfields": [["a", "X"]]}]}

        root = ET.fromstring(build_alma_bib_xml(spec))
        datafield = root.find("record").find("datafield")

        # Omitted indicators default to a single blank space.
        assert datafield.get("ind1") == " "
        assert datafield.get("ind2") == " "

    def test_explicit_indicators_are_preserved(self):
        spec = {
            "fields": [
                {"tag": "245", "ind1": "1", "ind2": "0",
                 "subfields": [["a", "Title"]]}
            ]
        }

        datafield = ET.fromstring(build_alma_bib_xml(spec)).find(
            "record"
        ).find("datafield")

        assert datafield.get("ind1") == "1"
        assert datafield.get("ind2") == "0"

    def test_ampersand_escaped_exactly_once(self):
        spec = {"fields": [{"tag": "245", "subfields": [["a", "Bread & Butter"]]}]}

        xml = build_alma_bib_xml(spec)

        # Escaped once (&amp;), never double-escaped (&amp;amp;).
        assert "&amp;" in xml
        assert "&amp;amp;" not in xml
        # Round-trips back to the original literal value.
        value = ET.fromstring(xml).find("record").find("datafield").find(
            "subfield"
        ).text
        assert value == "Bread & Butter"

    def test_less_than_escaped_exactly_once(self):
        spec = {"fields": [{"tag": "245", "subfields": [["a", "a < b"]]}]}

        xml = build_alma_bib_xml(spec)

        assert "&lt;" in xml
        assert "&lt;lt;" not in xml
        value = ET.fromstring(xml).find("record").find("datafield").find(
            "subfield"
        ).text
        assert value == "a < b"

    def test_leader_present_is_used(self):
        custom_leader = "01234nam a2200000 a 4500"
        spec = {"leader": custom_leader,
                "fields": [{"tag": "245", "subfields": [["a", "X"]]}]}

        leader = ET.fromstring(build_alma_bib_xml(spec)).find("record").find(
            "leader"
        )
        assert leader.text == custom_leader

    def test_leader_defaulted_when_omitted(self):
        spec = {"fields": [{"tag": "245", "subfields": [["a", "X"]]}]}

        leader = ET.fromstring(build_alma_bib_xml(spec)).find("record").find(
            "leader"
        )
        assert leader.text == DEFAULT_LEADER

    def test_illegal_control_chars_stripped(self):
        # NUL (illegal in XML 1.0) is stripped; the rest survives.
        spec = {"fields": [{"tag": "245", "subfields": [["a", "A\x00B"]]}]}

        value = ET.fromstring(build_alma_bib_xml(spec)).find("record").find(
            "datafield"
        ).find("subfield").text
        assert value == "AB"

    # --- validation -------------------------------------------------------

    def test_rejects_non_dict_spec(self):
        with pytest.raises(AlmaValidationError):
            build_alma_bib_xml(["not", "a", "dict"])  # type: ignore[arg-type]

    def test_rejects_missing_fields(self):
        with pytest.raises(AlmaValidationError):
            build_alma_bib_xml({"leader": DEFAULT_LEADER})

    def test_rejects_empty_fields(self):
        with pytest.raises(AlmaValidationError):
            build_alma_bib_xml({"fields": []})

    def test_rejects_field_missing_tag(self):
        with pytest.raises(AlmaValidationError):
            build_alma_bib_xml({"fields": [{"subfields": [["a", "X"]]}]})

    def test_rejects_data_field_without_subfields(self):
        # Tag 245, no 'data' (so not a control field) and no 'subfields'.
        with pytest.raises(AlmaValidationError):
            build_alma_bib_xml({"fields": [{"tag": "245"}]})

    def test_rejects_bad_subfield_pair(self):
        with pytest.raises(AlmaValidationError):
            build_alma_bib_xml(
                {"fields": [{"tag": "245", "subfields": [["a"]]}]}
            )

    def test_rejects_multichar_indicator(self):
        with pytest.raises(AlmaValidationError):
            build_alma_bib_xml(
                {"fields": [{"tag": "245", "ind1": "12",
                             "subfields": [["a", "X"]]}]}
            )


# ---------------------------------------------------------------------------
# create_record_from_fields
# ---------------------------------------------------------------------------


class TestCreateRecordFromFields:
    """Tests for ``BibliographicRecords.create_record_from_fields``."""

    def _spec(self) -> Dict[str, Any]:
        return {
            "fields": [
                {"tag": "245", "ind1": "1", "ind2": "0",
                 "subfields": [["a", "Data Reduction Methods"]]},
            ]
        }

    def test_posts_built_xml_to_bibs_endpoint_as_xml(self):
        client = MockAlmaAPIClient()
        client.post_response = MockAlmaResponse(body={"mms_id": "99123"})
        bibs = BibliographicRecords(client)

        response = bibs.create_record_from_fields(self._spec())

        assert len(client.calls["post"]) == 1
        call = client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/bibs"
        assert call["content_type"] == "application/xml"
        # Body is the built XML (a string), not a dict.
        assert isinstance(call["data"], str)
        assert call["data"] == build_alma_bib_xml(self._spec())
        assert "Data Reduction Methods" in call["data"]
        assert response is client.post_response

    def test_forwards_validate_params(self):
        client = MockAlmaAPIClient()
        bibs = BibliographicRecords(client)

        bibs.create_record_from_fields(
            self._spec(), validate=False, override_warning=True
        )

        params = client.calls["post"][0]["params"]
        assert params["validate"] == "false"
        assert params["override_warning"] == "true"

    def test_malformed_spec_raises_before_any_post(self):
        client = MockAlmaAPIClient()
        bibs = BibliographicRecords(client)

        with pytest.raises(AlmaValidationError):
            bibs.create_record_from_fields({"fields": []})

        assert client.calls["post"] == []


# ---------------------------------------------------------------------------
# create_record_from_pymarc
# ---------------------------------------------------------------------------

_PYMARC_INSTALLED = importlib.util.find_spec("pymarc") is not None


class TestCreateRecordFromPymarc:
    """Tests for the optional pymarc adapter."""

    def test_builds_and_posts_from_pymarc_record(self):
        pymarc = pytest.importorskip("pymarc")

        record = pymarc.Record()
        record.add_field(
            pymarc.Field(tag="008", data="230101s2023    xx")
        )
        record.add_field(
            pymarc.Field(
                tag="245",
                indicators=["1", "0"],
                subfields=[pymarc.Subfield(code="a", value="Title & More")],
            )
        )

        client = MockAlmaAPIClient()
        client.post_response = MockAlmaResponse(body={"mms_id": "99321"})
        bibs = BibliographicRecords(client)

        response = bibs.create_record_from_pymarc(record)

        assert len(client.calls["post"]) == 1
        call = client.calls["post"][0]
        assert call["endpoint"] == "almaws/v1/bibs"
        assert call["content_type"] == "application/xml"
        root = ET.fromstring(call["data"])
        assert root.find("record").find("controlfield").get("tag") == "008"
        # & escaped exactly once through the adapter -> builder path.
        assert "&amp;amp;" not in call["data"]
        title = root.find("record").find("datafield").find("subfield").text
        assert title == "Title & More"
        assert response is client.post_response

    @pytest.mark.skipif(
        _PYMARC_INSTALLED,
        reason="pymarc is installed; the missing-extra error path cannot fire",
    )
    def test_missing_pymarc_extra_raises_actionable_error(self):
        client = MockAlmaAPIClient()
        bibs = BibliographicRecords(client)

        with pytest.raises(AlmaValidationError) as excinfo:
            bibs.create_record_from_pymarc(object())

        assert "pymarc" in str(excinfo.value)
        assert client.calls["post"] == []
