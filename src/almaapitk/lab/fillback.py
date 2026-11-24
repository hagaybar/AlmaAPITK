"""Fill-back: send only the user's changes, onto the record as it is in Alma now.

Saved baselines are masked (issue #256), so an edited copy of one holds
placeholders (``<redacted>``, ``<...>789``) where personal data was. Sending it
would overwrite real values with placeholders. Instead, at send time the Lab:

1. fetches the record fresh and checks that its masked form still matches the
   masked baseline (otherwise "baseline changed", nothing sent);
2. works out which fields the user changed (the edit against the baseline, a
   field counting as unchanged when it equals the baseline value or its
   masked form);
3. applies only those changes onto the fresh raw record, so untouched masked
   fields keep their real values from Alma;
4. refuses to send if any placeholder would still go out.

A value of exactly ``<ask>`` in the edit is asked for at send time; it is sent
and shown on screen, never saved (evidence records ``<asked>``).

JSON bodies only: XML bodies are sent as edited, and refused if they hold a
placeholder.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

from almaapitk.redaction import (
    CREDENTIAL_PLACEHOLDER,
    PERSONAL_PLACEHOLDER,
    redact,
    redact_text,
)

ASK = "<ask>"
ASKED = "<asked>"  # what evidence shows instead of a value typed at the prompt

#: Text that must never reach Alma: mask placeholders, the ask markers, and
#: their XML-escaped forms (a masked XML file read back as text).
NEVER_SENT: tuple[str, ...] = (
    PERSONAL_PLACEHOLDER, "<...>", CREDENTIAL_PLACEHOLDER, ASK, ASKED,
    "&lt;redacted&gt;", "&lt;...&gt;", "&lt;ask&gt;", "&lt;asked&gt;",
)

Path = tuple[Union[str, int], ...]


class FillBackError(ValueError):
    """The edit cannot be applied; nothing is sent."""


@dataclass
class Change:
    """One field-level change: ``kind`` is ``set``, ``add`` or ``remove``."""

    path: Path
    kind: str
    before: Any = None
    after: Any = None
    asked: bool = False


def has_placeholder(text: Any) -> bool:
    """True when ``text`` (a string) holds any :data:`NEVER_SENT` marker."""
    return isinstance(text, str) and any(marker in text for marker in NEVER_SENT)


def placeholder_paths(data: Any, path: Path = ()) -> list[Path]:
    """Every path in ``data`` whose key or string value holds a placeholder."""
    found: list[Path] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if has_placeholder(k):
                found.append(path + (k,))
            found.extend(placeholder_paths(v, path + (k,)))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found.extend(placeholder_paths(item, path + (i,)))
    elif has_placeholder(data):
        found.append(path)
    return found


def path_text(path: Path) -> str:
    """``("contact_info", "email", 0, "email_address")`` -> ``contact_info.email[0].email_address``."""
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "(whole body)"


def ask_paths(data: Any, path: Path = ()) -> list[Path]:
    """Paths whose value is exactly ``<ask>``, in document order."""
    if isinstance(data, dict):
        return [p for k, v in data.items() for p in ask_paths(v, path + (k,))]
    if isinstance(data, list):
        return [p for i, v in enumerate(data) for p in ask_paths(v, path + (i,))]
    return [path] if data == ASK else []


def fill_asks(data: Any, ask: Optional[Callable[[str], Optional[str]]]) -> tuple[Any, dict[Path, str]]:
    """A copy of ``data`` with each ``<ask>`` replaced by the answer to ``ask(path text)``.

    Raises:
        FillBackError: no way to ask, or a question was cancelled / left empty.
    """
    paths = ask_paths(data)
    if not paths:
        return data, {}
    if ask is None:
        raise FillBackError(f"{path_text(paths[0])} is <ask>, but this front end cannot ask")
    out, answers = copy.deepcopy(data), {}
    for path in paths:
        value = ask(path_text(path))
        if value is None or value == "":
            raise FillBackError(f"no value given for {path_text(path)}; nothing was sent")
        _set(out, path, value)
        answers[path] = value
    return out, answers


def _set(data: Any, path: Path, value: Any) -> None:
    for part in path[:-1]:
        data = data[part]
    data[path[-1]] = value


def _get(data: Any, path: Path) -> Any:
    for part in path:
        data = data[part]
    return data


def merge(edit: Any, base: Any, fresh: Any) -> tuple[Any, list[Change]]:
    """Apply the user's changes (``edit`` against ``base``) onto ``fresh``.

    ``base`` is the baseline as the user got it (raw in the app, masked from a
    file); its masked form is computed here, so either works. Returns the body
    to send and the changes found.
    """
    changes: list[Change] = []
    merged = _merge(edit, base, redact(base), fresh, (), changes)
    return merged, changes


def _same(edit: Any, base: Any, masked: Any) -> bool:
    return edit == base or edit == masked


def _merge(e: Any, b: Any, mb: Any, f: Any, path: Path, changes: list[Change]) -> Any:
    if _same(e, b, mb):
        return copy.deepcopy(f)  # untouched: the real value from Alma now
    if isinstance(e, dict) and isinstance(b, dict) and isinstance(f, dict):
        out: dict = {}
        for k, v in e.items():
            if k in b and k in f:
                out[k] = _merge(v, b[k], (mb or {}).get(k), f[k], path + (k,), changes)
            else:
                out[k] = v
                changes.append(Change(path + (k,), "add", after=v))
        for k in b:
            if k not in e:
                changes.append(Change(path + (k,), "remove", before=f.get(k)))
        for k in f:  # in Alma now but not in the baseline: keep it
            if k not in b and k not in e:
                out[k] = copy.deepcopy(f[k])
        return out
    if isinstance(e, list) and isinstance(b, list) and isinstance(f, list):
        if len(e) == len(b) == len(f):
            return [_merge(e[i], b[i], _at(mb, i), f[i], path + (i,), changes)
                    for i in range(len(e))]
        return _merge_resized(e, b, mb, f, path, changes)
    changes.append(Change(path, "set", before=f, after=e))
    return e


def _at(data: Any, i: int) -> Any:
    return data[i] if isinstance(data, list) and i < len(data) else None


def _merge_resized(e: list, b: list, mb: Any, f: list, path: Path,
                   changes: list[Change]) -> list:
    """A list that gained or lost entries: an entry equal to a baseline entry is
    that entry as it is in Alma now; any other entry is new and sent as typed."""
    used: set[int] = set()
    out = []
    for i, item in enumerate(e):
        j = next((j for j in range(min(len(b), len(f)))
                  if j not in used and _same(item, b[j], _at(mb, j))), None)
        if j is None:
            out.append(item)
            changes.append(Change(path + (i,), "add", after=item))
        else:
            used.add(j)
            out.append(copy.deepcopy(f[j]))
    for j in range(len(b)):
        if j not in used:
            changes.append(Change(path + (j,), "remove", before=_at(f, j)))
    return out


def mark_asked(changes: list[Change], answers: dict[Path, str]) -> None:
    """Flag changes whose new value was typed at the prompt."""
    for c in changes:
        c.asked = any(c.path[:len(p)] == p or p[:len(c.path)] == c.path for p in answers)


def render(changes: list[Change], masked_fresh: Any = None, masked_sent: Any = None) -> str:
    """The changes, one per line.

    On screen (no masked documents given) values are raw. For the evidence, pass
    the masked fresh record and the masked body to send: values are taken from
    them (so a field is masked by its real context), and asked values show as
    ``<asked>``.
    """
    if not changes:
        return "(no field changes: the record is sent as it is in Alma now)"
    saved = masked_fresh is not None or masked_sent is not None
    lines = []
    for c in changes:
        before, after = c.before, c.after
        if saved:
            before = _lookup(masked_fresh, c.path, before) if c.kind != "add" else None
            after = ASKED if c.asked else (_lookup(masked_sent, c.path, after)
                                           if c.kind != "remove" else None)
        where = path_text(c.path)
        typed = "   (typed at the prompt)" if c.asked and not saved else ""
        if c.kind == "set":
            lines.append(f"  {where}: {_show(before)} → {_show(after)}{typed}")
        elif c.kind == "add":
            lines.append(f"+ {where}: {_show(after)}{typed}")
        else:
            lines.append(f"- {where}: {_show(before)}")
    return "\n".join(lines)


def _lookup(doc: Any, path: Path, default: Any) -> Any:
    try:
        return _get(doc, path)
    except (KeyError, IndexError, TypeError):
        return PERSONAL_PLACEHOLDER if default is not None else None


def _show(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= 200 else text[:200] + " …"


def masked_text(text: str) -> str:
    """The masked form of a response body, as a saved baseline file holds it."""
    return redact_text(text) if text else text


def scrub(data: Any, values: tuple[str, ...]) -> Any:
    """A copy of ``data`` with each of ``values`` replaced by ``<asked>`` in every string."""
    if not values:
        return data
    forms = sorted({v for value in values
                    for v in (value, json.dumps(value, ensure_ascii=False)[1:-1]) if v},
                   key=len, reverse=True)

    def clean(s: str) -> str:
        for form in forms:
            s = s.replace(form, ASKED)
        return s

    def walk(d: Any) -> Any:
        if isinstance(d, dict):
            return {clean(k) if isinstance(k, str) else k: walk(v) for k, v in d.items()}
        if isinstance(d, list):
            return [walk(item) for item in d]
        return clean(d) if isinstance(d, str) else d
    return walk(data)


__all__ = ["ASK", "ASKED", "NEVER_SENT", "Change", "FillBackError", "ask_paths", "fill_asks",
           "has_placeholder", "mark_asked", "masked_text", "merge", "path_text",
           "placeholder_paths", "render", "scrub"]
