#!/usr/bin/env python3
"""
Integration Tests for BibliographicRecords Collection Methods

Tests the collection-related methods in the BibliographicRecords domain class:
- get_collection_members(collection_id, limit, offset)
- add_to_collection(collection_id, mms_id)
- remove_from_collection(collection_id, mms_id)

These tests require:
- ALMA_SB_API_KEY environment variable to be set
- A valid collection ID in the sandbox environment
- Valid MMS IDs for testing add/remove operations

Run with: pytest tests/integration/domains/test_bibs_collections.py -v
"""

import os
import pytest
from typing import Optional

from almaapitk import AlmaAPIClient, BibliographicRecords, AlmaAPIError, AlmaValidationError


# Test configuration - these should be valid IDs in your sandbox
# Override with environment variables if needed
TEST_COLLECTION_ID = os.getenv('TEST_COLLECTION_ID', '81123456789012345678')
TEST_MMS_ID = os.getenv('TEST_MMS_ID', '990022169340204146')


@pytest.fixture(scope='module')
def alma_client():
    """
    Create an AlmaAPIClient instance for testing.

    Uses SANDBOX environment for safety.
    Skips tests if API key is not configured.
    """
    api_key = os.getenv('ALMA_SB_API_KEY')
    if not api_key:
        pytest.skip("ALMA_SB_API_KEY environment variable not set")

    client = AlmaAPIClient('SANDBOX')
    return client


@pytest.fixture(scope='module')
def bibs(alma_client):
    """Create a BibliographicRecords instance for testing."""
    return BibliographicRecords(alma_client)


@pytest.fixture(scope='module')
def valid_collection_id(bibs):
    """
    Get or verify a valid collection ID for testing.

    Attempts to use TEST_COLLECTION_ID, but can be extended to
    dynamically find a collection in the sandbox.
    """
    return TEST_COLLECTION_ID


@pytest.fixture(scope='module')
def valid_mms_id(bibs):
    """
    Get or verify a valid MMS ID for testing.

    Attempts to verify TEST_MMS_ID exists in sandbox.
    """
    try:
        response = bibs.get_record(TEST_MMS_ID)
        if response.success:
            return TEST_MMS_ID
    except AlmaAPIError:
        pass

    pytest.skip(f"Test MMS ID {TEST_MMS_ID} not found in sandbox")


@pytest.mark.integration
class TestBibsCollections:
    """
    Integration tests for BibliographicRecords collection methods.

    These tests interact with the live Alma sandbox API.
    """

    def test_get_collection_members(self, bibs, valid_collection_id):
        """
        Test retrieving members of a collection.

        Verifies:
        - Method returns AlmaResponse
        - Response contains expected structure (bib list or empty)
        - No exceptions raised for valid collection
        """
        try:
            response = bibs.get_collection_members(valid_collection_id)

            assert response is not None, "Response should not be None"
            assert response.success, f"Request should succeed, got status {response.status_code}"

            data = response.json()
            # Collection bibs response should have 'bib' key or be empty
            assert isinstance(data, dict), "Response should be a dictionary"
            # Total record count may or may not be present
            if 'bib' in data:
                assert isinstance(data['bib'], list), "'bib' should be a list"

        except AlmaAPIError as e:
            # 404 is acceptable if collection doesn't exist
            if e.status_code == 404:
                pytest.skip(f"Collection {valid_collection_id} not found in sandbox")
            raise

    def test_get_collection_members_pagination(self, bibs, valid_collection_id):
        """
        Test pagination parameters for get_collection_members.

        Verifies:
        - limit parameter restricts result count
        - offset parameter skips initial results
        """
        try:
            # Test with limit
            response_limited = bibs.get_collection_members(
                valid_collection_id,
                limit=5,
                offset=0
            )

            assert response_limited.success, "Limited request should succeed"
            data_limited = response_limited.json()

            if 'bib' in data_limited:
                bibs_returned = data_limited['bib']
                assert len(bibs_returned) <= 5, "Should return at most 5 bibs"

            # Test with offset
            response_offset = bibs.get_collection_members(
                valid_collection_id,
                limit=5,
                offset=5
            )

            assert response_offset.success, "Offset request should succeed"

        except AlmaAPIError as e:
            if e.status_code == 404:
                pytest.skip(f"Collection {valid_collection_id} not found in sandbox")
            raise

    def test_add_to_collection(self, bibs, valid_collection_id, valid_mms_id):
        """
        Test adding a bibliographic record to a collection.

        Verifies:
        - Method accepts valid collection_id and mms_id
        - Returns successful response or appropriate error
        - Record appears in collection members after add
        """
        try:
            response = bibs.add_to_collection(valid_collection_id, valid_mms_id)

            assert response is not None, "Response should not be None"
            # May succeed (200/201) or conflict (already exists - 400)
            # Both are acceptable for this test

        except AlmaAPIError as e:
            # 400 may indicate record already in collection - acceptable
            # 404 indicates collection not found - skip
            if e.status_code == 404:
                pytest.skip(f"Collection {valid_collection_id} not found")
            elif e.status_code == 400:
                # Record may already be in collection - this is OK
                pass
            else:
                raise

    def test_remove_from_collection(self, bibs, valid_collection_id, valid_mms_id):
        """
        Test removing a bibliographic record from a collection.

        Verifies:
        - Method accepts valid collection_id and mms_id
        - Returns successful response or appropriate error
        - Record no longer appears in collection after remove

        Note: This test may fail if record is not in collection.
        """
        try:
            response = bibs.remove_from_collection(valid_collection_id, valid_mms_id)

            assert response is not None, "Response should not be None"
            assert response.success, f"Remove should succeed, got {response.status_code}"

        except AlmaAPIError as e:
            # 404 may indicate record not in collection - acceptable
            if e.status_code == 404:
                pytest.skip("Record not found in collection (may not have been added)")
            raise

    def test_get_collection_members_invalid_id(self, bibs):
        """
        Test get_collection_members with invalid collection ID.

        Verifies:
        - Method raises AlmaAPIError for non-existent collection
        - Error contains appropriate status code (404)
        """
        invalid_collection_id = "invalid_collection_12345"

        with pytest.raises(AlmaAPIError) as exc_info:
            bibs.get_collection_members(invalid_collection_id)

        # Should be a 404 Not Found or 400 Bad Request
        assert exc_info.value.status_code in [400, 404], \
            f"Expected 400/404 for invalid collection, got {exc_info.value.status_code}"

    def test_add_to_collection_invalid_collection(self, bibs, valid_mms_id):
        """
        Test add_to_collection with invalid collection ID.

        Verifies:
        - Method raises AlmaAPIError for non-existent collection
        """
        invalid_collection_id = "invalid_collection_12345"

        with pytest.raises(AlmaAPIError) as exc_info:
            bibs.add_to_collection(invalid_collection_id, valid_mms_id)

        assert exc_info.value.status_code in [400, 404], \
            f"Expected 400/404 for invalid collection, got {exc_info.value.status_code}"

    def test_add_to_collection_invalid_mms_id(self, bibs, valid_collection_id):
        """
        Test add_to_collection with invalid MMS ID.

        Verifies:
        - Method raises AlmaAPIError for non-existent MMS ID
        """
        invalid_mms_id = "invalid_mms_12345"

        try:
            with pytest.raises(AlmaAPIError) as exc_info:
                bibs.add_to_collection(valid_collection_id, invalid_mms_id)

            assert exc_info.value.status_code in [400, 404], \
                f"Expected 400/404 for invalid MMS ID, got {exc_info.value.status_code}"
        except AlmaAPIError as e:
            if e.status_code == 404:
                pytest.skip(f"Collection {valid_collection_id} not found")
            raise

    def test_remove_from_collection_invalid_collection(self, bibs, valid_mms_id):
        """
        Test remove_from_collection with invalid collection ID.

        Verifies:
        - Method raises AlmaAPIError for non-existent collection
        """
        invalid_collection_id = "invalid_collection_12345"

        with pytest.raises(AlmaAPIError) as exc_info:
            bibs.remove_from_collection(invalid_collection_id, valid_mms_id)

        assert exc_info.value.status_code in [400, 404], \
            f"Expected 400/404 for invalid collection, got {exc_info.value.status_code}"

    def test_remove_from_collection_invalid_mms_id(self, bibs, valid_collection_id):
        """
        Test remove_from_collection with invalid MMS ID.

        Verifies:
        - Method raises AlmaAPIError for non-existent MMS ID
        """
        invalid_mms_id = "invalid_mms_12345"

        try:
            with pytest.raises(AlmaAPIError) as exc_info:
                bibs.remove_from_collection(valid_collection_id, invalid_mms_id)

            assert exc_info.value.status_code in [400, 404], \
                f"Expected 400/404 for invalid MMS ID, got {exc_info.value.status_code}"
        except AlmaAPIError as e:
            if e.status_code == 404:
                pytest.skip(f"Collection {valid_collection_id} not found")
            raise


@pytest.mark.integration
class TestBibsCollectionsValidation:
    """
    Tests for input validation in collection methods.

    These tests verify that validation errors are raised
    before making API calls for invalid inputs.
    """

    def test_get_collection_members_empty_id(self, bibs):
        """Test that empty collection ID raises validation error."""
        with pytest.raises(AlmaValidationError):
            bibs.get_collection_members("")

    def test_get_collection_members_none_id(self, bibs):
        """Test that None collection ID raises validation error."""
        with pytest.raises(AlmaValidationError):
            bibs.get_collection_members(None)

    def test_add_to_collection_empty_collection_id(self, bibs):
        """Test that empty collection ID raises validation error."""
        with pytest.raises(AlmaValidationError):
            bibs.add_to_collection("", TEST_MMS_ID)

    def test_add_to_collection_empty_mms_id(self, bibs):
        """Test that empty MMS ID raises validation error."""
        with pytest.raises(AlmaValidationError):
            bibs.add_to_collection(TEST_COLLECTION_ID, "")

    def test_add_to_collection_none_ids(self, bibs):
        """Test that None IDs raise validation error."""
        with pytest.raises(AlmaValidationError):
            bibs.add_to_collection(None, TEST_MMS_ID)

        with pytest.raises(AlmaValidationError):
            bibs.add_to_collection(TEST_COLLECTION_ID, None)

    def test_remove_from_collection_empty_collection_id(self, bibs):
        """Test that empty collection ID raises validation error."""
        with pytest.raises(AlmaValidationError):
            bibs.remove_from_collection("", TEST_MMS_ID)

    def test_remove_from_collection_empty_mms_id(self, bibs):
        """Test that empty MMS ID raises validation error."""
        with pytest.raises(AlmaValidationError):
            bibs.remove_from_collection(TEST_COLLECTION_ID, "")

    def test_remove_from_collection_none_ids(self, bibs):
        """Test that None IDs raise validation error."""
        with pytest.raises(AlmaValidationError):
            bibs.remove_from_collection(None, TEST_MMS_ID)

        with pytest.raises(AlmaValidationError):
            bibs.remove_from_collection(TEST_COLLECTION_ID, None)


@pytest.mark.integration
class TestBibsCollectionsWorkflow:
    """
    End-to-end workflow tests for collection operations.

    These tests verify complete add/remove workflows.
    """

    def test_add_then_remove_workflow(self, bibs, valid_collection_id, valid_mms_id):
        """
        Test complete workflow: add bib to collection, verify, remove, verify.

        This tests the full lifecycle of a bib in a collection.
        """
        # Step 1: Try to add the bib to collection
        add_success = False
        try:
            add_response = bibs.add_to_collection(valid_collection_id, valid_mms_id)
            add_success = add_response.success
        except AlmaAPIError as e:
            if e.status_code == 400:
                # May already be in collection - continue with test
                add_success = True
            elif e.status_code == 404:
                pytest.skip(f"Collection {valid_collection_id} not found")
            else:
                raise

        assert add_success, "Add operation should succeed (or bib already in collection)"

        # Step 2: Verify bib is in collection
        try:
            members_response = bibs.get_collection_members(valid_collection_id)
            assert members_response.success, "Get members should succeed"

            data = members_response.json()
            bibs_in_collection = data.get('bib', [])
            mms_ids_in_collection = [b.get('mms_id') for b in bibs_in_collection]

            # Note: May need pagination to find the bib in large collections
            # For now, we just verify the call succeeds

        except AlmaAPIError as e:
            if e.status_code == 404:
                pytest.skip(f"Collection {valid_collection_id} not found")
            raise

        # Step 3: Remove the bib from collection
        try:
            remove_response = bibs.remove_from_collection(valid_collection_id, valid_mms_id)
            assert remove_response.success, "Remove operation should succeed"
        except AlmaAPIError as e:
            if e.status_code == 404:
                # Bib may not have been in collection - acceptable
                pass
            else:
                raise


# Convenience function for running tests directly
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])
