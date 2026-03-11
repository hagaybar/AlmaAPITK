"""
AlmaAPIClient - General Abstract Gateway to Alma API
A foundational class that serves as the base for all Alma API interactions.
This is designed to be 'pluggable' - other classes will use this as their foundation.
"""
import os
import requests
import json
from typing import Optional, Dict, Any, Union, List
import time
from almaapitk.alma_logging import get_logger

class AlmaResponse:
    """Response wrapper to maintain compatibility with existing domain classes."""
    
    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.success = response.status_code < 400
        
    def json(self) -> Dict[str, Any]:
        """Return JSON data from response."""
        return self._response.json()
    
    def text(self) -> str:
        """Return text data from response."""
        return self._response.text
    
    @property
    def data(self) -> Dict[str, Any]:
        """Alias for json() to match expected interface."""
        return self.json()

class AlmaAPIError(Exception):
    """General Alma API error."""
    
    def __init__(self, message: str, status_code: int = None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class AlmaValidationError(ValueError):
    """Validation error for Alma API requests."""
    pass


class AlmaAPIClient:
    """
    General abstract gateway to the Alma API.
    
    This class provides:
    - Environment management (SANDBOX/PRODUCTION)
    - Core HTTP methods (GET, POST, PUT, DELETE)
    - Authentication handling
    - Connection testing
    - Foundation for pluggable domain-specific classes
    
    This class is designed to be inherited or composed by specific domain classes
    (BiblioGraphicRecords, Users, Admin, etc.)
    """
    
    def __init__(self, environment: str = 'SANDBOX'):
        """
        Initialize the API client.
        
        Args:
            environment: 'SANDBOX' or 'PRODUCTION'
        """
        self.environment = environment.upper()
        self._load_configuration()
        self._setup_headers()
        self._setup_logger() 

    def _setup_logger(self) -> None:
        """Setup comprehensive logger for API client."""
        self.logger = get_logger('api_client', environment=self.environment)


    def _load_configuration(self) -> None:
        """Load configuration based on environment."""
        if self.environment == 'SANDBOX':
            self.api_key = os.getenv('ALMA_SB_API_KEY')
            if not self.api_key:
                raise ValueError("ALMA_SB_API_KEY environment variable not set")
        elif self.environment == 'PRODUCTION':
            self.api_key = os.getenv('ALMA_PROD_API_KEY')
            if not self.api_key:
                raise ValueError("ALMA_PROD_API_KEY environment variable not set")
        else:
            raise ValueError("Environment must be 'SANDBOX' or 'PRODUCTION'")
        
        # Base URL (could be made configurable via env vars in the future)
        self.base_url = "https://api-eu.hosted.exlibrisgroup.com"
        
        print(f"✓ Configured for {self.environment} environment")
    
    def _setup_headers(self) -> None:
        """Setup default headers for API requests."""
        self.default_headers = {
            'Authorization': f'apikey {self.api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return f"{self.base_url}/{endpoint.lstrip('/')}"
    
    def _prepare_headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        """Prepare headers for request, optionally overriding content type."""
        headers = self.default_headers.copy()
        if content_type:
            headers['Content-Type'] = content_type
            if content_type == 'application/xml':
                headers['Accept'] = 'application/xml'
        return headers
    
    def _handle_response(self, response):
        """
        Handle response and convert to AlmaResponse for compatibility.
        
        Args:
            response: requests.Response object
            
        Returns:
            AlmaResponse object
            
        Raises:
            AlmaAPIError: If the response indicates an error
        """
        alma_response = AlmaResponse(response)
        
        if not alma_response.success:
            # Try to extract error message from response
            error_msg = f"HTTP {response.status_code}"
            try:
                if 'application/json' in response.headers.get('content-type', ''):
                    error_data = response.json()
                    if 'errorList' in error_data and 'error' in error_data['errorList']:
                        errors = error_data['errorList']['error']
                        if isinstance(errors, list) and errors:
                            error_msg = errors[0].get('errorMessage', error_msg)
                        elif isinstance(errors, dict):
                            error_msg = errors.get('errorMessage', error_msg)
                else:
                    error_msg = response.text[:200] if response.text else error_msg
            except:
                error_msg = response.text[:200] if response.text else error_msg
            
            raise AlmaAPIError(error_msg, response.status_code, response)
        
        return alma_response


    # Core HTTP Methods - These are the foundation for all API interactions
    
    def get(self, endpoint: str, params: Optional[Dict] = None,
            custom_headers: Optional[Dict] = None) -> AlmaResponse:
        """
        Make a GET request.

        Args:
            endpoint: API endpoint (e.g., 'almaws/v1/bibs/123456')
            params: Query parameters
            custom_headers: Additional headers

        Returns:
            AlmaResponse object
        """
        url = self._build_url(endpoint)
        headers = self._prepare_headers()
        if custom_headers:
            headers.update(custom_headers)

        # Log request
        self.logger.log_request('GET', endpoint, params=params, headers=headers)

        # Make request with timing
        start_time = time.time()
        response = requests.get(url, headers=headers, params=params)
        duration_ms = (time.time() - start_time) * 1000

        # Log response with body for successful requests
        try:
            response_body = response.json() if response.ok and 'application/json' in response.headers.get('content-type', '') else None
        except:
            response_body = None

        self.logger.log_response(response, duration_ms=duration_ms)

        # Log detailed response body for debugging
        if response_body:
            self.logger.debug(
                f"Response body from {endpoint}",
                endpoint=endpoint,
                status_code=response.status_code,
                response_data=response_body
            )

        return self._handle_response(response)
    
    def post(self, endpoint: str, data: Any = None, params: Optional[Dict] = None,
             content_type: Optional[str] = None,
             custom_headers: Optional[Dict] = None) -> requests.Response:
        """
        Make a POST request.

        Args:
            endpoint: API endpoint
            data: Request body (dict for JSON, str for XML)
            params: Query parameters
            content_type: Override content type ('application/xml', etc.)
            custom_headers: Additional headers

        Returns:
            AlmaResponse object
        """
        url = self._build_url(endpoint)
        headers = self._prepare_headers(content_type)
        if custom_headers:
            headers.update(custom_headers)

        # Log request with full body data
        self.logger.log_request('POST', endpoint, params=params, headers=headers, body=data)

        # Log detailed request body
        if isinstance(data, dict):
            self.logger.debug(
                f"POST request body to {endpoint}",
                endpoint=endpoint,
                request_data=data
            )

        # Make request with timing
        start_time = time.time()
        if isinstance(data, dict) and not content_type:
            # JSON data
            response = requests.post(url, headers=headers, json=data, params=params)
        else:
            # XML or other data
            response = requests.post(url, headers=headers, data=data, params=params)
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        self.logger.log_response(response, duration_ms=duration_ms)

        # Log detailed response body
        try:
            response_body = response.json() if 'application/json' in response.headers.get('content-type', '') else None
        except:
            response_body = None

        if response_body:
            self.logger.debug(
                f"POST response body from {endpoint}",
                endpoint=endpoint,
                status_code=response.status_code,
                response_data=response_body
            )

        return self._handle_response(response)
    
    def put(self, endpoint: str, data: Any = None, params: Optional[Dict] = None,
            content_type: Optional[str] = None,
            custom_headers: Optional[Dict] = None) -> AlmaResponse:
        """
        Make a PUT request.

        Args:
            endpoint: API endpoint
            data: Request body (dict for JSON, str for XML)
            params: Query parameters
            content_type: Override content type ('application/xml', etc.)
            custom_headers: Additional headers

        Returns:
            AlmaResponse object
        """
        url = self._build_url(endpoint)
        headers = self._prepare_headers(content_type)
        if custom_headers:
            headers.update(custom_headers)

        # Log request with full body data
        self.logger.log_request('PUT', endpoint, params=params, headers=headers, body=data)

        # Log detailed request body
        if isinstance(data, dict):
            self.logger.debug(
                f"PUT request body to {endpoint}",
                endpoint=endpoint,
                request_data=data
            )

        # Make request with timing
        start_time = time.time()
        if isinstance(data, dict) and not content_type:
            # JSON data
            response = requests.put(url, headers=headers, json=data, params=params)
        else:
            # XML or other data
            response = requests.put(url, headers=headers, data=data, params=params)
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        self.logger.log_response(response, duration_ms=duration_ms)

        # Log detailed response body
        try:
            response_body = response.json() if 'application/json' in response.headers.get('content-type', '') else None
        except:
            response_body = None

        if response_body:
            self.logger.debug(
                f"PUT response body from {endpoint}",
                endpoint=endpoint,
                status_code=response.status_code,
                response_data=response_body
            )

        return self._handle_response(response)
    
    def delete(self, endpoint: str, params: Optional[Dict] = None,
               custom_headers: Optional[Dict] = None)  -> AlmaResponse:
        """
        Make a DELETE request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            custom_headers: Additional headers

        Returns:
            AlmaResponse object
        """
        url = self._build_url(endpoint)
        headers = self._prepare_headers()
        if custom_headers:
            headers.update(custom_headers)

        # Log request
        self.logger.log_request('DELETE', endpoint, params=params, headers=headers)

        # Make request with timing
        start_time = time.time()
        response = requests.delete(url, headers=headers, params=params)
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        self.logger.log_response(response, duration_ms=duration_ms)

        return self._handle_response(response)
    
    def test_connection(self) -> bool:
        """
        Test if the API connection works.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self.get('almaws/v1/conf/libraries')
            success = response.status_code == 200
            if success:
                print(f"✓ Successfully connected to Alma API ({self.environment})")
            else:
                print(f"✗ Connection failed: {response.status_code} - {response.text}")
            return success
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
    
    def switch_environment(self, new_environment: str) -> None:
        """
        Switch between SANDBOX and PRODUCTION environments.
        
        Args:
            new_environment: 'SANDBOX' or 'PRODUCTION'
        """
        old_env = self.environment
        self.environment = new_environment.upper()
        try:
            self._load_configuration()
            self._setup_headers()
            print(f"✓ Switched from {old_env} to {self.environment}")
        except Exception as e:
            # Revert to old environment if switch fails
            self.environment = old_env
            self._load_configuration()
            self._setup_headers()
            raise e
    
    def get_environment(self) -> str:
        """Get current environment."""
        return self.environment
    
    def get_base_url(self) -> str:
        """Get base URL."""
        return self.base_url
    
    # Utility methods that domain classes can use
    
    def safe_request(self, method: str, endpoint: str, **kwargs) -> Union[Dict, str, None]:
        """
        Make a request and handle common errors gracefully.
        
        Args:
            method: HTTP method ('GET', 'POST', 'PUT', 'DELETE')
            endpoint: API endpoint
            **kwargs: Additional arguments for the request
            
        Returns:
            Parsed response data or None if error
        """
        try:
            method = method.upper()
            if method == 'GET':
                response = self.get(endpoint, **kwargs)
            elif method == 'POST':
                response = self.post(endpoint, **kwargs)
            elif method == 'PUT':
                response = self.put(endpoint, **kwargs)
            elif method == 'DELETE':
                response = self.delete(endpoint, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            
            # Try to return JSON, fall back to text
            try:
                return response.json()
            except:
                return response.text
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None








# Usage example and testing
if __name__ == "__main__":
    """
    Example usage of the AlmaAPIClient.
    This shows how the class works as a foundation.
    """
    try:
        # Initialize client
        client = AlmaAPIClient('PRODUCTION')  # or 'SANDBOX'
        
        # Test connection
        if client.test_connection():
            print("\n=== Basic API Test ===")
            
            # Example: Get libraries configuration
            response = client.get('almaws/v1/conf/libraries')
            if response.status_code == 200:
                libraries = response.json()
                print(f"Found {libraries['total_record_count']} libraries")
            
            # Example: Switch environment (if you have PROD key)
            print(f"\nCurrent environment: {client.get_environment()}")
            
        else:
            print("Cannot proceed - connection failed")
            
    except Exception as e:
        print(f"Setup error: {e}")
        print("\nMake sure you have set the environment variable:")
        print("export ALMA_SB_API_KEY='your_sandbox_api_key'")
