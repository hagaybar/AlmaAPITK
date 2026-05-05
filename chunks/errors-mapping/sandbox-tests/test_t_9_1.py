"""SANDBOX smoke test for chunk errors-mapping, test t-9-1.

Covers acceptance criteria (issue #9 + #10):
    - Alma error codes dispatch to typed ``AlmaAPIError`` subclasses.
    - Typed subclass still satisfies ``isinstance(_, AlmaAPIError)`` so
      existing broad except-blocks keep catching it.
    - ``tracking_id`` and ``alma_code`` are populated from the live payload.

Live SANDBOX returns HTTP 400 + errorCode 401861 ("User with identifier ...
was not found") for a missing user_primary_id — NOT HTTP 404 — so dispatch
is via the explicit registry entry for ``401861``, not the status fallback.
"""

import os

import pytest

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError, AlmaResourceNotFoundError
from almaapitk.domains.users import Users


def test_t_9_1_invalid_user_primary_id_raises_typed_not_found_with_metadata():
    if not os.environ.get("ALMA_SB_API_KEY"):
        pytest.skip("ALMA_SB_API_KEY not set")

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)

    with pytest.raises(AlmaAPIError) as exc_info:
        users.get_user("xxxxx")

    raised = exc_info.value
    assert raised is not None

    # Registry dispatch: 401861 -> AlmaResourceNotFoundError.
    assert isinstance(raised, AlmaResourceNotFoundError), (
        f"Expected AlmaResourceNotFoundError (via 401861 registry entry), "
        f"got {type(raised).__name__}: {raised!r}"
    )
    # Backward-compat: typed subclass is still an AlmaAPIError.
    assert isinstance(raised, AlmaAPIError) is True

    # Issue #10: tracking_id and alma_code propagated from the live payload.
    assert isinstance(raised.tracking_id, str) and raised.tracking_id != "", (
        f"tracking_id should be a non-empty string, got {raised.tracking_id!r}"
    )
    assert raised.alma_code == "401861", (
        f"alma_code should be the live errorCode '401861', got {raised.alma_code!r}"
    )
