"""The one personal-data mask for almaapitk (issue #256, building on #142).

Every output path in the library (logging, error messages, ``repr()``,
Alma Lab's saved files) masks through this module, and consumers use the same
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
- Staff names in records (``created_by``, ``operator``, ``approved_by``,
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
    "NOTE_FIELDS",
    "CONTACT_FIELDS",
    "VISIBLE_FIELDS",
    "USER_ID_PATTERNS",
    "CREDENTIAL_PLACEHOLDER",
    "PERSONAL_PLACEHOLDER",
    "contains_mask",
    "is_user_id_field",
    "masked_exception",
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
#: personal (issue #142). ``email`` and ``address`` are *not* substrings
#: here (``ip_address``, ``email_template`` are not personal): their
#: field names are listed exactly in :data:`CONTACT_FIELDS`.
PERSONAL_PATTERNS: tuple[str, ...] = (
    "first_name", "last_name", "middle_name", "full_name",
    "preferred_first_name", "preferred_middle_name", "preferred_last_name",
    "pref_first_name", "pref_middle_name", "pref_last_name",
    "birth_date", "birthdate", "phone", "gender",
    "requester_name", "patron_name", "user_full_name",
)

#: Exact contact-detail field names -> ``<redacted>``: the user record's
#: ``email`` / ``address`` lists and their parts, and the lending request's
#: requester contact (``text_email``, ``text_postal_1``..``4``; Ex Libris
#: rest_lending_request.xsd, checked 2026-11-24).
CONTACT_FIELDS: frozenset[str] = frozenset({
    "email", "emails", "email_address", "preferred_email", "user_email",
    "patron_email", "requester_email", "text_email",
    "address", "addresses", "postal_address", "user_address", "patron_address",
    "requester_address", "mailing_address",
    "text_postal_1", "text_postal_2", "text_postal_3", "text_postal_4",
})

#: Exact field names that hold a staff member's name or user name
#: -> ``<redacted>`` (owner, issue #256). ``received_by_circ_desk`` and
#: ``managed_by_library`` are codes, so ``_by`` is not matched loosely.
#: ``approved_by`` is the invoice's (rest_invoice.xsd).
STAFF_NAME_FIELDS: frozenset[str] = frozenset({
    "created_by", "updated_by", "modified_by", "last_modified_by",
    "approved_by", "approver", "operator", "last_loan_operator",
    "assignee", "cataloged_by", "cataloger",
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

#: The note fields confirmed in Ex Libris' schemas (2026-11-24). All of
#: them also match :data:`NOTE_FIELD`; they are listed so the list is
#: explicit and a change to the pattern cannot drop one silently.
NOTE_FIELDS: frozenset[str] = frozenset({
    "note", "notes", "note_text", "user_note", "rs_note",
    "receiving_note", "vendor_note", "renewal_note",
    "cancellation_restriction_note",
})

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
    if (any(p in kl for p in PERSONAL_PATTERNS) or kl in CONTACT_FIELDS
            or kl in STAFF_NAME_FIELDS or kl in ADDRESS_PART_FIELDS):
        return _PERSONAL
    if kl in NOTE_FIELDS or NOTE_FIELD.match(kl):
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


def is_user_id_field(key: Any) -> bool:
    """True when ``key`` names a user identifier (``primary_id``, ``user_id``,
    ``requester``, ``user_identifier``, ...): the fields masked to ``<...>789``."""
    return _classify(key, CREDENTIAL_PATTERNS) == _USER_ID


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
    # A user_identifier entry met on its own ({id_type, value, segment_type}):
    # the value is a user identifier whatever its type. Inside a user record
    # the ``user_identifier`` key already masks it. An ``{id_type, value}``
    # without ``segment_type`` (an ISSN, an ISBN) stays visible.
    is_user_identifier = "id_type" in data and "segment_type" in data
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
# users/<id> in an Alma path. Placeholders (users/<user_id>) and path templates
# (users/{user_id}, as evidence records the endpoint) stay.
_USER_ID_IN_PATH = re.compile(r"(users/)(?!\{[A-Za-z_]+\})([^/?#&\s\"'<>]+)")
# "user 123456789", "patron: tau000000123", "requester id 123456789":
# a singular word naming one person, then a token that contains a digit.
# Plurals are counts ("Processed users: 1500"), a bare "identifier" names
# any record's identifier (an MMS ID; only Alma's "User with identifier X"
# counts), and a date after the word is a date.
_USER_WORD_ID = re.compile(
    r"(?i)\b(?P<word>user(?:\s+with\s+identifier)?|patron|requester)"
    r"(?P<sep>(?:\s+id)?\s*[:=]?\s+)"
    r"(?!\d{4}-\d{2}-\d{2}(?:[T\s]|$|[^\w-]))"
    r"(?P<id>(?=[^\s,;)'\"]*\d)[^\s,;)'\"<>]{4,})"
)
# A user_identifier entry written as text: id_type {...} then its value.
# Applied only to text that is about user identifiers (it names
# ``user_identifier`` or ``segment_type``), so an ISSN stays visible.
_USER_IDENTIFIER_HINT = re.compile(r"user_identifier|segment_type")
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
    ``users/<id>`` paths and after the words *user*, *patron* or
    *requester* (singular; not a date), and every email address.

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
    out = text
    if _USER_IDENTIFIER_HINT.search(text):
        out = _USER_IDENTIFIER_VALUE.sub(
            lambda m: m.group("head") + m.group("q") + _partial_token(m.group("val"))
            + m.group("q"), text)
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


#: Plural words written as labels hold counts, not IDs ("users: 1500").
_COUNT_LABELS = frozenset({"users", "patrons", "requesters"})


def _sub_bare_pair(m: re.Match) -> str:
    quoted = m.group("qval") is not None
    value = m.group("qval") if quoted else m.group("val")
    if m.group("key").lower() in _COUNT_LABELS:
        return m.group(0)
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


# ---------------------------------------------------------------------------
# Masked data must never be sent back to Alma
# ---------------------------------------------------------------------------

_MASK_MARKERS = (CREDENTIAL_PLACEHOLDER, PERSONAL_PLACEHOLDER, _PARTIAL_PREFIX)


def contains_mask(data: Any) -> bool:
    """True when ``data`` (a string, or any value inside a dict / list) holds
    a mask placeholder (``<redacted>``, ``<...>``, ``***REDACTED***``).

    A masked copy read back from a file must not be sent to Alma as if it
    were the record: it would overwrite real values with placeholders.
    """
    if isinstance(data, str):
        return any(marker in data for marker in _MASK_MARKERS)
    if isinstance(data, dict):
        return any(contains_mask(k) or contains_mask(v) for k, v in data.items())
    if isinstance(data, (list, tuple)):
        return any(contains_mask(item) for item in data)
    return False


# ---------------------------------------------------------------------------
# Exception chains (tracebacks print every __cause__ / __context__)
# ---------------------------------------------------------------------------

_MASKED_TYPES: dict[type, type] = {}


def _masked_type(cls: type) -> type:
    """A subclass of ``cls`` whose ``str()`` is the stored masked text.

    Same name and module, so a traceback reads as before and ``except
    cls`` / ``isinstance`` still match.
    """
    if cls not in _MASKED_TYPES:
        _MASKED_TYPES[cls] = type(cls.__name__, (cls,), {
            "__module__": cls.__module__,
            "__qualname__": cls.__qualname__,
            "__str__": lambda self: self._almaapitk_masked_text,
            "__repr__": lambda self: f"{cls.__name__}({self._almaapitk_masked_text!r})",
        })
    return _MASKED_TYPES[cls]


def masked_exception(exc: Optional[BaseException],
                     _seen: Optional[dict] = None) -> Optional[BaseException]:
    """A copy of ``exc`` whose message, and every chained cause / context,
    is masked; ``exc`` itself when nothing in the chain is personal.

    For library code that re-raises or chains a third-party exception
    (``raise AlmaServerError(...) from masked_exception(e)``): the default
    traceback prints each chained exception's ``str()``, and a ``requests``
    error carries the request URL (``/almaws/v1/users/<id>``). The copy keeps
    the type (``except requests.ConnectionError`` still matches), the
    traceback and the attributes (``response``, ``request``); the original is
    unchanged.
    """
    if exc is None:
        return None
    seen = {} if _seen is None else _seen
    if id(exc) in seen:
        return seen[id(exc)]
    seen[id(exc)] = exc  # cycle guard while the chain is walked
    try:
        text = str(exc)
    except Exception:  # noqa: BLE001 - a broken __str__ is shown as the type only
        text = ""
    masked = redact_text(text)
    cause = masked_exception(exc.__cause__, seen)
    context = masked_exception(exc.__context__, seen)
    if masked == text and cause is exc.__cause__ and context is exc.__context__:
        return exc
    try:
        copy = _copy_exception(exc)
        copy.__class__ = _masked_type(type(exc))
        copy._almaapitk_masked_text = masked
    except Exception:  # noqa: BLE001 - an exception type that cannot be copied
        copy = RuntimeError(f"{type(exc).__module__}.{type(exc).__qualname__}: {masked}")
    copy.__traceback__ = exc.__traceback__
    copy.__cause__ = cause
    copy.__context__ = context
    copy.__suppress_context__ = exc.__suppress_context__
    seen[id(exc)] = copy
    return copy


def _copy_exception(exc: BaseException) -> BaseException:
    """A shallow copy: same args and attributes, a new object."""
    copy = type(exc).__new__(type(exc), *exc.args)
    copy.args = exc.args
    copy.__dict__.update(getattr(exc, "__dict__", {}))
    return copy
