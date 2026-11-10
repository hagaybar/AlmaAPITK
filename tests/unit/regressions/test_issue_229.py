"""R10 regression tests for issue #229.

``Analytics.fetch_report_rows()`` looped until Alma said ``IsFinished=true``
or stopped sending a ``ResumptionToken``. A report stuck server-side (Alma
answering ``IsFinished=false`` + token + no rows, forever) made it request
Alma without end, and nothing could stop it: exceptions from
``progress_callback`` are swallowed.

Covered here, with a scripted fake client (no network) and ``time.sleep``
patched out:

* endless empty pages raise ``AlmaAnalyticsStalledError`` (an
  ``AlmaAPIError``) within ``max_empty_pages`` requests;
* no new rows for ``max_stall_seconds`` raises the same error;
* endless pages with rows stop at ``max_pages`` when it is set;
* a few empty pages, then rows, completes and backs off between empties;
* the same token reused on every page is not mistaken for a stall;
* ``should_stop`` raises ``AlmaOperationCancelled`` and sends no more
  requests, including mid-backoff;
* ``progress_callback`` exceptions are still swallowed;
* the client's default ``Retry`` caps ``Retry-After`` at 120 s.

Every fake client refuses to answer more than ``_HARD_LIMIT`` requests, so a
regression fails fast instead of hanging the suite.
"""
import json
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from almaapitk import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaAnalyticsStalledError,
    AlmaOperationCancelled,
    Analytics,
)

_HARD_LIMIT = 200
_REPORT = "/shared/PLACEHOLDER/Reports/stall"
_SLEEP = "almaapitk.domains.analytics.time.sleep"
_CLOCK = "almaapitk.domains.analytics.time.monotonic"


def _page(n_rows: int, start: int = 0, finished: bool = False,
          token: Optional[str] = "TOKEN-A") -> str:
    rows = "".join(
        f"<Row><Column0>{start + i}</Column0></Row>" for i in range(n_rows)
    )
    token_xml = f"<ResumptionToken>{token}</ResumptionToken>" if token else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<report xmlns="urn:schemas-microsoft-com:xml-analysis:rowset">'
        f"{rows}{token_xml}<IsFinished>{'true' if finished else 'false'}"
        "</IsFinished></report>"
    )


class _Response:
    def __init__(self, xml: str):
        self._body = {"anies": [xml]}

    def json(self):
        return self._body


class _FakeClient:
    """Answers each GET with the next scripted page; the last one repeats."""

    def __init__(self, pages: List[str]):
        self.pages = pages
        self.calls = 0
        self.logger = MagicMock()

    def get(self, endpoint, params=None, custom_headers=None):
        self.calls += 1
        if self.calls > _HARD_LIMIT:
            raise RuntimeError("fetch_report_rows never stopped (issue #229)")
        return _Response(self.pages[min(self.calls, len(self.pages)) - 1])


def _analytics(pages: List[str]):
    client = _FakeClient(pages)
    return Analytics(client), client


def test_new_errors_are_alma_api_errors():
    assert issubclass(AlmaAnalyticsStalledError, AlmaAPIError)
    assert issubclass(AlmaOperationCancelled, AlmaAPIError)


@patch(_SLEEP)
def test_endless_empty_pages_raise_stalled(mock_sleep):
    analytics, client = _analytics([_page(0)])
    with pytest.raises(AlmaAnalyticsStalledError) as exc_info:
        analytics.fetch_report_rows(_REPORT)
    assert client.calls <= 20 + 1
    assert "20" in str(exc_info.value)


@patch(_SLEEP)
def test_custom_max_empty_pages(mock_sleep):
    analytics, client = _analytics([_page(5), _page(0)])
    with pytest.raises(AlmaAnalyticsStalledError) as exc_info:
        analytics.fetch_report_rows(_REPORT, max_empty_pages=3)
    assert client.calls == 1 + 3
    assert "5 rows" in str(exc_info.value)


def test_no_new_rows_for_max_stall_seconds_raises_stalled():
    analytics, client = _analytics([_page(0)])
    clock = iter(range(0, 10_000, 100))  # each reading advances 100 s
    with patch(_SLEEP), patch(_CLOCK, side_effect=lambda: next(clock)):
        with pytest.raises(AlmaAnalyticsStalledError):
            analytics.fetch_report_rows(
                _REPORT, max_empty_pages=1000, max_stall_seconds=600
            )
    assert client.calls < 20


@patch(_SLEEP)
def test_endless_pages_with_rows_stop_at_max_pages(mock_sleep):
    analytics, client = _analytics([_page(25)])
    with pytest.raises(AlmaAnalyticsStalledError):
        analytics.fetch_report_rows(_REPORT, limit=25, max_pages=5)
    assert client.calls == 5


@patch(_SLEEP)
def test_empty_pages_then_rows_completes_with_backoff(mock_sleep):
    pages = [_page(0), _page(0), _page(0), _page(2, 0), _page(1, 2, finished=True)]
    analytics, client = _analytics(pages)
    rows = analytics.fetch_report_rows(_REPORT)
    assert [r["Column0"] for r in rows] == ["0", "1", "2"]
    assert client.calls == 5
    waited = sum(c.args[0] for c in mock_sleep.call_args_list)
    assert waited == pytest.approx(2 + 4 + 8)


@patch(_SLEEP)
def test_backoff_is_capped_at_30_seconds(mock_sleep):
    analytics, _ = _analytics([_page(0)])
    with pytest.raises(AlmaAnalyticsStalledError):
        analytics.fetch_report_rows(_REPORT, max_empty_pages=10)
    assert max(c.args[0] for c in mock_sleep.call_args_list) <= 30


@patch(_SLEEP)
def test_same_token_reused_is_not_a_stall(mock_sleep):
    pages = [_page(25, i * 25, token="SAME") for i in range(30)]
    pages.append(_page(3, 750, finished=True, token="SAME"))
    analytics, client = _analytics(pages)
    rows = analytics.fetch_report_rows(_REPORT, limit=25)
    assert len(rows) == 753
    assert client.calls == 31
    mock_sleep.assert_not_called()


@patch(_SLEEP)
def test_should_stop_cancels_before_the_next_request(mock_sleep):
    analytics, client = _analytics([_page(25)])
    with pytest.raises(AlmaOperationCancelled):
        analytics.fetch_report_rows(
            _REPORT, limit=25, should_stop=lambda: client.calls >= 3
        )
    assert client.calls == 3


@patch(_SLEEP)
def test_should_stop_cancels_during_backoff(mock_sleep):
    analytics, client = _analytics([_page(0)])
    ticks = {"n": 0}

    def stop():
        ticks["n"] += 1
        return ticks["n"] > 3  # first request + a couple of backoff ticks

    with pytest.raises(AlmaOperationCancelled):
        analytics.fetch_report_rows(_REPORT, should_stop=stop)
    assert client.calls == 1


@patch(_SLEEP)
def test_progress_callback_errors_still_swallowed(mock_sleep):
    analytics, _ = _analytics([_page(2, 0), _page(1, 2, finished=True)])

    def boom(total):
        raise RuntimeError("consumer callback bug")

    rows = analytics.fetch_report_rows(_REPORT, progress_callback=boom)
    assert len(rows) == 3


@pytest.mark.parametrize("kwargs", [
    {"max_pages": 0},
    {"max_empty_pages": 0},
    {"max_stall_seconds": 0},
    {"empty_page_delay": -1},
    {"should_stop": "not callable"},
])
def test_new_kwargs_are_validated(kwargs):
    from almaapitk import AlmaValidationError
    analytics, client = _analytics([_page(1, finished=True)])
    with pytest.raises(AlmaValidationError):
        analytics.fetch_report_rows(_REPORT, **kwargs)
    assert client.calls == 0


def test_default_retry_caps_retry_after_at_120_seconds(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", "placeholder-for-unit-test")
    client = AlmaAPIClient("SANDBOX")
    try:
        retries = {
            adapter.max_retries for adapter in client._session.adapters.values()
        }
        assert retries, "no adapters mounted"
        response = MagicMock()
        response.headers = {"Retry-After": "21600"}
        response.getheader = lambda name, default=None: response.headers.get(name, default)
        for retry in retries:
            assert retry.retry_after_max == 120
            assert retry.get_retry_after(response) == 120
            # The cap survives urllib3's per-attempt Retry.new() copies.
            assert retry.new(total=1).retry_after_max == 120
    finally:
        client.close()
