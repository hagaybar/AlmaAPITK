"""SANDBOX smoke test for chunk pagination-helper, test t-11-2.

Confirms the migrated Acquisitions.list_invoices proof-point method still
produces a valid response against live SANDBOX data and preserves its pre-#11
public return shape ({'invoice': [...], 'total_record_count': N}) so existing
callers continue to work bit-for-bit.

Endpoint: GET /almaws/v1/acq/invoices
State-changing: no
"""

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.acquisition import Acquisitions

# Runtime fixture loader (R9 — never inline operator-supplied identifiers).
# This chunk has no fixture references in pythonCalls, but the loader stays
# for consistency with the rest of the SANDBOX-test suite.
_TEST_DATA = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent
     / "test-data.json").read_text()
)


def test_t_11_2():
    client = AlmaAPIClient("SANDBOX")
    acq = Acquisitions(client)

    result = acq.list_invoices(limit=5)

    # Legacy Alma list-payload shape is preserved.
    assert isinstance(result, dict)

    # 'invoice' key present and its value is a list.
    assert 'invoice' in result
    assert isinstance(result['invoice'], list)

    # 'total_record_count' key present.
    assert 'total_record_count' in result

    # The limit cap from the call is honoured.
    assert len(result['invoice']) <= 5

    # Every element of result['invoice'] is a dict.
    assert all(isinstance(item, dict) for item in result['invoice'])
