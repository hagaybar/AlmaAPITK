"""Regenerate src/almaapitk/lab/data/alma_endpoints.json from docs/alma-swagger.

Run after refreshing the swagger snapshot: ``python -m scripts.build_lab_endpoints``.
"""
from __future__ import annotations

import json
from pathlib import Path

from almaapitk.lab.endpoints import build_index

ROOT = Path(__file__).resolve().parents[1]
SWAGGER = ROOT / "docs" / "alma-swagger"
OUT = ROOT / "src" / "almaapitk" / "lab" / "data" / "alma_endpoints.json"


def main() -> Path:
    index = build_index(SWAGGER)
    OUT.write_text(
        json.dumps(index, indent=None, separators=(",", ":"), ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return OUT


if __name__ == "__main__":
    print(main())
