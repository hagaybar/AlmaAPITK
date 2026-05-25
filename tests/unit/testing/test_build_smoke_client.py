import pytest

from almaapitk.testing.client import build_smoke_client
from almaapitk.testing.guards import ReadOnlyViolation


def test_dry_run_records_and_blocks_network():
    client, transport = build_smoke_client(
        environment="PRODUCTION", readonly=True, dry_run=True, api_key="fake-key"
    )
    try:
        client.get("almaws/v1/analytics/reports", params={"path": "/x"})
        assert transport is not None
        assert len(transport.calls) == 1
        assert transport.calls[0].method == "GET"
    finally:
        client.close()


def test_dry_run_readonly_still_blocks_writes():
    client, _ = build_smoke_client(
        environment="PRODUCTION", readonly=True, dry_run=True, api_key="fake-key"
    )
    try:
        with pytest.raises(ReadOnlyViolation):
            client.post("almaws/v1/anything", data={"k": "v"})
    finally:
        client.close()


def test_live_readonly_blocks_writes_without_network():
    # The read-only guard wraps the real session; a POST must raise before any I/O.
    client, _ = build_smoke_client(
        environment="PRODUCTION", readonly=True, dry_run=False, api_key="fake-key"
    )
    try:
        with pytest.raises(ReadOnlyViolation):
            client.post("almaws/v1/anything", data={"k": "v"})
    finally:
        client.close()
