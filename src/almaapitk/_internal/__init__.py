"""
Internal namespace for almaapitk public API symbols.

This module aggregates all public symbols from the internal re-export modules.
It serves as an abstraction layer between the public API (almaapitk) and the
actual implementation modules (src.client.*).

WARNING: This is an internal module. Do not import from here directly.
         Use `from almaapitk import ...` instead.
"""
from .client import AlmaAPIClient
from .response import AlmaResponse
from .exceptions import AlmaAPIError, AlmaValidationError

__all__ = [
    "AlmaAPIClient",
    "AlmaResponse",
    "AlmaAPIError",
    "AlmaValidationError",
]
