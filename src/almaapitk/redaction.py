"""The one personal-data mask for almaapitk (issue #256, building on #142).

Every output path in the library (logging, error messages, ``repr()``,
lab CLI output) masks through this module, and consumers use the same
two functions for their own output::

    from almaapitk import redact, redact_text

    logger.info("fetched", record=redact(user))       # a dict / list copy
    print(redact_text(f"failed for {message}"))       # a string

The rule is drawn between two uses of personal data:

- **In memory** (look up a user, then create a request for them): raw.
  ``redact()`` returns a *copy*; it never changes its argument, and no
  library method masks its return value.
- **Written anywhere** (logs, terminal, files, error messages, reports):
  masked.

Masking is by Alma **field name**, because a value alone (an ID is just a
number) cannot say whether it is personal. The field lists below are the
only ones in the library; change them here.

What is masked, and how:

- Credentials (``apikey``, ``authorization``, ...): ``***REDACTED***``.
- Personal names, contact details, birth date, gender: ``<redacted>``.
- Staff names in records (``created_by``, ``operator``, ``assigned_to``,
  ...): ``<redacted>``.
- Free-text notes (user, request, receiving, vendor, item notes):
  ``<redacted>``.
- User identifiers (primary ID, user barcode and the other
  ``user_identifier`` values, ``users/<id>`` in a path): partial, the last
  three characters kept (``<...>789``).

What stays visible: record identifiers that are not personal (MMS, POL,
invoice, set IDs), codes, statuses, dates, titles, and patron-typed
request text (``comment``, ``citation_note``) the owner chose to keep.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Optional

__all__ = [
    "redact",
    "redact_text",
    "is_personal_field",
    "masked_repr",
    "CREDENTIAL_PATTERNS",
    "PERSONAL_PATTERNS",
    "STAFF_NAME_FIELDS",
    "ADDRESS_PART_FIELDS",
    "NOTE_FIELD",
    "VISIBLE_FIELDS",
    "USER_ID_PATTERNS",
    "CREDENTIAL_PLACEHOLDER",
    "PERSONAL_PLACEHOLDER",
]

# ---------------------------------------------------------------------------
# The field list. One place; every mask in the library reads it.
# ---------------------------------------------------------------------------

#: Field-name substrings for credentials -> ``***REDACTED***``.
CREDENTIAL_PATTERNS: tuple[str, ...] = (
    "apikey", "api_key", "password", "token", "secret", "authorization",
)

#: Field-name substrings for names and contact details -> ``<redacted>``.
#: No bare ``name`` entry: ``vendor_name`` and ``library_name`` are not
#: personal (issue #142).
PERSONAL_PATTERNS: tuple[str, ...] = (
    "first_name", "last_name", "middle_name", "full_name",
    "preferred_first_name", "preferred_middle_name", "preferred_last_name",
    "pref_first_name", "pref_middle_name", "pref_last_name",
    "birth_date", "birthdate", "email", "phone", "address", "gender",
    "requester_name", "patron_name", "user_full_name",
)

#: Exact field names that hold a staff member's name or user name
#: -> ``<redacted>`` (owner, issue #256). ``received_by_circ_desk`` and
#: ``managed_by_library`` are codes, so ``_by`` is not matched loosely.
STAFF_NAME_FIELDS: frozenset[str] = frozenset({
    "created_by", "updated_by", "modified_by", "last_modified_by",
    "approved_by", "approver", "operator", "last_loan_operator",
    "assigned_to", "assignee", "cataloged_by", "cataloger",
    "reviewed_by", "returned_by", "renewed_by", "staff_member",
    "staff_name", "librarian", "creator_user", "rejected_by",
})

#: Parts of a postal address -> ``<redacted>``. Inside an ``address``
#: object they are blanked anyway; listed so flat text (``line1=...``)
#: and the Lab's export rule catch them too.
ADDRESS_PART_FIELDS: frozenset[str] = frozenset({
    "line1", "line2", "line3", "line4", "line5", "city", "postal_code",
    "state_province",
})

#: Free-text note fields (``note``, ``notes``, ``note_text``, ``user_note``,
#: ``rs_note``, ``receiving_note``, ``vendor_note``, ``internal_note_1``,
#: ``statistics_note_2``, ...). A string value -> ``<redacted>``; a list or
#: object (``user_note: [{note_text, created_by, ...}]``) is walked, so
#: booleans like ``popup_note`` and codes like ``note_type`` stay visible.
NOTE_FIELD: re.Pattern[str] = re.compile(r"^(?:[a-z0-9]+_)*notes?(?:_text|_\d+)?$")

#: Patron-typed request text the owner keeps visible (issue #256, answer 1).
VISIBLE_FIELDS: frozenset[str] = frozenset({
    "comment", "comments", "citation_note", "citation_notes",
})

#: Field-name substrings for user identifiers -> last three characters kept.
USER_ID_PATTERNS: tuple[str, ...] = (
    "user_id", "user_primary_id", "primary_id", "userid", "user_name",
    "username", "user_barcode", "patron_barcode", "requester",
    "user_identifier",
)

CREDENTIAL_PLACEHOLDER = "***REDACTED***"
PERSONAL_PLACEHOLDER = "<redacted>"
_PARTIAL_PREFIX = "<...>"

# Classes returned by _classify.
_CREDENTIAL, _PERSONAL, _NOTE, _USER_ID, _WALK = "cred", "pers", "note", "uid", "walk"


def _classify(key: Any, credential_patterns: Iterable[str]) -> str:
    """Which rule applies to a field name."""
    kl = str(key).lower()
    if any(p in kl for p in credential_patterns):
        return _CREDENTIAL
    if kl in VISIBLE_FIELDS or kl.endswith("_type"):
        return _WALK  # patron-typed text, or a code (user_id_type, phone_type)
    if (any(p in kl for p in PERSONAL_PATTERNS) or kl in STAFF_NAME_FIELDS
            or kl in ADDRESS_PART_FIELDS):
        return _PERSONAL
    if NOTE_FIELD.match(kl):
        return _NOTE
    if any(p in kl for p in USER_ID_PATTERNS):
        return _USER_ID
    return _WALK


def is_personal_field(key: Any) -> bool:
    """True when ``key`` names personal data (credential, name, contact,
    staff name, free-text note or user identifier) under the shared list.

    For other masks that keep their own wider rule (the Alma Lab's export
    also replaces record IDs) but must not drift from this list.
    """
    return _classify(key, CREDENTIAL_PATTERNS) != _WALK


def partial(value: Any) -> str:
    """Keep the last three characters: ``"123456789"`` -> ``"<...>789"``.

    Three characters or fewer are blanked entirely, so a short ID is never
    shown in full.
    """
    s = str(value)
    return _PARTIAL_PREFIX if len(s) <= 3 else _PARTIAL_PREFIX + s[-3:]


# ---------------------------------------------------------------------------
# Structured data
# ---------------------------------------------------------------------------

def redact(data: Any, credential_patterns: Optional[Iterable[str]] = None) -> Any:
    """Return a masked **copy** of ``data`` (dict / list / str / scalar).

    The argument is never changed, so the raw record stays usable for the
    next API call. Strings anywhere in the structure go through
    :func:`redact_text`.

    Args:
        data: An Alma record, a list of them, a string, or a scalar.
        credential_patterns: Extra credential field-name substrings
            (the logging config's ``redact_patterns``); the built-in list
            always applies too.

    Returns:
        The masked copy.

    Example:
        >>> redact({"primary_id": "tau000000123", "full_name": "Fake Person",
        ...         "user_group": {"value": "STAFF"}})
        {'primary_id': '<...>123', 'full_name': '<redacted>', 'user_group': {'value': 'STAFF'}}
    """
    patterns = tuple(CREDENTIAL_PATTERNS) + tuple(credential_patterns or ())
    return _redact(data, patterns)


def _redact(data: Any, patterns: tuple[str, ...]) -> Any:
    if isinstance(data, dict):
        return _redact_dict(data, patterns)
    if isinstance(data, (list, tuple)):
        return [_redact(item, patterns) for item in data]
    if isinstance(data, str):
        return redact_text(data)
    return data


def _redact_dict(data: dict, patterns: tuple[str, ...]) -> dict:
    out: dict = {}
    # A user_identifier entry ({id_type: {value: BARCODE}, value: "..."}):
    # the value is a user identifier whatever its type.
    is_user_identifier = "id_type" in data
    for k, v in data.items():
        rule = _classify(k, patterns)
        if is_user_identifier and k == "value" and isinstance(v, (str, int)):
            out[k] = partial(v)
        elif rule == _CREDENTIAL:
            out[k] = CREDENTIAL_PLACEHOLDER
        elif rule == _PERSONAL:
            out[k] = _blank(v, patterns)
        elif rule == _NOTE:
            out[k] = PERSONAL_PLACEHOLDER if isinstance(v, str) else _redact(v, patterns)
        elif rule == _USER_ID:
            out[k] = _partial_any(v, patterns)
        else:
            out[k] = _redact(v, patterns)
    return out


def _blank(value: Any, patterns: tuple[str, ...]) -> Any:
    """Blank a personal value; keep booleans, empties and ``*_type`` codes.

    Containers are walked, so ``email: [{email_address, email_type,
    preferred}]`` keeps its structure and flags while every text is blanked.
    """
    if value is None or isinstance(value, bool) or value == "":
        return value
    if isinstance(value, dict):
        return {k: _redact(v, patterns) if _is_structural(k) else _blank(v, patterns)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_blank(item, patterns) for item in value]
    return PERSONAL_PLACEHOLDER


def _is_structural(key: Any) -> bool:
    """Code / flag keys inside a personal container (kept visible)."""
    kl = str(key).lower()
    return kl.endswith("_type") or kl in ("preferred", "preferred_sms", "link")


def _partial_any(value: Any, patterns: tuple[str, ...]) -> Any:
    """Partially mask a user identifier; walk containers (``user_identifier`` lists)."""
    if value is None or isinstance(value, bool) or value == "":
        return value
    if isinstance(value, dict):
        if "value" in value and isinstance(value["value"], (str, int)):
            out = {**_redact(value, patterns), "value": partial(value["value"])}
            if value.get("desc"):  # a {value, desc} user reference: desc is the name
                out["desc"] = PERSONAL_PLACEHOLDER
            return out
        return _redact(value, patterns)
    if isinstance(value, (list, tuple)):
        return [_partial_any(item, patterns) for item in value]
    return partial(value)


# ---------------------------------------------------------------------------
# Free text (log messages, error messages, reprs, serialised bodies)
# ---------------------------------------------------------------------------

_KEY = r"[A-Za-z_][A-Za-z0-9_]*"
# "key": "value"  /  'key': 'value'  /  "key": 123
_QUOTED_PAIR = re.compile(
    r"""(?P<q>["'])(?P<key>""" + _KEY + r""")(?P=q)(?P<sep>\s*:\s*)"""
    r"""(?:(?P<vq>["'])(?P<sval>(?:\\.|(?!(?P=vq)).)*)(?P=vq)|(?P<nval>-?\d[\d.]*))"""
)
# <key>value</key>
_XML_ELEMENT = re.compile(r"<(?P<key>" + _KEY + r")>(?P<val>[^<]+)</(?P=key)>")
# key=value  /  key='value'  /  key: value   (unquoted key)
_BARE_PAIR = re.compile(
    r"""(?<![\w"'])(?P<key>""" + _KEY + r""")(?P<sep>\s*=\s*|:\s+)"""
    r"""(?:(?P<vq>["'])(?P<qval>(?:\\.|(?!(?P=vq)).)*)(?P=vq)|(?P<val>[^\s,;&=)\]}'"]+)(?![=\w.-]))"""
)
# A bare note runs to the end of its clause (``user_note=call me later; x=1``).
_BARE_NOTE = re.compile(
    r"""(?i)(?<![\w"'])(?P<key>(?:[a-z0-9]+_)*notes?(?:_text|_\d+)?)(?P<sep>\s*=\s*)"""
    r"""(?P<val>[^"'\n;|<][^\n;|]*?)(?=\s*(?:[;|\n]|$|,?\s+[A-Za-z_]\w*\s*=))"""
)
# users/<id> in an Alma path. Placeholders like users/<user_id> stay.
_USER_ID_IN_PATH = re.compile(r"(users/)([^/?#&\s\"'<>]+)")
# "user 123456789", "patron: tau000000123", "identifier 123456789":
# a word naming a person followed by a token that contains a digit.
_USER_WORD_ID = re.compile(
    r"(?i)\b(?P<word>users?|patrons?|requesters?|identifier)(?P<sep>(?:\s+id)?\s*[:=]?\s+)"
    r"(?P<id>(?=[^\s,;)'\"]*\d)[^\s,;)'\"<>]{4,})"
)
# A user_identifier entry written as text: id_type {...} then its value.
_USER_IDENTIFIER_VALUE = re.compile(
    r"""(?P<head>["']?id_type["']?\s*[:=]\s*\{[^{}]*\}\s*,\s*["']?value["']?\s*[:=]\s*)"""
    r"""(?P<q>["']?)(?P<val>[^"',}\s]+)(?P=q)"""
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def redact_text(text: Any) -> Any:
    """Mask personal data inside a string; return non-strings unchanged.

    Applies the same field list as :func:`redact` to field/value pairs
    written as JSON (``"primary_id": "..."``), Python reprs
    (``'primary_id': '...'``), XML (``<primary_id>...</primary_id>``) and
    ``key=value`` / ``key: value`` text, then masks user IDs in
    ``users/<id>`` paths and after the words *user*, *patron*,
    *requester* or *identifier*, and every email address.

    A string that is a whole JSON document is parsed, masked as data and
    written back (indentation kept), so ``user_identifier`` values are
    caught too.

    Args:
        text: Any value; only ``str`` is masked.

    Returns:
        The masked string (or ``text`` unchanged when not a string).

    Example:
        >>> redact_text("GET almaws/v1/users/tau000000123 failed: user_note=call me")
        'GET almaws/v1/users/<...>123 failed: user_note=<redacted>'
    """
    if not isinstance(text, str) or not text:
        return text
    as_json = _redact_json_document(text)
    if as_json is not None:
        return as_json
    out = _USER_IDENTIFIER_VALUE.sub(
        lambda m: m.group("head") + m.group("q") + _partial_token(m.group("val")) + m.group("q"),
        text)
    out = _QUOTED_PAIR.sub(_sub_quoted_pair, out)
    out = _XML_ELEMENT.sub(_sub_xml, out)
    out = _BARE_NOTE.sub(_sub_bare_note, out)
    out = _BARE_PAIR.sub(_sub_bare_pair, out)
    out = _USER_ID_IN_PATH.sub(lambda m: m.group(1) + _partial_token(m.group(2)), out)
    out = _USER_WORD_ID.sub(
        lambda m: m.group("word") + m.group("sep") + _partial_token(m.group("id")), out)
    return _EMAIL.sub(PERSONAL_PLACEHOLDER, out)


def _partial_token(token: str) -> str:
    """Partial-mask a token unless it is already masked."""
    return token if token.startswith(_PARTIAL_PREFIX) else partial(token)


def _redact_json_document(text: str) -> Optional[str]:
    """Mask a string that is one whole JSON document; None if it is not one.

    Returned unchanged (same bytes) when nothing in it is personal, so
    output that needs no masking keeps its exact formatting.
    """
    stripped = text.strip()
    if not (stripped[:1] in "{[" and stripped[-1:] in "}]"):
        return None
    try:
        parsed = json.loads(stripped)
    except ValueError:
        return None
    masked = redact(parsed)
    if masked == parsed:
        return text
    indent = 2 if "\n" in stripped else None
    separators = None if indent else (
        ", " if ", " in stripped else ",", ": " if '": ' in stripped else ":")
    return json.dumps(masked, ensure_ascii=False, indent=indent, separators=separators)


_NO_DATA = frozenset({"True", "False", "true", "false", "None", "null", ""})


def _masked_scalar(key: str, value: str) -> Optional[str]:
    """The masked form of ``value`` under field ``key``, or None to keep it."""
    if value in _NO_DATA:
        return None
    rule = _classify(key, CREDENTIAL_PATTERNS)
    if rule == _CREDENTIAL:
        return CREDENTIAL_PLACEHOLDER
    if rule in (_PERSONAL, _NOTE):
        return PERSONAL_PLACEHOLDER if value else value
    if rule == _USER_ID:
        return _partial_token(value) if value else value
    return None


def _sub_quoted_pair(m: re.Match) -> str:
    value = m.group("sval") if m.group("sval") is not None else m.group("nval")
    masked = _masked_scalar(m.group("key"), value)
    if masked is None:
        return m.group(0)
    q = m.group("q")
    vq = m.group("vq") or '"'
    return f"{q}{m.group('key')}{q}{m.group('sep')}{vq}{masked}{vq}"


def _sub_xml(m: re.Match) -> str:
    masked = _masked_scalar(m.group("key"), m.group("val"))
    if masked is None:
        return m.group(0)
    return f"<{m.group('key')}>{masked}</{m.group('key')}>"


def _sub_bare_pair(m: re.Match) -> str:
    quoted = m.group("qval") is not None
    value = m.group("qval") if quoted else m.group("val")
    if ":" in m.group("sep") and _classify(m.group("key"), CREDENTIAL_PATTERNS) == _NOTE:
        return m.group(0)  # "note: ..." is how messages label a remark, not a field
    masked = _masked_scalar(m.group("key"), value)
    if masked is None:
        return m.group(0)
    if quoted:
        vq = m.group("vq")
        return f"{m.group('key')}{m.group('sep')}{vq}{masked}{vq}"
    return f"{m.group('key')}{m.group('sep')}{masked}"


def _sub_bare_note(m: re.Match) -> str:
    if (_classify(m.group("key"), CREDENTIAL_PATTERNS) != _NOTE
            or m.group("val").strip() in _NO_DATA):
        return m.group(0)
    return f"{m.group('key')}{m.group('sep')}{PERSONAL_PLACEHOLDER}"


def redact_url_ids(text: Any) -> Any:
    """Partially mask user IDs in ``users/<id>`` paths only (issue #142)."""
    if not isinstance(text, str):
        return text
    return _USER_ID_IN_PATH.sub(lambda m: m.group(1) + _partial_token(m.group(2)), text)


def masked_repr(obj: Any, fields: dict) -> str:
    """``ClassName(field=value, ...)`` with every value masked.

    For dataclasses and other objects that carry Alma data, so that
    ``repr()`` (what a debugger, a traceback or an f-string ``!r`` shows)
    never prints personal data. The object itself is unchanged.
    """
    parts = ", ".join(f"{k}={redact(v)!r}" for k, v in fields.items())
    return redact_text(f"{type(obj).__name__}({parts})")
