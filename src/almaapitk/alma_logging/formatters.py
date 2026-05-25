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
import re
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
            # Redact user ids embedded in the message (e.g. a request URL
            # like ``users/123456789``) — issue #142.
            "message": redact_url_ids(record.getMessage()),
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

    def __init__(self, use_colors: bool = True, redact_patterns: Optional[list] = None):
        """
        Initialize text formatter.

        Args:
            use_colors: Whether to use ANSI color codes (default: True)
            redact_patterns: List of field-name substrings to redact from
                structured custom fields before rendering. Defaults to the
                same list used by ``JSONFormatter`` so the two formatters
                give identical redaction behavior (issue #142).
        """
        super().__init__()
        self.use_colors = use_colors
        self.redact_patterns = redact_patterns or [
            'apikey', 'api_key', 'password', 'token', 'secret', 'authorization'
        ]

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

        # Add message — redact user ids embedded in the message (e.g. a
        # request URL like ``users/123456789``) — issue #142.
        parts.append(redact_url_ids(record.getMessage()))

        # Extract custom fields for display.
        # `taskName` was added in Python 3.12 — must be filtered (issue #2).
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
            'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'taskName',
            'exc_info', 'exc_text', 'stack_info', 'getMessage', 'domain', 'environment'
        }

        # Build a dict first so the recursive redactor can walk nested
        # structures (e.g., headers={'Authorization': 'apikey ...'})
        # exactly the way JSONFormatter does. Then render as text.
        # Without this redaction step the formatter leaks API keys and
        # other secrets to stderr — see issue #142.
        custom_fields_dict = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                custom_fields_dict[key] = value

        if custom_fields_dict:
            custom_fields_dict = redact_sensitive_data(
                custom_fields_dict, self.redact_patterns
            )
            rendered = ', '.join(
                f"{k}={v}" for k, v in custom_fields_dict.items()
            )
            parts.append(f"({rendered})")

        result = " ".join(parts)

        # Add exception info if present
        if record.exc_info:
            result += "\n" + self.formatException(record.exc_info)

        return result


# Credential field-name patterns -> fully replaced with the credential
# placeholder. Keep this list in lock-step with the formatters' default.
_CREDENTIAL_PATTERNS = [
    'apikey', 'api_key', 'password', 'token', 'secret', 'authorization'
]
_CREDENTIAL_PLACEHOLDER = '***REDACTED***'

# Personal name / contact field-name patterns -> blanked entirely. These
# have no safe partial form. Substrings are chosen so they don't match
# non-personal fields (e.g. 'first_name' won't match 'vendor_name', and
# there is deliberately no bare 'name' entry) — see issue #142.
_PII_NAME_PATTERNS = [
    'first_name', 'last_name', 'middle_name', 'full_name',
    'preferred_first_name', 'preferred_middle_name', 'preferred_last_name',
    'birth_date', 'birthdate', 'email', 'phone', 'address', 'gender',
]
_PII_PLACEHOLDER = '<redacted>'

# User-identifier field-name patterns -> partially redacted (last three
# characters kept). Deliberately excludes generic identifiers such as
# mms_id / pol_id / invoice_id, which are not personal data: issue #142 is
# scoped to *user* PII.
_PII_USER_ID_PATTERNS = [
    'user_id', 'user_primary_id', 'primary_id', 'userid', 'user_name',
    'username',
]

# Matches the id segment immediately after ``users/`` in an Alma API path,
# so identifiers embedded in request URLs (which land in the log *message*,
# not a labeled field) get the same partial redaction. Excludes '<' '>' so
# doc/test placeholders like ``users/<user_id>`` are left intact, and stops
# at path/query separators.
_USER_ID_IN_PATH = re.compile(r'(users/)([^/?#&\s"\'<>]+)')


def _partial_redact_id(value: Any) -> str:
    """Keep only the last three characters of an identifier.

    ``"123456789"`` -> ``"<...>789"``. Values of three characters or fewer
    are blanked entirely (``"<...>"``) so a short id is never revealed in
    full. Works for numeric and alphanumeric ids alike.
    """
    s = str(value)
    if len(s) <= 3:
        return '<...>'
    return '<...>' + s[-3:]


def redact_url_ids(text: Any) -> Any:
    """Partially redact user identifiers embedded in Alma API paths.

    ``"almaws/v1/users/123456789"`` -> ``"almaws/v1/users/<...>789"``.
    Bibliographic and other non-user paths are left untouched. Non-string
    input is returned unchanged.
    """
    if not isinstance(text, str):
        return text
    return _USER_ID_IN_PATH.sub(
        lambda m: m.group(1) + _partial_redact_id(m.group(2)), text
    )


def redact_sensitive_data(data: Any, patterns: list = None) -> Any:
    """
    Recursively redact sensitive data from dictionaries, lists and strings.

    Three classes of sensitive data are handled (issue #142):

    - **Credentials** (field name matches ``patterns``): fully replaced
      with ``***REDACTED***``.
    - **Personal names / contact info** (first/last/full name, email,
      phone, address, birth date, gender): blanked as ``<redacted>``.
    - **User identifiers** (``user_id``, ``primary_id``, ...): partially
      redacted, keeping the last three characters (``<...>789``).

    String *values* are additionally scanned for user identifiers embedded
    in ``users/<id>`` URL paths, so ids that ride inside an endpoint string
    are redacted too.

    Args:
        data: Data structure to redact (dict, list, str, or primitive)
        patterns: Credential field-name patterns (defaults to the standard
            credential list)

    Returns:
        Data structure with sensitive fields redacted.

    Example:
        >>> redact_sensitive_data({"apikey": "abc123", "user_id": "123456789"})
        {'apikey': '***REDACTED***', 'user_id': '<...>789'}
    """
    if patterns is None:
        # Missing 'authorization' here would mean that direct callers of
        # redact_sensitive_data() leak HTTP Authorization headers — see
        # issue #142.
        patterns = _CREDENTIAL_PATTERNS

    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            kl = k.lower()
            if any(p in kl for p in patterns):
                out[k] = _CREDENTIAL_PLACEHOLDER
            elif any(p in kl for p in _PII_NAME_PATTERNS):
                out[k] = _PII_PLACEHOLDER
            elif any(p in kl for p in _PII_USER_ID_PATTERNS):
                out[k] = _partial_redact_id(v)
            else:
                out[k] = redact_sensitive_data(v, patterns)
        return out
    elif isinstance(data, list):
        return [redact_sensitive_data(item, patterns) for item in data]
    elif isinstance(data, str):
        return redact_url_ids(data)
    else:
        return data


__all__ = [
    'JSONFormatter', 'TextFormatter', 'redact_sensitive_data', 'redact_url_ids'
]
