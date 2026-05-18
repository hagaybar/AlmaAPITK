"""Presence-check for chunks/users-requests-followup/test-data.json.

Verifies each expected fixture key is present and not a placeholder, WITHOUT
ever printing the values themselves. Designed to be safe for the agent to
invoke: the output reveals only key names + FILLED/EMPTY/PLACEHOLDER + value
length, never the value content.

Exit codes:
  0 — all fixtures filled, ready to run tests
  1 — one or more fixtures empty or still a placeholder
  2 — test-data.json missing entirely
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Fixtures that MUST be filled for the round-trip tests to work.
REQUIRED_KEYS = [
    "existing_user_primary_id",
    "rs_library_code",
    "pickup_library_code",
]

# Fixtures that are optional per the Alma swagger. The test scripts pass
# them only when filled; empty / null / "None" / placeholder means "omit
# from the API call." Listed so the operator sees them in the check
# output without them gating the test run.
OPTIONAL_KEYS = [
    "fund_code",       # update_shipping query param; required=False
    "shipping_cost",   # update_shipping query param; required=False
]

DATA_PATH = Path(__file__).resolve().parent.parent / "test-data.json"


def _classify(value) -> str:
    """Return one of FILLED, EMPTY, PLACEHOLDER, SKIP, never the value
    itself."""
    if value is None:
        return "SKIP (JSON null)"
    sval = str(value).strip()
    if not sval:
        return "EMPTY"
    if sval.startswith("<") and sval.endswith(">"):
        return "PLACEHOLDER (still the example.json default)"
    if sval.lower() in {"none", "null"}:
        return "SKIP (sentinel)"
    return f"FILLED (len={len(sval)})"


def main() -> int:
    if not DATA_PATH.exists():
        print(f"  ERROR: {DATA_PATH} does not exist.")
        print(f"         cp {DATA_PATH.parent}/test-data.example.json {DATA_PATH}")
        print(f"         and fill the placeholders in your editor.")
        return 2

    try:
        data = json.loads(DATA_PATH.read_text())
    except json.JSONDecodeError as e:
        print(f"  ERROR: {DATA_PATH} is not valid JSON: {e}")
        return 2

    required_ok = True
    print("  Required:")
    for key in REQUIRED_KEYS:
        status = _classify(data.get(key))
        print(f"    {key:<30s} {status}")
        if not status.startswith("FILLED"):
            required_ok = False

    print()
    print("  Optional (omitted from API call when SKIP / EMPTY / PLACEHOLDER):")
    for key in OPTIONAL_KEYS:
        status = _classify(data.get(key))
        print(f"    {key:<30s} {status}")

    print()
    if required_ok:
        print("  ✓ Required fixtures filled. Safe to run tests.")
        return 0
    else:
        print("  ✗ One or more required fixtures missing. Fill them before running.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
