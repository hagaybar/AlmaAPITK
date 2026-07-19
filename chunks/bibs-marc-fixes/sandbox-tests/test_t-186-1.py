"""Generated SANDBOX test t-186-1 -- #186 no double-escaping of &/</>.

Live-SANDBOX proof of the issue #186 fix: a field value containing '&', '<'
and '>' must round-trip through ``update_marc_field`` unmangled (escaped
exactly once). The test seeds a throwaway bib with a 245, calls
``update_marc_field(mms_id, "245", [["a", "Law & order <suppl> report"]],
ind1="1", ind2="0")``, RE-FETCHES and asserts (a) the decoded 245 $a is the
exact literal and (b) the raw re-fetched MARCXML contains no doubly-escaped
'&amp;amp;'. Pre-fix, ``_sanitize_xml_text`` pre-escaped '&' -> '&amp;' and
ElementTree escaped again, so Alma stored 'Law &amp; order'.

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

# Synthetic seed bib: leader + 008 + a single 245.
_SEED_XML = '<bib><record><leader>00000nam a2200000 a 4500</leader><controlfield tag="008">230101s2023    xx            000 0 eng d</controlfield><datafield tag="245" ind1="1" ind2="0"><subfield code="a">AlmaAPITK MARC-fix seed 186</subfield></datafield></record></bib>'

# Field value deliberately carrying all three XML-special characters.
_TITLE_VALUE = "Law & order <suppl> report"


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


def test_t_186_1():
    if not os.environ.get("ALMA_SB_API_KEY"):
        pytest.skip("ALMA_SB_API_KEY not set; live SANDBOX credentials required")

    client = AlmaAPIClient(environment="SANDBOX")
    bibs = BibliographicRecords(client)

    created_mms_id = None
    try:
        # --- seed: create a throwaway bib with a single 245 -----------------
        create_response = bibs.create_record(
            _SEED_XML, validate=True, override_warning=True
        )
        created_mms_id = ET.fromstring(create_response.text()).findtext("mms_id")
        print(f"[t-186-1] CREATED MMS_ID: {created_mms_id}")

        assert create_response.success is True
        assert isinstance(created_mms_id, str) and created_mms_id.strip() != "", (
            "seed bib create must return a non-empty mms_id"
        )

        # --- act: write a 245 $a containing '&', '<' and '>' ----------------
        update_response = bibs.update_marc_field(
            created_mms_id, "245", [["a", _TITLE_VALUE]], ind1="1", ind2="0"
        )
        assert update_response.success is True

        # --- verify by RE-FETCHING and parsing MARCXML ----------------------
        fetched = bibs.get_record(created_mms_id)
        raw_anies = fetched.data["anies"][0]
        record = _parse_record(fetched)
        title_245 = [
            sf.text
            for df in record.findall("datafield[@tag='245']")
            for sf in df.findall("subfield[@code='a']")
        ]

        assert title_245 == [_TITLE_VALUE], (
            f"value must round-trip decoded exactly once (pre-fix would read "
            f"'Law &amp; order ...'), got {title_245!r}"
        )
        assert "&amp;amp;" not in raw_anies, (
            "raw re-fetched MARCXML must carry a single level of escaping, "
            "never a doubly-escaped '&amp;amp;'"
        )
    finally:
        _delete_seed(bibs, created_mms_id, "t-186-1")
