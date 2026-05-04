"""
Unit tests for AlmaAPIClient HTTP plumbing.

These tests verify the persistent ``requests.Session`` introduced in
GitHub issue #3 (HTTP: use a persistent requests.Session for connection
pooling). They patch ``requests.Session.request`` so no real network
calls are made and assert that:

- A single ``requests.Session`` is created in ``__init__``.
- All four HTTP verb methods (get/post/put/delete) route through that
  session via ``self._session.request(...)``.
- Per-call ``custom_headers`` still merge over session-level headers
  (the old per-call override semantics are preserved).
- The same session instance is reused across multiple calls.

Pattern source: existing unit tests under tests/unit/domains/ and the
issue's acceptance criteria.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import (
    AlmaValidationError,
    _safe_response_body,
)


def _make_mock_response(
    status_code: int = 200,
    json_body=None,
    content_type: str = 'application/json',
):
    """Build a minimal ``requests.Response``-like mock for tests.

    We avoid constructing a real ``requests.Response`` because the client
    only touches a handful of attributes/methods on the response object.
    """
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.ok = status_code < 400
    mock_response.headers = {'content-type': content_type}
    mock_response.text = ''
    if json_body is None:
        json_body = {}
    mock_response.json.return_value = json_body
    return mock_response


class _AlmaAPIClientTestBase(unittest.TestCase):
    """Shared setUp that injects a fake API key into the environment.

    ``AlmaAPIClient.__init__`` calls ``_load_configuration`` which reads
    ``ALMA_SB_API_KEY`` from the environment. We patch the env so the
    client can be constructed in isolation, with no real key on disk.
    """

    def setUp(self):
        self._env_patcher = patch.dict(
            os.environ, {'ALMA_SB_API_KEY': 'test-sandbox-key'}, clear=False
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)


class TestSessionCreation(_AlmaAPIClientTestBase):
    """Tests for AC-1: a single ``requests.Session`` is created in init."""

    def test_init_creates_session(self):
        """``client._session`` should be a ``requests.Session`` instance."""
        client = AlmaAPIClient('SANDBOX')
        self.assertTrue(hasattr(client, '_session'))
        self.assertIsInstance(client._session, requests.Session)

    def test_session_has_default_auth_headers(self):
        """Session-level headers should carry the apikey Authorization."""
        client = AlmaAPIClient('SANDBOX')
        # Default headers live on the session per issue #3.
        self.assertEqual(
            client._session.headers.get('Authorization'),
            'apikey test-sandbox-key',
        )


class TestVerbsRouteThroughSession(_AlmaAPIClientTestBase):
    """Tests for AC-2: each verb routes through ``self._session.request``."""

    def test_get_routes_through_session(self):
        """``client.get`` should call ``Session.request`` with method GET."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'request', return_value=_make_mock_response()
        ) as mock_request:
            client.get('almaws/v1/conf/libraries', params={'limit': 5})

        self.assertEqual(mock_request.call_count, 1)
        args, kwargs = mock_request.call_args
        # First positional arg is the method, second is the URL.
        self.assertEqual(args[0], 'GET')
        self.assertEqual(
            args[1],
            'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/libraries',
        )
        self.assertEqual(kwargs.get('params'), {'limit': 5})
        # No real network call -- method should not have been the
        # module-level ``requests.get``.

    def test_post_routes_through_session(self):
        """``client.post`` with dict data should send JSON via the session."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'request', return_value=_make_mock_response(201)
        ) as mock_request:
            client.post('almaws/v1/users', data={'first_name': 'Ada'})

        self.assertEqual(mock_request.call_count, 1)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'POST')
        self.assertEqual(
            args[1], 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/users'
        )
        # Dict data is sent as JSON when no content_type override is given.
        self.assertEqual(kwargs.get('json'), {'first_name': 'Ada'})

    def test_post_with_xml_content_type_sends_data(self):
        """XML content-type should send via ``data=`` rather than ``json=``."""
        client = AlmaAPIClient('SANDBOX')
        xml_body = '<bib><record/></bib>'
        with patch.object(
            client._session, 'request', return_value=_make_mock_response(200)
        ) as mock_request:
            client.post(
                'almaws/v1/bibs',
                data=xml_body,
                content_type='application/xml',
            )

        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'POST')
        self.assertEqual(kwargs.get('data'), xml_body)
        self.assertNotIn('json', kwargs)

    def test_put_routes_through_session(self):
        """``client.put`` should call ``Session.request`` with method PUT."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'request', return_value=_make_mock_response()
        ) as mock_request:
            client.put('almaws/v1/users/123', data={'last_name': 'Lovelace'})

        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'PUT')
        self.assertEqual(
            args[1],
            'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/users/123',
        )
        self.assertEqual(kwargs.get('json'), {'last_name': 'Lovelace'})

    def test_delete_routes_through_session(self):
        """``client.delete`` should call ``Session.request`` with method DELETE."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'request', return_value=_make_mock_response(204)
        ) as mock_request:
            client.delete('almaws/v1/users/123')

        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'DELETE')
        self.assertEqual(
            args[1],
            'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/users/123',
        )


class TestCustomHeadersOverride(_AlmaAPIClientTestBase):
    """Tests for AC-3: per-call custom_headers still merge over session headers."""

    def test_custom_headers_override_session_headers(self):
        """``custom_headers`` should appear in the per-call ``headers=`` kwarg."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'request', return_value=_make_mock_response()
        ) as mock_request:
            client.get(
                'almaws/v1/conf/libraries',
                custom_headers={'X-Test': '1', 'Accept': 'application/xml'},
            )

        _args, kwargs = mock_request.call_args
        sent_headers = kwargs.get('headers') or {}
        # Custom header injected.
        self.assertEqual(sent_headers.get('X-Test'), '1')
        # Custom override of an existing default header wins.
        self.assertEqual(sent_headers.get('Accept'), 'application/xml')
        # The session-level Authorization should still be present in the
        # per-call headers (because ``_prepare_headers`` copies from
        # ``self.default_headers``).
        self.assertEqual(
            sent_headers.get('Authorization'), 'apikey test-sandbox-key'
        )


class TestSessionReuse(_AlmaAPIClientTestBase):
    """Tests that the same session instance is reused across calls."""

    def test_session_reuse_across_calls(self):
        """Two calls should hit the SAME ``client._session`` instance."""
        client = AlmaAPIClient('SANDBOX')
        session_id_before = id(client._session)
        with patch.object(
            client._session, 'request', return_value=_make_mock_response()
        ) as mock_request:
            client.get('almaws/v1/conf/libraries')
            client.get('almaws/v1/conf/libraries', params={'offset': 10})

        # Patched on the session instance itself, so two calls = two hits
        # on the same session.
        self.assertEqual(mock_request.call_count, 2)
        # The session reference must not have been swapped out.
        self.assertEqual(id(client._session), session_id_before)


class TestRequestChokepoint(_AlmaAPIClientTestBase):
    """Tests for issue #4: ``_request`` is the single HTTP chokepoint.

    AC-1 (signatures preserved) is covered by the existing
    ``TestVerbsRouteThroughSession`` class above. AC-2 (single chokepoint)
    is enforced here by routing each verb through ``_request`` and
    confirming the underlying ``Session.request`` is hit exactly once with
    the expected method/URL/dispatch shape.

    Pattern source: GitHub issue #4 acceptance criteria.
    """

    def test_request_single_chokepoint_for_get(self):
        """``client.get`` must reach ``Session.request`` exactly once."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'request', return_value=_make_mock_response()
        ) as mock_request:
            client.get('almaws/v1/conf/libraries', params={'limit': 5})

        # Exactly one call -- proving the verb method is a thin wrapper
        # over ``_request`` and not redundantly issuing the call itself.
        self.assertEqual(mock_request.call_count, 1)
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertEqual(
            args[1],
            'https://api-eu.hosted.exlibrisgroup.com/almaws/v1/conf/libraries',
        )
        self.assertEqual(kwargs.get('params'), {'limit': 5})
        # Default timeout flows from ``client.timeout`` when no per-call
        # override is supplied.
        self.assertEqual(kwargs.get('timeout'), client.timeout)

    def test_request_uses_json_for_dict_data(self):
        """Dict bodies without a content-type override go via ``json=``."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'request', return_value=_make_mock_response(201)
        ) as mock_request:
            client.post('almaws/v1/users', data={'first_name': 'Ada'})

        _args, kwargs = mock_request.call_args
        self.assertEqual(kwargs.get('json'), {'first_name': 'Ada'})
        # Mutually exclusive with ``data=`` so requests doesn't double-send.
        self.assertNotIn('data', kwargs)

    def test_request_uses_data_for_xml(self):
        """When content_type is set, the body goes via ``data=`` verbatim."""
        client = AlmaAPIClient('SANDBOX')
        xml_body = '<bib><record/></bib>'
        with patch.object(
            client._session, 'request', return_value=_make_mock_response(200)
        ) as mock_request:
            client.post(
                'almaws/v1/bibs',
                data=xml_body,
                content_type='application/xml',
            )

        _args, kwargs = mock_request.call_args
        self.assertEqual(kwargs.get('data'), xml_body)
        self.assertNotIn('json', kwargs)

    def test_request_custom_timeout_overrides_default(self):
        """Per-call ``timeout=`` should win over ``client.timeout``."""
        client = AlmaAPIClient('SANDBOX')
        # Sanity: default differs from the override we'll pass.
        self.assertNotEqual(client.timeout, 5)
        with patch.object(
            client._session, 'request', return_value=_make_mock_response()
        ) as mock_request:
            # ``_request`` is the documented entry point for callers that
            # need to override timeout (the public verbs don't expose it
            # to keep their signatures bit-stable).
            client._request('GET', 'almaws/v1/conf/libraries', timeout=5)

        _args, kwargs = mock_request.call_args
        self.assertEqual(kwargs.get('timeout'), 5)

    def test_safe_response_body_returns_none_on_parse_error(self):
        """``_safe_response_body`` should swallow JSON decode failures."""
        bad_response = MagicMock(spec=requests.Response)
        bad_response.headers = {'content-type': 'application/json'}
        bad_response.json.side_effect = ValueError('not json')
        # Helper must not propagate the parse error -- it returns None so
        # callers can fall through to text/empty handling.
        self.assertIsNone(_safe_response_body(bad_response))

    def test_safe_response_body_returns_none_for_non_json_content_type(self):
        """Non-JSON content types short-circuit without invoking ``.json()``."""
        text_response = MagicMock(spec=requests.Response)
        text_response.headers = {'content-type': 'text/plain'}
        text_response.json.side_effect = AssertionError(
            "should not be called for non-JSON content"
        )
        self.assertIsNone(_safe_response_body(text_response))


class TestRetryAdapterMounted(_AlmaAPIClientTestBase):
    """Tests for issue #5: HTTPAdapter with Retry policy mounted on session.

    These tests inspect the *configuration* of the mounted adapter
    rather than driving the retry loop end-to-end. The earlier code
    review of #5 noted that the existing test suite patches
    ``client._session.request`` — patching at that level bypasses
    urllib3's adapter logic, so retry behavior cannot be verified by
    patching at that level. Inspecting the adapter's ``max_retries``
    attribute (which is the ``Retry`` instance after ``HTTPAdapter``
    init) is the recommended alternative.

    Pattern source: GitHub issue #5 acceptance criteria.
    """

    def _get_mounted_retry(
        self, client: AlmaAPIClient, scheme: str
    ) -> Retry:
        """Pull the ``Retry`` instance off the adapter mounted for ``scheme``."""
        adapter = client._session.adapters[scheme]
        self.assertIsInstance(adapter, HTTPAdapter)
        retry = adapter.max_retries
        self.assertIsInstance(retry, Retry)
        return retry

    def test_init_mounts_retry_adapter_https(self):
        """AC-1 + AC-2: default Retry policy is mounted for ``https://``."""
        client = AlmaAPIClient('SANDBOX')
        retry = self._get_mounted_retry(client, 'https://')
        self.assertEqual(retry.total, 3)
        self.assertEqual(
            set(retry.status_forcelist), {429, 500, 502, 503, 504}
        )
        self.assertEqual(retry.backoff_factor, 1)
        # ``allowed_methods`` is normalized by urllib3 -- compare as a set.
        self.assertEqual(
            set(retry.allowed_methods), {"GET", "POST", "PUT", "DELETE"}
        )
        self.assertTrue(retry.respect_retry_after_header)

    def test_init_mounts_retry_adapter_http(self):
        """AC-1 + AC-2: default Retry policy is mounted for ``http://`` too."""
        client = AlmaAPIClient('SANDBOX')
        retry = self._get_mounted_retry(client, 'http://')
        self.assertEqual(retry.total, 3)
        self.assertEqual(
            set(retry.status_forcelist), {429, 500, 502, 503, 504}
        )
        self.assertEqual(retry.backoff_factor, 1)
        self.assertEqual(
            set(retry.allowed_methods), {"GET", "POST", "PUT", "DELETE"}
        )
        self.assertTrue(retry.respect_retry_after_header)

    def test_max_retries_kwarg_overrides_default(self):
        """AC-3: ``max_retries`` kwarg overrides the ``total`` default."""
        client = AlmaAPIClient('SANDBOX', max_retries=5)
        retry = self._get_mounted_retry(client, 'https://')
        self.assertEqual(retry.total, 5)
        # Other defaults should be unaffected by the override.
        self.assertEqual(retry.backoff_factor, 1)
        self.assertEqual(
            set(retry.status_forcelist), {429, 500, 502, 503, 504}
        )

    def test_backoff_factor_kwarg_overrides_default(self):
        """AC-3: ``backoff_factor`` kwarg overrides the multiplier."""
        client = AlmaAPIClient('SANDBOX', backoff_factor=0.5)
        retry = self._get_mounted_retry(client, 'https://')
        self.assertEqual(retry.backoff_factor, 0.5)
        # Defaults preserved for the other knobs.
        self.assertEqual(retry.total, 3)

    def test_retry_kwarg_wins_over_other_kwargs(self):
        """AC-4: a hand-built ``Retry`` instance overrides simple kwargs."""
        custom_retry = Retry(
            total=10,
            status_forcelist=[418],
            backoff_factor=0.25,
            allowed_methods=frozenset({"GET"}),
        )
        # Pass conflicting simple kwargs to prove ``retry`` wins.
        client = AlmaAPIClient(
            'SANDBOX',
            max_retries=99,
            backoff_factor=2.0,
            retry=custom_retry,
        )
        retry = self._get_mounted_retry(client, 'https://')
        self.assertEqual(retry.total, 10)
        self.assertEqual(list(retry.status_forcelist), [418])
        self.assertEqual(retry.backoff_factor, 0.25)
        self.assertEqual(set(retry.allowed_methods), {"GET"})

    def test_invalid_max_retries_raises(self):
        """Negative ``max_retries`` should be rejected at construction time."""
        with self.assertRaises(AlmaValidationError):
            AlmaAPIClient('SANDBOX', max_retries=-1)

    def test_invalid_backoff_factor_raises(self):
        """Negative ``backoff_factor`` should be rejected at construction time."""
        with self.assertRaises(AlmaValidationError):
            AlmaAPIClient('SANDBOX', backoff_factor=-0.1)


class TestTimeoutConfiguration(_AlmaAPIClientTestBase):
    """Tests for issue #6: configurable timeout, lower default (60s).

    AC-1: default lowered from 300s to 60s.
    AC-2: ``AlmaAPIClient(timeout=120.0)`` accepted and persisted.
    AC-3: per-call override path still works (issue #4 wiring).
    AC-4: the new default actually flows into ``Session.request`` calls.
    AC-5: invalid values rejected via ``AlmaValidationError``.

    Pattern source: GitHub issue #6 acceptance criteria.
    """

    def test_default_timeout_is_60(self):
        """A bare ``AlmaAPIClient`` should expose ``timeout == 60``."""
        client = AlmaAPIClient('SANDBOX')
        self.assertEqual(client.timeout, 60)

    def test_timeout_kwarg_overrides_default(self):
        """Passing ``timeout=120.0`` should win over the module default."""
        client = AlmaAPIClient('SANDBOX', timeout=120.0)
        self.assertEqual(client.timeout, 120.0)

    def test_timeout_none_uses_default(self):
        """``timeout=None`` is the documented "use the default" sentinel."""
        client = AlmaAPIClient('SANDBOX', timeout=None)
        self.assertEqual(client.timeout, 60)

    def test_timeout_passed_to_session_request(self):
        """The default ``self.timeout`` should flow into ``Session.request``."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'request', return_value=_make_mock_response()
        ) as mock_request:
            client.get('almaws/v1/conf/libraries')

        _args, kwargs = mock_request.call_args
        # The verb wrappers don't expose ``timeout`` to keep their
        # signatures bit-stable, so the value must come from
        # ``self.timeout``.
        self.assertEqual(kwargs.get('timeout'), 60)
        self.assertEqual(kwargs.get('timeout'), client.timeout)

    def test_per_call_timeout_overrides_self_timeout(self):
        """Per-call ``_request(..., timeout=5)`` must beat ``self.timeout``."""
        client = AlmaAPIClient('SANDBOX', timeout=120.0)
        with patch.object(
            client._session, 'request', return_value=_make_mock_response()
        ) as mock_request:
            client._request('GET', 'almaws/v1/conf/libraries', timeout=5)

        _args, kwargs = mock_request.call_args
        self.assertEqual(kwargs.get('timeout'), 5)
        # Sanity: self.timeout itself wasn't mutated by the per-call override.
        self.assertEqual(client.timeout, 120.0)

    def test_invalid_timeout_negative_raises(self):
        """Negative timeouts must be rejected at construction time."""
        with self.assertRaises(AlmaValidationError):
            AlmaAPIClient('SANDBOX', timeout=-1)

    def test_invalid_timeout_zero_raises(self):
        """Zero is rejected: a 0-second timeout would fire immediately."""
        with self.assertRaises(AlmaValidationError):
            AlmaAPIClient('SANDBOX', timeout=0)

    def test_invalid_timeout_string_raises(self):
        """Non-numeric values must be rejected (not silently coerced)."""
        with self.assertRaises(AlmaValidationError):
            AlmaAPIClient('SANDBOX', timeout="abc")

    def test_invalid_timeout_bool_raises(self):
        """``bool`` is rejected even though it's an ``int`` subclass."""
        with self.assertRaises(AlmaValidationError):
            AlmaAPIClient('SANDBOX', timeout=True)


if __name__ == '__main__':
    unittest.main()
