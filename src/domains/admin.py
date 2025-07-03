"""
Admin Domain Class for Alma API
Handles sets and administrative operations using the AlmaAPIClient foundation.
"""
from typing import List, Dict, Any
from src.client.AlmaAPIClient import AlmaAPIClient


class Admin:
    """
    Domain class for handling Alma Admin/Configuration API operations.
    Currently focused on sets management - will be expanded later.
    
    This class uses the AlmaAPIClient as its foundation for all HTTP operations.
    """
    
    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the Admin domain.
        
        Args:
            client: The AlmaAPIClient instance for making HTTP requests
        """
        self.client = client
        self.environment = client.get_environment()
    
    def get_set_members(self, set_id: str) -> List[str]:
        """
        Extract all MMS IDs from an Alma set using pagination.
        
        This method handles sets with any number of members by automatically
        paginating through all results (100 members per page).
        
        Args:
            set_id: The ID of the Alma set (e.g., "25793308630004146")
        
        Returns:
            List of MMS IDs from the set
            
        Raises:
            ValueError: If set_id is empty/None or set is not BIB_MMS type
            requests.RequestException: If the API request fails
        """
        if not set_id:
            raise ValueError("Set ID is required")
        
        print(f"Retrieving members from set: {set_id} ({self.environment})")
        
        try:
            # Step 1: Get set information and validate type
            set_info = self._get_set_info(set_id)
            
            # Step 2: Validate this is a bibliographic set
            content_type = set_info.get("content", {}).get("value", "")
            if content_type != "BIB_MMS":
                raise ValueError(f"Invalid set type: expected 'BIB_MMS', found '{content_type}'")
            
            # Step 3: Get total number of members
            total_members = set_info.get("number_of_members", {}).get("value", 0)
            print(f"Set contains {total_members} members")
            
            if total_members == 0:
                print("Set is empty")
                return []
            
            # Step 4: Retrieve all members using pagination
            all_mms_ids = []
            
            for offset in range(0, total_members, 100):
                print(f"Retrieving members {offset + 1}-{min(offset + 100, total_members)}...")
                
                # Get page of members
                members_response = self._get_set_members_page(set_id, offset)
                
                # Extract MMS IDs from this page
                members = members_response.get("member", [])
                if isinstance(members, dict):
                    # Single member returned as dict instead of list
                    members = [members]
                
                page_mms_ids = self._extract_mms_ids_from_members(members)
                all_mms_ids.extend(page_mms_ids)
                
                print(f"  Retrieved {len(page_mms_ids)} MMS IDs from this page")
            
            print(f"✓ Successfully retrieved {len(all_mms_ids)} MMS IDs from set {set_id}")
            return all_mms_ids
            
        except Exception as e:
            print(f"✗ Failed to retrieve set members: {str(e)}")
            raise
    
    def _get_set_info(self, set_id: str) -> Dict[str, Any]:
        """
        Get basic information about a set.
        
        Args:
            set_id: The set ID
            
        Returns:
            Dict containing set information
        """
        endpoint = f"almaws/v1/conf/sets/{set_id}"
        response = self.client.get(endpoint)
        
        # Raise for HTTP errors
        response.raise_for_status()
        
        return response.json()
    
    def _get_set_members_page(self, set_id: str, offset: int, limit: int = 100) -> Dict[str, Any]:
        """
        Get a page of set members.
        
        Args:
            set_id: The set ID
            offset: Starting position for this page
            limit: Number of members per page (default 100, max 100)
            
        Returns:
            Dict containing the page of members
        """
        endpoint = f"almaws/v1/conf/sets/{set_id}/members"
        params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        
        response = self.client.get(endpoint, params=params)
        
        # Raise for HTTP errors
        response.raise_for_status()
        
        return response.json()
    
    def _extract_mms_ids_from_members(self, members: List[Dict[str, Any]]) -> List[str]:
        """
        Extract MMS IDs from member objects.
        
        Each member object contains a 'link' field that includes the MMS ID.
        The link format is typically: 
        "https://api-eu.hosted.exlibrisgroup.com/almaws/v1/bibs/991234567890"
        
        Args:
            members: List of member dictionaries from the API
            
        Returns:
            List of MMS IDs extracted from the links
        """
        mms_ids = []
        
        for member in members:
            link = member.get("link", "")
            if link:
                # Extract MMS ID from the link
                # Link format: .../almaws/v1/bibs/{mms_id}
                try:
                    mms_id = link.split("/bibs/")[-1]
                    if mms_id:
                        mms_ids.append(mms_id)
                except Exception as e:
                    print(f"Warning: Could not extract MMS ID from link: {link} - {e}")
                    continue
        
        return mms_ids
    
    def get_set_info(self, set_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a set (public method).
        
        Args:
            set_id: The set ID
            
        Returns:
            Dict containing set information including name, description, type, etc.
        """
        if not set_id:
            raise ValueError("Set ID is required")
        
        try:
            set_info = self._get_set_info(set_id)
            
            # Extract key information
            summary = {
                "id": set_info.get("id", "Unknown"),
                "name": set_info.get("name", "Unknown"),
                "description": set_info.get("description", ""),
                "content_type": set_info.get("content", {}).get("value", "Unknown"),
                "status": set_info.get("status", {}).get("value", "Unknown"),
                "total_members": set_info.get("number_of_members", {}).get("value", 0),
                "created_date": set_info.get("created_date", "Unknown"),
                "created_by": set_info.get("created_by", "Unknown")
            }
            
            print(f"✓ Retrieved info for set: {summary['name']} (ID: {set_id})")
            return summary
            
        except Exception as e:
            print(f"✗ Failed to get set info: {str(e)}")
            raise
    
    def list_sets(self, limit: int = 25, offset: int = 0, 
                  content_type: str = None) -> Dict[str, Any]:
        """
        List sets with optional filtering.
        
        Args:
            limit: Maximum number of results to return (max 100)
            offset: Starting point for results
            content_type: Optional filter by content type (BIB_MMS, ITEM, etc.)
        
        Returns:
            Dict containing the list of sets
        """
        print(f"Listing sets (limit: {limit}, offset: {offset})")
        
        params = {
            "limit": str(min(limit, 100)),  # API max is 100
            "offset": str(offset)
        }
        
        if content_type:
            params["content_type"] = content_type
        
        try:
            endpoint = "almaws/v1/conf/sets"
            response = self.client.get(endpoint, params=params)
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Parse JSON response
            sets_data = response.json()
            
            total_count = sets_data.get('total_record_count', 0)
            print(f"✓ Successfully retrieved {total_count} sets")
            return sets_data
            
        except Exception as e:
            print(f"✗ Failed to list sets: {str(e)}")
            raise
    
    def get_environment(self) -> str:
        """Get the current environment from the client."""
        return self.client.get_environment()
    
    def test_connection(self) -> bool:
        """
        Test if the admin/configuration endpoints are accessible.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to list a small number of sets as a connection test
            response = self.client.get("almaws/v1/conf/sets", params={"limit": "1"})
            success = response.status_code == 200
            
            if success:
                print(f"✓ Admin API connection successful ({self.environment})")
            else:
                print(f"✗ Admin API connection failed: {response.status_code}")
            
            return success
            
        except Exception as e:
            print(f"✗ Admin API connection error: {e}")
            return False


# Usage examples and integration
if __name__ == "__main__":
    """
    Example usage of the Admin domain with AlmaAPIClient.
    """
    try:
        # Initialize the base client
        client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'
        
        # Test the base connection first
        if not client.test_connection():
            print("Cannot proceed - base API connection failed")
            exit(1)
        
        # Create the admin domain
        admin = Admin(client)
        
        # Test admin connection
        if not admin.test_connection():
            print("Cannot proceed - admin API connection failed")
            exit(1)
        
        print(f"\n=== Admin Domain Test ({admin.get_environment()}) ===")
        
        # Example: List sets
        try:
            print("\nTesting set listing...")
            sets = admin.list_sets(limit=5, content_type="BIB_MMS")
            total_sets = sets.get('total_record_count', 0)
            print(f"Found {total_sets} total BIB_MMS sets")
            
            # Show first set if available
            set_list = sets.get('set', [])
            if isinstance(set_list, list) and set_list:
                first_set = set_list[0]
                print(f"First set: {first_set.get('name', 'Unknown')} (ID: {first_set.get('id', 'Unknown')})")
            elif isinstance(set_list, dict):
                print(f"Single set: {set_list.get('name', 'Unknown')} (ID: {set_list.get('id', 'Unknown')})")
            
        except Exception as e:
            print(f"Set listing test failed: {e}")
        
        # Example: Test with specific set ID
        test_set_id = input("\nEnter a set ID to test get_set_members (or press Enter to skip): ").strip()
        
        if test_set_id:
            try:
                print(f"\nTesting set member retrieval for ID: {test_set_id}")
                
                # Get set info
                set_info = admin.get_set_info(test_set_id)
                print(f"Set name: {set_info['name']}")
                print(f"Set type: {set_info['content_type']}")
                print(f"Total members: {set_info['total_members']}")
                
                # Get set members (MMS IDs)
                if set_info['content_type'] == 'BIB_MMS':
                    mms_ids = admin.get_set_members(test_set_id)
                    print(f"Retrieved {len(mms_ids)} MMS IDs")
                    if mms_ids:
                        print(f"First few MMS IDs: {mms_ids[:5]}")
                else:
                    print(f"Skipping member retrieval - set is not BIB_MMS type")
                
            except Exception as e:
                print(f"Set member test failed: {e}")
        
        print("\n=== Admin Domain Test Complete ===")
        
    except Exception as e:
        print(f"Setup error: {e}")
        print("\nMake sure you have set the environment variable:")
        print("export ALMA_SB_API_KEY='your_sandbox_api_key'")