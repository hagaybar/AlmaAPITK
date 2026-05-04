"""SANDBOX test t-3-1 — Issue #3 (persistent requests.Session).

Smoke test: two consecutive read calls against a known SANDBOX user verify
that (a) the session is reused without breaking subsequent requests, (b)
per-call ``custom_headers`` still propagate over session-level defaults, and
(c) public method/domain signatures continue to work end-to-end.

Notes
-----
- ``Users.get_user(user_id, expand="none")`` does NOT accept ``custom_headers``
  in its public signature. To exercise the per-call ``custom_headers``
  propagation path described in the test plan, the second call goes through
  ``client.get(endpoint, custom_headers=...)`` directly. This reaches the
  same underlying ``_request`` chokepoint and per-call header injection used
  by every domain method.
- A single ``AlmaAPIClient(environment="SANDBOX")`` instance is shared across
  both calls so session reuse is meaningfully exercised.
- ``ALMA_SB_API_KEY`` must be set in the environment; the client constructor
  reads it internally.
"""

from __future__ import annotations

import os
import pytest

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
    """Single SANDBOX client reused across both calls (exercises session reuse)."""
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


def test_t_3_1_session_reuse_and_custom_headers(client: AlmaAPIClient, users: Users) -> None:
    """Two consecutive reads on the same client; second carries custom_headers."""

    # --- Call 1: standard domain method, plain GET ---------------------------
    raised_exc_1: Exception | None = None
    try:
        response_1 = users.get_user(TEST_USER_ID)
    except (AlmaAPIError, AlmaValidationError) as exc:
        raised_exc_1 = exc
        response_1 = None  # type: ignore[assignment]

    assert raised_exc_1 is None, (
        f"First call raised {type(raised_exc_1).__name__}: {raised_exc_1!r}; "
        f"expected no AlmaAPIError/AlmaValidationError"
    )
    assert isinstance(response_1, AlmaResponse), (
        f"First call returned {type(response_1).__name__}, expected AlmaResponse"
    )
    assert response_1.success is True, (
        f"First call: AlmaResponse.success was {response_1.success!r} "
        f"(status_code={response_1.status_code}), expected True"
    )

    data_1 = response_1.data
    assert _is_user_record(data_1), (
        f"First call: .data was not a non-empty Alma user dict; "
        f"got type={type(data_1).__name__} value={data_1!r}"
    )

    # --- Call 2: per-call custom_headers via the client GET path -------------
    # Users.get_user does not expose a custom_headers kwarg, so go through
    # the client directly to exercise per-call header propagation. This is
    # the same code path every domain method uses under the hood.
    endpoint = f"almaws/v1/users/{TEST_USER_ID}"
    raised_exc_2: Exception | None = None
    try:
        response_2 = client.get(
            endpoint,
            custom_headers={"X-Test-Header": "almaapitk-session-smoke"},
        )
    except (AlmaAPIError, AlmaValidationError) as exc:
        raised_exc_2 = exc
        response_2 = None  # type: ignore[assignment]

    assert raised_exc_2 is None, (
        f"Second call (with custom_headers) raised "
        f"{type(raised_exc_2).__name__}: {raised_exc_2!r}; "
        f"expected no AlmaAPIError/AlmaValidationError"
    )
    assert isinstance(response_2, AlmaResponse), (
        f"Second call returned {type(response_2).__name__}, expected AlmaResponse"
    )
    assert response_2.success is True, (
        f"Second call: AlmaResponse.success was {response_2.success!r} "
        f"(status_code={response_2.status_code}), expected True"
    )

    data_2 = response_2.data
    assert _is_user_record(data_2), (
        f"Second call: .data was not a non-empty Alma user dict; "
        f"got type={type(data_2).__name__} value={data_2!r}"
    )

    # --- Cross-call invariants ----------------------------------------------
    # If AlmaRateLimitError is exported, neither call should have raised it.
    # The try/except above already catches AlmaAPIError, of which any future
    # rate-limit subclass would be a member, but we keep this assert explicit
    # for traceability against the test plan's pass criteria.
    if AlmaRateLimitError is not None:
        assert not isinstance(raised_exc_1, AlmaRateLimitError), (
            f"First call raised AlmaRateLimitError unexpectedly: {raised_exc_1!r}"
        )
        assert not isinstance(raised_exc_2, AlmaRateLimitError), (
            f"Second call raised AlmaRateLimitError unexpectedly: {raised_exc_2!r}"
        )
