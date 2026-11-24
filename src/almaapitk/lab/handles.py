"""Short handles for user identifiers in the full-screen app (issue #256 round 3).

Every user identifier the app fetches or shows gets a handle (``@u1``,
``@u2``, ...), displayed beside the real ID. Any request input (path, query,
body) accepts ``@uN``; the app swaps it for the real ID just before the call,
so the session, the evidence (masked) and the logs only ever see the ID.

Handles live in memory while the app is open: never written to evidence,
baselines or logs. Single CLI commands do not share handles, so the Lab
refuses ``@uN`` outside the app.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from almaapitk.redaction import is_user_id_field

#: ``@u12`` standing alone: not inside an email (an address at a "u1" host) or a word.
HANDLE = re.compile(r"(?<![\w.@-])@u(\d+)(?![\w.@-])")


def holds_handle(value: Any) -> bool:
    """True when ``value`` (a string, or any string inside a dict / list) has a handle."""
    if isinstance(value, str):
        return bool(HANDLE.search(value))
    if isinstance(value, dict):
        return any(holds_handle(k) or holds_handle(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(holds_handle(item) for item in value)
    return False


class UnknownHandle(KeyError):
    """A ``@uN`` that this app has not shown."""

    def __init__(self, handle: str):
        super().__init__(handle)
        self.handle = handle

    def __str__(self) -> str:
        return f"{self.handle} is not a handle in this session; pick one with Ctrl+O"


class Handles:
    """The app's handle book: real user ID <-> ``@uN``, in memory only."""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._by_id: dict[str, str] = {}

    def __len__(self) -> int:
        return len(self._ids)

    def __repr__(self) -> str:  # never print the IDs
        return f"Handles({len(self._ids)})"

    def add(self, real_id: Any) -> Optional[str]:
        """The handle for ``real_id``, created if new; None for an empty value."""
        text = str(real_id).strip() if real_id is not None else ""
        if not text or isinstance(real_id, bool):
            return None
        if text not in self._by_id:
            self._ids.append(text)
            self._by_id[text] = f"@u{len(self._ids)}"
        return self._by_id[text]

    def handle_for(self, real_id: Any) -> Optional[str]:
        return self._by_id.get(str(real_id).strip()) if real_id is not None else None

    def items(self) -> list[tuple[str, str]]:
        """``(handle, real ID)`` in the order they were seen."""
        return [(f"@u{n}", real) for n, real in enumerate(self._ids, 1)]

    def resolve(self, text: Any) -> Any:
        """``text`` with every handle swapped for its real ID (non-strings unchanged).

        Raises:
            UnknownHandle: a handle this app has not shown.
        """
        if not isinstance(text, str):
            return text

        def swap(m: re.Match) -> str:
            n = int(m.group(1))
            if not 1 <= n <= len(self._ids):
                raise UnknownHandle(m.group(0))
            return self._ids[n - 1]
        return HANDLE.sub(swap, text)

    def resolve_all(self, values: dict[str, Any]) -> dict[str, Any]:
        """A copy of a ``{name: text}`` dict with handles swapped in every value."""
        return {k: self.resolve(v) for k, v in values.items()}

    # collecting ------------------------------------------------------------
    def collect(self, data: Any) -> None:
        """Give a handle to every user identifier found in ``data`` (a record,
        a list, or a JSON document as text)."""
        if isinstance(data, str):
            text = data.strip()
            if text[:1] in "{[":
                try:
                    self.collect(json.loads(text))
                except ValueError:
                    pass
            return
        if isinstance(data, dict):
            if "id_type" in data and "segment_type" in data:  # a user_identifier entry
                self._add_scalar(data.get("value"))
            for k, v in data.items():
                if is_user_id_field(k):
                    self._collect_ids(v)
                else:
                    self.collect(v)
        elif isinstance(data, (list, tuple)):
            for item in data:
                self.collect(item)

    def collect_path(self, path_values: dict[str, Any]) -> None:
        """Path values named like user IDs (``user_id``)."""
        for name, value in (path_values or {}).items():
            if is_user_id_field(name):
                self._add_scalar(value)

    def _collect_ids(self, value: Any) -> None:
        if isinstance(value, dict):
            self._add_scalar(value.get("value"))  # {value, desc}, {id_type, value}
            for k, v in value.items():
                if k == "value":
                    continue
                if is_user_id_field(k):
                    self._collect_ids(v)
                else:
                    self.collect(v)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self._collect_ids(item)
        else:
            self._add_scalar(value)

    def _add_scalar(self, value: Any) -> None:
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            self.add(value)


__all__ = ["HANDLE", "Handles", "UnknownHandle", "holds_handle"]
