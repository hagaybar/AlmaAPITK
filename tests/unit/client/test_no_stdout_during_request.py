"""Runtime guard: zero raw stdout writes during normal client lifecycle.

Issue #14: every ``print()`` in the library was replaced with a
``self.logger.x(...)`` call. This test pins the behavioral half of that
contract: constructing an ``AlmaAPIClient`` and exercising each HTTP
verb must not emit any *raw* stdout writes (i.e., stray ``print()``,
``sys.stdout.write()``, etc.).

The alma_logging framework currently routes its console handler to
stdout (``alma_logging/logger.py``); that destination choice is a
separate design concern and out of scope for #14. To isolate the
"no print() in library code" invariant we want to assert here, the
test temporarily removes the alma_logging console handlers for the
duration of the assertion window. Anything left in stdout afterwards
is, by elimination, a raw write from library code.
"""
from __future__ import annotations

import logging
import os
import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

import requests

from almaapitk import AlmaAPIClient


def _make_mock_response(status_code: int = 200, json_body=None) -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.ok = status_code < 400
    response.headers = {'content-type': 'application/json'}
    response.text = ''
    response.json.return_value = json_body if json_body is not None else {}
    return response


class TestNoStdoutDuringRequest(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patcher = patch.dict(
            os.environ, {'ALMA_SB_API_KEY': 'test-sandbox-key'}, clear=False
        )
        self._env_patcher.start()
        self.addCleanup(self._env_patcher.stop)

    def _mute_almapi_console_handlers(self) -> list[tuple[logging.Logger, list]]:
        """Strip console handlers from every ``almapi.*`` logger; return
        a saved list so the caller can restore them."""
        saved: list[tuple[logging.Logger, list]] = []
        for name in list(logging.Logger.manager.loggerDict):
            if not name.startswith('almapi'):
                continue
            lg = logging.getLogger(name)
            saved.append((lg, lg.handlers[:]))
            lg.handlers = [
                h for h in lg.handlers
                if not (isinstance(h, logging.StreamHandler)
                        and getattr(h, 'stream', None) in (sys.stdout, sys.stderr))
            ]
        return saved

    def _restore_handlers(self, saved: list[tuple[logging.Logger, list]]) -> None:
        for lg, handlers in saved:
            lg.handlers = handlers

    def test_no_raw_stdout_during_init_and_all_verbs(self) -> None:
        # Construct the client first so its loggers register, then mute their
        # console handlers (otherwise we'd be muting handlers that haven't
        # been added yet).
        with patch.object(
            requests.Session, 'request', return_value=_make_mock_response()
        ):
            AlmaAPIClient('SANDBOX')  # warm up logger registration

        saved = self._mute_almapi_console_handlers()
        captured = StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured
        try:
            with patch.object(
                requests.Session, 'request', return_value=_make_mock_response()
            ):
                client = AlmaAPIClient('SANDBOX')
                client.get('almaws/v1/bibs/test-mms')
                client.post('almaws/v1/bibs/test-mms', data={'k': 'v'})
                client.put('almaws/v1/bibs/test-mms', data={'k': 'v'})
                client.delete('almaws/v1/bibs/test-mms')
        finally:
            sys.stdout = original_stdout
            self._restore_handlers(saved)

        output = captured.getvalue()
        self.assertEqual(
            output,
            '',
            f"Expected zero raw stdout writes during client lifecycle "
            f"(logger output was muted to isolate print() detection); got:\n{output}",
        )


if __name__ == "__main__":
    unittest.main()
