"""R10 regression test for issue #167 — bib create/update Content-Type.

``BibliographicRecords.create_record`` and ``update_record`` passed
``content_type='xml'`` to the client. ``_prepare_headers`` only flips ``Accept``
to ``application/xml`` for the exact string ``'application/xml'``, so the request
went out with an invalid ``Content-Type: xml`` token *and* a mismatched
``Accept: application/json`` over a MARCXML body. The committed ``bibs.json``
swagger declares both endpoints ``consumes=['application/xml']``, and every other
XML caller in the repo already uses ``application/xml``.
"""
from unittest.mock import MagicMock

from almaapitk.domains.bibs import BibliographicRecords


# Minimal parseable XML (create/update only run ET.fromstring on it).
MARC_XML = "<bib><record><leader>00000nam</leader></record></bib>"


def _bibs():
    client = MagicMock()
    return BibliographicRecords(client), client


def test_create_record_sends_application_xml_content_type():
    bibs, client = _bibs()

    bibs.create_record(MARC_XML)

    assert client.post.call_args.kwargs.get("content_type") == "application/xml"


def test_update_record_sends_application_xml_content_type():
    bibs, client = _bibs()

    bibs.update_record("99100000000000", MARC_XML)

    assert client.put.call_args.kwargs.get("content_type") == "application/xml"
