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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from almaapitk.alma_logging import get_logger


# Default per-request timeout (seconds) for Alma API calls. Lowered from
# the previous 300s in issue #6: a 5-minute hang on a single request would
# stall scripts and CI runs long after the underlying call had clearly
# stopped making progress. 60s is a safer default for the typical Alma
# verb; long-running endpoints (paged jobs, exports) can opt back into a
# higher value via the ``timeout=`` constructor kwarg or the per-call
# ``_request(..., timeout=...)`` override.
DEFAULT_REQUEST_TIMEOUT = 60

# Default retry configuration for the urllib3-backed HTTPAdapter mounted
# on the persistent session (issue #5). The status forcelist covers Alma's
# rate-limit response (429) and the transient-server-error band (5xx) that
# is safe to retry idempotently.
DEFAULT_RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)
DEFAULT_RETRY_TOTAL = 3
DEFAULT_RETRY_BACKOFF_FACTOR = 1.0
DEFAULT_RETRY_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "DELETE"})


def _safe_response_body(response):
    """Best-effort JSON body extraction from a ``requests.Response``.

    Returns the parsed JSON body when the response advertises a JSON
    content-type and decodes cleanly, otherwise ``None``. This replaces
    the four near-identical ``try: response.json() except: None`` blocks
    that previously lived in each verb method (issue #4).

    Args:
        response: A ``requests.Response`` (or compatible test double).

    Returns:
        Parsed JSON body, or ``None`` if no JSON body is available.
    """
    content_type = ''
    try:
        content_type = response.headers.get('content-type', '') or ''
    except AttributeError:
        # Defensive: some test doubles may omit ``headers``.
        return None
    if 'application/json' not in content_type:
        return None
    try:
        return response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        return None


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
    
    def __init__(
        self,
        environment: str = 'SANDBOX',
        *,
        max_retries: int = DEFAULT_RETRY_TOTAL,
        backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        retry: Optional[Retry] = None,
        timeout: Optional[float] = None,
    ):
        """Initialize the API client.

        Args:
            environment: 'SANDBOX' or 'PRODUCTION'.
            max_retries: Total number of retries the mounted HTTPAdapter
                should attempt on retryable responses (429 and 5xx).
                Must be an ``int >= 0``. Ignored when ``retry`` is given.
            backoff_factor: Exponential backoff multiplier passed to
                ``urllib3.util.Retry``. With ``backoff_factor=1`` the wait
                schedule between attempts is roughly 1s, 2s, 4s, ...
                Must be a non-negative number. Ignored when ``retry`` is
                given.
            retry: Optional fully-built ``urllib3.util.Retry`` instance.
                When supplied, it is used verbatim and ``max_retries`` /
                ``backoff_factor`` are ignored — this is the escape hatch
                for advanced callers who need to tune fields not exposed
                by the simple kwargs (allowed_methods, raise_on_status,
                etc.).
            timeout: Default per-request timeout in seconds. ``None``
                falls back to ``DEFAULT_REQUEST_TIMEOUT`` (60s). Must be
                a positive number when supplied. Per-call
                ``_request(..., timeout=...)`` overrides this on a
                request-by-request basis.

        Raises:
            AlmaValidationError: If ``max_retries`` is negative or not an
                int, if ``backoff_factor`` is negative or not numeric,
                or if ``timeout`` is non-positive or non-numeric.

        Pattern source: GitHub issue #5 (HTTP: retry with exponential
        backoff for 429/5xx) and issue #6 (HTTP: make timeout
        configurable; lower default from 300s to 60s).
        """
        self.environment = environment.upper()
        # Default per-request timeout. Per-call ``timeout=`` kwargs in
        # ``_request`` override this on a request-by-request basis. The
        # constructor kwarg lets callers opt into a longer ceiling for
        # workloads dominated by paged/long-running endpoints.
        self._validate_timeout(timeout)
        self.timeout = (
            timeout if timeout is not None else DEFAULT_REQUEST_TIMEOUT
        )
        # Validate retry knobs early so misconfiguration surfaces at
        # construction time rather than on the first network failure.
        if retry is None:
            self._validate_retry_kwargs(max_retries, backoff_factor)
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._retry_override = retry
        self._load_configuration()
        self._setup_headers()
        self._setup_logger()
        self._setup_session()

    @staticmethod
    def _validate_retry_kwargs(max_retries: Any, backoff_factor: Any) -> None:
        """Validate the simple retry kwargs accepted by ``__init__``.

        Args:
            max_retries: Candidate value for the ``max_retries`` kwarg.
            backoff_factor: Candidate value for the ``backoff_factor``
                kwarg.

        Raises:
            AlmaValidationError: If either value falls outside its
                allowed domain.
        """
        # ``bool`` is a subclass of ``int`` in Python -- callers passing
        # ``True``/``False`` almost certainly mean to enable/disable the
        # feature, not to set a numeric retry count. Reject explicitly.
        if isinstance(max_retries, bool) or not isinstance(max_retries, int):
            raise AlmaValidationError(
                f"max_retries must be an int >= 0, got {type(max_retries).__name__}"
            )
        if max_retries < 0:
            raise AlmaValidationError(
                f"max_retries must be >= 0, got {max_retries}"
            )
        if isinstance(backoff_factor, bool) or not isinstance(
            backoff_factor, (int, float)
        ):
            raise AlmaValidationError(
                "backoff_factor must be a non-negative number, "
                f"got {type(backoff_factor).__name__}"
            )
        if backoff_factor < 0:
            raise AlmaValidationError(
                f"backoff_factor must be >= 0, got {backoff_factor}"
            )

    @staticmethod
    def _validate_timeout(timeout: Any) -> None:
        """Validate the ``timeout`` constructor kwarg.

        ``None`` is allowed and means "fall back to the module default".
        Anything else must be a positive ``int`` or ``float``. ``bool``
        is a subclass of ``int`` in Python -- callers passing
        ``True``/``False`` almost certainly mean to enable/disable the
        feature, not to set a numeric timeout, so it is rejected
        explicitly.

        Args:
            timeout: Candidate value for the ``timeout`` kwarg.

        Raises:
            AlmaValidationError: If ``timeout`` is not ``None`` and is
                not a positive ``int``/``float`` (excluding ``bool``).
        """
        if timeout is None:
            return
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise AlmaValidationError(
                "timeout must be a positive number or None, "
                f"got {type(timeout).__name__}"
            )
        if timeout <= 0:
            raise AlmaValidationError(
                f"timeout must be > 0, got {timeout}"
            )

    @staticmethod
    def _build_retry(max_retries: int, backoff_factor: float) -> Retry:
        """Construct the default ``urllib3.util.Retry`` policy.

        Args:
            max_retries: Total number of retry attempts.
            backoff_factor: Exponential backoff multiplier.

        Returns:
            A configured ``Retry`` instance with the project defaults
            applied (status forcelist, allowed methods, Retry-After
            header respected).
        """
        return Retry(
            total=max_retries,
            status_forcelist=list(DEFAULT_RETRY_STATUS_FORCELIST),
            backoff_factor=backoff_factor,
            allowed_methods=DEFAULT_RETRY_ALLOWED_METHODS,
            respect_retry_after_header=True,
        )

    def _setup_logger(self) -> None:
        """Setup comprehensive logger for API client."""
        self.logger = get_logger('api_client', environment=self.environment)

    def _setup_session(self) -> None:
        """Create a persistent ``requests.Session`` for connection pooling.

        Holding a single session for the lifetime of the client lets the
        underlying ``urllib3`` connection pool reuse TCP+TLS connections
        across calls instead of paying a fresh handshake per request. It
        also gives downstream improvements (retry adapters, rate limiting,
        context-manager support) a single mount point.

        Mounts an ``HTTPAdapter`` with a ``urllib3.util.Retry`` policy so
        transient 429/5xx responses from Alma are retried with
        exponential backoff and ``Retry-After`` header awareness — long
        paged jobs no longer have to be re-run from scratch when a single
        intermediate response trips the rate limiter (issue #5).

        Pattern source: GitHub issue #3 (HTTP: persistent requests.Session)
        and issue #5 (HTTP: add retry with exponential backoff for
        429/5xx).
        """
        self._session = requests.Session()
        # Default headers live on the session; per-call ``custom_headers``
        # still wins via the per-call ``headers=`` kwarg passed to
        # ``self._session.request(...)``.
        self._session.headers.update(self.default_headers)

        # Mount the retry-aware HTTPAdapter on both schemes. ``http://``
        # is included for completeness even though Alma's public API is
        # HTTPS-only -- a misconfigured base URL or a future on-prem
        # variant should still benefit from the same retry policy.
        retry_policy = (
            self._retry_override
            if self._retry_override is not None
            else self._build_retry(self._max_retries, self._backoff_factor)
        )
        adapter = HTTPAdapter(max_retries=retry_policy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)


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

    def _request(self, method: str, endpoint: str, *,
                 params: Optional[Dict] = None,
                 data: Any = None,
                 content_type: Optional[str] = None,
                 custom_headers: Optional[Dict] = None,
                 timeout: Optional[float] = None) -> AlmaResponse:
        """
        Single chokepoint for all HTTP requests to the Alma API.

        Replaces the near-duplicate bodies of ``get``/``post``/``put``/``delete``
        so cross-cutting concerns (timeout, retry, rate-limit, body redaction,
        header injection) live in one place. Per the proposal in issue #4,
        this is the only method in the client that should call
        ``self._session.request``.

        Args:
            method: HTTP verb ('GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint (e.g., 'almaws/v1/bibs/123456').
            params: Query parameters.
            data: Request body. ``dict`` is sent as JSON unless
                ``content_type`` overrides; any other type goes via ``data=``.
            content_type: Override Content-Type (e.g., 'application/xml').
                When set, ``data`` is sent verbatim via the ``data=`` kwarg
                regardless of its Python type.
            custom_headers: Additional/overriding per-call headers.
            timeout: Override the default per-request timeout (seconds).
                When ``None``, ``self.timeout`` is used.

        Returns:
            AlmaResponse wrapping the underlying ``requests.Response``.

        Raises:
            AlmaAPIError: When ``_handle_response`` rejects the response.

        Pattern source: GitHub issue #4 (HTTP: consolidate verbs into _request).
        """
        url = self._build_url(endpoint)
        headers = self._prepare_headers(content_type)
        if custom_headers:
            headers.update(custom_headers)

        # Log the outgoing request. Body is included only when present so
        # the logger's redaction layer can decide what to scrub.
        self.logger.log_request(
            method, endpoint, params=params, headers=headers, body=data
        )

        # Detailed request body trace (DEBUG only). Mirrors the previous
        # per-verb behaviour so log volume is unchanged.
        if isinstance(data, dict) and not content_type:
            self.logger.debug(
                f"{method} request body to {endpoint}",
                endpoint=endpoint,
                request_data=data,
            )

        # Build the kwargs for ``Session.request``. Dict bodies without an
        # explicit content_type go via ``json=`` so requests sets the
        # Content-Type to application/json correctly; everything else goes
        # via ``data=``. This preserves the prior per-verb dispatch.
        request_kwargs: Dict[str, Any] = {
            'headers': headers,
            'params': params,
            'timeout': timeout if timeout is not None else self.timeout,
        }
        if isinstance(data, dict) and not content_type:
            request_kwargs['json'] = data
        elif data is not None:
            request_kwargs['data'] = data

        # Route through self._session so TCP+TLS connections are pooled
        # across calls (issue #3).
        start_time = time.time()
        response = self._session.request(method, url, **request_kwargs)
        duration_ms = (time.time() - start_time) * 1000

        # Log the response (status + timing). The detailed body trace below
        # is DEBUG-only and gated on a successful JSON parse.
        self.logger.log_response(response, duration_ms=duration_ms)

        response_body = _safe_response_body(response)
        if response_body:
            self.logger.debug(
                f"{method} response body from {endpoint}",
                endpoint=endpoint,
                status_code=response.status_code,
                response_data=response_body,
            )

        return self._handle_response(response)

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
        return self._request(
            'GET', endpoint, params=params, custom_headers=custom_headers
        )

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
        return self._request(
            'POST', endpoint,
            params=params, data=data,
            content_type=content_type, custom_headers=custom_headers,
        )

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
        return self._request(
            'PUT', endpoint,
            params=params, data=data,
            content_type=content_type, custom_headers=custom_headers,
        )

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
        return self._request(
            'DELETE', endpoint,
            params=params, custom_headers=custom_headers,
        )
    
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
            # Keep the session's headers in sync with the new environment
            # so the persistent session sends the correct apikey going
            # forward (issue #3).
            if hasattr(self, '_session') and self._session is not None:
                self._session.headers.update(self.default_headers)
            print(f"✓ Switched from {old_env} to {self.environment}")
        except Exception as e:
            # Revert to old environment if switch fails
            self.environment = old_env
            self._load_configuration()
            self._setup_headers()
            if hasattr(self, '_session') and self._session is not None:
                self._session.headers.update(self.default_headers)
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
