import requests
import json
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
from archived.config_manager import ConfigManager
from archived.logger_manager import LoggerManager


class AlmaAPIError(Exception):
    """Base exception for Alma API errors."""
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class AlmaRateLimitError(AlmaAPIError):
    """Exception raised when API rate limit is exceeded."""
    pass


class AlmaAuthenticationError(AlmaAPIError):
    """Exception raised when API authentication fails."""
    pass


class AlmaValidationError(AlmaAPIError):
    """Exception raised when request validation fails."""
    pass


class AlmaResponse:
    """Standardized response object for Alma API calls."""
    
    def __init__(self, data: Union[Dict, str], status_code: int, headers: Dict[str, str], 
                 request_url: str = None, request_method: str = None):
        self.data = data
        self.status_code = status_code
        self.headers = headers
        self.success = 200 <= status_code < 300
        self.request_url = request_url
        self.request_method = request_method
    
    def json(self) -> Dict[str, Any]:
        """Return response data as JSON."""
        if isinstance(self.data, str):
            return json.loads(self.data)
        return self.data
    
    def text(self) -> str:
        """Return response data as text."""
        if isinstance(self.data, dict):
            return json.dumps(self.data)
        return self.data


class BaseAPIClient:
    """
    Enhanced base API client for Alma ILS with rate limiting, retry logic, and proper error handling.
    """
    
    # API rate limits (requests per minute)
    DEFAULT_RATE_LIMIT = 100
    RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    
    def __init__(self, config_manager: ConfigManager, logger_manager: LoggerManager) -> None:
        self.config_manager = config_manager
        self.logger = logger_manager.get_logger()
        self.base_url = self.config_manager.get_base_url()
        self.headers = self.config_manager.get_headers()
        
        # Rate limiting setup
        self._request_times: List[float] = []
        self._rate_limit = self.DEFAULT_RATE_LIMIT
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate the configuration settings."""
        if not self.base_url:
            raise AlmaValidationError("Base URL is not configured")
        
        if not self.headers or 'authorization' not in self.headers:
            raise AlmaValidationError("API authorization headers are not configured")
        
        if not self.headers['authorization'].startswith('apikey '):
            raise AlmaValidationError("Invalid API key format")
    
    def _enforce_rate_limit(self) -> None:
        """Enforce API rate limiting."""
        now = time.time()
        
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        # Check if we're at the rate limit
        if len(self._request_times) >= self._rate_limit:
            sleep_time = 60 - (now - self._request_times[0])
            if sleep_time > 0:
                self.logger.warning(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
        
        # Record this request time
        self._request_times.append(now)
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        if endpoint.startswith('http'):
            return endpoint
        
        # Ensure proper URL joining
        base = self.base_url.rstrip('/')
        endpoint = endpoint.lstrip('/')
        return f"{base}/{endpoint}"
    
    def _prepare_headers(self, content_type: str = 'json', accept: str = 'json') -> Dict[str, str]:
        """Prepare headers for API request."""
        headers = self.headers.copy()
        
        # Set content type
        if content_type.lower() == 'xml':
            headers['Content-Type'] = 'application/xml;charset=utf-8'
        else:
            headers['Content-Type'] = 'application/json;charset=utf-8'
        
        # Set accept header
        if accept.lower() == 'xml':
            headers['Accept'] = 'application/xml'
        else:
            headers['Accept'] = 'application/json'
        
        return headers
    
    def _parse_response(self, response: requests.Response) -> Union[Dict, str]:
        """Parse API response based on content type."""
        content_type = response.headers.get('Content-Type', '').lower()
        
        if 'application/json' in content_type:
            try:
                return response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {e}")
                return response.text
        else:
            return response.text
    
    def _handle_error_response(self, response: requests.Response, request_method: str, url: str) -> None:
        """Handle API error responses with specific Alma error mapping."""
        status_code = response.status_code
        
        try:
            error_data = self._parse_response(response)
        except Exception:
            error_data = response.text
        
        error_message = f"{request_method} {url} failed with status {status_code}"
        
        # Extract Alma-specific error information
        if isinstance(error_data, dict):
            if 'errorList' in error_data:
                errors = error_data['errorList'].get('error', [])
                if errors:
                    error_details = errors[0] if isinstance(errors, list) else errors
                    error_message += f": {error_details.get('errorMessage', 'Unknown error')}"
            elif 'error_description' in error_data:
                error_message += f": {error_data['error_description']}"
        
        # Map to specific exception types
        if status_code == 401:
            raise AlmaAuthenticationError(error_message, status_code, error_data)
        elif status_code == 429:
            raise AlmaRateLimitError(error_message, status_code, error_data)
        elif status_code in [400, 422]:
            raise AlmaValidationError(error_message, status_code, error_data)
        else:
            raise AlmaAPIError(error_message, status_code, error_data)
    
    def _make_request(self, method: str, url: str, headers: Dict[str, str], 
                     data: Any = None, params: Dict[str, str] = None, 
                     retry_count: int = 0) -> AlmaResponse:
        """Make HTTP request with retry logic."""
        self._enforce_rate_limit()
        
        try:
            self.logger.info(f"Making {method} request to {url}")
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == 'POST':
                if isinstance(data, dict):
                    response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
                else:
                    response = requests.post(url, headers=headers, data=data, params=params, timeout=30)
            elif method.upper() == 'PUT':
                if isinstance(data, dict):
                    response = requests.put(url, headers=headers, json=data, params=params, timeout=30)
                else:
                    response = requests.put(url, headers=headers, data=data, params=params, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=30)
            else:
                raise AlmaValidationError(f"Unsupported HTTP method: {method}")
            
            self.logger.info(f"Response status: {response.status_code}")
            
            # Handle error responses
            if not response.ok:
                # Retry on specific status codes
                if (response.status_code in self.RETRY_STATUS_CODES and 
                    retry_count < self.MAX_RETRIES):
                    
                    delay = self.RETRY_DELAY * (2 ** retry_count)  # Exponential backoff
                    self.logger.warning(f"Request failed with {response.status_code}, "
                                      f"retrying in {delay} seconds (attempt {retry_count + 1})")
                    time.sleep(delay)
                    return self._make_request(method, url, headers, data, params, retry_count + 1)
                
                self._handle_error_response(response, method, url)
            
            # Parse and return successful response
            parsed_data = self._parse_response(response)
            return AlmaResponse(
                data=parsed_data,
                status_code=response.status_code,
                headers=dict(response.headers),
                request_url=url,
                request_method=method
            )
            
        except requests.RequestException as e:
            self.logger.error(f"{method} request to {url} failed: {e}")
            raise AlmaAPIError(f"Network error: {str(e)}")
    
    def get(self, endpoint: str, params: Optional[Dict[str, str]] = None, 
            accept: str = 'json') -> AlmaResponse:
        """Make a GET request to the specified endpoint."""
        url = self._build_url(endpoint)
        headers = self._prepare_headers(accept=accept)
        return self._make_request('GET', url, headers, params=params)
    
    def post(self, endpoint: str, data: Any, content_type: str = 'json',
             accept: str = 'json', params: Optional[Dict[str, str]] = None) -> AlmaResponse:
        """Make a POST request to the specified endpoint."""
        url = self._build_url(endpoint)
        headers = self._prepare_headers(content_type=content_type, accept=accept)
        return self._make_request('POST', url, headers, data=data, params=params)
    
    def put(self, endpoint: str, data: Any, content_type: str = 'json',
            accept: str = 'json', params: Optional[Dict[str, str]] = None) -> AlmaResponse:
        """Make a PUT request to the specified endpoint."""
        url = self._build_url(endpoint)
        headers = self._prepare_headers(content_type=content_type, accept=accept)
        return self._make_request('PUT', url, headers, data=data, params=params)
    
    def delete(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> AlmaResponse:
        """Make a DELETE request to the specified endpoint."""
        url = self._build_url(endpoint)
        headers = self._prepare_headers()
        return self._make_request('DELETE', url, headers, params=params)
    
    def test_connection(self) -> bool:
        """Test API connection and authentication."""
        try:
            # Use a simple endpoint to test connectivity
            response = self.get('almaws/v1/conf/institutions')
            return response.success
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False