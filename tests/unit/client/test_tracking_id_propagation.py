"""
Unit tests for AlmaAPIClient tracking_id / alma_code propagation (issue #10).

Alma error responses include ``errorList.error[0].trackingId`` and
``errorList.error[0].errorCode``, which Ex Libris support uses to look up
the individual server-side request when investigating a case. Domain
logging code (e.g. ``users.py``) already references
``tracking_id=getattr(e, 'tracking_id', None)`` -- before issue #10 that
attribute was always ``None`` because ``_handle_response`` never extracted
the field. These tests pin the post-#10 behaviour so the attribute can
never silently regress to dead-code again.

Pattern source: GitHub issue #10 acceptance criteria. Mocking style mirrors
``tests/unit/client/test_alma_api_client.py`` (env-var patcher +
``_make_mock_response`` with ``spec=requests.Response``).
"""

import os
import unittest
from unittest.mock import patch, MagicMock

import requests

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import (
    AlmaAPIError,
    AlmaAuthenticationError,
    AlmaDuplicateInvoiceError,
    AlmaResourceNotFoundError,
)


def _make_mock_error_response(
    status_code: int,
    json_body=None,
    content_type: str = 'application/json',
    text: str = '',
):
    """Build a minimal ``requests.Response``-like mock for error tests.

    Mirrors the helper in ``test_alma_api_client.py`` /
    ``test_error_classification.py`` so the three test files share an
    interchangeable mocking idiom.
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


def _alma_error_payload(
    error_code: str,
    message: str = "synthetic error",
    tracking_id: str = "TRK-12345",
) -> dict:
    """Construct the standard Alma errorList payload for tests.

    The shape mirrors what Alma actually returns so that the parsing path
    exercised here is the same one live responses traverse:

        {
            "errorsExist": True,
            "errorList": {
                "error": [
                    {
                        "errorCode": "<code>",
                        "errorMessage": "<message>",
                        "trackingId": "<tracking_id>",
                    }
                ]
            },
        }
    """
    return {
        "errorsExist": True,
        "errorList": {
            "error": [
                {
                    "errorCode": error_code,
                    "errorMessage": message,
                    "trackingId": tracking_id,
                }
            ]
        },
    }


class _AlmaAPIClientTrackingTestBase(unittest.TestCase):
    """Shared setUp that injects a fake API key into the environment.

    Mirrors ``_AlmaAPIClientTestBase`` / ``_AlmaAPIClientErrorTestBase`` so
    the test bases stay interchangeable across the client test files.
    """

    def setUp(self):
        self._env_patcher = patch.dict(
            os.environ, {'ALMA_SB_API_KEY': 'test-sandbox-key'}, clear=False
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)


class TestTrackingIdPropagation(_AlmaAPIClientTrackingTestBase):
    """Tests that ``trackingId`` from the response body lands on the exception."""

    def test_tracking_id_from_payload_lands_on_exception(self):
        """Given a payload with ``trackingId``, ``exc.tracking_id`` must match."""
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload(
            "999999",
            "synthetic error",
            tracking_id="E01-2026-05-04-abc",
        )
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaAPIError) as ctx:
                client.get('almaws/v1/conf/libraries')

        self.assertEqual(ctx.exception.tracking_id, "E01-2026-05-04-abc")

    def test_missing_tracking_id_defaults_to_none(self):
        """Without a ``trackingId`` field, ``exc.tracking_id`` is ``None``.

        Crucially, the absence must NOT crash the parser -- the rest of
        the error pipeline still has to deliver a typed exception.
        """
        client = AlmaAPIClient('SANDBOX')
        payload = {
            "errorsExist": True,
            "errorList": {
                "error": [
                    {
                        "errorCode": "999999",
                        "errorMessage": "no tracking field here",
                        # trackingId deliberately omitted
                    }
                ]
            },
        }
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaAPIError) as ctx:
                client.get('almaws/v1/conf/libraries')

        self.assertIsNone(ctx.exception.tracking_id)

    def test_no_error_list_defaults_tracking_id_to_none(self):
        """A response with no ``errorList`` at all must still populate the attr.

        Pre-#10 the ``tracking_id`` attribute didn't exist on the
        exception class, so ``getattr(e, 'tracking_id', None)`` was the
        only safe access pattern in domain code. Post-#10 the attribute
        is always present (default ``None``), and this test guards that
        invariant for the bare-status error path.
        """
        client = AlmaAPIClient('SANDBOX')
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(401, json_body={}),
        ):
            with self.assertRaises(AlmaAuthenticationError) as ctx:
                client.get('almaws/v1/conf/libraries')

        # Attribute must exist on the exception even when no payload was
        # parsed -- direct attribute access (not getattr-with-default).
        self.assertIsNone(ctx.exception.tracking_id)
        self.assertEqual(ctx.exception.alma_code, "")

    def test_non_json_error_body_defaults_both_fields(self):
        """A text/HTML error body must still produce safe defaults."""
        client = AlmaAPIClient('SANDBOX')
        text_response = _make_mock_error_response(
            500,
            json_body=None,
            content_type='text/html',
            text='<html>Internal Server Error</html>',
        )
        with patch.object(
            client._session, 'request', return_value=text_response
        ):
            with self.assertRaises(AlmaAPIError) as ctx:
                client.get('almaws/v1/conf/libraries')

        self.assertIsNone(ctx.exception.tracking_id)
        self.assertEqual(ctx.exception.alma_code, "")


class TestAlmaCodePropagation(_AlmaAPIClientTrackingTestBase):
    """Tests that ``errorCode`` from the response body lands on the exception."""

    def test_alma_code_from_payload_lands_on_exception(self):
        """Given a payload with ``errorCode``, ``exc.alma_code`` must match."""
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload("999999", "Some error")
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaAPIError) as ctx:
                client.get('almaws/v1/conf/libraries')

        self.assertEqual(ctx.exception.alma_code, "999999")

    def test_numeric_alma_code_normalised_to_str(self):
        """Numeric ``errorCode`` from Alma must be normalised to ``str``.

        Alma's API has been observed to return the same code as either
        a JSON number or a JSON string depending on the endpoint. The
        client normalises to ``str`` so registry lookups and log lines
        are uniform regardless of upstream representation.
        """
        client = AlmaAPIClient('SANDBOX')
        payload = {
            "errorsExist": True,
            "errorList": {
                "error": [
                    {
                        "errorCode": 999999,  # NB: int, not str
                        "errorMessage": "numeric code from Alma",
                        "trackingId": "TRK-NUM",
                    }
                ]
            },
        }
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaAPIError) as ctx:
                client.get('almaws/v1/conf/libraries')

        # Stringified, not the int.
        self.assertEqual(ctx.exception.alma_code, "999999")
        self.assertIsInstance(ctx.exception.alma_code, str)


class TestTypedSubclassPropagation(_AlmaAPIClientTrackingTestBase):
    """Tests that typed subclasses (issue #9) ALSO carry tracking_id + alma_code."""

    def test_duplicate_invoice_error_carries_tracking_and_code(self):
        """``AlmaDuplicateInvoiceError`` must still expose both attributes.

        This is the load-bearing acceptance criterion for #10: the
        propagation has to flow through ``_classify_error``'s
        registry-driven dispatch path, not just the bare ``AlmaAPIError``
        fallback.
        """
        client = AlmaAPIClient('SANDBOX')
        payload = _alma_error_payload(
            "402459",
            "Invoice with the same number already exists for this vendor",
            tracking_id="E01-DUP-INV-001",
        )
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(400, json_body=payload),
        ):
            with self.assertRaises(AlmaDuplicateInvoiceError) as ctx:
                client.post('almaws/v1/acq/invoices', data={'foo': 'bar'})

        # Type was correctly picked from the registry...
        self.assertIsInstance(ctx.exception, AlmaDuplicateInvoiceError)
        self.assertIsInstance(ctx.exception, AlmaAPIError)
        # ...and the per-request fields propagated through the typed
        # subclass via the inherited ``AlmaAPIError.__init__`` -- no
        # subclass-specific ``__init__`` overrides are needed.
        self.assertEqual(ctx.exception.tracking_id, "E01-DUP-INV-001")
        self.assertEqual(ctx.exception.alma_code, "402459")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_status_dispatched_subclass_also_carries_fields(self):
        """A status-dispatched subclass (e.g. 404) must carry the fields too.

        Even though the registry didn't pick the type here -- the choice
        came from the HTTP status fallback -- the parsed body still has a
        ``trackingId``, and that value must land on the exception.
        """
        client = AlmaAPIClient('SANDBOX')
        payload = {
            "errorsExist": True,
            "errorList": {
                "error": [
                    {
                        # Unknown code so registry doesn't match -- forces
                        # the status-fallback branch in ``_classify_error``.
                        "errorCode": "401652",
                        "errorMessage": "Resource not found",
                        "trackingId": "TRK-404",
                    }
                ]
            },
        }
        with patch.object(
            client._session,
            'request',
            return_value=_make_mock_error_response(404, json_body=payload),
        ):
            with self.assertRaises(AlmaResourceNotFoundError) as ctx:
                client.get('almaws/v1/bibs/missing')

        self.assertIsInstance(ctx.exception, AlmaResourceNotFoundError)
        self.assertEqual(ctx.exception.tracking_id, "TRK-404")
        self.assertEqual(ctx.exception.alma_code, "401652")


class TestBackwardsCompatibleConstructor(_AlmaAPIClientTrackingTestBase):
    """Tests that the ``(message, status_code, response)`` signature still works.

    Pre-#10 callers (and the entire issue #9 typed-subclass test suite)
    rely on the three-positional-arg constructor. The new ``tracking_id``
    and ``alma_code`` kwargs are additive and must default to safe values.
    """

    def test_legacy_three_arg_construction_still_works(self):
        """Pre-#10 ``cls(msg, status, response)`` must still construct cleanly."""
        sentinel_response = object()
        exc = AlmaAPIError("legacy message", 418, sentinel_response)
        self.assertEqual(str(exc), "legacy message")
        self.assertEqual(exc.status_code, 418)
        self.assertIs(exc.response, sentinel_response)
        # New attributes default to safe sentinels even when omitted.
        self.assertIsNone(exc.tracking_id)
        self.assertEqual(exc.alma_code, "")

    def test_typed_subclass_inherits_init(self):
        """Subclasses must transparently accept the new kwargs via inheritance."""
        exc = AlmaDuplicateInvoiceError(
            "dup",
            400,
            None,
            tracking_id="TRK-X",
            alma_code="402459",
        )
        self.assertEqual(exc.tracking_id, "TRK-X")
        self.assertEqual(exc.alma_code, "402459")


if __name__ == '__main__':
    unittest.main()
