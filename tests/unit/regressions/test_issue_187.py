"""R10 regression test for issue #187 — build_alma_bib_xml accepted invalid
MARC content designation.

Bug: the structure-driven builder validated the spec *shape* (dict, non-empty
``fields``, ``[code, value]`` pairs) but skipped the MARC **content-designation**
rules the older ``update_marc_field`` / ``get_marc_subfield`` already enforce, so
it was *more permissive* than the readers. Invalid MARC passed straight through
to Alma (or nowhere):

  * a 2- or 4-character or non-numeric ``tag`` was accepted;
  * a data-range tag carrying ``data`` was emitted as ``<controlfield>``;
  * an uppercase / multi-character subfield ``code`` was accepted;
  * an uppercase / punctuation / fill-character (``|``) indicator was accepted.

These tests pin each gap: every case below fails against the pre-fix builder
(which built XML happily) and now raises ``AlmaValidationError``.

The builder is pure (no network), so it is exercised directly.
"""

import xml.etree.ElementTree as ET

import pytest

from almaapitk import AlmaValidationError
from almaapitk.domains.bibs import build_alma_bib_xml


def _spec(field):
    """Wrap a single field dict in a minimal valid spec envelope."""
    return {"fields": [field]}


# --- tag format: exactly 3 numeric characters -----------------------------

@pytest.mark.parametrize("bad_tag", ["24", "2455", "abc", "24a", ""])
def test_rejects_non_three_digit_tag(bad_tag):
    with pytest.raises(AlmaValidationError):
        build_alma_bib_xml(_spec({"tag": bad_tag, "subfields": [["a", "X"]]}))


def test_accepts_valid_three_digit_tag():
    xml = build_alma_bib_xml(_spec({"tag": "245", "subfields": [["a", "X"]]}))
    assert ET.fromstring(xml).find("./record/datafield").get("tag") == "245"


# --- control vs data is decided by the TAG, not the 'data' key ------------

def test_rejects_data_key_on_data_range_tag():
    # 245 is a data field; carrying 'data' would emit <controlfield tag="245">.
    with pytest.raises(AlmaValidationError):
        build_alma_bib_xml(_spec({"tag": "245", "data": "raw"}))


def test_control_field_with_data_still_valid():
    # 008 is a genuine 00X control field — 'data' is correct here.
    xml = build_alma_bib_xml(_spec({"tag": "008", "data": "230101s2023 xx"}))
    cf = ET.fromstring(xml).find("./record/controlfield")
    assert cf is not None and cf.get("tag") == "008"


# --- subfield code: one lowercase letter or digit -------------------------

@pytest.mark.parametrize("bad_code", ["A", "ab", "@", ""])
def test_rejects_invalid_subfield_code(bad_code):
    with pytest.raises(AlmaValidationError):
        build_alma_bib_xml(_spec({"tag": "245", "subfields": [[bad_code, "X"]]}))


def test_accepts_lowercase_and_digit_subfield_codes():
    # Digit subfield codes are legal MARC (e.g. $2 source, $0 auth number).
    xml = build_alma_bib_xml(
        _spec({"tag": "024", "ind1": "7",
               "subfields": [["a", "12345"], ["2", "isbn"]]})
    )
    codes = [sf.get("code") for sf in ET.fromstring(xml).findall(".//subfield")]
    assert codes == ["a", "2"]


# --- indicators: blank, digit, or lowercase letter; no fill char '|' ------

@pytest.mark.parametrize("bad_ind", ["X", "@", "|", "12"])
def test_rejects_invalid_indicator(bad_ind):
    with pytest.raises(AlmaValidationError):
        build_alma_bib_xml(
            _spec({"tag": "245", "ind1": bad_ind, "subfields": [["a", "X"]]})
        )


@pytest.mark.parametrize("good_ind", [" ", "0", "7", "a"])
def test_accepts_valid_indicators(good_ind):
    xml = build_alma_bib_xml(
        _spec({"tag": "245", "ind1": good_ind, "subfields": [["a", "X"]]})
    )
    assert ET.fromstring(xml).find("./record/datafield").get("ind1") == good_ind
