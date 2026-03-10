# =============================================================================
# almaapitk - Public API Surface
# =============================================================================
#
# TEMPORARY IMPLEMENTATION:
# This module provides a stable public import path: `import almaapitk`
#
# Current state: Minimal stub that imports client and utils packages.
# The client and utils __init__.py files are currently empty, so no symbols
# are actually exported yet. This will be tightened later to expose only
# the intended public API with explicit exports.
#
# Do NOT add logging exports here unless explicitly needed.
#
# Future usage (when exports are defined):
#     import almaapitk
#     client = almaapitk.AlmaAPIClient('SANDBOX')
#
# =============================================================================

# Import packages to ensure they're loadable (no symbols exported yet)
import client
import utils

__version__ = "0.1.0"
__all__ = []  # Will be populated as public API is formalized
