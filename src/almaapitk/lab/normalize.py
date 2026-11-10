"""Turn what an almaapitk method returned into JSON-safe data, and read paths in it.

Paths: dotted keys (``payment.payment_status.value``), list indexes
(``invoice_lines[1]``) and filters (``datafield[tag=505]``). XML text is parsed
on the fly, so MARC inside a JSON response is addressable:
``anies[0].record.datafield[tag=505].subfield[code=a]``.
"""
from __future__ import annotations

import dataclasses
import datetime
import itertools
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from typing import Any

from almaapitk import AlmaResponse

_SEGMENT = re.compile(r"([^.\[\]]+)|\[([^\]]+)\]")


def normalize_result(value: Any, cap: int = 1000) -> tuple[Any, bool]:
    """Return ``(json_safe_data, capped)``."""
    if isinstance(value, AlmaResponse):
        try:
            return _safe(value.json()), False
        except ValueError:
            return value._response.text, False
    if isinstance(value, (str, bytes, Mapping, list, tuple)) or not isinstance(value, Iterable):
        return _safe(value), False
    items = list(itertools.islice(value, cap + 1))
    return [_safe(i) for i in items[:cap]], len(items) > cap


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe(v) for v in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, AlmaResponse):
        return normalize_result(value)[0]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _safe(dataclasses.asdict(value))
    return repr(value)


def xml_to_tree(text: str) -> dict:
    """XML as ``{"tag", "attrs", "text", "children"}`` nodes (namespaces dropped)."""
    return _node(ET.fromstring(text))


def _node(elem: ET.Element) -> dict:
    return {
        "tag": elem.tag.split("}", 1)[-1],
        "attrs": dict(elem.attrib),
        "text": (elem.text or "").strip(),
        "children": [_node(c) for c in elem],
    }


def looks_like_xml(value: Any) -> bool:
    return isinstance(value, str) and value.lstrip().startswith("<")


def resolve(data: Any, path: str) -> Any:
    """Value at ``path``; raises ``KeyError`` naming the segment that is missing."""
    current: list[Any] = [data]
    for name, bracket in _SEGMENT.findall(path):
        current = _step(current, name, bracket, path)
        if not current:
            raise KeyError(f"{name or '[' + bracket + ']'} (in {path})")
    values = [_leaf(v) for v in current]
    return values[0] if len(values) == 1 else values


def _step(current: list[Any], name: str, bracket: str, path: str) -> list[Any]:
    out: list[Any] = []
    for value in current:
        if looks_like_xml(value):
            try:
                value = xml_to_tree(value)
            except ET.ParseError:
                pass
        if name:
            out.extend(_by_name(value, name))
        elif bracket.isdigit() or bracket.lstrip("-").isdigit():
            out.extend(_by_index(value, int(bracket)))
        else:
            out.extend(_by_filter(value, bracket))
    return out


def _is_node(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"tag", "attrs", "text", "children"}


def _by_name(value: Any, name: str) -> list[Any]:
    if _is_node(value):
        if value["tag"] == name:  # the root element itself
            return [value]
        return [c for c in value["children"] if c["tag"] == name]
    if isinstance(value, dict) and name in value:
        return [value[name]]
    if isinstance(value, list):
        return [v for item in value for v in _by_name(item, name)]
    return []


def _by_index(value: Any, index: int) -> list[Any]:
    if isinstance(value, list) and -len(value) <= index < len(value):
        return [value[index]]
    return []


def _by_filter(value: Any, expr: str) -> list[Any]:
    key, _, wanted = expr.partition("=")
    key, wanted = key.strip(), wanted.strip().strip("'\"")
    items = value if isinstance(value, list) else [value]
    matches = []
    for item in items:
        if _is_node(item):
            if item["attrs"].get(key) == wanted:
                matches.append(item)
        elif isinstance(item, dict) and str(item.get(key)) == wanted:
            matches.append(item)
    return matches


def _leaf(value: Any) -> Any:
    """An XML element without children reads as its text."""
    if _is_node(value) and not value["children"]:
        return value["text"]
    return value
