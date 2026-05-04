"""
Internal namespace for almaapitk public API symbols.

This module aggregates all public symbols from the internal re-export modules.
It serves as an abstraction layer between the public API (almaapitk) and the
actual implementation modules (src.client.*, src.domains.*).

WARNING: This is an internal module. Do not import from here directly.
         Use `from almaapitk import ...` instead.
"""
# Core client and response classes
from .client import AlmaAPIClient
from .response import AlmaResponse
from .exceptions import (
    AlmaAPIError,
    AlmaValidationError,
    AlmaAuthenticationError,
    AlmaRateLimitError,
    AlmaServerError,
    AlmaResourceNotFoundError,
    AlmaDuplicateInvoiceError,
    AlmaInvalidPolModeError,
)

# Domain classes
from .domains import (
    Admin,
    Users,
    BibliographicRecords,
    Acquisitions,
    ResourceSharing,
    Analytics,
)

__all__ = [
    # Core
    "AlmaAPIClient",
    "AlmaResponse",
    "AlmaAPIError",
    "AlmaValidationError",
    # Typed AlmaAPIError subclasses (issue #9)
    "AlmaAuthenticationError",
    "AlmaRateLimitError",
    "AlmaServerError",
    "AlmaResourceNotFoundError",
    "AlmaDuplicateInvoiceError",
    "AlmaInvalidPolModeError",
    # Domains
    "Admin",
    "Users",
    "BibliographicRecords",
    "Acquisitions",
    "ResourceSharing",
    "Analytics",
]
