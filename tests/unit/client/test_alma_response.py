"""
Unit tests for ``AlmaResponse`` body-caching and ``_safe_response_body``.

These tests pin the behaviour added in GitHub issue #16:

- ``AlmaResponse.data`` and ``AlmaResponse.json()`` cache the parsed body
  so ``self._response.json()`` is called at most once across repeated
  ``.data``/``.json()`` access (and the debug-body-logging path that the
  client routes through ``_safe_body``).
- The module-level ``_safe_response_body`` helper is the single
  decision point for "should we parse this body": it returns the
  parsed dict for ``application/json`` bodies, ``None`` for non-JSON
  content-types, and ``None`` for malformed JSON.
- The narrowed ``except`` clauses in the client module do **not** mask
  ``KeyboardInterrupt``: a JSON-decode path that raises
  ``KeyboardInterrupt`` propagates instead of being swallowed.

Pattern source: ``tests/unit/client/test_alma_api_client.py`` and
``tests/unit/client/test_context_manager.py`` -- same module style and
``MagicMock(spec=requests.Response)`` idiom.
"""

import json
import unittest
from unittest.mock import MagicMock

import requests

from almaapitk.client.AlmaAPIClient import (
    AlmaResponse,
    _safe_response_body,
)


def _make_mock_response(
    status_code: int = 200,
    json_body=None,
    content_type: str = 'application/json',
    text: str = '',
    json_side_effect=None,
):
    """Build a minimal ``requests.Response``-like mock.

    Mirrors the helper used in ``test_alma_api_client.py`` and
    ``test_context_manager.py`` so all client-tier tests speak the same
    vocabulary. The only twist is ``json_side_effect``, which lets a
    test wire ``.json()`` to raise on demand without giving up the
    ``MagicMock``'s call-count tracking.
    """
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.ok = status_code < 400
    mock_response.headers = {'content-type': content_type}
    mock_response.text = text
    mock_response.content = (text or json.dumps(json_body or {})).encode()
    if json_side_effect is not None:
        mock_response.json.side_effect = json_side_effect
    else:
        if json_body is None:
            json_body = {}
        mock_response.json.return_value = json_body
    return mock_response


class TestAlmaResponseDataCaching(unittest.TestCase):
    """Tests for AC: ``.data`` parses at most once per response."""

    def test_data_parses_only_once_across_repeated_access(self):
        """Three ``.data`` reads should call ``response.json`` exactly once.

        This is the headline acceptance criterion for issue #16 --
        repeated access (``if r.data and r.data.get('x'):`` and friends)
        must not re-parse on every read.
        """
        mock_response = _make_mock_response(json_body={'foo': 'bar'})
        wrapper = AlmaResponse(mock_response)

        first = wrapper.data
        second = wrapper.data
        third = wrapper.data

        self.assertEqual(mock_response.json.call_count, 1)
        # All three reads return the same parsed object (cache identity,
        # not just equality).
        self.assertIs(first, second)
        self.assertIs(second, third)
        self.assertEqual(first, {'foo': 'bar'})

    def test_json_and_data_share_cache(self):
        """``.json()`` and ``.data`` must hit the same cache slot.

        Calling ``.json()`` once then ``.data`` twice should still result
        in exactly one underlying parse.
        """
        mock_response = _make_mock_response(json_body={'a': 1})
        wrapper = AlmaResponse(mock_response)

        wrapper.json()
        wrapper.data
        wrapper.data

        self.assertEqual(mock_response.json.call_count, 1)

    def test_safe_body_and_data_share_cache(self):
        """The internal ``_safe_body`` (debug-log path) shares the cache.

        Pins the "called at most once across .json(), .data, and the
        debug-body-logging path" wording from the AC: the client uses
        ``_safe_body`` to log the body, then the caller reads ``.data``,
        and the underlying ``response.json`` should fire only once.
        """
        mock_response = _make_mock_response(json_body={'k': 'v'})
        wrapper = AlmaResponse(mock_response)

        wrapper._safe_body()  # debug-logging path
        wrapper.data           # caller path
        wrapper.json()         # belt-and-braces

        self.assertEqual(mock_response.json.call_count, 1)


class TestAlmaResponseEmptyBody(unittest.TestCase):
    """Tests for the empty/non-JSON body edge cases on ``.data``."""

    def test_safe_body_returns_none_for_non_json_content_type(self):
        """Non-JSON content-type must short-circuit without parsing.

        A response advertising ``text/xml`` should never have
        ``response.json()`` called -- the helper recognises the
        content-type and returns ``None`` outright.
        """
        mock_response = _make_mock_response(
            json_body={'should': 'not be parsed'},
            content_type='application/xml',
            text='<root/>',
        )
        wrapper = AlmaResponse(mock_response)

        result = wrapper._safe_body()

        self.assertIsNone(result)
        self.assertEqual(mock_response.json.call_count, 0)


class TestSafeResponseBodyHelper(unittest.TestCase):
    """Tests for the module-level ``_safe_response_body`` helper.

    The helper is the single decision point for "should we attempt to
    parse this body" -- per AC #3 of issue #16. Three branches matter:
    valid JSON, non-JSON content-type, malformed JSON.
    """

    def test_returns_parsed_dict_for_valid_json(self):
        """A clean ``application/json`` body should round-trip to a dict."""
        mock_response = _make_mock_response(json_body={'x': 1, 'y': 2})

        result = _safe_response_body(mock_response)

        self.assertEqual(result, {'x': 1, 'y': 2})
        self.assertEqual(mock_response.json.call_count, 1)

    def test_returns_none_for_non_json_content_type(self):
        """A non-JSON content-type must skip parsing entirely.

        ``response.json()`` should never be invoked on, e.g., XML
        responses -- the helper returns ``None`` purely from the
        content-type sniff.
        """
        mock_response = _make_mock_response(
            content_type='application/xml', text='<root/>'
        )

        result = _safe_response_body(mock_response)

        self.assertIsNone(result)
        self.assertEqual(mock_response.json.call_count, 0)

    def test_returns_none_for_malformed_json(self):
        """A malformed JSON body must collapse to ``None``, not raise.

        This is the contract that lets the debug-logging caller in
        ``_request`` route through the helper without wrapping every
        call site in its own ``try``/``except``.
        """
        mock_response = _make_mock_response(
            json_side_effect=ValueError('not json'),
        )

        result = _safe_response_body(mock_response)

        self.assertIsNone(result)


class TestNoBareExceptInJsonDecodePath(unittest.TestCase):
    """Tests for AC: bare ``except:`` clauses are gone.

    The strongest runtime check that the bare ``except:`` clauses were
    properly narrowed (per issue #16 problem #1) is that
    ``KeyboardInterrupt`` -- a ``BaseException`` subclass that bare
    ``except:`` would have swallowed -- now propagates through the
    JSON-decode path.
    """

    def test_keyboard_interrupt_propagates_through_safe_response_body(self):
        """``_safe_response_body`` must not swallow ``KeyboardInterrupt``.

        Pre-#16 the helper had a bare ``except:`` around ``response.json()``
        which would have caught ``KeyboardInterrupt`` -- a denial-of-service
        for the operator trying to ``Ctrl-C`` out of a long run.
        """
        mock_response = _make_mock_response(
            json_side_effect=KeyboardInterrupt(),
        )

        with self.assertRaises(KeyboardInterrupt):
            _safe_response_body(mock_response)

    def test_keyboard_interrupt_propagates_through_alma_response_safe_body(self):
        """``AlmaResponse._safe_body`` must not swallow ``KeyboardInterrupt``.

        Same guard as the helper-level test, exercised through the
        wrapper's debug-logging entry point.
        """
        mock_response = _make_mock_response(
            json_side_effect=KeyboardInterrupt(),
        )
        wrapper = AlmaResponse(mock_response)

        with self.assertRaises(KeyboardInterrupt):
            wrapper._safe_body()


if __name__ == '__main__':
    unittest.main()
