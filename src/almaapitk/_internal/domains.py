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
- Analytics: Analytics reports and data retrieval
- Configuration: Configuration API surface (foundation skeleton, issue #22)
- Electronic: Electronic API surface (foundation skeleton, issue #66)
"""
from almaapitk.domains.admin import Admin
from almaapitk.domains.users import Users
from almaapitk.domains.bibs import BibliographicRecords
from almaapitk.domains.acquisition import Acquisitions
from almaapitk.domains.resource_sharing import ResourceSharing
from almaapitk.domains.analytics import Analytics
from almaapitk.domains.configuration import Configuration
from almaapitk.domains.electronic import Electronic

__all__ = [
    "Admin",
    "Users",
    "BibliographicRecords",
    "Acquisitions",
    "ResourceSharing",
    "Analytics",
    "Configuration",
    "Electronic",
]
