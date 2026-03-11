"""
Internal re-export module for Alma domain classes.

This module is part of the internal namespace and should not be imported directly.
Use `from almaapitk import ...` instead.

Domain classes provide high-level API wrappers for specific Alma functional areas:
- Admin: Set management (BIB_MMS and USER sets)
- Users: User management and email operations
- BibliographicRecords: Bibliographic record operations
- Acquisitions: Invoice management and POL operations
- ResourceSharing: Lending/borrowing requests via Partners API
"""
from src.domains.admin import Admin
from src.domains.users import Users
from src.domains.bibs import BibliographicRecords
from src.domains.acquisition import Acquisitions
from src.domains.resource_sharing import ResourceSharing

__all__ = [
    "Admin",
    "Users",
    "BibliographicRecords",
    "Acquisitions",
    "ResourceSharing",
]
