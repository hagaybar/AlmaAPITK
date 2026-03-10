# =============================================================================
# almaapitk - Public API Surface
# =============================================================================
#
# This module provides a stable public import path for downstream projects:
#
#     import almaapitk
#     client = almaapitk.AlmaAPIClient('SANDBOX')
#
# EXPORTED (Public API):
#   - AlmaAPIClient: Main API client for Alma interactions
#   - AlmaResponse: Response wrapper with .data, .json(), .success properties
#   - AlmaAPIError: Base exception for API errors
#   - AlmaValidationError: Exception for validation failures
#
# NOT EXPORTED (intentionally kept internal):
#   - Domain classes (Admin, Users, Bibs, etc.) - import from src.domains directly
#   - Utility modules (TSVGenerator, etc.) - import from src.utils directly
#   - Logging infrastructure - import from src.alma_logging directly
#
# KNOWN ISSUE:
#   When PYTHONPATH=./src, the local `logging` folder shadows Python's stdlib
#   `logging` module, causing circular import errors when importing AlmaAPIClient
#   directly. This module uses lazy imports to allow `import almaapitk` to succeed
#   while deferring the actual class loading until first access.
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
