#!/usr/bin/env python3
"""
Test script for AlmaAPIClient logging integration.

Tests automatic logging of all API requests/responses.
"""

from almaapitk import AlmaAPIClient

def main():
    """Test AlmaAPIClient logging."""
    print("\n" + "=" * 70)
    print(" AlmaAPIClient Logging Integration Test")
    print("=" * 70)
    print("\nThis test will:")
    print("1. Create an AlmaAPIClient instance")
    print("2. Make a simple API call (test_connection)")
    print("3. Log all requests/responses automatically")
    print("4. Check logs for API key redaction\n")

    try:
        # Create client
        print("Creating AlmaAPIClient (SANDBOX)...")
        client = AlmaAPIClient(environment='SANDBOX')

        # Test connection (makes a GET request)
        print("\nTesting connection to Alma API...")
        success = client.test_connection()

        if success:
            print("✓ Connection successful!")
        else:
            print("✗ Connection failed!")

        print("\n" + "=" * 70)
        print("TEST COMPLETE")
        print("=" * 70)
        print("\nCheck logs:")
        print("  Console: Should show colored DEBUG logs above")
        print("  File: logs/api_requests/$(date +%Y-%m-%d)/api_client.log")
        print("\nVerify API key redaction:")
        print("  grep 'REDACTED' logs/api_requests/$(date +%Y-%m-%d)/api_client.log")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
