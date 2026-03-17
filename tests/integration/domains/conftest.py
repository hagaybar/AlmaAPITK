"""
Pytest configuration for integration tests.

Registers custom markers and provides shared fixtures.
"""
import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (may require API access)"
    )
