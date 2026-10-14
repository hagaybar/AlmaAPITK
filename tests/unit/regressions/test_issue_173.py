"""R10 regression tests for issue #173 (grouped lower-severity defects).

1. ``_build_invoice_line_structure`` took a ``currency`` it never used. Alma's
   ``invoice_line`` has no per-line currency (it is inherited from the
   invoice), so the parameter is documented as ignored; no test needed.
2. ``list_invoices`` / ``search_invoices`` returned ``total_record_count`` as
   the page length at ``offset=0`` but Alma's grand total at ``offset>0``.
   It now always carries Alma's grand total.
3. ``iter_paged`` stopped after one full page when ``total_record_count`` was
   absent or 0, despite its comment claiming to handle that case.
4. ``_parse_pubmed_xml`` read ``.text`` and truncated titles / abstracts at
   the first inline tag (``<i>``, ``<sup>``, ...).
5. ``_parse_crossref_json`` turned ``date-parts: [[null]]`` into ``'None'``.
"""
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from almaapitk.client.AlmaAPIClient import AlmaAPIClient
from almaapitk.domains.acquisition import Acquisitions
from almaapitk.utils.citation_metadata import (
    _parse_crossref_json,
    _parse_pubmed_xml,
)


def _response(body):
    resp = MagicMock()
    resp.json.return_value = body
    return resp


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", "test-sandbox-key")
    return AlmaAPIClient("SANDBOX")


# --- 2. total_record_count ---------------------------------------------------

@pytest.mark.parametrize("offset", [0, 10])
def test_list_invoices_total_is_alma_grand_total(client, offset):
    body = {"invoice": [{"id": f"inv-{i}"} for i in range(10)],
            "total_record_count": 500}
    client.get = MagicMock(return_value=_response(body))

    result = Acquisitions(client).list_invoices(limit=10, offset=offset)

    assert result["total_record_count"] == 500
    assert len(result["invoice"]) == 10


@pytest.mark.parametrize("offset", [0, 10])
def test_search_invoices_total_is_alma_grand_total(client, offset):
    body = {"invoice": [{"id": f"inv-{i}"} for i in range(10)],
            "total_record_count": 500}
    client.get = MagicMock(return_value=_response(body))

    result = Acquisitions(client).search_invoices("vendor~V1", limit=10,
                                                  offset=offset)

    assert result["total_record_count"] == 500


# --- 3. iter_paged without a total ------------------------------------------

@pytest.mark.parametrize("total", [None, 0])
def test_iter_paged_continues_past_full_page_without_total(client, total):
    pages = [
        {"thing": [{"n": 1}, {"n": 2}]},
        {"thing": [{"n": 3}, {"n": 4}]},
        {"thing": [{"n": 5}]},
    ]
    if total is not None:
        for page in pages:
            page["total_record_count"] = total
    client.get = MagicMock(side_effect=[_response(p) for p in pages])

    records = list(client.iter_paged("almaws/v1/x", record_key="thing",
                                     page_size=2))

    assert [r["n"] for r in records] == [1, 2, 3, 4, 5]
    assert client.get.call_count == 3


# --- 4. PubMed inline markup -------------------------------------------------

def test_pubmed_title_and_abstract_keep_inline_markup_text():
    article = ET.fromstring(
        "<PubmedArticle><MedlineCitation><Article>"
        "<ArticleTitle>Effect of <i>BRCA1</i> on survival</ArticleTitle>"
        "<Abstract><AbstractText>Rate of CO<sub>2</sub> rose.</AbstractText>"
        "</Abstract></Article></MedlineCitation></PubmedArticle>"
    )

    metadata = _parse_pubmed_xml(article, "1")

    assert metadata["title"] == "Effect of BRCA1 on survival"
    assert metadata["abstract"] == "Rate of CO2 rose."


# --- 5. Crossref [[null]] date ----------------------------------------------

def test_crossref_null_date_parts_give_empty_year():
    metadata = _parse_crossref_json(
        {"title": ["T"], "published-print": {"date-parts": [[None]]}},
        "10.0000/x",
    )

    assert metadata["year"] == ""
    assert "None" not in metadata.get("publication_date", "")
