"""SANDBOX smoke test for chunk errors-mapping, test t-10-1.

Covers acceptance criteria (issue #10):
    - "`AlmaAPIError` exposes `tracking_id` and `alma_code` attributes
      (both default-initialized)."
    - "`_handle_response` populates them from the response payload when
      present."

This test fires a real GET against Alma SANDBOX with a synthetic invalid
mms_id to deliberately trigger an error response. It asserts that the
parsed `trackingId` / `errorCode` from the live JSON payload are
propagated onto the raised typed exception as `tracking_id` and
`alma_code`.
"""

import os

import pytest

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.bibs import BibliographicRecords


def test_t_10_1_invalid_mms_id_propagates_tracking_id_and_alma_code():
    """GET on a synthetic invalid mms_id raises an AlmaAPIError whose
    `tracking_id` and `alma_code` were populated from the live Alma
    error payload (both non-empty strings)."""
    if not os.environ.get("ALMA_SB_API_KEY"):
        pytest.skip("ALMA_SB_API_KEY not set")

    client = AlmaAPIClient(environment="SANDBOX")
    bibs = BibliographicRecords(client)

    with pytest.raises(AlmaAPIError) as exc_info:
        bibs.get_record("3434343434")

    raised = exc_info.value
    assert raised is not None
    assert isinstance(raised, AlmaAPIError) is True

    # Both attributes must exist on AlmaAPIError (default-initialized per AC).
    assert hasattr(raised, "tracking_id") is True
    assert hasattr(raised, "alma_code") is True

    # Alma populates trackingId on real error responses — must be a non-empty str.
    assert isinstance(raised.tracking_id, str), (
        f"tracking_id should be a string, got {type(raised.tracking_id).__name__}: "
        f"{raised.tracking_id!r}"
    )
    assert raised.tracking_id != "", "tracking_id should be non-empty on a live Alma error"

    # Alma populates errorCode on real error responses — must be a non-empty str.
    assert isinstance(raised.alma_code, str), (
        f"alma_code should be a string, got {type(raised.alma_code).__name__}: "
        f"{raised.alma_code!r}"
    )
    assert raised.alma_code != "", "alma_code should be non-empty on a live Alma error"
