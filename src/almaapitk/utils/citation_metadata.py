"""
Citation Metadata Utility

Fetches article metadata from free public sources:
- PubMed (NCBI E-utilities) - using PubMed ID (PMID)
- Crossref API - using DOI (Digital Object Identifier)

Both services are free and don't require API keys for basic usage.

Usage:
    from almaapitk.utils.citation_metadata import get_pubmed_metadata, get_crossref_metadata

    # From PubMed
    metadata = get_pubmed_metadata("12345678")

    # From Crossref
    metadata = get_crossref_metadata("10.1000/example.2024.001")
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


# Configure logger
logger = logging.getLogger(__name__)


# API Endpoints
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CROSSREF_API_URL = "https://api.crossref.org/works"

# Request timeout (seconds)
REQUEST_TIMEOUT = 30


class CitationMetadataError(Exception):
    """Base exception for citation metadata errors."""
    pass


class PubMedError(CitationMetadataError):
    """Exception raised when PubMed API fails."""
    pass


class CrossrefError(CitationMetadataError):
    """Exception raised when Crossref API fails."""
    pass


def get_pubmed_metadata(pmid: str) -> Dict[str, Any]:
    """
    Fetch article metadata from PubMed using PubMed ID (PMID).

    Uses NCBI E-utilities API (efetch) to retrieve article information.
    Returns standardized metadata dictionary.

    Args:
        pmid: PubMed ID (e.g., "12345678")

    Returns:
        Dictionary with article metadata:
            - title: Article title
            - authors: List of author names
            - journal: Journal name
            - year: Publication year. Taken from PubDate/Year, falling back to
              the year inside PubDate/MedlineDate and then to ArticleDate/Year,
              because PubMed omits <Year> on irregular cover dates (issue #214)
            - medline_date: Raw PubDate/MedlineDate string when the record has
              one ("2023 Jan-Feb 01"), else '' — the original of a derived year
            - volume: Journal volume
            - issue: Journal issue
            - pages: Page range
            - doi: DOI if available
            - pmid: PubMed ID
            - abstract: Article abstract (if available)
            - publication_date: Full publication date

    Raises:
        PubMedError: If API request fails or PMID not found
        ValueError: If PMID is invalid format

    Examples:
        >>> metadata = get_pubmed_metadata("33219451")
        >>> print(metadata['title'])
        'Example Article Title'
        >>> print(metadata['authors'])
        ['Smith J', 'Jones A']
        >>> print(metadata['journal'])
        'Nature Medicine'
    """
    # Validate PMID format (should be numeric)
    if not pmid or not pmid.strip():
        raise ValueError("PMID cannot be empty")

    pmid = pmid.strip()
    if not pmid.isdigit():
        raise ValueError(f"Invalid PMID format: {pmid}. Must be numeric.")

    logger.info(f"Fetching PubMed metadata for PMID: {pmid}")

    # Build API request
    params = {
        'db': 'pubmed',
        'id': pmid,
        'retmode': 'xml',
        'rettype': 'abstract'
    }

    try:
        response = requests.get(
            PUBMED_EFETCH_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={'User-Agent': 'AlmaAPITK/1.0 (mailto:library@example.com)'}
        )
        response.raise_for_status()

    except requests.exceptions.Timeout:
        raise PubMedError(f"PubMed API request timed out for PMID: {pmid}")
    except requests.exceptions.RequestException as e:
        raise PubMedError(f"PubMed API request failed: {e}")

    # Parse XML response
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        raise PubMedError(f"Failed to parse PubMed XML response: {e}")

    # Check if article was found
    article = root.find('.//PubmedArticle')
    if article is None:
        raise PubMedError(f"Article not found for PMID: {pmid}")

    # Extract metadata
    try:
        metadata = _parse_pubmed_xml(article, pmid)
        logger.info(f"Successfully fetched PubMed metadata for PMID: {pmid}")
        return metadata

    except Exception as e:
        raise PubMedError(f"Failed to parse PubMed article data: {e}")


#: A 4-digit year anywhere in a free-text date. MEDLINE records run from the
#: 1800s, so 1xxx is in range; the alternation keeps 3-digit page numbers and
#: volume/issue values from ever matching.
_YEAR_IN_TEXT = re.compile(r'\b(1[0-9]{3}|20[0-9]{2})\b')


def _element_text(elem: Optional[ET.Element]) -> str:
    """Text of *elem*, or '' when the element is absent or empty."""
    if elem is None or elem.text is None:
        return ''
    return elem.text.strip()


def _first_year(text: str) -> str:
    """First 4-digit year in *text*, or '' when it holds none.

    PubMed's ``MedlineDate`` is free text covering every date PubMed cannot
    express structurally: ``2023 Jan-Feb 01``, ``2022 Winter``, ``1998-1999``,
    ``Spring 2019``. A record with no year at all (``n.d.``) must yield '' —
    never a partial or invented value.
    """
    match = _YEAR_IN_TEXT.search(text or '')
    return match.group(0) if match else ''


def _parse_pubmed_xml(article: ET.Element, pmid: str) -> Dict[str, Any]:
    """
    Parse PubMed XML article element into metadata dictionary.

    Args:
        article: PubmedArticle XML element
        pmid: PubMed ID

    Returns:
        Metadata dictionary
    """
    metadata = {'pmid': pmid}

    # Title
    title_elem = article.find('.//ArticleTitle')
    metadata['title'] = title_elem.text if title_elem is not None else ''

    # Authors
    authors = []
    for author in article.findall('.//Author'):
        last_name = author.find('LastName')
        initials = author.find('Initials')
        if last_name is not None:
            author_str = last_name.text
            if initials is not None:
                author_str += f" {initials.text}"
            authors.append(author_str)
    metadata['authors'] = authors
    metadata['author'] = ', '.join(authors) if authors else ''

    # Journal
    journal_elem = article.find('.//Journal/Title')
    if journal_elem is None:
        journal_elem = article.find('.//Journal/ISOAbbreviation')
    metadata['journal'] = journal_elem.text if journal_elem is not None else ''

    # Publication date
    pub_date = article.find('.//PubDate')
    year_elem = pub_date.find('Year') if pub_date is not None else None
    month_elem = pub_date.find('Month') if pub_date is not None else None
    day_elem = pub_date.find('Day') if pub_date is not None else None
    medline_elem = pub_date.find('MedlineDate') if pub_date is not None else None

    metadata['medline_date'] = _element_text(medline_elem)
    metadata['month'] = _element_text(month_elem)
    metadata['day'] = _element_text(day_elem)

    # PubMed omits <Year> whenever the issue's cover date is irregular — a
    # month range, a season, a year span — and puts the whole date in
    # <MedlineDate> instead ("2023 Jan-Feb 01"). Reading <Year> alone dropped
    # the year on those records even though it was in the response: issue #214,
    # hit in production 2026-09-02 by a borrowing request Alma then rejected
    # for having no year (401930).
    #
    # MedlineDate is tried before ArticleDate deliberately. MedlineDate is the
    # issue's own cover date, which is the year a citation should carry;
    # ArticleDate is the online-ahead-of-print date and is often a year
    # earlier (2022 vs. 2023 in the record that surfaced this).
    metadata['year'] = (
        _element_text(year_elem)
        or _first_year(metadata['medline_date'])
        or _element_text(article.find('.//ArticleDate/Year'))
    )

    # Build publication_date string
    date_parts = []
    if metadata['year']:
        date_parts.append(metadata['year'])
    if metadata['month']:
        date_parts.append(metadata['month'])
    if metadata['day']:
        date_parts.append(metadata['day'])
    metadata['publication_date'] = ' '.join(date_parts) if date_parts else ''

    # Volume, Issue, Pages
    volume_elem = article.find('.//Volume')
    issue_elem = article.find('.//Issue')
    pages_elem = article.find('.//MedlinePgn')

    metadata['volume'] = volume_elem.text if volume_elem is not None else ''
    metadata['issue'] = issue_elem.text if issue_elem is not None else ''
    metadata['pages'] = pages_elem.text if pages_elem is not None else ''

    # DOI
    doi_elem = article.find('.//ArticleId[@IdType="doi"]')
    metadata['doi'] = doi_elem.text if doi_elem is not None else ''

    # Abstract
    abstract_texts = []
    for abstract_elem in article.findall('.//AbstractText'):
        if abstract_elem.text:
            abstract_texts.append(abstract_elem.text)
    metadata['abstract'] = ' '.join(abstract_texts)

    # ISSN
    issn_elem = article.find('.//ISSN')
    metadata['issn'] = issn_elem.text if issn_elem is not None else ''

    return metadata


def get_crossref_metadata(doi: str) -> Dict[str, Any]:
    """
    Fetch article metadata from Crossref using DOI.

    Uses Crossref REST API to retrieve article information.
    Returns standardized metadata dictionary.

    Args:
        doi: Digital Object Identifier (e.g., "10.1000/example.2024.001")

    Returns:
        Dictionary with article metadata:
            - title: Article title
            - authors: List of author names
            - journal: Journal name (container-title)
            - year: Publication year
            - volume: Journal volume
            - issue: Journal issue
            - pages: Page range
            - doi: DOI
            - publisher: Publisher name
            - publication_date: Full publication date
            - issn: ISSN if available
            - type: Work type (journal-article, book-chapter, etc.)

    Raises:
        CrossrefError: If API request fails or DOI not found
        ValueError: If DOI is invalid format

    Examples:
        >>> metadata = get_crossref_metadata("10.1038/s41591-020-1124-9")
        >>> print(metadata['title'])
        'Example Article Title'
        >>> print(metadata['authors'])
        ['Smith, John', 'Jones, Alice']
        >>> print(metadata['journal'])
        'Nature Medicine'
    """
    # Validate DOI format
    if not doi or not doi.strip():
        raise ValueError("DOI cannot be empty")

    doi = doi.strip()

    # Remove common DOI URL prefixes if present
    if doi.startswith('https://doi.org/'):
        doi = doi.replace('https://doi.org/', '')
    elif doi.startswith('http://dx.doi.org/'):
        doi = doi.replace('http://dx.doi.org/', '')
    elif doi.startswith('doi:'):
        doi = doi.replace('doi:', '')

    logger.info(f"Fetching Crossref metadata for DOI: {doi}")

    # Build API request
    url = f"{CROSSREF_API_URL}/{quote(doi, safe='')}"

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                'User-Agent': 'AlmaAPITK/1.0 (mailto:library@example.com)',
                'Accept': 'application/json'
            }
        )

        if response.status_code == 404:
            raise CrossrefError(f"DOI not found: {doi}")

        response.raise_for_status()

    except requests.exceptions.Timeout:
        raise CrossrefError(f"Crossref API request timed out for DOI: {doi}")
    except CrossrefError:
        raise
    except requests.exceptions.RequestException as e:
        raise CrossrefError(f"Crossref API request failed: {e}")

    # Parse JSON response
    try:
        data = response.json()
        if 'message' not in data:
            raise CrossrefError("Invalid Crossref API response format")

        work = data['message']

    except ValueError as e:
        raise CrossrefError(f"Failed to parse Crossref JSON response: {e}")

    # Extract metadata
    try:
        metadata = _parse_crossref_json(work, doi)
        logger.info(f"Successfully fetched Crossref metadata for DOI: {doi}")
        return metadata

    except Exception as e:
        raise CrossrefError(f"Failed to parse Crossref work data: {e}")


def _parse_crossref_json(work: Dict[str, Any], doi: str) -> Dict[str, Any]:
    """
    Parse Crossref work JSON into metadata dictionary.

    Args:
        work: Crossref work data (message object)
        doi: DOI

    Returns:
        Metadata dictionary
    """
    metadata = {'doi': doi}

    # Title (may be array)
    titles = work.get('title', [])
    metadata['title'] = titles[0] if titles else ''

    # Authors
    authors = []
    for author in work.get('author', []):
        given = author.get('given', '')
        family = author.get('family', '')
        if family:
            author_str = family
            if given:
                author_str = f"{family}, {given}"
            authors.append(author_str)
    metadata['authors'] = authors
    metadata['author'] = '; '.join(authors) if authors else ''

    # Journal (container-title)
    container_titles = work.get('container-title', [])
    metadata['journal'] = container_titles[0] if container_titles else ''

    # Publisher
    metadata['publisher'] = work.get('publisher', '')

    # Publication date
    published = work.get('published-print') or work.get('published-online') or work.get('created')
    if published and 'date-parts' in published:
        date_parts = published['date-parts'][0]  # First date
        metadata['year'] = str(date_parts[0]) if len(date_parts) > 0 else ''
        metadata['month'] = str(date_parts[1]) if len(date_parts) > 1 else ''
        metadata['day'] = str(date_parts[2]) if len(date_parts) > 2 else ''

        # Build publication_date string
        parts = []
        if metadata['year']:
            parts.append(metadata['year'])
        if metadata['month']:
            parts.append(metadata['month'])
        if metadata['day']:
            parts.append(metadata['day'])
        metadata['publication_date'] = '-'.join(parts) if parts else ''
    else:
        metadata['year'] = ''
        metadata['month'] = ''
        metadata['day'] = ''
        metadata['publication_date'] = ''

    # Volume, Issue, Pages
    metadata['volume'] = work.get('volume', '')
    metadata['issue'] = work.get('issue') or work.get('journal-issue', {}).get('issue', '')
    metadata['pages'] = work.get('page', '')

    # ISSN
    issn_list = work.get('ISSN', [])
    metadata['issn'] = issn_list[0] if issn_list else ''

    # Type
    metadata['type'] = work.get('type', '')

    # Subject (keywords)
    metadata['subject'] = work.get('subject', [])

    return metadata


def enrich_citation_metadata(
    pmid: Optional[str] = None,
    doi: Optional[str] = None,
    source_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch citation metadata from PubMed or Crossref.

    Convenience function that fetches metadata from specified source or auto-detects.

    When source_type is specified, ONLY that source is used (no fallback).
    This is recommended when you know the identifier type upfront (e.g., from a form).

    When source_type is None, uses auto-detect mode with fallback:
    If both PMID and DOI are provided, tries PubMed first, then Crossref as fallback.

    Args:
        pmid: PubMed ID (optional)
        doi: Digital Object Identifier (optional)
        source_type: Explicit source type - 'pmid' or 'doi' (optional).
                     If specified, only that source is tried (no fallback).
                     If None, uses auto-detect with fallback.

    Returns:
        Metadata dictionary with 'source' field indicating which API was used

    Raises:
        ValueError: If neither PMID nor DOI provided, or invalid source_type
        CitationMetadataError: If metadata fetch fails

    Examples:
        >>> # Explicit source - recommended for form inputs
        >>> metadata = enrich_citation_metadata(
        ...     pmid="33219451",
        ...     source_type='pmid'
        ... )

        >>> # Explicit DOI source
        >>> metadata = enrich_citation_metadata(
        ...     doi="10.1038/s41591-020-1124-9",
        ...     source_type='doi'
        ... )

        >>> # Auto-detect mode (backward compatible)
        >>> metadata = enrich_citation_metadata(pmid="33219451")

        >>> # Auto-detect with fallback
        >>> metadata = enrich_citation_metadata(
        ...     pmid="33219451",
        ...     doi="10.1038/s41591-020-1124-9"
        ... )
    """
    # Explicit mode - use specified source only (no fallback)
    if source_type == 'pmid':
        if not pmid:
            raise ValueError("pmid parameter required when source_type='pmid'")
        logger.info(f"Fetching metadata from PubMed (explicit mode, PMID: {pmid})")
        metadata = get_pubmed_metadata(pmid)
        metadata['source'] = 'pubmed'
        logger.info("Successfully fetched metadata from PubMed")
        return metadata

    elif source_type == 'doi':
        if not doi:
            raise ValueError("doi parameter required when source_type='doi'")
        logger.info(f"Fetching metadata from Crossref (explicit mode, DOI: {doi})")
        metadata = get_crossref_metadata(doi)
        metadata['source'] = 'crossref'
        logger.info("Successfully fetched metadata from Crossref")
        return metadata

    elif source_type is not None:
        raise ValueError(
            f"Invalid source_type: '{source_type}'. "
            "Valid options: 'pmid', 'doi', or None for auto-detect"
        )

    # Auto-detect mode (backward compatible) - try with fallback
    if not pmid and not doi:
        raise ValueError("Must provide at least one of: pmid, doi")

    errors = []

    # Try PubMed first if PMID provided
    if pmid:
        try:
            logger.info(f"Attempting to fetch metadata from PubMed (PMID: {pmid})")
            metadata = get_pubmed_metadata(pmid)
            metadata['source'] = 'pubmed'
            logger.info("Successfully fetched metadata from PubMed")
            return metadata
        except Exception as e:
            error_msg = f"PubMed fetch failed: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)

    # Try Crossref if DOI provided
    if doi:
        try:
            logger.info(f"Attempting to fetch metadata from Crossref (DOI: {doi})")
            metadata = get_crossref_metadata(doi)
            metadata['source'] = 'crossref'
            logger.info("Successfully fetched metadata from Crossref")
            return metadata
        except Exception as e:
            error_msg = f"Crossref fetch failed: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)

    # All sources failed
    error_summary = "Failed to fetch metadata from all sources:\n" + "\n".join(errors)
    raise CitationMetadataError(error_summary)
