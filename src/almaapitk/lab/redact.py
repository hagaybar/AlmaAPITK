"""Redacted copies of evidence records, safe to quote in skills, issues and PRs.

Default rule (spec 5.4): values of known sensitive fields (record IDs, user
identifiers and names, contact details, barcodes, notes, institution codes),
every identifier taken from the call's inputs, MARC 001 and email / phone
patterns are replaced by stable placeholders wherever they appear (URL,
command, request and response bodies, result). Status values, codes, counts,
dates and structure stay. When unsure, replace: a lost value can be read from
the local record; a leaked one cannot be taken back.
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any, Iterator

SENSITIVE_KEYS: frozenset[str] = frozenset({
    # record identifiers
    "mms_id", "holding_id", "item_pid", "pid", "po_line", "pol_id", "po_line_id", "invoice_id",
    "invoice_number", "vendor_code", "vendor_reference_number", "set_id", "request_id",
    "external_id", "loan_id", "portfolio_id", "collection_id", "service_id", "license_code",
    "barcode", "fund_code", "user_request_id", "partner_code",
    # people
    "primary_id", "user_primary_id", "user_id", "requester", "first_name", "middle_name",
    "last_name", "full_name", "preferred_first_name", "preferred_last_name", "pref_first_name",
    "pref_last_name", "birth_date", "email", "email_address", "phone_number", "address_line_1",
    "address_line_2", "address_line_3", "address_line_4", "address_line_5", "line1", "line2",
    "line3", "line4", "line5", "city", "postal_code", "note_text", "user_note",
    # institution
    "institution_code",
})
# Inputs whose names look like identifiers are redacted wherever their value appears.
_ID_NAME = re.compile(r"(^|_)(id|ids|code|barcode|number|pid|primary)($|_)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{7,}\d(?![\w-])")
_XML_FIELD = re.compile(r"<(\w+)>([^<]+)</\1>")
_MARC_001 = re.compile(r'<controlfield tag="001">([^<]+)</controlfield>')


def find_sensitive(record: dict) -> list[tuple[str, str]]:
    """``(value, kind)`` for every value the default rule would replace, in order found."""
    found: dict[str, str] = {}
    for kind, value in _collect(record):
        if value and len(value) >= 3 and value not in found:
            found[value] = kind
    return list(found.items())


def redact(record: dict, keep: frozenset[str] = frozenset()) -> tuple[dict, list[dict]]:
    """Return ``(redacted copy, replacements)``; ``keep`` holds values to leave in."""
    found = dict(find_sensitive(record))
    placeholders: dict[str, str] = {}
    counters: dict[str, int] = {}
    replacements: list[dict] = []
    for value, kind in found.items():
        if value in keep:
            replacements.append({"placeholder": None, "kind": kind, "value_kept": True})
            continue
        counters[kind] = counters.get(kind, 0) + 1
        placeholders[value] = f"<{kind}_{counters[kind]}>"
        replacements.append({"placeholder": placeholders[value], "kind": kind, "value_kept": False})
    out = _replace(copy.deepcopy(record), placeholders)
    return out, replacements


def _collect(record: dict) -> Iterator[tuple[str, str]]:
    for name, value in (record.get("inputs") or {}).items():
        if isinstance(value, (str, int)) and (name in SENSITIVE_KEYS or _ID_NAME.search(name)):
            yield _kind_for(name), str(value)
    yield from _walk(record)


def _walk(value: Any, key: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        if key == "user_identifier" or "id_type" in value:
            if isinstance(value.get("value"), str):
                yield "user_identifier", value["value"]
        for k, v in value.items():
            if k in SENSITIVE_KEYS and isinstance(v, (str, int)) and not isinstance(v, bool):
                yield _kind_for(k), str(v)
            elif k in SENSITIVE_KEYS and isinstance(v, dict) and isinstance(v.get("value"), str):
                yield _kind_for(k), v["value"]
            yield from _walk(v, k)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item, key)
    elif isinstance(value, str):
        yield from _from_text(value)


def _from_text(text: str) -> Iterator[tuple[str, str]]:
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            yield from _walk(json.loads(text))
            return
        except ValueError:
            pass
    if stripped.startswith("<"):
        for m in _MARC_001.finditer(text):
            yield "mms_id", m.group(1)
        for tag, val in _XML_FIELD.findall(text):
            if tag in SENSITIVE_KEYS:
                yield _kind_for(tag), val
    for m in _EMAIL.finditer(text):
        yield "email", m.group(0)
    for m in _PHONE.finditer(text):
        if sum(ch.isdigit() for ch in m.group(0)) >= 9 and not m.group(0).strip().isdigit():
            yield "phone", m.group(0)


def _kind_for(name: str) -> str:
    if name in ("email", "email_address"):
        return "email"
    if name in ("primary_id", "user_primary_id", "user_id", "requester"):
        return "user"
    return name


def _replace(value: Any, placeholders: dict[str, str]) -> Any:
    if not placeholders:
        return value
    if isinstance(value, dict):
        return {k: _replace(v, placeholders) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace(v, placeholders) for v in value]
    if isinstance(value, int) and not isinstance(value, bool) and str(value) in placeholders:
        return placeholders[str(value)]
    if isinstance(value, str):
        return _pattern(tuple(placeholders)).sub(lambda m: placeholders[m.group(0)], value)
    return value


_cache: dict[tuple[str, ...], re.Pattern] = {}


def _pattern(values: tuple[str, ...]) -> re.Pattern:
    if values not in _cache:
        ordered = sorted(values, key=len, reverse=True)
        alternation = "|".join(re.escape(v) for v in ordered)
        _cache[values] = re.compile(rf"(?<![\w@.-])(?:{alternation})(?![\w@-])")
    return _cache[values]
