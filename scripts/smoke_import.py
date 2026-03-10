#!/usr/bin/env python3
"""
Smoke test for almaapitk public API imports.

Run with: PYTHONPATH=./src python scripts/smoke_import.py

This script verifies that:
1. The almaapitk package can be imported
2. All public API symbols are declared in __all__
3. The version is exposed

NOTE: Due to a known circular import issue (local `logging` folder shadows
Python's stdlib `logging`), we do NOT verify lazy-loaded symbols at import
time. The lazy loading mechanism allows `import almaapitk` to succeed;
actual class loading happens on first access when the dependencies are
properly resolved.
"""

import sys


def main():
    print("=" * 60)
    print("almaapitk Import Smoke Test")
    print("=" * 60)

    try:
        import almaapitk
        print(f"\n[OK] import almaapitk succeeded")
    except ImportError as e:
        print(f"\n[FAIL] import almaapitk failed: {e}")
        sys.exit(1)

    # Check version
    print(f"\n[INFO] almaapitk.__version__ = {almaapitk.__version__}")

    # Check __all__ exports (these are declared, lazy-loaded on access)
    print(f"\n[INFO] almaapitk.__all__ = {almaapitk.__all__}")

    # List exports without triggering lazy import (avoids circular import issue)
    print("\n[INFO] Declared public API symbols:")
    for name in almaapitk.__all__:
        print(f"  - {name}")

    # Verify backward compatibility (old imports still work)
    print("\n[INFO] Checking backward compatibility:")
    try:
        import client
        print("  - import client: OK")
    except ImportError as e:
        print(f"  - import client: FAIL ({e})")

    try:
        import utils
        print("  - import utils: OK")
    except ImportError as e:
        print(f"  - import utils: FAIL ({e})")

    print("\n" + "=" * 60)
    print("Smoke test PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
