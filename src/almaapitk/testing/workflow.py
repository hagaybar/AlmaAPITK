"""The ``@workflow`` marker for smoke tests.

A workflow smoke is an ordinary pytest test decorated with ``@workflow(...)``;
the decorator records the workflow's metadata on the function so the ``alma``
fixture can build the right client (environment, read-only). See issue #156.
"""
from __future__ import annotations

from typing import Callable


def workflow(*, name: str, environment: str, readonly: bool) -> Callable:
    """Mark a test function as a workflow smoke.

    Args:
        name: Human-readable workflow name (for reports).
        environment: ``"SANDBOX"`` or ``"PRODUCTION"``.
        readonly: When True, the client handed to the test refuses writes
            (mandatory for ``PRODUCTION``).
    """
    if environment == "PRODUCTION" and not readonly:
        raise ValueError(
            "PRODUCTION workflows must be readonly=True (the harness enforces "
            "PRODUCTION = read-only)."
        )

    def deco(fn: Callable) -> Callable:
        fn.__alma_workflow__ = {
            "name": name,
            "environment": environment,
            "readonly": readonly,
        }
        return fn

    return deco
