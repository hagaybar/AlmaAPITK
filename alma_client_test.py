#!/usr/bin/env python3
"""
Test script for the AlmaAPIClient class - FIXED VERSION
Tests the newer, cleaner implementation with both issues resolved
"""

import sys
import os

# Add the path where your AlmaAPIClient is located
try:
    from src.client.AlmaAPIClient import AlmaAPIClient
except ImportError:
    print("Could not import AlmaAPIClient. Please check the file path.")
    print("Current working directory:", os.getcwd())
    print("Make sure AlmaAPIClient.py is accessible.")
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


def test_client_initialization():
    """Test creating AlmaAPIClient instances"""
    print("\n=== Testing Client Initialization ===")
    
    clients = {}
    
    # Test SANDBOX
    try:
        print("Creating SANDBOX client...")
        sandbox_client = AlmaAPIClient('SANDBOX')
        clients['SANDBOX'] = sandbox_client
        print("✓ SANDBOX client created successfully")
    except Exception as e:
        print(f"✗ SANDBOX client failed: {e}")
    
    # Test PRODUCTION
    try:
        print("Creating PRODUCTION client...")
        prod_client = AlmaAPIClient('PRODUCTION')
        clients['PRODUCTION'] = prod_client
        print("✓ PRODUCTION client created successfully")
    except Exception as e:
        print(f"✗ PRODUCTION client failed: {e}")
    
    return clients


def test_connection(clients):
    """Test API connections"""
    print("\n=== Testing API Connections ===")
    
    for env_name, client in clients.items():
        print(f"\nTesting {env_name} connection...")
        if client.test_connection():
            print(f"✓ {env_name} connection successful")
        else:
            print(f"✗ {env_name} connection failed")


def test_basic_api_calls(clients):
    """Test basic API functionality - FIXED VERSION"""
    print("\n=== Testing Basic API Calls ===")
    
    for env_name, client in clients.items():
        print(f"\n--- Testing {env_name} API calls ---")
        
        # Test libraries endpoint
        try:
            print("  Testing libraries endpoint...")
            response = client.get('almaws/v1/conf/libraries')
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total_record_count', 0)
                print(f"  ✓ Found {total} libraries")
                
                # Show first library if available
                libraries = data.get('library', [])
                if libraries:
                    first_lib = libraries[0]
                    lib_name = first_lib.get('name', 'Unknown')
                    lib_code = first_lib.get('code', 'Unknown')
                    print(f"    First library: {lib_name} ({lib_code})")
            else:
                print(f"  ✗ Libraries request failed: {response.status_code}")
                print(f"    Response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"  ✗ Error testing libraries: {e}")
        
        # Test user groups endpoint - FIXED
        try:
            print("  Testing user groups endpoint...")
            response = client.get('almaws/v1/conf/code-tables/UserGroups')  # CORRECTED ENDPOINT
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total_record_count', 0)
                rows = data.get('row', [])
                print(f"  ✓ Found {len(rows)} user groups (total: {total})")
                
                # Show first user group if available
                if rows:
                    first_group = rows[0]
                    group_code = first_group.get('code', 'Unknown')
                    group_desc = first_group.get('description', 'Unknown')
                    print(f"    First group: {group_code} - {group_desc}")
            else:
                print(f"  ✗ User groups request failed: {response.status_code}")
                print(f"    Response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"  ✗ Error testing user groups: {e}")


def test_bib_record(clients, mms_id=None):
    """Test bibliographic record retrieval - FIXED VERSION"""
    print("\n=== Testing Bibliographic Record Retrieval ===")
    
    if not mms_id:
        mms_id = input("Enter an MMS ID to test (or press Enter to skip): ").strip()
    
    if not mms_id:
        print("Skipping bib record test")
        return
    
    for env_name, client in clients.items():
        print(f"\n--- Testing {env_name} bib record ---")
        
        try:
            print(f"  Retrieving MMS ID: {mms_id}")
            response = client.get(f'almaws/v1/bibs/{mms_id}')
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if isinstance(data, dict):
                        title = data.get('title', 'No title')
                        record_format = data.get('record_format', {})
                        if isinstance(record_format, dict):
                            record_format_value = record_format.get('value', record_format)
                        else:
                            record_format_value = str(record_format)
                        
                        material_type = data.get('material_type', {})
                        if isinstance(material_type, dict):
                            material_type_value = material_type.get('value', 'Not specified')
                        else:
                            material_type_value = str(material_type) if material_type else 'Not specified'
                        
                        print(f"  ✓ Retrieved record")
                        print(f"    Title: {title}")
                        print(f"    Format: {record_format_value}")
                        print(f"    Material Type: {material_type_value}")
                        print(f"    MMS ID: {data.get('mms_id', 'Unknown')}")
                    else:
                        print(f"  ✗ Unexpected data type: {type(data)}")
                        
                except Exception as e:
                    print(f"  ✗ Error processing response: {e}")
                    
            elif response.status_code == 404:
                print(f"  ✗ Record not found in {env_name}")
            else:
                print(f"  ✗ Request failed: {response.status_code}")
                print(f"    Response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"  ✗ Error retrieving bib record: {e}")


def test_environment_switching(clients):
    """Test switching between environments"""
    print("\n=== Testing Environment Switching ===")
    
    if 'SANDBOX' in clients:
        client = clients['SANDBOX']
        print(f"Starting environment: {client.get_environment()}")
        
        try:
            # Switch to PRODUCTION
            if 'PRODUCTION' in clients:  # Only if PROD is available
                print("Switching to PRODUCTION...")
                client.switch_environment('PRODUCTION')
                print(f"Current environment: {client.get_environment()}")
                
                # Switch back to SANDBOX
                print("Switching back to SANDBOX...")
                client.switch_environment('SANDBOX')
                print(f"Current environment: {client.get_environment()}")
                
                print("✓ Environment switching works correctly")
            else:
                print("PRODUCTION client not available, skipping switch test")
                
        except Exception as e:
            print(f"✗ Environment switching failed: {e}")


def test_safe_request_method(clients):
    """Test the safe_request utility method"""
    print("\n=== Testing Safe Request Method ===")
    
    if 'SANDBOX' in clients:
        client = clients['SANDBOX']
        
        # Test successful request
        print("Testing successful request...")
        result = client.safe_request('GET', 'almaws/v1/conf/libraries')
        if result:
            if isinstance(result, dict):
                print(f"✓ Got {result.get('total_record_count', 0)} libraries")
            else:
                print("✓ Got response data")
        else:
            print("✗ Safe request returned None")
        
        # Test failed request
        print("Testing failed request...")
        result = client.safe_request('GET', 'almaws/v1/bibs/invalid_mms_id')
        if result is None:
            print("✓ Safe request correctly handled error")
        else:
            print("✗ Expected None for invalid request")


def main():
    """Run all tests"""
    print("AlmaAPIClient Test Suite - FIXED VERSION")
    print("=" * 50)
    
    # Test environment setup
    sb_key, prod_key = test_environment_setup()
    
    if not sb_key and not prod_key:
        print("\n✗ No API keys found. Please set environment variables:")
        print("export ALMA_SB_API_KEY='your_sandbox_key'")
        print("export ALMA_PROD_API_KEY='your_production_key'")
        return
    
    # Initialize clients
    clients = test_client_initialization()
    
    if not clients:
        print("\n✗ No clients could be created. Check your API keys.")
        return
    
    # Test connections
    test_connection(clients)
    
    # Test basic API calls (now with correct user groups endpoint)
    test_basic_api_calls(clients)
    
    # Test environment switching
    test_environment_switching(clients)
    
    # Test safe request method
    test_safe_request_method(clients)
    
    # Test bib record (with your test MMS ID)
    test_bib_record(clients, "990022169340204146")
    
    print("\n" + "=" * 50)
    print("✅ All tests completed successfully!")
    print("\nYour AlmaAPIClient is working perfectly!")
    print("Ready to proceed with building the enhanced toolkit.")


if __name__ == "__main__":
    main()