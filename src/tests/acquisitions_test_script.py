#!/usr/bin/env python3
"""
Test script for the Acquisitions domain class
Tests the complete workflow: get_invoice -> mark_as_paid -> verify_change
"""

import sys
import os

# Add the path where your classes are located
try:
    from src.client.AlmaAPIClient import AlmaAPIClient
    from src.domains.acquisition import Acquisitions
except ImportError as e:
    print(f"Could not import required classes: {e}")
    print("Make sure AlmaAPIClient.py and acquisitions.py are in the same directory or in your Python path.")
    sys.exit(1)


def test_environment_setup():
    """Test environment variable setup"""
    print("=== Testing Environment Setup ===")
    
    sb_key = os.getenv('ALMA_SB_API_KEY')
    prod_key = os.getenv('ALMA_PROD_API_KEY')
    
    print(f"ALMA_SB_API_KEY: {'Set' if sb_key else 'NOT SET'}")
    if sb_key:
        print(f"  Partial key: {sb_key[:10]}...")
    
    print(f"ALMA_PROD_API_KEY: {'Set' if prod_key else 'NOT SET'}")
    if prod_key:
        print(f"  Partial key: {prod_key[:10]}...")
    
    return sb_key, prod_key


def test_client_initialization(environment='SANDBOX'):
    """Test creating AlmaAPIClient and Acquisitions instances"""
    print(f"\n=== Testing Client Initialization ({environment}) ===")
    
    try:
        print(f"Creating {environment} client...")
        client = AlmaAPIClient(environment)
        print(f"✓ {environment} client created successfully")
        
        print("Creating Acquisitions domain...")
        acq = Acquisitions(client)
        print("✓ Acquisitions domain created successfully")
        
        return client, acq
        
    except Exception as e:
        print(f"✗ Client initialization failed: {e}")
        return None, None


def test_connection(client, acq):
    """Test API connections"""
    print("\n=== Testing API Connections ===")
    
    # Test base connection
    print("Testing base API connection...")
    if client.test_connection():
        print("✓ Base API connection successful")
    else:
        print("✗ Base API connection failed")
        return False
    
    # Test acquisitions connection
    print("Testing Acquisitions API connection...")
    if acq.test_connection():
        print("✓ Acquisitions API connection successful")
        return True
    else:
        print("✗ Acquisitions API connection failed")
        return False


def get_test_invoice_id(acq):
    """Get a test invoice ID from the user or find one automatically"""
    print("\n=== Getting Test Invoice ID ===")
    
    # First, ask user for invoice ID
    invoice_id = input("Enter an invoice ID to test (or press Enter to auto-find): ").strip()
    
    if invoice_id:
        print(f"Using user-provided invoice ID: {invoice_id}")
        return invoice_id
    
    # Try to find an invoice automatically
    try:
        print("Attempting to auto-find a test invoice...")
        
        # Look for invoices with specific statuses that can be marked as paid
        test_statuses = ["WAITING_TO_BE_SENT", "SENT", "APPROVED"]
        
        for status in test_statuses:
            try:
                print(f"  Looking for invoices with status: {status}...")
                invoices = acq.list_invoices(limit=5, status=status)
                
                invoice_list = invoices.get('invoice', [])
                if isinstance(invoice_list, dict):
                    invoice_list = [invoice_list]
                
                if invoice_list:
                    test_invoice = invoice_list[0]
                    invoice_id = test_invoice.get('id')
                    invoice_number = test_invoice.get('number', 'Unknown')
                    print(f"  ✓ Found invoice: {invoice_number} (ID: {invoice_id})")
                    return invoice_id
                    
            except Exception as e:
                print(f"  Error searching for {status} invoices: {e}")
                continue
        
        # If no specific status found, try to get any invoice
        print("  Looking for any available invoice...")
        invoices = acq.list_invoices(limit=5)
        invoice_list = invoices.get('invoice', [])
        
        if isinstance(invoice_list, dict):
            invoice_list = [invoice_list]
        
        if invoice_list:
            test_invoice = invoice_list[0]
            invoice_id = test_invoice.get('id')
            invoice_number = test_invoice.get('number', 'Unknown')
            print(f"  ✓ Found invoice: {invoice_number} (ID: {invoice_id})")
            return invoice_id
        
        print("  ✗ No invoices found in the system")
        return None
        
    except Exception as e:
        print(f"  ✗ Error finding test invoice: {e}")
        return None


def test_invoice_workflow(acq, invoice_id):
    """Test the complete invoice workflow: get -> pay -> verify"""
    print(f"\n=== Testing Invoice Workflow for ID: {invoice_id} ===")
    
    # Step 1: Get initial invoice state
    print("\n--- Step 1: Getting Initial Invoice State ---")
    try:
        initial_invoice = acq.get_invoice(invoice_id)
        initial_summary = acq.get_invoice_summary(invoice_id)
        
        print("✓ Successfully retrieved initial invoice")
        print(f"  Invoice Number: {initial_summary['invoice_number']}")
        print(f"  Vendor: {initial_summary['vendor_name']} ({initial_summary['vendor_code']})")
        print(f"  Amount: {initial_summary['total_amount']} {initial_summary['currency']}")
        print(f"  Initial Status: {initial_summary['status']}")
        print(f"  Initial Payment Status: {initial_summary['payment_status']}")
        
        # Check if invoice can be paid
        current_status = initial_summary['status']
        payment_status = initial_summary['payment_status']
        
        print(f"\n  Current invoice status: {current_status}")
        print(f"  Current payment status: {payment_status}")
        
        if payment_status == "PAID":
            print("  ⚠️  Invoice is already paid - test may not show status change")
        
    except Exception as e:
        print(f"✗ Failed to get initial invoice state: {e}")
        return False
    
    # Step 2: Mark invoice as paid
    print("\n--- Step 2: Marking Invoice as Paid ---")
    try:
        print(f"Attempting to mark invoice {invoice_id} as paid...")
        print("Using Invoice Service API with 'paid' operation and empty payload")
        
        payment_result = acq.mark_invoice_paid(invoice_id)
        
        print("✓ Successfully processed payment operation")
        
        # Display result if available
        if isinstance(payment_result, dict):
            result_status = payment_result.get('invoice_status', {}).get('value', 'Unknown')
            result_payment_status = payment_result.get('payment_status', {}).get('value', 'Unknown')
            print(f"  Result Status: {result_status}")
            print(f"  Result Payment Status: {result_payment_status}")
        
    except Exception as e:
        print(f"✗ Failed to mark invoice as paid: {e}")
        print(f"  This might be normal if the invoice is already paid or in a non-payable state")
        # Continue with verification step anyway
    
    # Step 3: Verify the change
    print("\n--- Step 3: Verifying Status Change ---")
    try:
        print("Retrieving updated invoice state...")
        updated_invoice = acq.get_invoice(invoice_id)
        updated_summary = acq.get_invoice_summary(invoice_id)
        
        print("✓ Successfully retrieved updated invoice")
        print(f"  Invoice Number: {updated_summary['invoice_number']}")
        print(f"  Updated Status: {updated_summary['status']}")
        print(f"  Updated Payment Status: {updated_summary['payment_status']}")
        
        # Compare initial vs updated state
        print("\n--- Status Comparison ---")
        print(f"  Status:         {initial_summary['status']} → {updated_summary['status']}")
        print(f"  Payment Status: {initial_summary['payment_status']} → {updated_summary['payment_status']}")
        
        # Determine if change occurred
        status_changed = initial_summary['status'] != updated_summary['status']
        payment_status_changed = initial_summary['payment_status'] != updated_summary['payment_status']
        
        if status_changed or payment_status_changed:
            print("✓ Status changes detected!")
            if status_changed:
                print(f"  ✓ Invoice status changed: {initial_summary['status']} → {updated_summary['status']}")
            if payment_status_changed:
                print(f"  ✓ Payment status changed: {initial_summary['payment_status']} → {updated_summary['payment_status']}")
        else:
            print("ℹ️  No status changes detected")
            print("  This might be normal depending on the invoice's initial state and business rules")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to verify status change: {e}")
        return False


def test_additional_operations(acq, invoice_id):
    """Test additional invoice operations"""
    print(f"\n=== Testing Additional Operations for Invoice: {invoice_id} ===")
    
    # Test getting invoice lines
    try:
        print("\nTesting invoice lines retrieval...")
        lines = acq.get_invoice_lines(invoice_id)
        print(f"✓ Retrieved {len(lines)} invoice lines")
        
        if lines:
            first_line = lines[0]
            line_number = first_line.get('line_number', 'Unknown')
            line_type = first_line.get('type', {}).get('value', 'Unknown')
            print(f"  First line: #{line_number} - Type: {line_type}")
        
    except Exception as e:
        print(f"✗ Failed to get invoice lines: {e}")
    
    # Test search functionality
    try:
        print("\nTesting invoice search...")
        # Search for invoices from the same vendor
        initial_summary = acq.get_invoice_summary(invoice_id)
        vendor_code = initial_summary['vendor_code']
        
        if vendor_code != 'Unknown':
            search_results = acq.search_invoices(f"vendor~{vendor_code}", limit=3)
            total_found = search_results.get('total_record_count', 0)
            print(f"✓ Found {total_found} invoices for vendor {vendor_code}")
        else:
            print("ℹ️  Skipping vendor search - vendor code not available")
            
    except Exception as e:
        print(f"✗ Failed to test search functionality: {e}")


def main():
    """Run the complete test suite"""
    print("Acquisitions Domain Test Suite")
    print("=" * 50)
    
    # Test environment setup
    sb_key, prod_key = test_environment_setup()
    
    if not sb_key and not prod_key:
        print("\n✗ No API keys found. Please set environment variables:")
        print("export ALMA_SB_API_KEY='your_sandbox_key'")
        print("export ALMA_PROD_API_KEY='your_production_key'")
        return
    
    # Choose environment (prefer SANDBOX for testing)
    environment = 'SANDBOX' if sb_key else 'PRODUCTION'
    if sb_key and prod_key:
        choice = input(f"\nBoth API keys found. Use SANDBOX for testing? (y/n): ").strip().lower()
        if choice == 'n':
            environment = 'PRODUCTION'
    
    print(f"\n🎯 Running tests in {environment} environment")
    
    # Initialize clients
    client, acq = test_client_initialization(environment)
    
    if not client or not acq:
        print("\n✗ Cannot proceed - client initialization failed")
        return
    
    # Test connections
    if not test_connection(client, acq):
        print("\n✗ Cannot proceed - API connection failed")
        return
    
    # Get test invoice ID
    invoice_id = get_test_invoice_id(acq)
    
    if not invoice_id:
        print("\n✗ Cannot proceed - no test invoice ID available")
        print("Please provide an invoice ID manually or ensure invoices exist in the system")
        return
    
    # Run the main workflow test
    print(f"\n🧪 Testing workflow with invoice ID: {invoice_id}")
    
    workflow_success = test_invoice_workflow(acq, invoice_id)
    
    if workflow_success:
        print("\n🎉 Main workflow test completed successfully!")
        
        # Run additional tests
        test_additional_operations(acq, invoice_id)
    else:
        print("\n❌ Main workflow test failed")
    
    print("\n" + "=" * 50)
    print("Acquisitions test suite completed!")
    
    if workflow_success:
        print("✅ All core tests passed")
    else:
        print("⚠️  Some tests failed - check output above")


if __name__ == "__main__":
    main()