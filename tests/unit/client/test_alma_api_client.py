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

from almaapitk import AlmaAPIClient


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


if __name__ == '__main__':
    unittest.main()
