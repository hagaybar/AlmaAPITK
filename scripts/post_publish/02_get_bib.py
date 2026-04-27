"""Smoke test 02: fetch a known SANDBOX bib record.

Reads ALMA_SB_API_KEY and scripts/post_publish/smoke_config.json.
"""
import json
import pathlib
from almaapitk import AlmaAPIClient, BibliographicRecords

cfg = json.loads(pathlib.Path(__file__).parent.joinpath("smoke_config.json").read_text())
client = AlmaAPIClient("SANDBOX")
bibs = BibliographicRecords(client)
result = bibs.get_record(cfg["sandbox_mms_id"])
assert result is not None, f"get_record returned None for {cfg['sandbox_mms_id']}"
print(f"OK: got bib {cfg['sandbox_mms_id']}")
