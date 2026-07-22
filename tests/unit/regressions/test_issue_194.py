"""R10 regression test for issue #194 — no guardrail against wrong code-table
values on the RS-borrowing create path.

Bug (real-world, SANDBOX 2026-07-19): ``Users.create_user_rs_request`` forwards
``request_data`` verbatim and validates no code-table *values*. Sending a value
from the wrong Alma code table — ``format: {"value": "P"}``, the
*purchase-request* code, on the **borrowing** endpoint, which wants
``PHYSICAL`` / ``DIGITAL`` — makes Alma answer with::

    Invalid field value. Field: [Ljava.lang.Object;@2f3cde3, Value: {1}

``[Ljava.lang.Object;@…`` is a Java array's ``toString()`` and ``{1}`` is an
unsubstituted message-template placeholder: Alma itself fails to render *which*
field is bad, so the developer gets no signal at all and burns a trial-and-error
loop. The same payload with ``format: {"value": "PHYSICAL"}`` succeeds.

Two guardrails, both from the issue's option list:

* **Option 1 (client)** — detect the mangled message shape and append an
  actionable ``[almaapitk hint: …]`` naming the likely culprits for the called
  endpoint. Message-only; the exception type is untouched.
* **Option 2 (domain)** — opt-in ``validate=True`` pre-flight check of the
  well-known borrowing code-table fields, raising ``AlmaValidationError`` that
  *names the field*. Opt-in because Alma code tables are tenant-extensible.

Also pinned here: the two ``ERROR_CODE_REGISTRY`` findings cross-checked against
``chunks/rs-borrowing-ergonomics/_swagger_errors_194.json`` — the newly mapped
``401890`` and the ``40166411`` cross-domain collision.

Every test below fails on the pre-fix tree (no hint text, no ``validate``
kwarg, no ``401890`` mapping) and passes after.
"""

import os
import unittest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
import requests

from almaapitk import AlmaAPIClient, AlmaValidationError
from almaapitk.client.AlmaAPIClient import (
    AlmaAPIError,
    AlmaInvalidPolModeError,
    AlmaResourceNotFoundError,
    ERROR_CODE_REGISTRY,
)
from almaapitk.domains.users import Users

#: The exact message Alma returned in the reproduction, verbatim.
MANGLED_ALMA_MESSAGE = (
    "Invalid field value. Field: [Ljava.lang.Object;@2f3cde3, Value: {1}"
)

RS_CREATE_URL = (
    "https://api-eu.hosted.exlibrisgroup.com/almaws/v1/users/u1/"
    "resource-sharing-requests"
)


# ---------------------------------------------------------------------------
# Option 2 — opt-in soft validation (domain layer)
# ---------------------------------------------------------------------------


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
        return _MockResponse({"request_id": "rs-194"})


#: The reproduction payload from the issue, minus the operator's real
#: identifiers (rule R9).
def _repro_body(format_code: str = "P") -> Dict[str, Any]:
    return {
        "owner": "RS_LIB",
        "format": {"value": format_code},
        # The original #194 reproduction used BOOK; changed to BK after the
        # #207 tightening removed the wrong-table codes from the allow-set
        # (see tests/unit/regressions/test_issue_207.py).
        "citation_type": {"value": "BK"},
        "title": "Sample title",
        "pickup_location_type": "LIBRARY",
        "pickup_location": {"value": "PICKUP_LIB"},
        "agree_to_copyright_terms": True,
    }


def test_wrong_format_code_is_caught_before_the_network_call():
    client = _MockClient()
    users = Users(client)

    with pytest.raises(AlmaValidationError) as exc_info:
        users.create_user_rs_request(
            "u1", request_data=_repro_body("P"), validate=True
        )

    message = str(exc_info.value)
    assert "format" in message, (
        "the whole point of #194 is that the error names the offending "
        "field — Alma's own error does not"
    )
    assert "PHYSICAL" in message and "DIGITAL" in message
    assert client.calls["post"] == [], "must fail before the POST is issued"


def test_the_same_payload_with_the_right_code_is_sent_verbatim():
    client = _MockClient()
    users = Users(client)

    body = _repro_body("PHYSICAL")
    users.create_user_rs_request("u1", request_data=body, validate=True)

    assert client.calls["post"][0]["data"] == body


def test_validation_is_opt_in_so_tenant_extended_codes_still_work():
    # Alma code tables are tenant-extensible: an institution with a local
    # ``format`` code must never be blocked client-side. Default = off.
    client = _MockClient()
    users = Users(client)

    body = _repro_body("LOCAL_CUSTOM_FORMAT")
    users.create_user_rs_request("u1", request_data=body)

    assert client.calls["post"][0]["data"] == body


@pytest.mark.parametrize("code", ["BK", "CR"])
def test_citation_type_ambiguity_is_not_silently_resolved(code):
    # The borrowing XSD lists BK/CR. This test originally also accepted BOOK
    # (a 2026-05-18 SANDBOX create passed with it, so the sources conflicted
    # and the check refused to pick a side). The conflict was RESOLVED by the
    # 2026-07-22 decomposition matrix (#207): BOOK/JOURNAL are wrong-table
    # codes that Alma now answers with a raw pre-validation 500, so they were
    # removed from the allow-set — see test_issue_207.py for the pin.
    client = _MockClient()
    users = Users(client)

    users.create_user_rs_request(
        "u1",
        request_data={
            "format": {"value": "DIGITAL"},
            "citation_type": {"value": code},
        },
        validate=True,
    )

    assert len(client.calls["post"]) == 1


@pytest.mark.parametrize("code", ["E_CR", "E_BK"])
def test_electronic_citation_type_codes_pass_validation(code):
    # Live SANDBOX evidence (2026-07-22, chunk rs-borrowing-ergonomics test
    # run): citation_type E_CR ("Electronic Article") is ACCEPTED by Alma on
    # a real borrowing-request create — it sits in the same
    # ReadingListCitationTypes code table as BK/CR (E_BK is its book
    # sibling). The original guardrail set lacked both, so validate=True
    # wrongly rejected a request shape Alma demonstrably accepts.
    client = _MockClient()
    users = Users(client)

    users.create_user_rs_request(
        "u1",
        request_data={
            "format": {"value": "DIGITAL"},
            "citation_type": {"value": code},
        },
        validate=True,
    )

    assert len(client.calls["post"]) == 1


# ---------------------------------------------------------------------------
# Option 1 — better error surfacing (client layer)
# ---------------------------------------------------------------------------


def _mangled_error_response(url: str, message: str = MANGLED_ALMA_MESSAGE):
    """Build a ``requests.Response`` double carrying Alma's mangled error."""
    response = MagicMock(spec=requests.Response)
    response.status_code = 400
    response.ok = False
    response.headers = {"content-type": "application/json"}
    response.text = ""
    response.url = url
    response.json.return_value = {
        "errorsExist": True,
        "errorList": {
            "error": [
                {
                    "errorCode": "401652",
                    "errorMessage": message,
                    "trackingId": "test-tracking-id",
                }
            ]
        },
    }
    return response


class TestMangledErrorHint(unittest.TestCase):
    """The dead-end Alma message must become actionable (issue #194)."""

    def setUp(self):
        patcher = patch.dict(
            os.environ, {"ALMA_SB_API_KEY": "test-sandbox-key"}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = AlmaAPIClient("SANDBOX")

    def _post_and_capture(self, url: str, message: str = MANGLED_ALMA_MESSAGE):
        with patch.object(
            self.client._session,
            "request",
            return_value=_mangled_error_response(url, message),
        ):
            with self.assertRaises(AlmaAPIError) as ctx:
                self.client.post(
                    "almaws/v1/users/u1/resource-sharing-requests",
                    data={"format": {"value": "P"}},
                )
        return ctx.exception

    def test_rs_borrowing_hint_names_the_likely_culprits(self):
        exc = self._post_and_capture(RS_CREATE_URL)
        message = str(exc)

        # Alma's own text is preserved verbatim ...
        self.assertIn(MANGLED_ALMA_MESSAGE, message)
        # ... and the hint tells the developer where to look.
        self.assertIn("almaapitk hint", message)
        self.assertIn("format", message)
        self.assertIn("PHYSICAL/DIGITAL", message)
        self.assertIn("citation_type", message)

    def test_hint_does_not_change_the_exception_type_or_attributes(self):
        exc = self._post_and_capture(RS_CREATE_URL)

        # Purely additive: classification, status and the support-facing
        # identifiers are untouched.
        self.assertIs(type(exc), AlmaAPIError)
        self.assertEqual(exc.status_code, 400)
        self.assertEqual(exc.alma_code, "401652")
        self.assertEqual(exc.tracking_id, "test-tracking-id")

    def test_generic_hint_on_other_endpoints(self):
        exc = self._post_and_capture(
            "https://api-eu.hosted.exlibrisgroup.com/almaws/v1/acq/invoices"
        )
        message = str(exc)

        self.assertIn("almaapitk hint", message)
        # The RS-specific culprit list must not leak onto unrelated surfaces.
        self.assertNotIn("PHYSICAL/DIGITAL", message)

    def test_well_rendered_alma_errors_are_left_alone(self):
        # Alma named the field: the message is already actionable and must not
        # be decorated.
        exc = self._post_and_capture(
            RS_CREATE_URL, "Invalid field value. Field: format, Value: P"
        )

        self.assertNotIn("almaapitk hint", str(exc))


# ---------------------------------------------------------------------------
# ERROR_CODE_REGISTRY cross-check against the #194 swagger error sidecar
# ---------------------------------------------------------------------------


class TestErrorRegistryCrossCheck(unittest.TestCase):
    """Findings from ``_swagger_errors_194.json`` (users domain)."""

    def setUp(self):
        patcher = patch.dict(
            os.environ, {"ALMA_SB_API_KEY": "test-sandbox-key"}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = AlmaAPIClient("SANDBOX")

    def test_401890_user_not_found_is_mapped(self):
        # HTTP 400 (not 404), so the status fallback never fires — exactly the
        # reason its near-twin 401861 was mapped explicitly.
        self.assertIs(
            ERROR_CODE_REGISTRY.get("401890"), AlmaResourceNotFoundError
        )
        self.assertIs(
            self.client._classify_error(400, "401890"),
            AlmaResourceNotFoundError,
        )

    def test_40166411_keeps_its_pol_meaning_off_the_rs_surface(self):
        self.assertIs(
            self.client._classify_error(400, "40166411"),
            AlmaInvalidPolModeError,
        )
        self.assertIs(
            self.client._classify_error(
                400,
                "40166411",
                "https://api-eu.hosted.exlibrisgroup.com/almaws/v1/acq/"
                "po-lines/POL-1",
            ),
            AlmaInvalidPolModeError,
        )

    def test_40166411_on_the_rs_surface_is_not_a_pol_mode_error(self):
        # The users swagger publishes 40166411 as the generic "Parameter value
        # is invalid." on POST /users/{id}/resource-sharing-requests/{rid}.
        exc_class = self.client._classify_error(
            400,
            "40166411",
            "https://api-eu.hosted.exlibrisgroup.com/almaws/v1/users/u1/"
            "resource-sharing-requests/rs-1?op=cancel",
        )

        self.assertIs(exc_class, AlmaAPIError)
        self.assertNotEqual(exc_class, AlmaInvalidPolModeError)
