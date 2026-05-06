"""
Log Formatters for AlmaAPITK

Provides JSON and text formatters for structured logging output.

Formatters:
    - JSONFormatter: Structured JSON output for machine parsing (JSON Lines format)
    - TextFormatter: Human-readable text output for console viewing

Features:
    - Automatic timestamp formatting (ISO 8601 with timezone)
    - Field extraction from LogRecord
    - Sensitive data redaction (API keys, passwords, tokens)
    - Compact JSON output (one line per entry)
"""

import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured log output.

    Formats log records as JSON objects with fields:
        - timestamp: ISO 8601 formatted timestamp
        - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - domain: Domain name (acquisitions, users, etc.)
        - message: Log message
        - context: Additional context fields

    Example output:
        {
            "timestamp": "2025-10-23T14:30:45.123Z",
            "level": "INFO",
            "domain": "acquisitions",
            "message": "Creating invoice",
            "context": {
                "invoice_number": "INV-001",
                "vendor": "RIALTO"
            }
        }
    """

    def __init__(self, redact_patterns: Optional[list] = None):
        """
        Initialize JSON formatter.

        Args:
            redact_patterns: List of field name patterns to redact (optional)
        """
        super().__init__()
        self.redact_patterns = redact_patterns or ['apikey', 'api_key', 'password', 'token', 'secret', 'authorization']

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as compact JSON string (JSON Lines format).

        Args:
            record: Python logging.LogRecord

        Returns:
            JSON string representation of log record (one line)
        """
        # Base log data
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Extract custom fields from record
        # These are added via logger.info("message", key=value, ...)
        if hasattr(record, 'domain'):
            log_data['domain'] = record.domain

        if hasattr(record, 'environment'):
            log_data['environment'] = record.environment

        # Extract all custom attributes (anything not in standard LogRecord).
        # `taskName` was added in Python 3.12 — must be filtered (issue #2).
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
            'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'taskName',
            'exc_info', 'exc_text', 'stack_info', 'getMessage', 'domain', 'environment'
        }

        custom_fields = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                custom_fields[key] = value

        if custom_fields:
            # Redact sensitive data from custom fields
            custom_fields = redact_sensitive_data(custom_fields, self.redact_patterns)
            log_data['context'] = custom_fields

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Return compact JSON (one line per entry - JSON Lines format)
        return json.dumps(log_data, separators=(',', ':'))


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter for console output.

    Formats log records in readable text format with optional color coding.

    Example output:
        [2025-10-23 14:30:45] INFO     [acquisitions] Creating invoice (invoice_number=INV-001)
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }

    def __init__(self, use_colors: bool = True):
        """
        Initialize text formatter.

        Args:
            use_colors: Whether to use ANSI color codes (default: True)
        """
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as human-readable text.

        Args:
            record: Python logging.LogRecord

        Returns:
            Formatted text string
        """
        # Format timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Get color code if enabled
        color = self.COLORS.get(record.levelname, '') if self.use_colors else ''
        reset = self.COLORS['RESET'] if self.use_colors else ''

        # Base format: [timestamp] LEVEL [domain] message
        parts = [f"[{timestamp}]"]

        # Add colored level
        parts.append(f"{color}{record.levelname:8s}{reset}")

        # Add domain if present
        if hasattr(record, 'domain'):
            parts.append(f"[{record.domain}]")

        # Add message
        parts.append(record.getMessage())

        # Extract custom fields for display.
        # `taskName` was added in Python 3.12 — must be filtered (issue #2).
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
            'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'taskName',
            'exc_info', 'exc_text', 'stack_info', 'getMessage', 'domain', 'environment'
        }

        custom_fields = []
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                custom_fields.append(f"{key}={value}")

        if custom_fields:
            parts.append(f"({', '.join(custom_fields)})")

        result = " ".join(parts)

        # Add exception info if present
        if record.exc_info:
            result += "\n" + self.formatException(record.exc_info)

        return result


def redact_sensitive_data(data: Any, patterns: list = None) -> Any:
    """
    Recursively redact sensitive data from dictionaries and lists.

    Args:
        data: Data structure to redact (dict, list, or primitive)
        patterns: List of field name patterns to redact (e.g., ['apikey', 'password'])

    Returns:
        Data structure with sensitive fields replaced by '***REDACTED***'

    Example:
        >>> data = {"apikey": "abc123", "user": "john"}
        >>> redact_sensitive_data(data, patterns=['apikey'])
        {"apikey": "***REDACTED***", "user": "john"}
    """
    if patterns is None:
        patterns = ['apikey', 'api_key', 'password', 'token', 'secret']

    # TODO: Phase 1.1 - Implement recursive redaction for dicts
    # TODO: Phase 1.1 - Implement recursive redaction for lists
    # TODO: Phase 1.1 - Handle nested structures
    # TODO: Phase 1.1 - Case-insensitive pattern matching

    if isinstance(data, dict):
        return {
            k: '***REDACTED***' if any(p in k.lower() for p in patterns)
            else redact_sensitive_data(v, patterns)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_sensitive_data(item, patterns) for item in data]
    else:
        return data


__all__ = ['JSONFormatter', 'TextFormatter', 'redact_sensitive_data']
