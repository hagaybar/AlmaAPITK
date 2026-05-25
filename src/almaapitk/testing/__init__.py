"""Workflow smoke-test harness for almaapitk.

Install with ``pip install almaapitk[smoke]``. See
``docs/superpowers/specs/2026-05-25-workflow-smoke-harness-design.md``.
"""
from __future__ import annotations

from .client import build_smoke_client
from .flaky import TransientAPIError, run_with_flaky_tolerance
from .guards import ReadOnlyViolation, install_readonly_guard
from .inputs import MissingTestInput, smoke_input
from .transport import RecordedCall, RecordingTransport
from .workflow import workflow

__all__ = [
    "build_smoke_client",
    "RecordingTransport",
    "RecordedCall",
    "install_readonly_guard",
    "ReadOnlyViolation",
    "smoke_input",
    "MissingTestInput",
    "run_with_flaky_tolerance",
    "TransientAPIError",
    "workflow",
]
