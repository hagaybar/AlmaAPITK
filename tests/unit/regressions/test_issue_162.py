"""R10 regression test for issue #162 — list_user_deposits envelope key.

The Alma ``user_deposits`` response wraps its array under ``user_deposit`` —
matching the prefixed convention of every sibling user-collection in this file
(``user_request``, ``user_attachment``). ``list_user_deposits`` read the
unprefixed ``deposit``, which never exists in a real response, so it silently
returned ``[]`` for users who actually have deposits.

The fix reads ``user_deposit`` first with a ``deposit`` fallback (mirroring
``list_user_attachments``), so it is correct against the schema and still
tolerant of the old key if live ever returned it.
"""
from unittest.mock import MagicMock

from almaapitk.domains.users import Users


def _users(payload):
    client = MagicMock()
    client.get_environment.return_value = "SANDBOX"
    resp = MagicMock()
    resp.json.return_value = payload
    client.get.return_value = resp
    return Users(client)


def test_list_user_deposits_reads_user_deposit_envelope():
    users = _users(
        {"user_deposit": [{"id": "D1"}, {"id": "D2"}], "total_record_count": 2}
    )

    result = users.list_user_deposits("tau000000")

    assert [d["id"] for d in result] == ["D1", "D2"]


def test_list_user_deposits_tolerates_legacy_deposit_key():
    """Defensive fallback: the old unprefixed key still works if seen live."""
    users = _users({"deposit": [{"id": "D9"}], "total_record_count": 1})

    assert [d["id"] for d in users.list_user_deposits("tau000000")] == ["D9"]
