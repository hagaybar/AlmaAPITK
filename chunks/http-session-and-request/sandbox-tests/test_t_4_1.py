"""SANDBOX test t-4-1 — Issue #4 (consolidated _request() method).

Smoke test: a single read call exercises the consolidated ``_request()``
path end-to-end:
- public GET signature on the domain method is preserved,
- ``_safe_response_body()`` parses the live JSON response cleanly,
- ``AlmaResponse`` is returned with the expected shape (.success, .data).

Notes
-----
- ``ALMA_SB_API_KEY`` must be set in the environment; the
  ``AlmaAPIClient(environment="SANDBOX")`` constructor reads it internally.
- Uses the same fixture user as t-3-1 (``027393602``).
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
    """Single SANDBOX client; only one call is made in this test."""
    if not os.getenv("ALMA_SB_API_KEY"):
        pytest.skip("ALMA_SB_API_KEY not set; cannot run live SANDBOX test")
    return AlmaAPIClient(environment="SANDBOX")


@pytest.fixture(scope="module")
def users(client: AlmaAPIClient) -> Users:
    """Users domain bound to the shared SANDBOX client."""
    return Users(client)


def test_t_4_1_consolidated_request_path(users: Users) -> None:
    """Single GET against a SANDBOX user exercises the consolidated _request path."""

    raised_exc: Exception | None = None
    try:
        response = users.get_user(TEST_USER_ID)
    except (AlmaAPIError, AlmaValidationError) as exc:
        raised_exc = exc
        response = None  # type: ignore[assignment]

    # Pass criterion: no AlmaAPIError, AlmaValidationError, or
    # AlmaRateLimitError (when available) raised.
    assert raised_exc is None, (
        f"get_user raised {type(raised_exc).__name__}: {raised_exc!r}; "
        f"expected the call to return cleanly"
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
    # _safe_response_body without raising.
    try:
        data = response.data
    except Exception as exc:  # noqa: BLE001 - we want any parse failure to fail loudly
        pytest.fail(
            f"Accessing AlmaResponse.data raised {type(exc).__name__}: {exc!r}; "
            f"_safe_response_body should have produced a parsed body cleanly"
        )

    assert isinstance(data, dict), (
        f"AlmaResponse.data was {type(data).__name__}, expected dict; value={data!r}"
    )
    assert len(data) > 0, (
        f"AlmaResponse.data was an empty dict; expected a non-empty user record"
    )
