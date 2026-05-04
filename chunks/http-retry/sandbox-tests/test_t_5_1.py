"""SANDBOX test t-5-1 — Issue #5 (HTTP retry adapter mounted on session).

Smoke test: after the Retry adapter is mounted on the session, a normal GET
against SANDBOX still completes successfully — verifies the adapter doesn't
break the happy path.

This test exercises:
- ``Users.get_user(user_id)`` returns an ``AlmaResponse`` with ``.success``
  True and a non-empty parsed dict body (live JSON parsed by
  ``_safe_response_body``);
- the HTTPS adapter mounted on ``client._session`` is the retry-enabled
  ``HTTPAdapter`` (i.e. ``adapter.max_retries`` is a ``urllib3`` ``Retry``
  instance with ``total >= 1``), not the stdlib default that uses an int;
- no ``AlmaAPIError`` / ``AlmaValidationError`` is raised on the happy path.

Notes
-----
- ``ALMA_SB_API_KEY`` must be set in the environment; the
  ``AlmaAPIClient(environment="SANDBOX")`` constructor reads it internally.
- Uses the same fixture user as t-3-1 / t-4-1 (``<provided-at-runtime>``).
"""

from __future__ import annotations

import os
import pytest

import requests.adapters
from urllib3.util.retry import Retry

from almaapitk import (
    AlmaAPIClient,
    AlmaResponse,
    AlmaAPIError,
    AlmaValidationError,
    Users,
)

# AlmaRateLimitError is referenced in project docs but is not currently part
# of the exported public API. Guard the import so the test still runs while
# also asserting the no-raise property when the class is available.
try:  # pragma: no cover - import-time guard
    from almaapitk import AlmaRateLimitError  # type: ignore[attr-defined]
except (ImportError, AttributeError):  # pragma: no cover
    AlmaRateLimitError = None  # type: ignore[assignment]


# Load fixture from chunks/<name>/test-data.json (operator-supplied, gitignored)
# OR from TEST_USER_ID env var. Skips cleanly if neither is available.
def _load_test_user_id() -> str:
    import os, json, pathlib
    env_value = os.environ.get("TEST_USER_ID", "").strip()
    if env_value:
        return env_value
    test_data = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
    if test_data.exists():
        try:
            data = json.loads(test_data.read_text())
            v = (data.get("test_user_id") or "").strip()
            if v and v != "<provided-at-runtime>":
                return v
        except Exception:
            pass
    return ""


TEST_USER_ID = _load_test_user_id()
if not TEST_USER_ID:
    pytest.skip(
        "TEST_USER_ID unavailable — set TEST_USER_ID env var or populate "
        "chunks/<name>/test-data.json with a valid user_primary_id.",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def client() -> AlmaAPIClient:
    """Single SANDBOX client; only one call is made in this test."""
    if not os.getenv("ALMA_SB_API_KEY"):
        pytest.skip("ALMA_SB_API_KEY not set; cannot run live SANDBOX test")
    return AlmaAPIClient(environment="SANDBOX")


@pytest.fixture(scope="module")
def users(client: AlmaAPIClient) -> Users:
    """Users domain bound to the shared SANDBOX client."""
    return Users(client)


def _is_user_record(payload) -> bool:
    """Heuristic check that the parsed body looks like an Alma user record.

    An Alma user GET response is a JSON object that always carries at least
    ``primary_id``; we also accept ``user_primary_id`` defensively.
    """
    if not isinstance(payload, dict) or not payload:
        return False
    return any(k in payload for k in ("primary_id", "user_primary_id"))


def test_t_5_1_retry_adapter_does_not_break_happy_path(
    client: AlmaAPIClient, users: Users
) -> None:
    """Retry adapter is mounted; a normal SANDBOX GET still succeeds."""

    # --- Pass criterion: the HTTPS adapter is the retry-enabled HTTPAdapter
    # ---------------------------------------------------------------------
    # The default ``requests.Session`` mounts an ``HTTPAdapter`` whose
    # ``max_retries`` is an ``int`` (0). When our code mounts a Retry-
    # configured adapter, ``max_retries`` becomes a ``urllib3`` ``Retry``
    # instance with a non-zero ``total``. We assert both conditions.
    assert hasattr(client, "_session"), (
        "AlmaAPIClient does not expose a `_session` attribute; cannot inspect "
        "the mounted HTTPS adapter"
    )

    adapters = client._session.adapters
    assert "https://" in adapters, (
        f"Expected an HTTPS adapter mounted on `client._session`; "
        f"got adapters={list(adapters)!r}"
    )

    adapter = adapters["https://"]
    assert isinstance(adapter, requests.adapters.HTTPAdapter), (
        f"Mounted HTTPS adapter is {type(adapter).__name__}, "
        f"expected requests.adapters.HTTPAdapter"
    )
    assert isinstance(adapter.max_retries, Retry), (
        f"Expected adapter.max_retries to be a urllib3 Retry instance "
        f"(indicating our retry-enabled adapter is mounted), but got "
        f"{type(adapter.max_retries).__name__} (value={adapter.max_retries!r}); "
        f"the default requests.Session adapter uses an int max_retries=0"
    )
    assert adapter.max_retries.total >= 1, (
        f"Expected Retry.total >= 1 to indicate retries are enabled; "
        f"got total={adapter.max_retries.total!r}"
    )

    # --- Live happy-path GET ------------------------------------------------
    raised_exc: Exception | None = None
    try:
        response = users.get_user(TEST_USER_ID)
    except (AlmaAPIError, AlmaValidationError) as exc:
        raised_exc = exc
        response = None  # type: ignore[assignment]

    # Pass criterion: no AlmaAPIError / AlmaValidationError raised.
    assert raised_exc is None, (
        f"get_user raised {type(raised_exc).__name__}: {raised_exc!r}; "
        f"expected the call to return cleanly with the retry adapter mounted"
    )

    if AlmaRateLimitError is not None:
        assert not isinstance(raised_exc, AlmaRateLimitError), (
            f"get_user raised AlmaRateLimitError unexpectedly: {raised_exc!r}"
        )

    # Pass criterion: returns AlmaResponse with success == True.
    assert isinstance(response, AlmaResponse), (
        f"get_user returned {type(response).__name__}, expected AlmaResponse"
    )
    assert response.success is True, (
        f"AlmaResponse.success was {response.success!r} "
        f"(status_code={response.status_code}), expected True"
    )

    # Pass criterion: AlmaResponse.data is a non-empty dict produced by
    # _safe_response_body without raising — i.e. live JSON parsed cleanly.
    try:
        data = response.data
    except Exception as exc:  # noqa: BLE001 - any parse failure should fail loudly
        pytest.fail(
            f"Accessing AlmaResponse.data raised {type(exc).__name__}: {exc!r}; "
            f"_safe_response_body should have produced a parsed body cleanly"
        )

    assert isinstance(data, dict), (
        f"AlmaResponse.data was {type(data).__name__}, expected dict; "
        f"value={data!r}"
    )
    assert len(data) > 0, (
        "AlmaResponse.data was an empty dict; expected a non-empty user record"
    )
    assert _is_user_record(data), (
        f"AlmaResponse.data did not look like an Alma user record "
        f"(missing primary_id / user_primary_id); got keys={list(data)!r}"
    )
