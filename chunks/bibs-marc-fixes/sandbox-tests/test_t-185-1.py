"""Generated SANDBOX test t-185-1 -- #185 repeated subfield codes round-trip.

Live-SANDBOX proof of the issue #185 fix: the MARC-editing path must accept
an ordered list of ``[code, value]`` pairs (not a dict) and preserve
repeated subfield codes. The test seeds a throwaway bib with a single 650,
then calls ``update_marc_field(mms_id, "650", [["a","Science"],
["x","History"], ["x","20th century"]])`` -- a shape a dict could never
express (two ``$x``). It RE-FETCHES and asserts the 650 comes back as
$a Science / $x History / $x 20th century, in order, with BOTH ``$x`` values
present. Pre-fix the dict-typed path silently dropped the second ``$x`` at
dict-construction time.

R9: the seed bib is created by the test itself with only synthetic MARC
data. ``test-data.json`` is loaded at runtime for consistency (no fixture
keys are referenced). Verification RE-FETCHES with ``get_record`` and parses
the returned MARCXML rather than trusting the update echo (GET/PUT
asymmetry).

STATE-CHANGING: the seed bib is deleted in a ``try/finally``; a failed
cleanup prints a MANUAL CLEANUP banner naming the leftover mms_id.

DO NOT EDIT by hand. Generated from
chunks/bibs-marc-fixes/test-recommendation.json.
"""
from __future__ import annotations

import json
import os
import pathlib
import xml.etree.ElementTree as ET

import pytest

from almaapitk import AlmaAPIClient, AlmaAPIError, AlmaValidationError
from almaapitk.domains.bibs import BibliographicRecords

_TEST_DATA = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "test-data.json").read_text()
)

# Synthetic seed bib: leader + 008 + 245 + a single 650.
_SEED_XML = '<bib><record><leader>00000nam a2200000 a 4500</leader><controlfield tag="008">230101s2023    xx            000 0 eng d</controlfield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">AlmaAPITK MARC-fix seed 185</subfield></datafield><datafield tag="650" ind1=" " ind2="0"><subfield code="a">Science</subfield></datafield></record></bib>'


def _parse_record(fetched):
    """Return the <record> element from a re-fetched bib's MARCXML."""
    root = ET.fromstring(fetched.data["anies"][0])
    return root.find("record") if root.tag == "bib" else root


def _delete_seed(bibs, mms_id, test_id):
    """Best-effort cleanup: delete the seed bib, retry with override, then warn."""
    if not mms_id:
        return
    try:
        bibs.delete_record(mms_id)
        print(f"[{test_id}] CLEANUP OK: deleted seed bib {mms_id}")
        return
    except (AlmaAPIError, AlmaValidationError):
        pass
    try:
        bibs.delete_record(mms_id, override_attached_items=True)
        print(f"[{test_id}] CLEANUP OK (override): deleted seed bib {mms_id}")
    except Exception as cleanup_err:  # noqa: BLE001
        print(
            f"\n!!! [{test_id}] MANUAL CLEANUP REQUIRED !!!\n"
            f"!!! seed bib mms_id: {mms_id}\n"
            f"!!! reason: {cleanup_err!r}\n"
            f"!!! Operator must delete this bib via the Alma staff UI.\n"
        )


def test_t_185_1():
    if not os.environ.get("ALMA_SB_API_KEY"):
        pytest.skip("ALMA_SB_API_KEY not set; live SANDBOX credentials required")

    client = AlmaAPIClient(environment="SANDBOX")
    bibs = BibliographicRecords(client)

    created_mms_id = None
    try:
        # --- seed: create a throwaway bib with a single 650 -----------------
        create_response = bibs.create_record(
            _SEED_XML, validate=True, override_warning=True
        )
        created_mms_id = ET.fromstring(create_response.text()).findtext("mms_id")
        print(f"[t-185-1] CREATED MMS_ID: {created_mms_id}")

        assert create_response.success is True
        assert isinstance(created_mms_id, str) and created_mms_id.strip() != "", (
            "seed bib create must return a non-empty mms_id"
        )

        # --- act: rewrite the 650 with an ordered list carrying two $x ------
        update_response = bibs.update_marc_field(
            created_mms_id,
            "650",
            [["a", "Science"], ["x", "History"], ["x", "20th century"]],
        )
        assert update_response.success is True

        # --- verify by RE-FETCHING and parsing MARCXML ----------------------
        fetched = bibs.get_record(created_mms_id)
        record = _parse_record(fetched)
        pairs_650 = [
            (sf.get("code"), sf.text)
            for df in record.findall("datafield[@tag='650']")
            for sf in df.findall("subfield")
        ]

        assert pairs_650 == [
            ("a", "Science"),
            ("x", "History"),
            ("x", "20th century"),
        ], f"ordered subfields (incl. two $x) should round-trip, got {pairs_650!r}"
        assert [v for c, v in pairs_650 if c == "x"] == ["History", "20th century"], (
            f"both distinct $x values must survive, got {pairs_650!r}"
        )
    finally:
        _delete_seed(bibs, created_mms_id, "t-185-1")
