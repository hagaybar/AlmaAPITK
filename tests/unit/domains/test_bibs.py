"""
Unit tests for the BibliographicRecords domain class.

Currently scoped to the issue #11 ``iter_paged`` migration proof point:
``BibliographicRecords.search_records`` is now a thin wrapper over
``client.iter_paged(...)`` and returns a list of bib record dicts.

Pattern source: GitHub issue #11 acceptance criteria +
``tests/unit/client/test_alma_api_client.py`` mocking style.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

import requests

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.bibs import BibliographicRecords


def _mock_alma_response(status_code: int = 200, json_body=None):
    """Build a minimal ``requests.Response``-like mock for unit tests."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.ok = status_code < 400
    mock_response.headers = {'content-type': 'application/json'}
    mock_response.text = ''
    mock_response.json.return_value = json_body or {}
    return mock_response


class _BibsTestBase(unittest.TestCase):
    """Shared setUp injecting a fake API key into the environment."""

    def setUp(self):
        self._env_patcher = patch.dict(
            os.environ, {'ALMA_SB_API_KEY': 'test-sandbox-key'}, clear=False
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)


class TestSearchRecordsIterPaged(_BibsTestBase):
    """Tests for ``BibliographicRecords.search_records`` post-#11 migration."""

    def test_search_records_validates_empty_query(self):
        """Empty query must raise ``AlmaValidationError``."""
        client = AlmaAPIClient('SANDBOX')
        bibs = BibliographicRecords(client)
        with self.assertRaises(AlmaValidationError):
            bibs.search_records(q='')

    def test_search_records_validates_limit_over_100(self):
        """Limit > 100 must raise ``AlmaValidationError`` (Alma per-endpoint cap)."""
        client = AlmaAPIClient('SANDBOX')
        bibs = BibliographicRecords(client)
        with self.assertRaises(AlmaValidationError):
            bibs.search_records(q='title~foo', limit=101)

    def test_search_records_returns_list(self):
        """Migrated method must return a list of bib dicts (not AlmaResponse)."""
        client = AlmaAPIClient('SANDBOX')
        bibs = BibliographicRecords(client)
        records = [{'mms_id': '991'}, {'mms_id': '992'}]
        with patch.object(
            client._session,
            'request',
            return_value=_mock_alma_response(
                json_body={
                    'bib': records,
                    'total_record_count': 2,
                },
            ),
        ):
            out = bibs.search_records(q='title~foo', limit=10)

        self.assertIsInstance(out, list)
        self.assertEqual(out, records)

    def test_search_records_routes_through_iter_paged(self):
        """``offset=0`` (default) must walk via ``client.iter_paged``."""
        client = AlmaAPIClient('SANDBOX')
        bibs = BibliographicRecords(client)
        with patch.object(
            client,
            'iter_paged',
            return_value=iter([{'mms_id': '991'}]),
        ) as mock_paged:
            out = bibs.search_records(
                q='title~foo', limit=5, order_by='date', direction='desc'
            )

        self.assertEqual(out, [{'mms_id': '991'}])
        self.assertEqual(mock_paged.call_count, 1)
        _args, kwargs = mock_paged.call_args
        self.assertEqual(_args[0], 'almaws/v1/bibs')
        self.assertEqual(kwargs.get('record_key'), 'bib')
        self.assertEqual(kwargs.get('page_size'), 5)
        self.assertEqual(kwargs.get('max_records'), 5)
        sent_params = kwargs.get('params', {})
        self.assertEqual(sent_params.get('q'), 'title~foo')
        self.assertEqual(sent_params.get('order_by'), 'date')
        self.assertEqual(sent_params.get('direction'), 'desc')

    def test_search_records_default_order_by_is_mms_id(self):
        """When ``order_by`` is omitted, the wrapper must default to ``mms_id``."""
        client = AlmaAPIClient('SANDBOX')
        bibs = BibliographicRecords(client)
        with patch.object(
            client, 'iter_paged', return_value=iter([])
        ) as mock_paged:
            bibs.search_records(q='title~foo')

        _args, kwargs = mock_paged.call_args
        self.assertEqual(kwargs.get('params', {}).get('order_by'), 'mms_id')

    def test_search_records_offset_falls_back_to_direct_get(self):
        """Non-zero ``offset`` skips ``iter_paged`` and issues a single GET."""
        client = AlmaAPIClient('SANDBOX')
        bibs = BibliographicRecords(client)
        body = {'bib': [{'mms_id': '991'}], 'total_record_count': 500}
        with patch.object(
            client._session,
            'request',
            return_value=_mock_alma_response(json_body=body),
        ) as mock_request, patch.object(
            client, 'iter_paged'
        ) as mock_paged:
            out = bibs.search_records(q='title~foo', limit=10, offset=200)

        mock_paged.assert_not_called()
        self.assertEqual(mock_request.call_count, 1)
        _args, kwargs = mock_request.call_args
        sent = kwargs.get('params', {})
        self.assertEqual(sent.get('offset'), '200')
        self.assertEqual(sent.get('limit'), '10')
        # Returns the extracted ``bib`` list, not the full envelope.
        self.assertEqual(out, [{'mms_id': '991'}])


if __name__ == '__main__':
    unittest.main()
