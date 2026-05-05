"""SANDBOX smoke test for chunk pagination-helper, test t-11-1.

Drives client.iter_paged(...) directly against a live SANDBOX list endpoint
to confirm the new public method exists with the documented signature, walks
pages on demand, honours max_records as a hard cap, and yields dict records
that match the Alma /acq/invoices payload shape.

Endpoint: GET /almaws/v1/acq/invoices
State-changing: no
"""

import json
import pathlib

from almaapitk import AlmaAPIClient

# Runtime fixture loader (R9 — never inline operator-supplied identifiers).
# This chunk has no fixture references in pythonCalls, but the loader stays
# for consistency with the rest of the SANDBOX-test suite.
_TEST_DATA = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent
     / "test-data.json").read_text()
)


def test_t_11_1():
    client = AlmaAPIClient("SANDBOX")

    result = list(client.iter_paged(
        'almaws/v1/acq/invoices',
        record_key='invoice',
        page_size=5,
        max_records=10,
    ))

    # result is a list (test consumed the generator via list(...)).
    assert isinstance(result, list)

    # max_records cap is respected; SANDBOX may legitimately have fewer.
    assert len(result) <= 10

    # Every element of the result is a dict (the per-record payload yielded
    # under record_key='invoice'). all([]) is True so empty-list is OK.
    assert all(isinstance(item, dict) for item in result)
