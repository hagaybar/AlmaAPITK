"""
Enhanced Users Domain Class for Alma API
Aligned with AlmaAPIClient integration patterns and focused on email update workflow
for users expired 2+ years from Alma sets.
"""

import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Import the working AlmaAPIClient and its response/error classes
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'client'))
from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError


class Users:
    """
    Enhanced Users domain class for Alma API operations.
    
    Focused on email update workflow for expired users:
    - Retrieve users by ID from sets
    - Analyze expiry dates (2+ years expired)
    - Extract and validate email addresses
    - Update user email addresses
    - Bulk processing capabilities
    """
    
    def __init__(self, client: AlmaAPIClient):
        """
        Initialize the Users domain.
        
        Args:
            client: The AlmaAPIClient instance for making HTTP requests
        """
        self.client = client
        self.logger = client.logger
        self.environment = client.get_environment()
         # Setup enhanced logger with optional file handler
        self.logger = self._setup_enhanced_logger("sb_log_file.log" if self.environment == "SANDBOX" else "prod_log_file.log")
    
    # Core User Retrieval Methods



    def _setup_enhanced_logger(self, log_file: str = None):
        """
        Setup enhanced logger with both console and optional file handlers.
        
        Args:
            log_file: Optional path to log file
            
        Returns:
            Enhanced logger instance
        """
        
        # Create logger name
        logger_name = f"Users_{self.environment}"
        logger = logging.getLogger(logger_name)
        
        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()
        logger.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler (INFO level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler (DEBUG level) - if log_file specified
        if log_file:
            try:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
                logger.info(f"File logging enabled: {log_file}")
            except Exception as e:
                logger.error(f"Could not create file handler for {log_file}: {e}")
        
        return logger





    
    def get_user(self, user_id: str, expand: str = "none") -> AlmaResponse:
        """
        Retrieve a user by their ID.
        
        Args:
            user_id: User identifier (primary ID, barcode, etc.)
            expand: Additional data to include (loans, requests, fees)
        
        Returns:
            AlmaResponse containing user data
            
        Raises:
            AlmaValidationError: If user_id is empty
            AlmaAPIError: If API request fails
        """
        if not user_id or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        
        params = {'expand': expand} if expand != "none" else {}
        endpoint = f'almaws/v1/users/{user_id.strip()}'
        
        try:
            response = self.client.get(endpoint, params=params)
            self.logger.info(f"Retrieved user {user_id}")
            return response
            
        except AlmaAPIError as e:
            if e.status_code == 404:
                self.logger.warning(f"User not found: {user_id}")
            else:
                self.logger.error(f"API error retrieving user {user_id}: {e}")
            raise
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> AlmaResponse:
        """
        Update a user record.
        
        Args:
            user_id: User identifier
            user_data: Complete user data to update
        
        Returns:
            AlmaResponse containing updated user data
            
        Raises:
            AlmaValidationError: If user_id is empty or user_data is invalid
            AlmaAPIError: If API request fails
        """
        if not user_id or not user_id.strip():
            raise AlmaValidationError("User ID cannot be empty")
        
        if not user_data or not isinstance(user_data, dict):
            raise AlmaValidationError("User data must be a non-empty dictionary")
        
        endpoint = f'almaws/v1/users/{user_id.strip()}'
        
        try:
            response = self.client.put(endpoint, data=user_data)
            self.logger.info(f"Updated user {user_id}")
            return response
            
        except AlmaAPIError as e:
            self.logger.error(f"API error updating user {user_id}: {e}")
            raise
    
    # Expiry Date Analysis Methods
    
    def get_user_expiry_date(self, user_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract expiry date from user data.
        
        Args:
            user_data: User data from Alma API
        
        Returns:
            Expiry date as string (YYYY-MM-DDTZ format) or None if not found
        """
        try:
            expiry_date = user_data.get('expiry_date')
            if expiry_date and isinstance(expiry_date, str):
                return expiry_date.strip()
            return None
        except Exception as e:
            self.logger.error(f"Error extracting expiry date: {e}")
            return None
    
    def parse_expiry_date(self, expiry_date_str: str) -> Optional[datetime]:
        """
        Parse Alma expiry date string to datetime object.
        
        Args:
            expiry_date_str: Expiry date string from Alma (YYYY-MM-DDTZ format)
        
        Returns:
            datetime object or None if parsing fails
        """
        if not expiry_date_str:
            return None
        
        try:
            # Handle Alma date format: remove 'Z' suffix if present
            clean_date = expiry_date_str.replace('Z', '')
            
            # Parse the date (assuming YYYY-MM-DD format)
            expiry_dt = datetime.strptime(clean_date, '%Y-%m-%d')
            return expiry_dt
            
        except ValueError as e:
            self.logger.error(f"Error parsing expiry date '{expiry_date_str}': {e}")
            return None
    
    def is_user_expired_years(self, user_data: Dict[str, Any], years_threshold: int = 2) -> Tuple[bool, Optional[int]]:
        """
        Check if user is expired for the specified number of years or more.
        
        Args:
            user_data: User data from Alma API
            years_threshold: Minimum years expired to return True (default: 2)
        
        Returns:
            Tuple of (is_expired_enough, years_expired)
            - is_expired_enough: True if expired >= years_threshold
            - years_expired: Number of years expired (None if no expiry date)
        """
        expiry_date_str = self.get_user_expiry_date(user_data)
        if not expiry_date_str:
            self.logger.debug("User has no expiry date")
            return False, None
        
        expiry_dt = self.parse_expiry_date(expiry_date_str)
        if not expiry_dt:
            self.logger.warning(f"Could not parse expiry date: {expiry_date_str}")
            return False, None
        
        # Calculate years expired
        today = datetime.now()
        time_diff = today - expiry_dt
        years_expired = time_diff.days // 365  # Simple years calculation
        
        is_expired_enough = years_expired >= years_threshold
        
        self.logger.debug(f"User expired {years_expired} years ago, threshold: {years_threshold}, qualifies: {is_expired_enough}")
        return is_expired_enough, years_expired
    
    # Email Management Methods
    
    def extract_user_emails(self, user_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract all email addresses from user data.
        
        Args:
            user_data: User data from Alma API
        
        Returns:
            List of email dictionaries with type, address, and preferred status
        """
        emails = []
        
        try:
            contact_info = user_data.get('contact_info', {})
            email_list = contact_info.get('email', [])
            
            # Handle three possible cases for email_list
            if isinstance(email_list, dict):
                # Single email as dict
                email_list = [email_list]
            elif not isinstance(email_list, list):
                # No emails or invalid format
                email_list = []
            
            for email_entry in email_list:
                if isinstance(email_entry, dict):
                    email_address = email_entry.get('email_address', '').strip()
                    if email_address:
                        email_info = {
                            'address': email_address,
                            'type': self._extract_email_type(email_entry),
                            'preferred': email_entry.get('preferred', False),
                            'original_entry': email_entry  # Keep for updates
                        }
                        emails.append(email_info)
            
            self.logger.debug(f"Extracted {len(emails)} emails from user")
            return emails
            
        except Exception as e:
            self.logger.error(f"Error extracting user emails: {e}")
            return []
    
    def _extract_email_type(self, email_entry: Dict[str, Any]) -> str:
        """Extract email type from email entry."""
        email_type = email_entry.get('email_type', {})
        if isinstance(email_type, dict):
            return email_type.get('value', 'unknown')
        return str(email_type) if email_type else 'unknown'
    
    def validate_email(self, email: str) -> bool:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not email or not isinstance(email, str):
            return False
        
        # Basic email validation regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email.strip()) is not None
    
    def generate_new_email(self, user_data: Dict[str, Any], email_pattern: str) -> str:
        """
        Generate new email address using pattern and user data.
        
        Args:
            user_data: User data from Alma API
            email_pattern: Email pattern with placeholders like "expired-{user_id}@institution.edu"
        
        Returns:
            Generated email address
            
        Raises:
            AlmaValidationError: If pattern is invalid or required data is missing
        """
        if not email_pattern or '{user_id}' not in email_pattern:
            raise AlmaValidationError("Email pattern must contain {user_id} placeholder")
        
        try:
            # Extract user information for pattern replacement
            user_id = user_data.get('primary_id', '')
            first_name = user_data.get('first_name', '').lower()
            last_name = user_data.get('last_name', '').lower()
            
            if not user_id:
                raise AlmaValidationError("User ID not found in user data")
            
            # Replace placeholders
            new_email = email_pattern.format(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name
            )
            
            if not self.validate_email(new_email):
                raise AlmaValidationError(f"Generated email is invalid: {new_email}")
            
            return new_email
            
        except KeyError as e:
            raise AlmaValidationError(f"Unknown placeholder in email pattern: {e}")
        except Exception as e:
            raise AlmaValidationError(f"Error generating email: {e}")
    
    def update_user_email(self, user_id: str, new_email: str, email_type: str = 'personal') -> AlmaResponse:
        """
        Update a user's primary email address.
        
        Args:
            user_id: User identifier
            new_email: New email address
            email_type: Type of email (personal, work, etc.)
        
        Returns:
            AlmaResponse containing updated user data
            
        Raises:
            AlmaValidationError: If inputs are invalid
            AlmaAPIError: If API request fails
        """
        if not self.validate_email(new_email):
            raise AlmaValidationError(f"Invalid email format: {new_email}")
        
        try:
            # Get current user data
            user_response = self.get_user(user_id)
            user_data = user_response.json()
            
            # Get current contact info
            contact_info = user_data.get('contact_info', {})
            email_list = contact_info.get('email', [])
            
            # Handle email list format
            if isinstance(email_list, dict):
                email_list = [email_list]
            elif not isinstance(email_list, list):
                email_list = []
            
            # Update existing email or add new one
            email_updated = False
            for email_entry in email_list:
                if isinstance(email_entry, dict):
                    # Update preferred email or the first one if only one exists
                    if email_entry.get('preferred', False) or len(email_list) == 1:
                        email_entry['email_address'] = new_email
                        email_updated = True
                        break
            
            # If no email was updated, add a new one
            if not email_updated:
                new_email_entry = {
                    'email_address': new_email,
                    'email_type': {'value': email_type},
                    'preferred': True
                }
                email_list.append(new_email_entry)
            
            # Update the user data
            contact_info['email'] = email_list
            user_data['contact_info'] = contact_info
            
            # Send the update to Alma
            response = self.update_user(user_id, user_data)
            self.logger.info(f"Updated email for user {user_id} to {new_email}")
            return response
            
        except AlmaAPIError:
            raise  # Re-raise API errors
        except Exception as e:
            raise AlmaAPIError(f"Failed to update user email: {e}")
    
    # Set-Based Processing Methods
    
    def process_user_for_expiry(self, user_id: str, years_threshold: int = 2) -> Dict[str, Any]:
        """
        Process a single user to determine if they qualify for email update.
        
        Args:
            user_id: User identifier
            years_threshold: Minimum years expired to qualify
        
        Returns:
            Dict with processing results including qualification status
        """
        result = {
            'user_id': user_id,
            'success': False,
            'qualifies_for_update': False,
            'error': None,
            'user_data': None,
            'emails': [],
            'years_expired': None,
            'expiry_date': None
        }
        
        try:
            # Get user data
            user_response = self.get_user(user_id)
            user_data = user_response.json()
            result['user_data'] = user_data
            result['success'] = True
            
            # Check expiry status
            is_expired_enough, years_expired = self.is_user_expired_years(user_data, years_threshold)
            result['years_expired'] = years_expired
            result['expiry_date'] = self.get_user_expiry_date(user_data)
            
            # Extract emails
            emails = self.extract_user_emails(user_data)
            result['emails'] = emails
            
            # Determine if user qualifies for email update
            has_email = len(emails) > 0
            result['qualifies_for_update'] = is_expired_enough and has_email
            
            if result['qualifies_for_update']:
                self.logger.info(f"User {user_id} qualifies: expired {years_expired} years, has {len(emails)} emails")
            else:
                if not is_expired_enough:
                    self.logger.debug(f"User {user_id} not expired enough: {years_expired} years")
                if not has_email:
                    self.logger.debug(f"User {user_id} has no email addresses")
            
        except AlmaAPIError as e:
            result['error'] = f"API error: {e}"
            self.logger.error(f"Error processing user {user_id}: {e}")
        except Exception as e:
            result['error'] = f"Processing error: {e}"
            self.logger.error(f"Unexpected error processing user {user_id}: {e}")
        
        return result
    
    def process_users_batch(self, user_ids: List[str], years_threshold: int = 2, 
                           max_workers: int = 5) -> List[Dict[str, Any]]:
        """
        Process multiple users for expiry qualification in batch.
        
        Args:
            user_ids: List of user IDs to process
            years_threshold: Minimum years expired to qualify
            max_workers: Maximum concurrent processing (respect rate limits)
        
        Returns:
            List of processing results for each user
        """
        if not user_ids:
            return []
        
        results = []
        total_users = len(user_ids)
        
        self.logger.info(f"Processing {total_users} users for expiry qualification")
        
        for i, user_id in enumerate(user_ids, 1):
            # Progress reporting
            if i % 10 == 0 or i == total_users:
                self.logger.info(f"Processing user {i}/{total_users}: {user_id}")
            
            result = self.process_user_for_expiry(user_id, years_threshold)
            results.append(result)
            
            # Basic rate limiting - pause every 50 requests
            if i % 50 == 0:
                time.sleep(1)
        
        # Summary statistics
        successful = sum(1 for r in results if r['success'])
        qualified = sum(1 for r in results if r['qualifies_for_update'])
        
        self.logger.info(f"Batch processing complete: {successful}/{total_users} successful, {qualified} qualified for update")
        
        return results
    
    def bulk_update_emails(self, email_updates: List[Dict[str, str]], 
                          dry_run: bool = True) -> List[Dict[str, Any]]:
        """
        Update multiple users' emails in bulk.
        
        Args:
            email_updates: List of dicts with 'user_id' and 'new_email' keys
            dry_run: If True, don't actually update emails (default: True for safety)
        
        Returns:
            List of update results
        """
        if not email_updates:
            return []
        
        results = []
        total_updates = len(email_updates)
        
        mode = "DRY RUN" if dry_run else "LIVE UPDATE"
        self.logger.info(f"Starting bulk email update ({mode}) for {total_updates} users")
        
        for i, update in enumerate(email_updates, 1):
            user_id = update.get('user_id', '')
            new_email = update.get('new_email', '')
            email_type = update.get('email_type', 'personal')
            
            result = {
                'user_id': user_id,
                'new_email': new_email,
                'success': False,
                'error': None,
                'dry_run': dry_run
            }
            
            # Progress reporting
            if i % 5 == 0 or i == total_updates:
                self.logger.info(f"Processing email update {i}/{total_updates}: {user_id}")
            
            try:
                if dry_run:
                    # Validate inputs without updating
                    if not user_id or not new_email:
                        raise AlmaValidationError("Missing user_id or new_email")
                    if not self.validate_email(new_email):
                        raise AlmaValidationError(f"Invalid email format: {new_email}")
                    
                    # Try to get user to verify they exist
                    self.get_user(user_id)
                    
                    result['success'] = True
                    self.logger.debug(f"DRY RUN: Would update {user_id} email to {new_email}")
                else:
                    # Actually update the email
                    self.update_user_email(user_id, new_email, email_type)
                    result['success'] = True
                    self.logger.info(f"Updated {user_id} email to {new_email}")
                
            except (AlmaAPIError, AlmaValidationError) as e:
                result['error'] = str(e)
                self.logger.error(f"Error updating email for {user_id}: {e}")
            except Exception as e:
                result['error'] = f"Unexpected error: {e}"
                self.logger.error(f"Unexpected error updating email for {user_id}: {e}")
            
            results.append(result)
            
            # Rate limiting for bulk operations
            if i % 25 == 0:
                time.sleep(2)
        
        # Summary statistics
        successful = sum(1 for r in results if r['success'])
        failed = total_updates - successful
        
        self.logger.info(f"Bulk email update complete ({mode}): {successful} successful, {failed} failed")
        
        return results
    
    # Utility Methods
    
    def get_environment(self) -> str:
        """Get current environment from client."""
        return self.client.get_environment()
    
    def test_connection(self) -> bool:
        """
        Test if the users endpoints are accessible.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get current user (which should always work with a valid API key)
            response = self.client.get("almaws/v1/users", params={"limit": "1"})
            success = response.status_code == 200
            
            if success:
                self.logger.info(f"✓ Users API connection successful ({self.environment})")
            else:
                self.logger.error(f"✗ Users API connection failed: {response.status_code}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"✗ Users API connection error: {e}")
            return False


# Usage examples for the email update workflow
if __name__ == "__main__":
    """
    Example usage of the enhanced Users class for email update workflow
    """
    
    def example_workflow():
        # Initialize client and users domain
        from almaapitk.client.AlmaAPIClient import AlmaAPIClient
        
        client = AlmaAPIClient('SANDBOX')
        users = Users(client)

        print(f"Logger name: {users.logger.name}")
        print(f"Logger level: {users.logger.level}")
        print(f"Logger handlers: {users.logger.handlers}")
        for handler in users.logger.handlers:
            print(f"  Handler: {type(handler).__name__}, Level: {handler.level}")
            if hasattr(handler, 'baseFilename'):
                print(f"    File: {handler.baseFilename}")
        
        # Test connection
        if not users.test_connection():
            print("Cannot proceed - users API connection failed")
            return
        
        # Example: Process single user for expiry
        print("=== Single User Processing ===")
        user_id = "123456789"
        result = users.process_user_for_expiry(user_id, years_threshold=2)
        
        if result['success']:
            print(f"User {user_id}: qualifies={result['qualifies_for_update']}, expired {result['years_expired']} years")
        else:
            print(f"Error processing user {user_id}: {result['error']}")
        
        # Example: Batch processing from set
        print("\n=== Batch User Processing ===")
        user_ids = ['222333444', '987654321', '333444555']  # Would come from admin.get_set_members()
        batch_results = users.process_users_batch(user_ids, years_threshold=2)
        
        qualified_users = [r for r in batch_results if r['qualifies_for_update']]
        print(f"Found {len(qualified_users)} users qualified for email update")
        
        # Example: Bulk email update (DRY RUN)
        if qualified_users:
            print("\n=== Email Update (DRY RUN) ===")
            email_updates = []
            for result in qualified_users:
                user_data = result['user_data']
                new_email = users.generate_new_email(user_data, "expired-{user_id}@institution.edu")
                email_updates.append({
                    'user_id': result['user_id'],
                    'new_email': new_email
                })
            
            update_results = users.bulk_update_emails(email_updates, dry_run=True)
            successful_updates = sum(1 for r in update_results if r['success'])
            print(f"DRY RUN: {successful_updates}/{len(email_updates)} email updates would succeed")
    
    # Uncomment to run example
    example_workflow()