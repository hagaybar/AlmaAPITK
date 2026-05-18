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

EXPECTED_KEYS = [
    "existing_user_primary_id",
    "rs_library_code",
    "pickup_library_code",
    "fund_code",
    "shipping_cost",
]

DATA_PATH = Path(__file__).resolve().parent.parent / "test-data.json"


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

    all_ok = True
    for key in EXPECTED_KEYS:
        value = data.get(key, "")
        sval = str(value).strip() if value is not None else ""
        if not sval:
            print(f"  {key:<32s} EMPTY")
            all_ok = False
        elif sval.startswith("<") and sval.endswith(">"):
            print(f"  {key:<32s} PLACEHOLDER (still the example.json default)")
            all_ok = False
        else:
            print(f"  {key:<32s} FILLED (len={len(sval)})")

    print()
    if all_ok:
        print("  ✓ All fixtures filled. Safe to run tests.")
        return 0
    else:
        print("  ✗ One or more fixtures missing. Fill them in test-data.json before running.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
