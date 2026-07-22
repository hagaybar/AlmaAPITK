"""Regression tests for issue #209.

``40166411`` was mapped to ``AlmaInvalidPolModeError`` (a purchase-order-line
exception) on every surface except the user resource-sharing endpoints
(special-cased in issue #194). Live SANDBOX repro (2026-07-22):
``GET /almaws/v1/bibs/collections/{bad-pid}/bibs`` returns HTTP 400 with
alma_code 40166411 ("The parameter pid is invalid") and was raised as a POL
exception on a bibs call.

The swagger snapshot (docs/alma-swagger, 2026-05-29) shows the code is
published by five domains — acq, bibs, conf, partners, users — and in ALL of
them, acq included, the description is the generic "Param(eter) value is
invalid". The POL-mode meaning is the narrow exception, so classification is
inverted: POL meaning only on the acq surface (and for URL-less legacy
calls, preserving the issue-#194 pins), plain ``AlmaAPIError`` elsewhere.
"""

import pytest

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import (
    AlmaAPIError,
    AlmaInvalidPolModeError,
)

_BASE = "https://api-eu.hosted.exlibrisgroup.com/almaws/v1"


@pytest.fixture(scope="module")
def client():
    return AlmaAPIClient("SANDBOX")


@pytest.mark.parametrize(
    "url",
    [
        f"{_BASE}/bibs/collections/81000000000000000000/bibs",
        f"{_BASE}/conf/libraries/MAIN/locations/STACKS",
        f"{_BASE}/partners/SOME_PARTNER/lending-requests",
        f"{_BASE}/users/u1/resource-sharing-requests/rs-1?op=cancel",
    ],
)
def test_40166411_is_generic_off_the_acq_surface(client, url):
    exc_class = client._classify_error(400, "40166411", url)
    assert exc_class is AlmaAPIError
    assert exc_class is not AlmaInvalidPolModeError


def test_40166411_keeps_pol_meaning_on_the_acq_surface(client):
    assert (
        client._classify_error(
            400, "40166411", f"{_BASE}/acq/po-lines/POL-1"
        )
        is AlmaInvalidPolModeError
    )


def test_40166411_without_a_url_keeps_the_legacy_pol_default(client):
    # Backward compat: direct callers that classify without a URL keep the
    # historical mapping (also pinned by tests/unit/regressions/
    # test_issue_194.py).
    assert (
        client._classify_error(400, "40166411") is AlmaInvalidPolModeError
    )
