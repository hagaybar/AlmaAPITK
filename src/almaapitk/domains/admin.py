"""
Enhanced Admin Domain Class for Alma API
Handles sets and administrative operations with support for both BIB_MMS and USER sets.
Enhanced for the email update project to process user sets.
"""
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError, AlmaResponse, AlmaValidationError
from almaapitk.domains.users import Users


class Admin:
    """
    Enhanced Admin domain class for handling Alma Admin/Configuration API operations.
    
    Now supports:
    - BIB_MMS sets (original functionality)  
    - USER sets (new for email update project)
    - Flexible set processing with type validation
    - Enhanced error handling and logging
    """
    
    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the Admin domain.
        
        Args:
            client: The AlmaAPIClient instance for making HTTP requests
        """
        self.client = client
        self.logger = client.logger
        self.environment = client.get_environment()
    
    # Enhanced Set Member Retrieval Methods
    
    def get_set_members(self, set_id: str, expected_type: Optional[str] = None) -> List[str]:
        """
        Extract all member IDs from an Alma set using pagination.
        
        This method now supports both BIB_MMS and USER sets automatically,
        or can validate against a specific expected type.
        
        Args:
            set_id: The ID of the Alma set (e.g., "25793308630004146")
            expected_type: Optional validation - "BIB_MMS", "USER", or None for auto-detect
        
        Returns:
            List of member IDs from the set (MMS IDs for BIB sets, User IDs for USER sets)
            
        Raises:
            AlmaValidationError: If set_id is empty or set type doesn't match expected
            AlmaAPIError: If the API request fails
        """
        if not set_id:
            raise AlmaValidationError("Set ID is required")
        
        self.logger.info(f"Retrieving members from set: {set_id} ({self.environment})")
        
        try:
            # Step 1: Get set information and validate
            set_info = self._get_set_info(set_id)
            
            # Step 2: Validate set type
            content_type = set_info.get("content", {}).get("value", "")
            self._validate_set_type(content_type, expected_type, set_id)
            
            # Step 3: Get total number of members
            total_members = set_info.get("number_of_members", {}).get("value", 0)
            self.logger.info(f"Set contains {total_members} members (type: {content_type})")
            
            if total_members == 0:
                self.logger.info("Set is empty")
                return []
            
            # Step 4: Retrieve all members using pagination
            all_member_ids = []
            
            for offset in range(0, total_members, 100):
                self.logger.info(f"Retrieving members {offset + 1}-{min(offset + 100, total_members)}...")
                
                # Get page of members
                members_response = self._get_set_members_page(set_id, offset)
                
                # Extract member IDs from this page
                members = members_response.get("member", [])
                if isinstance(members, dict):
                    # Single member returned as dict instead of list
                    members = [members]
                
                page_member_ids = self._extract_member_ids_from_members(members, content_type)
                all_member_ids.extend(page_member_ids)
                
                self.logger.debug(f"  Retrieved {len(page_member_ids)} member IDs from this page")
            
            self.logger.info(f"✓ Successfully retrieved {len(all_member_ids)} member IDs from set {set_id}")
            return all_member_ids
            
        except AlmaAPIError:
            raise  # Re-raise API errors
        except Exception as e:
            self.logger.error(f"✗ Failed to retrieve set members: {str(e)}")
            raise AlmaAPIError(f"Set processing failed: {e}")
    
    def get_user_set_members(self, set_id: str) -> List[str]:
        """
        Extract all user IDs from a USER set (convenience method).
        
        Args:
            set_id: The ID of the Alma USER set
        
        Returns:
            List of user IDs from the set
            
        Raises:
            AlmaValidationError: If set is not a USER set
            AlmaAPIError: If the API request fails
        """
        return self.get_set_members(set_id, expected_type="USER")
    
    def get_bib_set_members(self, set_id: str) -> List[str]:
        """
        Extract all MMS IDs from a BIB_MMS set (convenience method).
        
        Args:
            set_id: The ID of the Alma BIB_MMS set
        
        Returns:
            List of MMS IDs from the set
            
        Raises:
            AlmaValidationError: If set is not a BIB_MMS set
            AlmaAPIError: If the API request fails
        """
        return self.get_set_members(set_id, expected_type="BIB_MMS")
    
    # Set Validation Methods
    
    def validate_user_set(self, set_id: str) -> Dict[str, Any]:
        """
        Validate that a set exists and is a USER type set.
        
        Args:
            set_id: The set ID to validate
        
        Returns:
            Dict containing set information if valid
            
        Raises:
            AlmaValidationError: If set doesn't exist or is not USER type
            AlmaAPIError: If API request fails
        """
        if not set_id:
            raise AlmaValidationError("Set ID is required")
        
        try:
            set_info = self._get_set_info(set_id)
            content_type = set_info.get("content", {}).get("value", "")
            
            if content_type != "USER":
                raise AlmaValidationError(
                    f"Set {set_id} is not a USER set. Found type: '{content_type}'. "
                    f"Expected type: 'USER'"
                )
            
            result = {
                "id": set_info.get("id", set_id),
                "name": set_info.get("name", "Unknown"),
                "content_type": content_type,
                "total_members": set_info.get("number_of_members", {}).get("value", 0),
                "status": set_info.get("status", {}).get("value", "Unknown"),
                "created_date": set_info.get("created_date", "Unknown")
            }
            
            self.logger.info(f"✓ Validated USER set: {result['name']} ({result['total_members']} members)")
            return result
            
        except AlmaAPIError:
            raise
        except AlmaValidationError:
            raise
        except Exception as e:
            raise AlmaAPIError(f"Set validation failed: {e}")
    
    def _validate_set_type(self, content_type: str, expected_type: Optional[str], set_id: str) -> None:
        """
        Validate set content type against expected type.
        
        Args:
            content_type: Actual content type from set info
            expected_type: Expected content type or None for any supported type
            set_id: Set ID for error messages
            
        Raises:
            AlmaValidationError: If type validation fails
        """
        supported_types = ["BIB_MMS", "USER"]
        
        # Check if content type is supported
        if content_type not in supported_types:
            raise AlmaValidationError(
                f"Unsupported set type: '{content_type}' for set {set_id}. "
                f"Supported types: {', '.join(supported_types)}"
            )
        
        # Check against expected type if specified
        if expected_type and content_type != expected_type:
            raise AlmaValidationError(
                f"Set type mismatch for set {set_id}: expected '{expected_type}', found '{content_type}'"
            )
        
        self.logger.debug(f"Set type validation passed: {content_type}")
    
    # Core Set Processing Methods (Enhanced)
    
    def _get_set_info(self, set_id: str) -> Dict[str, Any]:
        """
        Get basic information about a set.
        
        Args:
            set_id: The set ID
            
        Returns:
            Dict containing set information
            
        Raises:
            AlmaAPIError: If API request fails
        """
        endpoint = f"almaws/v1/conf/sets/{set_id}"
        
        try:
            response = self.client.get(endpoint)
            return response.json()
            
        except AlmaAPIError as e:
            self.logger.error(f"Failed to retrieve set info for {set_id}: {e}")
            raise
    
    def _get_set_members_page(self, set_id: str, offset: int, limit: int = 100) -> Dict[str, Any]:
        """
        Get a page of set members.
        
        Args:
            set_id: The set ID
            offset: Starting position for this page
            limit: Number of members per page (default 100, max 100)
            
        Returns:
            Dict containing the page of members
            
        Raises:
            AlmaAPIError: If API request fails
        """
        endpoint = f"almaws/v1/conf/sets/{set_id}/members"
        params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        
        try:
            response = self.client.get(endpoint, params=params)
            return response.json()
            
        except AlmaAPIError as e:
            self.logger.error(f"Failed to retrieve set members page for {set_id}: {e}")
            raise
    
    def _extract_member_ids_from_members(self, members: List[Dict[str, Any]], content_type: str) -> List[str]:
        """
        Extract member IDs from member objects based on set type.
        
        Args:
            members: List of member dictionaries from the API
            content_type: Type of set ("BIB_MMS" or "USER")
            
        Returns:
            List of member IDs extracted from the links
        """
        member_ids = []
        
        for member in members:
            link = member.get("link", "")
            if link:
                try:
                    if content_type == "BIB_MMS":
                        # Extract MMS ID from bibliographic link
                        # Link format: .../almaws/v1/bibs/{mms_id}
                        member_id = link.split("/bibs/")[-1]
                    elif content_type == "USER":
                        # Extract User ID from user link
                        # Link format: .../almaws/v1/users/{user_id}
                        member_id = link.split("/users/")[-1]
                    else:
                        self.logger.warning(f"Unknown content type for ID extraction: {content_type}")
                        continue
                    
                    if member_id:
                        member_ids.append(member_id)
                        self.logger.debug(f"Extracted {content_type} ID: {member_id}")
                    else:
                        self.logger.warning(f"Could not extract ID from link: {link}")
                        
                except Exception as e:
                    self.logger.error(f"Error extracting member ID from link: {link} - {e}")
                    continue
        
        return member_ids
    
    # Enhanced Set Information Methods
    
    def get_set_info(self, set_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a set (public method).
        
        Args:
            set_id: The set ID
            
        Returns:
            Dict containing set information including name, description, type, etc.
            
        Raises:
            AlmaValidationError: If set_id is empty
            AlmaAPIError: If API request fails
        """
        if not set_id:
            raise AlmaValidationError("Set ID is required")
        
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
            
            self.logger.info(f"✓ Retrieved info for set: {summary['name']} (ID: {set_id}, Type: {summary['content_type']})")
            return summary
            
        except AlmaAPIError:
            raise
        except Exception as e:
            raise AlmaAPIError(f"Failed to get set info: {e}")
    
    def get_set_metadata_and_member_count(self, set_id: str) -> Dict[str, Any]:
        """
        Get set metadata and member count for user sets (enhanced method).
        
        Args:
            set_id: The set ID
            
        Returns:
            Dict with metadata and member count information
            
        Raises:
            AlmaValidationError: If set_id is empty
            AlmaAPIError: If API request fails
        """
        if not set_id:
            raise AlmaValidationError("Set ID is required")
        
        try:
            set_info = self.get_set_info(set_id)
            
            # Enhanced metadata
            metadata = {
                "basic_info": {
                    "id": set_info["id"],
                    "name": set_info["name"],
                    "description": set_info["description"],
                    "content_type": set_info["content_type"],
                    "status": set_info["status"]
                },
                "member_info": {
                    "total_members": set_info["total_members"],
                    "estimated_processing_time_minutes": self._estimate_processing_time(set_info["total_members"]),
                    "pages_required": (set_info["total_members"] + 99) // 100  # Round up division
                },
                "creation_info": {
                    "created_date": set_info["created_date"],
                    "created_by": set_info["created_by"]
                },
                "processing_warnings": self._generate_processing_warnings(set_info)
            }
            
            self.logger.info(f"✓ Set metadata retrieved: {metadata['member_info']['total_members']} members, "
                           f"~{metadata['member_info']['estimated_processing_time_minutes']} min processing time")
            
            return metadata
            
        except AlmaAPIError:
            raise
        except Exception as e:
            raise AlmaAPIError(f"Failed to get set metadata: {e}")
    
    def _estimate_processing_time(self, member_count: int) -> int:
        """Estimate processing time in minutes based on member count."""
        # Rough estimate: 2-3 seconds per user (API calls + processing)
        # Plus rate limiting delays
        seconds_per_user = 3
        estimated_seconds = member_count * seconds_per_user
        
        # Add rate limiting overhead (pause every 50 users)
        rate_limit_pauses = (member_count // 50) * 2  # 2 seconds per pause
        
        total_seconds = estimated_seconds + rate_limit_pauses
        return max(1, total_seconds // 60)  # Convert to minutes, minimum 1
    
    def _generate_processing_warnings(self, set_info: Dict[str, Any]) -> List[str]:
        """Generate warnings for large sets or potential issues."""
        warnings = []
        member_count = set_info["total_members"]
        content_type = set_info["content_type"]
        
        if member_count > 1000:
            warnings.append(f"Large set detected ({member_count} members). Processing may take significant time.")
        
        if member_count > 5000:
            warnings.append("Very large set. Consider running during off-peak hours.")
        
        if content_type == "USER" and member_count > 100:
            warnings.append("Large user set. Email updates will require careful rate limiting.")
        
        if set_info["status"] != "ACTIVE":
            warnings.append(f"Set status is '{set_info['status']}', not 'ACTIVE'. Verify set is ready for processing.")
        
        return warnings
    
    # List Sets Methods (Enhanced)
    
    def list_sets(self, limit: int = 25, offset: int = 0, 
                  content_type: str = None, include_member_counts: bool = False) -> AlmaResponse:
        """
        List sets with optional filtering.
        
        Note: The Alma API list endpoint does NOT include member counts in the response.
        Member counts are only available via individual set API calls.
        Set include_member_counts=True to fetch member counts (slower but complete).
        
        Args:
            limit: Maximum number of results to return (max 100)
            offset: Starting point for results
            content_type: Optional filter by content type (BIB_MMS, USER, etc.)
            include_member_counts: If True, fetch member counts via individual API calls (slower)
        
        Returns:
            AlmaResponse containing the list of sets
            
        Raises:
            AlmaAPIError: If API request fails
        """
        self.logger.info(f"Listing sets (limit: {limit}, offset: {offset}, type: {content_type or 'all'})")
        
        if include_member_counts:
            self.logger.info("include_member_counts=True will make individual API calls for each set - this will be slower")
        
        params = {
            "limit": str(min(limit, 100)),  # API max is 100
            "offset": str(offset)
        }
        
        if content_type:
            params["content_type"] = content_type
        
        try:
            endpoint = "almaws/v1/conf/sets"
            response = self.client.get(endpoint, params=params)
            
            # Add member counts if requested
            if include_member_counts:
                response = self._add_member_counts_to_sets(response)
            
            # Log summary 
            sets_data = response.json()
            total_count = sets_data.get('total_record_count', 0)
            
            if include_member_counts:
                self.logger.info(f"✓ Successfully retrieved {total_count} sets with member counts")
            else:
                self.logger.info(f"✓ Successfully retrieved {total_count} sets")
                self.logger.info("ℹ️  Member counts not included in list view. Use include_member_counts=True or get_set_info() for member counts.")
            
            return response
            
        except AlmaAPIError as e:
            self.logger.error(f"✗ Failed to list sets: {e}")
            raise
    
    def _add_member_counts_to_sets(self, list_response: AlmaResponse) -> AlmaResponse:
        """
        Add member counts to a list response by calling individual set APIs.
        
        Args:
            list_response: Response from list_sets API
            
        Returns:
            Enhanced response with member counts added
        """
        
        sets_data = list_response.json()
        sets_list = sets_data.get('set', [])
        
        if isinstance(sets_list, dict):
            sets_list = [sets_list]
        
        self.logger.info(f"Fetching member counts for {len(sets_list)} sets...")
        
        for i, set_info in enumerate(sets_list, 1):
            set_id = set_info.get('id')
            if set_id:
                try:
                    # Get member count for this set
                    individual_info = self.get_set_info(set_id)
                    
                    # Add the number_of_members field that's missing from list view
                    set_info['number_of_members'] = {
                        'value': individual_info['total_members']
                    }
                    
                    self.logger.debug(f"Set {i}/{len(sets_list)}: {set_id} has {individual_info['total_members']} members")
                    
                    # Rate limiting for bulk operations
                    if i % 5 == 0:
                        time.sleep(1)
                        
                except Exception as e:
                    self.logger.warning(f"Could not get member count for set {set_id}: {e}")
                    # Add a placeholder to indicate the fetch failed
                    set_info['number_of_members'] = {
                        'value': 'ERROR',
                        'error': str(e)
                    }
        
        # Update the response data
        sets_data['set'] = sets_list
        
        # Create a new response with updated content
        # Note: This is a simplified approach - in production you might want a more robust way
        try:
            updated_content = json.dumps(sets_data)
            # Update the internal response content
            list_response._response._content = updated_content.encode('utf-8')
        except Exception as e:
            self.logger.warning(f"Could not update response content: {e}")
        
        return list_response
    
    # Utility Methods
    
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
                self.logger.info(f"✓ Admin API connection successful ({self.environment})")
            else:
                self.logger.error(f"✗ Admin API connection failed: {response.status_code}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"✗ Admin API connection error: {e}")
            return False


# Usage examples and integration for the email update project
if __name__ == "__main__":
    """
    Example usage of the enhanced Admin class for email update workflow

    """


    def example_user_set_workflow():
            
            # Initialize client and admin domain
            client = AlmaAPIClient('SANDBOX')
            admin = Admin(client)
            
            # Test connection
            if not admin.test_connection():
                print("Cannot proceed - admin API connection failed")
                return
            
            print("=== Enhanced Admin Domain Test ===")
            
            # Example: Validate user set
            user_set_id = input("Enter a USER set ID to test (or press Enter to skip): ").strip()
            
            if user_set_id:
                try:
                    print(f"\n=== Validating USER Set: {user_set_id} ===")
                    
                    # Validate set is USER type
                    set_info = admin.validate_user_set(user_set_id)
                    print(f"✓ Valid USER set: {set_info['name']}")
                    print(f"  Members: {set_info['total_members']}")
                    print(f"  Status: {set_info['status']}")
                    
                    # Get detailed metadata
                    metadata = admin.get_set_metadata_and_member_count(user_set_id)
                    print(f"\n=== Set Metadata ===")
                    print(f"Estimated processing time: {metadata['member_info']['estimated_processing_time_minutes']} minutes")
                    print(f"Pages required: {metadata['member_info']['pages_required']}")
                    
                    if metadata['processing_warnings']:
                        print(f"\n⚠️  Warnings:")
                        for warning in metadata['processing_warnings']:
                            print(f"  - {warning}")
                    
                    # Get user IDs from set
                    proceed = input(f"\nRetrieve all {set_info['total_members']} user IDs from this set? (y/n): ").strip().lower()
                    
                    if proceed == 'y':
                        print(f"\n=== Retrieving User IDs ===")
                        user_ids = admin.get_user_set_members(user_set_id)
                        
                        print(f"✓ Retrieved {len(user_ids)} user IDs")
                        print(f"First 5 user IDs: {user_ids[:5]}")
                        
                        if len(user_ids) > 5:
                            print(f"Last 5 user IDs: {user_ids[-5:]}")
                        
                        # Save all user IDs and names to file
                        try:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"user_set_{user_set_id}_{timestamp}.txt"
                            
                            print(f"\n=== Saving User Details to File ===")
                            print(f"Fetching user names and saving to: {filename}")
                            
                            # Initialize Users domain to get user names
                            users = Users(client)
                            
                            with open(filename, 'w', encoding='utf-8') as f:
                                # Write header
                                f.write(f"User Set Export\n")
                                f.write(f"Set ID: {user_set_id}\n")
                                f.write(f"Set Name: {set_info['name']}\n")
                                f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                f.write(f"Total Users: {len(user_ids)}\n")
                                f.write("-" * 80 + "\n\n")
                                f.write("User_ID\tFirst_Name\tLast_Name\tFull_Name\tStatus\n")
                                f.write("-" * 80 + "\n")
                                
                                # Process each user ID
                                successful_exports = 0
                                failed_exports = 0
                                
                                for i, user_id in enumerate(user_ids, 1):
                                    # Progress indicator
                                    if i % 50 == 0 or i == len(user_ids):
                                        print(f"  Processing user {i}/{len(user_ids)}: {user_id}")
                                    
                                    try:
                                        # Get user details
                                        user_response = users.get_user(user_id)
                                        user_data = user_response.json()
                                        
                                        # Extract user information
                                        first_name = user_data.get('first_name', '').strip()
                                        last_name = user_data.get('last_name', '').strip()
                                        full_name = f"{first_name} {last_name}".strip()
                                        status = user_data.get('status', {}).get('value', 'Unknown')
                                        
                                        # Write to file
                                        f.write(f"{user_id}\t{first_name}\t{last_name}\t{full_name}\t{status}\n")
                                        successful_exports += 1
                                        
                                    except Exception as e:
                                        # Write error entry
                                        f.write(f"{user_id}\tERROR\tERROR\tERROR: {str(e)}\tERROR\n")
                                        failed_exports += 1
                                        admin.logger.warning(f"Could not get details for user {user_id}: {e}")
                                    
                                    # Rate limiting
                                    if i % 25 == 0:
                                                        time.sleep(1)
                                
                                # Write summary at end of file
                                f.write("-" * 80 + "\n")
                                f.write(f"\nExport Summary:\n")
                                f.write(f"Total Users: {len(user_ids)}\n")
                                f.write(f"Successful: {successful_exports}\n")
                                f.write(f"Failed: {failed_exports}\n")
                                f.write(f"Success Rate: {(successful_exports/len(user_ids)*100):.1f}%\n")
                            
                            print(f"✓ User details saved to: {filename}")
                            print(f"  Total users: {len(user_ids)}")
                            print(f"  Successful: {successful_exports}")
                            print(f"  Failed: {failed_exports}")
                            
                            if failed_exports > 0:
                                print(f"  ⚠️  {failed_exports} users could not be retrieved (see file for details)")
                            
                        except Exception as e:
                            print(f"✗ Error saving user details to file: {e}")
                        
                        # This list would now be passed to the Users domain for processing
                        print(f"\n✓ Ready to pass {len(user_ids)} user IDs to Users domain for email processing")
                    
                except (AlmaValidationError, AlmaAPIError) as e:
                    print(f"✗ Error: {e}")
            
            # Example: List USER sets
            print(f"\n=== Available USER Sets ===")
            try:
                user_sets_response = admin.list_sets(limit=10, content_type="USER")
                user_sets_data = user_sets_response.json()
                
                sets_list = user_sets_data.get('set', [])
                if isinstance(sets_list, dict):
                    sets_list = [sets_list]
                
                if sets_list:
                    print(f"Found {len(sets_list)} USER sets:")
                    for i, set_info in enumerate(sets_list, 1):
                        name = set_info.get('name', 'Unknown')
                        set_id = set_info.get('id', 'Unknown')
                        
                        # Check if member count is available (it won't be in list view)
                        members_info = set_info.get('number_of_members')
                        if members_info:
                            members = members_info.get('value', 'Unknown')
                        else:
                            members = 'Not available in list view'
                        
                        print(f"  {i}. {name} (ID: {set_id}, Members: {members})")
                    
                    print(f"\nℹ️  Note: Member counts are not included in list view.")
                    print(f"   Use validate_user_set() or get_set_info() for accurate member counts.")
                else:
                    print("No USER sets found")
                    
            except Exception as e:
                print(f"✗ Error listing USER sets: {e}")

    
    # Uncomment to run example
    example_user_set_workflow()