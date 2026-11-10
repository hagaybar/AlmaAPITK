"""SANDBOX smoke for Alma Lab (issue #230). Opt-in, not a release gate.

Runs one read through the headless command against the live Sandbox and checks
the evidence record. Needs ALMA_SB_API_KEY; refuses to run with
ALMA_PROD_API_KEY set (repo rule R8).
"""
from __future__ import annotations

import json
import os

import pytest

from almaapitk.lab.cli import main

pytestmark = [
    pytest.mark.skipif(not os.environ.get("ALMA_SB_API_KEY"), reason="needs ALMA_SB_API_KEY"),
]


def test_headless_read_leaves_evidence(tmp_path, capsys):
    if os.environ.get("ALMA_PROD_API_KEY"):
        pytest.fail("R8: unset ALMA_PROD_API_KEY before running SANDBOX tooling")
    code = main(["call", "admin.list_sets", "--expect", "status == 200",
                 "--evidence-dir", str(tmp_path), "--json"])
    record = json.loads(capsys.readouterr().out)
    assert code == 0, record.get("error")
    assert record["environment"] == "SANDBOX"
    assert record["requests"] and record["requests"][0]["headers"]["Authorization"] == "apikey ***"
    assert os.environ["ALMA_SB_API_KEY"] not in json.dumps(record)
    assert list(tmp_path.glob("*/*.json"))
