"""SANDBOX smoke test for chunk pagination-helper, test t-11-3.

Confirms the migrated Acquisitions.search_invoices proof-point method
still produces valid results against live SANDBOX data after being
rewired to client.iter_paged. Replaces the original /bibs-based test:
GET /almaws/v1/bibs is identifier-only and rejects q= queries (HTTP
400, errorCode 401873), so it cannot validate iter_paged() against a
paginated search. /acq/invoices genuinely supports q= + offset
pagination, which is what iter_paged() is for.

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


def test_t_11_3():
    client = AlmaAPIClient("SANDBOX")
    acq = Acquisitions(client)

    result = acq.search_invoices(query="invoice_status~ACTIVE", limit=5)

    # Migrated method preserves the legacy Alma list payload shape.
    assert isinstance(result, dict)
    assert "invoice" in result
    assert "total_record_count" in result

    invoices = result["invoice"]
    assert isinstance(invoices, list)

    # The limit cap from the call is honoured (SANDBOX may legitimately
    # return fewer hits, including zero).
    assert len(invoices) <= 5

    # Every element of invoices, when present, is a dict.
    # all([]) is True so empty-list naturally passes.
    assert all(isinstance(item, dict) for item in invoices)
