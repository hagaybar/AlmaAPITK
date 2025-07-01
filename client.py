from typing import Optional
from core.config_manager import ConfigManager
from core.logger_manager import LoggerManager
from core.base_client import BaseAPIClient, AlmaResponse
from domains.bibs import BibliographicRecords
from domains.users import Users


class AlmaClient:
    """
    Main Alma API client that provides access to all Alma API domains.
    This is the primary interface for interacting with Alma APIs.
    """
    
    def __init__(self, environment: str = 'PROD', 
                 config_manager: Optional[ConfigManager] = None,
                 logger_manager: Optional[LoggerManager] = None):
        """
        Initialize the Alma API client.
        
        Args:
            environment: Environment to use ('PROD' or 'SB')
            config_manager: Optional custom config manager
            logger_manager: Optional custom logger manager
        """
        # Initialize managers
        self.config_manager = config_manager or ConfigManager()
        self.logger_manager = logger_manager or LoggerManager()
        
        # Set environment
        self.config_manager.set_environment(environment)
        
        # Initialize base client
        self.base_client = BaseAPIClient(self.config_manager, self.logger_manager)
        
        # Initialize domain clients
        self.bibs = BibliographicRecords(self.base_client)
        self.users = Users(self.base_client)
        # TODO: Add other domains (items, holdings, acquisitions, etc.)
        
        self.logger = self.logger_manager.get_logger()
        
        # Log initialization
        self.logger.info(f"AlmaClient initialized for {environment} environment")
        
        # Test connection on initialization
        if not self.test_connection():
            self.logger.warning("Initial connection test failed")
    
    def test_connection(self) -> bool:
        """
        Test the API connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            return self.base_client.test_connection()
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def switch_environment(self, environment: str) -> bool:
        """
        Switch between production and sandbox environments.
        
        Args:
            environment: Environment to switch to ('PROD' or 'SB')
        
        Returns:
            True if switch was successful, False otherwise
        """
        try:
            self.config_manager.set_environment(environment)
            self.base_client.headers = self.config_manager.get_headers()
            self.base_client.base_url = self.config_manager.get_base_url()
            
            # Test new environment
            if self.test_connection():
                self.logger.info(f"Successfully switched to {environment} environment")
                return True
            else:
                self.logger.error(f"Failed to connect to {environment} environment")
                return False
                
        except Exception as e:
            self.logger.error(f"Error switching to {environment} environment: {e}")
            return False
    
    def get_current_environment(self) -> str:
        """
        Get the current environment.
        
        Returns:
            Current environment string ('PROD' or 'SB')
        """
        return self.config_manager.current_environment
    
    def get_rate_limit_status(self) -> dict:
        """
        Get current rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        return {
            "requests_in_last_minute": len(self.base_client._request_times),
            "rate_limit": self.base_client._rate_limit,
            "requests_remaining": max(0, self.base_client._rate_limit - len(self.base_client._request_times))
        }
    
    def set_rate_limit(self, requests_per_minute: int) -> None:
        """
        Set custom rate limit.
        
        Args:
            requests_per_minute: Maximum requests per minute
        """
        if requests_per_minute <= 0:
            raise ValueError("Rate limit must be positive")
        
        self.base_client._rate_limit = requests_per_minute
        self.logger.info(f"Rate limit set to {requests_per_minute} requests per minute")
    
    # Convenience methods for common operations
    def search_users_by_name(self, first_name: str = None, last_name: str = None) -> AlmaResponse:
        """
        Search users by name (convenience method).
        
        Args:
            first_name: User's first name
            last_name: User's last name
        
        Returns:
            AlmaResponse containing search results
        """
        query_parts = []
        if first_name:
            query_parts.append(f"first_name~{first_name}")
        if last_name:
            query_parts.append(f"last_name~{last_name}")
        
        if not query_parts:
            raise ValueError("At least one name parameter is required")
        
        query = " AND ".join(query_parts)
        return self.users.search_users(query)
    
    def search_users_by_email(self, email: str) -> AlmaResponse:
        """
        Search users by email (convenience method).
        
        Args:
            email: User's email address
        
        Returns:
            AlmaResponse containing search results
        """
        query = f"email~{email}"
        return self.users.search_users(query)
    
    def search_bibs_by_title(self, title: str, limit: int = 10) -> AlmaResponse:
        """
        Search bibliographic records by title (convenience method).
        
        Args:
            title: Title to search for
            limit: Maximum number of results
        
        Returns:
            AlmaResponse containing search results
        """
        query = f"title~{title}"
        return self.bibs.search_records(query, limit=limit)
    
    def search_bibs_by_isbn(self, isbn: str) -> AlmaResponse:
        """
        Search bibliographic records by ISBN (convenience method).
        
        Args:
            isbn: ISBN to search for
        
        Returns:
            AlmaResponse containing search results
        """
        query = f"isbn~{isbn}"
        return self.bibs.search_records(query)
    
    def get_user_full_info(self, user_id: str) -> dict:
        """
        Get comprehensive user information including loans, requests, and fees.
        
        Args:
            user_id: User identifier
        
        Returns:
            Dictionary with complete user information
        """
        try:
            # Get basic user info
            user_response = self.users.get_user(user_id, expand="loans,requests,fees")
            
            if not user_response.success:
                return {"error": "Failed to retrieve user information"}
            
            user_data = user_response.json()
            
            # Get additional details if needed
            result = {
                "user": user_data,
                "loans": [],
                "requests": [],
                "fees": []
            }
            
            # Get loans
            try:
                loans_response = self.users.get_user_loans(user_id, limit=100)
                if loans_response.success:
                    loans_data = loans_response.json()
                    result["loans"] = loans_data.get("item_loan", [])
            except Exception as e:
                self.logger.warning(f"Failed to get loans for user {user_id}: {e}")
            
            # Get requests
            try:
                requests_response = self.users.get_user_requests(user_id, limit=100)
                if requests_response.success:
                    requests_data = requests_response.json()
                    result["requests"] = requests_data.get("user_request", [])
            except Exception as e:
                self.logger.warning(f"Failed to get requests for user {user_id}: {e}")
            
            # Get fees
            try:
                fees_response = self.users.get_user_fees(user_id, limit=100)
                if fees_response.success:
                    fees_data = fees_response.json()
                    result["fees"] = fees_data.get("user_fee", [])
            except Exception as e:
                self.logger.warning(f"Failed to get fees for user {user_id}: {e}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting full user info for {user_id}: {e}")
            return {"error": str(e)}
    
    def get_bib_full_info(self, mms_id: str) -> dict:
        """
        Get comprehensive bibliographic record information including holdings and items.
        
        Args:
            mms_id: MMS ID of the bibliographic record
        
        Returns:
            Dictionary with complete bibliographic information
        """
        try:
            # Get basic bib info
            bib_response = self.bibs.get_record(mms_id, expand="p_avail,e_avail,d_avail")
            
            if not bib_response.success:
                return {"error": "Failed to retrieve bibliographic record"}
            
            bib_data = bib_response.json()
            
            result = {
                "bib": bib_data,
                "holdings": [],
                "items": [],
                "representations": []
            }
            
            # Get holdings
            try:
                holdings_response = self.bibs.get_holdings(mms_id)
                if holdings_response.success:
                    holdings_data = holdings_response.json()
                    result["holdings"] = holdings_data.get("holding", [])
            except Exception as e:
                self.logger.warning(f"Failed to get holdings for bib {mms_id}: {e}")
            
            # Get items
            try:
                items_response = self.bibs.get_items(mms_id)
                if items_response.success:
                    items_data = items_response.json()
                    result["items"] = items_data.get("item", [])
            except Exception as e:
                self.logger.warning(f"Failed to get items for bib {mms_id}: {e}")
            
            # Get representations
            try:
                repr_response = self.bibs.get_representations(mms_id)
                if repr_response.success:
                    repr_data = repr_response.json()
                    result["representations"] = repr_data.get("representation", [])
            except Exception as e:
                self.logger.warning(f"Failed to get representations for bib {mms_id}: {e}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting full bib info for {mms_id}: {e}")
            return {"error": str(e)}
    
    # Bulk operations support
    def bulk_update_marc_fields(self, updates: list) -> list:
        """
        Perform bulk MARC field updates.
        
        Args:
            updates: List of dictionaries containing update information
                    Each dict should have: mms_id, field, subfields, ind1, ind2
        
        Returns:
            List of results with success/failure status
        """
        results = []
        total_updates = len(updates)
        
        self.logger.info(f"Starting bulk MARC field updates for {total_updates} records")
        
        for i, update in enumerate(updates, 1):
            try:
                mms_id = update.get('mms_id')
                field = update.get('field')
                subfields = update.get('subfields')
                ind1 = update.get('ind1', ' ')
                ind2 = update.get('ind2', ' ')
                
                if not all([mms_id, field, subfields]):
                    results.append({
                        "mms_id": mms_id,
                        "success": False,
                        "error": "Missing required fields (mms_id, field, subfields)"
                    })
                    continue
                
                response = self.bibs.update_marc_field(mms_id, field, subfields, ind1, ind2)
                
                results.append({
                    "mms_id": mms_id,
                    "success": response.success,
                    "response": response.data if response.success else None,
                    "error": None if response.success else "Update failed"
                })
                
                if i % 10 == 0:
                    self.logger.info(f"Processed {i}/{total_updates} updates")
                    
            except Exception as e:
                results.append({
                    "mms_id": update.get('mms_id', 'unknown'),
                    "success": False,
                    "error": str(e)
                })
                self.logger.error(f"Error updating record {update.get('mms_id')}: {e}")
        
        successful = sum(1 for r in results if r['success'])
        self.logger.info(f"Bulk update completed: {successful}/{total_updates} successful")
        
        return results
    
    def close(self) -> None:
        """
        Clean up resources and close connections.
        """
        try:
            self.logger_manager.stop_listener()
            self.logger.info("AlmaClient closed successfully")
        except Exception as e:
            print(f"Error closing AlmaClient: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Example usage and convenience factory functions
def create_alma_client(environment: str = 'PROD') -> AlmaClient:
    """
    Factory function to create an AlmaClient with default settings.
    
    Args:
        environment: Environment to use ('PROD' or 'SB')
    
    Returns:
        Configured AlmaClient instance
    """
    return AlmaClient(environment=environment)


def create_alma_client_with_custom_config(config_path: str, environment: str = 'PROD') -> AlmaClient:
    """
    Factory function to create an AlmaClient with custom configuration.
    
    Args:
        config_path: Path to custom configuration file
        environment: Environment to use ('PROD' or 'SB')
    
    Returns:
        Configured AlmaClient instance with custom config
    """
    # This would be implemented to load custom config
    # For now, return standard client
    return AlmaClient(environment=environment)


if __name__ == "__main__":
    # Example usage
    with create_alma_client('SB') as alma:
        # Test connection
        if alma.test_connection():
            print("✓ Connected to Alma API successfully")
            
            # Show rate limit status
            rate_status = alma.get_rate_limit_status()
            print(f"Rate limit: {rate_status['requests_remaining']}/{rate_status['rate_limit']} requests remaining")
            
            # Example search
            try:
                results = alma.search_bibs_by_title("Python programming", limit=5)
                if results.success:
                    data = results.json()
                    print(f"Found {data.get('total_record_count', 0)} bibliographic records")
                else:
                    print("Search failed")
            except Exception as e:
                print(f"Search error: {e}")
        else:
            print("✗ Failed to connect to Alma API")