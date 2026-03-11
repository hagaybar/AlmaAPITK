"""
Internal re-export module for Alma exceptions.

This module is part of the internal namespace and should not be imported directly.
Use `from almaapitk import AlmaAPIError, AlmaValidationError` instead.
"""
from src.client.AlmaAPIClient import AlmaAPIError, AlmaValidationError

__all__ = ["AlmaAPIError", "AlmaValidationError"]
