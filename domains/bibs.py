import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Union
from base_client import BaseAPIClient, AlmaResponse, AlmaAPIError, AlmaValidationError


class BibliographicRecords:
    """
    Domain class for handling Alma Bibliographic Records API operations.
    Builds upon and improves the existing bib record functionality.
    """
    
    def __init__(self, client: BaseAPIClient):
        self.client = client
        self.logger = client.logger
    
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
    
    def search_records(self, q: str, limit: int = 10, offset: int = 0, 
                      order_by: str = None, direction: str = "asc") -> AlmaResponse:
        """
        Search bibliographic records.
        
        Args:
            q: Search query (e.g., "title~Harry Potter")
            limit: Number of results to return (max 100)
            offset: Starting point for results
            order_by: Field to sort by
            direction: Sort direction (asc, desc)
        
        Returns:
            AlmaResponse containing search results
        """
        if not q:
            raise AlmaValidationError("Search query is required")
        
        if limit > 100:
            raise AlmaValidationError("Limit cannot exceed 100")
        
        params = {
            "q": q,
            "limit": str(limit),
            "offset": str(offset),
            "order_by": order_by or "mms_id",
            "direction": direction
        }
        
        endpoint = "almaws/v1/bibs"
        response = self.client.get(endpoint, params=params)
        
        self.logger.info(f"Searched bibs with query: {q}, found {limit} results")
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
                                  content_type='xml', params=params)
        
        self.logger.info("Created new bib record")
        return response
    
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
                                 content_type='xml', params=params)
        
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
        if not all([mms_id, access_rights_value, lib_code]):
            raise AlmaValidationError("MMS ID, access rights value, and library code are required")
        
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