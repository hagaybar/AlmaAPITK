"""Regression tests for ``Users.__init__`` — issue #132.

The 0.4.x release-review (findings F-004 / F-010) flagged that
``Users.__init__`` re-created a bespoke console+file logger and wrote
``sb_log_file.log`` / ``prod_log_file.log`` into the operator's current
working directory on every instantiation. That bypassed the
``alma_logging`` framework (issues #2 / #14) and dropped INFO-level
records onto ``stdout`` during request execution.

These tests pin the new contract:

- ``Users.logger`` is the same instance ``alma_logging.get_logger`` would
  return for the same domain/environment pair.
- Instantiating ``Users`` does NOT create stray ``*_log_file.log`` files
  in the current working directory.
- Instantiating ``Users`` does NOT emit INFO-or-higher records on
  ``sys.stdout``.

Pattern source: the stub-client / no-real-HTTP shape mirrors
``tests/unit/domains/test_users.py`` (``MockAlmaAPIClient``); the
stdout-capture idiom mirrors the project's existing no-stdout discipline
(issue #14).
"""

from __future__ import annotations

import io
import logging
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from almaapitk.alma_logging import get_logger
from almaapitk.domains.users import Users


class _StubClient:
    """Minimal AlmaAPIClient stand-in for ``Users.__init__``.

    ``Users.__init__`` only reads ``client.get_environment()``; no HTTP
    is exercised in these tests.
    """

    def __init__(self, environment: str = "SANDBOX") -> None:
        self.environment = environment
        # Real ``AlmaAPIClient`` exposes a ``.logger`` attribute; some
        # downstream Users methods used to read it. Provide a benign stub
        # so a future regression that re-introduces ``client.logger``
        # reliance does not silently AttributeError here.
        self.logger = logging.getLogger("stub-client")

    def get_environment(self) -> str:
        return self.environment


def _existing_log_files(directory: Path) -> set[str]:
    """Return the set of ``*_log_file.log`` names currently in *directory*."""

    return {p.name for p in directory.glob("*_log_file.log")}


@pytest.fixture
def cwd_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Change cwd into a clean tmp dir so we can detect stray log files."""

    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_users_init_uses_alma_logging_get_logger(cwd_tmp: Path) -> None:
    """``Users.logger`` must come from ``alma_logging.get_logger``.

    ``get_logger`` is cached per ``(domain, environment)``; a fresh
    ``Users(client)`` instantiation should produce the *same* logger
    instance the framework returns when called directly with matching
    arguments.
    """

    client = _StubClient(environment="SANDBOX")
    expected_logger = get_logger("users", environment="SANDBOX")

    users = Users(client)

    assert users.logger is expected_logger


def test_users_init_does_not_create_cwd_log_files(cwd_tmp: Path) -> None:
    """Instantiating ``Users`` must not drop ``*_log_file.log`` in CWD.

    Pre-fix behaviour created ``sb_log_file.log`` (SANDBOX) or
    ``prod_log_file.log`` (PRODUCTION) via a bespoke ``FileHandler``
    rooted at the current working directory. With the
    ``alma_logging.get_logger`` migration neither file should appear.
    """

    before = _existing_log_files(cwd_tmp)
    assert before == set(), "tmp cwd should start empty"

    Users(_StubClient(environment="SANDBOX"))
    Users(_StubClient(environment="PRODUCTION"))

    after = _existing_log_files(cwd_tmp)
    assert after == set(), (
        f"Users.__init__ created stray log files in CWD: {sorted(after)}"
    )
    assert not (cwd_tmp / "sb_log_file.log").exists()
    assert not (cwd_tmp / "prod_log_file.log").exists()


def test_users_init_no_stdout_writes(cwd_tmp: Path) -> None:
    """No INFO-or-higher record may leak onto ``sys.stdout`` on init.

    The bespoke logger added a ``StreamHandler()`` (defaults to stdout)
    at INFO level and emitted ``"File logging enabled: ..."`` during
    construction. Both behaviours are gone now; instantiation must be
    stdout-silent.
    """

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        Users(_StubClient(environment="SANDBOX"))

    captured = buffer.getvalue()
    assert captured == "", (
        f"Users.__init__ wrote to stdout (expected silent): {captured!r}"
    )


def test_users_module_has_no_sys_path_append() -> None:
    """The module-level ``sys.path.append`` no-op must stay deleted.

    ``src/almaapitk/domains/users.py`` previously appended
    ``../client`` to ``sys.path`` immediately before an absolute import,
    making the manipulation a no-op and the only domain file to carry
    that pattern. Asserting on the source text here makes the regression
    visible without running ``grep`` in CI.
    """

    module_path = Path(__file__).resolve().parents[3] / "src" / "almaapitk" / "domains" / "users.py"
    source = module_path.read_text(encoding="utf-8")

    assert "sys.path.append" not in source, (
        "src/almaapitk/domains/users.py still contains sys.path.append; "
        "the dead path-manipulation block must stay removed."
    )


def test_users_init_does_not_require_client_logger_attr(cwd_tmp: Path) -> None:
    """``Users.__init__`` no longer reads ``client.logger``.

    Pre-fix code assigned ``self.logger = client.logger`` before
    overriding it with the bespoke logger. The new wiring relies solely
    on ``client.get_environment()`` and ``alma_logging.get_logger``, so
    a client stub that omits ``.logger`` entirely must still construct
    cleanly.
    """

    class _NoLoggerClient:
        def get_environment(self) -> str:
            return "SANDBOX"

    users = Users(_NoLoggerClient())  # type: ignore[arg-type]

    assert users.environment == "SANDBOX"
    assert users.logger is get_logger("users", environment="SANDBOX")
