"""
AlmaAPITK Logging Module

Comprehensive logging infrastructure for API requests, responses, errors, and performance.

Components:
    - logger: Main logger class for domain-specific logging
    - formatters: JSON and text formatters for log output
    - handlers: File handlers with rotation support
    - config: Configuration management for logging settings

Usage:
    from almaapitk.alma_logging import get_logger

    logger = get_logger('acquisitions', environment='SANDBOX')
    logger.info("Creating invoice", invoice_number="INV-001")

Features:
    - Automatic API key redaction
    - Request/response logging
    - Error tracking with context
    - Performance metrics
    - Log rotation
    - JSON formatted logs

Security:
    - All logs are stored in logs/ directory (gitignored)
    - Sensitive data (API keys, passwords, tokens) automatically redacted
    - Never committed to version control

See: docs/alma_logging/LOGGING_IMPLEMENTATION_PLAN.md for complete documentation
"""

__version__ = '1.0.0'
__author__ = 'AlmaAPITK Development Team'

# Phase 1: Infrastructure - skeleton implementations available
from .logger import AlmaLogger, get_logger
from .formatters import JSONFormatter, TextFormatter, redact_sensitive_data
from .handlers import AlmaRotatingFileHandler, DateOrganizedFileHandler, create_log_directory_structure
from .config import LoggingConfig, load_config

__all__ = [
    # Core logging
    'AlmaLogger',
    'get_logger',
    # Formatters
    'JSONFormatter',
    'TextFormatter',
    'redact_sensitive_data',
    # Handlers
    'AlmaRotatingFileHandler',
    'DateOrganizedFileHandler',
    'create_log_directory_structure',
    # Configuration
    'LoggingConfig',
    'load_config',
]
