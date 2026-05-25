"""Tolerate transient Alma hiccups in live smokes.

Live analytics (and other PROD reads) intermittently return ``5xx``/``429``
(observed: analytics 500 storms). Such a failure should not turn a smoke
red — it means "couldn't check right now", not "the workflow is broken". So
we retry a few times and, if still failing, raise :class:`TransientAPIError`
which callers translate into ``skipped``. See issue #156.
"""
from __future__ import annotations

import time
from typing import Callable, Optional, TypeVar

from almaapitk import AlmaRateLimitError, AlmaServerError

T = TypeVar("T")

_TRANSIENT = (AlmaServerError, AlmaRateLimitError)


class TransientAPIError(RuntimeError):
    """A live check could not complete due to a transient API failure.

    Callers should treat this as ``skipped``, not ``failed``.
    """


def run_with_flaky_tolerance(
    fn: Callable[[], T], *, retries: int = 2, delay: float = 1.0
) -> T:
    """Call ``fn``; retry on transient API errors, then skip.

    Returns ``fn()``'s result on success. Re-raises any non-transient error
    unchanged. Raises :class:`TransientAPIError` if every attempt hit a
    transient failure.
    """
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except _TRANSIENT as exc:
            last = exc
            if attempt < retries:
                time.sleep(delay)
    raise TransientAPIError(
        f"transient API failure after {retries + 1} attempts: {last}"
    )
