#!/usr/bin/env python3
"""
Test verbose logging with full request/response bodies.

Demonstrates detailed logging for POST/PUT operations with complete data objects.
"""

from almaapitk import AlmaAPIClient
from almaapitk import Acquisitions

def test_get_pol_verbose():
    """Test GET with full response body logging."""
    print("\n" + "=" * 70)
    print("TEST: Get POL with Full Response Body Logging")
    print("=" * 70)

    client = AlmaAPIClient(environment='SANDBOX')
    acq = Acquisitions(client)

    pol_id = "POL-12350"
    print(f"\nGetting POL: {pol_id}")
    print("This will log:")
    print("  1. Request summary (method, endpoint, params)")
    print("  2. Response summary (status, duration)")
    print("  3. FULL response body (complete POL object)\n")

    try:
        pol_data = acq.get_pol(pol_id)
        print(f"✓ POL retrieved: {pol_data.get('number')}")
        print(f"  Status: {pol_data.get('status', {}).get('value')}")
        print(f"\n→ Check logs/api_requests/$(date +%Y-%m-%d)/api_client.log")
        print("  You'll see the COMPLETE POL object with all fields")

    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    """Run verbose logging test."""
    print("\n" + "*" * 70)
    print(" Verbose Logging Test - Full Request/Response Bodies")
    print("*" * 70)
    print("\nThis test demonstrates detailed logging with:")
    print("  - Full request bodies (for POST/PUT)")
    print("  - Full response bodies (complete JSON objects)")
    print("  - All logged at DEBUG level")
    print()

    test_get_pol_verbose()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nView the detailed logs:")
    print("  tail -50 logs/api_requests/$(date +%Y-%m-%d)/api_client.log")
    print("\nYou'll see entries like:")
    print('  - "API Request: GET ..." (summary)')
    print('  - "Response body from ..." (FULL POL object)')
    print('  - "API Response: 200" (summary with duration)')
    print()


if __name__ == "__main__":
    main()
