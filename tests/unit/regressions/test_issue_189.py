"""R10 regression test for issue #189 — no client-side 245 completeness check.

Decision recorded and implemented: ``build_alma_bib_xml`` gains an opt-in
``require_245`` gate. 245 (Title Statement) is mandatory and non-repeatable in
MARC 21, so when the gate is on, exactly one 245 must be present. The pure
builder defaults ``require_245=False`` (completeness delegated to Alma's
``validate=true``), but the network create path
(``create_record_from_fields`` / ``create_record_from_pymarc``) defaults it
``True`` — a cheap pre-flight that beats a round-trip for the most common
caller mistake (a record with no title).

These tests fail against the pre-fix code (which had no 245 check at all) and
pass once the gate exists and the create path enables it by default.
"""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from almaapitk import AlmaValidationError
from almaapitk.domains.bibs import BibliographicRecords, build_alma_bib_xml

_NO_245 = {"fields": [{"tag": "500", "subfields": [["a", "A lonely note"]]}]}
_ONE_245 = {"fields": [{"tag": "245", "ind1": "1", "ind2": "0",
                        "subfields": [["a", "A title"]]}]}
_TWO_245 = {"fields": [
    {"tag": "245", "subfields": [["a", "First"]]},
    {"tag": "245", "subfields": [["a", "Second"]]},
]}


class _MockResponse:
    def __init__(self, body=None, success=True):
        self._body = body or {}
        self.success = success
        self.status_code = 200

    def json(self):
        return self._body

    @property
    def data(self):
        return self._body


class _MockClient:
    """Records POSTs so we can assert the create path did / did not fire."""

    def __init__(self):
        self.environment = "SANDBOX"
        self.logger = MagicMock()
        self.calls: Dict[str, list] = {"post": []}

    def post(self, endpoint, data=None, params=None, content_type=None,
             custom_headers=None):
        self.calls["post"].append({"endpoint": endpoint, "data": data,
                                   "params": params})
        return _MockResponse(body={"mms_id": "99123456789"})


# --- pure builder gate ----------------------------------------------------

def test_builder_require_245_rejects_missing_title():
    with pytest.raises(AlmaValidationError):
        build_alma_bib_xml(_NO_245, require_245=True)


def test_builder_require_245_rejects_repeated_title():
    # 245 is non-repeatable; two of them is a completeness error too.
    with pytest.raises(AlmaValidationError):
        build_alma_bib_xml(_TWO_245, require_245=True)


def test_builder_require_245_accepts_exactly_one_title():
    xml = build_alma_bib_xml(_ONE_245, require_245=True)
    assert "A title" in xml


def test_builder_default_delegates_completeness_to_alma():
    # Default (False): a title-less record still builds (Alma validates).
    xml = build_alma_bib_xml(_NO_245)
    assert "A lonely note" in xml


# --- create path enables the gate by default ------------------------------

def test_create_from_fields_defaults_to_requiring_245_before_post():
    client = _MockClient()
    bibs = BibliographicRecords(client)

    with pytest.raises(AlmaValidationError):
        bibs.create_record_from_fields(_NO_245)

    assert client.calls["post"] == [], "no POST should fire when 245 is missing"


def test_create_from_fields_can_opt_out_of_245_check():
    client = _MockClient()
    bibs = BibliographicRecords(client)

    bibs.create_record_from_fields(_NO_245, require_245=False)

    assert len(client.calls["post"]) == 1, "opt-out must reach the create POST"
