"""R10 regression test for issue #207 — the ``validate=True`` guardrail
allow-set contained citation-type codes Alma can no longer digest.

Bug (real-world, SANDBOX 2026-07-22): the #194 guardrail's citation-type
allow-set kept the lending/purchase-table codes ``BOOK`` / ``JOURNAL``,
justified by a 2026-05-18 SANDBOX create that succeeded with ``BOOK``. The
#207 decomposition matrix invalidated that justification: Alma's user-side
borrowing create now answers **any** ``citation_type`` outside the RS table
``BK`` / ``CR`` / ``E_BK`` / ``E_CR`` with a raw HTTP 500 *before* field
validation (tracking-ID only, no alma_code, no errorList) — reproduced with
``BOOK``, ``JOURNAL``, and a deliberately bogus code; ``BK`` / ``E_CR`` /
``E_BK`` created cleanly under both formats. So ``validate=True`` waved
through exactly the two codes whose live failure mode is the most opaque
one the API has.

Fix: tighten ``_RS_BORROWING_CITATION_TYPE_CODES`` to the RS table
``{BK, CR, E_BK, E_CR}`` so the guardrail rejects wrong-table codes
pre-send with an error that names the field — which is the guardrail's
entire reason to exist (#194).

The opt-in philosophy is untouched: without ``validate=True`` any code is
still forwarded verbatim (Alma code tables are tenant-extensible).

Every test below fails on the pre-fix tree (``BOOK`` / ``JOURNAL`` pass
validation silently) and passes after.
"""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from almaapitk import AlmaValidationError
from almaapitk.domains.users import (
    Users,
    _RS_BORROWING_CITATION_TYPE_CODES,
)


class _MockResponse:
    def __init__(self, body: Optional[Dict[str, Any]] = None):
        self._body = body or {}
        self.success = True
        self.status_code = 200

    def json(self) -> Dict[str, Any]:
        return self._body

    @property
    def data(self) -> Dict[str, Any]:
        return self._body


class _MockClient:
    """Records POST calls so "no network call happened" can be asserted."""

    def __init__(self):
        self.environment = "SANDBOX"
        self.logger = MagicMock()
        self.calls: Dict[str, list] = {"post": []}

    def get_environment(self) -> str:
        return self.environment

    def post(self, endpoint, data=None, params=None):
        self.calls["post"].append(
            {"endpoint": endpoint, "data": data, "params": params}
        )
        return _MockResponse({"request_id": "rs-207"})


def _body(citation_code: str) -> Dict[str, Any]:
    # Synthetic values only (rule R9).
    return {
        "owner": "RS_LIB",
        "format": {"value": "PHYSICAL"},
        "citation_type": {"value": citation_code},
        "title": "Sample title",
        "year": "2024",
        "pickup_location_type": "LIBRARY",
        "pickup_location": {"value": "PICKUP_LIB"},
        "agree_to_copyright_terms": True,
    }


def test_the_allow_set_is_exactly_the_rs_table():
    # Pins the set itself: the RS borrowing citation-type table per the
    # borrowing XSD + the live 2026-07-22 matrix (#207). ``BOOK`` /
    # ``JOURNAL`` are lending/purchase-table values whose live failure mode
    # is a raw pre-validation 500.
    assert _RS_BORROWING_CITATION_TYPE_CODES == frozenset(
        {"BK", "CR", "E_BK", "E_CR"}
    )


@pytest.mark.parametrize("code", ["BOOK", "JOURNAL"])
def test_wrong_table_citation_codes_are_caught_before_the_network_call(code):
    client = _MockClient()
    users = Users(client)

    with pytest.raises(AlmaValidationError) as exc_info:
        users.create_user_rs_request(
            "u1", request_data=_body(code), validate=True
        )

    message = str(exc_info.value)
    assert "citation_type" in message, (
        "the guardrail's whole point (#194) is naming the offending field — "
        "Alma's own answer to a wrong-table citation code is a raw 500 with "
        "no message at all (#207)"
    )
    assert "BK" in message, "the message must list the accepted codes"
    assert client.calls["post"] == [], "must fail before the POST is issued"


@pytest.mark.parametrize("code", ["BK", "CR", "E_BK", "E_CR"])
def test_rs_table_citation_codes_pass_validation(code):
    # All four RS-table codes verified live (SB 2026-07-22): BK under
    # PHYSICAL, E_CR under both formats, E_BK under DIGITAL, CR in the
    # rs-borrowing-ergonomics chunk run.
    client = _MockClient()
    users = Users(client)

    users.create_user_rs_request("u1", request_data=_body(code), validate=True)

    assert len(client.calls["post"]) == 1


@pytest.mark.parametrize("code", ["BOOK", "JOURNAL", "LOCAL_TENANT_CODE"])
def test_without_validate_any_code_is_still_forwarded_verbatim(code):
    # The guardrail stays opt-in: Alma code tables are tenant-extensible,
    # so the default path must never block a code client-side.
    client = _MockClient()
    users = Users(client)

    body = _body(code)
    users.create_user_rs_request("u1", request_data=body)

    assert client.calls["post"][0]["data"] == body
