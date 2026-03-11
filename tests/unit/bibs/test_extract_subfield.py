# TEST CODE
"""
Test script for updated bibs.py and AlmaAPIClient compatibility
Save as test_bibs_marc.py
"""

from almaapitk import AlmaAPIClient
from almaapitk import BibliographicRecords

def test_bibs_compatibility():
    """Test AlmaAPIClient compatibility with bibs.py"""
    try:
        # Initialize clients
        client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'
        bibs = BibliographicRecords(client)
        
        print("=== Testing AlmaAPIClient + bibs.py Compatibility ===")
        
        # Test 1: Basic connection
        if not client.test_connection():
            print("✗ Client connection failed")
            return
        
        print("✓ Client connection successful")
        
        # Test 2: Logger compatibility
        bibs.logger.info("Logger test - this should work")
        print("✓ Logger compatibility working")
        
        # Test 3: Get a test record (you'll need a valid MMS ID)
        test_mms_id = input("Enter a test MMS ID (or press Enter to skip): ").strip()
        
        if test_mms_id:
            try:
                print(f"\nTesting record retrieval for MMS ID: {test_mms_id}")
                
                # Test get_record method
                response = bibs.get_record(test_mms_id)
                print(f"✓ get_record works: {response.success}")
                
                if response.success:
                    # Test MARC subfield extraction
                    print("\nTesting MARC subfield extraction...")
                    
                    # Test 907$e extraction
                    values_907e = bibs.get_marc_subfield(test_mms_id, "907", "e")
                    print(f"✓ MARC 907$e extraction: found {len(values_907e)} values")
                    if values_907e:
                        print(f"  Values: {values_907e}")
                    
                    # Test another common field (245$a - title)
                    values_245a = bibs.get_marc_subfield(test_mms_id, "245", "a")
                    print(f"✓ MARC 245$a extraction: found {len(values_245a)} values")
                    if values_245a:
                        print(f"  Title: {values_245a[0]}")
                
            except Exception as e:
                print(f"✗ Record test failed: {e}")
        
        print("\n=== Test Complete ===")
        print("If you see checkmarks above, the compatibility is working!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bibs_compatibility()