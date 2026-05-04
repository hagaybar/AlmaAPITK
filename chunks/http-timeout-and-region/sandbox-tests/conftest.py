"""Shared fixtures for chunk http-timeout-and-region SANDBOX smoke tests.

Loads operator-supplied IDs from `chunks/<name>/test-data.json` or env vars,
and skips cleanly when nothing is supplied (regression-smoke contract).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


CHUNK_DIR = Path(__file__).resolve().parent.parent
TEST_DATA_PATH = CHUNK_DIR / "test-data.json"


def _load_test_data() -> dict:
    if TEST_DATA_PATH.exists():
        try:
            return json.loads(TEST_DATA_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


@pytest.fixture(scope="session")
def test_user_id() -> str:
    val = _load_test_data().get("test_user_id") or os.environ.get("TEST_USER_ID")
    if not val:
        pytest.skip(
            "test_user_id not supplied; populate chunks/http-timeout-and-region/"
            "test-data.json or set TEST_USER_ID env var"
        )
    return val


@pytest.fixture(scope="session")
def sandbox_key_present() -> None:
    if not os.environ.get("ALMA_SB_API_KEY"):
        pytest.skip("ALMA_SB_API_KEY not set; required for SANDBOX smoke")
