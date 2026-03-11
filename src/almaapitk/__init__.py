# =============================================================================
# almaapitk - Public API Surface (API Contract v0.1.0)
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
# PUBLIC API (__all__):
#   - __version__: Package version string
#   - AlmaAPIClient: Main API client for Alma interactions
#   - AlmaResponse: Response wrapper with .data, .json(), .success properties
#   - AlmaAPIError: Base exception for API errors
#   - AlmaValidationError: Exception for validation failures
#
# INTERNAL (not part of public API - may change without notice):
#   - src.client.* - Use almaapitk.AlmaAPIClient instead
#   - src.domains.* - Domain classes (Admin, Users, Bibs, etc.)
#   - src.utils.* - Utility modules
#   - src.alma_logging.* - Logging infrastructure
#
# MIGRATION:
#   If you currently import from internal modules, please migrate:
#     OLD: from src.client.AlmaAPIClient import AlmaAPIClient
#     NEW: from almaapitk import AlmaAPIClient
#
# IMPLEMENTATION NOTE:
#   This module uses lazy imports to avoid circular import issues with stdlib
#   logging. The actual class loading happens on first attribute access.
#
# =============================================================================

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "AlmaAPIClient",
    "AlmaResponse",
    "AlmaAPIError",
    "AlmaValidationError",
]

# Lazy import implementation to avoid circular import at module load time
# The actual imports happen on first attribute access
_lazy_imports = {
    "AlmaAPIClient": ("client.AlmaAPIClient", "AlmaAPIClient"),
    "AlmaResponse": ("client.AlmaAPIClient", "AlmaResponse"),
    "AlmaAPIError": ("client.AlmaAPIClient", "AlmaAPIError"),
    "AlmaValidationError": ("client.AlmaAPIClient", "AlmaValidationError"),
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
