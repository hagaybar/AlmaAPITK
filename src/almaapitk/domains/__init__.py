"""
almaapitk.domains - Domain-specific API wrappers.
"""
from .admin import Admin
from .users import Users
from .bibs import BibliographicRecords
from .acquisition import Acquisitions
from .resource_sharing import ResourceSharing

__all__ = [
    "Admin",
    "Users",
    "BibliographicRecords",
    "Acquisitions",
    "ResourceSharing",
]
