"""Shared pytest configuration for rs-borrowing-ergonomics SANDBOX tests.

Routes alma_logging output away from stderr into a per-run detail log file
under sandbox-test-output/ (gitignored), so pytest's captured output never
surfaces operator-supplied identifiers (rule R9). Ported from the proven
conftest in chunks/users-requests-followup/sandbox-tests/ (issue #148
agent-safe dual-output design), trimmed to the logging-isolation hook:
fixtures are loaded by each test file directly from the gitignored
test-data.json at RUNTIME, never inlined at generation time.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

CHUNK_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = CHUNK_DIR / "sandbox-test-output"

# Run-scoped timestamp so all artifacts from one invocation share a stamp.
RUN_STAMP = time.strftime("%Y%m%d-%H%M%S")
DETAIL_LOG_PATH = OUTPUT_DIR / f"run-{RUN_STAMP}-detail.log"


def pytest_configure(config):
    """Re-route alma_logging output to a detail log file only.

    Aggressive isolation: clears handlers on EVERY logger whose name
    starts with 'almapi' or is one of the known domain-style names.
    Sets propagate=False so child loggers don't bubble back to root and
    re-emit. From this point on, the only alma_logging output is the
    detail-log file (operator-only, gitignored).

    Walk the whole logger tree, not just the parent — the parent-only
    approach leaked tenant identifiers into pytest's captured output in
    the 2026-05-18 run.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Force the toolkit's logger setup to fire so we can override it.
    from almaapitk.client import AlmaAPIClient  # noqa: F401
    from almaapitk.alma_logging.formatters import TextFormatter

    # Touching the domain module forces its loggers to register.
    from almaapitk.domains import users as _users_mod  # noqa: F401

    file_handler = logging.FileHandler(DETAIL_LOG_PATH)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(TextFormatter(use_colors=False))

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
    # Defensive: pick up any logger already registered under the toolkit
    # prefix (handles names added in future releases).
    for name in list(logging.Logger.manager.loggerDict.keys()):
        if name.startswith("almapi") or name in {"api_client", "users"}:
            target_loggers.add(name)

    for name in target_loggers:
        logger = logging.getLogger(name)
        logger.handlers = [file_handler]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    # Keep pytest's own root handlers, but drop bare StreamHandlers that
    # could re-emit toolkit records to stderr.
    root = logging.getLogger()
    root.handlers = [
        h
        for h in root.handlers
        if not isinstance(h, logging.StreamHandler)
        or isinstance(h, logging.FileHandler)
    ]
