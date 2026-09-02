"""R10 regression test for issue #214 — PubMed year lost to MedlineDate.

``_parse_pubmed_xml`` read the publication year only from ``PubDate/Year``.
PubMed omits ``<Year>`` whenever the issue's cover date is irregular — a month
range, a season, or a year span — and puts the whole date in ``<MedlineDate>``
instead. The parser then returned ``year=''`` even though the year was sitting
right there in the response.

Found in production 2026-09-02 by the resource-sharing borrowing pipeline,
which cannot create an article request without a year (Alma ``401930``). Title,
journal and author all parsed fine; only the year was lost, so the failure
looked like bad input rather than a parsing gap.

These tests pin the fallback chain so it can never silently regress:

- ``PubDate/Year`` still wins when present (the common case, unchanged).
- ``PubDate/MedlineDate`` supplies the year when ``<Year>`` is absent, across
  the shapes PubMed actually emits (month range, season, year span).
- ``ArticleDate/Year`` is the last resort, and loses to ``MedlineDate`` — the
  cover date is the citation's year, and the two disagree on online-ahead-of-
  print records.
- The raw ``MedlineDate`` string survives on the returned dict.
- A record with no date at all still parses, with an empty year.
"""

import xml.etree.ElementTree as ET

import pytest

from almaapitk.utils.citation_metadata import _parse_pubmed_xml

# Synthetic PMID throughout — R9: no real identifiers in committed files.
_PMID = "00000000"


def _article(pub_date_xml: str, article_date_xml: str = "") -> ET.Element:
    """A minimal PubmedArticle carrying just the date elements under test."""
    return ET.fromstring(
        "<PubmedArticle><MedlineCitation><Article>"
        "<Journal><JournalIssue>"
        f"{pub_date_xml}"
        "</JournalIssue><Title>Some Journal</Title></Journal>"
        "<ArticleTitle>Some Article</ArticleTitle>"
        f"{article_date_xml}"
        "</Article></MedlineCitation></PubmedArticle>"
    )


def test_year_element_still_wins():
    """The ordinary record must be untouched by the fallback chain."""
    article = _article(
        "<PubDate><Year>2021</Year><Month>Mar</Month><Day>04</Day></PubDate>",
        "<ArticleDate DateType='Electronic'><Year>2020</Year></ArticleDate>",
    )

    metadata = _parse_pubmed_xml(article, _PMID)

    assert metadata["year"] == "2021"
    assert metadata["month"] == "Mar"
    assert metadata["day"] == "04"
    assert metadata["publication_date"] == "2021 Mar 04"


@pytest.mark.parametrize("medline_date, expected", [
    ("2023 Jan-Feb 01", "2023"),   # the shape that broke production
    ("2022 Winter", "2022"),       # season instead of a month
    ("1998-1999", "1998"),         # a volume spanning two years
    ("2020 Nov-Dec", "2020"),
    ("Spring 2019", "2019"),       # year is not always the first token
])
def test_year_is_recovered_from_medline_date(medline_date, expected):
    article = _article(f"<PubDate><MedlineDate>{medline_date}</MedlineDate></PubDate>")

    metadata = _parse_pubmed_xml(article, _PMID)

    assert metadata["year"] == expected


def test_medline_date_string_is_preserved():
    """The derived year is lossy; the original must stay available."""
    article = _article(
        "<PubDate><MedlineDate>2023 Jan-Feb 01</MedlineDate></PubDate>")

    metadata = _parse_pubmed_xml(article, _PMID)

    assert metadata["medline_date"] == "2023 Jan-Feb 01"


def test_publication_date_stays_a_plain_year_not_the_raw_string():
    """``resource_sharing`` passes ``publication_date`` straight into Alma's
    ``year`` field, so the free-text MedlineDate must not leak into it."""
    article = _article(
        "<PubDate><MedlineDate>2023 Jan-Feb 01</MedlineDate></PubDate>")

    assert _parse_pubmed_xml(article, _PMID)["publication_date"] == "2023"


def test_medline_date_beats_article_date():
    """Online-ahead-of-print: the issue's cover year is the citation's year.

    The production record carried MedlineDate '2023 Jan-Feb 01' and
    ArticleDate 2022. A citation must say 2023.
    """
    article = _article(
        "<PubDate><MedlineDate>2023 Jan-Feb 01</MedlineDate></PubDate>",
        "<ArticleDate DateType='Electronic'>"
        "<Year>2022</Year><Month>11</Month><Day>15</Day></ArticleDate>",
    )

    assert _parse_pubmed_xml(article, _PMID)["year"] == "2023"


def test_article_date_is_the_last_resort():
    article = _article(
        "<PubDate></PubDate>",
        "<ArticleDate DateType='Electronic'>"
        "<Year>2022</Year><Month>11</Month><Day>15</Day></ArticleDate>",
    )

    assert _parse_pubmed_xml(article, _PMID)["year"] == "2022"


def test_unparseable_medline_date_does_not_invent_a_year():
    """No 4-digit year anywhere means no year — never a partial guess."""
    article = _article("<PubDate><MedlineDate>n.d.</MedlineDate></PubDate>")

    metadata = _parse_pubmed_xml(article, _PMID)

    assert metadata["year"] == ""
    assert metadata["medline_date"] == "n.d."


def test_record_with_no_date_at_all_still_parses():
    article = _article("")

    metadata = _parse_pubmed_xml(article, _PMID)

    assert metadata["year"] == ""
    assert metadata["medline_date"] == ""
    assert metadata["publication_date"] == ""
    assert metadata["title"] == "Some Article"
