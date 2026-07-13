"""R10 regression test for issue #190 — get_marc_subfield hid fetch failures
and could not read control fields.

Two problems pinned here:

1. **Silent empty list on failure.** ``get_marc_subfield`` caught *all*
   exceptions and returned ``[]`` so batch jobs continue — but a caller then
   could not tell "the subfield is genuinely absent" from "the record fetch /
   MARC parse failed." The fix adds a ``strict`` flag: default ``False`` keeps
   the swallow-and-continue behaviour; ``strict=True`` re-raises fetch/parse
   failures while still returning ``[]`` for a genuine absence.

2. **Control fields unreadable, silently.** ``_extract_marc_subfield_values``
   searches ``<datafield>`` only; a 00X control-field tag could only ever yield
   ``[]``. The fix rejects 00X tags with a clear ``AlmaValidationError`` instead
   of a misleading empty list.

These fail against the pre-fix code (which returned ``[]`` for every failure
mode and accepted 00X tags) and pass after the fix.
"""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from almaapitk import AlmaValidationError
from almaapitk.domains.bibs import BibliographicRecords

_MMS = "99123456789"
_GOOD_MARC = (
    "<record>"
    "<leader>00000nam a2200000 a 4500</leader>"
    '<datafield tag="245" ind1="1" ind2="0">'
    '<subfield code="a">A test title</subfield></datafield>'
    '<datafield tag="907" ind1=" " ind2=" ">'
    '<subfield code="e">campus-A</subfield></datafield>'
    "</record>"
)


class _MockResponse:
    def __init__(self, body=None, success=True):
        self._body = body or {}
        self.success = success
        self.status_code = 200

    def json(self):
        return self._body


class _MockClient:
    def __init__(self, get_response: "_MockResponse"):
        self.environment = "SANDBOX"
        self.logger = MagicMock()
        self._get_response = get_response
        self.calls: Dict[str, list] = {"get": []}

    def get(self, endpoint, params: Optional[Dict[str, Any]] = None):
        self.calls["get"].append({"endpoint": endpoint, "params": params})
        return self._get_response


def _bibs(get_response):
    client = _MockClient(get_response)
    return BibliographicRecords(client), client


# --- control-field tags are rejected, not silently empty ------------------

@pytest.mark.parametrize("control_tag", ["001", "003", "008", "005"])
def test_control_field_tag_rejected_with_clear_error(control_tag):
    bibs, client = _bibs(_MockResponse(body={"anies": [_GOOD_MARC]}))
    with pytest.raises(AlmaValidationError):
        bibs.get_marc_subfield(_MMS, control_tag, "a")
    assert client.calls["get"] == [], "must reject before any fetch"


# --- genuine absence returns [] in both modes -----------------------------

def test_absent_subfield_returns_empty_even_in_strict():
    bibs, _ = _bibs(_MockResponse(body={"anies": [_GOOD_MARC]}))
    # 907 exists but has no $z — genuinely absent, not an error.
    assert bibs.get_marc_subfield(_MMS, "907", "z") == []
    assert bibs.get_marc_subfield(_MMS, "907", "z", strict=True) == []


def test_present_subfield_returns_values():
    bibs, _ = _bibs(_MockResponse(body={"anies": [_GOOD_MARC]}))
    assert bibs.get_marc_subfield(_MMS, "907", "e") == ["campus-A"]


# --- fetch failure: swallowed by default, surfaced under strict -----------

def test_fetch_failure_returns_empty_by_default():
    bibs, _ = _bibs(_MockResponse(body={}, success=False))
    assert bibs.get_marc_subfield(_MMS, "907", "e") == []


def test_fetch_failure_raises_in_strict_mode():
    bibs, _ = _bibs(_MockResponse(body={}, success=False))
    with pytest.raises(Exception):
        bibs.get_marc_subfield(_MMS, "907", "e", strict=True)


# --- unparseable MARC: swallowed by default, surfaced under strict --------

def test_unparseable_marc_returns_empty_by_default():
    bibs, _ = _bibs(_MockResponse(body={"anies": ["<record><not-closed"]}))
    assert bibs.get_marc_subfield(_MMS, "907", "e") == []


def test_unparseable_marc_raises_in_strict_mode():
    bibs, _ = _bibs(_MockResponse(body={"anies": ["<record><not-closed"]}))
    with pytest.raises(AlmaValidationError):
        bibs.get_marc_subfield(_MMS, "907", "e", strict=True)
