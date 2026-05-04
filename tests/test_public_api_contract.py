"""
Unit tests for almaapitk public API contract.

These tests verify that the public API surface is stable and correctly exposes
all documented symbols. This is part of Phase B2 TDD approach.

v0.2.0: Extended to include domain classes (Admin, Users, BibliographicRecords,
        Acquisitions, ResourceSharing)
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

    def test_all_contains_expected_core_symbols(self):
        """Test that __all__ contains all expected core public symbols."""
        import almaapitk
        expected_core_symbols = [
            '__version__',
            'AlmaAPIClient',
            'AlmaResponse',
            'AlmaAPIError',
            'AlmaValidationError',
        ]
        self.assertTrue(hasattr(almaapitk, '__all__'))
        for symbol in expected_core_symbols:
            self.assertIn(
                symbol,
                almaapitk.__all__,
                f"Expected core symbol '{symbol}' to be in __all__"
            )

    def test_all_contains_expected_domain_symbols(self):
        """Test that __all__ contains all expected domain class symbols (v0.2.0)."""
        import almaapitk
        expected_domain_symbols = [
            'Admin',
            'Users',
            'BibliographicRecords',
            'Acquisitions',
            'ResourceSharing',
        ]
        self.assertTrue(hasattr(almaapitk, '__all__'))
        for symbol in expected_domain_symbols:
            self.assertIn(
                symbol,
                almaapitk.__all__,
                f"Expected domain symbol '{symbol}' to be in __all__"
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

    def test_typed_error_subclasses_importable(self):
        """Test that typed AlmaAPIError subclasses are importable from almaapitk (issue #9)."""
        from almaapitk import (
            AlmaAPIError,
            AlmaAuthenticationError,
            AlmaRateLimitError,
            AlmaServerError,
            AlmaResourceNotFoundError,
            AlmaDuplicateInvoiceError,
            AlmaInvalidPolModeError,
        )
        # Each must be a non-None class.
        for cls in (
            AlmaAuthenticationError,
            AlmaRateLimitError,
            AlmaServerError,
            AlmaResourceNotFoundError,
            AlmaDuplicateInvoiceError,
            AlmaInvalidPolModeError,
        ):
            self.assertIsNotNone(cls)
            # All typed subclasses must remain ``AlmaAPIError`` so existing
            # ``except AlmaAPIError:`` blocks continue to catch them.
            self.assertTrue(
                issubclass(cls, AlmaAPIError),
                f"{cls.__name__} must subclass AlmaAPIError for backwards-compat",
            )

    def test_typed_error_subclasses_in_all(self):
        """Test that typed AlmaAPIError subclasses are in __all__ (issue #9)."""
        import almaapitk
        expected_typed_errors = [
            'AlmaAuthenticationError',
            'AlmaRateLimitError',
            'AlmaServerError',
            'AlmaResourceNotFoundError',
            'AlmaDuplicateInvoiceError',
            'AlmaInvalidPolModeError',
        ]
        for symbol in expected_typed_errors:
            self.assertIn(
                symbol,
                almaapitk.__all__,
                f"Expected typed-error symbol '{symbol}' to be in __all__",
            )

    def test_admin_importable(self):
        """Test that Admin domain class is importable from almaapitk."""
        from almaapitk import Admin
        self.assertIsNotNone(Admin)
        self.assertTrue(callable(Admin))

    def test_users_importable(self):
        """Test that Users domain class is importable from almaapitk."""
        from almaapitk import Users
        self.assertIsNotNone(Users)
        self.assertTrue(callable(Users))

    def test_bibliographic_records_importable(self):
        """Test that BibliographicRecords domain class is importable from almaapitk."""
        from almaapitk import BibliographicRecords
        self.assertIsNotNone(BibliographicRecords)
        self.assertTrue(callable(BibliographicRecords))

    def test_acquisitions_importable(self):
        """Test that Acquisitions domain class is importable from almaapitk."""
        from almaapitk import Acquisitions
        self.assertIsNotNone(Acquisitions)
        self.assertTrue(callable(Acquisitions))

    def test_resource_sharing_importable(self):
        """Test that ResourceSharing domain class is importable from almaapitk."""
        from almaapitk import ResourceSharing
        self.assertIsNotNone(ResourceSharing)
        self.assertTrue(callable(ResourceSharing))

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
            expected_core = ['AlmaAPIClient', 'AlmaResponse', 'AlmaAPIError', 'AlmaValidationError']
            expected_domains = ['Admin', 'Users', 'BibliographicRecords', 'Acquisitions', 'ResourceSharing']
            for symbol in expected_core + expected_domains:
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

    def test_direct_import_style_domains(self):
        """Test that direct import style works for domain classes."""
        # This should work without errors
        from almaapitk import (
            Admin,
            Users,
            BibliographicRecords,
            Acquisitions,
            ResourceSharing,
        )
        # All should be non-None
        self.assertIsNotNone(Admin)
        self.assertIsNotNone(Users)
        self.assertIsNotNone(BibliographicRecords)
        self.assertIsNotNone(Acquisitions)
        self.assertIsNotNone(ResourceSharing)

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

    def test_module_attribute_style_domains(self):
        """Test that module attribute style works for domain classes."""
        import almaapitk
        # Access via module attributes
        admin_cls = almaapitk.Admin
        users_cls = almaapitk.Users
        bibs_cls = almaapitk.BibliographicRecords
        acq_cls = almaapitk.Acquisitions
        rs_cls = almaapitk.ResourceSharing

        self.assertIsNotNone(admin_cls)
        self.assertIsNotNone(users_cls)
        self.assertIsNotNone(bibs_cls)
        self.assertIsNotNone(acq_cls)
        self.assertIsNotNone(rs_cls)


class TestMigrationReadiness(unittest.TestCase):
    """
    Tests verifying the API surface is ready for project migration.

    These tests ensure that projects can be migrated from legacy imports
    (src.client.*, src.domains.*) to the public API (almaapitk).
    """

    def test_update_expired_users_emails_imports_available(self):
        """
        Test that all imports needed by update_expired_users_emails are available.

        The project needs: AlmaAPIClient, AlmaAPIError, AlmaValidationError, Admin, Users
        """
        from almaapitk import (
            AlmaAPIClient,
            AlmaAPIError,
            AlmaValidationError,
            Admin,
            Users,
        )
        self.assertIsNotNone(AlmaAPIClient)
        self.assertIsNotNone(AlmaAPIError)
        self.assertIsNotNone(AlmaValidationError)
        self.assertIsNotNone(Admin)
        self.assertIsNotNone(Users)

    def test_acquisitions_project_imports_available(self):
        """
        Test that all imports needed by Acquisitions projects are available.

        The projects need: AlmaAPIClient, AlmaAPIError, Acquisitions
        """
        from almaapitk import (
            AlmaAPIClient,
            AlmaAPIError,
            Acquisitions,
        )
        self.assertIsNotNone(AlmaAPIClient)
        self.assertIsNotNone(AlmaAPIError)
        self.assertIsNotNone(Acquisitions)

    def test_rialto_project_imports_available(self):
        """
        Test that all imports needed by RialtoProduction projects are available.

        The projects need: AlmaAPIClient, AlmaAPIError, Acquisitions, BibliographicRecords
        """
        from almaapitk import (
            AlmaAPIClient,
            AlmaAPIError,
            Acquisitions,
            BibliographicRecords,
        )
        self.assertIsNotNone(AlmaAPIClient)
        self.assertIsNotNone(AlmaAPIError)
        self.assertIsNotNone(Acquisitions)
        self.assertIsNotNone(BibliographicRecords)

    def test_resource_sharing_project_imports_available(self):
        """
        Test that all imports needed by ResourceSharing projects are available.

        The projects need: AlmaAPIClient, AlmaAPIError, Users, ResourceSharing
        """
        from almaapitk import (
            AlmaAPIClient,
            AlmaAPIError,
            Users,
            ResourceSharing,
        )
        self.assertIsNotNone(AlmaAPIClient)
        self.assertIsNotNone(AlmaAPIError)
        self.assertIsNotNone(Users)
        self.assertIsNotNone(ResourceSharing)


if __name__ == '__main__':
    unittest.main()
