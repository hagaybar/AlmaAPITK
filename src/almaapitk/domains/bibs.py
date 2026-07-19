import xml.etree.ElementTree as ET
from collections.abc import Sequence
from typing import Any, Dict, List, Optional, Tuple, Union

from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError, AlmaResponse, AlmaValidationError

# Accepted shapes for a datafield's subfields (issue #185). Either:
#   * a ``dict`` — backward-compatible, but a dict key cannot repeat, so it
#     can never express a repeated subfield code; or
#   * an ordered list/sequence of ``[code, value]`` pairs — preserves order
#     AND repeated codes (e.g. ``650 ... $x History $x 20th century``),
#     mirroring the creation builder ``build_alma_bib_xml``.
# Both normalise to an ordered ``list[(code, value)]`` via
# ``BibliographicRecords._normalize_subfields``.
SubfieldsArg = Union[Dict[str, str], Sequence[Sequence[str]]]


# Documented default MARC leader used by ``build_alma_bib_xml`` when a spec
# omits ``leader``. Callers own leader validity (issue #179); this is a
# reasonable "new textual monograph" default and can be overridden per-spec.
# Ldr positions: 05=n (new) 06=a (language material) 07=m (monograph);
# 09=a (Unicode/UTF-8, matches the XML encoding); 17=3 (abbreviated); and
# Ldr/18=i (ISBD punctuation) rather than the old ``u`` (unknown), which is the
# expected descriptive-cataloging form for current RDA cataloguing (issue #188).
DEFAULT_LEADER = "     nam a22     3i 4500"


def _strip_illegal_xml_chars(text: str) -> str:
    """Strip characters that are illegal in XML 1.0 text/attribute content.

    Only the C0 control characters (except tab, newline and carriage return)
    are removed. This deliberately does **not** escape XML markup characters
    (``&``, ``<``, ``>``): escaping is left to ``xml.etree.ElementTree`` at
    serialisation time so values are escaped exactly once (issue #179 — the
    old ``_sanitize_xml_text`` + ET path double-escaped ``&`` into
    ``&amp;amp;``).

    Args:
        text: Raw text to clean.

    Returns:
        ``text`` with illegal control characters removed.
    """
    if not text:
        return ""
    return "".join(ch for ch in text if ord(ch) >= 0x20 or ch in "\t\n\r")


def _normalize_indicator(value: Any) -> str:
    """Coerce an indicator value to a single MARC indicator character.

    Args:
        value: Indicator from a spec field; ``None`` or ``""`` become a blank
            indicator (a single space).

    Returns:
        A one-character indicator string.

    Raises:
        AlmaValidationError: If ``value`` is not a single legal MARC indicator
            character (a blank, a digit ``0-9``, or a lowercase letter
            ``a-z``). The fill character ``|`` is not permitted in an indicator
            position (issue #187).
    """
    if value is None or value == "":
        return " "
    text = str(value)
    if len(text) != 1:
        raise AlmaValidationError(
            f"MARC indicator must be a single character, got {text!r}"
        )
    # #187: legal indicator values are a blank, a digit, or a lowercase letter.
    # Uppercase letters, punctuation and the fill character '|' are rejected.
    if not (text == " " or text.isdigit() or ("a" <= text <= "z")):
        raise AlmaValidationError(
            f"MARC indicator {text!r} is invalid: expected a blank, a digit "
            "(0-9), or a lowercase letter (a-z); the fill character '|' is not "
            "allowed in an indicator"
        )
    return text


def build_alma_bib_xml(spec: Dict[str, Any], require_245: bool = False) -> str:
    """Build Alma's non-namespaced ``<bib><record>`` MARCXML from a spec.

    Pure, network-free helper (the XML-assembly shape mirrors
    ``BibliographicRecords._build_updated_marc_xml`` but is spec-driven and
    escapes exactly once). The ``spec`` is plain JSON-serialisable data so it
    is usable from non-Python callers (e.g. Power Automate)::

        spec = {
            "leader": "     nam a22     3i 4500",   # optional; default if omitted
            "fields": [
                {"tag": "008", "data": "..."},                       # control field
                {"tag": "245", "ind1": "1", "ind2": "0",
                 "subfields": [["a", "Data Reduction Methods"]]},    # data field
                {"tag": "650", "ind1": " ", "ind2": "0",
                 "subfields": [["a", "Data reduction"]]},
                {"tag": "650", "ind1": " ", "ind2": "0",
                 "subfields": [["a", "Data science"]]},
            ],
        }

    Beyond spec *shape*, the builder enforces MARC *content designation*
    (issue #187) so it is not more permissive than the editing/reading paths:
    tags must be three digits, control vs data is decided by the tag (``00X``
    is a control field carrying ``data``; ``010``-``999`` is a data field
    carrying ``subfields`` — a data-range tag with ``data`` is rejected),
    subfield codes are a single lowercase letter or digit, and indicators are a
    blank / digit / lowercase letter.

    Args:
        spec: Mapping with an optional ``leader`` string and a non-empty
            ``fields`` list. Each field needs a 3-digit string ``tag``; control
            fields (``00X``) carry ``data``, data fields carry ``ind1`` /
            ``ind2`` (default blank) and a non-empty ``subfields`` list of
            ``[code, value]`` pairs. Field and subfield order is preserved and
            repeated tags/subfields are supported.
        require_245: When ``True``, assert client-side that the record contains
            exactly one ``245`` Title Statement (mandatory, non-repeatable in
            MARC 21) before building — a cheap pre-flight that beats a network
            round-trip to Alma's validator (issue #189). Default ``False``
            delegates completeness to Alma's ``validate=true``.

    Returns:
        A ``<bib><record>...</record></bib>`` XML string ready for
        :meth:`BibliographicRecords.create_record`.

    Raises:
        AlmaValidationError: If the spec is malformed (not a dict, missing or
            empty ``fields``, a field without a valid 3-digit ``tag``, a control
            field without ``data``, a data-range tag carrying ``data``, a data
            field without ``subfields``, an invalid subfield code or indicator),
            or — when ``require_245`` is set — if exactly one ``245`` is not
            present.
    """
    if not isinstance(spec, dict):
        raise AlmaValidationError("spec must be a dict")

    fields = spec.get("fields")
    if not isinstance(fields, list) or not fields:
        raise AlmaValidationError("spec must include a non-empty 'fields' list")

    # #189: optional client-side completeness gate. 245 (Title Statement) is
    # mandatory and non-repeatable in MARC 21, so exactly one must be present.
    if require_245:
        n245 = sum(
            1 for f in fields if isinstance(f, dict) and f.get("tag") == "245"
        )
        if n245 != 1:
            raise AlmaValidationError(
                "MARC completeness check (require_245): a bibliographic record "
                "must contain exactly one 245 Title Statement, found "
                f"{n245} (pass require_245=False to delegate this to Alma's "
                "validator)"
            )

    leader_text = spec.get("leader", DEFAULT_LEADER)
    if not isinstance(leader_text, str):
        raise AlmaValidationError("'leader' must be a string when provided")

    bib_elem = ET.Element("bib")
    record_elem = ET.SubElement(bib_elem, "record")

    leader_elem = ET.SubElement(record_elem, "leader")
    leader_elem.text = _strip_illegal_xml_chars(leader_text)

    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            raise AlmaValidationError(f"field at index {index} must be a dict")

        tag = field.get("tag")
        if not tag or not isinstance(tag, str):
            raise AlmaValidationError(
                f"field at index {index} is missing a string 'tag'"
            )
        # #187: MARC tags are exactly three numeric characters. Mirrors the
        # check update_marc_field / get_marc_subfield already enforce, so the
        # builder is not more permissive than the editing/reading paths.
        if len(tag) != 3 or not tag.isdigit():
            raise AlmaValidationError(
                f"MARC tag must be exactly 3 digits, got {tag!r} "
                f"(field at index {index})"
            )

        # #187: control vs data is decided by the TAG (00X = control field),
        # NOT by the presence of a 'data' key. A data-range tag (010-999)
        # carrying 'data' would emit a <controlfield> for a data tag —
        # structurally invalid MARC — so it is rejected here.
        is_control = tag.startswith("00")
        if is_control:
            if "data" not in field:
                raise AlmaValidationError(
                    f"control field {tag} requires a 'data' value"
                )
            control_elem = ET.SubElement(record_elem, "controlfield")
            control_elem.set("tag", tag)
            # Assign to .text and let ET escape at serialisation (no pre-escape).
            control_elem.text = _strip_illegal_xml_chars(str(field["data"]))
            continue

        if "data" in field:
            raise AlmaValidationError(
                f"data field {tag} must not carry control-field 'data'; only "
                "00X control fields use 'data'. Provide 'subfields' instead"
            )

        subfields = field.get("subfields")
        if not subfields:
            raise AlmaValidationError(
                f"data field {tag} requires a non-empty 'subfields' list"
            )
        if not isinstance(subfields, list):
            raise AlmaValidationError(
                f"field {tag} 'subfields' must be a list of [code, value] pairs"
            )

        data_elem = ET.SubElement(record_elem, "datafield")
        data_elem.set("tag", tag)
        data_elem.set("ind1", _normalize_indicator(field.get("ind1", " ")))
        data_elem.set("ind2", _normalize_indicator(field.get("ind2", " ")))

        for sf_index, subfield in enumerate(subfields):
            if not isinstance(subfield, (list, tuple)) or len(subfield) != 2:
                raise AlmaValidationError(
                    f"subfield {sf_index} of field {tag} must be a "
                    "[code, value] pair"
                )
            code, value = subfield
            if not code or not isinstance(code, str):
                raise AlmaValidationError(
                    f"subfield {sf_index} of field {tag} needs a string code"
                )
            # #187: subfield codes are a single lowercase letter or digit.
            if len(code) != 1 or not (("a" <= code <= "z") or code.isdigit()):
                raise AlmaValidationError(
                    f"subfield code {code!r} in field {tag} must be a single "
                    "lowercase letter (a-z) or digit (0-9)"
                )
            subfield_elem = ET.SubElement(data_elem, "subfield")
            subfield_elem.set("code", code)
            subfield_elem.text = _strip_illegal_xml_chars(
                "" if value is None else str(value)
            )

    # ``encoding='unicode'`` returns a str; ET escapes &, <, > exactly once.
    return ET.tostring(bib_elem, encoding="unicode")


def _pymarc_record_to_spec(record: Any) -> Dict[str, Any]:
    """Convert a ``pymarc.Record`` into a ``build_alma_bib_xml`` spec.

    Duck-typed over the ``pymarc`` field API so it works across pymarc
    versions (the subfield container changed shape between pymarc 4 and 5).

    Args:
        record: A ``pymarc.Record`` instance.

    Returns:
        A spec dict suitable for :func:`build_alma_bib_xml`.
    """
    spec: Dict[str, Any] = {"leader": str(record.leader), "fields": []}

    for field in record.fields:
        if field.is_control_field():
            spec["fields"].append({"tag": field.tag, "data": field.data})
            continue

        indicators = getattr(field, "indicators", None)
        if indicators is not None:
            ind1, ind2 = indicators[0], indicators[1]
        else:  # pragma: no cover - very old pymarc fallback
            ind1 = getattr(field, "indicator1", " ")
            ind2 = getattr(field, "indicator2", " ")

        subfields: List[List[str]] = []
        raw_subfields = list(field.subfields)
        if raw_subfields and hasattr(raw_subfields[0], "code"):
            # pymarc >= 5: list of Subfield(code, value) namedtuples.
            for subfield in raw_subfields:
                subfields.append([subfield.code, subfield.value])
        else:  # pragma: no cover - pymarc < 5 flat [code, value, ...] list
            iterator = iter(raw_subfields)
            for code in iterator:
                subfields.append([code, next(iterator, "")])

        spec["fields"].append(
            {
                "tag": field.tag,
                "ind1": ind1,
                "ind2": ind2,
                "subfields": subfields,
            }
        )

    return spec


class BibliographicRecords:
    """
    Domain class for handling Alma Bibliographic Records API operations.
    Builds upon and improves the existing bib record functionality.
    """
    
    def __init__(self, client: AlmaAPIClient):
        self.client = client
        self.logger = client.logger

    def _extract_marc_subfield_values(self, marc_xml: str, field: str, subfield: str) -> List[str]:
        """
        Extract subfield values from MARC XML.
        
        Args:
            marc_xml: MARC XML string
            field: MARC field number
            subfield: Subfield code
            
        Returns:
            List of subfield values

        Raises:
            AlmaValidationError: If ``marc_xml`` cannot be parsed. The parse
                failure is propagated (not swallowed) so ``get_marc_subfield``
                can distinguish "genuinely absent" (``[]``) from "unparseable
                MARC" under its ``strict`` flag (issue #190).
        """
        try:
            root = ET.fromstring(marc_xml)
        except ET.ParseError as e:
            raise AlmaValidationError(f"Unparseable MARC XML: {e}") from e

        values = []
        # Find all datafields with the specified tag
        datafields = root.findall(f"./datafield[@tag='{field}']")

        for datafield in datafields:
            # Find all subfields with the specified code
            subfields = datafield.findall(f"./subfield[@code='{subfield}']")
            for sf in subfields:
                if sf.text:
                    values.append(sf.text.strip())

        return values

    def get_record(self, mms_id: str, view: str = "full", expand: str = None) -> AlmaResponse:
        """
        Retrieve a bibliographic record by MMS ID.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            view: Level of detail (brief, full)
            expand: Additional data to include (p_avail, e_avail, d_avail)
        
        Returns:
            AlmaResponse containing the bibliographic record
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        params = {"view": view}
        if expand:
            params["expand"] = expand
        
        endpoint = f"almaws/v1/bibs/{mms_id}"
        response = self.client.get(endpoint, params=params)
        
        self.logger.info(f"Retrieved bib record {mms_id}")
        return response

    def create_record(self, marc_xml: str, validate: bool = True,
                     override_warning: bool = False) -> AlmaResponse:
        """
        Create a new bibliographic record.
        
        Args:
            marc_xml: MARC XML data for the record
            validate: Whether to validate the record
            override_warning: Whether to override validation warnings
        
        Returns:
            AlmaResponse containing the created record
        """
        if not marc_xml:
            raise AlmaValidationError("MARC XML data is required")
        
        # Validate XML structure
        try:
            ET.fromstring(marc_xml)
        except ET.ParseError as e:
            raise AlmaValidationError(f"Invalid XML structure: {e}")
        
        params = {
            "validate": "true" if validate else "false",
            "override_warning": "true" if override_warning else "false"
        }
        
        endpoint = "almaws/v1/bibs"
        response = self.client.post(endpoint, data=marc_xml,
                                  content_type='application/xml', params=params)

        self.logger.info("Created new bib record")
        return response

    def create_record_from_fields(self, spec: Dict[str, Any], validate: bool = True,
                                  override_warning: bool = False,
                                  require_245: bool = True) -> AlmaResponse:
        """
        Create a new bibliographic record from a native, structure-driven spec.

        Builds Alma's non-namespaced ``<bib><record>`` XML from ``spec`` via
        :func:`build_alma_bib_xml` and funnels it into :meth:`create_record`,
        so callers never hand-assemble MARCXML. Pattern source: thin
        builder-then-``create_record`` wrapper (issue #179).

        Args:
            spec: JSON-serialisable field structure (see
                :func:`build_alma_bib_xml`).
            validate: Whether Alma should validate the record.
            override_warning: Whether to override validation warnings.
            require_245: Assert client-side that the record has exactly one
                ``245`` before the network round-trip (issue #189). Defaults to
                ``True`` for the create path — a real bib needs a title; pass
                ``False`` to delegate the check to Alma.

        Returns:
            AlmaResponse containing the created record.

        Raises:
            AlmaValidationError: If ``spec`` is malformed or (by default) has no
                single ``245``.
        """
        marc_xml = build_alma_bib_xml(spec, require_245=require_245)

        self.logger.info("Creating bib record from field spec")
        return self.create_record(
            marc_xml, validate=validate, override_warning=override_warning
        )

    def create_record_from_pymarc(self, record: Any, validate: bool = True,
                                 override_warning: bool = False,
                                 require_245: bool = True) -> AlmaResponse:
        """
        Create a new bibliographic record from a ``pymarc.Record``.

        Converts the record to a native spec and delegates to
        :meth:`create_record_from_fields`. ``pymarc`` is an optional extra
        (``pip install almaapitk[pymarc]``) imported lazily here so the core
        install stays dependency-light (issue #179).

        Args:
            record: A ``pymarc.Record`` instance.
            validate: Whether Alma should validate the record.
            override_warning: Whether to override validation warnings.
            require_245: Assert client-side that the record has exactly one
                ``245`` before creating (issue #189); default ``True``.

        Returns:
            AlmaResponse containing the created record.

        Raises:
            AlmaValidationError: If ``pymarc`` is not installed or ``record``
                is not a ``pymarc.Record`` instance.
        """
        try:
            import pymarc  # noqa: F401  (optional dependency, imported lazily)
        except ImportError as exc:
            raise AlmaValidationError(
                "create_record_from_pymarc requires the optional 'pymarc' "
                "extra. Install it with: pip install almaapitk[pymarc]"
            ) from exc

        if not isinstance(record, pymarc.Record):
            raise AlmaValidationError("record must be a pymarc.Record instance")

        spec = _pymarc_record_to_spec(record)

        self.logger.info("Creating bib record from pymarc record")
        return self.create_record_from_fields(
            spec, validate=validate, override_warning=override_warning,
            require_245=require_245
        )

    def update_record(self, mms_id: str, marc_xml: str, validate: bool = True,
                     override_warning: bool = True, override_lock: bool = True,
                     stale_version_check: bool = False) -> AlmaResponse:
        """
        Update an existing bibliographic record.
        
        Args:
            mms_id: The MMS ID of the record to update
            marc_xml: Updated MARC XML data
            validate: Whether to validate the record
            override_warning: Whether to override validation warnings
            override_lock: Whether to override record locks
            stale_version_check: Whether to check for stale versions
        
        Returns:
            AlmaResponse containing the updated record
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        if not marc_xml:
            raise AlmaValidationError("MARC XML data is required")
        
        # Validate XML structure
        try:
            ET.fromstring(marc_xml)
        except ET.ParseError as e:
            raise AlmaValidationError(f"Invalid XML structure: {e}")
        
        params = {
            "validate": "true" if validate else "false",
            "override_warning": "true" if override_warning else "false",
            "override_lock": "true" if override_lock else "false",
            "stale_version_check": "true" if stale_version_check else "false"
        }
        
        endpoint = f"almaws/v1/bibs/{mms_id}"
        response = self.client.put(endpoint, data=marc_xml, 
                                 content_type='application/xml', params=params)
        
        self.logger.info(f"Updated bib record {mms_id}")
        return response
    
    def delete_record(self, mms_id: str, override_attached_items: bool = False) -> AlmaResponse:
        """
        Delete a bibliographic record.
        
        Args:
            mms_id: The MMS ID of the record to delete
            override_attached_items: Whether to delete even if items are
                attached (overrides Alma's deletion warnings).

        Returns:
            AlmaResponse confirming deletion
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")

        # #193: Alma's DELETE /bibs/{mms_id} 'override' is a boolean-valued
        # string (true/false), per docs/alma-swagger/bibs.json. Sending
        # 'attached_items' is rejected ("Make sure the override parameter is
        # false or true"), so the override branch never worked. Send 'true'.
        params = {}
        if override_attached_items:
            params["override"] = "true"

        endpoint = f"almaws/v1/bibs/{mms_id}"
        response = self.client.delete(endpoint, params=params)
        
        self.logger.info(f"Deleted bib record {mms_id}")
        return response
    
    def update_marc_field(self, mms_id: str, field: str, subfields: SubfieldsArg,
                         ind1: str = ' ', ind2: str = ' ',
                         mode: str = "replace_first") -> AlmaResponse:
        """
        Update, replace, or append a MARC field in a bibliographic record.

        Many MARC tags (6XX/5XX/7XX/020/490/856, etc.) are **repeatable**, so a
        record routinely carries several occurrences of the same tag (e.g. three
        650 subject headings). This method only touches the occurrence(s)
        selected by ``mode`` and preserves every other occurrence untouched, so
        an update to one instance never silently drops the rest (issue #184).

        Args:
            mms_id: The MMS ID of the record.
            field: MARC field number (e.g. ``"650"``); must be a 3-digit tag.
            subfields: Subfields for the new/updated field, in one of two
                shapes (see :data:`SubfieldsArg`):

                * an ordered list of ``[code, value]`` pairs, e.g.
                  ``[["a", "Science"], ["x", "History"], ["x", "20th century"]]``
                  — preserves order **and** repeated subfield codes (many
                  MARC subfields are Repeatable); or
                * a ``dict`` (``{"a": "Science", "x": "History"}``) —
                  accepted for backward compatibility, but a dict key cannot
                  repeat so it cannot express a repeated subfield code.
            ind1: First indicator for the new/updated field.
            ind2: Second indicator for the new/updated field.
            mode: How to apply the change to the target tag:

                * ``"replace_first"`` (default) — replace the *first* occurrence
                  of ``field`` in place and preserve every other occurrence of
                  the same tag. If the tag is absent it is created. This is the
                  non-destructive default.
                * ``"replace_all"`` — remove *all* existing occurrences of
                  ``field`` and add a single new one built from ``subfields``.
                  Use this to intentionally collapse a repeated tag to one value.
                * ``"append"`` — keep every existing occurrence of ``field`` and
                  add one additional occurrence built from ``subfields``.

        Returns:
            AlmaResponse containing the updated record.

        Raises:
            AlmaValidationError: If ``mms_id`` is empty, ``field`` is not a
                3-digit tag, ``subfields`` is empty or malformed (each pair
                must be ``[code, value]`` with a single-character code), or
                ``mode`` is not one of
                ``"replace_first"``/``"replace_all"``/``"append"``.
            AlmaAPIError: If the record cannot be retrieved or has no MARC XML.
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")

        if not field or not field.isdigit() or len(field) != 3:
            raise AlmaValidationError("Field must be a 3-digit number")

        # Normalise (and validate) subfields into ordered (code, value)
        # pairs up front so bad input fails before any API round-trip.
        # Accepts both a dict and a list of [code, value] pairs; the list
        # form is the only one that can carry a repeated subfield code
        # (issue #185).
        subfield_pairs = self._normalize_subfields(subfields)

        valid_modes = ("replace_first", "replace_all", "append")
        if mode not in valid_modes:
            raise AlmaValidationError(
                f"mode must be one of {valid_modes}, got {mode!r}"
            )

        try:
            # Get current record
            self.logger.info(
                f"Updating MARC field {field} for record {mms_id} (mode={mode})"
            )

            response = self.get_record(mms_id)
            if not response.success:
                raise AlmaAPIError(f"Failed to retrieve record {mms_id}")

            bib_data = response.json()
            marc_xml = bib_data.get('anies', [''])[0]

            if not marc_xml:
                raise AlmaAPIError("No MARC XML found in record")

            # Parse XML
            try:
                root = ET.fromstring(marc_xml)
            except ET.ParseError as e:
                raise AlmaValidationError(f"Invalid MARC XML: {e}")

            # Build updated XML
            updated_xml = self._build_updated_marc_xml(
                root, field, subfield_pairs, ind1, ind2, mode
            )

            # Update the record
            return self.update_record(mms_id, updated_xml)

        except Exception as e:
            self.logger.error(f"Error updating MARC field {field} for record {mms_id}: {e}")
            raise

    def _build_updated_marc_xml(self, root: ET.Element, field: str,
                               subfields: List[Tuple[str, str]],
                               ind1: str, ind2: str,
                               mode: str = "replace_first") -> str:
        """
        Rebuild the record's MARC XML applying the field change per ``mode``.

        Repeatable tags are preserved: only the occurrence(s) selected by
        ``mode`` are altered — every untargeted occurrence of ``field`` is
        copied through verbatim. See :meth:`update_marc_field` for the semantics
        of ``replace_first`` / ``replace_all`` / ``append``.
        """
        # Create new root structure
        bib_elem = ET.Element('bib')
        record_elem = ET.SubElement(bib_elem, 'record')

        # Add leader
        leader = root.find('leader')
        if leader is not None:
            new_leader = ET.SubElement(record_elem, 'leader')
            new_leader.text = leader.text

        # Add control fields
        for cf in root.findall('controlfield'):
            new_cf = ET.SubElement(record_elem, 'controlfield')
            new_cf.set('tag', cf.get('tag'))
            new_cf.text = cf.text

        # Add data fields, applying the requested change to the target tag only.
        replacement_written = False
        for df in root.findall('datafield'):
            df_tag = df.get('tag')

            if df_tag == field and mode != "append":
                if mode == "replace_first":
                    if not replacement_written:
                        # Replace the first occurrence in place.
                        self._add_datafield(record_elem, field, subfields, ind1, ind2)
                        replacement_written = True
                    else:
                        # Preserve every later occurrence of the repeatable tag
                        # (the #184 fix: the old code dropped these).
                        self._copy_datafield(record_elem, df)
                elif mode == "replace_all":
                    # Collapse all occurrences into one new field: emit the
                    # replacement once and drop the remaining occurrences.
                    if not replacement_written:
                        self._add_datafield(record_elem, field, subfields, ind1, ind2)
                        replacement_written = True
                continue

            # Copy every other field (and, in append mode, the target tag too).
            self._copy_datafield(record_elem, df)

        # Field absent for replace_* modes -> create it; append always adds one.
        if mode == "append" or not replacement_written:
            self._add_datafield(record_elem, field, subfields, ind1, ind2)

        # Convert to string with proper formatting
        xml_str = ET.tostring(bib_elem, encoding='unicode')
        return xml_str

    def _copy_datafield(self, parent: ET.Element, df: ET.Element) -> None:
        """Copy an existing datafield (tag, indicators, subfields) verbatim."""
        new_df = ET.SubElement(parent, 'datafield')
        new_df.set('tag', df.get('tag'))
        new_df.set('ind1', df.get('ind1', ' '))
        new_df.set('ind2', df.get('ind2', ' '))

        for sf in df.findall('subfield'):
            new_sf = ET.SubElement(new_df, 'subfield')
            new_sf.set('code', sf.get('code'))
            new_sf.text = sf.text or ''

    def _normalize_subfields(self, subfields: SubfieldsArg) -> List[Tuple[str, str]]:
        """Normalise ``subfields`` into an ordered list of ``(code, value)`` pairs.

        This is the single validation/normalisation point for the
        MARC-editing path (issue #185). It accepts either shape described by
        :data:`SubfieldsArg` and always returns ordered ``(code, value)``
        tuples, so a subfield code may legitimately repeat — impossible when
        the subfields were held in a ``dict``.

        Args:
            subfields: Either a ``dict`` of ``{code: value}`` or an ordered
                sequence of ``[code, value]`` pairs.

        Returns:
            An ordered list of ``(code, value)`` tuples (values coerced to
            ``str``), preserving input order and any repeated codes.

        Raises:
            AlmaValidationError: If ``subfields`` is ``None``/empty, is a
                bare string, contains an entry that is not a 2-item
                ``[code, value]`` pair, or a code that is not a single
                character.
        """
        if subfields is None:
            raise AlmaValidationError("subfields is required")

        # A bare string is technically a Sequence but never a valid container.
        if isinstance(subfields, str):
            raise AlmaValidationError(
                "subfields must be a dict or a list of [code, value] pairs, "
                "not a bare string"
            )

        if isinstance(subfields, dict):
            raw_pairs: List[Sequence[str]] = list(subfields.items())
        elif isinstance(subfields, Sequence):
            raw_pairs = list(subfields)
        else:
            raise AlmaValidationError(
                "subfields must be a dict or a list of [code, value] pairs"
            )

        if not raw_pairs:
            raise AlmaValidationError(
                "subfields must contain at least one [code, value] pair"
            )

        normalized: List[Tuple[str, str]] = []
        for entry in raw_pairs:
            if isinstance(entry, str) or not isinstance(entry, Sequence):
                raise AlmaValidationError(
                    f"Each subfield must be a [code, value] pair; got {entry!r}"
                )
            if len(entry) != 2:
                raise AlmaValidationError(
                    "Each subfield pair must have exactly 2 items "
                    f"[code, value]; got {entry!r}"
                )
            code, value = entry[0], entry[1]
            if not isinstance(code, str) or len(code) != 1:
                raise AlmaValidationError(
                    f"Subfield code must be a single character; got {code!r}"
                )
            normalized.append((code, "" if value is None else str(value)))

        return normalized

    def _add_datafield(self, parent: ET.Element, tag: str,
                       subfields: List[Tuple[str, str]],
                       ind1: str, ind2: str) -> None:
        """Add a datafield element with its subfields.

        Iterates an ordered list of ``(code, value)`` pairs (as produced by
        :meth:`_normalize_subfields`) rather than a ``dict``, so a subfield
        code may repeat — e.g. ``650 ... $x History $x 20th century``
        (issue #185).

        Args:
            parent: The ``<record>`` element to append the datafield to.
            tag: 3-digit MARC tag for the new datafield.
            subfields: Ordered ``(code, value)`` pairs for the datafield.
            ind1: First indicator.
            ind2: Second indicator.
        """
        df = ET.SubElement(parent, 'datafield')
        df.set('tag', tag)
        df.set('ind1', ind1)
        df.set('ind2', ind2)

        for code, value in subfields:
            sf = ET.SubElement(df, 'subfield')
            sf.set('code', code)
            # Strip-only via the module-level helper (issue #186): ElementTree
            # escapes ``.text`` exactly once at serialisation, so pre-escaping
            # here would double-escape ``&`` into ``&amp;amp;``. Same helper the
            # creation builder ``build_alma_bib_xml`` uses (issue #179).
            sf.text = _strip_illegal_xml_chars(value)

    # Holdings-related methods
    def get_holdings(self, mms_id: str, holding_id: str = None) -> AlmaResponse:
        """
        Get holdings for a bibliographic record.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            holding_id: Specific holding ID, or None for all holdings
        
        Returns:
            AlmaResponse containing holdings data
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        if holding_id:
            endpoint = f"almaws/v1/bibs/{mms_id}/holdings/{holding_id}"
        else:
            endpoint = f"almaws/v1/bibs/{mms_id}/holdings"
        
        response = self.client.get(endpoint)
        self.logger.info(f"Retrieved holdings for bib {mms_id}")
        return response
    
    def create_holding(self, mms_id: str, holding_data: Dict[str, Any]) -> AlmaResponse:
        """
        Create a new holding record.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            holding_data: Holding record data
        
        Returns:
            AlmaResponse containing the created holding
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        endpoint = f"almaws/v1/bibs/{mms_id}/holdings"
        response = self.client.post(endpoint, data=holding_data)
        
        self.logger.info(f"Created holding for bib {mms_id}")
        return response
    
    # Items-related methods
    def get_items(self, mms_id: str, holding_id: str = "ALL", item_id: str = None) -> AlmaResponse:
        """
        Get items for a bibliographic record.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            holding_id: Holding ID or "ALL" for all holdings
            item_id: Specific item ID, or None for all items
        
        Returns:
            AlmaResponse containing items data
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        if item_id:
            endpoint = f"almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_id}"
        else:
            endpoint = f"almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items"
        
        response = self.client.get(endpoint)
        self.logger.info(f"Retrieved items for bib {mms_id}")
        return response
    
    def create_item(self, mms_id: str, holding_id: str, item_data: Dict[str, Any]) -> AlmaResponse:
        """
        Create a new item record.

        Args:
            mms_id: The MMS ID of the bibliographic record
            holding_id: The holding ID
            item_data: Item record data

        Returns:
            AlmaResponse containing the created item
        """
        if not mms_id or not holding_id:
            raise AlmaValidationError("MMS ID and holding ID are required")

        endpoint = f"almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items"
        response = self.client.post(endpoint, data=item_data)

        self.logger.info(f"Created item for bib {mms_id}, holding {holding_id}")
        return response

    def scan_in_item(self, mms_id: str, holding_id: str, item_pid: str,
                     library: str, department: Optional[str] = None,
                     circ_desk: Optional[str] = None,
                     work_order_type: Optional[str] = None,
                     status: Optional[str] = None,
                     done: bool = False,
                     confirm: bool = True) -> AlmaResponse:
        """
        Scan in an item to a department with optional work order.

        This operation simulates the UI "Scan In Items" function, which allows placing
        items in a work order within a department. When used after receiving an item,
        it prevents the item from going into Transit status and keeps it in the
        specified department.

        Args:
            mms_id: The MMS ID of the bibliographic record
            holding_id: The holding ID
            item_pid: The item PID (item identifier)
            library: Library code where item should be scanned in
            department: Department code (provide either department or circ_desk)
            circ_desk: Circulation desk code (alternative to department)
            work_order_type: Work order type code (e.g., 'AcqWorkOrder')
            status: Work order status (e.g., 'CopyCataloging', 'Labeling')
            done: If True, completes the work order; if False, keeps item in department
            confirm: Whether to bypass confirmation prompts (default: True)

        Returns:
            AlmaResponse containing the updated item data

        Raises:
            AlmaValidationError: If required parameters are missing or invalid

        Example:
            >>> # Scan in item to acquisitions department with work order
            >>> bibs.scan_in_item(
            ...     mms_id="99123456789",
            ...     holding_id="22123456789",
            ...     item_pid="23123456789",
            ...     library="ACQ_LIB",
            ...     department="ACQ_DEPT",
            ...     work_order_type="AcqWorkOrder",
            ...     status="CopyCataloging",
            ...     done=False  # Keep in department
            ... )

        Notes:
            - Either department or circ_desk must be provided
            - When done=False, item stays in department with work order
            - When done=True, work order is completed and item may move to next step
            - Work order configuration must exist in Alma (Configuration > Fulfillment >
              Physical Fulfillment > Work Order Types)
        """
        if not all([mms_id, holding_id, item_pid, library]):
            raise AlmaValidationError(
                "MMS ID, holding ID, item PID, and library are required"
            )

        if not department and not circ_desk:
            raise AlmaValidationError(
                "Either department or circ_desk must be provided"
            )

        # Build query parameters
        params = {
            "op": "scan",
            "library": library,
            "confirm": str(confirm).lower()
        }

        if department:
            params["department"] = department
        elif circ_desk:
            params["circ_desk"] = circ_desk

        if work_order_type:
            params["work_order_type"] = work_order_type

        if status:
            params["status"] = status

        if done:
            params["done"] = str(done).lower()

        endpoint = f"almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}"

        self.logger.info(
            f"Scanning in item {item_pid} to {department or circ_desk} "
            f"at library {library}"
            + (f" with work order {work_order_type}" if work_order_type else "")
        )

        response = self.client.post(endpoint, data={}, params=params)

        if response.success:
            self.logger.info(
                f"Successfully scanned in item {item_pid} to department"
            )

        return response

    # Digital representations methods (enhanced from your existing code)
    def get_representations(self, mms_id: str, representation_id: str = None) -> AlmaResponse:
        """
        Get digital representations for a bibliographic record.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            representation_id: Specific representation ID, or None for all
        
        Returns:
            AlmaResponse containing representation data
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        if representation_id:
            endpoint = f"almaws/v1/bibs/{mms_id}/representations/{representation_id}"
        else:
            endpoint = f"almaws/v1/bibs/{mms_id}/representations"
        
        response = self.client.get(endpoint)
        self.logger.info(f"Retrieved representations for bib {mms_id}")
        return response
    
    def create_representation(self, mms_id: str, access_rights_value: str, 
                            access_rights_desc: str, lib_code: str, 
                            usage_type: str = "PRESERVATION_MASTER") -> AlmaResponse:
        """
        Create a new digital representation.
        Enhanced version of your existing method.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            access_rights_value: Access rights policy value
            access_rights_desc: Access rights description
            lib_code: Library code
            usage_type: Usage type for the representation
        
        Returns:
            AlmaResponse containing the created representation
        """

        # Check for None/null values but allow empty strings
        if mms_id is None or access_rights_value is None or lib_code is None:
            raise AlmaValidationError("MMS ID, access rights value, and library code cannot be None")

        # Check for empty strings only for critical fields (not access_rights)
        if not mms_id or not lib_code:
            raise AlmaValidationError("MMS ID and library code are required and cannot be empty")

        # access_rights_value and access_rights_desc can be empty strings (but not None)
        if not isinstance(access_rights_value, str) or not isinstance(lib_code, str) or not isinstance(mms_id, str):
            raise AlmaValidationError("MMS ID, access rights value, and library code must be strings")

        
        rep_data = {
            "access_rights_policy_id": {
                "value": access_rights_value,
                "desc": access_rights_desc
            },
            "is_remote": False,
            "library": {"value": lib_code},
            "usage_type": {"value": usage_type}
        }
        
        endpoint = f"almaws/v1/bibs/{mms_id}/representations"
        response = self.client.post(endpoint, data=rep_data)
        
        self.logger.info(f"Created representation for bib {mms_id}")
        return response
    
    def get_representation_files(self, mms_id: str, representation_id: str, 
                               file_id: str = None) -> AlmaResponse:
        """
        Get files for a digital representation.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            representation_id: The representation ID
            file_id: Specific file ID, or None for all files
        
        Returns:
            AlmaResponse containing file data
        """
        if not all([mms_id, representation_id]):
            raise AlmaValidationError("MMS ID and representation ID are required")
        
        if file_id:
            endpoint = f"almaws/v1/bibs/{mms_id}/representations/{representation_id}/files/{file_id}"
        else:
            endpoint = f"almaws/v1/bibs/{mms_id}/representations/{representation_id}/files"
        
        response = self.client.get(endpoint)
        self.logger.info(f"Retrieved files for representation {representation_id}")
        return response
    
    def link_file_to_representation(self, mms_id: str, representation_id: str, 
                                   file_path: str) -> AlmaResponse:
        """
        Link a file to a digital representation.
        Enhanced version of your existing method.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            representation_id: The representation ID
            file_path: Path to the file in storage
        
        Returns:
            AlmaResponse containing the linked file data
        """
        if not all([mms_id, representation_id, file_path]):
            raise AlmaValidationError("MMS ID, representation ID, and file path are required")
        
        file_data = {"path": file_path}
        
        endpoint = f"almaws/v1/bibs/{mms_id}/representations/{representation_id}/files"
        response = self.client.post(endpoint, data=file_data)
        
        self.logger.info(f"Linked file {file_path} to representation {representation_id}")
        return response
    
    def update_representation_file(self, mms_id: str, representation_id: str, 
                                 file_id: str, file_data: Dict[str, Any]) -> AlmaResponse:
        """
        Update a file in a digital representation.
        Enhanced version of your existing method.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            representation_id: The representation ID
            file_id: The file ID
            file_data: Updated file data
        
        Returns:
            AlmaResponse containing the updated file data
        """
        if not all([mms_id, representation_id, file_id]):
            raise AlmaValidationError("MMS ID, representation ID, and file ID are required")
        
        endpoint = f"almaws/v1/bibs/{mms_id}/representations/{representation_id}/files/{file_id}"
        response = self.client.put(endpoint, data=file_data)
        
        self.logger.info(f"Updated file {file_id} in representation {representation_id}")
        return response
    

    # Collection methods
    def get_collection_members(self, collection_id: str, limit: int = 100,
                               offset: int = 0) -> AlmaResponse:
        """
        Get bibliographic records that are members of a collection.

        Args:
            collection_id: The collection ID
            limit: Maximum number of records to return (default 100)
            offset: Starting position for pagination (default 0)

        Returns:
            AlmaResponse containing list of bib records in the collection

        Raises:
            AlmaValidationError: If collection_id is empty or None
            AlmaAPIError: If the API request fails (e.g., collection not found)
        """
        if not collection_id:
            raise AlmaValidationError("Collection ID is required")

        params = {
            "limit": str(limit),
            "offset": str(offset)
        }

        endpoint = f"almaws/v1/bibs/collections/{collection_id}/bibs"
        response = self.client.get(endpoint, params=params)

        self.logger.info(f"Retrieved collection members for collection {collection_id}")
        return response

    def add_to_collection(self, collection_id: str, mms_id: str) -> AlmaResponse:
        """
        Add a bibliographic record to a collection.

        Args:
            collection_id: The collection ID
            mms_id: The MMS ID of the bibliographic record to add

        Returns:
            AlmaResponse containing the added bib record

        Raises:
            AlmaValidationError: If collection_id or mms_id is empty or None
            AlmaAPIError: If the API request fails (e.g., collection/bib not found)
        """
        if not collection_id:
            raise AlmaValidationError("Collection ID is required")
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")

        # The API expects a bib object with mms_id
        bib_data = {
            "mms_id": mms_id
        }

        endpoint = f"almaws/v1/bibs/collections/{collection_id}/bibs"
        response = self.client.post(endpoint, data=bib_data)

        self.logger.info(f"Added bib {mms_id} to collection {collection_id}")
        return response

    def remove_from_collection(self, collection_id: str, mms_id: str) -> AlmaResponse:
        """
        Remove a bibliographic record from a collection.

        Args:
            collection_id: The collection ID
            mms_id: The MMS ID of the bibliographic record to remove

        Returns:
            AlmaResponse confirming removal

        Raises:
            AlmaValidationError: If collection_id or mms_id is empty or None
            AlmaAPIError: If the API request fails (e.g., collection/bib not found)
        """
        if not collection_id:
            raise AlmaValidationError("Collection ID is required")
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")

        endpoint = f"almaws/v1/bibs/collections/{collection_id}/bibs/{mms_id}"
        response = self.client.delete(endpoint)

        self.logger.info(f"Removed bib {mms_id} from collection {collection_id}")
        return response

    def get_marc_subfield(self, mms_id: str, field: str, subfield: str,
                          strict: bool = False) -> List[str]:
        """
        Get specific MARC subfield values from a bibliographic record.

        Args:
            mms_id: The MMS ID of the record
            field: MARC data-field tag (e.g., "907"). Data fields (010-999)
                only — control fields (00X) have no subfields.
            subfield: Subfield code (e.g., "e")
            strict: When ``True``, a failed record fetch or unparseable MARC
                **raises** instead of returning ``[]``. This lets a caller tell
                "the field/subfield is genuinely absent" (always ``[]``) from
                "the fetch/parse failed" (raises). Default ``False`` keeps the
                batch-friendly behaviour of swallowing errors and returning
                ``[]`` so a bulk job continues (issue #190).

        Returns:
            List of subfield values; an **empty list** means the field/subfield
            is genuinely absent from the record.

        Raises:
            AlmaValidationError: for a missing ``mms_id``, a tag that is not a
                3-digit number, a control-field (00X) tag, or a ``subfield``
                that is not a single character.
            AlmaAPIError / Exception: on fetch/parse failure **only when**
                ``strict`` is ``True``.
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")

        if not field or not field.isdigit() or len(field) != 3:
            raise AlmaValidationError("Field must be a 3-digit number")

        # #190: control fields (00X) are <controlfield> elements with no
        # subfields, so a subfield lookup could only ever return []. Reject the
        # nonsensical request with a clear message instead of silently yielding
        # an empty list that reads like "absent".
        if field.startswith("00"):
            raise AlmaValidationError(
                f"get_marc_subfield reads data fields (010-999); {field} is a "
                "control field (00X) with no subfields — read it via get_record"
            )

        if not subfield or len(subfield) != 1:
            raise AlmaValidationError("Subfield must be a single character")

        try:
            # Structured kwargs (never f-string interpolation) so the redactor
            # sees each value (issue #154 pattern).
            self.logger.info(
                "Getting MARC subfield",
                mms_id=mms_id, field=field, subfield=subfield,
            )

            response = self.get_record(mms_id)
            if not response.success:
                raise AlmaAPIError(f"Failed to retrieve record {mms_id}")

            bib_data = response.json()
            marc_xml = bib_data.get('anies', [''])[0]

            if not marc_xml:
                self.logger.warning("No MARC XML found in record", mms_id=mms_id)
                return []

            # Parse MARC XML and extract subfield values
            values = self._extract_marc_subfield_values(marc_xml, field, subfield)

            self.logger.info(
                "Found MARC subfield values",
                mms_id=mms_id, field=field, subfield=subfield, count=len(values),
            )
            return values

        except Exception as e:
            # #190: surface the failure in strict mode so callers can tell it
            # apart from a genuine "absent"; otherwise swallow and return [] so
            # batch processing continues. Structured kwargs keep the redactor
            # in the loop.
            self.logger.error(
                "Error getting MARC subfield",
                mms_id=mms_id, field=field, subfield=subfield, error=str(e),
            )
            if strict:
                raise
            return []