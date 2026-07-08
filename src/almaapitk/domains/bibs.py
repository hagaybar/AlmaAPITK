import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from almaapitk.client.AlmaAPIClient import AlmaAPIClient, AlmaAPIError, AlmaResponse, AlmaValidationError


# Documented default MARC leader used by ``build_alma_bib_xml`` when a spec
# omits ``leader``. Callers own leader validity (issue #179); this is a
# reasonable "new textual monograph" default and can be overridden per-spec.
DEFAULT_LEADER = "     nam a22     3u 4500"


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
        AlmaValidationError: If ``value`` is not representable as a single
            character.
    """
    if value is None or value == "":
        return " "
    text = str(value)
    if len(text) != 1:
        raise AlmaValidationError(
            f"MARC indicator must be a single character, got {text!r}"
        )
    return text


def build_alma_bib_xml(spec: Dict[str, Any]) -> str:
    """Build Alma's non-namespaced ``<bib><record>`` MARCXML from a spec.

    Pure, network-free helper (the XML-assembly shape mirrors
    ``BibliographicRecords._build_updated_marc_xml`` but is spec-driven and
    escapes exactly once). The ``spec`` is plain JSON-serialisable data so it
    is usable from non-Python callers (e.g. Power Automate)::

        spec = {
            "leader": "     nam a22     3u 4500",   # optional; default if omitted
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

    Args:
        spec: Mapping with an optional ``leader`` string and a non-empty
            ``fields`` list. Each field needs a string ``tag``; control fields
            carry ``data`` (or have a ``00X`` tag), data fields carry ``ind1``
            / ``ind2`` (default blank) and a non-empty ``subfields`` list of
            ``[code, value]`` pairs. Field and subfield order is preserved and
            repeated tags/subfields are supported.

    Returns:
        A ``<bib><record>...</record></bib>`` XML string ready for
        :meth:`BibliographicRecords.create_record`.

    Raises:
        AlmaValidationError: If the spec is malformed (not a dict, missing or
            empty ``fields``, a field without a ``tag``, a control field
            without ``data``, or a data field without ``subfields``).
    """
    if not isinstance(spec, dict):
        raise AlmaValidationError("spec must be a dict")

    fields = spec.get("fields")
    if not isinstance(fields, list) or not fields:
        raise AlmaValidationError("spec must include a non-empty 'fields' list")

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

        # Control fields carry a 'data' string (or a 00X tag); everything else
        # is a data field with indicators + subfields.
        is_control = "data" in field or tag.startswith("00")
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

        subfields = field.get("subfields")
        if not subfields:
            raise AlmaValidationError(
                f"data field {tag} requires 'data' (control) or a non-empty "
                "'subfields' list"
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
        """
        
        try:
            root = ET.fromstring(marc_xml)
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
            
        except ET.ParseError as e:
            self.logger.error(f"Error parsing MARC XML: {e}")
            return []

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
                                  override_warning: bool = False) -> AlmaResponse:
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

        Returns:
            AlmaResponse containing the created record.

        Raises:
            AlmaValidationError: If ``spec`` is malformed.
        """
        marc_xml = build_alma_bib_xml(spec)

        self.logger.info("Creating bib record from field spec")
        return self.create_record(
            marc_xml, validate=validate, override_warning=override_warning
        )

    def create_record_from_pymarc(self, record: Any, validate: bool = True,
                                 override_warning: bool = False) -> AlmaResponse:
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
            spec, validate=validate, override_warning=override_warning
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
            override_attached_items: Whether to delete even if items are attached
        
        Returns:
            AlmaResponse confirming deletion
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        params = {}
        if override_attached_items:
            params["override"] = "attached_items"
        
        endpoint = f"almaws/v1/bibs/{mms_id}"
        response = self.client.delete(endpoint, params=params)
        
        self.logger.info(f"Deleted bib record {mms_id}")
        return response
    
    def update_marc_field(self, mms_id: str, field: str, subfields: Dict[str, str], 
                         ind1: str = ' ', ind2: str = ' ') -> AlmaResponse:
        """
        Update or create a MARC field in a bibliographic record.
        Enhanced version of your existing method with better error handling.
        
        Args:
            mms_id: The MMS ID of the record
            field: MARC field number (e.g., "594")
            subfields: Dictionary of subfield codes and values
            ind1: First indicator
            ind2: Second indicator
        
        Returns:
            AlmaResponse containing the updated record
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        if not field or not field.isdigit() or len(field) != 3:
            raise AlmaValidationError("Field must be a 3-digit number")
        
        if not subfields:
            raise AlmaValidationError("Subfields dictionary is required")
        
        try:
            # Get current record
            self.logger.info(f"Updating MARC field {field} for record {mms_id}")
            
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
            updated_xml = self._build_updated_marc_xml(root, field, subfields, ind1, ind2)
            
            # Update the record
            return self.update_record(mms_id, updated_xml)
            
        except Exception as e:
            self.logger.error(f"Error updating MARC field {field} for record {mms_id}: {e}")
            raise
    
    def _build_updated_marc_xml(self, root: ET.Element, field: str, 
                               subfields: Dict[str, str], ind1: str, ind2: str) -> str:
        """
        Build updated MARC XML with the new/modified field.
        Improved version with better XML formatting.
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
        
        # Add data fields, replacing the target field
        field_added = False
        for df in root.findall('datafield'):
            df_tag = df.get('tag')
            
            # Skip the field we're replacing
            if df_tag == field:
                if not field_added:
                    self._add_datafield(record_elem, field, subfields, ind1, ind2)
                    field_added = True
                continue
            
            # Copy other fields
            new_df = ET.SubElement(record_elem, 'datafield')
            new_df.set('tag', df_tag)
            new_df.set('ind1', df.get('ind1', ' '))
            new_df.set('ind2', df.get('ind2', ' '))
            
            for sf in df.findall('subfield'):
                new_sf = ET.SubElement(new_df, 'subfield')
                new_sf.set('code', sf.get('code'))
                new_sf.text = sf.text or ''
        
        # Add the field if it wasn't in the original record
        if not field_added:
            self._add_datafield(record_elem, field, subfields, ind1, ind2)
        
        # Convert to string with proper formatting
        xml_str = ET.tostring(bib_elem, encoding='unicode')
        return xml_str
    
    def _add_datafield(self, parent: ET.Element, tag: str, subfields: Dict[str, str], 
                      ind1: str, ind2: str) -> None:
        """Add a datafield element with subfields."""
        df = ET.SubElement(parent, 'datafield')
        df.set('tag', tag)
        df.set('ind1', ind1)
        df.set('ind2', ind2)
        
        for code, value in subfields.items():
            sf = ET.SubElement(df, 'subfield')
            sf.set('code', code)
            sf.text = self._sanitize_xml_text(value)
    
    def _sanitize_xml_text(self, text: str) -> str:
        """
        Sanitize text for XML inclusion.
        Improved version of your existing sanitization logic.
        """
        if not text:
            return ''
        
        # Remove control characters except tab, newline, carriage return
        sanitized = ''.join(char for char in text 
                          if ord(char) >= 32 or char in '\n\t\r')
        
        # Handle XML special characters
        sanitized = (sanitized
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&apos;'))
        
        return sanitized.strip()
    
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

    def get_marc_subfield(self, mms_id: str, field: str, subfield: str) -> List[str]:
        """
        Get specific MARC subfield values from a bibliographic record.
        
        Args:
            mms_id: The MMS ID of the record
            field: MARC field number (e.g., "907")  
            subfield: Subfield code (e.g., "e")
            
        Returns:
            List of subfield values (empty list if not found)
        """
        if not mms_id:
            raise AlmaValidationError("MMS ID is required")
        
        if not field or not field.isdigit() or len(field) != 3:
            raise AlmaValidationError("Field must be a 3-digit number")
        
        if not subfield or len(subfield) != 1:
            raise AlmaValidationError("Subfield must be a single character")
        
        try:
            # Get the bibliographic record
            self.logger.info(f"Getting MARC field {field} subfield {subfield} for record {mms_id}")
            
            response = self.get_record(mms_id)
            if not response.success:
                raise AlmaAPIError(f"Failed to retrieve record {mms_id}")
            
            bib_data = response.json()
            marc_xml = bib_data.get('anies', [''])[0]
            
            if not marc_xml:
                self.logger.warning(f"No MARC XML found in record {mms_id}")
                return []
            
            # Parse MARC XML and extract subfield values
            values = self._extract_marc_subfield_values(marc_xml, field, subfield)
            
            self.logger.info(f"Found {len(values)} values for {field}${subfield} in record {mms_id}")
            return values
            
        except Exception as e:
            self.logger.error(f"Error getting MARC field {field}${subfield} for record {mms_id}: {e}")
            # Return empty list instead of raising, so processing can continue
            return []