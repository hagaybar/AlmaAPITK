"""R10 regression test for issue #193 — delete_record sent an invalid override.

Bug: ``delete_record(mms_id, override_attached_items=True)`` set the query
parameter ``override=attached_items``. Alma's ``DELETE /bibs/{mms_id}`` defines
``override`` as a boolean-valued string (``true`` / ``false``, per
``docs/alma-swagger/bibs.json``), so it rejected the request with *"Make sure the
override parameter is false or true."* — the override-delete path could never
succeed.

These tests pin the wire value: the override branch must send ``override=true``
(fails against the pre-fix ``attached_items``), and the default no-override call
must send no ``override`` param at all.
"""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from almaapitk.domains.bibs import BibliographicRecords

_MMS = "99123456789"


class _MockResponse:
    def __init__(self):
        self.success = True
        self.status_code = 204

    def json(self):
        return {}


class _MockClient:
    """Records DELETE calls so the override param can be asserted."""

    def __init__(self):
        self.environment = "SANDBOX"
        self.logger = MagicMock()
        self.calls: Dict[str, list] = {"delete": []}

    def delete(self, endpoint, params: Optional[Dict[str, Any]] = None):
        self.calls["delete"].append({"endpoint": endpoint, "params": params})
        return _MockResponse()


def _bibs():
    client = _MockClient()
    return BibliographicRecords(client), client


def test_override_sends_true_not_attached_items():
    bibs, client = _bibs()

    bibs.delete_record(_MMS, override_attached_items=True)

    params = client.calls["delete"][0]["params"]
    assert params.get("override") == "true", (
        f"override must be the boolean-valued 'true', got {params!r} "
        "(pre-fix bug sent the invalid 'attached_items')"
    )
    assert params.get("override") != "attached_items"


def test_default_delete_sends_no_override_param():
    bibs, client = _bibs()

    bibs.delete_record(_MMS)

    params = client.calls["delete"][0]["params"]
    assert "override" not in params, (
        f"a plain delete must not send an override param, got {params!r}"
    )
