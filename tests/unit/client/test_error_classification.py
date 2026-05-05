"""
Unit tests for AlmaAPIClient error classification (issue #9).

These tests verify that ``AlmaAPIClient._handle_response`` raises the most
specific ``AlmaAPIError`` subclass for each error condition, instead of
the previous behaviour of always raising a bare ``AlmaAPIError`` and
forcing domain code to inspect the message string.

Pattern source: GitHub issue #9 acceptance criteria. Mocking style follows
``tests/unit/client/test_alma_api_client.py`` (``_AlmaAPIClientTestBase``
+ ``_make_mock_response`` helper, ``patch.object(client._session, 'request', ...)``).
"""

import os
import unittest
from unittest.mock import patch, MagicMock

import requests

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import (
    AlmaAPIError,
    AlmaAuthenticationError,
    AlmaRateLimitError,
    AlmaServerError,
    AlmaResourceNotFoundError,
    AlmaDuplicateInvoiceError,
    AlmaInvalidPolModeError,
    ERROR_CODE_REGISTRY,
)


def _make_mock_error_response(
    status_code: int,
    json_body=None,
    content_type: str = 'application/json',
    text: str = '',
):
    """Build a minimal ``requests.Response``-like mock for error tests.

    Mirrors the ``_make_mock_response`` helper in
    ``tests/unit/client/test_alma_api_client.py`` but defaults to error
    semantics (``ok = False``) so the tests below stay terse.
    """
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.ok = status_code < 400
    mock_response.headers = {'content-type': content_type}
    mock_response.text = text
    if json_body is None:
        json_body = {}
    mock_response.json.return_value = json_body
    return mock_response


def _alma_error_payload(error_code: str, message: str = "synthetic error") -> dict:
    """Construct the standard Alma errorList payload for tests.

    The shape mirrors what Alma actually returns, so registry-lookup
    tests exercise the same parsing path as live responses:

        {
            "errorsExist": true,
            "errorList": {
                "error": [{"errorCode": "<code>", "errorMessage": "...", "trackingId": "..."}]
            }
        }
    """
    return {
        "errorsExist": True,
        "errorList": {
            "error": [
                {
                    "errorCode": error_code,
                    "errorMessage": message,
                    "trackingId": "test-tracking-id",
                }
            ]
        },
    }


class _AlmaAPIClientErrorTestBase(unittest.TestCase):
    """Shared setUp that injects a fake API key into the environment.

    Mirrors ``_AlmaAPIClientTestBase`` in ``test_alma_api_client.py``.
    """

    def setUp(self):
        self._env_patcher = patch.dict(
            os.environ, {'ALMA_SB_API_KEY': 'test-sandbox-key'}, clear=False
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)


class TestErrorClassificationByStatus(_AlmaAPIClientErrorTestBase):
    """Tests that HTTP-status fallbacks raise the right typed subclass."""

    def test_401_raises_authentication_error(self):
        """HTTP 401 must raise ``AlmaAuthenticationError``."""
        client = AlmaAPIClient('SANDBOX')
        # 401 with no errorList payload exercises the status-only fallback.
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(401, json_body={}),
        ):
            with self.assertRaises(AlmaAuthenticationError) as ctx:
                client.get('almaws/v1/conf/libraries')
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_404_raises_resource_not_found_error(self):
        """HTTP 404 must raise ``AlmaResourceNotFoundError``."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(404, json_body={}),
        ):
            with self.assertRaises(AlmaResourceNotFoundError) as ctx:
                client.get('almaws/v1/bibs/does-not-exist')
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_429_raises_rate_limit_error(self):
        """HTTP 429 must raise ``AlmaRateLimitError``."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(429, json_body={}),
        ):
            with self.assertRaises(AlmaRateLimitError) as ctx:
                client.get('almaws/v1/conf/libraries')
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_503_raises_server_error(self):
        """HTTP 503 (any 5xx) must raise ``AlmaServerError``."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(503, json_body={}),
        ):
            with self.assertRaises(AlmaServerError) as ctx:
                client.get('almaws/v1/conf/libraries')
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        self.assertEqual(ctx.exception.status_code, 503)

    def test_500_also_raises_server_error(self):
        """HTTP 500 must also map to ``AlmaServerError`` (5xx band guard)."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(500, json_body={}),
        ):
            with self.assertRaises(AlmaServerError):
                client.get('almaws/v1/conf/libraries')

    def test_502_also_raises_server_error(self):
        """HTTP 502 must also map to ``AlmaServerError`` (5xx band guard)."""
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(502, json_body={}),
        ):
            with self.assertRaises(AlmaServerError):
                client.get('almaws/v1/conf/libraries')


class TestErrorClassificationByAlmaCode(_AlmaAPIClientErrorTestBase):
    """Tests that registry-driven Alma error codes pick the right subclass."""

    def test_code_402459_raises_duplicate_invoice_error(self):
        """Alma error code 402459 must raise ``AlmaDuplicateInvoiceError``."""
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload(
            "402459", "Invoice with the same number already exists for this vendor"
        )
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaDuplicateInvoiceError) as ctx:
                client.post('almaws/v1/acq/invoices', data={'foo': 'bar'})
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        self.assertEqual(ctx.exception.status_code, 400)
        # The message should preserve Alma's text so log output is intact.
        self.assertIn("Invoice", str(ctx.exception))

    def test_code_40166411_raises_invalid_pol_mode_error(self):
        """Alma error code 40166411 must raise ``AlmaInvalidPolModeError``."""
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload(
            "40166411", "PO Line is not in the right mode for this operation"
        )
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaInvalidPolModeError) as ctx:
                client.post(
                    'almaws/v1/acq/po-lines/POL-1/items',
                    data={'foo': 'bar'},
                )
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_code_401861_raises_resource_not_found_error(self):
        """Alma returns HTTP 400 + errorCode 401861 (not HTTP 404) for a missing
        user_primary_id. The registry maps the code to ``AlmaResourceNotFoundError``
        so callers can write ``except AlmaResourceNotFoundError`` instead of
        inspecting the message string. Discovered via SANDBOX smoke (chunk
        errors-mapping)."""
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload(
            "401861", "User with identifier xxxxx was not found."
        )
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaResourceNotFoundError) as ctx:
                client.get('almaws/v1/users/xxxxx')
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        # The response was HTTP 400; subclass dispatch came from the alma_code,
        # not the status code — so status_code on the raised exception still
        # reflects the original HTTP value.
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.alma_code, "401861")

    def test_code_60224_raises_resource_not_found_error(self):
        """Alma error code 60224 ("Organization institution not found") on
        the /users endpoints must raise ``AlmaResourceNotFoundError``.

        Pattern source: issue #90 swagger backfill — the code is documented
        in Ex Libris's users.json swagger across GET/POST /almaws/v1/users,
        and the typed exception lets callers branch on missing-org as
        cleanly as on missing-user (#9 / 401861) without parsing
        errorMessage strings.
        """
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload(
            "60224", "Organization institution not found.",
        )
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaResourceNotFoundError) as ctx:
                client.get('almaws/v1/users')
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.alma_code, "60224")

    def test_400_with_unrecognized_code_raises_bare_alma_api_error(self):
        """A 400 with an unknown Alma code falls through to bare ``AlmaAPIError``."""
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload(
            "999999", "Some other validation problem"
        )
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaAPIError) as ctx:
                client.post('almaws/v1/acq/invoices', data={'foo': 'bar'})
        # Must be the *bare* base class -- not any of the typed subclasses.
        self.assertIs(type(ctx.exception), AlmaAPIError)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_alma_code_overrides_status_dispatch(self):
        """When both an Alma code and a status would map, the code wins.

        A 404 response that *also* carries a registered Alma code should
        be classified by the code (more specific), not by the status.
        """
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload("402459", "Duplicate invoice")
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(404, json_body=payload),
        ):
            with self.assertRaises(AlmaDuplicateInvoiceError) as ctx:
                client.post('almaws/v1/acq/invoices', data={'foo': 'bar'})
        # status_code is preserved as-is on the exception even though the
        # type was picked from the registry.
        self.assertEqual(ctx.exception.status_code, 404)


class TestBackwardsCompatibility(_AlmaAPIClientErrorTestBase):
    """Tests that all typed subclasses remain catchable as ``AlmaAPIError``."""

    def test_all_typed_errors_are_alma_api_errors(self):
        """Every registry entry + status-mapped class must subclass AlmaAPIError."""
        for code, cls in ERROR_CODE_REGISTRY.items():
            with self.subTest(code=code):
                self.assertTrue(
                    issubclass(cls, AlmaAPIError),
                    f"Registry entry {code} -> {cls.__name__} must subclass AlmaAPIError",
                )

        for cls in (
            AlmaAuthenticationError,
            AlmaRateLimitError,
            AlmaServerError,
            AlmaResourceNotFoundError,
            AlmaDuplicateInvoiceError,
            AlmaInvalidPolModeError,
        ):
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(cls, AlmaAPIError))

    def test_existing_except_alma_api_error_still_catches_typed_subclasses(self):
        """Existing ``except AlmaAPIError`` blocks must keep working.

        This is the core backwards-compat guarantee: callers that catch
        the broad base type should not need to update for issue #9.
        """
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(429, json_body={}),
        ):
            try:
                client.get('almaws/v1/conf/libraries')
                self.fail("Expected an exception")
            except AlmaAPIError as e:
                # Specifically the rate-limit subclass, but caught by the
                # base type -- which is exactly the contract we promise.
                self.assertIsInstance(e, AlmaRateLimitError)

    def test_typed_exception_preserves_constructor_signature(self):
        """All typed subclasses must accept ``(message, status_code, response)``.

        ``_handle_response`` calls them with three positional args, so any
        subclass that breaks the signature would crash on first use.
        """
        sentinel_response = object()
        for cls in (
            AlmaAuthenticationError,
            AlmaRateLimitError,
            AlmaServerError,
            AlmaResourceNotFoundError,
            AlmaDuplicateInvoiceError,
            AlmaInvalidPolModeError,
        ):
            with self.subTest(cls=cls.__name__):
                exc = cls("test message", 418, sentinel_response)
                self.assertEqual(str(exc), "test message")
                self.assertEqual(exc.status_code, 418)
                self.assertIs(exc.response, sentinel_response)


class TestClassifyErrorMethod(_AlmaAPIClientErrorTestBase):
    """Direct unit tests for ``AlmaAPIClient._classify_error``."""

    def test_classify_picks_registry_for_known_code(self):
        client = AlmaAPIClient('SANDBOX')
        self.assertIs(
            client._classify_error(400, "402459"),
            AlmaDuplicateInvoiceError,
        )
        self.assertIs(
            client._classify_error(400, "40166411"),
            AlmaInvalidPolModeError,
        )

    def test_classify_falls_back_to_status_when_code_unknown(self):
        client = AlmaAPIClient('SANDBOX')
        self.assertIs(client._classify_error(401, None), AlmaAuthenticationError)
        self.assertIs(client._classify_error(404, None), AlmaResourceNotFoundError)
        self.assertIs(client._classify_error(429, None), AlmaRateLimitError)
        self.assertIs(client._classify_error(500, None), AlmaServerError)
        self.assertIs(client._classify_error(599, None), AlmaServerError)

    def test_classify_returns_base_for_unmapped_status(self):
        client = AlmaAPIClient('SANDBOX')
        # 400 with no Alma code falls through to the base class.
        self.assertIs(client._classify_error(400, None), AlmaAPIError)
        # Any other unmapped status is also base.
        self.assertIs(client._classify_error(418, None), AlmaAPIError)

    def test_classify_unknown_code_falls_back_to_status(self):
        client = AlmaAPIClient('SANDBOX')
        # Unknown Alma code + 401 status should still pick auth error.
        self.assertIs(
            client._classify_error(401, "999999"),
            AlmaAuthenticationError,
        )


if __name__ == '__main__':
    unittest.main()
