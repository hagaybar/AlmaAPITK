"""
Main Logger Class for AlmaAPITK

Provides structured logging for API requests, responses, errors, and performance metrics.

Usage:
    from almaapitk.alma_logging import get_logger

    logger = get_logger('acquisitions', environment='SANDBOX')
    logger.info("Creating invoice", invoice_number="INV-001")
    logger.error("Failed to create invoice", error_code="60260", tracking_id="E01-...")

Features:
    - Domain-specific logging (acquisitions, users, bibs, admin)
    - Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Automatic API key redaction
    - Request/response logging with timing
    - Error tracking with full context
    - JSON and text output formats
"""

import logging
import sys
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from .formatters import JSONFormatter, TextFormatter
from .handlers import AlmaRotatingFileHandler
from .config import load_config


class AlmaLogger:
    """
    Main logger class for AlmaAPITK operations.

    Provides structured logging with automatic redaction of sensitive data,
    request/response tracking, and domain-specific log files.

    Attributes:
        domain: The domain this logger is for (acquisitions, users, bibs, admin)
        environment: The Alma environment (SANDBOX, PRODUCTION)
        logger: The underlying Python logger instance
    """

    def __init__(self, domain: str, environment: str = 'SANDBOX', config=None):
        """
        Initialize logger for a specific domain.

        Args:
            domain: Domain name (acquisitions, users, bibs, admin, api_client)
            environment: Alma environment (SANDBOX, PRODUCTION)
            config: Optional LoggingConfig instance (loads default if not provided)
        """
        self.domain = domain
        self.environment = environment
        self.logger = logging.getLogger(f"almapi.{domain}")

        # Load configuration
        if config is None:
            config = load_config()
        self.config = config

        # Only configure if not already configured
        if not self.logger.handlers:
            self._configure_logger()

    def _configure_logger(self):
        """Configure logger with handlers and formatters."""
        # The level gate lives on the shared ``almapi`` parent, not on the
        # per-domain child, so a consumer can quiet (or open up) the whole
        # toolkit with a single call -- ``logging.getLogger("almapi")
        # .setLevel(logging.WARNING)`` -- instead of having to know and
        # reconfigure every ``almapi.<domain>`` logger by name (issue #142).
        parent = logging.getLogger("almapi")
        if parent.level == logging.NOTSET:
            # Honour a consumer who set the level before first use; only
            # seed the default when nobody has touched it.
            parent.setLevel(
                getattr(logging, self.config.log_level, logging.INFO)
            )

        # Leave the child level unset so it inherits the parent's level.
        self.logger.setLevel(logging.NOTSET)

        # Prevent propagation to root logger (avoid duplicate logs); the
        # handlers below live on this child logger.
        self.logger.propagate = False

        # Add console handler with text formatter. No explicit handler
        # level: the parent logger's level is the single gate.
        if self.config.output.get('console', True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(TextFormatter(use_colors=True))
            self.logger.addHandler(console_handler)

        # Add file handler with JSON formatter (opt-in; off by default).
        if self.config.output.get('file', False):
            # Create log directory structure
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_dir = Path("logs") / "api_requests" / date_str
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / f"{self.domain}.log"

            # Get rotation settings
            rotation_settings = self.config.get_rotation_settings()

            file_handler = AlmaRotatingFileHandler(
                filename=str(log_file),
                maxBytes=rotation_settings['max_bytes'],
                backupCount=rotation_settings['backup_count']
            )
            file_handler.setFormatter(JSONFormatter(
                redact_patterns=self.config.get_redact_patterns()
            ))
            self.logger.addHandler(file_handler)

    def _log(self, level: int, message: str, **kwargs):
        """
        Internal logging method that adds custom fields to LogRecord.

        Args:
            level: Logging level (logging.DEBUG, INFO, etc.)
            message: Log message
            **kwargs: Additional context fields to attach to log record
        """
        # Create log record with custom fields
        extra = {
            'domain': self.domain,
            'environment': self.environment
        }
        # Add all custom fields from kwargs
        extra.update(kwargs)

        self.logger.log(level, message, extra=extra)

    def info(self, message: str, **kwargs):
        """
        Log informational message with optional context.

        Args:
            message: Log message
            **kwargs: Additional context fields (e.g., invoice_number="INV-001")

        Example:
            logger.info("Creating invoice", invoice_number="INV-001", vendor="RIALTO")
        """
        self._log(logging.INFO, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """
        Log debug message with optional context.

        Args:
            message: Log message
            **kwargs: Additional context fields
        """
        self._log(logging.DEBUG, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """
        Log warning message with optional context.

        Args:
            message: Log message
            **kwargs: Additional context fields
        """
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """
        Log error message with optional context.

        Args:
            message: Log message
            **kwargs: Additional context fields (e.g., error_code="60260")
        """
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """
        Log critical message with optional context.

        Args:
            message: Log message
            **kwargs: Additional context fields
        """
        self._log(logging.CRITICAL, message, **kwargs)

    def should_log_bodies(self) -> bool:
        """Whether full request/response bodies may be logged.

        Off by default (issue #142): bodies are the largest PII source.
        Gated by the ``log_bodies`` config flag.
        """
        return self.config.get_log_bodies()

    def log_request(self, method: str, endpoint: str, **kwargs):
        """
        Log API request with full context.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            **kwargs: Additional request details (params, headers, body)

        Example:
            logger.log_request('POST', 'almaws/v1/acq/invoices',
                              params={'op': 'paid'},
                              headers={'Content-Type': 'application/json'},
                              body={'invoice_number': 'INV-001'})
        """
        # Bodies are PII-heavy; drop unless the consumer opted in (#142).
        if not self.should_log_bodies():
            kwargs.pop('body', None)
        self.debug(
            f"API Request: {method} {endpoint}",
            method=method,
            endpoint=endpoint,
            **kwargs
        )

    def log_request_body(self, method: str, endpoint: str, request_data):
        """Log the full outgoing request body at DEBUG.

        No-op unless body logging is explicitly enabled (issue #142):
        request bodies can carry personal data (e.g. user-note text).
        """
        if not self.should_log_bodies():
            return
        self.debug(
            f"{method} request body to {endpoint}",
            endpoint=endpoint,
            request_data=request_data,
        )

    def log_response_body(self, method: str, endpoint: str,
                          status_code, response_data):
        """Log the full response body at DEBUG.

        No-op unless body logging is explicitly enabled (issue #142): a
        single user lookup returns the entire patron record.
        """
        if not self.should_log_bodies():
            return
        self.debug(
            f"{method} response body from {endpoint}",
            endpoint=endpoint,
            status_code=status_code,
            response_data=response_data,
        )

    def log_response(self, response, duration_ms: float):
        """
        Log API response with timing.

        Args:
            response: HTTP response object (must have status_code attribute)
            duration_ms: Request duration in milliseconds

        Example:
            logger.log_response(response, duration_ms=234.5)
        """
        status_code = getattr(response, 'status_code', 'unknown')
        self.debug(
            f"API Response: {status_code}",
            status_code=status_code,
            duration_ms=duration_ms
        )

    def log_error(self, error: Exception, **context):
        """
        Log error with full context and stack trace.

        The exception text is attached as structured ``exception_message``
        in ``extra`` (where the redactor can scrub credential-shaped
        fields) and the traceback is captured via ``exc_info``. The
        message string itself only names the exception type so a future
        ``str(exception)`` carrying a URL with credentials cannot bypass
        the redactor (issue #154, F-003).

        Args:
            error: Exception that occurred
            **context: Additional context about the error

        Example:
            logger.log_error(exception, invoice_number="INV-001", operation="create")
        """
        extra = {
            'domain': self.domain,
            'environment': self.environment,
            'exception_type': type(error).__name__,
            'exception_message': str(error)
        }
        extra.update(context)

        self.logger.error(
            f"Exception: {type(error).__name__}",
            extra=extra,
            exc_info=True
        )

    def exception(self, message: str, **kwargs):
        """
        Log ``message`` at ERROR level with the current exception
        attached via ``exc_info``.

        Mirrors stdlib ``logging.Logger.exception`` so callers can write
        ``self.logger.exception("operation failed", ...)`` from inside
        an ``except`` block. The traceback (including the exception's
        ``__str__``) is captured by ``exc_info`` automatically — do NOT
        interpolate the exception text into ``message``. Pass
        exception-derived detail as structured kwargs so
        ``redact_sensitive_data`` can scrub credential-shaped fields
        (issue #154, F-003).

        Args:
            message: Log message describing the operation that failed.
            **kwargs: Additional context fields attached as redactable
                ``extra`` data.
        """
        extra = {
            'domain': self.domain,
            'environment': self.environment,
        }
        extra.update(kwargs)
        self.logger.error(message, extra=extra, exc_info=True)


# Logger cache to reuse instances
_logger_cache: Dict[str, AlmaLogger] = {}


def get_logger(domain: str, environment: str = 'SANDBOX', config=None) -> AlmaLogger:
    """
    Get or create logger for a specific domain.

    Loggers are cached per domain-environment combination to avoid
    creating multiple handlers for the same logger.

    Args:
        domain: Domain name (acquisitions, users, bibs, admin, api_client)
        environment: Alma environment (SANDBOX, PRODUCTION)
        config: Optional LoggingConfig instance

    Returns:
        AlmaLogger instance for the specified domain

    Example:
        >>> logger = get_logger('acquisitions', environment='SANDBOX')
        >>> logger.info("Creating invoice", invoice_number="INV-001")
    """
    # Create cache key from domain and environment
    cache_key = f"{domain}:{environment}"

    # Return cached logger if exists
    if cache_key in _logger_cache:
        return _logger_cache[cache_key]

    # Create new logger and cache it
    logger = AlmaLogger(domain, environment, config=config)
    _logger_cache[cache_key] = logger

    return logger


__all__ = ['AlmaLogger', 'get_logger']
