"""
Enhanced Users Domain Class for Alma API
Focused on user email management and expiry date processing

This class builds upon your existing AlmaAPIClient foundation.
"""

import re
import json
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, date
import sys
import os

# Import your working AlmaAPIClient
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'client'))
from AlmaAPIClient import AlmaAPIClient


class AlmaUsersManager:
    """
    Enhanced Users management class for Alma API operations.
    Built on your existing AlmaAPIClient foundation.
    
    Focuses on:
    - User retrieval and search
    - Email management and updates
    - Expiry date processing
    - Bulk operations for user email updates
    """
    
    def __init__(self, environment: str = 'SANDBOX'):
        """
        Initialize the Users manager.
        
        Args:
            environment: 'SANDBOX' or 'PRODUCTION'
        """
        self.client = AlmaAPIClient(environment)
        self.environment = environment
        
    def get_user_by_id(self, user_id: str, expand: str = "none") -> Dict[str, Any]:
        """
        Retrieve a user by their ID with complete information.
        
        Args:
            user_id: User identifier (primary ID, barcode, etc.)
            expand: Additional data to include (loans, requests, fees)
        
        Returns:
            Dict containing user data or error information
        """
        if not user_id or not user_id.strip():
            return {
                'success': False,
                'error': 'User ID cannot be empty',
                'user_id': user_id
            }
        
        try:
            endpoint = f'almaws/v1/users/{user_id.strip()}'
            params = {'expand': expand} if expand != "none" else {}
            
            response = self.client.get(endpoint, params=params)
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    'success': True,
                    'user_data': user_data,
                    'user_id': user_id,
                    'primary_id': user_data.get('primary_id', ''),
                    'full_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                }
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'User not found',
                    'user_id': user_id,
                    'status_code': 404
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'user_id': user_id,
                    'status_code': response.status_code,
                    'response_text': response.text[:200]
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Request failed: {str(e)}',
                'user_id': user_id
            }
    
    def get_users_bulk(self, user_id_list: List[str], max_concurrent: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve multiple users efficiently.
        
        Args:
            user_id_list: List of user IDs to retrieve
            max_concurrent: Maximum number of concurrent requests (respect rate limits)
        
        Returns:
            List of user data dictionaries
        """
        if not user_id_list:
            return []
        
        results = []
        
        print(f"Retrieving {len(user_id_list)} users from {self.environment}...")
        
        for i, user_id in enumerate(user_id_list, 1):
            if i % 10 == 0:  # Progress indicator
                print(f"  Progress: {i}/{len(user_id_list)} users processed")
            
            result = self.get_user_by_id(user_id)
            results.append(result)
            
            # Basic rate limiting - respect Alma's limits
            if i % 50 == 0:  # Every 50 requests, pause briefly
                import time
                time.sleep(1)
        
        print(f"Completed: {len(results)} users processed")
        return results
    
    def extract_user_emails(self, user_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract all email addresses from user data.
        
        Args:
            user_data: User data from Alma API
        
        Returns:
            List of email dictionaries with type and address
        """
        emails = []
        
        try:
            contact_info = user_data.get('contact_info', {})
            email_list = contact_info.get('email', [])
            
            # Handle both single email and list of emails
            if isinstance(email_list, dict):
                email_list = [email_list]
            elif not isinstance(email_list, list):
                return emails
            
            for email_entry in email_list:
                if isinstance(email_entry, dict):
                    email_address = email_entry.get('email_address', '')
                    email_type = email_entry.get('email_type', {})
                    
                    if email_address:
                        emails.append({
                            'address': email_address,
                            'type': email_type.get('value', 'unknown') if isinstance(email_type, dict) else str(email_type),
                            'preferred': email_entry.get('preferred', False)
                        })
        
        except Exception as e:
            print(f"Error extracting emails: {e}")
        
        return emails
    
    def get_user_expiry_date(self, user_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract expiry date from user data.
        
        Args:
            user_data: User data from Alma API
        
        Returns:
            Expiry date as string (YYYY-MM-DDTZ format) or None
        """
        try:
            return user_data.get('expiry_date')
        except Exception:
            return None
    
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
    
    def update_user_email(self, user_id: str, new_email: str, email_type: str = 'personal') -> Dict[str, Any]:
        """
        Update a user's primary email address.
        
        Args:
            user_id: User identifier
            new_email: New email address
            email_type: Type of email (personal, work, etc.)
        
        Returns:
            Dict with success status and details
        """
        if not self.validate_email(new_email):
            return {
                'success': False,
                'error': 'Invalid email format',
                'user_id': user_id,
                'new_email': new_email
            }
        
        try:
            # First, get the current user data
            user_result = self.get_user_by_id(user_id)
            print("-----------------------------------------------\n")
            print(f"This is user_result:\n{user_result}")
            print("-----------------------------------------------\n")
            if not user_result['success']:
                return {
                    'success': False,
                    'error': f"Could not retrieve user: {user_result['error']}",
                    'user_id': user_id,
                    'new_email': new_email
                }
            
            user_data = user_result['user_data']
            print("-----------------------------------------------\n")
            print(f"Updating email for user:\n{user_data}")
            print("-----------------------------------------------\n")            


            
            # Update the email in the user data
            contact_info = user_data.get('contact_info', {})
            print("-----------------------------------------------\n")
            print(f"This is contact_info:\n{contact_info}")
            print("-----------------------------------------------\n")            

            email_list = contact_info.get('email', [])
            print("-----------------------------------------------\n")
            print(f"This is the email_list:\n{email_list}")
            print("-----------------------------------------------\n")            
            
            
            # Handle both single email and list of emails
            if isinstance(email_list, dict):
                print(f"Email list is a single dictionary, converting to list{type(email_list)}")
                email_list = [email_list]
            elif not isinstance(email_list, list):
                print(f"Email list is not a list, initializing empty list{type(email_list)}")
                email_list = []
            else:
                # this is crucial for the next steps. The AI did not realized that the email_list could be a list or a dict, so it was not handling the case where it is a list properly.
                print(f"Email list is already a list{type(email_list)}") 
            
        #     # Update existing email or add new one
        #     email_updated = False
        #     for email_entry in email_list:
        #         if email_entry.get('preferred', False) or len(email_list) == 1:
        #             email_entry['email_address'] = new_email
        #             email_updated = True
        #             break
            
        #     # If no email found, add a new one
        #     if not email_updated:
        #         new_email_entry = {
        #             'email_address': new_email,
        #             'email_type': {'value': email_type},
        #             'preferred': True
        #         }
        #         email_list.append(new_email_entry)
            
        #     # Update the contact info
        #     contact_info['email'] = email_list
        #     user_data['contact_info'] = contact_info
            
        #     # Send the update to Alma
        #     endpoint = f'almaws/v1/users/{user_id}'
        #     response = self.client.put(endpoint, data=user_data)
            
        #     if response.status_code == 200:
        #         return {
        #             'success': True,
        #             'user_id': user_id,
        #             'new_email': new_email,
        #             'message': 'Email updated successfully'
        #         }
        #     else:
        #         return {
        #             'success': False,
        #             'error': f'Update failed: {response.status_code}',
        #             'user_id': user_id,
        #             'new_email': new_email,
        #             'status_code': response.status_code,
        #             'response_text': response.text[:200]
        #         }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Update failed: {str(e)}',
                'user_id': user_id,
                'new_email': new_email
            }
    
    def bulk_update_user_emails(self, updates_list: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Update multiple users' emails in bulk.
        
        Args:
            updates_list: List of dicts with 'user_id' and 'new_email' keys
        
        Returns:
            List of update results
        """
        if not updates_list:
            return []
        
        results = []
        
        print(f"Starting bulk email update for {len(updates_list)} users in {self.environment}...")
        
        for i, update in enumerate(updates_list, 1):
            user_id = update.get('user_id', '')
            new_email = update.get('new_email', '')
            email_type = update.get('email_type', 'personal')
            
            if i % 5 == 0:  # Progress indicator
                print(f"  Progress: {i}/{len(updates_list)} email updates processed")
            
            result = self.update_user_email(user_id, new_email, email_type)
            result['update_index'] = i
            results.append(result)
            
            # Rate limiting for bulk operations
            if i % 25 == 0:  # Every 25 updates, pause briefly
                import time
                time.sleep(2)
        
        # Summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        print(f"Bulk email update completed:")
        print(f"  ✓ Successful: {successful}")
        print(f"  ✗ Failed: {failed}")
        
        return results
    
    def analyze_user_expiry_dates(self, user_id_list: List[str], target_date: str = None) -> Dict[str, Any]:
        """
        Analyze expiry dates for a list of users.
        
        Args:
            user_id_list: List of user IDs to analyze
            target_date: Date to compare against (YYYY-MM-DD format), defaults to today
        
        Returns:
            Analysis results with expired/expiring users
        """
        if target_date is None:
            target_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get all users
        users = self.get_users_bulk(user_id_list)
        
        expired_users = []
        expiring_soon = []  # Within 30 days
        valid_users = []
        error_users = []
        
        target_dt = datetime.strptime(target_date, '%Y-%m-%d')
        
        for user_result in users:
            if not user_result['success']:
                error_users.append(user_result)
                continue
            
            user_data = user_result['user_data']
            expiry_date_str = self.get_user_expiry_date(user_data)
            
            if not expiry_date_str:
                continue
            
            try:
                # Parse Alma date format (YYYY-MM-DDTZ)
                expiry_date_clean = expiry_date_str.replace('Z', '')
                expiry_dt = datetime.strptime(expiry_date_clean, '%Y-%m-%d')
                
                days_until_expiry = (expiry_dt - target_dt).days
                
                user_info = {
                    'user_id': user_result['user_id'],
                    'primary_id': user_result['primary_id'],
                    'full_name': user_result['full_name'],
                    'expiry_date': expiry_date_str,
                    'days_until_expiry': days_until_expiry,
                    'emails': self.extract_user_emails(user_data)
                }
                
                if days_until_expiry < 0:
                    expired_users.append(user_info)
                elif days_until_expiry <= 30:
                    expiring_soon.append(user_info)
                else:
                    valid_users.append(user_info)
                    
            except ValueError as e:
                error_users.append({
                    'user_id': user_result['user_id'],
                    'error': f'Date parsing error: {e}',
                    'expiry_date': expiry_date_str
                })
        
        return {
            'analysis_date': target_date,
            'total_users': len(users),
            'expired_users': expired_users,
            'expiring_soon': expiring_soon,
            'valid_users': valid_users,
            'error_users': error_users,
            'summary': {
                'expired_count': len(expired_users),
                'expiring_soon_count': len(expiring_soon),
                'valid_count': len(valid_users),
                'error_count': len(error_users)
            }
        }
    
    def switch_environment(self, new_environment: str):
        """Switch between SANDBOX and PRODUCTION environments."""
        self.client.switch_environment(new_environment)
        self.environment = new_environment
        print(f"✓ Switched to {new_environment} environment")
    
    def get_environment(self) -> str:
        """Get current environment."""
        return self.environment


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the AlmaUsersManager class
    """
    
    def example_usage():
        # Initialize manager
        users_mgr = AlmaUsersManager('SANDBOX')
        
        # Example: Get a single user
        # print("=== Getting Single User ===")
        # user_result = users_mgr.get_user_by_id('027393602')
        # if user_result['success']:
        #     print(f"✓ Found user: {user_result['full_name']}")
            
        #     # Extract emails
        #     emails = users_mgr.extract_user_emails(user_result['user_data'])
        #     print(f"  Emails: {[e['address'] for e in emails]}")
            
        #     # Get expiry date
        #     expiry = users_mgr.get_user_expiry_date(user_result['user_data'])
        #     print(f"  Expiry: {expiry}")
        # else:
        #     print(f"✗ Error: {user_result['error']}")
        
        # # Example: Bulk user analysis
        # print("\n=== Bulk User Analysis ===")
        # user_ids = ['000191908', '000213751', '027393602']  # Your user list
        # analysis = users_mgr.analyze_user_expiry_dates(user_ids)
        
        # print(f"Expired users: {analysis['summary']['expired_count']}")
        # print(f"Expiring soon: {analysis['summary']['expiring_soon_count']}")
        
        # # Example: Update email
        print("\n=== Update User Email ===")
        update_result = users_mgr.update_user_email('027393602', 'new@email.com')
        # if update_result['success']:
        #     print("✓ Email updated successfully")
        # else:
        #     print(f"✗ Update failed: {update_result['error']}")
    
    # Uncomment to run examples
    example_usage()