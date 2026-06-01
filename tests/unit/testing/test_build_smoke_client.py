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


# --- R-H2: PRODUCTION is read-only, always — enforced in the Infra ----------
# Before this, the guard was only installed when the caller passed
# readonly=True, so build_smoke_client("PRODUCTION", readonly=False) handed
# back a writable PROD client. The first mutating consumer
# (Alma-RS-lending-request-automation) is the first to pass readonly=False, so
# the footgun becomes reachable — close it at construction, fail loud.


def test_writable_production_client_is_refused():
    with pytest.raises(ValueError):
        build_smoke_client(
            environment="PRODUCTION", readonly=False, dry_run=True, api_key="fake-key"
        )


@pytest.mark.parametrize("env", ["production", "Production"])
def test_writable_production_refusal_is_case_insensitive(env):
    # AlmaAPIClient accepts these case variants, so the R-H2 guard must
    # normalize case too — otherwise lowercase "production" sneaks a writable
    # PROD client through.
    with pytest.raises(ValueError):
        build_smoke_client(
            environment=env, readonly=False, dry_run=True, api_key="fake-key"
        )


def test_readonly_production_client_is_still_allowed():
    client, _ = build_smoke_client(
        environment="PRODUCTION", readonly=True, dry_run=True, api_key="fake-key"
    )
    client.close()


def test_writable_sandbox_client_is_allowed_and_records_the_write():
    # SANDBOX is the disposable mutation target: a write smoke is fine there.
    client, transport = build_smoke_client(
        environment="SANDBOX", readonly=False, dry_run=True, api_key="fake-key"
    )
    try:
        client.post("almaws/v1/partners/EXAMPLE/lending-requests", data={"k": "v"})
        assert transport is not None
        assert transport.calls[-1].method == "POST"
    finally:
        client.close()
