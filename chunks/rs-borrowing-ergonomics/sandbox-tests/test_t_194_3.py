"""t-194-3: network-free smoke — error-surfacing internals (issue #194).

Pins, against the shipped build, the two client-side behaviours t-194-2
can only sample once: (a) the mangled-message detector and its
endpoint-scoped hint selection, and (b) the error-code classification
changes. Exercises: the RS-borrowing hint on the resource-sharing
surface; the generic hint elsewhere; a well-rendered Alma error (one
that DOES name its field) left completely untouched; unrelated messages
returned unchanged; the 40166411 collision resolved endpoint-scoped
(acquisitions AlmaInvalidPolModeError meaning kept by default, plain
AlmaAPIError on the RS surface); and 401890 mapped to
AlmaResourceNotFoundError despite arriving as HTTP 400.

All calls are pure functions over strings — no HTTP request is issued
and no SANDBOX state is read or mutated. The '<user_primary_id>' in the
URL below is a literal synthetic placeholder, exactly as prescribed by
the test recommendation (R9: no operator fixture values are needed or
used).
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

# Fixtures are loaded at RUNTIME from the gitignored test-data.json —
# never inlined at generation time (R9). This test is fixture-free (pure
# string functions under test); the loader is tolerant so the smoke
# stays runnable when the operator-filled file is absent.
_TEST_DATA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
)
_TEST_DATA = (
    json.loads(_TEST_DATA_PATH.read_text()) if _TEST_DATA_PATH.exists() else {}
)

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import (
    ERROR_CODE_REGISTRY,
    AlmaAPIError,
    AlmaInvalidPolModeError,
    AlmaResourceNotFoundError,
    _augment_code_table_error_message,
)

TEST_NAME = "t-194-3"


def test_t_194_3() -> None:
    if "ALMA_SB_API_KEY" not in os.environ:
        pytest.skip("ALMA_SB_API_KEY not set (needed to construct the client)")

    # Constructing the client performs no HTTP; SANDBOX only, never PROD.
    client = AlmaAPIClient("SANDBOX")

    rs_url = (
        "https://api-eu.hosted.exlibrisgroup.com/almaws/v1/users/"
        "<user_primary_id>/resource-sharing-requests"
    )
    rs_action_url = rs_url + "/00000000000000"
    other_url = (
        "https://api-eu.hosted.exlibrisgroup.com/almaws/v1/acq/po-lines/"
        "POL-00000"
    )

    # --- (a) mangled-message detector + endpoint-scoped hint ------------
    mangled = "Invalid field value. Field: [Ljava.lang.Object;@2f3cde3, Value: {1}"
    rs_hinted = _augment_code_table_error_message(mangled, rs_url)
    generic_hinted = _augment_code_table_error_message(mangled, other_url)

    assert rs_hinted.startswith(mangled)
    for needle in (
        "[almaapitk hint:",
        "PHYSICAL/DIGITAL",
        "BK/CR",
        "build_user_rs_request",
        "validate=True",
    ):
        assert needle in rs_hinted, f"RS hint is missing {needle!r}"

    assert "[almaapitk hint:" in generic_hinted
    assert "PHYSICAL/DIGITAL" not in generic_hinted, (
        "the hint is not endpoint-scoped: RS-specific culprits leaked into "
        "the generic hint"
    )

    # A well-rendered Alma error that DID name its field gets no hint:
    # purely additive, never degrading.
    well_rendered = "Invalid field value. Field: format, Value: P"
    untouched = _augment_code_table_error_message(well_rendered, rs_url)
    assert untouched == well_rendered

    # Messages that are not the mangled shape are returned unchanged.
    unrelated_in = "User with identifier X of type Y was not found."
    unrelated_out = _augment_code_table_error_message(unrelated_in, rs_url)
    assert unrelated_out == unrelated_in

    # --- (b) error-code classification ----------------------------------
    pol_default = client._classify_error(400, "40166411", None)
    pol_on_rs = client._classify_error(400, "40166411", rs_action_url)
    user_not_found = client._classify_error(400, "401890", rs_url)
    registry_401890 = ERROR_CODE_REGISTRY.get("401890")
    registry_40166411 = ERROR_CODE_REGISTRY.get("40166411")

    print(
        f"[{TEST_NAME}] pol_default={pol_default.__name__} "
        f"pol_on_rs={pol_on_rs.__name__} "
        f"user_not_found={user_not_found.__name__}"
    )

    # Off the RS surface, 40166411 keeps its acquisitions meaning.
    assert pol_default is AlmaInvalidPolModeError
    # On the RS surface the collision is resolved: a bad parameter is not
    # reported as a POL-mode error.
    assert pol_on_rs is AlmaAPIError
    assert pol_on_rs is not AlmaInvalidPolModeError
    # 401890 is mapped despite arriving as HTTP 400 (so the 404 status
    # fallback never fires for it).
    assert user_not_found is AlmaResourceNotFoundError
    assert registry_401890 is AlmaResourceNotFoundError
    # The registry default is unchanged; only the endpoint-scoped override
    # differs.
    assert registry_40166411 is AlmaInvalidPolModeError

    # No HTTP request was issued and no SANDBOX state was read or mutated.
    print(f"[{TEST_NAME}] done: hint selection and classification verified")
