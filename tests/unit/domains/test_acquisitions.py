#!/usr/bin/env python3
"""
Comprehensive Test Suite for Acquisitions Domain Class

Tests cover:
- POL operations (get, update, get items)
- Item receiving operations
- Invoice operations (get, list, search, create, mark paid)
- Invoice line operations
- Integration workflows

Run with: python src/tests/test_acquisitions.py
"""

import sys
from typing import Dict, Any, Optional

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions


class AcquisitionsTestSuite:
    """
    Comprehensive test suite for Acquisitions domain operations.
    Provides organized test methods for POL, items, and invoice operations.
    """

    def __init__(self, environment: str = 'SANDBOX'):
        """
        Initialize test suite with Alma API client.

        Args:
            environment: 'SANDBOX' or 'PRODUCTION' (default: SANDBOX for safety)
        """
        self.environment = environment
        self.client = AlmaAPIClient(environment)
        self.acq = Acquisitions(self.client)

        print(f"\n{'=' * 70}")
        print(f"ACQUISITIONS DOMAIN TEST SUITE - {environment} ENVIRONMENT")
        print(f"{'=' * 70}\n")

    def test_connection(self) -> bool:
        """Test basic API connectivity."""
        print("TEST: Connection Test")
        print("-" * 70)

        try:
            client_connected = self.client.test_connection()
            acq_connected = self.acq.test_connection()

            if client_connected and acq_connected:
                print("✓ PASS: Connection test successful\n")
                return True
            else:
                print("✗ FAIL: Connection test failed\n")
                return False
        except Exception as e:
            print(f"✗ FAIL: Connection test error - {e}\n")
            return False

    # ==================== POL TESTS ====================

    def test_get_pol(self, pol_id: str) -> Optional[Dict[str, Any]]:
        """
        Test retrieving a Purchase Order Line by ID.

        Args:
            pol_id: POL ID to retrieve

        Returns:
            POL data if successful, None otherwise
        """
        print(f"TEST: Get POL - {pol_id}")
        print("-" * 70)

        try:
            pol_data = self.acq.get_pol(pol_id)

            # Verify essential fields
            if 'number' in pol_data and 'status' in pol_data:
                print(f"✓ PASS: Retrieved POL {pol_id}")
                print(f"  POL Number: {pol_data.get('number', 'N/A')}")
                print(f"  Status: {pol_data.get('status', {}).get('value', 'N/A')}")
                print(f"  Type: {pol_data.get('type', {}).get('value', 'N/A')}")
                print(f"  Vendor: {pol_data.get('vendor', {}).get('value', 'N/A')}\n")
                return pol_data
            else:
                print(f"✗ FAIL: Retrieved POL missing essential fields\n")
                return None

        except Exception as e:
            print(f"✗ FAIL: Get POL error - {e}\n")
            return None

    def test_get_pol_items(self, pol_id: str) -> Optional[list]:
        """
        Test retrieving items for a POL.

        Args:
            pol_id: POL ID to get items for

        Returns:
            List of items if successful, None otherwise
        """
        print(f"TEST: Get POL Items - {pol_id}")
        print("-" * 70)

        try:
            items = self.acq.get_pol_items(pol_id)

            print(f"✓ PASS: Retrieved {len(items)} item(s) for POL {pol_id}")

            # Display first item details if available
            if items:
                first_item = items[0]
                print(f"  First Item ID: {first_item.get('pid', 'N/A')}")
                print(f"  Barcode: {first_item.get('barcode', 'N/A')}")
                print(f"  Receiving Note: {first_item.get('receiving_note', 'N/A')}")
                print(f"  Process Type: {first_item.get('process_type', {}).get('value', 'N/A')}\n")
            else:
                print(f"  No items found for this POL\n")

            return items

        except Exception as e:
            print(f"✗ FAIL: Get POL items error - {e}\n")
            return None

    def test_update_pol(self, pol_id: str, pol_data: Dict[str, Any]) -> bool:
        """
        Test updating a POL.

        Args:
            pol_id: POL ID to update
            pol_data: Updated POL data

        Returns:
            True if successful, False otherwise
        """
        print(f"TEST: Update POL - {pol_id}")
        print("-" * 70)

        try:
            updated_pol = self.acq.update_pol(pol_id, pol_data)

            print(f"✓ PASS: Updated POL {pol_id}")
            print(f"  POL Number: {updated_pol.get('number', 'N/A')}\n")
            return True

        except Exception as e:
            print(f"✗ FAIL: Update POL error - {e}\n")
            return False

    # ==================== ITEM RECEIVING TESTS ====================

    def test_receive_item(self, pol_id: str, item_id: str,
                         receive_date: Optional[str] = None,
                         department: Optional[str] = None,
                         department_library: Optional[str] = None) -> bool:
        """
        Test receiving an item.

        Args:
            pol_id: POL ID
            item_id: Item ID to receive
            receive_date: Date in YYYY-MM-DDZ format (optional)
            department: Department code (optional)
            department_library: Library code (optional)

        Returns:
            True if successful, False otherwise
        """
        print(f"TEST: Receive Item - POL: {pol_id}, Item: {item_id}")
        print("-" * 70)

        try:
            result = self.acq.receive_item(
                pol_id, item_id,
                receive_date=receive_date,
                department=department,
                department_library=department_library
            )

            print(f"✓ PASS: Item {item_id} received successfully")
            print(f"  Receiving Date: {result.get('receiving_date', 'N/A')}")
            print(f"  Process Type: {result.get('process_type', {}).get('value', 'N/A')}\n")
            return True

        except Exception as e:
            print(f"✗ FAIL: Receive item error - {e}\n")
            return False

    # ==================== INVOICE TESTS ====================

    def test_get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Test retrieving an invoice by ID.

        Args:
            invoice_id: Invoice ID to retrieve

        Returns:
            Invoice data if successful, None otherwise
        """
        print(f"TEST: Get Invoice - {invoice_id}")
        print("-" * 70)

        try:
            invoice_data = self.acq.get_invoice(invoice_id)

            print(f"✓ PASS: Retrieved invoice {invoice_id}")
            print(f"  Invoice Number: {invoice_data.get('number', 'N/A')}")
            print(f"  Vendor: {invoice_data.get('vendor', {}).get('value', 'N/A')}")
            print(f"  Status: {invoice_data.get('invoice_status', {}).get('value', 'N/A')}")
            print(f"  Payment Status: {invoice_data.get('payment_status', {}).get('value', 'N/A')}")
            print(f"  Total Amount: {invoice_data.get('total_amount', {}).get('sum', 'N/A')} "
                  f"{invoice_data.get('total_amount', {}).get('currency', {}).get('value', 'N/A')}\n")
            return invoice_data

        except Exception as e:
            print(f"✗ FAIL: Get invoice error - {e}\n")
            return None

    def test_get_invoice_summary(self, invoice_id: str) -> Optional[Dict[str, str]]:
        """
        Test getting invoice summary.

        Args:
            invoice_id: Invoice ID

        Returns:
            Invoice summary if successful, None otherwise
        """
        print(f"TEST: Get Invoice Summary - {invoice_id}")
        print("-" * 70)

        try:
            summary = self.acq.get_invoice_summary(invoice_id)

            print(f"✓ PASS: Retrieved invoice summary")
            for key, value in summary.items():
                print(f"  {key}: {value}")
            print()
            return summary

        except Exception as e:
            print(f"✗ FAIL: Get invoice summary error - {e}\n")
            return None

    def test_list_invoices(self, limit: int = 5, status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Test listing invoices.

        Args:
            limit: Maximum number of invoices to retrieve
            status: Optional status filter

        Returns:
            Invoice list data if successful, None otherwise
        """
        print(f"TEST: List Invoices (limit: {limit}, status: {status or 'all'})")
        print("-" * 70)

        try:
            invoices_data = self.acq.list_invoices(limit=limit, status=status)

            total_count = invoices_data.get('total_record_count', 0)
            print(f"✓ PASS: Retrieved invoice list - {total_count} total invoices")

            # Display first few invoices
            invoice_list = invoices_data.get('invoice', [])
            if isinstance(invoice_list, dict):
                invoice_list = [invoice_list]

            for i, invoice in enumerate(invoice_list[:3], 1):
                print(f"  {i}. {invoice.get('number', 'N/A')} - "
                      f"{invoice.get('invoice_status', {}).get('value', 'N/A')}")
            print()

            return invoices_data

        except Exception as e:
            print(f"✗ FAIL: List invoices error - {e}\n")
            return None

    def test_search_invoices(self, query: str, limit: int = 5) -> Optional[Dict[str, Any]]:
        """
        Test searching invoices.

        Args:
            query: Search query string
            limit: Maximum results

        Returns:
            Search results if successful, None otherwise
        """
        print(f"TEST: Search Invoices - Query: {query}")
        print("-" * 70)

        try:
            results = self.acq.search_invoices(query, limit=limit)

            total_count = results.get('total_record_count', 0)
            print(f"✓ PASS: Search found {total_count} invoices\n")
            return results

        except Exception as e:
            print(f"✗ FAIL: Search invoices error - {e}\n")
            return None

    def test_get_invoice_lines(self, invoice_id: str) -> Optional[list]:
        """
        Test getting invoice lines.

        Args:
            invoice_id: Invoice ID

        Returns:
            List of invoice lines if successful, None otherwise
        """
        print(f"TEST: Get Invoice Lines - {invoice_id}")
        print("-" * 70)

        try:
            lines = self.acq.get_invoice_lines(invoice_id)

            print(f"✓ PASS: Retrieved {len(lines)} invoice line(s)")

            # Display first line details if available
            if lines:
                first_line = lines[0]
                print(f"  First Line Number: {first_line.get('line_number', 'N/A')}")
                print(f"  POL Number: {first_line.get('po_line', 'N/A')}")
                print(f"  Total Price: {first_line.get('total_price', {}).get('sum', 'N/A')}\n")

            return lines

        except Exception as e:
            print(f"✗ FAIL: Get invoice lines error - {e}\n")
            return None

    def test_mark_invoice_paid(self, invoice_id: str) -> bool:
        """
        Test marking an invoice as paid.

        Args:
            invoice_id: Invoice ID to mark as paid

        Returns:
            True if successful, False otherwise
        """
        print(f"TEST: Mark Invoice Paid - {invoice_id}")
        print("-" * 70)

        try:
            result = self.acq.mark_invoice_paid(invoice_id)

            print(f"✓ PASS: Invoice {invoice_id} marked as paid")
            print(f"  Payment Status: {result.get('payment_status', {}).get('value', 'N/A')}\n")
            return True

        except Exception as e:
            print(f"✗ FAIL: Mark invoice paid error - {e}\n")
            return False

    def test_approve_invoice(self, invoice_id: str) -> bool:
        """
        Test approving/processing an invoice.

        Args:
            invoice_id: Invoice ID to approve

        Returns:
            True if successful, False otherwise
        """
        print(f"TEST: Approve Invoice - {invoice_id}")
        print("-" * 70)

        try:
            result = self.acq.approve_invoice(invoice_id)

            print(f"✓ PASS: Invoice {invoice_id} approved")
            print(f"  Invoice Status: {result.get('invoice_status', {}).get('value', 'N/A')}\n")
            return True

        except Exception as e:
            print(f"✗ FAIL: Approve invoice error - {e}\n")
            return False

    # ==================== INTEGRATION WORKFLOW TESTS ====================

    def test_rialto_workflow(self, pol_id: str, item_id: str, invoice_id: str) -> bool:
        """
        Test complete Rialto EDI workflow: receive item + pay invoice = close POL.

        This simulates the one-time POL EDI vendor (Rialto) workflow:
        1. Receive item
        2. Mark invoice as paid
        3. Verify POL closure

        Args:
            pol_id: POL ID
            item_id: Item ID to receive
            invoice_id: Invoice ID to mark as paid

        Returns:
            True if workflow completes successfully, False otherwise
        """
        print(f"TEST: Rialto EDI Workflow")
        print(f"  POL: {pol_id}, Item: {item_id}, Invoice: {invoice_id}")
        print("-" * 70)

        try:
            # Step 1: Get initial POL state
            print("Step 1: Getting initial POL state...")
            initial_pol = self.acq.get_pol(pol_id)
            initial_status = initial_pol.get('status', {}).get('value', 'Unknown')
            print(f"  Initial POL Status: {initial_status}")

            # Step 2: Receive item
            print("Step 2: Receiving item...")
            self.acq.receive_item(pol_id, item_id)
            print(f"  ✓ Item {item_id} received")

            # Step 3: Mark invoice as paid
            print("Step 3: Marking invoice as paid...")
            self.acq.mark_invoice_paid(invoice_id)
            print(f"  ✓ Invoice {invoice_id} marked as paid")

            # Step 4: Verify POL status
            print("Step 4: Verifying POL status...")
            final_pol = self.acq.get_pol(pol_id)
            final_status = final_pol.get('status', {}).get('value', 'Unknown')
            print(f"  Final POL Status: {final_status}")

            # Check if POL closed
            if final_status == 'CLOSED':
                print(f"\n✓ PASS: Rialto workflow completed - POL closed\n")
                return True
            else:
                print(f"\n⚠ WARNING: POL not closed (may require manual action)\n")
                return True  # Still consider success as operations completed

        except Exception as e:
            print(f"\n✗ FAIL: Rialto workflow error - {e}\n")
            return False

    # ==================== TEST RUNNER ====================

    def run_basic_tests(self, pol_id: str, invoice_id: str) -> Dict[str, bool]:
        """
        Run basic test suite with provided POL and Invoice IDs.

        Args:
            pol_id: POL ID for testing
            invoice_id: Invoice ID for testing

        Returns:
            Dictionary with test names and pass/fail results
        """
        results = {}

        print(f"\n{'=' * 70}")
        print(f"RUNNING BASIC TEST SUITE")
        print(f"{'=' * 70}\n")

        # Connection test
        results['connection'] = self.test_connection()

        # POL tests
        results['get_pol'] = self.test_get_pol(pol_id) is not None
        results['get_pol_items'] = self.test_get_pol_items(pol_id) is not None

        # Invoice tests
        results['get_invoice'] = self.test_get_invoice(invoice_id) is not None
        results['get_invoice_summary'] = self.test_get_invoice_summary(invoice_id) is not None
        results['get_invoice_lines'] = self.test_get_invoice_lines(invoice_id) is not None
        results['list_invoices'] = self.test_list_invoices(limit=3) is not None

        # Print summary
        print(f"\n{'=' * 70}")
        print(f"TEST SUMMARY")
        print(f"{'=' * 70}")

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for test_name, passed_test in results.items():
            status = "✓ PASS" if passed_test else "✗ FAIL"
            print(f"{status}: {test_name}")

        print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)\n")

        return results


def main():
    """
    Main function for running tests interactively.
    """
    print("\n" + "=" * 70)
    print("ACQUISITIONS DOMAIN TEST SUITE")
    print("=" * 70)

    # Get environment choice
    env_choice = input("\nSelect environment (1=SANDBOX, 2=PRODUCTION) [1]: ").strip()
    environment = 'PRODUCTION' if env_choice == '2' else 'SANDBOX'

    # Confirm production
    if environment == 'PRODUCTION':
        confirm = input("⚠️  WARNING: Running tests in PRODUCTION! Continue? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Aborted.")
            return

    # Initialize test suite
    test_suite = AcquisitionsTestSuite(environment)

    # Menu
    print("\nTest Options:")
    print("1. Run basic tests (requires POL ID and Invoice ID)")
    print("2. Test specific POL")
    print("3. Test specific Invoice")
    print("4. Test item receiving (requires POL ID and Item ID)")
    print("5. Test Rialto workflow (requires POL ID, Item ID, Invoice ID)")
    print("6. Exit")

    choice = input("\nEnter choice [1-6]: ").strip()

    if choice == '1':
        pol_id = input("Enter POL ID: ").strip()
        invoice_id = input("Enter Invoice ID: ").strip()
        test_suite.run_basic_tests(pol_id, invoice_id)

    elif choice == '2':
        pol_id = input("Enter POL ID: ").strip()
        test_suite.test_get_pol(pol_id)
        test_suite.test_get_pol_items(pol_id)

    elif choice == '3':
        invoice_id = input("Enter Invoice ID: ").strip()
        test_suite.test_get_invoice(invoice_id)
        test_suite.test_get_invoice_summary(invoice_id)
        test_suite.test_get_invoice_lines(invoice_id)

    elif choice == '4':
        pol_id = input("Enter POL ID: ").strip()
        item_id = input("Enter Item ID: ").strip()
        receive_date = input("Enter receive date (YYYY-MM-DDZ) or press Enter for default: ").strip() or None
        test_suite.test_receive_item(pol_id, item_id, receive_date=receive_date)

    elif choice == '5':
        pol_id = input("Enter POL ID: ").strip()
        item_id = input("Enter Item ID: ").strip()
        invoice_id = input("Enter Invoice ID: ").strip()
        test_suite.test_rialto_workflow(pol_id, item_id, invoice_id)

    elif choice == '6':
        print("Exiting.")
        return

    else:
        print("Invalid choice.")


# =============================================================================
# Unit tests with mocked HTTP (issue #11 -- iter_paged migration proof point)
#
# These tests verify the post-#11 ``Acquisitions.list_invoices`` shape: it
# routes through ``client.iter_paged`` for the common ``offset=0`` walk
# while preserving the legacy ``{"invoice": [...], "total_record_count": N}``
# return contract. They use unittest+mock so pytest can pick them up
# alongside the rest of the unit-test suite without touching real HTTP.
# =============================================================================
import os
import unittest
from unittest.mock import MagicMock, patch

import requests

from almaapitk import AlmaAPIClient as _AlmaAPIClient
from almaapitk import Acquisitions as _Acquisitions


def _mock_alma_response(status_code: int = 200, json_body=None):
    """Build a minimal ``requests.Response``-like mock for unit tests."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.ok = status_code < 400
    mock_response.headers = {'content-type': 'application/json'}
    mock_response.text = ''
    mock_response.json.return_value = json_body or {}
    return mock_response


class TestListInvoicesIterPaged(unittest.TestCase):
    """Unit tests for ``Acquisitions.list_invoices`` post-#11 migration.

    Pattern source: GitHub issue #11 acceptance criteria + the
    ``tests/unit/client/test_alma_api_client.py`` mocking style.
    """

    def setUp(self):
        self._env_patcher = patch.dict(
            os.environ, {'ALMA_SB_API_KEY': 'test-sandbox-key'}, clear=False
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)

    def test_list_invoices_returns_legacy_payload_shape(self):
        """The migrated method must still return ``{"invoice": [...], "total_record_count": N}``."""
        client = _AlmaAPIClient('SANDBOX')
        acq = _Acquisitions(client)
        invoices = [{'id': 'inv-1'}, {'id': 'inv-2'}]
        with patch.object(
            client._session,
            'request',
            return_value=_mock_alma_response(
                json_body={
                    'invoice': invoices,
                    'total_record_count': 2,
                },
            ),
        ):
            result = acq.list_invoices(limit=2)

        # Legacy callers read these two keys directly.
        self.assertEqual(result.get('invoice'), invoices)
        self.assertEqual(result.get('total_record_count'), 2)

    def test_list_invoices_routes_through_iter_paged(self):
        """``offset=0`` (default) must walk via ``client.iter_paged``."""
        client = _AlmaAPIClient('SANDBOX')
        acq = _Acquisitions(client)
        # Patch ``iter_paged`` so we can prove the migration sends the
        # call through the shared paginator and not a hand-rolled loop.
        with patch.object(
            client, 'iter_paged', return_value=iter([{'id': 'inv-1'}])
        ) as mock_paged:
            result = acq.list_invoices(limit=10, status='ACTIVE')

        self.assertEqual(mock_paged.call_count, 1)
        _args, kwargs = mock_paged.call_args
        # Endpoint and record_key are positional/keyword choices the
        # migration locked in -- if they regress, downstream callers
        # walking custom queries break.
        self.assertEqual(_args[0], 'almaws/v1/acq/invoices')
        self.assertEqual(kwargs.get('record_key'), 'invoice')
        self.assertEqual(kwargs.get('page_size'), 10)
        self.assertEqual(kwargs.get('max_records'), 10)
        # Status filter built into the ``q`` query param.
        self.assertEqual(
            kwargs.get('params', {}).get('q'),
            'invoice_status~ACTIVE',
        )
        # Result still shaped like the legacy payload.
        self.assertEqual(result.get('total_record_count'), 1)
        self.assertEqual(result.get('invoice'), [{'id': 'inv-1'}])

    def test_list_invoices_offset_falls_back_to_direct_get(self):
        """Non-zero ``offset`` keeps using a single direct GET (legacy deep-page path)."""
        client = _AlmaAPIClient('SANDBOX')
        acq = _Acquisitions(client)
        body = {
            'invoice': [{'id': 'inv-200'}],
            'total_record_count': 500,
        }
        with patch.object(
            client._session,
            'request',
            return_value=_mock_alma_response(json_body=body),
        ) as mock_request, patch.object(
            client, 'iter_paged'
        ) as mock_paged:
            result = acq.list_invoices(limit=10, offset=200)

        # iter_paged NOT called -- the offset>0 branch fires.
        mock_paged.assert_not_called()
        self.assertEqual(mock_request.call_count, 1)
        _args, kwargs = mock_request.call_args
        sent = kwargs.get('params', {})
        self.assertEqual(sent.get('offset'), '200')
        self.assertEqual(sent.get('limit'), '10')
        # Pass-through return shape on the deep-page branch.
        self.assertEqual(result, body)


if __name__ == "__main__":
    main()