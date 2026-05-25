"""Pilot workflow smoke: fetch an analytics report (PRODUCTION, read-only).

Dry-run validates the request wiring with no credentials (runs anywhere,
including CI). Live mode (``make smoke-live`` with a prod key present)
additionally checks the response, under flaky-API tolerance.

R9: in live mode the report path is a synthetic placeholder from the
gitignored ``smoke-data.json``; report rows are never printed.
"""
from __future__ import annotations

from almaapitk import Analytics
from almaapitk.testing import run_with_flaky_tolerance, smoke_input, workflow

# Dry-run never reaches a real API, so any path works for the request-check.
_DRY_RUN_PLACEHOLDER_PATH = "/shared/PLACEHOLDER/Reports/dry-run"


@workflow(name="analytics-report-fetch", environment="PRODUCTION", readonly=True)
def test_analytics_report_fetch(alma, request):
    live = request.node.alma_live
    report_path = (
        smoke_input("analytics_report_path") if live else _DRY_RUN_PLACEHOLDER_PATH
    )
    analytics = Analytics(alma)

    def _fetch():
        headers = analytics.get_report_headers(report_path)
        rows = list(analytics.fetch_report_rows(report_path, max_rows=5))
        return headers, rows

    if not live:
        # DRY-RUN: run the workflow against the recorder, then request-check.
        # Parsing the canned response is not under test here.
        try:
            _fetch()
        except Exception:
            pass
        calls = request.node.alma_transport.calls
        assert calls, "workflow issued no requests"
        assert any("analytics/reports" in (c.url or "") for c in calls), (
            "workflow did not hit the analytics reports endpoint"
        )
        return

    # LIVE (PROD, read-only): response-checks, under flaky tolerance.
    headers, rows = run_with_flaky_tolerance(_fetch, retries=2, delay=2.0)
    assert headers, "analytics report returned no column headers"
    assert rows, "analytics report returned no rows"
