"""Smoke test 03: fetch Alma Analytics report headers.

Important: Alma Analytics has a single shared DB accessible only via
PRODUCTION credentials. SANDBOX has no analytics endpoint. This script
therefore uses ALMA_PROD_API_KEY (not ALMA_SB_API_KEY).
"""
import json
import pathlib
from almaapitk import AlmaAPIClient, Analytics

cfg = json.loads(pathlib.Path(__file__).parent.joinpath("smoke_config.json").read_text())
client = AlmaAPIClient("PRODUCTION")
analytics = Analytics(client)
headers = analytics.get_report_headers(cfg["analytics_report_path"])
assert headers, "no headers returned"
print(f"OK: got {len(headers)} headers")
