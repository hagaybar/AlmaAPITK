"""
Enhanced Admin Domain Class for Alma API
Handles sets and administrative operations with support for both BIB_MMS and USER sets.
Enhanced for the email update project to process user sets.
"""
import json
import time
from typing import Any, Dict, List, Optional

from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError, AlmaResponse, AlmaValidationError


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
            total_members = self._member_count(set_info)
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
                "total_members": self._member_count(set_info),
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
    
    @staticmethod
    def _member_count(set_info: Dict[str, Any]) -> int:
        """Coerce Alma's ``number_of_members.value`` to ``int``.

        The Alma schema (``rest_set.json``) types this nested value as a
        **string** (e.g. ``"100"``), but callers feed it to ``range()`` and
        integer arithmetic. Coerce once here so every call site gets an int;
        a missing/blank value yields ``0``.
        """
        return int(set_info.get("number_of_members", {}).get("value", 0) or 0)

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
                "total_members": self._member_count(set_info),
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

    # =========================================================================
    # Set CRUD + member-management methods (issue #23)
    #
    # Pattern source: read pattern mirrors ``Admin.list_sets`` (line 439);
    # write pattern mirrors ``Acquisitions.create_invoice_simple`` -- input
    # validation up top, ``self.client.<verb>`` for HTTP, structured
    # logging at entry / success / error, AlmaAPIError surfaced verbatim
    # with full context. The member-management endpoint matches the Alma
    # developer-network spec: ``POST /almaws/v1/conf/sets/{set_id}`` with
    # an ``op`` query parameter (``add_members`` / ``delete_members``)
    # and a body shaped as ``{"members": {"member": [{"id": ...}, ...]}}``.
    # =========================================================================

    def create_set(self, set_data: Dict[str, Any]) -> AlmaResponse:
        """Create a new itemized or logical set.

        Wraps ``POST /almaws/v1/conf/sets``. ``set_data`` must include at
        minimum the ``name`` and ``type`` fields Alma requires; the rest
        of the payload (description, content type, status, query, etc.)
        is passed through verbatim so callers can build any set Alma
        accepts without having to wait for explicit kwargs.

        Args:
            set_data: Set object payload. Required keys:

                - ``name`` (str): The set name shown in Alma.
                - ``type`` (dict): The set type, e.g.
                  ``{"value": "ITEMIZED"}`` or ``{"value": "LOGICAL"}``.

                Almost every real call also wants ``content`` (the
                content type, e.g. ``{"value": "BIB_MMS"}`` or
                ``{"value": "USER"}``) — but Alma's own validation owns
                that, so it is documented but not enforced here.

        Returns:
            AlmaResponse wrapping the create response. The created set's
            ``id`` lives at ``response.data["id"]``.

        Raises:
            AlmaValidationError: If ``set_data`` is empty / not a dict,
                or if ``name`` / ``type`` are missing.
            AlmaAPIError: On API failure (typed subclass when the Alma
                error code or HTTP status maps to one — see
                ``AlmaAPIClient._classify_error``).

        Example:
            >>> response = admin.create_set({
            ...     "name": "My BIB set",
            ...     "type": {"value": "ITEMIZED"},
            ...     "content": {"value": "BIB_MMS"},
            ... })
            >>> set_id = response.data["id"]
        """
        self._validate_set_data_for_create(set_data)
        set_name = set_data.get("name")

        # ``type`` and ``content`` may be either a bare string or the
        # canonical ``{"value": "..."}`` dict shape -- normalise here
        # for the log record only; the body sent to Alma is forwarded
        # verbatim.
        raw_type = set_data.get("type")
        type_value = (
            raw_type.get("value") if isinstance(raw_type, dict) else raw_type
        )
        raw_content = set_data.get("content")
        content_value = (
            raw_content.get("value")
            if isinstance(raw_content, dict)
            else raw_content
        )

        self.logger.info(
            f"Creating set: {set_name}",
            set_name=set_name,
            set_type=type_value,
            content_type=content_value,
        )

        try:
            response = self.client.post("almaws/v1/conf/sets", data=set_data)
            created_id = None
            try:
                created_id = response.data.get("id")
            except (ValueError, AttributeError):
                # Body may not be JSON / dict; the response itself is
                # still a valid AlmaResponse and we should hand it back.
                created_id = None

            if created_id:
                self.logger.info(
                    f"✓ Created set: {set_name} (id={created_id})",
                    set_id=created_id,
                    set_name=set_name,
                )
            else:
                self.logger.info(
                    f"✓ Created set: {set_name}",
                    set_name=set_name,
                )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to create set: {set_name}",
                set_name=set_name,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    def update_set(self, set_id: str, set_data: Dict[str, Any]) -> AlmaResponse:
        """Update an existing set's metadata.

        Wraps ``PUT /almaws/v1/conf/sets/{set_id}``. Alma expects a
        complete set object (see ``get_set_info`` for the shape Alma
        returns); callers typically read the current set, mutate the
        fields they want to change, and pass the whole dict here.

        Args:
            set_id: The Alma set identifier to update.
            set_data: Full set object payload. Must be a non-empty dict.

        Returns:
            AlmaResponse wrapping the updated set object.

        Raises:
            AlmaValidationError: If ``set_id`` is empty or ``set_data``
                is empty / not a dict.
            AlmaAPIError: On API failure.

        Example:
            >>> info = admin.get_set_info(set_id)
            >>> info["description"] = "Updated description"
            >>> response = admin.update_set(set_id, info)
        """
        if not set_id:
            raise AlmaValidationError("Set ID is required")
        if not isinstance(set_data, dict) or not set_data:
            raise AlmaValidationError(
                "set_data must be a non-empty dict"
            )

        self.logger.info(
            f"Updating set: {set_id}",
            set_id=set_id,
            set_name=set_data.get("name"),
        )

        try:
            response = self.client.put(
                f"almaws/v1/conf/sets/{set_id}", data=set_data
            )
            self.logger.info(
                f"✓ Updated set: {set_id}",
                set_id=set_id,
            )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to update set: {set_id}",
                set_id=set_id,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    def delete_set(self, set_id: str) -> AlmaResponse:
        """Delete a set.

        Wraps ``DELETE /almaws/v1/conf/sets/{set_id}``. Removes the set
        record from Alma; the underlying member records (bibs, users,
        etc.) are untouched.

        Args:
            set_id: The Alma set identifier to delete.

        Returns:
            AlmaResponse wrapping the delete response. Alma typically
            returns an empty body on a successful delete.

        Raises:
            AlmaValidationError: If ``set_id`` is empty.
            AlmaAPIError: On API failure.
        """
        if not set_id:
            raise AlmaValidationError("Set ID is required")

        self.logger.info(
            f"Deleting set: {set_id}",
            set_id=set_id,
        )

        try:
            response = self.client.delete(f"almaws/v1/conf/sets/{set_id}")
            self.logger.info(
                f"✓ Deleted set: {set_id}",
                set_id=set_id,
            )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to delete set: {set_id}",
                set_id=set_id,
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise

    def add_members_to_set(
        self, set_id: str, member_ids: List[str]
    ) -> AlmaResponse:
        """Add members to an existing set.

        Wraps ``POST /almaws/v1/conf/sets/{set_id}?op=add_members``. The
        body shape Alma expects is ``{"members": {"member": [{"id":
        "<member_id>"}, ...]}}``.

        Member-content validation: a ``BIB_MMS`` set takes MMS IDs and
        a ``USER`` set takes user primary IDs. Caller-side ID-shape
        validation is intentionally NOT performed here — Alma owns that
        rule and will reject mismatched IDs server-side with a typed
        error code (``60116`` / ``60120``).

        Args:
            set_id: The Alma set identifier to extend.
            member_ids: Non-empty list of member IDs to add. Each entry
                must be a non-empty string.

        Returns:
            AlmaResponse wrapping the updated set object.

        Raises:
            AlmaValidationError: If ``set_id`` is empty, ``member_ids``
                is empty / not a list, or any entry is empty / not a
                string.
            AlmaAPIError: On API failure.
        """
        return self._manage_set_members(set_id, member_ids, op="add_members")

    def remove_members_from_set(
        self, set_id: str, member_ids: List[str]
    ) -> AlmaResponse:
        """Remove members from an existing set.

        Wraps ``POST /almaws/v1/conf/sets/{set_id}?op=delete_members``.
        Body shape matches ``add_members_to_set``: ``{"members":
        {"member": [{"id": "<member_id>"}, ...]}}``.

        Args:
            set_id: The Alma set identifier to shrink.
            member_ids: Non-empty list of member IDs to remove. Each
                entry must be a non-empty string.

        Returns:
            AlmaResponse wrapping the updated set object.

        Raises:
            AlmaValidationError: If ``set_id`` is empty, ``member_ids``
                is empty / not a list, or any entry is empty / not a
                string.
            AlmaAPIError: On API failure.
        """
        return self._manage_set_members(
            set_id, member_ids, op="delete_members"
        )

    # ----- internal helpers for the set CRUD methods (issue #23) -------------

    @staticmethod
    def _validate_set_data_for_create(set_data: Any) -> None:
        """Validate the ``set_data`` argument to ``create_set``.

        Args:
            set_data: Candidate payload for ``create_set``.

        Raises:
            AlmaValidationError: If ``set_data`` is not a non-empty
                dict, or if the required ``name``/``type`` keys are
                missing.
        """
        if not isinstance(set_data, dict) or not set_data:
            raise AlmaValidationError(
                "set_data must be a non-empty dict"
            )
        name = set_data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise AlmaValidationError(
                "set_data['name'] is required and must be a non-empty string"
            )
        # ``type`` may be either the bare string code or the canonical
        # ``{"value": "ITEMIZED"}`` shape Alma returns on reads. Accept
        # both -- callers using the shape returned by ``get_set_info``
        # should not have to reshape it before sending it back.
        set_type = set_data.get("type")
        if isinstance(set_type, dict):
            type_value = set_type.get("value")
            if not isinstance(type_value, str) or not type_value.strip():
                raise AlmaValidationError(
                    "set_data['type']['value'] is required and must be a "
                    "non-empty string (e.g. 'ITEMIZED' or 'LOGICAL')"
                )
        elif isinstance(set_type, str):
            if not set_type.strip():
                raise AlmaValidationError(
                    "set_data['type'] must be a non-empty string"
                )
        else:
            raise AlmaValidationError(
                "set_data['type'] is required (string or "
                "{'value': '<TYPE>'} dict)"
            )

    def _manage_set_members(
        self, set_id: str, member_ids: List[str], op: str
    ) -> AlmaResponse:
        """Shared add/remove-members implementation.

        Centralises validation, body construction, logging, and error
        handling for ``add_members_to_set`` / ``remove_members_from_set``
        so the two public wrappers differ only by the ``op`` value sent
        on the query string.

        Args:
            set_id: Target set identifier.
            member_ids: Members to add/remove (non-empty list of
                non-empty strings).
            op: Either ``"add_members"`` or ``"delete_members"`` — the
                value Alma's ``op`` query parameter expects.

        Returns:
            AlmaResponse wrapping the API response.

        Raises:
            AlmaValidationError: For any input violation.
            AlmaAPIError: On API failure.
        """
        if not set_id:
            raise AlmaValidationError("Set ID is required")
        if not isinstance(member_ids, list) or not member_ids:
            raise AlmaValidationError(
                "member_ids must be a non-empty list of strings"
            )
        for index, mid in enumerate(member_ids):
            if not isinstance(mid, str) or not mid.strip():
                raise AlmaValidationError(
                    f"member_ids[{index}] must be a non-empty string"
                )

        # Body shape per Alma developer-network sets API:
        # {"members": {"member": [{"id": "<id>"}, ...]}}
        body = {
            "members": {
                "member": [{"id": mid} for mid in member_ids]
            }
        }

        action = "Adding" if op == "add_members" else "Removing"
        self.logger.info(
            f"{action} {len(member_ids)} member(s) {('to' if op == 'add_members' else 'from')} set {set_id}",
            set_id=set_id,
            op=op,
            member_count=len(member_ids),
        )

        try:
            response = self.client.post(
                f"almaws/v1/conf/sets/{set_id}",
                data=body,
                params={"op": op},
            )
            self.logger.info(
                f"✓ {action} {len(member_ids)} member(s): set {set_id}",
                set_id=set_id,
                op=op,
                member_count=len(member_ids),
            )
            return response

        except AlmaAPIError as e:
            self.logger.error(
                f"✗ Failed to {op.replace('_', ' ')} on set {set_id}",
                set_id=set_id,
                op=op,
                member_count=len(member_ids),
                error_code=e.status_code,
                alma_code=getattr(e, "alma_code", ""),
                tracking_id=getattr(e, "tracking_id", None),
                error_message=str(e),
            )
            raise
