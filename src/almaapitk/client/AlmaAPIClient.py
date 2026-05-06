"""
AlmaAPIClient - General Abstract Gateway to Alma API
A foundational class that serves as the base for all Alma API interactions.
This is designed to be 'pluggable' - other classes will use this as their foundation.
"""
import os
import sys
import requests
import json
from typing import Optional, Dict, Any, Iterator
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


# Mapping of Alma hosting regions to their public API base URLs.
#
# Historically the client hardcoded the EU host, which silently broke
# every non-European Alma tenant. Issue #7 lifts the host into a kwarg,
# defaulting to ``"EU"`` so existing callers see no behavioural change.
#
# Notes:
# - Asia Pacific is split between Singapore (``AP``) and Australia
#   (``APS``); Ex Libris exposes them as separate hostnames.
# - China uses the ``.com.cn`` TLD (NOT ``.com``). The original issue
#   body had a typo here; the audit-fixed mapping below is the
#   ground-truth one tested in ``test_cn_uses_com_cn_tld``.
# - Advanced callers can sidestep this dict entirely by passing the
#   ``host=`` kwarg with an arbitrary base URL (useful for staging/proxy
#   deployments and on-prem mirrors).
REGION_HOSTS: Dict[str, str] = {
    "EU":  "https://api-eu.hosted.exlibrisgroup.com",
    "NA":  "https://api-na.hosted.exlibrisgroup.com",
    "AP":  "https://api-ap.hosted.exlibrisgroup.com",       # Asia Pacific (Singapore)
    "APS": "https://api-aps.hosted.exlibrisgroup.com",      # Asia Pacific (Australia)
    "CA":  "https://api-ca.hosted.exlibrisgroup.com",
    "CN":  "https://api-cn.hosted.exlibrisgroup.com.cn",    # China -- note .com.cn TLD
}
DEFAULT_REGION = "EU"


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


_UNSET = object()  # Sentinel for "body not yet parsed" (issue #16).


class AlmaResponse:
    """Response wrapper to maintain compatibility with existing domain classes.

    The parsed JSON body is cached on first access (issue #16): ``.data``
    and ``.json()`` and the client's debug-body-logging path all share a
    single ``response.json()`` call. Repeated access — common in idioms
    like ``if r.data and r.data.get("foo"):`` — no longer re-parses the
    body on every read, which is measurable on large analytics payloads.
    """

    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.success = response.status_code < 400
        # Sentinel-based cache: ``None`` is a legitimate parsed body
        # value (e.g. content-type is non-JSON, or the body is empty), so
        # we cannot use ``None`` itself as the "not yet parsed" marker.
        self._cached_body: Any = _UNSET

    def _safe_body(self) -> Any:
        """Best-effort cached body access for non-raising callers.

        Returns the cached parsed body if one is already populated.
        Otherwise attempts to parse the body via ``self._response.json``
        and caches the result; on any decode failure returns ``None``
        without populating the cache, so a later strict ``.json()``
        call still surfaces the malformed-JSON exception.

        Used by the client's debug-body-logging path (where a malformed
        body should never crash the request) and by error-field
        extraction. ``data`` and ``json()`` share the same
        ``_cached_body`` slot so that on a successful parse all three
        paths reuse one parsed object (issue #16).

        Returns:
            Parsed JSON body, or ``None`` when the response is not JSON
            or cannot be decoded.
        """
        if self._cached_body is not _UNSET:
            return self._cached_body
        # Reuse the module-level helper so the content-type / decode
        # logic lives in exactly one place. The helper never raises and
        # never calls ``response.json()`` for non-JSON content-types,
        # which keeps this safe for the debug-logging caller.
        body = _safe_response_body(self._response)
        # Only cache successful parses. A ``None`` result either means
        # "not JSON content-type" (cheap to recompute) or "malformed
        # JSON" (we want a later ``.json()`` to still raise rather than
        # silently return ``None`` from cache).
        if body is not None:
            self._cached_body = body
        return body

    def json(self) -> Dict[str, Any]:
        """Return the parsed JSON body of the response.

        Cached on first successful parse; subsequent calls return the
        cached value without touching ``self._response.json()`` again
        (issue #16). Exception behaviour matches the pre-#16 contract
        -- callers that previously got a ``ValueError`` on a malformed
        body still do.

        Returns:
            Parsed JSON body of the response.

        Raises:
            ValueError: When the response body is not valid JSON.
        """
        if self._cached_body is _UNSET:
            # ``self._response.json()`` raises ``ValueError`` (or its
            # ``requests.exceptions.JSONDecodeError`` subclass) on
            # malformed bodies; let that propagate so existing callers
            # see the same exception shape they used to.
            self._cached_body = self._response.json()
        return self._cached_body

    def text(self) -> str:
        """Return text data from response."""
        return self._response.text

    @property
    def data(self) -> Dict[str, Any]:
        """Cached parsed JSON body (alias for ``json()``).

        First access parses; subsequent accesses return the cached
        object, so idioms like ``if r.data and r.data.get('x'):`` only
        pay the parse cost once (issue #16). Shares its cache with
        ``json()`` and the internal ``_safe_body()`` debug-logging
        path -- ``self._response.json()`` is called at most once per
        response across all three.

        Returns:
            Parsed JSON body of the response.

        Raises:
            ValueError: When the response body is not valid JSON.
        """
        return self.json()

class AlmaAPIError(Exception):
    """General Alma API error.

    Carries the HTTP status, the underlying ``requests.Response``, and --
    when the failing response body included an Alma ``errorList`` payload --
    the per-error ``trackingId`` and ``errorCode`` Ex Libris support uses
    to investigate cases (issue #10). Both fields default to safe
    sentinels (``None`` / ``""``) so call sites that construct exceptions
    without a parsed body (tests, the typed-subclass constructors, the
    legacy ``(message, status_code, response)`` positional path used
    pre-#10) keep working unchanged.

    Attributes:
        status_code: HTTP status code of the failing response, or ``None``
            for synthetic errors raised outside the response handler.
        response: The underlying ``requests.Response`` (or test double).
        tracking_id: The ``trackingId`` field from
            ``errorList.error[0]``. ``None`` when the body had no
            ``errorList`` or no trackingId entry.
        alma_code: The ``errorCode`` field from ``errorList.error[0]``,
            normalised to ``str``. Empty string when no code was present
            -- chosen over ``None`` so log formatters can interpolate it
            without a falsy guard.
    """

    def __init__(
        self,
        message: str,
        status_code: int = None,
        response=None,
        tracking_id: Optional[str] = None,
        alma_code: str = "",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.tracking_id = tracking_id
        self.alma_code = alma_code

class AlmaValidationError(ValueError):
    """Validation error for Alma API requests."""
    pass


# -----------------------------------------------------------------------------
# Typed AlmaAPIError subclasses (issue #9)
#
# These specialise ``AlmaAPIError`` so domain code can branch on exception
# *type* instead of inspecting error message strings or status codes inline.
# Every subclass keeps the same ``(message, status_code, response)``
# constructor signature as ``AlmaAPIError`` so existing
# ``except AlmaAPIError:`` blocks continue to catch them transparently.
# -----------------------------------------------------------------------------

class AlmaAuthenticationError(AlmaAPIError):
    """API authentication failed (HTTP 401)."""
    pass


class AlmaRateLimitError(AlmaAPIError):
    """Alma API rate limit exceeded (HTTP 429)."""
    pass


class AlmaServerError(AlmaAPIError):
    """Alma server-side error (HTTP 5xx)."""
    pass


class AlmaResourceNotFoundError(AlmaAPIError):
    """Requested Alma resource was not found (HTTP 404)."""
    pass


class AlmaDuplicateInvoiceError(AlmaAPIError):
    """Invoice already exists for the given vendor (Alma error code 402459)."""
    pass


class AlmaInvalidPolModeError(AlmaAPIError):
    """POL is not in the right mode for the requested operation (Alma error code 40166411)."""
    pass


# Mapping of Alma-specific error codes to typed exception subclasses.
# When the Alma response payload carries an ``errorList.error[].errorCode``
# entry that lives in this registry, ``_classify_error`` routes the raised
# exception to the mapped class. HTTP-status fallbacks (401, 404, 429, 5xx)
# are handled separately in ``_classify_error`` itself.
#
# Pattern source: GitHub issue #9 (errors: map Alma error codes to
# specific exception subclasses).
ERROR_CODE_REGISTRY: Dict[str, type] = {
    "402459":   AlmaDuplicateInvoiceError,
    "40166411": AlmaInvalidPolModeError,
    # Alma returns HTTP 400 + errorCode 401861 ("User with identifier ... was not
    # found") for a missing user_primary_id — NOT HTTP 404 — so status-fallback
    # never fires. Map the code explicitly. Discovered via SANDBOX smoke test
    # t-9-1 (chunk errors-mapping, 2026-05-04).
    "401861":   AlmaResourceNotFoundError,
    # Issue #90 swagger backfill (users domain). Alma returns HTTP 400 +
    # errorCode 60224 ("Organization institution not found") for GET/POST
    # /almaws/v1/users when the requested organization institution does not
    # exist. Documented in the Ex Libris users.json swagger; mapped here as
    # the proof-of-concept that swagger-driven harvesting (issue #90) can
    # replace ad-hoc registry growth.
    "60224":    AlmaResourceNotFoundError,
}


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
        region: str = DEFAULT_REGION,
        host: Optional[str] = None,
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
            region: Alma hosting region key. Must be one of the keys in
                ``REGION_HOSTS`` (``EU``, ``NA``, ``AP``, ``APS``, ``CA``,
                ``CN``). Defaults to ``"EU"`` for backward compatibility
                with all pre-#7 callers. Ignored when ``host`` is set.
            host: Override the resolved base URL with an arbitrary
                string. When non-``None`` this beats ``region`` entirely
                — useful for staging proxies, on-prem mirrors, and
                tests. The value is stored verbatim on
                ``self.base_url``.

        Raises:
            AlmaValidationError: If ``max_retries`` is negative or not an
                int, if ``backoff_factor`` is negative or not numeric,
                if ``timeout`` is non-positive or non-numeric, or if
                ``region`` is not a known key and ``host`` is not given.

        Pattern source: GitHub issue #5 (HTTP: retry with exponential
        backoff for 429/5xx), issue #6 (HTTP: make timeout configurable;
        lower default from 300s to 60s), and issue #7 (HTTP: make
        region/host configurable).
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
        # Region/host are stashed before ``_load_configuration`` so the
        # base-URL resolver can pick them up (issue #7). ``switch_environment``
        # also re-runs ``_load_configuration`` and must therefore see the
        # same values on ``self``.
        self._region = region
        self._host_override = host
        # Logger is set up first so ``_load_configuration`` can use
        # ``self.logger`` instead of ``print()``. Only ``self.environment``
        # (set above) is required for logger setup.
        self._setup_logger()
        self._load_configuration()
        self._setup_headers()
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
        """Load configuration based on environment.

        Resolves ``self.api_key`` from ``ALMA_SB_API_KEY`` /
        ``ALMA_PROD_API_KEY`` and ``self.base_url`` from either an
        explicit ``host`` override or a ``region`` lookup against
        ``REGION_HOSTS`` (issue #7).

        Raises:
            ValueError: If the environment-specific API key env var is
                not set, or if ``environment`` is not SANDBOX/PRODUCTION.
            AlmaValidationError: If ``region`` is not a known
                ``REGION_HOSTS`` key and no ``host`` override was given.
        """
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

        # Base URL resolution (issue #7):
        # - ``host`` (when set) wins outright; advanced callers passing
        #   their own URL (staging proxies, on-prem mirrors, tests) get
        #   exactly what they asked for, with no further validation
        #   beyond it being non-None.
        # - Otherwise look up ``region`` in ``REGION_HOSTS``. An unknown
        #   key is surfaced as ``AlmaValidationError`` with a list of the
        #   accepted keys so the user can self-correct.
        if self._host_override is not None:
            self.base_url = self._host_override
        else:
            if self._region not in REGION_HOSTS:
                raise AlmaValidationError(
                    f"Unknown region {self._region!r}. "
                    f"Valid regions: {sorted(REGION_HOSTS.keys())}. "
                    "Pass host='<full-url>' to bypass region lookup."
                )
            self.base_url = REGION_HOSTS[self._region]

        self.logger.info(f"Configured for {self.environment} environment")
    
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
    
    def _classify_error(
        self, status_code: int, alma_code: Optional[str]
    ) -> type:
        """Pick the most specific ``AlmaAPIError`` subclass for an error.

        Resolution order:

        1. If ``alma_code`` is in ``ERROR_CODE_REGISTRY``, return the mapped
           subclass — Alma error codes are more specific than HTTP status
           and should always win when both are available.
        2. Otherwise, dispatch by HTTP ``status_code``:

           - ``401`` -> ``AlmaAuthenticationError``
           - ``404`` -> ``AlmaResourceNotFoundError``
           - ``429`` -> ``AlmaRateLimitError``
           - ``5xx`` -> ``AlmaServerError``
           - anything else -> bare ``AlmaAPIError``

        Args:
            status_code: HTTP status code of the failing response.
            alma_code: Alma-specific error code extracted from the
                response body's ``errorList.error[0].errorCode``, or
                ``None`` if no such code was present.

        Returns:
            The most specific ``AlmaAPIError`` subclass to raise.

        Pattern source: GitHub issue #9.
        """
        if alma_code is not None and alma_code in ERROR_CODE_REGISTRY:
            return ERROR_CODE_REGISTRY[alma_code]

        if status_code == 401:
            return AlmaAuthenticationError
        if status_code == 404:
            return AlmaResourceNotFoundError
        if status_code == 429:
            return AlmaRateLimitError
        if 500 <= status_code < 600:
            return AlmaServerError
        return AlmaAPIError

    @staticmethod
    def _extract_alma_error_fields(response_or_wrapper):
        """Pull ``(error_msg, alma_code, tracking_id)`` from an error response.

        Centralises the JSON-body / ``errorList.error[0]`` traversal that
        used to live inline in ``_handle_response``. Splitting it out lets
        ``_handle_response`` stay readable and gives the parsing logic a
        single, unit-testable home.

        Accepts either a raw ``requests.Response`` (legacy direct callers,
        tests) or an ``AlmaResponse`` wrapper. When an ``AlmaResponse`` is
        passed, the cached body is reused so ``response.json()`` is not
        called a second time on the error path -- this preserves the
        "parse at most once per response" contract from issue #16.

        Returns:
            Tuple of ``(error_msg, alma_code, tracking_id)``:

            - ``error_msg``: human-readable message; falls back to
              ``"HTTP <status>"`` when no message can be extracted.
            - ``alma_code``: ``str`` form of ``errorList.error[0].errorCode``,
              or ``None`` when no recognisable code is present. Always
              normalised to ``str`` so ``ERROR_CODE_REGISTRY`` lookups
              don't hinge on whether Alma returned a number or a string.
            - ``tracking_id``: ``trackingId`` value from the same payload,
              or ``None``. Ex Libris support uses this to look up the
              individual server-side request when investigating a case
              (issue #10).

        The parsing is best-effort: any exception while traversing the
        body collapses to ``(error_msg-from-text, None, None)`` so that a
        malformed response can never mask the original API error.
        """
        if isinstance(response_or_wrapper, AlmaResponse):
            wrapper = response_or_wrapper
            response = wrapper._response
            error_data = wrapper._safe_body()
        else:
            wrapper = None
            response = response_or_wrapper
            error_data = _safe_response_body(response)

        error_msg = f"HTTP {response.status_code}"
        alma_code: Optional[str] = None
        tracking_id: Optional[str] = None
        try:
            if isinstance(error_data, dict):
                if 'errorList' in error_data and 'error' in error_data['errorList']:
                    errors = error_data['errorList']['error']
                    if isinstance(errors, list) and errors:
                        first_error = errors[0]
                    elif isinstance(errors, dict):
                        first_error = errors
                    else:
                        first_error = None
                    if isinstance(first_error, dict):
                        error_msg = first_error.get('errorMessage', error_msg)
                        raw_code = first_error.get('errorCode')
                        # Alma sometimes returns numeric codes; normalise
                        # to ``str`` so registry lookups are uniform.
                        if raw_code is not None:
                            alma_code = str(raw_code)
                        # ``trackingId`` is opaque -- keep it verbatim so
                        # operators can quote it back to Ex Libris support.
                        raw_tracking = first_error.get('trackingId')
                        if raw_tracking is not None:
                            tracking_id = raw_tracking
            else:
                # Non-JSON or empty body -- fall back to text.
                error_msg = response.text[:200] if response.text else error_msg
        except (KeyError, AttributeError, TypeError, IndexError):
            # Defensive: never let response-parsing errors mask the
            # original API error. Narrow-to-traversal errors only --
            # ``KeyboardInterrupt`` and ``SystemExit`` must still
            # propagate (issue #16).
            error_msg = response.text[:200] if response.text else error_msg

        return error_msg, alma_code, tracking_id

    def _handle_response(self, response_or_wrapper):
        """
        Handle response and convert to AlmaResponse for compatibility.

        Accepts either a raw ``requests.Response`` (legacy callers) or an
        already-built ``AlmaResponse`` (the new ``_request`` path, which
        creates the wrapper up front so the JSON body is parsed at most
        once across the success / error / debug-logging paths -- issue
        #16).

        Args:
            response_or_wrapper: ``requests.Response`` or ``AlmaResponse``.

        Returns:
            AlmaResponse object.

        Raises:
            AlmaAPIError: If the response indicates an error. The actual
                exception class raised is selected by ``_classify_error``
                based on Alma error code (when present) or HTTP status,
                so callers can branch on type via ``except`` clauses
                without parsing message strings (issue #9). The raised
                exception also carries ``tracking_id`` and ``alma_code``
                attributes extracted from the same ``errorList.error[0]``
                payload so log lines and operator hand-offs to Ex Libris
                support can quote the per-request trackingId (issue #10).
        """
        if isinstance(response_or_wrapper, AlmaResponse):
            alma_response = response_or_wrapper
        else:
            alma_response = AlmaResponse(response_or_wrapper)

        if not alma_response.success:
            error_msg, alma_code, tracking_id = self._extract_alma_error_fields(
                alma_response
            )
            exc_class = self._classify_error(
                alma_response.status_code, alma_code
            )
            # ``alma_code`` is normalised to "" on the exception (the
            # default in ``AlmaAPIError.__init__``) so log formatters can
            # interpolate it without a None-guard. ``tracking_id`` stays
            # ``None`` when missing because there's no sensible empty
            # tracking value to hand to support.
            raise exc_class(
                error_msg,
                alma_response.status_code,
                alma_response._response,
                tracking_id=tracking_id,
                alma_code=alma_code if alma_code is not None else "",
            )

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
        # Issue #13: refuse to issue HTTP after ``close()`` has run. A
        # ``None`` session is the documented sentinel for "this client
        # has been closed"; we surface this as a clear ``AlmaAPIError``
        # rather than letting an ``AttributeError`` bubble out of the
        # session call below.
        if getattr(self, "_session", None) is None:
            raise AlmaAPIError(
                "AlmaAPIClient has been closed; construct a new client "
                "instance to make further API calls."
            )

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

        # Build the AlmaResponse up front so the JSON body is parsed at
        # most once across the debug-logging, success, and error paths
        # (issue #16). All three paths read through ``_safe_body()``,
        # which caches on first call.
        alma_response = AlmaResponse(response)

        response_body = alma_response._safe_body()
        if response_body:
            self.logger.debug(
                f"{method} response body from {endpoint}",
                endpoint=endpoint,
                status_code=response.status_code,
                response_data=response_body,
            )

        return self._handle_response(alma_response)

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
    
    def iter_paged(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        page_size: int = 100,
        record_key: Optional[str] = None,
        max_records: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Yield records one at a time, fetching pages on demand.

        Walks any Alma "list/search" endpoint that uses the standard
        ``limit`` / ``offset`` pagination contract and exposes a
        ``total_record_count`` field plus a record array under a
        well-known key (``invoice``, ``pol``, ``user``, ``bib``, ...).
        Centralises the offset bookkeeping that previously lived inline
        in every domain method that walked paged results, so callers no
        longer have to re-derive the loop or remember to stop on the
        ``total_record_count`` boundary.

        The method is a *generator*: pages are fetched on demand, so a
        caller that breaks out early after the first match never pays
        for pages it does not need. Callers that want a list use
        ``list(client.iter_paged(...))``.

        Args:
            endpoint: API endpoint (e.g., ``'almaws/v1/acq/invoices'``).
                Must be non-empty.
            params: Caller-supplied query parameters. Merged with the
                paginator's ``limit`` / ``offset`` on each request; the
                paginator's values always win on key collision so the
                walk cannot be derailed by a stray caller-supplied
                offset.
            page_size: Records to request per page. Must be a positive
                ``int``. Defaults to ``100`` (the most common Alma
                per-endpoint cap). Some Alma endpoints cap below this;
                callers walking those should pass an explicit
                ``page_size`` matching the endpoint's documented limit.
            record_key: Top-level key in the response body under which
                the record array lives (e.g., ``'invoice'``,
                ``'pol'``, ``'user'``, ``'bib'``). When ``None`` (the
                default), the first page is fetched but no records are
                yielded — useful only for total-count probes; almost
                every real caller will pass a string here.
            max_records: Hard cap on the number of records yielded.
                ``None`` (the default) means yield until the endpoint
                is exhausted. Must be ``None`` or a non-negative
                ``int`` when supplied.

        Yields:
            Each record dict in turn, in the order Alma returns them.

        Raises:
            AlmaValidationError: If ``endpoint`` is empty, ``page_size``
                is non-positive / non-int, or ``max_records`` is
                negative / non-int.
            AlmaAPIError: Surfaces verbatim from the underlying
                ``self.get`` call when a page fetch fails.

        Pattern source: GitHub issue #11 (API: add iter_paged()
        generator at the client level).
        """
        # Input validation. ``bool`` is an ``int`` subclass in Python,
        # so reject it explicitly for the same reason
        # ``_validate_retry_kwargs`` does -- callers passing ``True``
        # almost certainly mean to enable a feature, not to set a
        # numeric size.
        if not endpoint:
            raise AlmaValidationError("endpoint is required")
        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size <= 0
        ):
            raise AlmaValidationError(
                f"page_size must be a positive int, got {page_size!r}"
            )
        if max_records is not None:
            if (
                isinstance(max_records, bool)
                or not isinstance(max_records, int)
                or max_records < 0
            ):
                raise AlmaValidationError(
                    "max_records must be a non-negative int or None, "
                    f"got {max_records!r}"
                )

        self.logger.info(
            "Paginating Alma endpoint",
            endpoint=endpoint,
            page_size=page_size,
            record_key=record_key,
            max_records=max_records,
        )

        offset = 0
        yielded = 0
        # Snapshot the caller-supplied params once; per-page kwargs are
        # built by overlaying ``limit``/``offset`` so pagination state
        # cannot leak back into the caller's dict between iterations.
        base_params = dict(params or {})

        while True:
            page_params = {
                **base_params,
                "limit": page_size,
                "offset": offset,
            }
            body = self.get(endpoint, params=page_params).json()

            if record_key:
                items = body.get(record_key, []) or []
            else:
                items = []

            for item in items:
                if max_records is not None and yielded >= max_records:
                    return
                yield item
                yielded += 1

            # ``max_records`` cap may also fire mid-page; check at the
            # top of the next iteration too so we don't over-fetch.
            if max_records is not None and yielded >= max_records:
                return

            total = body.get("total_record_count", 0) or 0
            offset += page_size
            # Stop conditions:
            # 1. We've walked past the reported total_record_count.
            # 2. The page came back empty (defensive: handles endpoints
            #    that omit total_record_count or report it as 0 even
            #    when records are present on the last page).
            if offset >= total or not items:
                return

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
                self.logger.info(f"Successfully connected to Alma API ({self.environment})")
            else:
                self.logger.error(
                    f"Connection failed: {response.status_code} - {response.text}"
                )
            return success
        except Exception as e:
            self.logger.exception(f"Connection error: {e}")
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
            self.logger.info(f"Switched from {old_env} to {self.environment}")
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

    # -------------------------------------------------------------------------
    # Context-manager / close support (issue #13)
    #
    # Pattern source: GitHub issue #13 (API: add context-manager support to
    # AlmaAPIClient). With #3 in place the client owns a persistent
    # ``requests.Session`` whose underlying TCP+TLS pool needs explicit
    # teardown to release file descriptors and close keep-alive
    # connections. ``__enter__``/``__exit__``/``close`` give callers a
    # clean ``with``-statement story without changing any of the existing
    # construction or HTTP-verb semantics.
    # -------------------------------------------------------------------------

    def __enter__(self) -> "AlmaAPIClient":
        """Enter the runtime context, returning ``self``.

        Enables the standard ``with AlmaAPIClient(...) as alma:`` idiom.
        The session is set up eagerly in ``__init__`` (issue #3), so
        nothing additional needs to happen on entry — this hook exists
        solely so the matching ``__exit__`` can close the session
        deterministically.

        Returns:
            The client instance, ready for use inside the ``with`` block.

        Pattern source: GitHub issue #13.
        """
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Exit the runtime context and close the underlying session.

        Args:
            exc_type: Exception class, or ``None`` if the block exited
                normally.
            exc: Exception instance, or ``None``.
            tb: Traceback object, or ``None``.

        Pattern source: GitHub issue #13.
        """
        self.close()

    def close(self) -> None:
        """Close the persistent ``requests.Session`` and release pooled connections.

        Idempotent: calling ``close`` more than once is safe and is a
        no-op after the first call. After the session is closed, the
        client transitions to a "closed" state and any subsequent HTTP
        verb call (``get``/``post``/``put``/``delete``/``_request``) will
        raise :class:`AlmaAPIError`. Re-creating a session implicitly on
        next use was deliberately rejected: a closed client signals the
        caller's intent to release the resource, and silently rebuilding
        it would mask programmer errors (e.g., reusing a ``with``-block
        client outside the block).

        If the caller still needs to make calls after closing, they
        should construct a new ``AlmaAPIClient``.

        Raises:
            None. The ``requests.Session.close`` call is best-effort: any
            exception while closing is swallowed and logged at WARNING
            level so teardown in ``__exit__`` (the typical caller) never
            masks an in-flight exception from the ``with`` body.

        Pattern source: GitHub issue #13.
        """
        session = getattr(self, "_session", None)
        if session is None:
            return
        try:
            session.close()
        except Exception as exc:  # noqa: BLE001 — defensive teardown only
            # Never let a teardown failure mask the user's primary
            # exception. Log and move on; the session reference is still
            # cleared so the client lands in the closed state.
            self.logger.warning(
                "Error while closing AlmaAPIClient session", error=str(exc)
            )
        finally:
            self._session = None
    





# Usage example and testing
if __name__ == "__main__":
    """
    Example usage of the AlmaAPIClient.
    This shows how the class works as a foundation.
    """
    # Mirror INFO+ logger output to stderr so CLI users see the same
    # progress/error messages that the alma_logging file handlers
    # capture. Library code itself emits no raw stdout (issue #14).
    import logging as _logging
    _stderr_handler = _logging.StreamHandler(sys.stderr)
    _stderr_handler.setFormatter(_logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    _logging.getLogger("almapi").addHandler(_stderr_handler)
    _logging.getLogger("almapi").setLevel(_logging.INFO)

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
