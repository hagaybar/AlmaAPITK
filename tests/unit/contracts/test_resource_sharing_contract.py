"""L1 contract tests: the ResourceSharing surface consumers depend on.

These pin the exact `almaapitk` behaviors the
`Alma-RS-lending-request-automation` consumer relies on — audited from its
`from almaapitk import ...` lines and its `rs.*` call sites (create lending
requests directly and from PubMed/Crossref citations, retrieve them, and
summarize them).

They run in the normal unit suite, on every change, with no credentials and
no network: the real `AlmaAPIClient` + `ResourceSharing` code runs against
canned responses fed through the harness's dry-run recorder. The POST path
uses a writable SANDBOX smoke client (PRODUCTION is read-only — R-H2); the
RecordingTransport intercepts the write so no I/O happens.

If a future change alters one of these behaviors (a method renamed, the
`owner` field silently wrapped, a return shape changed, an exception base
class changed, validation moved server-side), the matching test goes red here
— before any version is cut — protecting the consumer at once.

R-H5: assertions are specific (shape + values), with no error-swallowing.
R9: all values are synthetic placeholders.
"""
from __future__ import annotations

import json

import pytest

from almaapitk import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaValidationError,
    ResourceSharing,
)
from almaapitk.testing import build_smoke_client

# Synthetic placeholders (R9 — never real partner codes / IDs / titles).
_PARTNER = "EXAMPLE_PARTNER"
_OWNER = "MAIN"
_EXTERNAL_ID = "EXT-CONTRACT-001"
_TITLE = "Synthetic Title for Contract Test"
_REQUEST_ID = "RS-CONTRACT-0001"


def _rs_for(canned: dict):
    """Real AlmaAPIClient + ResourceSharing, wired to return one canned JSON
    response (no creds, no network) via the harness dry-run recorder.

    SANDBOX + readonly=False so the create POST is allowed; dry-run records it.
    """
    body = json.dumps(canned).encode()
    client, transport = build_smoke_client(
        environment="SANDBOX",
        readonly=False,
        dry_run=True,
        api_key="contract-test",
        canned_response_factory=lambda req: (200, body, "application/json"),
    )
    return ResourceSharing(client), client, transport


# --- imports + construction + error hierarchy ------------------------------


def test_consumer_symbols_are_importable():
    # The exact imports the RS-lending consumer makes across its modules.
    from almaapitk import (  # noqa: F401
        AlmaAPIClient,
        AlmaAPIError,
        CitationMetadataError,
        ResourceSharing,
        Users,
    )
    from almaapitk.utils.citation_metadata import (  # noqa: F401
        enrich_citation_metadata,
    )


def test_resource_sharing_constructs_with_client():
    client = AlmaAPIClient("SANDBOX", api_key="contract-test")
    try:
        rs = ResourceSharing(client)
        assert rs.client is client
    finally:
        client.close()


def test_error_hierarchy_is_stable():
    # The consumer catches (AlmaAPIError, ValueError); validation failures must
    # stay a ValueError subclass so its `except ValueError` keeps catching them.
    assert issubclass(AlmaValidationError, ValueError)
    assert issubclass(AlmaAPIError, Exception)


# --- create_lending_request ------------------------------------------------


def test_create_lending_request_returns_dict_with_request_id():
    rs, client, _ = _rs_for({"request_id": _REQUEST_ID, "title": _TITLE})
    try:
        result = rs.create_lending_request(
            partner_code=_PARTNER,
            external_id=_EXTERNAL_ID,
            owner=_OWNER,
            format_type="PHYSICAL",
            title=_TITLE,
            citation_type="BOOK",
        )
    finally:
        client.close()
    assert isinstance(result, dict)
    assert result["request_id"] == _REQUEST_ID


def test_create_lending_request_sends_owner_plain_partner_and_format_wrapped():
    # The load-bearing quirk: `owner` is a PLAIN STRING on create; `partner`
    # and `format` are wrapped {"value": ...}. If almaapitk ever regresses to
    # wrapping `owner`, the consumer's real POSTs would 400 — catch it here.
    rs, client, transport = _rs_for({"request_id": _REQUEST_ID})
    try:
        rs.create_lending_request(
            partner_code=_PARTNER,
            external_id=_EXTERNAL_ID,
            owner=_OWNER,
            format_type="PHYSICAL",
            title=_TITLE,
            citation_type="BOOK",
        )
    finally:
        client.close()
    body = transport.calls[-1].body
    assert body["owner"] == _OWNER  # plain string, NOT {"value": ...}
    assert body["partner"] == {"value": _PARTNER}
    assert body["format"] == {"value": "PHYSICAL"}
    assert body["citation_type"] == {"value": "BOOK"}


def test_create_lending_request_posts_to_lending_requests_endpoint():
    rs, client, transport = _rs_for({"request_id": _REQUEST_ID})
    try:
        rs.create_lending_request(
            partner_code=_PARTNER,
            external_id=_EXTERNAL_ID,
            owner=_OWNER,
            format_type="PHYSICAL",
            title=_TITLE,
            citation_type="BOOK",
        )
    finally:
        client.close()
    call = transport.calls[-1]
    assert call.method == "POST"
    assert call.url.endswith(
        f"almaws/v1/partners/{_PARTNER}/lending-requests"
    )


def test_create_lending_request_missing_owner_raises_valueerror_before_any_request():
    rs, client, transport = _rs_for({"request_id": _REQUEST_ID})
    try:
        with pytest.raises(ValueError):
            rs.create_lending_request(
                partner_code=_PARTNER,
                external_id=_EXTERNAL_ID,
                owner="",  # missing mandatory owner
                format_type="PHYSICAL",
                title=_TITLE,
                citation_type="BOOK",
            )
        # Outside the raises-block so it actually runs: validation is
        # client-side, so no HTTP request was ever attempted.
        assert transport.calls == []
    finally:
        client.close()


# --- get_lending_request ---------------------------------------------------


def test_get_lending_request_returns_dict_and_uses_get():
    rs, client, transport = _rs_for(
        {"request_id": _REQUEST_ID, "title": _TITLE}
    )
    try:
        result = rs.get_lending_request(_PARTNER, _REQUEST_ID)
    finally:
        client.close()
    assert isinstance(result, dict)
    assert result["request_id"] == _REQUEST_ID
    call = transport.calls[-1]
    assert call.method == "GET"
    assert call.url.endswith(
        f"almaws/v1/partners/{_PARTNER}/lending-requests/{_REQUEST_ID}"
    )


# --- get_request_summary ---------------------------------------------------


def test_get_request_summary_returns_documented_keys():
    rs, client, _ = _rs_for({})
    try:
        summary = rs.get_request_summary(
            {
                "request_id": _REQUEST_ID,
                "external_id": _EXTERNAL_ID,
                "title": _TITLE,
                "author": "Synthetic, Author",
                "citation_type": {"value": "BOOK"},
                "format": {"value": "PHYSICAL"},
                "status": {"value": "REQUEST_CREATED_LEN"},
                "partner": {"value": _PARTNER},
                "owner": _OWNER,
            }
        )
    finally:
        client.close()
    assert set(summary.keys()) == {
        "request_id",
        "external_id",
        "title",
        "author",
        "citation_type",
        "format",
        "status",
        "partner",
        "owner",
    }
    # Nested code-table values are unwrapped to their .value.
    assert summary["status"] == "REQUEST_CREATED_LEN"
    assert summary["format"] == "PHYSICAL"
    assert summary["request_id"] == _REQUEST_ID


# --- create_lending_request_from_citation ----------------------------------


def test_create_lending_request_from_citation_enriches_and_delegates(monkeypatch):
    # The consumer's primary runtime path. Patch the external metadata fetch
    # (PubMed/Crossref — the only unavoidable network dependency); the contract
    # is that enriched fields flow into a normal create POST that returns a dict.
    def _fake_enrich(pmid=None, doi=None, source_type=None):
        return {
            "source": "pmid",
            "title": _TITLE,
            "author": "Synthetic, Author",
            "year": "2024",
            "journal": "Synthetic Journal",
            "pmid": pmid,
        }

    monkeypatch.setattr(
        "almaapitk.utils.citation_metadata.enrich_citation_metadata",
        _fake_enrich,
    )

    rs, client, transport = _rs_for({"request_id": _REQUEST_ID})
    try:
        result = rs.create_lending_request_from_citation(
            partner_code=_PARTNER,
            external_id=_EXTERNAL_ID,
            owner=_OWNER,
            format_type="DIGITAL",
            pmid="00000000",
            source_type="pmid",
        )
    finally:
        client.close()
    assert isinstance(result, dict)
    assert result["request_id"] == _REQUEST_ID
    # Enriched title made it into the POST body, owner still plain string.
    body = transport.calls[-1].body
    assert body["title"] == _TITLE
    assert body["owner"] == _OWNER
