"""Load synthetic smoke inputs from a gitignored JSON file.

Workflow smokes read environment-specific values (a test user id, an
analytics report path, …) through :func:`smoke_input`. The values live in a
gitignored ``smoke-data.json`` so real identifiers never reach the repo (R9).
The file path is overridable via ``ALMA_SMOKE_DATA``. See issue #156.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class MissingTestInput(KeyError):
    """Raised when a requested smoke input (or its file) is absent."""


def _path() -> Path:
    return Path(os.getenv("ALMA_SMOKE_DATA", "smoke-data.json"))


def smoke_input(key: str) -> Any:
    """Return the synthetic value for ``key`` from the smoke-data file.

    Raises :class:`MissingTestInput` with actionable guidance when the file
    or the key is missing.
    """
    path = _path()
    if not path.exists():
        raise MissingTestInput(
            f"smoke data file not found at {path}. Copy smoke-data.example.json "
            "to smoke-data.json (gitignored) and fill in synthetic values."
        )
    data = json.loads(path.read_text())
    if key not in data:
        raise MissingTestInput(f"missing smoke input {key!r} in {path}")
    return data[key]
