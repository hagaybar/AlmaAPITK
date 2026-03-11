#!/usr/bin/env python3
"""
Smoke test for almaapitk public API imports.

Run with: PYTHONPATH=./src python scripts/smoke_import.py

This script verifies that:
1. The almaapitk package can be imported
2. All public API symbols are accessible (core + domains)
3. The version is exposed
4. stdlib logging is not shadowed
5. requests library is available
"""

import sys


def main():
    print("=" * 60)
    print("almaapitk Public API Smoke Test (v0.2.0)")
    print("=" * 60)

    errors = []

    # Test 1: Import almaapitk
    print("\n[TEST] Import almaapitk package...")
    try:
        import almaapitk
        print(f"  [OK] import almaapitk succeeded")
    except ImportError as e:
        print(f"  [FAIL] import almaapitk failed: {e}")
        sys.exit(1)

    # Test 2: Check version
    print("\n[TEST] Check __version__...")
    try:
        version = almaapitk.__version__
        print(f"  [OK] almaapitk.__version__ = {version}")
    except AttributeError as e:
        print(f"  [FAIL] __version__ not accessible: {e}")
        errors.append("__version__")

    # Test 3: Verify __all__ contains expected core symbols
    print("\n[TEST] Verify __all__ core exports...")
    expected_core_symbols = ["__version__", "AlmaAPIClient", "AlmaResponse", "AlmaAPIError", "AlmaValidationError"]
    actual_all = almaapitk.__all__
    print(f"  [INFO] __all__ = {actual_all}")

    for symbol in expected_core_symbols:
        if symbol in actual_all:
            print(f"  [OK] '{symbol}' in __all__")
        else:
            print(f"  [FAIL] '{symbol}' NOT in __all__")
            errors.append(f"__all__ missing {symbol}")

    # Test 3b: Verify __all__ contains expected domain symbols
    print("\n[TEST] Verify __all__ domain exports (v0.2.0)...")
    expected_domain_symbols = ["Admin", "Users", "BibliographicRecords", "Acquisitions", "ResourceSharing"]

    for symbol in expected_domain_symbols:
        if symbol in actual_all:
            print(f"  [OK] '{symbol}' in __all__")
        else:
            print(f"  [FAIL] '{symbol}' NOT in __all__")
            errors.append(f"__all__ missing {symbol}")

    # Test 4: Access each public symbol (triggers lazy import)
    print("\n[TEST] Access public API symbols...")

    try:
        client_cls = almaapitk.AlmaAPIClient
        print(f"  [OK] AlmaAPIClient: {client_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] AlmaAPIClient not accessible: {e}")
        errors.append("AlmaAPIClient")

    try:
        response_cls = almaapitk.AlmaResponse
        print(f"  [OK] AlmaResponse: {response_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] AlmaResponse not accessible: {e}")
        errors.append("AlmaResponse")

    try:
        error_cls = almaapitk.AlmaAPIError
        print(f"  [OK] AlmaAPIError: {error_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] AlmaAPIError not accessible: {e}")
        errors.append("AlmaAPIError")

    try:
        validation_cls = almaapitk.AlmaValidationError
        print(f"  [OK] AlmaValidationError: {validation_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] AlmaValidationError not accessible: {e}")
        errors.append("AlmaValidationError")

    # Test 4b: Access domain class symbols (v0.2.0)
    print("\n[TEST] Access domain class symbols (v0.2.0)...")

    try:
        admin_cls = almaapitk.Admin
        print(f"  [OK] Admin: {admin_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] Admin not accessible: {e}")
        errors.append("Admin")

    try:
        users_cls = almaapitk.Users
        print(f"  [OK] Users: {users_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] Users not accessible: {e}")
        errors.append("Users")

    try:
        bibs_cls = almaapitk.BibliographicRecords
        print(f"  [OK] BibliographicRecords: {bibs_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] BibliographicRecords not accessible: {e}")
        errors.append("BibliographicRecords")

    try:
        acq_cls = almaapitk.Acquisitions
        print(f"  [OK] Acquisitions: {acq_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] Acquisitions not accessible: {e}")
        errors.append("Acquisitions")

    try:
        rs_cls = almaapitk.ResourceSharing
        print(f"  [OK] ResourceSharing: {rs_cls}")
    except (AttributeError, ImportError) as e:
        print(f"  [FAIL] ResourceSharing not accessible: {e}")
        errors.append("ResourceSharing")

    # Test 5: Check stdlib logging is not shadowed
    print("\n[TEST] Check stdlib logging is not shadowed...")
    try:
        import logging
        assert hasattr(logging, "Formatter"), "logging.Formatter not found"
        assert hasattr(logging, "Logger"), "logging.Logger not found"
        print(f"  [OK] stdlib logging is accessible (has Formatter, Logger)")
    except (ImportError, AssertionError) as e:
        print(f"  [FAIL] stdlib logging issue: {e}")
        errors.append("stdlib logging shadowed")

    # Test 6: Check requests library
    print("\n[TEST] Check requests library...")
    try:
        import requests
        print(f"  [OK] requests library available (version: {requests.__version__})")
    except ImportError as e:
        print(f"  [FAIL] requests not available: {e}")
        errors.append("requests")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"Smoke test FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        print("=" * 60)
        sys.exit(1)
    else:
        print("Smoke test PASSED - All public API symbols accessible")
        print("=" * 60)
        sys.exit(0)


if __name__ == "__main__":
    main()
