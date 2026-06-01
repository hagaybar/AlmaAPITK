"""R10 regression test for issue #177 — fetch_report_rows limit/max_rows type.

``Analytics.fetch_report_rows`` compared ``limit``/``max_rows`` against integer
bounds and then did ``str(limit)`` without ever coercing to ``int``. A consumer
that read ``limit`` from a JSON config or CLI argument (where it arrives as a
**string**) crashed with a raw ``TypeError`` before any API call; a **float**
limit silently reached Alma as the invalid token ``"1000.0"``. Same string/int
class as #164.

The fix coerces ``limit`` and ``max_rows`` to ``int`` up front (clear
``AlmaValidationError`` on non-coercible input). These tests drive the method
with string/float values and assert it runs and sends a clean integer ``limit``.
"""
import pytest

from unittest.mock import MagicMock

from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.analytics import Analytics


def _analytics(rows=None, finished=True):
    client = MagicMock()
    client.get_environment.return_value = "SANDBOX"
    analytics = Analytics(client)
    # Drive one controlled page through the loop without real HTTP/XML.
    analytics._extract_xml_from_response = lambda response: "<rows/>"
    analytics._parse_rows_from_xml = lambda xml: (rows or [], None, finished)
    return analytics, client


def _sent_limit(client):
    return client.get.call_args.kwargs["params"]["limit"]


def test_string_limit_is_coerced_and_runs():
    analytics, client = _analytics(rows=[{"Column0": "v"}])

    result = analytics.fetch_report_rows("/shared/report", limit="1000")

    assert result == [{"Column0": "v"}]
    assert _sent_limit(client) == "1000"


def test_float_limit_sent_as_clean_int_string():
    analytics, client = _analytics(rows=[])

    analytics.fetch_report_rows("/shared/report", limit=1000.0)

    # Must be "1000", not "1000.0" (the latter is an invalid Alma limit value).
    assert _sent_limit(client) == "1000"


def test_string_max_rows_is_coerced():
    analytics, client = _analytics(rows=[{"Column0": "v"}])

    result = analytics.fetch_report_rows("/shared/report", limit=1000, max_rows="500")

    assert result == [{"Column0": "v"}]


def test_non_numeric_limit_raises_validation_error():
    analytics, _ = _analytics()

    with pytest.raises(AlmaValidationError):
        analytics.fetch_report_rows("/shared/report", limit="lots")
