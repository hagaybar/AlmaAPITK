from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date
from base_client import BaseAPIClient, AlmaResponse, AlmaValidationError


class Users:
    """
    Domain class for handling Alma Users API operations.
    Covers user management, loans, requests, and fines/fees.
    """
    
    def __init__(self, client: BaseAPIClient):
        self.client = client
        self.logger = client.logger
    
    def get_user(self, user_id: str, view: str = "full", expand: str = None) -> AlmaResponse:
        """
        Retrieve a user by ID.
        
        Args:
            user_id: User identifier (primary ID, barcode, etc.)
            view: Level of detail (brief, full)
            expand: Additional data to include (loans, requests, fees)
        
        Returns:
            AlmaResponse containing user data
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        params = {"view": view}
        if expand:
            params["expand"] = expand
        
        endpoint = f"almaws/v1/users/{user_id}"
        response = self.client.get(endpoint, params=params)
        
        self.logger.info(f"Retrieved user {user_id}")
        return response
    
    def search_users(self, q: str, limit: int = 10, offset: int = 0,
                    order_by: str = None, direction: str = "asc") -> AlmaResponse:
        """
        Search for users.
        
        Args:
            q: Search query (e.g., "first_name~John AND last_name~Doe")
            limit: Number of results to return (max 100)
            offset: Starting point for results
            order_by: Field to sort by
            direction: Sort direction (asc, desc)
        
        Returns:
            AlmaResponse containing search results
        """
        if not q:
            raise AlmaValidationError("Search query is required")
        
        if limit > 100:
            raise AlmaValidationError("Limit cannot exceed 100")
        
        params = {
            "q": q,
            "limit": str(limit),
            "offset": str(offset),
            "order_by": order_by or "last_name",
            "direction": direction
        }
        
        endpoint = "almaws/v1/users"
        response = self.client.get(endpoint, params=params)
        
        self.logger.info(f"Searched users with query: {q}")
        return response
    
    def create_user(self, user_data: Dict[str, Any], 
                   send_pin_number_letter: bool = False,
                   password: str = None) -> AlmaResponse:
        """
        Create a new user.
        
        Args:
            user_data: User record data
            send_pin_number_letter: Whether to send PIN letter
            password: User password (if not using PIN)
        
        Returns:
            AlmaResponse containing the created user
        """
        if not user_data:
            raise AlmaValidationError("User data is required")
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'user_group']
        missing_fields = [field for field in required_fields 
                         if field not in user_data or not user_data[field]]
        
        if missing_fields:
            raise AlmaValidationError(f"Missing required fields: {', '.join(missing_fields)}")
        
        params = {}
        if send_pin_number_letter:
            params["send_pin_number_letter"] = "true"
        if password:
            params["password"] = password
        
        endpoint = "almaws/v1/users"
        response = self.client.post(endpoint, data=user_data, params=params)
        
        self.logger.info(f"Created user: {user_data.get('first_name')} {user_data.get('last_name')}")
        return response
    
    def update_user(self, user_id: str, user_data: Dict[str, Any],
                   override: str = None, send_pin_number_letter: bool = False) -> AlmaResponse:
        """
        Update an existing user.
        
        Args:
            user_id: User identifier
            user_data: Updated user data
            override: Override options (user_with_requests, user_with_loans, user_with_fees)
            send_pin_number_letter: Whether to send PIN letter
        
        Returns:
            AlmaResponse containing the updated user
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        if not user_data:
            raise AlmaValidationError("User data is required")
        
        params = {}
        if override:
            params["override"] = override
        if send_pin_number_letter:
            params["send_pin_number_letter"] = "true"
        
        endpoint = f"almaws/v1/users/{user_id}"
        response = self.client.put(endpoint, data=user_data, params=params)
        
        self.logger.info(f"Updated user {user_id}")
        return response
    
    def delete_user(self, user_id: str, override: str = None) -> AlmaResponse:
        """
        Delete a user.
        
        Args:
            user_id: User identifier
            override: Override options (user_with_requests, user_with_loans, user_with_fees)
        
        Returns:
            AlmaResponse confirming deletion
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        params = {}
        if override:
            params["override"] = override
        
        endpoint = f"almaws/v1/users/{user_id}"
        response = self.client.delete(endpoint, params=params)
        
        self.logger.info(f"Deleted user {user_id}")
        return response
    
    # User loans management
    def get_user_loans(self, user_id: str, limit: int = 10, offset: int = 0) -> AlmaResponse:
        """
        Get loans for a user.
        
        Args:
            user_id: User identifier
            limit: Number of results to return
            offset: Starting point for results
        
        Returns:
            AlmaResponse containing loan data
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        params = {
            "limit": str(limit),
            "offset": str(offset)
        }
        
        endpoint = f"almaws/v1/users/{user_id}/loans"
        response = self.client.get(endpoint, params=params)
        
        self.logger.info(f"Retrieved loans for user {user_id}")
        return response
    
    def get_loan(self, user_id: str, loan_id: str) -> AlmaResponse:
        """
        Get a specific loan for a user.
        
        Args:
            user_id: User identifier
            loan_id: Loan identifier
        
        Returns:
            AlmaResponse containing loan details
        """
        if not user_id or not loan_id:
            raise AlmaValidationError("User ID and loan ID are required")
        
        endpoint = f"almaws/v1/users/{user_id}/loans/{loan_id}"
        response = self.client.get(endpoint)
        
        self.logger.info(f"Retrieved loan {loan_id} for user {user_id}")
        return response
    
    def renew_loan(self, user_id: str, loan_id: str) -> AlmaResponse:
        """
        Renew a loan for a user.
        
        Args:
            user_id: User identifier
            loan_id: Loan identifier
        
        Returns:
            AlmaResponse containing renewal result
        """
        if not user_id or not loan_id:
            raise AlmaValidationError("User ID and loan ID are required")
        
        endpoint = f"almaws/v1/users/{user_id}/loans/{loan_id}"
        
        # Create loan object with op=renew
        loan_data = {
            "user_loan": {
                "loan_id": loan_id,
                "op": "renew"
            }
        }
        
        response = self.client.put(endpoint, data=loan_data)
        
        self.logger.info(f"Renewed loan {loan_id} for user {user_id}")
        return response
    
    def return_loan(self, user_id: str, loan_id: str, 
                   library_code: str = None, circ_desk: str = None) -> AlmaResponse:
        """
        Return a loan for a user.
        
        Args:
            user_id: User identifier
            loan_id: Loan identifier
            library_code: Library where item is returned
            circ_desk: Circulation desk code
        
        Returns:
            AlmaResponse containing return result
        """
        if not user_id or not loan_id:
            raise AlmaValidationError("User ID and loan ID are required")
        
        params = {}
        if library_code:
            params["library_code"] = library_code
        if circ_desk:
            params["circ_desk"] = circ_desk
        
        endpoint = f"almaws/v1/users/{user_id}/loans/{loan_id}"
        response = self.client.delete(endpoint, params=params)
        
        self.logger.info(f"Returned loan {loan_id} for user {user_id}")
        return response
    
    # User requests management
    def get_user_requests(self, user_id: str, request_type: str = "HOLD",
                         limit: int = 10, offset: int = 0) -> AlmaResponse:
        """
        Get requests for a user.
        
        Args:
            user_id: User identifier
            request_type: Type of request (HOLD, DIGITIZATION, BOOKING)
            limit: Number of results to return
            offset: Starting point for results
        
        Returns:
            AlmaResponse containing request data
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        params = {
            "request_type": request_type,
            "limit": str(limit),
            "offset": str(offset)
        }
        
        endpoint = f"almaws/v1/users/{user_id}/requests"
        response = self.client.get(endpoint, params=params)
        
        self.logger.info(f"Retrieved {request_type} requests for user {user_id}")
        return response
    
    def create_request(self, user_id: str, request_data: Dict[str, Any]) -> AlmaResponse:
        """
        Create a request for a user.
        
        Args:
            user_id: User identifier
            request_data: Request details
        
        Returns:
            AlmaResponse containing the created request
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        if not request_data:
            raise AlmaValidationError("Request data is required")
        
        endpoint = f"almaws/v1/users/{user_id}/requests"
        response = self.client.post(endpoint, data=request_data)
        
        self.logger.info(f"Created request for user {user_id}")
        return response
    
    def cancel_request(self, user_id: str, request_id: str, 
                      reason: str = "CancelledByPatron") -> AlmaResponse:
        """
        Cancel a request for a user.
        
        Args:
            user_id: User identifier
            request_id: Request identifier
            reason: Cancellation reason
        
        Returns:
            AlmaResponse confirming cancellation
        """
        if not user_id or not request_id:
            raise AlmaValidationError("User ID and request ID are required")
        
        params = {"reason": reason}
        
        endpoint = f"almaws/v1/users/{user_id}/requests/{request_id}"
        response = self.client.delete(endpoint, params=params)
        
        self.logger.info(f"Cancelled request {request_id} for user {user_id}")
        return response
    
    # User fees management
    def get_user_fees(self, user_id: str, status: str = "ACTIVE",
                     limit: int = 10, offset: int = 0) -> AlmaResponse:
        """
        Get fees for a user.
        
        Args:
            user_id: User identifier
            status: Fee status (ACTIVE, CLOSED)
            limit: Number of results to return
            offset: Starting point for results
        
        Returns:
            AlmaResponse containing fee data
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        params = {
            "status": status,
            "limit": str(limit),
            "offset": str(offset)
        }
        
        endpoint = f"almaws/v1/users/{user_id}/fees"
        response = self.client.get(endpoint, params=params)
        
        self.logger.info(f"Retrieved {status} fees for user {user_id}")
        return response
    
    def create_fee(self, user_id: str, fee_data: Dict[str, Any]) -> AlmaResponse:
        """
        Create a fee for a user.
        
        Args:
            user_id: User identifier
            fee_data: Fee details including type, amount, comment
        
        Returns:
            AlmaResponse containing the created fee
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        if not fee_data:
            raise AlmaValidationError("Fee data is required")
        
        # Validate required fee fields
        required_fields = ['type', 'sum']
        missing_fields = [field for field in required_fields 
                         if field not in fee_data]
        
        if missing_fields:
            raise AlmaValidationError(f"Missing required fee fields: {', '.join(missing_fields)}")
        
        endpoint = f"almaws/v1/users/{user_id}/fees"
        response = self.client.post(endpoint, data=fee_data)
        
        self.logger.info(f"Created fee for user {user_id}")
        return response
    
    def pay_fee(self, user_id: str, fee_id: str, amount: float, 
               method: str = "CASH", comment: str = None) -> AlmaResponse:
        """
        Pay a fee for a user.
        
        Args:
            user_id: User identifier
            fee_id: Fee identifier
            amount: Payment amount
            method: Payment method (CASH, CREDIT_CARD, CHECK, etc.)
            comment: Payment comment
        
        Returns:
            AlmaResponse containing payment result
        """
        if not user_id or not fee_id:
            raise AlmaValidationError("User ID and fee ID are required")
        
        if amount <= 0:
            raise AlmaValidationError("Payment amount must be positive")
        
        payment_data = {
            "amount": {"sum": str(amount)},
            "method": {"value": method},
            "external_transaction_id": f"payment_{fee_id}_{int(datetime.now().timestamp())}"
        }
        
        if comment:
            payment_data["comment"] = comment
        
        endpoint = f"almaws/v1/users/{user_id}/fees/{fee_id}"
        params = {"op": "pay"}
        
        response = self.client.post(endpoint, data=payment_data, params=params)
        
        self.logger.info(f"Paid fee {fee_id} for user {user_id}: {amount}")
        return response
    
    def waive_fee(self, user_id: str, fee_id: str, amount: float,
                 reason: str = "GOODWILL", comment: str = None) -> AlmaResponse:
        """
        Waive a fee for a user.
        
        Args:
            user_id: User identifier
            fee_id: Fee identifier
            amount: Waived amount
            reason: Waive reason
            comment: Waive comment
        
        Returns:
            AlmaResponse containing waive result
        """
        if not user_id or not fee_id:
            raise AlmaValidationError("User ID and fee ID are required")
        
        if amount <= 0:
            raise AlmaValidationError("Waive amount must be positive")
        
        waive_data = {
            "amount": {"sum": str(amount)},
            "reason": {"value": reason}
        }
        
        if comment:
            waive_data["comment"] = comment
        
        endpoint = f"almaws/v1/users/{user_id}/fees/{fee_id}"
        params = {"op": "waive"}
        
        response = self.client.post(endpoint, data=waive_data, params=params)
        
        self.logger.info(f"Waived fee {fee_id} for user {user_id}: {amount}")
        return response
    
    # User deposits management
    def get_user_deposits(self, user_id: str) -> AlmaResponse:
        """
        Get deposits for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            AlmaResponse containing deposit data
        """
        if not user_id:
            raise AlmaValidationError("User ID is required")
        
        endpoint = f"almaws/v1/users/{user_id}/deposits"
        response = self.client.get(endpoint)
        
        self.logger.info(f"Retrieved deposits for user {user_id}")
        return response
    
    # Utility methods
    def validate_user_data(self, user_data: Dict[str, Any]) -> List[str]:
        """
        Validate user data structure.
        
        Args:
            user_data: User data to validate
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Required fields
        required_fields = ['first_name', 'last_name', 'user_group']
        for field in required_fields:
            if field not in user_data or not user_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Email validation
        if 'contact_info' in user_data and 'email' in user_data['contact_info']:
            emails = user_data['contact_info']['email']
            if isinstance(emails, list):
                for email in emails:
                    if '@' not in email.get('email_address', ''):
                        errors.append(f"Invalid email format: {email.get('email_address')}")
        
        # Date validation
        if 'expiry_date' in user_data:
            try:
                datetime.strptime(user_data['expiry_date'], '%Y-%m-%dZ')
            except ValueError:
                errors.append("Invalid expiry_date format. Use YYYY-MM-DDTZ")
        
        return errors