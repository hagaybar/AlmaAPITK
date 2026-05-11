#!/usr/bin/env python3
"""
Test script for extracting items from POL data using the new helper method.
This uses the extract_items_from_pol_data() method with debugging.
"""
import sys
from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

# Get POL ID from command line
if len(sys.argv) < 2:
    print("Usage: python test_extract_items.py <POL_ID>")
    sys.exit(1)

pol_id = sys.argv[1]

# Initialize
client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

print(f"\nTesting Extract Items from POL Data: {pol_id}")
print("=" * 70)

try:
    # Step 1: Get POL data
    print("\nStep 1: Getting POL data...")
    pol_data = acq.get_pol(pol_id)
    print(f"✓ POL retrieved: {pol_data.get('number', 'N/A')}")
    print(f"  Status: {pol_data.get('status', {}).get('value', 'N/A')}")
    print(f"  Type: {pol_data.get('type', {}).get('value', 'N/A')}")

    # Step 2: Extract invoice reference from POL
    print("\nStep 2: Extracting Invoice Reference from POL...")
    print("-" * 70)

    invoice_ref = pol_data.get('invoice_reference', None)
    # print(type, invoice_ref)
    # print(invoice_ref)


    if invoice_ref:
        print(f"✓ Invoice Reference field found")
        print(f"  Type: {type(invoice_ref)}")

        # Handle if it's a dict
        if isinstance(invoice_ref, dict):
            print(f"  Invoice Reference Keys: {list(invoice_ref.keys())}")
            print(f"  Invoice Reference Content:")
            for key, value in invoice_ref.items():
                print(f"    {key}: {value}")
        # Handle if it's a list
        elif isinstance(invoice_ref, list):
            print(f"  Number of invoice references: {len(invoice_ref)}")
            for i, inv in enumerate(invoice_ref, 1):
                print(f"\n  Invoice Reference {i}:")
                if isinstance(inv, dict):
                    for key, value in inv.items():
                        print(f"    {key}: {value}")
                else:
                    print(f"    {inv}")
        # Handle if it's a simple value
        else:
            print(f"  Invoice Reference Value: {invoice_ref}")
    else:
        print(f"⚠️  No 'invoice_reference' field found in POL data")
        print(f"  Available top-level fields that might contain invoice info:")
        invoice_fields = [key for key in pol_data.keys() if 'invoice' in key.lower()]
        if invoice_fields:
            for field in invoice_fields:
                print(f"    - {field}: {pol_data[field]}")
        else:
            print(f"    No fields with 'invoice' in the name")

    print("-" * 70)

    # Step 3: Extract items from POL data using the NEW method with debug
    print("\nStep 3: Extracting items from POL data (with debug)...")
    print("-" * 70)
    items = acq.extract_items_from_pol_data(pol_data)
    print("-" * 70)

    # Display results
    print(f"\n✓ EXTRACTION COMPLETE")

    if items:
        print(f"\n=== ITEM DETAILS ===")
        for i, item in enumerate(items, 1):
            print(f"\nItem {i}:")
            print(f"  PID (Item ID): {item.get('pid', 'N/A')}")
            print(f"  Barcode: {item.get('barcode', 'N/A')}")
            print(f"  Description: {item.get('description', 'N/A')}")
            print(f"  Process Type: {item.get('process_type', {}).get('value', 'N/A')}")
            print(f"  Receive Date: {item.get('receive_date', 'Not yet received')}")
            print(f"  Item Policy: {item.get('item_policy', {}).get('desc', 'N/A')}")

            # Check if item has been received
            receive_date = item.get('receive_date')
            if receive_date:
                print(f"  ⚠️  Already Received: {receive_date}")
            else:
                print(f"  ✓ Not Yet Received (can be used for receiving test)")

        # Identify unreceived items for next test
        unreceived = [item for item in items if not item.get('receive_date')]
        print(f"\n=== SUMMARY ===")
        print(f"Total Items: {len(items)}")
        print(f"Already Received Items: {len(items) - len(unreceived)}")
        print(f"Unreceived Items: {len(unreceived)}")

        if unreceived:
            print(f"\n✓ First unreceived item ID for TEST 3.1: {unreceived[0].get('pid', 'N/A')}")
        else:
            print(f"\n⚠️  All items already received. Need a POL with unreceived items for receiving test.")
            if items:
                print(f"\nNote: You can still use item ID for testing: {items[0].get('pid', 'N/A')}")
    else:
        print("\n⚠️  WARNING: No items found in POL")
        print("\nPlease check the debug output above to see where the extraction failed.")

    print("\n" + ("✓ TEST PASSED" if items else "✗ TEST FAILED - No items extracted"))

except Exception as e:
    print(f"\n✗ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)