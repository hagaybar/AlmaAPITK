# BibliographicRecords Domain Class

## Overview

The `BibliographicRecords` domain class provides comprehensive operations for managing Alma bibliographic records, holdings, items, and digital representations through the Alma Bibs API.

### What This Domain Handles

- **Bibliographic Records**: MARC-format catalog records with metadata
- **Holdings**: Physical and electronic collection information linked to bib records
- **Items**: Individual physical pieces within holdings (books, journals, media)
- **Digital Representations**: Digital files (PDFs, images) associated with catalog records
- **MARC Field Operations**: Extract and update specific MARC fields and subfields

### When to Use It

- Retrieving catalog records and their associated data
- Creating or updating bibliographic records
- Managing physical items (receiving, scanning, location updates)
- Uploading and managing digital content
- Extracting metadata from MARC fields
- Integrating with Acquisitions workflows (scan-in after receiving)

### Key Concepts

| Term | Description |
|------|-------------|
| **MMS ID** | Bibliographic record identifier (typically 18 digits including institution code) |
| **Holding ID** | Identifier for a holdings record linked to a bib record |
| **Item PID** | Persistent identifier for a physical item |
| **Representation ID** | Identifier for a digital representation container |
| **MARC XML** | Standard format for bibliographic data in Alma |

### Data Hierarchy

```
Bibliographic Record (MMS ID)
  |
  +-- Holdings (Holding ID)
  |     |
  |     +-- Items (Item PID)
  |           - Barcode
  |           - Location
  |           - Status
  |
  +-- Representations (Representation ID)
        |
        +-- Files (File ID)
              - S3 path
              - MIME type
              - Size
```

---

## Initialization

### Basic Setup

```python
from almaapitk import AlmaAPIClient, BibliographicRecords

# Initialize client
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'

# Create domain instance
bibs = BibliographicRecords(client)
```

### Environment Variables Required

```bash
# For SANDBOX
export ALMA_SB_API_KEY="your_sandbox_api_key"

# For PRODUCTION
export ALMA_PROD_API_KEY="your_production_api_key"
```

---

## Methods Reference

### Bibliographic Record Operations

#### `get_record(mms_id, view, expand)`

Retrieve a bibliographic record by MMS ID.

**Signature:**
```python
def get_record(self, mms_id: str, view: str = "full", expand: str = None) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | The MMS ID of the bibliographic record |
| `view` | str | No | "full" | Level of detail ("brief" or "full") |
| `expand` | str | No | None | Additional data to include ("p_avail", "e_avail", "d_avail") |

**Returns:** `AlmaResponse` containing the bibliographic record

**Example:**
```python
# Get full record
response = bibs.get_record("991234567890123456")

if response.success:
    record = response.json()
    print(f"Title: {record.get('title')}")
    print(f"Author: {record.get('author')}")

# Get record with availability info
response = bibs.get_record(
    "991234567890123456",
    view="full",
    expand="p_avail,e_avail"
)
```

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 401861 | Invalid MMS ID | Verify MMS ID exists in Alma |
| 401652 | Record not found | Check MMS ID format and institution code |

---

#### `search_records(q, limit, offset, order_by, direction)`

Search bibliographic records using Alma query syntax.

**Signature:**
```python
def search_records(self, q: str, limit: int = 10, offset: int = 0,
                   order_by: str = None, direction: str = "asc") -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | str | Yes | - | Search query (e.g., "title~Harry Potter") |
| `limit` | int | No | 10 | Number of results (max 100) |
| `offset` | int | No | 0 | Starting point for pagination |
| `order_by` | str | No | "mms_id" | Field to sort by |
| `direction` | str | No | "asc" | Sort direction ("asc" or "desc") |

**Returns:** `AlmaResponse` containing search results

**Example:**
```python
# Search by title
response = bibs.search_records("title~Python Programming", limit=20)

if response.success:
    results = response.json()
    for bib in results.get('bib', []):
        print(f"{bib['mms_id']}: {bib['title']}")

# Search with pagination
response = bibs.search_records(
    "author~Smith",
    limit=50,
    offset=100,
    order_by="title",
    direction="asc"
)
```

**Query Syntax Examples:**
- `title~keyword` - Title contains keyword
- `author~name` - Author contains name
- `isbn~1234567890` - ISBN match
- `mms_id~99123` - MMS ID partial match

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 40166411 | Invalid query syntax | Check query format (use `~` for contains) |
| 400 | Limit exceeds 100 | Reduce limit parameter |

---

#### `create_record(marc_xml, validate, override_warning)`

Create a new bibliographic record from MARC XML.

**Signature:**
```python
def create_record(self, marc_xml: str, validate: bool = True,
                  override_warning: bool = False) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `marc_xml` | str | Yes | - | MARC XML data for the record |
| `validate` | bool | No | True | Whether to validate the record |
| `override_warning` | bool | No | False | Override validation warnings |

**Returns:** `AlmaResponse` containing the created record

**Example:**
```python
marc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<bib>
  <record>
    <leader>00000nam a2200000 a 4500</leader>
    <controlfield tag="008">240101s2024    xx            000 0 eng d</controlfield>
    <datafield tag="245" ind1="1" ind2="0">
      <subfield code="a">New Book Title</subfield>
    </datafield>
    <datafield tag="100" ind1="1" ind2=" ">
      <subfield code="a">Author Name</subfield>
    </datafield>
  </record>
</bib>"""

response = bibs.create_record(marc_xml, validate=True)

if response.success:
    new_record = response.json()
    print(f"Created record: {new_record['mms_id']}")
```

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 400 | Invalid XML structure | Validate XML before submitting |
| 401653 | Missing mandatory MARC fields | Include required fields (Leader, 008) |

---

#### `update_record(mms_id, marc_xml, validate, override_warning, override_lock, stale_version_check)`

Update an existing bibliographic record.

**Signature:**
```python
def update_record(self, mms_id: str, marc_xml: str, validate: bool = True,
                  override_warning: bool = True, override_lock: bool = True,
                  stale_version_check: bool = False) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of record to update |
| `marc_xml` | str | Yes | - | Updated MARC XML data |
| `validate` | bool | No | True | Validate the record |
| `override_warning` | bool | No | True | Override validation warnings |
| `override_lock` | bool | No | True | Override record locks |
| `stale_version_check` | bool | No | False | Check for stale versions |

**Returns:** `AlmaResponse` containing the updated record

**Example:**
```python
# Get current record
response = bibs.get_record("991234567890123456")
record = response.json()

# Modify MARC XML
marc_xml = record.get('anies', [''])[0]
# ... modify marc_xml ...

# Update
response = bibs.update_record(
    mms_id="991234567890123456",
    marc_xml=updated_marc_xml,
    override_lock=True
)
```

---

#### `delete_record(mms_id, override_attached_items)`

Delete a bibliographic record.

**Signature:**
```python
def delete_record(self, mms_id: str, override_attached_items: bool = False) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of record to delete |
| `override_attached_items` | bool | No | False | Delete even if items attached |

**Returns:** `AlmaResponse` confirming deletion

**Example:**
```python
# Delete record (fails if items attached)
response = bibs.delete_record("991234567890123456")

# Force delete with attached items
response = bibs.delete_record(
    "991234567890123456",
    override_attached_items=True
)
```

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 401867 | Items attached to record | Use `override_attached_items=True` or remove items first |

---

#### `update_marc_field(mms_id, field, subfields, ind1, ind2)`

Update or create a specific MARC field in a bibliographic record.

**Signature:**
```python
def update_marc_field(self, mms_id: str, field: str, subfields: Dict[str, str],
                      ind1: str = ' ', ind2: str = ' ') -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the record |
| `field` | str | Yes | - | MARC field number (3 digits, e.g., "594") |
| `subfields` | dict | Yes | - | Dictionary of subfield codes and values |
| `ind1` | str | No | ' ' | First indicator |
| `ind2` | str | No | ' ' | Second indicator |

**Returns:** `AlmaResponse` containing the updated record

**Example:**
```python
# Add/update local note field 590
response = bibs.update_marc_field(
    mms_id="991234567890123456",
    field="590",
    subfields={
        "a": "Local processing note",
        "b": "Additional info"
    },
    ind1=" ",
    ind2=" "
)

# Add subject heading field 650
response = bibs.update_marc_field(
    mms_id="991234567890123456",
    field="650",
    subfields={
        "a": "Library science",
        "x": "Data processing"
    },
    ind1=" ",
    ind2="0"
)
```

---

#### `get_marc_subfield(mms_id, field, subfield)`

Extract specific MARC subfield values from a bibliographic record.

**Signature:**
```python
def get_marc_subfield(self, mms_id: str, field: str, subfield: str) -> List[str]
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the record |
| `field` | str | Yes | - | MARC field number (3 digits) |
| `subfield` | str | Yes | - | Single character subfield code |

**Returns:** List of subfield values (empty list if not found)

**Example:**
```python
# Get all ISBN values (020$a)
isbns = bibs.get_marc_subfield("991234567890123456", "020", "a")
print(f"ISBNs found: {isbns}")

# Get local field value (907$e for file paths)
paths = bibs.get_marc_subfield("991234567890123456", "907", "e")
if paths:
    print(f"File path: {paths[0]}")

# Get all subject headings (650$a)
subjects = bibs.get_marc_subfield("991234567890123456", "650", "a")
for subject in subjects:
    print(f"Subject: {subject}")
```

---

### Holdings Operations

#### `get_holdings(mms_id, holding_id)`

Get holdings for a bibliographic record.

**Signature:**
```python
def get_holdings(self, mms_id: str, holding_id: str = None) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `holding_id` | str | No | None | Specific holding ID, or None for all |

**Returns:** `AlmaResponse` containing holdings data

**Example:**
```python
# Get all holdings for a bib record
response = bibs.get_holdings("991234567890123456")

if response.success:
    holdings = response.json()
    for holding in holdings.get('holding', []):
        print(f"Holding {holding['holding_id']}")
        print(f"  Library: {holding['library']['desc']}")
        print(f"  Location: {holding['location']['desc']}")
        print(f"  Call Number: {holding.get('call_number', 'N/A')}")

# Get specific holding
response = bibs.get_holdings("991234567890123456", "221234567890004146")
```

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 401689 | Holding not found | Verify holding ID exists |

---

#### `create_holding(mms_id, holding_data)`

Create a new holding record.

**Signature:**
```python
def create_holding(self, mms_id: str, holding_data: Dict[str, Any]) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `holding_data` | dict | Yes | - | Holding record data |

**Returns:** `AlmaResponse` containing the created holding

**Example:**
```python
holding_data = {
    "library": {"value": "MAIN"},
    "location": {"value": "STACKS"},
    "call_number": "QA76.73.P98 S65 2024",
    "call_number_type": {"value": "0"}  # LC
}

response = bibs.create_holding("991234567890123456", holding_data)

if response.success:
    new_holding = response.json()
    print(f"Created holding: {new_holding['holding_id']}")
```

---

### Items Operations

#### `get_items(mms_id, holding_id, item_id)`

Get items for a bibliographic record.

**Signature:**
```python
def get_items(self, mms_id: str, holding_id: str = "ALL", item_id: str = None) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `holding_id` | str | No | "ALL" | Holding ID or "ALL" for all holdings |
| `item_id` | str | No | None | Specific item ID, or None for all |

**Returns:** `AlmaResponse` containing items data

**Example:**
```python
# Get all items across all holdings
response = bibs.get_items("991234567890123456")

if response.success:
    items = response.json()
    for item in items.get('item', []):
        item_data = item.get('item_data', {})
        print(f"Barcode: {item_data.get('barcode')}")
        print(f"Location: {item_data.get('location', {}).get('desc')}")
        print(f"Status: {item_data.get('base_status', {}).get('desc')}")

# Get items for specific holding
response = bibs.get_items(
    "991234567890123456",
    holding_id="221234567890004146"
)

# Get specific item
response = bibs.get_items(
    "991234567890123456",
    holding_id="221234567890004146",
    item_id="231234567890004146"
)
```

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 401694 | Item not found | Verify item PID exists |
| 401689 | Invalid holding ID | Use valid holding ID or "ALL" |

---

#### `create_item(mms_id, holding_id, item_data)`

Create a new item record.

**Signature:**
```python
def create_item(self, mms_id: str, holding_id: str, item_data: Dict[str, Any]) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `holding_id` | str | Yes | - | Holding ID |
| `item_data` | dict | Yes | - | Item record data |

**Returns:** `AlmaResponse` containing the created item

**Example:**
```python
item_data = {
    "barcode": "2239409-11",
    "item_data": {
        "physical_material_type": {"value": "BOOK"},
        "policy": {"value": "STANDARD"},
        "description": "Copy 1",
        "enumeration_a": "v.1",
        "chronology_i": "2024"
    }
}

response = bibs.create_item(
    mms_id="991234567890123456",
    holding_id="221234567890004146",
    item_data=item_data
)

if response.success:
    new_item = response.json()
    print(f"Created item: {new_item['item_data']['pid']}")
```

**Mandatory Fields for Item Creation:**
- `barcode` - Must be unique across institution
- `item_data.physical_material_type` - Material type code
- `item_data.policy` - Item policy code

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 401660 | Duplicate barcode | Use unique barcode |
| 401674 | Invalid library code | Verify library configuration |
| 401675 | Invalid location code | Verify location configuration |

---

#### `scan_in_item(mms_id, holding_id, item_pid, library, department, circ_desk, work_order_type, status, done, confirm)`

Scan in an item to a department with optional work order.

**Signature:**
```python
def scan_in_item(self, mms_id: str, holding_id: str, item_pid: str,
                 library: str, department: Optional[str] = None,
                 circ_desk: Optional[str] = None,
                 work_order_type: Optional[str] = None,
                 status: Optional[str] = None,
                 done: bool = False,
                 confirm: bool = True) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the record |
| `holding_id` | str | Yes | - | Holding ID |
| `item_pid` | str | Yes | - | Item persistent identifier |
| `library` | str | Yes | - | Library code |
| `department` | str | No* | None | Department code |
| `circ_desk` | str | No* | None | Circulation desk code |
| `work_order_type` | str | No | None | Work order type code |
| `status` | str | No | None | Work order status |
| `done` | bool | No | False | Complete work order immediately |
| `confirm` | bool | No | True | Bypass confirmation prompts |

*Either `department` or `circ_desk` must be provided.

**Returns:** `AlmaResponse` containing updated item data

**Example:**
```python
# Scan in item to acquisitions department with work order
response = bibs.scan_in_item(
    mms_id="991234567890123456",
    holding_id="221234567890004146",
    item_pid="231234567890004146",
    library="MAIN",
    department="ACQ",
    work_order_type="AcqWorkOrder",
    status="CopyCataloging",
    done=False  # Keep in department
)

if response.success:
    print("Item scanned in successfully")

# Scan to circulation desk
response = bibs.scan_in_item(
    mms_id="991234567890123456",
    holding_id="221234567890004146",
    item_pid="231234567890004146",
    library="MAIN",
    circ_desk="MAIN_CIRC"
)
```

**Common Work Order Types:**
- `AcqWorkOrder` - Acquisitions processing
- `CatalogingWorkOrder` - Cataloging
- `ConservationWorkOrder` - Conservation/repair

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 401694 | Item not found | Verify all IDs (mms_id, holding_id, item_pid) |
| 401674 | Invalid library | Check library code in configuration |

---

### Digital Representations Operations

#### `get_representations(mms_id, representation_id)`

Get digital representations for a bibliographic record.

**Signature:**
```python
def get_representations(self, mms_id: str, representation_id: str = None) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `representation_id` | str | No | None | Specific representation ID, or None for all |

**Returns:** `AlmaResponse` containing representation data

**Example:**
```python
# Get all representations
response = bibs.get_representations("991234567890123456")

if response.success:
    reps = response.json()
    for rep in reps.get('representation', []):
        print(f"Rep ID: {rep['id']}")
        print(f"  Usage Type: {rep['usage_type']['desc']}")
        print(f"  Library: {rep['library']['desc']}")

# Get specific representation
response = bibs.get_representations(
    "991234567890123456",
    representation_id="231234567890004146"
)
```

---

#### `create_representation(mms_id, access_rights_value, access_rights_desc, lib_code, usage_type)`

Create a new digital representation.

**Signature:**
```python
def create_representation(self, mms_id: str, access_rights_value: str,
                         access_rights_desc: str, lib_code: str,
                         usage_type: str = "PRESERVATION_MASTER") -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `access_rights_value` | str | Yes | - | Access rights policy value (empty for default) |
| `access_rights_desc` | str | Yes | - | Access rights description |
| `lib_code` | str | Yes | - | Library code (must match Alma configuration) |
| `usage_type` | str | No | "PRESERVATION_MASTER" | Usage type code |

**Returns:** `AlmaResponse` containing the created representation

**Usage Types:**
| Value | Description | Use Case |
|-------|-------------|----------|
| `PRESERVATION_MASTER` | Primary/original file | Master scans, preservation copies |
| `VIEW` | Derivative/access copy | Web-optimized versions |
| `THUMBNAIL` | Thumbnail image | Preview images |
| `AUXILIARY` | Supplementary content | Table of contents, indexes |

**Example:**
```python
# Create preservation master representation
response = bibs.create_representation(
    mms_id="991234567890123456",
    access_rights_value="",      # System default
    access_rights_desc="",
    lib_code="RARE_BOOKS",       # Must match Alma config exactly!
    usage_type="PRESERVATION_MASTER"
)

if response.success:
    rep = response.json()
    print(f"Created representation: {rep['id']}")

# Create web access version
response = bibs.create_representation(
    mms_id="991234567890123456",
    access_rights_value="200",   # Open Access policy
    access_rights_desc="Open Access",
    lib_code="RARE_BOOKS",
    usage_type="VIEW"
)
```

**Common Errors:**
| Error Code | Cause | Solution |
|------------|-------|----------|
| 400 | Invalid library code | Verify library code in Alma configuration (NOT MARC field values!) |
| 400 | Missing required field | Ensure mms_id and lib_code are provided |

**Important Note on Library Codes:**

The `lib_code` must be the exact Alma library configuration code, NOT values from MARC fields.

```python
# WRONG - Using MARC 914 field value
lib_code = "LGBTQ-NLI-2"  # This is a collection identifier

# CORRECT - Using Alma library code
lib_code = "LGBTQ"  # This is the actual library code
```

---

#### `get_representation_files(mms_id, representation_id, file_id)`

Get files for a digital representation.

**Signature:**
```python
def get_representation_files(self, mms_id: str, representation_id: str,
                            file_id: str = None) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `representation_id` | str | Yes | - | Representation ID |
| `file_id` | str | No | None | Specific file ID, or None for all |

**Returns:** `AlmaResponse` containing file data

**Example:**
```python
# Get all files in a representation
response = bibs.get_representation_files(
    "991234567890123456",
    "231234567890004146"
)

if response.success:
    files = response.json()
    for f in files.get('file', []):
        print(f"File: {f['label']}")
        print(f"  Path: {f['path']}")
        print(f"  Size: {f['size']} bytes")
        print(f"  MIME: {f['mime_type']}")
```

---

#### `link_file_to_representation(mms_id, representation_id, file_path)`

Link an uploaded file (from S3) to a digital representation.

**Signature:**
```python
def link_file_to_representation(self, mms_id: str, representation_id: str,
                                file_path: str) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `representation_id` | str | Yes | - | Representation ID |
| `file_path` | str | Yes | - | S3 path where file is stored |

**Returns:** `AlmaResponse` containing the linked file data

**Example:**
```python
# File must already be uploaded to S3
s3_path = "972TAU_INST/upload/991234567890123456/document.pdf"

response = bibs.link_file_to_representation(
    mms_id="991234567890123456",
    representation_id="231234567890004146",
    file_path=s3_path
)

if response.success:
    file_info = response.json()
    print(f"Linked file: {file_info['pid']}")
```

---

#### `update_representation_file(mms_id, representation_id, file_id, file_data)`

Update a file in a digital representation.

**Signature:**
```python
def update_representation_file(self, mms_id: str, representation_id: str,
                              file_id: str, file_data: Dict[str, Any]) -> AlmaResponse
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `mms_id` | str | Yes | - | MMS ID of the bibliographic record |
| `representation_id` | str | Yes | - | Representation ID |
| `file_id` | str | Yes | - | File ID |
| `file_data` | dict | Yes | - | Updated file data |

**Returns:** `AlmaResponse` containing the updated file data

**Example:**
```python
# Update file label
file_data = {
    "label": "Updated Document Name.pdf"
}

response = bibs.update_representation_file(
    mms_id="991234567890123456",
    representation_id="231234567890004146",
    file_id="DS12345678",
    file_data=file_data
)
```

---

## Common Workflows

### Workflow 1: Get Bib Record with Holdings and Items

Complete workflow to retrieve a bibliographic record with all associated data.

```python
from almaapitk import AlmaAPIClient, BibliographicRecords

# Initialize
client = AlmaAPIClient('SANDBOX')
bibs = BibliographicRecords(client)

mms_id = "991234567890123456"

# Step 1: Get bibliographic record
bib_response = bibs.get_record(mms_id, view="full")
if not bib_response.success:
    print(f"Failed to get bib record: {bib_response.status_code}")
    exit(1)

bib_data = bib_response.json()
print(f"Title: {bib_data.get('title')}")
print(f"Author: {bib_data.get('author')}")

# Step 2: Get all holdings
holdings_response = bibs.get_holdings(mms_id)
if holdings_response.success:
    holdings = holdings_response.json().get('holding', [])
    print(f"\nFound {len(holdings)} holdings:")

    for holding in holdings:
        holding_id = holding['holding_id']
        print(f"\n  Holding: {holding_id}")
        print(f"    Library: {holding['library']['desc']}")
        print(f"    Location: {holding['location']['desc']}")
        print(f"    Call Number: {holding.get('call_number', 'N/A')}")

        # Step 3: Get items for each holding
        items_response = bibs.get_items(mms_id, holding_id)
        if items_response.success:
            items = items_response.json().get('item', [])
            print(f"    Items: {len(items)}")

            for item in items:
                item_data = item.get('item_data', {})
                print(f"      - Barcode: {item_data.get('barcode')}")
                print(f"        PID: {item_data.get('pid')}")
                print(f"        Status: {item_data.get('base_status', {}).get('desc', 'Unknown')}")
```

---

### Workflow 2: Scan-In Item After Receiving

Use after receiving items via Acquisitions to keep them in a department for processing instead of going to "in transit" status.

```python
from almaapitk import AlmaAPIClient, BibliographicRecords, Acquisitions

# Initialize
client = AlmaAPIClient('SANDBOX')
bibs = BibliographicRecords(client)
acq = Acquisitions(client)

# Configuration
pol_id = "POL-12347"
library = "MAIN"
department = "ACQ"
work_order_type = "AcqWorkOrder"
work_order_status = "CopyCataloging"

# Step 1: Get POL data to find items
pol_response = acq.get_pol(pol_id)
pol_data = pol_response.json()

# Step 2: Extract items (nested in location[0].copy[])
items = pol_data.get('location', [{}])[0].get('copy', [])

# Step 3: Find unreceived items
unreceived_items = [item for item in items if not item.get('receive_date')]

for item in unreceived_items:
    item_id = item.get('pid')
    mms_id = pol_data.get('resource_metadata', {}).get('mms_id', {}).get('value')
    holding_id = pol_data.get('location', [{}])[0].get('holding_id')

    print(f"Processing item: {item_id}")

    # Step 4: Receive the item via Acquisitions
    receive_response = acq.receive_item(pol_id, item_id)
    if not receive_response.success:
        print(f"  Failed to receive item: {receive_response.status_code}")
        continue

    print("  Received item successfully")

    # Step 5: Scan in to keep in department (prevent "in transit")
    scan_response = bibs.scan_in_item(
        mms_id=mms_id,
        holding_id=holding_id,
        item_pid=item_id,
        library=library,
        department=department,
        work_order_type=work_order_type,
        status=work_order_status,
        done=False  # Keep in department, don't complete work order
    )

    if scan_response.success:
        print(f"  Scanned in to {department} with work order")
    else:
        print(f"  Scan-in failed: {scan_response.status_code}")
```

**Why This Workflow Matters:**
- After receiving, items automatically go to "in transit" status
- Scan-in with work order keeps items in the acquisitions department
- Allows cataloging/processing before shelving
- Matches the UI "Scan In Items" function

---

### Workflow 3: Digital Representations - Upload Files

Complete workflow for uploading digital files to Alma.

```python
import os
import boto3
from almaapitk import AlmaAPIClient, BibliographicRecords

# Initialize Alma client
client = AlmaAPIClient('SANDBOX')
bibs = BibliographicRecords(client)

# Initialize AWS S3
s3_resource = boto3.resource(
    service_name='s3',
    region_name='eu-central-1',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET')
)
bucket_name = os.getenv('ALMA_SB_BUCKET_NAME')
bucket = s3_resource.Bucket(bucket_name)

# Configuration
mms_id = "991234567890123456"
local_file = "/path/to/document.pdf"
library_code = "RARE_BOOKS"
institution_code = "972TAU_INST"

# Step 1: Check for existing representations
reps_response = bibs.get_representations(mms_id)
reps = reps_response.json()

if reps.get('representation'):
    # Use existing representation
    rep_id = reps['representation'][0]['id']
    print(f"Using existing representation: {rep_id}")
else:
    # Step 2: Create new representation
    rep_response = bibs.create_representation(
        mms_id=mms_id,
        access_rights_value="",      # System default
        access_rights_desc="",
        lib_code=library_code,
        usage_type="PRESERVATION_MASTER"
    )

    if not rep_response.success:
        print(f"Failed to create representation: {rep_response.status_code}")
        exit(1)

    rep_id = rep_response.json()['id']
    print(f"Created representation: {rep_id}")

# Step 3: Upload file to S3
filename = os.path.basename(local_file)
s3_key = f"{institution_code}/upload/{mms_id}/{filename}"

print(f"Uploading to S3: {s3_key}")
bucket.upload_file(local_file, s3_key)
print("Upload complete")

# Step 4: Link file to representation
link_response = bibs.link_file_to_representation(
    mms_id=mms_id,
    representation_id=rep_id,
    file_path=s3_key
)

if link_response.success:
    file_info = link_response.json()
    print(f"File linked successfully")
    print(f"  File ID: {file_info['pid']}")
    print(f"  Label: {file_info['label']}")
else:
    print(f"Failed to link file: {link_response.status_code}")
```

**AWS Environment Variables Required:**
```bash
export AWS_ACCESS_KEY="your_aws_access_key"
export AWS_SECRET="your_aws_secret_key"
export ALMA_SB_BUCKET_NAME="your_sandbox_bucket"
export ALMA_PROD_BUCKET_NAME="your_production_bucket"
```

---

## Best Practices and Gotchas

### MARC XML Handling

1. **Always validate XML before sending:**
   ```python
   import xml.etree.ElementTree as ET

   try:
       ET.fromstring(marc_xml)
   except ET.ParseError as e:
       print(f"Invalid XML: {e}")
   ```

2. **Sanitize text for XML:**
   - Remove control characters
   - Escape special characters (`&`, `<`, `>`, `"`, `'`)

3. **MARC field format:**
   - Field numbers must be exactly 3 digits (e.g., "590", not "59")
   - Subfield codes are single characters

### Library Code Validation

**Critical:** Library codes must match Alma configuration exactly.

```python
# WRONG - Values from MARC fields
lib_code = "LGBTQ-NLI-2"  # This is from MARC 914, NOT a valid library code

# CORRECT - Actual Alma library codes
lib_code = "LGBTQ"
lib_code = "MAIN"
lib_code = "RARE_BOOKS"
```

To find valid library codes:
- Via API: `GET /almaws/v1/conf/libraries`
- Via UI: Configuration > General > Libraries

### Item Hierarchy

Always provide all three identifiers for item operations:
- `mms_id` - Bibliographic record
- `holding_id` - Holdings record
- `item_pid` - Item identifier

### Scan-In After Receiving

When receiving items via Acquisitions, they automatically go to "in transit". Use `scan_in_item()` immediately after receiving to:
- Keep items in the acquisitions department
- Assign work orders
- Prevent premature transit

### Digital Upload Best Practices

1. **Check for existing representations** before creating new ones
2. **Upload to S3 first**, then link to Alma
3. **S3 path must match** between upload and link operations
4. **Use correct institution code** in S3 path structure

### Error Handling Pattern

```python
from almaapitk import AlmaAPIError, AlmaValidationError

try:
    response = bibs.get_record(mms_id)

    if response.success:
        data = response.json()
        # Process data
    else:
        print(f"API error: {response.status_code}")

except AlmaValidationError as e:
    print(f"Validation error: {e}")
except AlmaAPIError as e:
    print(f"API error: {e}")
    print(f"Status code: {e.status_code}")
```

---

## Alma API Reference

### Relevant Endpoints

| Operation | Endpoint | Method |
|-----------|----------|--------|
| Get bib record | `/almaws/v1/bibs/{mms_id}` | GET |
| Search bibs | `/almaws/v1/bibs` | GET |
| Create bib | `/almaws/v1/bibs` | POST |
| Update bib | `/almaws/v1/bibs/{mms_id}` | PUT |
| Delete bib | `/almaws/v1/bibs/{mms_id}` | DELETE |
| Get holdings | `/almaws/v1/bibs/{mms_id}/holdings` | GET |
| Create holding | `/almaws/v1/bibs/{mms_id}/holdings` | POST |
| Get items | `/almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items` | GET |
| Create item | `/almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items` | POST |
| Scan-in item | `/almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}?op=scan` | POST |
| Get representations | `/almaws/v1/bibs/{mms_id}/representations` | GET |
| Create representation | `/almaws/v1/bibs/{mms_id}/representations` | POST |
| Get files | `/almaws/v1/bibs/{mms_id}/representations/{rep_id}/files` | GET |
| Link file | `/almaws/v1/bibs/{mms_id}/representations/{rep_id}/files` | POST |

### Official Documentation

- [Alma Bibs API](https://developers.exlibrisgroup.com/alma/apis/bibs/)
- [Digital Representations](https://developers.exlibrisgroup.com/alma/apis/bibs/#representations)

### API Quirks

1. **MMS ID Format:** Typically 18 digits including institution code suffix
2. **MARC XML in responses:** Located in `anies` array of bib record
3. **Item process type:** Changes automatically after operations (e.g., "acquisition" to "in_transit" after receiving)
4. **Work order types:** Must be configured in Alma (Configuration > Fulfillment > Physical Fulfillment > Work Order Types)

---

## Related Documentation

- [Acquisitions Domain](./acquisitions.md) - For POL and invoice operations
- [Resource Sharing Guide](/docs/RESOURCE_SHARING_GUIDE.md) - For lending/borrowing workflows
- [API Reference](/docs/api-reference.md) - Complete API documentation
- [Getting Started](/docs/getting-started.md) - Initial setup guide
