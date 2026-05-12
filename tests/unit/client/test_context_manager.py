"""
Unit tests for AlmaAPIClient context-manager / close() support.

These tests verify the ``__enter__``/``__exit__``/``close`` trio added in
GitHub issue #13. They build on the persistent ``requests.Session``
introduced in #3 and pin the following behaviours:

- ``with AlmaAPIClient(...) as alma:`` works and closes the session on
  exit (AC-1).
- ``alma.close()`` is callable directly and is idempotent (AC-2).
- HTTP calls after ``close()`` raise a clear ``AlmaAPIError`` rather
  than an opaque ``AttributeError`` from the underlying session (AC-3 —
  we picked the "raise on use after close" branch documented in the
  ``close`` docstring; the alternative was lazy re-creation).
- Tests cover the with-statement path end-to-end (AC-4).

Pattern source: tests/unit/client/test_alma_api_client.py and the
acceptance criteria of GitHub issue #13.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

import requests

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError


def _make_mock_response(
    status_code: int = 200,
    json_body=None,
    content_type: str = 'application/json',
):
    """Build a minimal ``requests.Response``-like mock for tests.

    Mirrors the helper in ``test_alma_api_client.py`` so the two suites
    speak the same vocabulary; we duplicate it here rather than importing
    a private helper across test modules.
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
    """Inject a fake API key into the environment for isolated tests.

    Pattern source: ``_AlmaAPIClientTestBase`` in
    tests/unit/client/test_alma_api_client.py.
    """

    def setUp(self):
        self._env_patcher = patch.dict(
            os.environ, {'ALMA_SB_API_KEY': 'test-sandbox-key'}, clear=False
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)


class TestContextManagerProtocol(_AlmaAPIClientTestBase):
    """Tests for AC-1: ``with AlmaAPIClient(...) as alma:`` works."""

    def test_with_statement_returns_client(self):
        """``__enter__`` must return the client instance itself."""
        with AlmaAPIClient('SANDBOX') as alma:
            self.assertIsInstance(alma, AlmaAPIClient)
            # The session is still live inside the block.
            self.assertIsNotNone(alma._session)

    def test_with_statement_closes_session_on_exit(self):
        """The session's ``close`` should fire when the ``with`` block exits."""
        client = AlmaAPIClient('SANDBOX')
        # Spy on the live session's ``close`` method without swapping
        # the session out — we want to assert the real teardown path.
        with patch.object(
            client._session, 'close', wraps=client._session.close
        ) as mock_close:
            with client as alma:
                # Make a call inside the block to prove the client is
                # functional. Patch ``_session.request`` (the chokepoint
                # used by ``_request``) so no network IO occurs.
                with patch.object(
                    alma._session,
                    'request',
                    return_value=_make_mock_response(),
                ):
                    alma.get('almaws/v1/conf/libraries')
            mock_close.assert_called_once()
        # After the block, the client should be in the closed state.
        self.assertIsNone(client._session)

    def test_with_statement_closes_on_exception(self):
        """Exiting via an exception should still close the session.

        Regression guard: an exception raised inside the ``with`` body
        must not prevent teardown — that's the entire point of the
        context-manager protocol.
        """
        client = AlmaAPIClient('SANDBOX')
        with patch.object(client._session, 'close') as mock_close:
            with self.assertRaises(RuntimeError):
                with client:
                    raise RuntimeError("boom")
            mock_close.assert_called_once()
        self.assertIsNone(client._session)


class TestCloseMethod(_AlmaAPIClientTestBase):
    """Tests for AC-2: ``close()`` callable directly and idempotent."""

    def test_close_releases_session(self):
        """A direct ``close()`` call should release the session reference."""
        client = AlmaAPIClient('SANDBOX')
        live_session = client._session
        self.assertIsNotNone(live_session)

        with patch.object(live_session, 'close') as mock_close:
            client.close()
            mock_close.assert_called_once()

        # ``_session`` is the documented "closed" sentinel.
        self.assertIsNone(client._session)

    def test_close_is_idempotent(self):
        """Calling ``close()`` twice must not raise."""
        client = AlmaAPIClient('SANDBOX')
        client.close()
        # Second call must be a silent no-op — this is the AC-2 contract.
        client.close()
        self.assertIsNone(client._session)

    def test_close_swallows_session_close_errors(self):
        """A ``Session.close`` failure must not propagate.

        Teardown in ``__exit__`` is the dominant caller; an error there
        would mask whatever exception the ``with`` body raised. The
        client logs and moves on.
        """
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session, 'close', side_effect=OSError('fd closed twice')
        ):
            # No exception should escape ``close()``.
            client.close()
        # State still cleared so subsequent calls hit the "closed" guard.
        self.assertIsNone(client._session)


class TestUseAfterClose(_AlmaAPIClientTestBase):
    """Tests for AC-3: HTTP calls after ``close()`` raise a clear error.

    We deliberately picked "raise on use after close" over "lazy
    re-create" — see the ``close`` docstring. The error must be an
    ``AlmaAPIError`` (so it slots into the existing exception hierarchy)
    with a message that names the cause.
    """

    def test_get_after_close_raises(self):
        """``get`` after ``close`` should raise ``AlmaAPIError``."""
        client = AlmaAPIClient('SANDBOX')
        client.close()
        with self.assertRaises(AlmaAPIError) as ctx:
            client.get('almaws/v1/conf/libraries')
        self.assertIn('closed', str(ctx.exception).lower())

    def test_post_after_close_raises(self):
        """``post`` after ``close`` should raise ``AlmaAPIError``."""
        client = AlmaAPIClient('SANDBOX')
        client.close()
        with self.assertRaises(AlmaAPIError):
            client.post('almaws/v1/users', data={'first_name': 'Ada'})

    def test_put_after_close_raises(self):
        """``put`` after ``close`` should raise ``AlmaAPIError``."""
        client = AlmaAPIClient('SANDBOX')
        client.close()
        with self.assertRaises(AlmaAPIError):
            client.put('almaws/v1/users/123', data={'last_name': 'L'})

    def test_delete_after_close_raises(self):
        """``delete`` after ``close`` should raise ``AlmaAPIError``."""
        client = AlmaAPIClient('SANDBOX')
        client.close()
        with self.assertRaises(AlmaAPIError):
            client.delete('almaws/v1/users/123')

    def test_use_after_with_block_raises(self):
        """The end-to-end usage pattern from the issue: raise after exit."""
        client = AlmaAPIClient('SANDBOX')
        with client as alma:
            with patch.object(
                alma._session, 'request', return_value=_make_mock_response()
            ):
                alma.get('almaws/v1/conf/libraries')
        # The block has exited — further use should raise.
        with self.assertRaises(AlmaAPIError):
            client.get('almaws/v1/conf/libraries')


class TestSwitchEnvironmentAfterClose(_AlmaAPIClientTestBase):
    """Tests for issue #138 (F-012): ``switch_environment`` after ``close``.

    Before this fix, ``switch_environment`` defensively guarded the
    ``self._session.headers.update(...)`` call with ``hasattr/is not
    None`` so the call did not crash, but it also did NOT re-create the
    session. The client landed in an unusable "no session" state and the
    very next HTTP verb call failed in an undocumented way. We picked
    "raise a clear ``AlmaAPIError``" over "lazy re-init" to stay
    consistent with the HTTP-verb guard added in issue #13 (see
    ``close``'s docstring): a closed client signals an explicit caller
    intent to release the resource, and silently rebuilding it would
    mask programmer errors. The ``switch_environment`` docstring now
    documents this exception.
    """

    def setUp(self):
        super().setUp()
        # Also inject a fake production key so ``_load_configuration``
        # does not blow up if the rollback path is exercised.
        self._prod_env_patcher = patch.dict(
            os.environ, {'ALMA_PROD_API_KEY': 'test-prod-key'}, clear=False
        )
        self._prod_env_patcher.start()
        self.addCleanup(self._prod_env_patcher.stop)

    def test_switch_environment_after_close_raises(self):
        """``switch_environment`` after ``close`` must raise ``AlmaAPIError``."""
        client = AlmaAPIClient('SANDBOX')
        client.close()
        with self.assertRaises(AlmaAPIError) as ctx:
            client.switch_environment('PRODUCTION')
        self.assertIn('closed', str(ctx.exception).lower())
        # Environment must remain unchanged when the guard fires; the
        # caller's view of the world is "this client is dead" rather
        # than "this client mutated half-way through a switch".
        self.assertEqual(client.environment, 'SANDBOX')
        # Session must still be ``None`` — the guard refused to rebuild it.
        self.assertIsNone(client._session)

    def test_switch_environment_after_with_block_raises(self):
        """End-to-end: switch after the ``with`` block must raise."""
        client = AlmaAPIClient('SANDBOX')
        with client as alma:
            with patch.object(
                alma._session, 'request', return_value=_make_mock_response()
            ):
                alma.get('almaws/v1/conf/libraries')
        # The block has exited — switching environments should raise.
        with self.assertRaises(AlmaAPIError):
            client.switch_environment('PRODUCTION')

    def test_switch_environment_before_close_still_works(self):
        """Regression guard: the live-session path is unchanged."""
        client = AlmaAPIClient('SANDBOX')
        live_session = client._session
        self.assertIsNotNone(live_session)
        # Switch should succeed and the same session object must remain.
        client.switch_environment('PRODUCTION')
        self.assertEqual(client.environment, 'PRODUCTION')
        self.assertIs(client._session, live_session)


if __name__ == '__main__':
    unittest.main()
