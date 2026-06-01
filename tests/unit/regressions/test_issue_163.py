"""R10 regression test for issue #163 — get_fee_transactions_report envelope key.

The fee-transactions endpoint returns the ``rest_fees`` envelope whose array key
is ``fee`` — the same key ``Users.list_user_fees`` reads correctly in production
against the same schema. ``get_fee_transactions_report`` read a non-existent
``fee_transaction`` key, so it always returned ``[]`` no matter how many
transactions Alma sent.
"""
from unittest.mock import MagicMock

from almaapitk.domains.configuration import Configuration


def _config(payload):
    client = MagicMock()
    client.get_environment.return_value = "SANDBOX"
    resp = MagicMock()
    resp.json.return_value = payload
    client.get.return_value = resp
    return Configuration(client)


def test_get_fee_transactions_report_reads_fee_envelope():
    config = _config(
        {
            "fee": [{"id": "F1"}, {"id": "F2"}],
            "total_record_count": 2,
            "total_sum": "10.0",
            "currency": "USD",
        }
    )

    result = config.get_fee_transactions_report()

    assert [f["id"] for f in result] == ["F1", "F2"]
