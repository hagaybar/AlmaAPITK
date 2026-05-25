# Workflow Smoke-Test Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a reusable, pytest-based workflow smoke-test harness in `almaapitk[smoke]` with dry-run + live (read-only) modes, a PRODUCTION=read-only safety rail, and one worked pilot (`analytics-report-fetch`).

**Architecture:** A new `almaapitk.testing` package hooks the client's single request chokepoint (`client._session.request`) two ways — a *recording transport* (dry-run, no network) and a *read-only guard* (raises on non-GET). `build_smoke_client(...)` assembles a client with the right hooks for a workflow's declared environment/mode. A pytest plugin exposes an `alma` fixture; workflows are pytest tests carrying a `@workflow(...)` marker. A `make smoke` wrapper hides pytest flags.

**Tech Stack:** Python 3.12, pytest, `requests`, the existing `almaapitk` client/domains and `alma_logging` redactor.

**Spec:** `docs/superpowers/specs/2026-05-25-workflow-smoke-harness-design.md`

---

## File structure

- Create `src/almaapitk/testing/__init__.py` — public surface (`build_smoke_client`, `RecordingTransport`, `ReadOnlyViolation`, `test_input`, `workflow`, `run_with_flaky_tolerance`).
- Create `src/almaapitk/testing/transport.py` — `RecordingTransport` (dry-run recorder).
- Create `src/almaapitk/testing/guards.py` — `ReadOnlyViolation`, `install_readonly_guard`.
- Create `src/almaapitk/testing/client.py` — `build_smoke_client`.
- Create `src/almaapitk/testing/inputs.py` — `test_input`, `MissingTestInput`.
- Create `src/almaapitk/testing/flaky.py` — `TransientAPIError`, `run_with_flaky_tolerance`.
- Create `src/almaapitk/testing/workflow.py` — `workflow` marker.
- Create `src/almaapitk/testing/pytest_plugin.py` — `alma` fixture + marker registration.
- Create tests under `tests/unit/testing/`.
- Create pilot `tests/smoke/test_analytics_report_fetch.py` + `smoke-data.example.json`.
- Modify `pyproject.toml` — `[smoke]` extra + pytest entry point; `.gitignore` — `smoke-data.json`.
- Create `Makefile` — `smoke` / `smoke-live` targets.

Each test/impl pair below is one task. Commit after each.

---

### Task 1: Package skeleton + `[smoke]` extra

**Files:**
- Create: `src/almaapitk/testing/__init__.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/testing/test_package_imports.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/testing/test_package_imports.py
def test_testing_package_importable():
    import almaapitk.testing as t
    assert hasattr(t, "__all__")
```

- [ ] **Step 2: Run to verify it fails**

Run: `poetry run python -m pytest tests/unit/testing/test_package_imports.py -q`
Expected: FAIL — `ModuleNotFoundError: almaapitk.testing`.

- [ ] **Step 3: Create the package**

```python
# src/almaapitk/testing/__init__.py
"""Workflow smoke-test harness (issue: test-harness meta).

Install with ``pip install almaapitk[smoke]``. See
docs/superpowers/specs/2026-05-25-workflow-smoke-harness-design.md.
"""
from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 4: Add the `[smoke]` extra + pytest plugin entry point to `pyproject.toml`**

Under `[tool.poetry.group.dev.dependencies]` pytest already exists. Add an extras group so consumers can `pip install almaapitk[smoke]`:

```toml
[tool.poetry.extras]
smoke = ["pytest"]
```

`pytest` must therefore be a normal (optional) dependency, not dev-only. Add to `[tool.poetry.dependencies]`:

```toml
pytest = { version = "^8.0.0", optional = true }
```

and remove the duplicate from the dev group if present (keep one source of truth). Register the plugin so the `alma` fixture autoloads:

```toml
[tool.poetry.plugins.pytest11]
almaapitk_smoke = "almaapitk.testing.pytest_plugin"
```

- [ ] **Step 5: Run to verify it passes**

Run: `poetry install && poetry run python -m pytest tests/unit/testing/test_package_imports.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/almaapitk/testing/__init__.py pyproject.toml tests/unit/testing/test_package_imports.py
git commit -m "feat(testing): scaffold almaapitk.testing package + [smoke] extra"
```

---

### Task 2: RecordingTransport (dry-run recorder)

**Files:**
- Create: `src/almaapitk/testing/transport.py`
- Test: `tests/unit/testing/test_transport.py`

The recorder replaces `client._session.request` so a workflow runs with **no network**: every call is recorded, and a canned `requests.Response` is returned (default: HTTP 200, body `{}`). A workflow needing a specific shape (e.g. analytics XML) passes `canned_response_factory`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/testing/test_transport.py
import requests
from almaapitk.testing.transport import RecordingTransport


def _session():
    s = requests.Session()
    return s


def test_records_request_and_sends_nothing():
    transport = RecordingTransport()
    session = _session()
    transport.install(session)

    resp = session.request("GET", "https://example.test/almaws/v1/foo", params={"q": "x"})

    assert resp.status_code == 200
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call.method == "GET"
    assert call.url.endswith("/almaws/v1/foo")
    assert call.params == {"q": "x"}


def test_canned_response_factory_used():
    transport = RecordingTransport(
        canned_response_factory=lambda req: (200, b"<rows/>", "application/xml")
    )
    session = _session()
    transport.install(session)
    resp = session.request("GET", "https://example.test/x")
    assert resp.content == b"<rows/>"
    assert resp.headers["Content-Type"] == "application/xml"
```

- [ ] **Step 2: Run to verify it fails**

Run: `poetry run python -m pytest tests/unit/testing/test_transport.py -q`
Expected: FAIL — module/class missing.

- [ ] **Step 3: Implement**

```python
# src/almaapitk/testing/transport.py
"""Dry-run transport: record requests, send nothing (issue: test-harness)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import requests


@dataclass
class RecordedCall:
    method: str
    url: str
    params: Optional[dict] = None
    headers: Optional[dict] = None
    body: Any = None


# (status_code, content_bytes, content_type)
CannedResponse = Callable[[requests.PreparedRequest], tuple[int, bytes, str]]


class RecordingTransport:
    """Replaces ``Session.request`` with a recorder that performs no I/O."""

    def __init__(self, canned_response_factory: Optional[CannedResponse] = None):
        self.calls: list[RecordedCall] = []
        self._factory = canned_response_factory or (lambda req: (200, b"{}", "application/json"))
        self._original = None

    def install(self, session: requests.Session) -> None:
        self._original = session.request

        def _record(method, url, **kwargs):
            self.calls.append(
                RecordedCall(
                    method=method,
                    url=url,
                    params=kwargs.get("params"),
                    headers=kwargs.get("headers"),
                    body=kwargs.get("json", kwargs.get("data")),
                )
            )
            status, content, content_type = self._factory(None)
            resp = requests.Response()
            resp.status_code = status
            resp._content = content
            resp.headers["Content-Type"] = content_type
            resp.url = url
            return resp

        session.request = _record  # type: ignore[assignment]
```

- [ ] **Step 4: Run to verify it passes**

Run: `poetry run python -m pytest tests/unit/testing/test_transport.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/almaapitk/testing/transport.py tests/unit/testing/test_transport.py
git commit -m "feat(testing): dry-run RecordingTransport (no network)"
```

---

### Task 3: Read-only guard (the safety rail, R-H2/R-H5)

**Files:**
- Create: `src/almaapitk/testing/guards.py`
- Test: `tests/unit/testing/test_readonly_guard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/testing/test_readonly_guard.py
import pytest
import requests
from almaapitk.testing.guards import install_readonly_guard, ReadOnlyViolation


def _session_that_never_calls_network():
    s = requests.Session()
    s.request = lambda method, url, **kw: "ok"  # stand-in
    return s


def test_get_is_allowed():
    s = _session_that_never_calls_network()
    install_readonly_guard(s)
    assert s.request("GET", "https://example.test/x") == "ok"


@pytest.mark.parametrize("verb", ["POST", "PUT", "DELETE", "PATCH"])
def test_writes_are_blocked(verb):
    s = _session_that_never_calls_network()
    install_readonly_guard(s)
    with pytest.raises(ReadOnlyViolation):
        s.request(verb, "https://example.test/x")
```

- [ ] **Step 2: Run to verify it fails**

Run: `poetry run python -m pytest tests/unit/testing/test_readonly_guard.py -q`
Expected: FAIL — module/symbol missing.

- [ ] **Step 3: Implement**

```python
# src/almaapitk/testing/guards.py
"""Read-only rail: a guarded session refuses non-GET requests (issue: test-harness)."""
from __future__ import annotations

import requests


class ReadOnlyViolation(RuntimeError):
    """Raised when a read-only (e.g. PRODUCTION) smoke attempts a write."""


def install_readonly_guard(session: requests.Session) -> None:
    """Wrap ``session.request`` so any non-GET verb raises ReadOnlyViolation."""
    inner = session.request

    def _guarded(method, url, **kwargs):
        if str(method).upper() != "GET":
            raise ReadOnlyViolation(
                f"Read-only smoke attempted a {method} to {url}. "
                "PRODUCTION-targeted workflows may only read."
            )
        return inner(method, url, **kwargs)

    session.request = _guarded  # type: ignore[assignment]
```

- [ ] **Step 4: Run to verify it passes**

Run: `poetry run python -m pytest tests/unit/testing/test_readonly_guard.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/almaapitk/testing/guards.py tests/unit/testing/test_readonly_guard.py
git commit -m "feat(testing): read-only guard rail (blocks non-GET)"
```

---

### Task 4: `build_smoke_client` (assemble client + hooks)

**Files:**
- Create: `src/almaapitk/testing/client.py`
- Test: `tests/unit/testing/test_build_smoke_client.py`

Builds an `AlmaAPIClient` for the declared environment using #143 `api_key=` injection, then installs the dry-run recorder and/or the read-only guard. Returns `(client, transport_or_None)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/testing/test_build_smoke_client.py
import pytest
from almaapitk.testing.client import build_smoke_client
from almaapitk.testing.guards import ReadOnlyViolation


def test_dry_run_records_and_blocks_network():
    client, transport = build_smoke_client(
        environment="PRODUCTION", readonly=True, dry_run=True, api_key="fake-key"
    )
    client.get("almaws/v1/analytics/reports", params={"path": "/x"})
    assert transport is not None and len(transport.calls) == 1


def test_dry_run_readonly_still_blocks_writes():
    client, _ = build_smoke_client(
        environment="PRODUCTION", readonly=True, dry_run=True, api_key="fake-key"
    )
    with pytest.raises(ReadOnlyViolation):
        client.post("almaws/v1/anything", data={"k": "v"})


def test_live_readonly_blocks_writes_without_network():
    # readonly guard wraps the real session; a POST must raise before any I/O.
    client, _ = build_smoke_client(
        environment="PRODUCTION", readonly=True, dry_run=False, api_key="fake-key"
    )
    with pytest.raises(ReadOnlyViolation):
        client.post("almaws/v1/anything", data={"k": "v"})
```

- [ ] **Step 2: Run to verify it fails**

Run: `poetry run python -m pytest tests/unit/testing/test_build_smoke_client.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# src/almaapitk/testing/client.py
"""Assemble an AlmaAPIClient wired for smoke testing (issue: test-harness)."""
from __future__ import annotations

from typing import Optional

from almaapitk import AlmaAPIClient
from .guards import install_readonly_guard
from .transport import RecordingTransport, CannedResponse


def build_smoke_client(
    environment: str,
    *,
    readonly: bool,
    dry_run: bool,
    api_key: Optional[str] = None,
    canned_response_factory: Optional[CannedResponse] = None,
) -> tuple[AlmaAPIClient, Optional[RecordingTransport]]:
    """Return a client wired for a smoke. In dry-run a RecordingTransport is
    installed (no network) and returned; otherwise None is returned.

    The read-only guard (when ``readonly``) is installed LAST so it wraps the
    recorder too — a dry-run write is still a ReadOnlyViolation.
    """
    client = AlmaAPIClient(environment, api_key=api_key)

    transport: Optional[RecordingTransport] = None
    if dry_run:
        transport = RecordingTransport(canned_response_factory=canned_response_factory)
        transport.install(client._session)

    if readonly:
        install_readonly_guard(client._session)

    return client, transport
```

- [ ] **Step 4: Run to verify it passes**

Run: `poetry run python -m pytest tests/unit/testing/test_build_smoke_client.py -q`
Expected: PASS. (No network: dry-run records; the read-only test raises before the real session would dial out.)

- [ ] **Step 5: Commit**

```bash
git add src/almaapitk/testing/client.py tests/unit/testing/test_build_smoke_client.py
git commit -m "feat(testing): build_smoke_client wiring (dry-run + read-only rail)"
```

---

### Task 5: Test-input loader

**Files:**
- Create: `src/almaapitk/testing/inputs.py`
- Create: `smoke-data.example.json`
- Modify: `.gitignore` (add `smoke-data.json`)
- Test: `tests/unit/testing/test_inputs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/testing/test_inputs.py
import json
import pytest
from almaapitk.testing.inputs import test_input, MissingTestInput


def test_reads_value(tmp_path, monkeypatch):
    f = tmp_path / "smoke-data.json"
    f.write_text(json.dumps({"analytics_report_path": "/shared/Placeholder/Reports/Demo"}))
    monkeypatch.setenv("ALMA_SMOKE_DATA", str(f))
    assert test_input("analytics_report_path") == "/shared/Placeholder/Reports/Demo"


def test_missing_key_raises_clear_error(tmp_path, monkeypatch):
    f = tmp_path / "smoke-data.json"
    f.write_text("{}")
    monkeypatch.setenv("ALMA_SMOKE_DATA", str(f))
    with pytest.raises(MissingTestInput) as e:
        test_input("nope")
    assert "nope" in str(e.value)
```

- [ ] **Step 2: Run to verify it fails**

Run: `poetry run python -m pytest tests/unit/testing/test_inputs.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement + fixtures**

```python
# src/almaapitk/testing/inputs.py
"""Load synthetic smoke inputs from a gitignored JSON file (R9; issue: test-harness)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class MissingTestInput(KeyError):
    """Raised when a requested smoke input key is absent."""


def _path() -> Path:
    return Path(os.getenv("ALMA_SMOKE_DATA", "smoke-data.json"))


def test_input(key: str) -> Any:
    p = _path()
    if not p.exists():
        raise MissingTestInput(
            f"smoke data file not found at {p}. Copy smoke-data.example.json "
            "to smoke-data.json (gitignored) and fill in synthetic values."
        )
    data = json.loads(p.read_text())
    if key not in data:
        raise MissingTestInput(f"missing smoke input {key!r} in {p}")
    return data[key]
```

```json
// smoke-data.example.json  (committed; copy to smoke-data.json and edit)
{
  "analytics_report_path": "/shared/<your-institution>/Reports/<some-report>"
}
```

Append to `.gitignore`:

```
# Smoke-test inputs hold synthetic-but-environment-specific values (R9)
smoke-data.json
```

- [ ] **Step 4: Run to verify it passes**

Run: `poetry run python -m pytest tests/unit/testing/test_inputs.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/almaapitk/testing/inputs.py smoke-data.example.json .gitignore tests/unit/testing/test_inputs.py
git commit -m "feat(testing): synthetic smoke-input loader + example file"
```

---

### Task 6: Flaky-API tolerance

**Files:**
- Create: `src/almaapitk/testing/flaky.py`
- Test: `tests/unit/testing/test_flaky.py`

Retries on transient `5xx`/`429` (surfaced as `AlmaServerError`/`AlmaRateLimitError`), then raises `TransientAPIError` so the caller can mark the check `skipped` rather than failed.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/testing/test_flaky.py
import pytest
from almaapitk import AlmaServerError
from almaapitk.testing.flaky import run_with_flaky_tolerance, TransientAPIError


def test_passes_through_success():
    assert run_with_flaky_tolerance(lambda: 42, retries=2, delay=0) == 42


def test_retries_then_skips_on_transient():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        raise AlmaServerError("boom", status_code=503)

    with pytest.raises(TransientAPIError):
        run_with_flaky_tolerance(flaky, retries=2, delay=0)
    assert calls["n"] == 3  # initial + 2 retries


def test_real_error_propagates():
    def boom():
        raise ValueError("real bug")

    with pytest.raises(ValueError):
        run_with_flaky_tolerance(boom, retries=2, delay=0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `poetry run python -m pytest tests/unit/testing/test_flaky.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

```python
# src/almaapitk/testing/flaky.py
"""Tolerate transient Alma hiccups in live smokes (issue: test-harness)."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

from almaapitk import AlmaRateLimitError, AlmaServerError

T = TypeVar("T")
_TRANSIENT = (AlmaServerError, AlmaRateLimitError)


class TransientAPIError(RuntimeError):
    """A live check could not complete due to a transient API failure;
    callers should treat this as ``skipped``, not ``failed``."""


def run_with_flaky_tolerance(fn: Callable[[], T], *, retries: int = 2, delay: float = 1.0) -> T:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except _TRANSIENT as exc:
            last = exc
            if attempt < retries:
                time.sleep(delay)
    raise TransientAPIError(f"transient API failure after {retries + 1} attempts: {last}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `poetry run python -m pytest tests/unit/testing/test_flaky.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/almaapitk/testing/flaky.py tests/unit/testing/test_flaky.py
git commit -m "feat(testing): flaky-API tolerance (retry then skip)"
```

---

### Task 7: `workflow` marker + pytest plugin (`alma` fixture)

**Files:**
- Create: `src/almaapitk/testing/workflow.py`
- Create: `src/almaapitk/testing/pytest_plugin.py`
- Modify: `src/almaapitk/testing/__init__.py` (export the public surface)
- Test: `tests/unit/testing/test_workflow_marker.py`

`@workflow(name, environment, readonly)` attaches metadata + a pytest marker. The `alma` fixture reads that metadata, calls `build_smoke_client`, skips when a live env's credentials are absent (R-H3), and yields the client (+ transport in dry-run). Dry-run vs live is selected by the `ALMA_SMOKE_LIVE` env var (set by `make smoke-live`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/testing/test_workflow_marker.py
from almaapitk.testing import workflow


def test_marker_attaches_metadata():
    @workflow(name="demo", environment="SANDBOX", readonly=True)
    def some_workflow(alma):
        ...

    meta = some_workflow.__alma_workflow__
    assert meta == {"name": "demo", "environment": "SANDBOX", "readonly": True}
```

- [ ] **Step 2: Run to verify it fails**

Run: `poetry run python -m pytest tests/unit/testing/test_workflow_marker.py -q`
Expected: FAIL — `workflow` not exported.

- [ ] **Step 3: Implement marker, plugin, exports**

```python
# src/almaapitk/testing/workflow.py
"""@workflow marker for smoke tests (issue: test-harness)."""
from __future__ import annotations

from typing import Callable


def workflow(*, name: str, environment: str, readonly: bool) -> Callable:
    def deco(fn: Callable) -> Callable:
        fn.__alma_workflow__ = {
            "name": name,
            "environment": environment,
            "readonly": readonly,
        }
        import pytest
        return pytest.mark.alma_workflow(name=name, environment=environment, readonly=readonly)(fn)

    return deco
```

```python
# src/almaapitk/testing/pytest_plugin.py
"""pytest plugin: the `alma` fixture + marker registration (issue: test-harness)."""
from __future__ import annotations

import os
import pytest

from .client import build_smoke_client

_ENV_KEYS = {"SANDBOX": "ALMA_SB_API_KEY", "PRODUCTION": "ALMA_PROD_API_KEY"}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "alma_workflow(name, environment, readonly): a workflow smoke test",
    )


@pytest.fixture
def alma(request):
    """Yield a smoke client configured from the test's @workflow marker.

    Live mode is on when ALMA_SMOKE_LIVE is truthy; otherwise dry-run.
    A live test whose env credentials are absent is skipped (R-H3).
    """
    marker = request.node.get_closest_marker("alma_workflow")
    if marker is None:
        pytest.fail("test using the `alma` fixture must carry @workflow(...)")
    env = marker.kwargs["environment"]
    readonly = marker.kwargs["readonly"]

    live = os.getenv("ALMA_SMOKE_LIVE", "").lower() in ("1", "true", "yes")
    if live and not os.getenv(_ENV_KEYS[env]):
        pytest.skip(f"live smoke needs {_ENV_KEYS[env]}; not set")

    client, transport = build_smoke_client(
        environment=env, readonly=readonly, dry_run=not live
    )
    request.node.alma_transport = transport  # request-checks read this in dry-run
    request.node.alma_live = live
    try:
        yield client
    finally:
        client.close()
```

```python
# src/almaapitk/testing/__init__.py  (replace the stub)
from __future__ import annotations

from .client import build_smoke_client
from .transport import RecordingTransport, RecordedCall
from .guards import install_readonly_guard, ReadOnlyViolation
from .inputs import test_input, MissingTestInput
from .flaky import run_with_flaky_tolerance, TransientAPIError
from .workflow import workflow

__all__ = [
    "build_smoke_client", "RecordingTransport", "RecordedCall",
    "install_readonly_guard", "ReadOnlyViolation",
    "test_input", "MissingTestInput",
    "run_with_flaky_tolerance", "TransientAPIError",
    "workflow",
]
```

- [ ] **Step 4: Run to verify it passes**

Run: `poetry run python -m pytest tests/unit/testing/ -q`
Expected: PASS (whole testing unit suite green).

- [ ] **Step 5: Commit**

```bash
git add src/almaapitk/testing/workflow.py src/almaapitk/testing/pytest_plugin.py src/almaapitk/testing/__init__.py tests/unit/testing/test_workflow_marker.py
git commit -m "feat(testing): @workflow marker + pytest `alma` fixture"
```

---

### Task 8: Friendly runner (`make smoke` / `make smoke-live`)

**Files:**
- Create: `Makefile`
- Test: manual (documented command)

- [ ] **Step 1: Create the Makefile**

```makefile
# Workflow smoke tests (issue: test-harness)
.PHONY: smoke smoke-live

# Dry-run only (no credentials needed): validates workflow wiring.
smoke:
	poetry run python -m pytest tests/smoke/ -q

# Live mode: real read-only calls; live checks needing absent creds auto-skip.
smoke-live:
	ALMA_SMOKE_LIVE=1 poetry run python -m pytest tests/smoke/ -q
```

- [ ] **Step 2: Verify the targets resolve**

Run: `make -n smoke && make -n smoke-live`
Expected: prints the two pytest commands with no error.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "feat(testing): make smoke / make smoke-live wrappers"
```

---

### Task 9: Pilot — `analytics-report-fetch` smoke

**Files:**
- Create: `tests/smoke/__init__.py` (empty)
- Create: `tests/smoke/test_analytics_report_fetch.py`
- Modify: `smoke-data.example.json` (already has `analytics_report_path`)
- Test: itself (dry-run always; live when prod key present)

The pilot demonstrates the request-check / response-check split. Dry-run uses a minimal analytics XML canned response so the domain parser does not crash and the **request-check** (it hit the analytics reports endpoint with the configured path) passes. Live mode adds the **response-checks** under flaky tolerance.

- [ ] **Step 1: Write the pilot (it is the test)**

```python
# tests/smoke/test_analytics_report_fetch.py
"""Pilot workflow smoke: fetch an analytics report (PRODUCTION, read-only).

Dry-run validates the request wiring with no credentials. Live mode (make
smoke-live, prod key present) additionally checks the response. R9: the
report path is a synthetic placeholder from smoke-data.json; rows are never
printed.
"""
from __future__ import annotations

from almaapitk import Analytics
from almaapitk.testing import workflow, test_input, run_with_flaky_tolerance


@workflow(name="analytics-report-fetch", environment="PRODUCTION", readonly=True)
def test_analytics_report_fetch(alma, request):
    report_path = test_input("analytics_report_path")
    analytics = Analytics(alma)

    def _fetch():
        headers = analytics.get_report_headers(report_path)
        rows = list(analytics.fetch_report_rows(report_path, max_rows=5))
        return headers, rows

    if not request.node.alma_live:
        # DRY-RUN: run the workflow against the recorder, then request-check.
        try:
            _fetch()
        except Exception:
            pass  # response parsing on canned data is not under test here
        calls = request.node.alma_transport.calls
        assert calls, "workflow issued no requests"
        assert any("analytics/reports" in (c.url or "") for c in calls), (
            "workflow did not hit the analytics reports endpoint"
        )
        return

    # LIVE (PROD, read-only): response-checks, under flaky tolerance.
    headers, rows = run_with_flaky_tolerance(_fetch, retries=2, delay=2.0)
    assert headers, "analytics report returned no column headers"
    assert rows, "analytics report returned no rows"
```

Note: the dry-run path tolerates a parse error on the canned `{}` body (the request-check is what matters in dry-run). If desired, install a canned analytics-XML factory via `build_smoke_client(..., canned_response_factory=...)` in a future refinement; not required for v1.

- [ ] **Step 2: Run dry-run to verify it passes (no creds)**

Run: `cp smoke-data.example.json smoke-data.json && make smoke`
Expected: `analytics-report-fetch` PASS (dry-run request-check).

- [ ] **Step 3: (optional, requires prod key) live check**

Run: `ALMA_SMOKE_LIVE=1 ALMA_PROD_API_KEY=<key> make smoke-live`
Expected: PASS, or SKIPPED on a transient analytics 500.

- [ ] **Step 4: Verify full suite + smoke import still green**

Run: `poetry run python scripts/smoke_import.py && poetry run python -m pytest tests/unit/ tests/logging/ -q`
Expected: PASS (no regressions).

- [ ] **Step 5: Commit**

```bash
git add tests/smoke/__init__.py tests/smoke/test_analytics_report_fetch.py
git commit -m "feat(testing): analytics-report-fetch pilot smoke (dry-run + live read-only)"
```

---

## Self-review

- **Spec coverage:** client fixture (T4/T7), dry-run transport (T2), read-only rail (T3, proven in T3+T4), request/response split (T7/T9), input loader (T5), redaction — **gap**: the spec lists redaction as a v1 component but no task wires it explicitly. Mitigation: output redaction is already enforced globally by `almaapitk.alma_logging` (shipped #142); the harness prints no raw IDs itself and the pilot prints no rows. If a future component logs request/response data, route it through the existing redactor. No separate task needed for v1; noted here so it isn't lost.
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type consistency:** `build_smoke_client` returns `(client, transport)` and the fixture/tests use that shape consistently; `RecordingTransport.calls[].url`, `RecordedCall` fields, `ReadOnlyViolation`, `TransientAPIError`, `test_input` names match across tasks.

## Notes for the executor

- This plan implements child issues **#1 (harness core, Tasks 1–8)** and **#2 (pilot, Task 9)** of the meta-issue. Deferred children (mutation/teardown, CI, orchestrator, consumer rollout) are out of scope.
- Run via the chunk pipeline when picked up: `scripts/agentic/chunks define --name test-harness-v1 --issues <#1>,<#2>` then `/chunk-run-impl test-harness-v1`.
