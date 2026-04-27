# =============================================================================
# almaapitk - Public API Surface (API Contract v0.2.0)
# =============================================================================
#
# This is the ONLY supported public API surface for the AlmaAPITK package.
# All consumer code should import from this module only.
#
# USAGE:
#     import almaapitk
#     client = almaapitk.AlmaAPIClient('SANDBOX')
#
#     # Or import specific symbols:
#     from almaapitk import AlmaAPIClient, AlmaAPIError
#
#     # Domain classes (new in v0.2.0):
#     from almaapitk import Admin, Users, Acquisitions
#
# PUBLIC API (__all__):
#   Core:
#   - __version__: Package version string
#   - AlmaAPIClient: Main API client for Alma interactions
#   - AlmaResponse: Response wrapper with .data, .json(), .success properties
#   - AlmaAPIError: Base exception for API errors
#   - AlmaValidationError: Exception for validation failures
#
#   Domains (new in v0.2.0):
#   - Admin: Set management (BIB_MMS and USER sets)
#   - Users: User management and email operations
#   - BibliographicRecords: Bibliographic record operations
#   - Acquisitions: Invoice management and POL operations
#   - ResourceSharing: Lending/borrowing requests via Partners API
#
# INTERNAL (not part of public API - may change without notice):
#   - src.client.* - Use almaapitk.AlmaAPIClient instead
#   - src.domains.* - Use almaapitk domain classes instead
#   - src.utils.* - Utility modules (project-level, not part of public API)
#   - src.alma_logging.* - Logging infrastructure (internal)
#
# MIGRATION:
#   If you currently import from internal modules, please migrate:
#     OLD: from src.client.AlmaAPIClient import AlmaAPIClient
#     NEW: from almaapitk import AlmaAPIClient
#
#     OLD: from src.domains.admin import Admin
#     NEW: from almaapitk import Admin
#
#     OLD: from src.domains.acquisition import Acquisitions
#     NEW: from almaapitk import Acquisitions
#
# IMPLEMENTATION NOTE:
#   This module uses lazy imports via the _internal namespace to decouple the
#   public API from the internal implementation layout. The actual class loading
#   happens on first attribute access, avoiding circular import issues with
#   stdlib logging.
#
# =============================================================================

__version__ = "0.3.1"

__all__ = [
    # Package metadata
    "__version__",
    # Core client and response
    "AlmaAPIClient",
    "AlmaResponse",
    "AlmaAPIError",
    "AlmaValidationError",
    # Domain classes
    "Admin",
    "Users",
    "BibliographicRecords",
    "Acquisitions",
    "ResourceSharing",
    "Analytics",
    # Utilities
    "TSVGenerator",
    "CitationMetadataError",
]

# Lazy import implementation to avoid circular import at module load time
# The actual imports happen on first attribute access
_lazy_imports = {
    # Core
    "AlmaAPIClient": ("almaapitk._internal", "AlmaAPIClient"),
    "AlmaResponse": ("almaapitk._internal", "AlmaResponse"),
    "AlmaAPIError": ("almaapitk._internal", "AlmaAPIError"),
    "AlmaValidationError": ("almaapitk._internal", "AlmaValidationError"),
    # Domains
    "Admin": ("almaapitk._internal", "Admin"),
    "Users": ("almaapitk._internal", "Users"),
    "BibliographicRecords": ("almaapitk._internal", "BibliographicRecords"),
    "Acquisitions": ("almaapitk._internal", "Acquisitions"),
    "ResourceSharing": ("almaapitk._internal", "ResourceSharing"),
    "Analytics": ("almaapitk._internal", "Analytics"),
    # Utilities
    "TSVGenerator": ("almaapitk.utils.tsv_generator", "TSVGenerator"),
    "CitationMetadataError": ("almaapitk.utils.citation_metadata", "CitationMetadataError"),
}

_loaded = {}


def __getattr__(name):
    """Lazy import handler for public API symbols."""
    if name in _lazy_imports:
        if name not in _loaded:
            module_path, attr_name = _lazy_imports[name]
            import importlib
            module = importlib.import_module(module_path)
            _loaded[name] = getattr(module, attr_name)
        return _loaded[name]
    raise AttributeError(f"module 'almaapitk' has no attribute '{name}'")
