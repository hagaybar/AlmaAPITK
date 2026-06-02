"""L1 contract tests: the BibliographicRecords collection surface consumers
depend on.

These pin the exact `almaapitk` behaviors the `Update_Alma_Digital_Collections`
consumer (prod: `Update_Digital_Collections`) relies on — audited from its
`from almaapitk import AlmaAPIClient, BibliographicRecords, AlmaAPIError` and
its `self.bibs.*` call sites in `AlmaCollectionManager_6.py`:

- `get_collection_members(...)` → the consumer reads
  `response.json()["total_record_count"]` (with `limit=1` to fetch just the
  count, then `limit=100, offset=...` to page).
- `add_to_collection(collection_id, mms_id)` and
  `remove_from_collection(collection_id, mms_id)` → called for their effect;
  the consumer counts successes and relies on the right verb/endpoint.

This consumer is pinned far back (`almaapitk >= 0.3.1`); the bump to the
current release crosses a lot of changes, so these contracts (plus the repo's
own live SANDBOX smoke) are what de-risk that jump and guard against future
drift. They run in the normal unit suite with no creds and no network: the
real `AlmaAPIClient` + `BibliographicRecords` code runs against canned
responses via the harness dry-run recorder. The write paths use a SANDBOX
writable smoke client (PRODUCTION is read-only — R-H2).

R-H5: assertions are specific (shape + values), no error-swallowing.
R9: all values are synthetic placeholders.
"""
from __future__ import annotations

import json

import pytest

from almaapitk import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaValidationError,
    BibliographicRecords,
)
from almaapitk.testing import build_smoke_client

# Synthetic placeholders (R9 — never real collection/MMS IDs).
_COLLECTION_ID = "81000000000000000"
_MMS_ID = "99000000000000000"


def _bibs_for(canned: dict):
    """Real AlmaAPIClient + BibliographicRecords, wired to return one canned
    JSON response (no creds, no network) via the harness dry-run recorder.

    SANDBOX + readonly=False so the POST/DELETE write paths are allowed;
    dry-run records them so no I/O happens.
    """
    body = json.dumps(canned).encode()
    client, transport = build_smoke_client(
        environment="SANDBOX",
        readonly=False,
        dry_run=True,
        api_key="contract-test",
        canned_response_factory=lambda req: (200, body, "application/json"),
    )
    return BibliographicRecords(client), client, transport


# --- imports + construction + error hierarchy ------------------------------


def test_consumer_symbols_are_importable():
    from almaapitk import (  # noqa: F401
        AlmaAPIClient,
        AlmaAPIError,
        BibliographicRecords,
    )


def test_bibs_constructs_with_client():
    client = AlmaAPIClient("SANDBOX", api_key="contract-test")
    try:
        bibs = BibliographicRecords(client)
        assert bibs.client is client
    finally:
        client.close()


def test_error_hierarchy_is_stable():
    assert issubclass(AlmaValidationError, ValueError)
    assert issubclass(AlmaAPIError, Exception)


# --- get_collection_members ------------------------------------------------


def test_get_collection_members_exposes_total_record_count_via_json():
    # The consumer's exact dependency: response.json()["total_record_count"].
    bibs, client, _ = _bibs_for(
        {"total_record_count": 2, "bib": [{"mms_id": _MMS_ID}]}
    )
    try:
        response = bibs.get_collection_members(_COLLECTION_ID, limit=1)
    finally:
        client.close()
    assert response.json()["total_record_count"] == 2


def test_get_collection_members_issues_get_to_collection_bibs_with_paging():
    bibs, client, transport = _bibs_for({"total_record_count": 0})
    try:
        bibs.get_collection_members(_COLLECTION_ID, limit=100, offset=200)
    finally:
        client.close()
    call = transport.calls[-1]
    assert call.method == "GET"
    assert call.url.endswith(
        f"almaws/v1/bibs/collections/{_COLLECTION_ID}/bibs"
    )
    # limit/offset are forwarded as query params (current code stringifies them).
    assert call.params == {"limit": "100", "offset": "200"}


# --- add_to_collection -----------------------------------------------------


def test_add_to_collection_posts_mms_id_to_collection_bibs_endpoint():
    bibs, client, transport = _bibs_for({"mms_id": _MMS_ID})
    try:
        bibs.add_to_collection(_COLLECTION_ID, _MMS_ID)
    finally:
        client.close()
    call = transport.calls[-1]
    assert call.method == "POST"
    assert call.url.endswith(
        f"almaws/v1/bibs/collections/{_COLLECTION_ID}/bibs"
    )
    assert call.body == {"mms_id": _MMS_ID}


# --- remove_from_collection ------------------------------------------------


def test_remove_from_collection_deletes_at_collection_bib_path():
    bibs, client, transport = _bibs_for({})
    try:
        bibs.remove_from_collection(_COLLECTION_ID, _MMS_ID)
    finally:
        client.close()
    call = transport.calls[-1]
    assert call.method == "DELETE"
    assert call.url.endswith(
        f"almaws/v1/bibs/collections/{_COLLECTION_ID}/bibs/{_MMS_ID}"
    )


# --- client-side validation (no request attempted) -------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda bibs: bibs.get_collection_members(""),
        lambda bibs: bibs.add_to_collection("", _MMS_ID),
        lambda bibs: bibs.remove_from_collection("", _MMS_ID),
    ],
)
def test_collection_methods_require_collection_id(call):
    bibs, client, transport = _bibs_for({})
    try:
        with pytest.raises(AlmaValidationError):
            call(bibs)
        # Outside the raises-block so it runs: validation is client-side, so
        # no HTTP request was attempted.
        assert transport.calls == []
    finally:
        client.close()


@pytest.mark.parametrize(
    "call",
    [
        lambda bibs: bibs.add_to_collection(_COLLECTION_ID, ""),
        lambda bibs: bibs.remove_from_collection(_COLLECTION_ID, ""),
    ],
)
def test_collection_writes_require_mms_id(call):
    bibs, client, transport = _bibs_for({})
    try:
        with pytest.raises(AlmaValidationError):
            call(bibs)
        assert transport.calls == []
    finally:
        client.close()
