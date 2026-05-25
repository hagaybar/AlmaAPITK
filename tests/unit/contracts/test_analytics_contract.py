"""L1 contract tests: the Analytics surface consumers depend on (issue #160).

These pin the exact `almaapitk` behaviors that consumer projects rely on —
modelled on `Fetch_Alma_Analytics_Reports/docs/almaapitk-0.4.5-audit.md`.
They run in the normal unit suite, on every change, with no credentials and
no network: the real `AlmaAPIClient` + `Analytics` code runs against canned
analytics responses fed through the harness's dry-run recorder.

If a future change alters one of these behaviors (a method renamed, a return
shape changed from a sized list to a lazy generator, a kwarg dropped, an
exception base class changed), the matching test goes red here — before any
version is cut — protecting every consumer at once.

R-H5: assertions are specific (shape + values), with no error-swallowing.
R9: all values are synthetic.
"""
from __future__ import annotations

import json

import pytest

from almaapitk import AlmaAPIClient, AlmaAPIError, AlmaValidationError, Analytics
from almaapitk.testing import build_smoke_client

# Proven-parseable analytics payloads (same shape as the Analytics domain's
# own unit-test fixtures). Schema response → headers; single-page rows
# response (IsFinished=true) → two rows, no pagination loop.
_SCHEMA_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<report xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:saw="urn:saw-sql">'
    "<xsd:schema>"
    '<xsd:element name="Column0" saw:columnHeading="MMS ID" type="xsd:string"/>'
    '<xsd:element name="Column1" saw:columnHeading="Title" type="xsd:string"/>'
    '<xsd:element name="Column2" saw:columnHeading="Author" type="xsd:string"/>'
    "</xsd:schema></report>"
)
_SINGLE_PAGE_ROWS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<report xmlns="urn:schemas-microsoft-com:xml-analysis:rowset">'
    "<Row><Column0>990000000000001</Column0><Column1>Synthetic One</Column1>"
    "<Column2>Author One</Column2></Row>"
    "<Row><Column0>990000000000002</Column0><Column1>Synthetic Two</Column1>"
    "<Column2>Author Two</Column2></Row>"
    "<IsFinished>true</IsFinished></report>"
)
_REPORT_PATH = "/shared/PLACEHOLDER/Reports/contract"


def _analytics_for(canned_xml: str):
    """Real AlmaAPIClient + Analytics, wired to return one canned analytics
    response (no creds, no network) via the harness dry-run recorder."""
    body = json.dumps({"anies": [canned_xml]}).encode()
    client, _ = build_smoke_client(
        environment="PRODUCTION",
        readonly=True,
        dry_run=True,
        api_key="contract-test",
        canned_response_factory=lambda req: (200, body, "application/json"),
    )
    return Analytics(client), client


# --- import + construction + error hierarchy ------------------------------


def test_consumer_symbols_are_importable():
    # The exact import the analytics consumer makes (runner.py).
    from almaapitk import (  # noqa: F401
        AlmaAPIClient,
        AlmaAPIError,
        AlmaValidationError,
        Analytics,
    )


def test_client_constructs_with_environment_positional():
    # Consumer calls AlmaAPIClient("PRODUCTION"); later params are keyword-only.
    client = AlmaAPIClient("PRODUCTION", api_key="contract-test")
    try:
        assert client.environment == "PRODUCTION"
    finally:
        client.close()


def test_error_hierarchy_is_stable():
    # runner.py catches (AlmaAPIError, AlmaValidationError, ValueError).
    assert issubclass(AlmaValidationError, ValueError)
    assert issubclass(AlmaAPIError, Exception)


# --- get_report_headers ---------------------------------------------------


def test_get_report_headers_returns_ordered_list_of_str():
    analytics, client = _analytics_for(_SCHEMA_XML)
    try:
        headers = analytics.get_report_headers(_REPORT_PATH)
    finally:
        client.close()
    assert isinstance(headers, list)
    assert all(isinstance(h, str) for h in headers)
    assert headers == ["MMS ID", "Title", "Author"]  # order preserved


# --- fetch_report_rows ----------------------------------------------------


def test_fetch_report_rows_returns_sized_list_of_column_dicts():
    analytics, client = _analytics_for(_SINGLE_PAGE_ROWS_XML)
    try:
        rows = analytics.fetch_report_rows(_REPORT_PATH)
    finally:
        client.close()
    # The consumer runner calls len(rows) — the result MUST be a materialised,
    # sized list, NOT a lazy generator.
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert all(isinstance(r, dict) for r in rows)
    assert rows[0]["Column0"] == "990000000000001"
    assert set(rows[0].keys()) == {"Column0", "Column1", "Column2"}


def test_fetch_report_rows_accepts_contract_kwargs_and_calls_progress_callback():
    analytics, client = _analytics_for(_SINGLE_PAGE_ROWS_XML)
    seen: list[int] = []
    try:
        rows = analytics.fetch_report_rows(
            _REPORT_PATH,
            limit=100,
            max_rows=5,
            progress_callback=lambda total: seen.append(total),
        )
    finally:
        client.close()
    assert len(rows) == 2
    assert seen, "progress_callback was never called"
    assert all(isinstance(n, int) for n in seen)


@pytest.mark.parametrize("bad_limit", [24, 1001])
def test_fetch_report_rows_rejects_out_of_bounds_limit(bad_limit):
    analytics, client = _analytics_for(_SINGLE_PAGE_ROWS_XML)
    try:
        with pytest.raises(AlmaValidationError):
            # AlmaValidationError is a ValueError, so the consumer's
            # `except (... ValueError)` keeps catching it.
            list(_as_iter(analytics.fetch_report_rows(_REPORT_PATH, limit=bad_limit)))
    finally:
        client.close()


def _as_iter(value):
    """Force evaluation whether the bounds check is eager or lazy."""
    return value if isinstance(value, list) else list(value)
