"""R10 regression test for issue #184 — repeatable MARC field data loss.

Bug: ``BibliographicRecords._build_updated_marc_xml`` rebuilt the record and
replaced the target tag at its *first* occurrence, then ``continue``-d past
every other occurrence of the same tag — silently dropping them from the XML
PUT back to Alma.

MARC 6XX/5XX/7XX/020/490/856 etc. are **Repeatable**; a record routinely
carries several 650s. Failure scenario from the issue: a record with
``650 _0 $a Physics``, ``650 _0 $a Astrophysics`` and ``650 _0 $a Cosmology``
calling ``update_marc_field(mms_id, "650", {"a": "Physics -- data reduction"})``
collapsed three subject headings to one — no error, no warning.

These tests pin the *symptom*: the captured PUT body must still carry the
untargeted occurrences of the tag. They fail against the pre-fix code (3 -> 1
collapse) and pass once every untargeted occurrence is preserved and an explicit
non-destructive ``mode`` is available.

Pattern source: ``tests/unit/regressions/test_issue_119_user_note_write_shape.py``
— same ``MockAlmaAPIClient`` / ``MockAlmaResponse`` shape (mocked ``get`` + ``put``).
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
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


# A record shaped like Alma's ``anies[0]``: a bare <record> with three 650s.
_THREE_650_MARC = (
    "<record>"
    "<leader>00000nam a2200000 a 4500</leader>"
    '<controlfield tag="001">99123456789</controlfield>'
    '<datafield tag="245" ind1="1" ind2="0">'
    '<subfield code="a">A test title</subfield>'
    "</datafield>"
    '<datafield tag="650" ind1=" " ind2="0">'
    '<subfield code="a">Physics</subfield>'
    "</datafield>"
    '<datafield tag="650" ind1=" " ind2="0">'
    '<subfield code="a">Astrophysics</subfield>'
    "</datafield>"
    '<datafield tag="650" ind1=" " ind2="0">'
    '<subfield code="a">Cosmology</subfield>'
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


def _subfield_a_values(record: ET.Element, tag: str) -> list:
    """All ``$a`` values for a given datafield tag, in document order."""
    values = []
    for df in record.findall(f"datafield[@tag='{tag}']"):
        for sf in df.findall("subfield[@code='a']"):
            values.append(sf.text)
    return values


def test_replace_first_preserves_other_650s_regression_184() -> None:
    """R10: updating one 650 must NOT delete the other two.

    Pre-fix, ``_build_updated_marc_xml`` replaced the first 650 and dropped the
    rest — three subject headings collapsed to one. The default (non-destructive)
    behaviour must leave the untargeted occurrences intact.
    """
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_THREE_650_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field(
        "99123456789", "650", {"a": "Physics -- data reduction"}
    )

    record = _captured_put_record(client)
    values = _subfield_a_values(record, "650")

    # The whole point of the regression: three 650s must remain three.
    assert len(values) == 3, (
        f"expected 3 preserved 650 fields, the record collapsed to {len(values)}: "
        f"{values!r}"
    )
    # First occurrence updated, the other two headings preserved verbatim.
    assert values[0] == "Physics -- data reduction"
    assert "Astrophysics" in values
    assert "Cosmology" in values


def test_append_mode_adds_occurrence_without_deleting_regression_184() -> None:
    """R10: append mode adds a 4th 650 and keeps the original three."""
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_THREE_650_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field(
        "99123456789", "650", {"a": "Particle physics"}, mode="append"
    )

    record = _captured_put_record(client)
    values = _subfield_a_values(record, "650")

    assert len(values) == 4, f"append must keep all + add one, got {values!r}"
    assert "Physics" in values
    assert "Astrophysics" in values
    assert "Cosmology" in values
    assert "Particle physics" in values


def test_replace_all_collapses_to_single_650_regression_184() -> None:
    """``replace_all`` is the *explicit, opt-in* destructive path.

    It intentionally collapses every occurrence of the tag into one new field —
    the behaviour that used to happen silently must now require asking for it.
    """
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_THREE_650_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field(
        "99123456789", "650", {"a": "Physics"}, mode="replace_all"
    )

    record = _captured_put_record(client)
    values = _subfield_a_values(record, "650")

    assert values == ["Physics"], f"replace_all must yield one 650, got {values!r}"


def test_untargeted_fields_are_untouched_regression_184() -> None:
    """Updating 650 must leave the 245 title field intact."""
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_THREE_650_MARC))
    bibs = BibliographicRecords(client)

    bibs.update_marc_field("99123456789", "650", {"a": "Physics -- data reduction"})

    record = _captured_put_record(client)
    titles = _subfield_a_values(record, "245")
    assert titles == ["A test title"], f"245 must be preserved, got {titles!r}"


def test_invalid_mode_raises_validation_error_regression_184() -> None:
    """An unsupported ``mode`` must fail fast with AlmaValidationError."""
    from almaapitk.client.AlmaAPIClient import AlmaValidationError
    from almaapitk.domains.bibs import BibliographicRecords

    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_bib(_THREE_650_MARC))
    bibs = BibliographicRecords(client)

    with pytest.raises(AlmaValidationError):
        bibs.update_marc_field(
            "99123456789", "650", {"a": "X"}, mode="obliterate"
        )
    assert client.calls["put"] == [], "no PUT should occur on invalid mode"
