"""Behaviour-lock test for issue #165 — multi-page analytics pagination.

The 2026-05-29 audit hypothesised that `fetch_report_rows` truncates reports of
3+ pages, on the premise that Alma returns the resumption token *only on the
first page* (so pages 2+ would parse to None and the loop's
`if not resumption_token: break` would fire early).

Production logs of a real multi-page fetch (2026-05-30) disprove that premise:
**every** page request carries the *same* resumption token, page after page,
until the report is exhausted. So `resumption_token` never goes empty mid-stream
and the loop terminates on `IsFinished=true`, not on token absence — the report
downloads in full.

This test pins that real behaviour (same token reused across all pages, finish
on IsFinished) so a future change can't reintroduce the truncation the audit
feared. It also closes the test-masking gap the audit noted: the existing unit
fixtures set IsFinished=true on page 2 and never reach a 3rd page.

R9: synthetic path/token only — no real report path or live token here.
"""
from unittest.mock import MagicMock

from almaapitk.domains.analytics import Analytics


def _analytics():
    client = MagicMock()
    client.get_environment.return_value = "SANDBOX"
    return Analytics(client), client


def test_multipage_fetch_reuses_same_token_and_returns_all_rows():
    analytics, client = _analytics()
    TOKEN = "SAME_SESSION_TOKEN"
    # Mirrors the prod log: same token on every page; IsFinished only on the last.
    pages = iter(
        [
            ([{"Column0": "r1"}], TOKEN, False),  # page 1
            ([{"Column0": "r2"}], TOKEN, False),  # page 2 — same token, not finished
            ([{"Column0": "r3"}], TOKEN, True),   # page 3 — same token, finished
        ]
    )
    analytics._extract_xml_from_response = lambda response: "<rows/>"
    analytics._parse_rows_from_xml = lambda xml: next(pages)

    rows = analytics.fetch_report_rows("/shared/report", limit=1000)

    # All three pages must be returned — no truncation at page 2.
    assert [r["Column0"] for r in rows] == ["r1", "r2", "r3"]

    # The page-1 token must be re-sent on every subsequent request, matching the
    # live log (first request has no token; pages 2+ reuse the same one).
    sent_tokens = [
        c.kwargs["params"].get("token") for c in client.get.call_args_list
    ]
    assert sent_tokens == [None, TOKEN, TOKEN]
