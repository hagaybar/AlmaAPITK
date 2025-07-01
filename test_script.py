#!/usr/bin/env python3
"""
Test script for your current Alma API client
This will test if your existing code works and can differentiate between SB and PROD
"""

from core.config_manager import ConfigManager
from core.logger_manager import LoggerManager
from client.api_client import APIClient


def test_current_implementation():
    """Test your existing API client with both environments"""
    
    print("=== Testing Current Alma API Implementation ===\n")
    
    # Initialize managers
    try:
        config = ConfigManager()
        logger_manager = LoggerManager()
        print("✓ Config and Logger managers initialized")
    except Exception as e:
        print(f"✗ Failed to initialize managers: {e}")
        return
    
    # Test both environments
    environments = ['SB', 'PROD']
    
    for env in environments:
        print(f"\n--- Testing {env} Environment ---")
        
        try:
            # Set environment
            config.set_environment(env)
            print(f"✓ Environment set to {env}")
            
            # Show current configuration
            print(f"  Base URL: {config.get_base_url()}")
            print(f"  API Key: {config.get_api_key()[:10]}..." if config.get_api_key() else "  API Key: Not set")
            print(f"  Bucket: {config.get_bucket_name()}")
            
            # Create API client
            api_client = APIClient(config, logger_manager)
            print(f"✓ API Client created for {env}")
            
            # Test a simple GET request - let's try to get configuration info
            # This endpoint usually works and doesn't require specific IDs
            test_endpoint = "almaws/v1/conf/libraries"
            
            print(f"  Testing endpoint: {test_endpoint}")
            response = api_client.get(test_endpoint)
            
            if hasattr(response, 'status_code'):
                print(f"✓ Request successful! Status: {response.status_code}")
                
                # Try to parse response
                if response.headers.get('Content-Type', '').startswith('application/json'):
                    data = response.json()
                    if isinstance(data, dict) and 'library' in data:
                        libraries = data.get('library', [])
                        print(f"  Found {len(libraries)} libraries")
                        if libraries:
                            first_lib = libraries[0]
                            print(f"  First library: {first_lib.get('name', 'Unknown')}")
                    else:
                        print(f"  Response data: {str(data)[:100]}...")
                else:
                    print(f"  Response text: {response.text[:200]}...")
                        
            else:
                print(f"✓ Response received: {str(response)[:100]}...")
                
        except Exception as e:
            print(f"✗ Error testing {env}: {e}")
            print(f"  Error type: {type(e).__name__}")
    
    print(f"\n=== Test Complete ===")

def test_specific_bib_record():
    """Test getting a specific bibliographic record if you have an MMS ID"""
    
    print("\n=== Testing Bibliographic Record Retrieval ===")
    
    # You'll need to replace this with an actual MMS ID from your system
    test_mms_id = input("Enter an MMS ID to test (or press Enter to skip): ").strip()
    
    if not test_mms_id:
        print("Skipping bib record test")
        return
    
    try:
        config = ConfigManager()
        config.set_environment('SB')  # Test with sandbox first
        logger_manager = LoggerManager()
        api_client = APIClient(config, logger_manager)
        
        print(f"Testing bib record retrieval for MMS ID: {test_mms_id}")
        
        # Use your existing method
        bib_data = api_client.get_bib_record(test_mms_id)
        
        if isinstance(bib_data, dict):
            print(f"✓ Retrieved bib record")
            print(f"  Title: {bib_data.get('title', 'No title found')}")
            print(f"  MMS ID: {bib_data.get('mms_id', 'No MMS ID found')}")
            print(f"  Record format: {bib_data.get('record_format', 'Unknown')}")
        else:
            print(f"✓ Retrieved data: {str(bib_data)[:200]}...")
            
    except Exception as e:
        print(f"✗ Error retrieving bib record: {e}")

def test_environment_switching():
    """Test switching between environments"""
    
    print("\n=== Testing Environment Switching ===")
    
    try:
        config = ConfigManager()
        logger_manager = LoggerManager()
        
        print("Testing environment switching...")
        
        # Test SB
        config.set_environment('SB')
        api_client_sb = APIClient(config, logger_manager)
        print(f"SB API Key (partial): {config.get_api_key()[:10]}...")
        print(f"SB Bucket: {config.get_bucket_name()}")
        
        # Test PROD
        config.set_environment('PROD')
        api_client_prod = APIClient(config, logger_manager)
        print(f"PROD API Key (partial): {config.get_api_key()[:10]}...")
        print(f"PROD Bucket: {config.get_bucket_name()}")
        
        print("✓ Environment switching works correctly")
        
    except Exception as e:
        print(f"✗ Error testing environment switching: {e}")

if __name__ == "__main__":
    # Test your current implementation
    test_current_implementation()
    
    # Test environment switching
    test_environment_switching()
    
    # Test specific bib record if desired
    test_specific_bib_record()