"""
Unit tests for almaapitk public API contract.

These tests verify that the public API surface is stable and correctly exposes
all documented symbols. This is part of Phase B2 TDD approach.
"""
import unittest
import sys


class TestPublicAPIContract(unittest.TestCase):
    """Tests for the almaapitk public API contract."""

    def test_import_almaapitk(self):
        """Test that almaapitk package can be imported."""
        import almaapitk
        self.assertIsNotNone(almaapitk)

    def test_version_exists_and_is_string(self):
        """Test that __version__ exists and is a string."""
        import almaapitk
        self.assertTrue(hasattr(almaapitk, '__version__'))
        self.assertIsInstance(almaapitk.__version__, str)
        self.assertGreater(len(almaapitk.__version__), 0)

    def test_all_contains_expected_symbols(self):
        """Test that __all__ contains all expected public symbols."""
        import almaapitk
        expected_symbols = [
            '__version__',
            'AlmaAPIClient',
            'AlmaResponse',
            'AlmaAPIError',
            'AlmaValidationError',
        ]
        self.assertTrue(hasattr(almaapitk, '__all__'))
        for symbol in expected_symbols:
            self.assertIn(
                symbol,
                almaapitk.__all__,
                f"Expected '{symbol}' to be in __all__"
            )

    def test_all_symbols_are_accessible(self):
        """Test that every symbol in __all__ is accessible as an attribute."""
        import almaapitk
        for symbol in almaapitk.__all__:
            self.assertTrue(
                hasattr(almaapitk, symbol),
                f"Symbol '{symbol}' in __all__ but not accessible as attribute"
            )

    def test_alma_api_client_importable(self):
        """Test that AlmaAPIClient is importable from almaapitk."""
        from almaapitk import AlmaAPIClient
        self.assertIsNotNone(AlmaAPIClient)
        # It should be a class
        self.assertTrue(callable(AlmaAPIClient))

    def test_alma_response_importable(self):
        """Test that AlmaResponse is importable from almaapitk."""
        from almaapitk import AlmaResponse
        self.assertIsNotNone(AlmaResponse)
        self.assertTrue(callable(AlmaResponse))

    def test_alma_api_error_importable(self):
        """Test that AlmaAPIError is importable from almaapitk."""
        from almaapitk import AlmaAPIError
        self.assertIsNotNone(AlmaAPIError)
        # It should be an exception class
        self.assertTrue(issubclass(AlmaAPIError, Exception))

    def test_alma_validation_error_importable(self):
        """Test that AlmaValidationError is importable from almaapitk."""
        from almaapitk import AlmaValidationError
        self.assertIsNotNone(AlmaValidationError)
        # It should be a ValueError subclass
        self.assertTrue(issubclass(AlmaValidationError, ValueError))

    def test_stdlib_logging_not_shadowed(self):
        """Test that stdlib logging is not shadowed by internal modules."""
        import logging
        self.assertTrue(
            hasattr(logging, 'Formatter'),
            "logging.Formatter should exist (stdlib logging)"
        )
        self.assertTrue(
            hasattr(logging, 'Logger'),
            "logging.Logger should exist (stdlib logging)"
        )
        self.assertTrue(
            hasattr(logging, 'getLogger'),
            "logging.getLogger should exist (stdlib logging)"
        )

    def test_internal_namespace_exists_after_b2(self):
        """
        Test that _internal namespace exists (resilient check).

        This test is designed to pass both before and after Phase B2:
        - Before B2: _internal may not exist, so we skip gracefully
        - After B2: _internal should exist and contain public symbols
        """
        try:
            import almaapitk._internal
            # If we get here, _internal exists (post-B2)
            self.assertTrue(hasattr(almaapitk._internal, '__all__'))
            expected = ['AlmaAPIClient', 'AlmaResponse', 'AlmaAPIError', 'AlmaValidationError']
            for symbol in expected:
                self.assertIn(
                    symbol,
                    almaapitk._internal.__all__,
                    f"Expected '{symbol}' in _internal.__all__"
                )
        except ImportError:
            # Before B2, _internal doesn't exist - this is OK
            self.skipTest("almaapitk._internal not yet created (pre-Phase B2)")


class TestPublicAPIUsage(unittest.TestCase):
    """Tests verifying the public API can be used correctly."""

    def test_exception_hierarchy(self):
        """Test that exception classes have correct hierarchy."""
        from almaapitk import AlmaAPIError, AlmaValidationError

        # AlmaAPIError is a base Exception
        self.assertTrue(issubclass(AlmaAPIError, Exception))

        # AlmaValidationError is a ValueError
        self.assertTrue(issubclass(AlmaValidationError, ValueError))

    def test_direct_import_style(self):
        """Test that direct import style works."""
        # This should work without errors
        from almaapitk import (
            AlmaAPIClient,
            AlmaResponse,
            AlmaAPIError,
            AlmaValidationError,
        )
        # All should be non-None
        self.assertIsNotNone(AlmaAPIClient)
        self.assertIsNotNone(AlmaResponse)
        self.assertIsNotNone(AlmaAPIError)
        self.assertIsNotNone(AlmaValidationError)

    def test_module_attribute_style(self):
        """Test that module attribute style works."""
        import almaapitk
        # Access via module attributes
        client_cls = almaapitk.AlmaAPIClient
        response_cls = almaapitk.AlmaResponse
        error_cls = almaapitk.AlmaAPIError
        validation_cls = almaapitk.AlmaValidationError

        self.assertIsNotNone(client_cls)
        self.assertIsNotNone(response_cls)
        self.assertIsNotNone(error_cls)
        self.assertIsNotNone(validation_cls)


if __name__ == '__main__':
    unittest.main()
