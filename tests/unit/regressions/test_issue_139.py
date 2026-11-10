"""R10 regression tests for issue #139.

Several ``Configuration`` list methods made a single GET and returned what
came back, so they truncated silently:

* ``get_fee_transactions_report`` sent no ``limit``, so Alma applied its
  documented default of 10.
* ``list_printers``, ``list_deposit_profiles`` and ``list_circ_desks`` sent
  ``limit='100'`` (a string), so anything past 100 records was dropped.

A SANDBOX probe (2026-11-10) confirmed that these four endpoints honour
``limit``/``offset``, while libraries, departments, locations, code-tables,
mapping-tables, md-import-profiles and letters ignore both and always
return the full list. The paged four now walk every page through
``client.iter_paged``. The unpaged seven send no paging params at all.
Paging them would re-fetch the same full list and duplicate records.

The fake client below borrows the real ``AlmaAPIClient.iter_paged`` so the
production pagination loop is what runs, against scripted pages.
"""
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration

_HARD_LIMIT = 50


class _Response:
    def __init__(self, body: Dict[str, Any]):
        self._body = body

    def json(self) -> Dict[str, Any]:
        return self._body


class _PagedFakeClient:
    """Serves ``total`` records under ``record_key``, honouring limit/offset.

    With ``ignores_paging=True`` it mimics the unpaged conf endpoints and
    returns every record on every call.
    """

    iter_paged = AlmaAPIClient.iter_paged

    def __init__(self, record_key: str, total: int, ignores_paging=False):
        self.record_key = record_key
        self.total = total
        self.ignores_paging = ignores_paging
        self.environment = "SANDBOX"
        self.logger = MagicMock()
        self.calls: List[Optional[Dict[str, Any]]] = []

    def get_environment(self) -> str:
        return self.environment

    def get(self, endpoint, params=None, custom_headers=None):
        self.calls.append(None if params is None else dict(params))
        assert len(self.calls) <= _HARD_LIMIT, "runaway pagination"
        records = [{"code": f"R{i:04d}"} for i in range(self.total)]
        if not self.ignores_paging:
            params = params or {}
            limit = int(params.get("limit", 10))  # Alma default is 10
            offset = int(params.get("offset", 0))
            records = records[offset:offset + limit]
        return _Response(
            {self.record_key: records, "total_record_count": self.total}
        )


def _codes(records):
    return [r["code"] for r in records]


# --- paged endpoints: every record comes back ---------------------------

_PAGED = [
    ("get_fee_transactions_report", (), "fee"),
    ("list_printers", (), "printer"),
    ("list_deposit_profiles", (), "deposit_profile"),
    ("list_circ_desks", ("LIB_PLACEHOLDER",), "circ_desk"),
]


@pytest.mark.parametrize("method,args,record_key", _PAGED)
@pytest.mark.parametrize("total", [0, 7, 10, 11, 100, 101, 250])
def test_paged_methods_return_every_record(method, args, record_key, total):
    client = _PagedFakeClient(record_key, total)
    result = getattr(Configuration(client), method)(*args)
    assert _codes(result) == [f"R{i:04d}" for i in range(total)]


@pytest.mark.parametrize("method,args,record_key", _PAGED)
def test_paged_methods_send_int_paging_params(method, args, record_key):
    client = _PagedFakeClient(record_key, 3)
    getattr(Configuration(client), method)(*args)
    for params in client.calls:
        assert isinstance(params["limit"], int)
        assert isinstance(params["offset"], int)


def test_fee_report_more_than_alma_default_of_ten():
    """The concrete defect from the audit: 25 fees, not 10."""
    client = _PagedFakeClient("fee", 25)
    result = Configuration(client).get_fee_transactions_report(
        transaction_type="PLACEHOLDER"
    )
    assert len(result) == 25
    assert all(c["transaction_type"] == "PLACEHOLDER" for c in client.calls)


def test_fee_report_explicit_limit_offset_is_a_single_page():
    """A caller doing its own paging keeps the old one-call behaviour."""
    client = _PagedFakeClient("fee", 25)
    result = Configuration(client).get_fee_transactions_report(
        limit=5, offset=10
    )
    assert _codes(result) == [f"R{i:04d}" for i in range(10, 15)]
    assert len(client.calls) == 1


# --- unpaged endpoints: one call, no paging params, no duplicates ---------

_UNPAGED = [
    ("list_libraries", (), "library"),
    ("list_departments", (), "department"),
    ("list_locations", ("LIB_PLACEHOLDER",), "location"),
    ("list_code_tables", (), "code_table"),
    ("list_mapping_tables", (), "mapping_table"),
    ("list_import_profiles", (), "import_profile"),
    ("list_letters", (), "letter"),
]


@pytest.mark.parametrize("method,args,record_key", _UNPAGED)
def test_unpaged_methods_make_one_call_without_paging_params(
    method, args, record_key
):
    client = _PagedFakeClient(record_key, 196, ignores_paging=True)
    result = getattr(Configuration(client), method)(*args)
    assert len(result) == 196
    assert len(client.calls) == 1
    params = client.calls[0] or {}
    assert "limit" not in params and "offset" not in params


# --- iter_paged: single-record dict envelope ------------------------------


def test_iter_paged_normalises_single_record_dict():
    """A lone record serialised as a dict must yield the record, not its keys."""

    class _OneDict(_PagedFakeClient):
        def get(self, endpoint, params=None, custom_headers=None):
            self.calls.append(params)
            return _Response({"printer": {"code": "R0000"},
                              "total_record_count": 1})

    client = _OneDict("printer", 1)
    assert _codes(Configuration(client).list_printers()) == ["R0000"]
