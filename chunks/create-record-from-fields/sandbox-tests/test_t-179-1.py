"""Generated SANDBOX test t-179-1 - create_record_from_fields round-trip (issue #179).

Maps to:
  - AC-1 (live facet): create_record_from_fields(spec) creates a bib in SANDBOX
    from a native structure-driven spec.
  - AC-2 (live facet): build_alma_bib_xml emits valid, non-namespaced Alma
    <bib><record> MARCXML that Alma accepts on POST.
  - AC-4 (live facet): no double-escaping and repeated fields/subfields are
    preserved end-to-end through a real Alma round-trip.

Drives BibliographicRecords.create_record_from_fields(spec) against live SANDBOX
with a synthetic native spec (default-ish leader, an 008 control field, a 245
whose $a carries an ampersand, and two repeated 650 subject fields), then
retrieves the created bib and inspects the returned MARCXML:

  * Alma accepting the POSTed structure-built XML proves the builder emits valid
    non-namespaced <bib><record> MARCXML.
  * Re-fetching proves the ampersand survived as a single '&' (raw MARCXML holds
    the single entity '&amp;', never the double-escaped '&amp;amp;'; the parsed
    subfield text is the literal 'Data Reduction & Analysis').
  * Both 650 subject fields persist, in order (repeated datafields preserved).

The exact XML-shape/escaping/repetition correctness is authoritatively pinned by
the offline unit + regression suites (tests/unit/domains/test_bibs.py,
tests/unit/regressions/test_issue_179.py); this live test is end-to-end
corroboration.

This test is state-changing: it creates a bib and deletes it in a try/finally so
the SANDBOX is left clean even if an assertion fails.

The synthetic spec is fully hardcoded (no operator-supplied identifiers), so
there are no fixtures to load. The runtime test-data.json load pattern is kept
for consistency with the chunk-test harness and to guarantee no fixture value is
ever inlined at generation time (R9 - this file is committed to a public repo).

DO NOT EDIT by hand. Generated from
chunks/create-record-from-fields/test-recommendation.json.
"""
from __future__ import annotations

import json
import pathlib
import xml.etree.ElementTree as ET

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import (
    AlmaAPIError,
    AlmaRateLimitError,
    AlmaValidationError,
)
from almaapitk.domains.bibs import BibliographicRecords

# Load fixtures at RUNTIME (never inline values at generation time - R9). For
# this chunk test-data.json is `{}`; the spec below is fully synthetic and uses
# no fixtures, but the runtime-load pattern is kept for consistency.
_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def _subfield_values(root: ET.Element, tag: str, code: str) -> list[str]:
    """Return the text of every ``<subfield code=...>`` under ``<datafield tag=...>``.

    Uses a descendant search (``.//``) so it works whether the retrieved
    ``anies[0]`` root element is ``<record>`` (the usual Alma bib shape) or a
    ``<bib>`` wrapper. Field and subfield document order is preserved.
    """
    values: list[str] = []
    for datafield in root.findall(f".//datafield[@tag='{tag}']"):
        for subfield in datafield.findall(f"./subfield[@code='{code}']"):
            values.append((subfield.text or ""))
    return values


def test_t_179_1():
    # SANDBOX only - uses ALMA_SB_API_KEY, never PROD.
    client = AlmaAPIClient("SANDBOX")
    bibs = BibliographicRecords(client)

    # Synthetic native spec built inline from the recommendation's pythonCalls:
    # default-ish leader, an 008 control field, a 245 whose $a carries an
    # ampersand, and two repeated 650 subject fields.
    spec = {
        "leader": "00000nam a2200000 a 4500",
        "fields": [
            {"tag": "008", "data": "230101s2023    xx            000 0 eng d"},
            {
                "tag": "245",
                "ind1": "1",
                "ind2": "0",
                "subfields": [
                    ["a", "Data Reduction & Analysis :"],
                    ["b", "a structure-driven test record"],
                ],
            },
            {"tag": "650", "ind1": " ", "ind2": "0", "subfields": [["a", "Data reduction"]]},
            {"tag": "650", "ind1": " ", "ind2": "0", "subfields": [["a", "Data science"]]},
        ],
    }

    created_mms_id = None
    try:
        # --- create --------------------------------------------------------
        # A raised AlmaAPIError / AlmaValidationError / AlmaRateLimitError here
        # propagates (caught below and re-raised as a readable AssertionError),
        # which satisfies the "no such error is raised" pass criterion.
        response = bibs.create_record_from_fields(
            spec, validate=True, override_warning=True
        )
        assert response is not None, "create_record_from_fields returned None"
        assert response.success is True, (
            "Alma rejected the structure-built <bib><record> XML "
            f"(status_code={getattr(response, 'status_code', None)})"
        )

        # The create (POST /bibs) response body is XML, not JSON: create_record
        # sends Content-Type: application/xml and AlmaAPIClient._prepare_headers
        # mirrors that into Accept: application/xml, so Alma replies with the
        # created <bib> as XML. Read the new mms_id from that returned XML --
        # calling response.data here would run .json() on an XML body and raise
        # JSONDecodeError. (Manual correction: the recommendation's illustrative
        # `response.data.get('mms_id')` wrongly assumed a JSON create response.)
        created_root = ET.fromstring(response.text())
        created_mms_id = created_root.findtext(".//mms_id")
        assert isinstance(created_mms_id, str) and created_mms_id.strip(), (
            "created bib carries no non-empty mms_id in the returned <bib> XML "
            f"(got {created_mms_id!r})"
        )

        # --- retrieve ------------------------------------------------------
        fetched = bibs.get_record(created_mms_id)
        assert fetched.success is True, (
            f"created bib {created_mms_id!r} could not be retrieved "
            f"(status_code={getattr(fetched, 'status_code', None)})"
        )

        anies = fetched.data.get("anies")
        assert anies and isinstance(anies, list) and anies[0], (
            "retrieved bib payload has no MARCXML in 'anies'"
        )
        marc_xml = anies[0]

        # --- ampersand: no double-escaping (raw-XML authoritative check) ----
        # A correctly single-escaped record holds '&amp;' in the raw MARCXML;
        # a double-escaped one would hold '&amp;amp;'. Assert on the raw bytes.
        assert "&amp;amp;" not in marc_xml, (
            "retrieved MARCXML contains a double-escaped ampersand "
            "('&amp;amp;') - build_alma_bib_xml double-escaped '&'"
        )

        root = ET.fromstring(marc_xml)

        # --- 245 title round-trips to the literal 'Data Reduction & Analysis' -
        title_a_values = _subfield_values(root, "245", "a")
        assert title_a_values, "retrieved record has no 245 $a subfield"
        title_a = title_a_values[0]
        # ElementTree un-escapes '&amp;' -> '&' on parse; a correct round-trip
        # yields a single literal '&'. A double-escaped record would parse to
        # 'Data Reduction &amp; Analysis' (entity text still present).
        assert "Data Reduction & Analysis" in title_a, (
            "245 $a did not round-trip to the literal 'Data Reduction & Analysis' "
            f"(got {title_a!r})"
        )
        assert "&amp;" not in title_a, (
            "parsed 245 $a still contains the entity '&amp;' - the ampersand "
            f"was double-escaped through the round-trip (got {title_a!r})"
        )

        # --- two repeated 650s preserved, in order -------------------------
        all_650_a = [value.strip() for value in _subfield_values(root, "650", "a")]
        ordered_targets = [
            value for value in all_650_a if value in ("Data reduction", "Data science")
        ]
        assert ordered_targets == ["Data reduction", "Data science"], (
            "retrieved record did not preserve the two 650 subject fields "
            "'Data reduction' then 'Data science' in order "
            f"(650 $a values seen: {all_650_a!r})"
        )

    except (AlmaAPIError, AlmaValidationError, AlmaRateLimitError) as exc:
        # Surface an Alma error as an explicit, readable failure. The typed
        # subclasses (e.g. AlmaRateLimitError) are AlmaAPIError subclasses but
        # are listed explicitly to mirror the pass criterion.
        raise AssertionError(
            f"create/retrieve raised an Alma error: {type(exc).__name__}: {exc}"
        ) from exc

    finally:
        # Cleanup is mandatory for this state-changing test: delete the created
        # bib. Guarded so it only runs if a bib was actually created.
        if created_mms_id:
            try:
                bibs.delete_record(created_mms_id)
            except AlmaAPIError:
                # Best-effort cleanup: if the bib is already gone or delete
                # fails, do not mask the original test outcome.
                pass
