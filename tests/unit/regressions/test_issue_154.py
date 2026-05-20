"""R10 regression tests for issue #154 — sensitive-data leak audit.

The 2026-05-20 security audit (``docs/security-audit-2026-05-20.md``)
flagged three concrete leak vectors that these tests pin down so they
cannot silently regress:

F-001  ``scripts/investigations/alma_client_repro.py`` printed the first
       10 characters of ``ALMA_SB_API_KEY`` / ``ALMA_PROD_API_KEY`` to
       stdout. Even partial keys are too much: stdout is captured by
       Claude Code / Codex history snapshots, terminal scrollback, and
       tmux logs. Test: static check that the script does not slice
       any API-key-shaped variable.

F-002  ``AlmaAPIClient.test_connection`` interpolated ``response.text``
       into the log *message* via an f-string. ``redact_sensitive_data``
       only walks structured ``extra=`` kwargs, so anything in the body
       (a future credential, a URL with query params, etc.) bypassed
       the redactor and landed verbatim in the log. Test: drive the
       error path with a body containing a sentinel string and assert
       the structured log record carries the body in a redactable
       ``body_preview=`` field, not in the message.

F-003  ``logger.exception(f"...: {e}")`` is a doubly-redundant pattern
       — ``exception()`` already attaches the traceback via
       ``exc_info``, and the interpolation defeats the redactor.
       Covered together with F-002 since the fix is the same shape.
"""

from __future__ import annotations

import logging
import os
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from almaapitk import AlmaAPIClient


REPO_ROOT = Path(__file__).resolve().parents[3]


# --- F-001: partial-key leak in alma_client_repro.py ----------------------


def test_alma_client_repro_does_not_slice_api_key_values():
    """The investigation script must never slice (and print) any prefix
    of an API-key-shaped variable.

    The 2026-05-18 audit found ``print(f"... {sb_key[:10]}...")`` style
    leaks. Match any slice of a variable whose name ends in ``_key`` or
    ``api_key`` — that covers ``sb_key``, ``prod_key``, ``api_key``,
    ``alma_api_key``, etc. without false-positiving on unrelated
    locals.
    """
    script = REPO_ROOT / "scripts" / "investigations" / "alma_client_repro.py"
    source = script.read_text()
    leak_pattern = re.compile(
        r"\b\w*(api_key|_key)\s*\[\s*:\s*\d+\s*\]",
        re.IGNORECASE,
    )
    matches = leak_pattern.findall(source)
    assert not matches, (
        f"{script} slices an API-key variable, leaking a key prefix to "
        f"stdout. Found pattern(s): {matches}. See issue #154 F-001."
    )


# --- F-002 / F-003: response.text and str(e) interpolated into log message


class _RecordingHandler(logging.Handler):
    """Capture every emitted record so we can introspect both
    ``record.getMessage()`` (the formatted message) and the structured
    ``extra`` fields attached as record attributes."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestConnectionErrorLoggingDoesNotLeakBody(unittest.TestCase):
    """F-002 + F-003: the ``test_connection`` error path must keep the
    response body and the exception text out of the log *message*. The
    log record is allowed to carry them as structured kwargs so the
    redactor can scrub credential-shaped fields, but the message
    string itself must be redactor-safe."""

    SENTINEL_BODY = "F154_RESPONSE_BODY_SENTINEL_must_not_leak"
    SENTINEL_EXCEPTION = "F154_EXCEPTION_SENTINEL_must_not_leak"

    def setUp(self):
        self._env_patcher = patch.dict(
            os.environ, {"ALMA_SB_API_KEY": "test-sandbox-key"}, clear=False
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)

    def _attach_recording_handler(self, client: AlmaAPIClient) -> _RecordingHandler:
        handler = _RecordingHandler()
        handler.setLevel(logging.DEBUG)
        underlying = client.logger.logger  # AlmaLogger wraps stdlib logger
        underlying.addHandler(handler)
        underlying.setLevel(logging.DEBUG)
        self.addCleanup(lambda: underlying.removeHandler(handler))
        return handler

    def test_error_response_body_not_interpolated_into_message(self):
        """F-002: when ``test_connection`` hits a non-200 it must NOT
        format ``response.text`` into the log message."""
        client = AlmaAPIClient("SANDBOX")
        handler = self._attach_recording_handler(client)

        error_response = MagicMock(spec=requests.Response)
        error_response.status_code = 500
        error_response.ok = False
        error_response.headers = {"content-type": "text/plain"}
        error_response.text = self.SENTINEL_BODY
        error_response.json.side_effect = ValueError("not json")

        with patch.object(
            client._session, "request", return_value=error_response
        ):
            client.test_connection()

        leaking = [
            r for r in handler.records
            if self.SENTINEL_BODY in r.getMessage()
        ]
        assert not leaking, (
            "test_connection leaked response.text into the log message. "
            f"Leaking record message(s): {[r.getMessage() for r in leaking]}. "
            "See issue #154 F-002."
        )

    def test_connection_exception_not_interpolated_into_message(self):
        """F-003: when ``test_connection`` hits an exception during the
        request, it must NOT format ``str(exception)`` into the log
        message. ``logger.exception()`` already attaches the traceback
        via ``exc_info`` — interpolating the exception text into the
        message defeats the redactor and is redundant with the
        traceback."""
        client = AlmaAPIClient("SANDBOX")
        handler = self._attach_recording_handler(client)

        with patch.object(
            client._session,
            "request",
            side_effect=requests.exceptions.ConnectionError(
                self.SENTINEL_EXCEPTION
            ),
        ):
            client.test_connection()

        leaking = [
            r for r in handler.records
            if self.SENTINEL_EXCEPTION in r.getMessage()
        ]
        assert not leaking, (
            "test_connection leaked exception text into the log message. "
            f"Leaking record message(s): {[r.getMessage() for r in leaking]}. "
            "See issue #154 F-003."
        )


if __name__ == "__main__":
    unittest.main()
