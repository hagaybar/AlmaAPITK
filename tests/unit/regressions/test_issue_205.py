"""R10 regression tests for issue #205.

``AlmaAPIClient._classify_error`` used to consult ``ERROR_CODE_REGISTRY``
before looking at the HTTP status, so a registry-mapped body code silently
outranked an *operational* status. An HTTP 429 carrying ``401890`` raised
``AlmaResourceNotFoundError`` ("that user does not exist") instead of
``AlmaRateLimitError`` ("back off and retry"), and retry logic keyed to the
exception type gave up instead of retrying.

Chosen precedence (issue #205, option 1): the operational statuses 401, 429
and 5xx win over any body code. For every other status (the 400/404 cases
where the code really is more specific than the status) the registry still
wins, and the endpoint-scoped ``40166411`` override from #194 still applies.
"""
import pytest

from almaapitk import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaAuthenticationError,
    AlmaRateLimitError,
    AlmaResourceNotFoundError,
    AlmaServerError,
)
from almaapitk.client.AlmaAPIClient import ERROR_CODE_REGISTRY

_ACQ_URL = "https://api.example/almaws/v1/acq/po-lines/PLACEHOLDER"
_USERS_URL = "https://api.example/almaws/v1/users/PLACEHOLDER"

_OPERATIONAL = [
    (401, AlmaAuthenticationError),
    (429, AlmaRateLimitError),
    (500, AlmaServerError),
    (502, AlmaServerError),
    (503, AlmaServerError),
    (599, AlmaServerError),
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", "test-sandbox-key")
    return AlmaAPIClient("SANDBOX")


@pytest.mark.parametrize("code", sorted(ERROR_CODE_REGISTRY))
@pytest.mark.parametrize("status,expected", _OPERATIONAL)
def test_operational_status_outranks_registry_code(
    client, code, status, expected
):
    assert client._classify_error(status, code) is expected
    assert client._classify_error(status, code, url=_ACQ_URL) is expected
    assert client._classify_error(status, code, url=_USERS_URL) is expected


def test_429_with_401890_is_rate_limit_not_not_found(client):
    """The concrete scenario from the issue."""
    exc_class = client._classify_error(429, "401890")
    assert exc_class is AlmaRateLimitError
    assert not issubclass(exc_class, AlmaResourceNotFoundError)


@pytest.mark.parametrize("code", sorted(ERROR_CODE_REGISTRY))
@pytest.mark.parametrize("status", [400, 404])
def test_registry_still_wins_for_non_operational_status(client, code, status):
    assert client._classify_error(status, code) is ERROR_CODE_REGISTRY[code]


def test_40166411_collision_override_still_applies_on_400(client):
    """#194/#209: non-acq 40166411 on a 400 stays the base class."""
    assert client._classify_error(400, "40166411", url=_USERS_URL) is AlmaAPIError
    assert (
        client._classify_error(400, "40166411", url=_ACQ_URL)
        is ERROR_CODE_REGISTRY["40166411"]
    )


def test_precedence_is_documented_in_registry_docstring():
    """The decision must be written where the next person adds a code."""
    import importlib

    # ``import almaapitk.client.AlmaAPIClient as mod`` would bind the class
    # (the package re-exports it under the module's name), so go via importlib.
    mod = importlib.import_module("almaapitk.client.AlmaAPIClient")
    source = open(mod.__file__, encoding="utf-8").read()
    registry_block = source.split("ERROR_CODE_REGISTRY: Dict[str, type] = {")[0]
    assert "#205" in registry_block[-2500:]
