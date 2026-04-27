"""Smoke test 01: confirm SANDBOX auth works.

Reads ALMA_SB_API_KEY from environment.
"""
from almaapitk import AlmaAPIClient

client = AlmaAPIClient("SANDBOX")
client.test_connection()  # raises AlmaAPIError on failure; success is silent
print("OK: test_connection passed")
