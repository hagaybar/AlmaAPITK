"""Shared pytest configuration for users-requests-followup SANDBOX tests.

Implements the agent-safe dual-output design for issue #148:

- alma_logging's stderr handlers are CLEARED at pytest config time and
  replaced with a single FileHandler that writes to a per-run detail log
  under sandbox-test-output/. The detail log contains the full HTTP
  request/response trace (with Authorization headers redacted by 0.4.5)
  and is for the OPERATOR's eyes only. It is gitignored.

- Each test writes its own agent-safe summary JSON to sandbox-test-output/
  containing only: stage-by-stage boolean pass/fail, numeric Alma error
  codes, timings, and a redaction-effectiveness count. No user IDs,
  request IDs, library codes, fund codes, or bib metadata appear in the
  summary.

- Fixtures load test-data.json (operator-filled, gitignored) and provide
  values to tests without exposing them to pytest's captured output.

- print() inside tests is minimal and never emits a fixture value or
  Alma response payload. Only stage banners ("[t-42-3] starting",
  "[t-42-3] done: pass") and the summary file path.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

CHUNK_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = CHUNK_DIR / "sandbox-test-output"
DATA_PATH = CHUNK_DIR / "test-data.json"

# Run-scoped timestamp so all artifacts from one invocation share a stamp.
RUN_STAMP = time.strftime("%Y%m%d-%H%M%S")
DETAIL_LOG_PATH = OUTPUT_DIR / f"run-{RUN_STAMP}-detail.log"


def pytest_configure(config):
    """Re-route alma_logging output to a detail log file only.

    Aggressive isolation: clears handlers on EVERY logger whose name
    starts with 'almapi' or is one of the known domain-style names
    ('users', 'api_client', 'acquisitions', etc.). Sets propagate=False
    so child loggers don't bubble back to root and re-emit. From this
    point on, the only alma_logging output is the detail-log file.

    The earlier version of this hook only handled the ``almapi`` parent
    logger and missed handlers attached to children — leading to a
    safety failure in the 2026-05-18 run where pytest's captured-output
    display surfaced tenant identifiers. Don't trust the parent-only
    approach; walk the tree.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Force the toolkit's logger setup to fire so we can override it.
    from almaapitk.client import AlmaAPIClient  # noqa: F401
    from almaapitk.alma_logging.formatters import TextFormatter

    # Touching the domain modules forces their __init__ to register loggers.
    from almaapitk.domains import users as _users_mod  # noqa: F401

    file_handler = logging.FileHandler(DETAIL_LOG_PATH)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(TextFormatter(use_colors=False))

    # The set of logger names alma_logging actually uses (per the
    # toolkit's get_logger() factory and AlmaAPIClient's module-level
    # setup). Names that don't exist yet are a no-op — getLogger creates
    # them implicitly.
    target_loggers = {
        "almapi",
        "almapi.api_client",
        "almapi.users",
        "almapi.acquisitions",
        "almapi.bibs",
        "almapi.admin",
        "almapi.analytics",
        "almapi.configuration",
        "almapi.resource_sharing",
        # The toolkit also emits under bare names in some paths.
        "api_client",
        "users",
    }
    # Plus: walk the entire logger tree for anything starting with the
    # toolkit prefix (defensive — handles names added in future releases).
    all_loggers = logging.Logger.manager.loggerDict.keys()
    for name in list(all_loggers):
        if name.startswith("almapi") or name in {"api_client", "users"}:
            target_loggers.add(name)

    for name in target_loggers:
        logger = logging.getLogger(name)
        # Strip every handler — stream, file, anything.
        logger.handlers = [file_handler]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    # Also disable the root logger's stderr handler if any toolkit code
    # has poked at it.
    root = logging.getLogger()
    # Don't nuke root entirely (pytest's caplog plugin uses it). Just
    # ensure no StreamHandler at the root level can emit toolkit content.
    root.handlers = [
        h for h in root.handlers
        if not isinstance(h, logging.StreamHandler) or isinstance(h, logging.FileHandler)
    ]


@pytest.fixture(scope="session")
def test_data() -> Dict[str, str]:
    """Operator-filled fixtures from test-data.json (gitignored)."""
    if not DATA_PATH.exists():
        pytest.skip(
            f"test-data.json missing at {DATA_PATH}. "
            f"Copy test-data.example.json, fill values, and re-run."
        )
    data = json.loads(DATA_PATH.read_text())
    return data


@pytest.fixture(scope="session")
def detail_log_path() -> Path:
    return DETAIL_LOG_PATH


def _scan_detail_log_for_redaction(detail_log_path: Path) -> Dict[str, int]:
    """Count-only scan of the detail log for redaction effectiveness.

    Returns ZERO content from the file — only integer counts of pattern
    matches. Safe to include in the agent-readable summary.
    """
    if not detail_log_path.exists():
        return {"alma_key_shape_count": 0, "redacted_marker_count": 0}
    text = detail_log_path.read_text()
    return {
        "alma_key_shape_count": len(re.findall(r"l[78]xx[0-9a-f]{32}", text)),
        "redacted_marker_count": text.count("***REDACTED***"),
    }


def write_summary(
    test_name: str,
    stages: List[Dict[str, Any]],
    started_at: str,
    ended_at: str,
    cleanup_ok: bool,
    request_id_returned: bool,
    detail_log_path: Path,
) -> Path:
    """Write the agent-safe summary JSON.

    Stage records may include: name (string), ok (bool), duration_ms
    (number), alma_code (string of digits or null), exception_class
    (string class name without message, or null).
    """
    summary_path = OUTPUT_DIR / f"run-{RUN_STAMP}-{test_name}-summary.json"

    exit_status = "pass" if all(s["ok"] for s in stages) else "fail"
    summary = {
        "test_name": test_name,
        "version": "almaapitk 0.4.5",
        "started_at": started_at,
        "ended_at": ended_at,
        "exit": exit_status,
        "stages": stages,
        "cleanup_ok": cleanup_ok,
        "request_id_returned": request_id_returned,
        "redaction_check": _scan_detail_log_for_redaction(detail_log_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"summary written: {summary_path.relative_to(Path.cwd())}", file=sys.stderr)
    return summary_path


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class StageRecorder:
    """Records (stage_name, ok, alma_code, duration_ms) tuples without
    ever exposing the wrapper's return value to the summary or stdout.

    Usage:
        rec = StageRecorder()
        with rec.stage("create") as ctx:
            response = users.create_user_rs_request(...)
            ctx.result = response          # stored locally, never serialized
            ctx.request_id = extract_request_id(response)  # stored locally
        # After exit: rec.stages has one new entry with name='create',
        # ok=(no-exception), duration_ms, alma_code (if AlmaAPIError captured)
    """

    def __init__(self) -> None:
        self.stages: List[Dict[str, Any]] = []
        # Locally-stored values (NOT serialized to summary):
        self._scratch: Dict[str, Any] = {}

    def stage(self, name: str):
        return _StageContext(self, name)

    def store(self, key: str, value: Any) -> None:
        """Stash a value locally (e.g., request_id) for use by later
        stages. Never serialized to summary."""
        self._scratch[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._scratch.get(key, default)


class _StageContext:
    def __init__(self, recorder: StageRecorder, name: str) -> None:
        self._rec = recorder
        self._name = name
        self._t0: float = 0.0
        self.alma_code: Optional[str] = None
        self.expected_failure: bool = False

    def __enter__(self) -> "_StageContext":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration_ms = int((time.perf_counter() - self._t0) * 1000)
        from almaapitk.client.AlmaAPIClient import AlmaAPIError, AlmaValidationError

        ok = True
        exception_class: Optional[str] = None
        alma_code: Optional[str] = self.alma_code
        sanitized_error: Optional[str] = None
        if exc_type is not None:
            if self.expected_failure and (
                exc_type is AlmaAPIError or issubclass(exc_type, AlmaAPIError)
            ):
                ok = True
                alma_code = (
                    getattr(exc_val, "alma_code", None)
                    or alma_code
                    or "expected-error"
                )
                self._rec.stages.append(
                    {
                        "name": self._name,
                        "ok": ok,
                        "duration_ms": duration_ms,
                        "alma_code": alma_code,
                        "exception_class": exc_type.__name__,
                    }
                )
                return True  # Suppress the exception.
            ok = False
            exception_class = exc_type.__name__
            alma_code = getattr(exc_val, "alma_code", None) or alma_code
            sanitized_error = _sanitize_alma_error(exc_val)
        entry = {
            "name": self._name,
            "ok": ok,
            "duration_ms": duration_ms,
            "alma_code": alma_code,
            "exception_class": exception_class,
        }
        if sanitized_error:
            entry["sanitized_error"] = sanitized_error
        self._rec.stages.append(entry)
        # If unexpected exception, do NOT suppress — let pytest fail the test
        # but the exception class is already recorded in the stage list.
        return False


def _sanitize_alma_error(exc: Any) -> Optional[str]:
    """Extract a safe-to-share excerpt from an Alma error.

    Strategy: keep STRUCTURAL diagnostic content (Java type names,
    JAXB / Jackson error keywords, JSON keys, swagger field names).
    Redact obvious tenant identifier shapes (long digit runs,
    single-quoted values that look like operator-supplied codes,
    embedded ${placeholders}).

    Double-quoted strings are NOT redacted, because in Alma's standard
    error envelope they are JSON keys (``"errorCode"``, ``"errorMessage"``)
    and Java type names — both useful for diagnosis and identifier-free.
    """
    if exc is None:
        return None
    text = str(exc)
    if not text:
        return None
    snippet = text[:600]
    # Redact long digit runs (likely Alma internal IDs).
    snippet = re.sub(r"\b\d{4,}\b", "<digits-redacted>", snippet)
    # Redact single-quoted short tokens (most likely places for
    # operator-supplied codes like 'RS_LIB' or 'AC_1').
    snippet = re.sub(r"'[A-Z0-9_\-]{2,30}'", "'<code-redacted>'", snippet)
    # Collapse whitespace.
    snippet = " ".join(snippet.split())
    return snippet[:400]
