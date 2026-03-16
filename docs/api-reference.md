# AlmaAPITK API Reference

**Version:** 0.2.0
**Package:** `almaapitk`

This document provides comprehensive API reference documentation for the AlmaAPITK Python library.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [AlmaAPIClient](#almaapiclient)
- [AlmaResponse](#almaresponse)
- [Exceptions](#exceptions)
- [Domain Classes](#domain-classes)
  - [Acquisitions](#acquisitions)
  - [Users](#users)
  - [BibliographicRecords](#bibliographicrecords)
  - [Admin](#admin)
  - [ResourceSharing](#resourcesharing)
- [Utilities](#utilities)
  - [TSVGenerator](#tsvgenerator)
  - [Citation Metadata](#citation-metadata)

---

## Installation

```bash
# Install with poetry
poetry install

# Or with pip
pip install almaapitk
```

### Environment Setup

Set the required environment variables:

```bash
export ALMA_SB_API_KEY='your_sandbox_api_key'
export ALMA_PROD_API_KEY='your_production_api_key'
```

---

## Quick Start

```python
from almaapitk import AlmaAPIClient, Acquisitions, Users, Admin

# Initialize client
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'

# Test connection
if client.test_connection():
    print("Connected successfully!")

# Use domain classes
acq = Acquisitions(client)
users = Users(client)
admin = Admin(client)
```

---

## AlmaAPIClient

The main HTTP client for all Alma API interactions.

### Class Definition

```python
class AlmaAPIClient:
    """
    General abstract gateway to the Alma API.

    This class provides:
    - Environment management (SANDBOX/PRODUCTION)
    - Core HTTP methods (GET, POST, PUT, DELETE)
    - Authentication handling
    - Connection testing
    - Foundation for pluggable domain-specific classes
    """
```

### Constructor

```python
AlmaAPIClient(environment: str = 'SANDBOX')
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `environment` | `str` | `'SANDBOX'` | Environment to use. Must be `'SANDBOX'` or `'PRODUCTION'` |

**Raises:**
- `ValueError`: If environment is not 'SANDBOX' or 'PRODUCTION'
- `ValueError`: If the corresponding environment variable is not set

**Example:**

```python
from almaapitk import AlmaAPIClient

# Sandbox environment
client = AlmaAPIClient('SANDBOX')

# Production environment
client = AlmaAPIClient('PRODUCTION')
```

### Methods

#### get()

```python
def get(
    self,
    endpoint: str,
    params: Optional[Dict] = None,
    custom_headers: Optional[Dict] = None
) -> AlmaResponse
```

Make a GET request to the Alma API.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `endpoint` | `str` | API endpoint (e.g., `'almaws/v1/bibs/123456'`) |
| `params` | `Optional[Dict]` | Query parameters |
| `custom_headers` | `Optional[Dict]` | Additional headers to include |

**Returns:** `AlmaResponse` object

**Example:**

```python
# Get a bibliographic record
response = client.get('almaws/v1/bibs/991234567890123456')
data = response.json()

# With query parameters
response = client.get('almaws/v1/bibs', params={'limit': '10', 'offset': '0'})
```

#### post()

```python
def post(
    self,
    endpoint: str,
    data: Any = None,
    params: Optional[Dict] = None,
    content_type: Optional[str] = None,
    custom_headers: Optional[Dict] = None
) -> AlmaResponse
```

Make a POST request to the Alma API.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `endpoint` | `str` | API endpoint |
| `data` | `Any` | Request body (dict for JSON, str for XML) |
| `params` | `Optional[Dict]` | Query parameters |
| `content_type` | `Optional[str]` | Override content type (e.g., `'application/xml'`) |
| `custom_headers` | `Optional[Dict]` | Additional headers |

**Returns:** `AlmaResponse` object

**Example:**

```python
# Create a resource (JSON)
response = client.post('almaws/v1/acq/invoices', data={'number': 'INV-001', ...})

# Create a resource (XML)
response = client.post('almaws/v1/bibs', data=marc_xml, content_type='application/xml')
```

#### put()

```python
def put(
    self,
    endpoint: str,
    data: Any = None,
    params: Optional[Dict] = None,
    content_type: Optional[str] = None,
    custom_headers: Optional[Dict] = None
) -> AlmaResponse
```

Make a PUT request to the Alma API.

**Parameters:** Same as `post()`

**Returns:** `AlmaResponse` object

**Example:**

```python
# Update a user
response = client.put(f'almaws/v1/users/{user_id}', data=user_data)
```

#### delete()

```python
def delete(
    self,
    endpoint: str,
    params: Optional[Dict] = None,
    custom_headers: Optional[Dict] = None
) -> AlmaResponse
```

Make a DELETE request to the Alma API.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `endpoint` | `str` | API endpoint |
| `params` | `Optional[Dict]` | Query parameters |
| `custom_headers` | `Optional[Dict]` | Additional headers |

**Returns:** `AlmaResponse` object

#### test_connection()

```python
def test_connection(self) -> bool
```

Test if the API connection works.

**Returns:** `True` if connection successful, `False` otherwise

**Example:**

```python
if client.test_connection():
    print("Connected to Alma API")
else:
    print("Connection failed")
```

#### switch_environment()

```python
def switch_environment(self, new_environment: str) -> None
```

Switch between SANDBOX and PRODUCTION environments.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_environment` | `str` | `'SANDBOX'` or `'PRODUCTION'` |

**Example:**

```python
client = AlmaAPIClient('SANDBOX')
client.switch_environment('PRODUCTION')
```

#### get_environment()

```python
def get_environment(self) -> str
```

Get current environment.

**Returns:** Current environment string (`'SANDBOX'` or `'PRODUCTION'`)

#### get_base_url()

```python
def get_base_url(self) -> str
```

Get base URL.

**Returns:** Base URL string (e.g., `'https://api-eu.hosted.exlibrisgroup.com'`)

---

## AlmaResponse

Response wrapper that provides consistent response handling.

### Class Definition

```python
class AlmaResponse:
    """Response wrapper to maintain compatibility with existing domain classes."""
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `status_code` | `int` | HTTP status code |
| `success` | `bool` | `True` if status_code < 400 |
| `data` | `Dict[str, Any]` | Alias for `json()` - returns parsed JSON response |

### Methods

#### json()

```python
def json(self) -> Dict[str, Any]
```

Return JSON data from response.

**Returns:** Parsed JSON response as dictionary

**Example:**

```python
response = client.get('almaws/v1/bibs/991234567890123456')
data = response.json()
print(data['mms_id'])
```

#### text()

```python
def text(self) -> str
```

Return text data from response.

**Returns:** Raw response text

### Usage Example

```python
response = client.get('almaws/v1/bibs/991234567890123456')

# Check success
if response.success:
    # Access data via property
    bib_data = response.data

    # Or via method
    bib_data = response.json()

    print(f"Title: {bib_data.get('title')}")
else:
    print(f"Request failed with status: {response.status_code}")
```

---

## Exceptions

### AlmaAPIError

Base exception for Alma API errors.

```python
class AlmaAPIError(Exception):
    """General Alma API error."""

    def __init__(self, message: str, status_code: int = None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `status_code` | `int` | HTTP status code that caused the error |
| `response` | `Response` | The original response object |

**When Raised:**
- HTTP status code >= 400
- API returns an error in the response body
- Network or connection errors

**Example:**

```python
from almaapitk import AlmaAPIClient, AlmaAPIError

client = AlmaAPIClient('SANDBOX')

try:
    response = client.get('almaws/v1/bibs/invalid_mms_id')
except AlmaAPIError as e:
    print(f"API Error: {e}")
    print(f"Status Code: {e.status_code}")
```

### AlmaValidationError

Exception for validation failures.

```python
class AlmaValidationError(ValueError):
    """Validation error for Alma API requests."""
    pass
```

**When Raised:**
- Required parameters are missing
- Parameter values are invalid
- Data structure validation fails

**Example:**

```python
from almaapitk import AlmaAPIClient, AlmaValidationError, Users

client = AlmaAPIClient('SANDBOX')
users = Users(client)

try:
    users.get_user('')  # Empty user ID
except AlmaValidationError as e:
    print(f"Validation Error: {e}")
```

---

## Domain Classes

### Acquisitions

Handles invoice management and POL operations.

#### Constructor

```python
Acquisitions(client: AlmaAPIClient)
```

**Example:**

```python
from almaapitk import AlmaAPIClient, Acquisitions

client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)
```

#### Key Methods

##### create_invoice_simple()

```python
def create_invoice_simple(
    self,
    invoice_number: str,
    invoice_date: str,
    vendor_code: str,
    total_amount: float,
    currency: str = "ILS",
    **optional_fields
) -> Dict[str, Any]
```

Create an invoice with simplified parameters.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `invoice_number` | `str` | Required | Vendor invoice number |
| `invoice_date` | `str` | Required | Date in `'YYYY-MM-DD'` or `'YYYY-MM-DDZ'` format |
| `vendor_code` | `str` | Required | Vendor code from Alma |
| `total_amount` | `float` | Required | Total invoice amount |
| `currency` | `str` | `'ILS'` | Currency code |

**Optional Fields:**
- `invoice_due_date`: str or datetime
- `vendor_account`: str
- `reference_number`: str
- `payment_method`: str
- `notes`: List[str]
- `payment`: Dict (voucher info)
- `invoice_vat`: Dict (VAT details)
- `additional_charges`: Dict

**Returns:** Created invoice dictionary with `id` field

**Example:**

```python
invoice = acq.create_invoice_simple(
    invoice_number="INV-2025-001",
    invoice_date="2025-10-21",
    vendor_code="RIALTO",
    total_amount=100.00,
    currency="ILS"
)
print(f"Created invoice: {invoice['id']}")
```

##### create_invoice_line_simple()

```python
def create_invoice_line_simple(
    self,
    invoice_id: str,
    pol_id: str,
    amount: float,
    quantity: int = 1,
    fund_code: Optional[str] = None,
    currency: str = "ILS",
    **optional_fields
) -> Dict[str, Any]
```

Create an invoice line with simplified parameters.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `invoice_id` | `str` | Required | Invoice ID |
| `pol_id` | `str` | Required | POL number (e.g., `'POL-12349'`) |
| `amount` | `float` | Required | Line amount |
| `quantity` | `int` | `1` | Line quantity |
| `fund_code` | `Optional[str]` | `None` | Fund code (auto-extracted from POL if not provided) |
| `currency` | `str` | `'ILS'` | Currency code |

**Returns:** Created invoice line dictionary

##### create_invoice_with_lines()

```python
def create_invoice_with_lines(
    self,
    invoice_number: str,
    invoice_date: str,
    vendor_code: str,
    lines: List[Dict[str, Any]],
    currency: str = "ILS",
    auto_process: bool = True,
    auto_pay: bool = False,
    check_duplicates: bool = False,
    **invoice_kwargs
) -> Dict[str, Any]
```

Create a complete invoice with lines in a single workflow.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `invoice_number` | `str` | Required | Vendor invoice number |
| `invoice_date` | `str` | Required | Invoice date |
| `vendor_code` | `str` | Required | Vendor code |
| `lines` | `List[Dict]` | Required | List of line items |
| `currency` | `str` | `'ILS'` | Currency code |
| `auto_process` | `bool` | `True` | Automatically approve invoice |
| `auto_pay` | `bool` | `False` | Automatically mark as paid |
| `check_duplicates` | `bool` | `False` | Check for duplicate POL invoicing |

**Line Item Structure:**

```python
{
    'pol_id': 'POL-12349',  # Required
    'amount': 50.00,       # Required
    'quantity': 1,         # Optional, default 1
    'fund_code': 'FUND1',  # Optional, auto-extracted if missing
    'note': 'Optional note'
}
```

**Returns:** Dictionary containing:
- `invoice_id`: Created invoice ID
- `invoice_number`: Invoice number
- `line_ids`: List of created line IDs
- `total_amount`: Calculated total
- `status`: Final invoice status
- `processed`: Whether invoice was processed
- `paid`: Whether invoice was paid
- `errors`: List of any errors

**Example:**

```python
lines = [
    {"pol_id": "POL-12347", "amount": 50.00, "quantity": 1},
    {"pol_id": "POL-12348", "amount": 75.00, "quantity": 2}
]

result = acq.create_invoice_with_lines(
    invoice_number="INV-2025-001",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    lines=lines,
    auto_process=True,
    auto_pay=True
)

print(f"Invoice ID: {result['invoice_id']}")
print(f"Lines created: {len(result['line_ids'])}")
```

##### Other Invoice Methods

| Method | Description |
|--------|-------------|
| `get_invoice(invoice_id, view='full')` | Retrieve invoice by ID |
| `list_invoices(limit, offset, status, vendor_code)` | List invoices with filters |
| `search_invoices(query, limit, offset)` | Search invoices with query |
| `get_invoice_lines(invoice_id, limit, offset)` | Get invoice lines |
| `approve_invoice(invoice_id)` | Process/approve an invoice |
| `mark_invoice_paid(invoice_id, force=False)` | Mark invoice as paid |
| `reject_invoice(invoice_id)` | Reject an invoice |
| `check_invoice_payment_status(invoice_id)` | Check payment status |
| `get_invoice_summary(invoice_id)` | Get invoice summary |

##### POL Methods

| Method | Description |
|--------|-------------|
| `get_pol(pol_id)` | Retrieve a Purchase Order Line |
| `extract_items_from_pol_data(pol_data)` | Extract items from POL data |
| `get_fund_from_pol(pol_id)` | Get fund code from POL |
| `check_pol_invoiced(pol_id)` | Check if POL is already invoiced |

---

### Users

Handles user management and email operations.

#### Constructor

```python
Users(client: AlmaAPIClient)
```

#### Key Methods

##### get_user()

```python
def get_user(self, user_id: str, expand: str = "none") -> AlmaResponse
```

Retrieve a user by their ID.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | `str` | Required | User identifier (primary ID, barcode, etc.) |
| `expand` | `str` | `'none'` | Additional data to include (`loans`, `requests`, `fees`) |

**Returns:** `AlmaResponse` containing user data

**Example:**

```python
response = users.get_user('john.doe@example.com')
user_data = response.json()
print(f"User: {user_data['first_name']} {user_data['last_name']}")
```

##### update_user()

```python
def update_user(self, user_id: str, user_data: Dict[str, Any]) -> AlmaResponse
```

Update a user record.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | `str` | User identifier |
| `user_data` | `Dict[str, Any]` | Complete user data to update |

**Returns:** `AlmaResponse` containing updated user data

##### update_user_email()

```python
def update_user_email(
    self,
    user_id: str,
    new_email: str,
    email_type: str = 'personal'
) -> AlmaResponse
```

Update a user's primary email address.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | `str` | Required | User identifier |
| `new_email` | `str` | Required | New email address |
| `email_type` | `str` | `'personal'` | Type of email |

**Returns:** `AlmaResponse` containing updated user data

##### Expiry Analysis Methods

| Method | Description |
|--------|-------------|
| `get_user_expiry_date(user_data)` | Extract expiry date from user data |
| `parse_expiry_date(expiry_date_str)` | Parse Alma expiry date string to datetime |
| `is_user_expired_years(user_data, years_threshold=2)` | Check if user is expired for specified years |

##### Email Methods

| Method | Description |
|--------|-------------|
| `extract_user_emails(user_data)` | Extract all email addresses from user data |
| `validate_email(email)` | Validate email format |
| `generate_new_email(user_data, email_pattern)` | Generate new email using pattern |

##### Batch Processing Methods

| Method | Description |
|--------|-------------|
| `process_user_for_expiry(user_id, years_threshold=2)` | Process single user for expiry qualification |
| `process_users_batch(user_ids, years_threshold=2, max_workers=5)` | Process multiple users |
| `bulk_update_emails(email_updates, dry_run=True)` | Update multiple users' emails |

---

### BibliographicRecords

Handles bibliographic records, holdings, items, and digital representations.

#### Constructor

```python
BibliographicRecords(client: AlmaAPIClient)
```

#### Key Methods

##### get_record()

```python
def get_record(
    self,
    mms_id: str,
    view: str = "full",
    expand: str = None
) -> AlmaResponse
```

Retrieve a bibliographic record by MMS ID.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mms_id` | `str` | Required | The MMS ID of the bibliographic record |
| `view` | `str` | `'full'` | Level of detail (`brief`, `full`) |
| `expand` | `str` | `None` | Additional data (`p_avail`, `e_avail`, `d_avail`) |

**Returns:** `AlmaResponse` containing the bibliographic record

**Example:**

```python
response = bibs.get_record('991234567890123456')
bib_data = response.json()
```

##### search_records()

```python
def search_records(
    self,
    q: str,
    limit: int = 10,
    offset: int = 0,
    order_by: str = None,
    direction: str = "asc"
) -> AlmaResponse
```

Search bibliographic records.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | `str` | Required | Search query (e.g., `'title~Harry Potter'`) |
| `limit` | `int` | `10` | Number of results (max 100) |
| `offset` | `int` | `0` | Starting point |
| `order_by` | `str` | `None` | Field to sort by |
| `direction` | `str` | `'asc'` | Sort direction (`asc`, `desc`) |

**Returns:** `AlmaResponse` containing search results

##### create_record()

```python
def create_record(
    self,
    marc_xml: str,
    validate: bool = True,
    override_warning: bool = False
) -> AlmaResponse
```

Create a new bibliographic record.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `marc_xml` | `str` | Required | MARC XML data for the record |
| `validate` | `bool` | `True` | Whether to validate the record |
| `override_warning` | `bool` | `False` | Whether to override validation warnings |

**Returns:** `AlmaResponse` containing the created record

##### update_record()

```python
def update_record(
    self,
    mms_id: str,
    marc_xml: str,
    validate: bool = True,
    override_warning: bool = True,
    override_lock: bool = True,
    stale_version_check: bool = False
) -> AlmaResponse
```

Update an existing bibliographic record.

##### Holdings Methods

| Method | Description |
|--------|-------------|
| `get_holdings(mms_id, holding_id=None)` | Get holdings for a bib record |
| `create_holding(mms_id, holding_data)` | Create a new holding record |

##### Items Methods

| Method | Description |
|--------|-------------|
| `get_items(mms_id, holding_id='ALL', item_id=None)` | Get items for a bib record |
| `create_item(mms_id, holding_id, item_data)` | Create a new item |
| `scan_in_item(mms_id, holding_id, item_pid, library, ...)` | Scan in an item |

##### scan_in_item()

```python
def scan_in_item(
    self,
    mms_id: str,
    holding_id: str,
    item_pid: str,
    library: str,
    department: Optional[str] = None,
    circ_desk: Optional[str] = None,
    work_order_type: Optional[str] = None,
    status: Optional[str] = None,
    done: bool = False,
    confirm: bool = True
) -> AlmaResponse
```

Scan in an item to a department with optional work order.

**Example:**

```python
bibs.scan_in_item(
    mms_id="99123456789",
    holding_id="22123456789",
    item_pid="23123456789",
    library="ACQ_LIB",
    department="ACQ_DEPT",
    work_order_type="AcqWorkOrder",
    status="CopyCataloging",
    done=False
)
```

##### Digital Representations Methods

| Method | Description |
|--------|-------------|
| `get_representations(mms_id, representation_id=None)` | Get digital representations |
| `create_representation(mms_id, access_rights_value, ...)` | Create a representation |
| `get_representation_files(mms_id, representation_id, file_id=None)` | Get files |
| `link_file_to_representation(mms_id, representation_id, file_path)` | Link a file |
| `update_representation_file(mms_id, representation_id, file_id, file_data)` | Update a file |

##### MARC Field Methods

| Method | Description |
|--------|-------------|
| `get_marc_subfield(mms_id, field, subfield)` | Get MARC subfield values |
| `update_marc_field(mms_id, field, subfields, ind1, ind2)` | Update a MARC field |

---

### Admin

Handles sets management and administrative operations.

#### Constructor

```python
Admin(client: AlmaAPIClient)
```

#### Key Methods

##### get_set_members()

```python
def get_set_members(
    self,
    set_id: str,
    expected_type: Optional[str] = None
) -> List[str]
```

Extract all member IDs from an Alma set using pagination.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `set_id` | `str` | Required | The ID of the Alma set |
| `expected_type` | `Optional[str]` | `None` | Validate type: `'BIB_MMS'`, `'USER'`, or `None` for auto-detect |

**Returns:** List of member IDs (MMS IDs for BIB sets, User IDs for USER sets)

**Example:**

```python
# Get all members from any set type
members = admin.get_set_members('25793308630004146')

# Get members with type validation
bib_ids = admin.get_set_members('25793308630004146', expected_type='BIB_MMS')
```

##### Convenience Methods

| Method | Description |
|--------|-------------|
| `get_user_set_members(set_id)` | Get user IDs from a USER set |
| `get_bib_set_members(set_id)` | Get MMS IDs from a BIB_MMS set |

##### get_set_info()

```python
def get_set_info(self, set_id: str) -> Dict[str, Any]
```

Get detailed information about a set.

**Returns:** Dictionary containing:
- `id`: Set ID
- `name`: Set name
- `description`: Set description
- `content_type`: Set type (`'BIB_MMS'`, `'USER'`)
- `status`: Set status
- `total_members`: Number of members
- `created_date`: Creation date
- `created_by`: Creator

##### validate_user_set()

```python
def validate_user_set(self, set_id: str) -> Dict[str, Any]
```

Validate that a set exists and is a USER type set.

**Returns:** Set information if valid

**Raises:** `AlmaValidationError` if set is not USER type

##### list_sets()

```python
def list_sets(
    self,
    limit: int = 25,
    offset: int = 0,
    content_type: str = None,
    include_member_counts: bool = False
) -> AlmaResponse
```

List sets with optional filtering.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | `int` | `25` | Maximum results (max 100) |
| `offset` | `int` | `0` | Starting point |
| `content_type` | `str` | `None` | Filter by type (`'BIB_MMS'`, `'USER'`) |
| `include_member_counts` | `bool` | `False` | Fetch member counts (slower) |

**Returns:** `AlmaResponse` containing the list of sets

##### get_set_metadata_and_member_count()

```python
def get_set_metadata_and_member_count(self, set_id: str) -> Dict[str, Any]
```

Get set metadata with processing estimates.

**Returns:** Dictionary containing:
- `basic_info`: Set details
- `member_info`: Member count and processing estimates
- `creation_info`: Creation details
- `processing_warnings`: List of warnings for large sets

---

### ResourceSharing

Handles resource sharing lending and borrowing requests via the Partners API.

#### Constructor

```python
ResourceSharing(client: AlmaAPIClient)
```

#### Key Methods

##### create_lending_request()

```python
def create_lending_request(
    self,
    partner_code: str,
    external_id: str,
    owner: str,
    format_type: str,
    title: str,
    citation_type: Optional[str] = None,
    mms_id: Optional[str] = None,
    **optional_fields
) -> Dict[str, Any]
```

Create a new lending request for a partner.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `partner_code` | `str` | Required | Partner institution code |
| `external_id` | `str` | Required | External identifier for the request |
| `owner` | `str` | Required | Resource sharing library code (e.g., `'MAIN'`) |
| `format_type` | `str` | Required | Request format (`'PHYSICAL'` or `'DIGITAL'`) |
| `title` | `str` | Required | Resource title (required unless mms_id provided) |
| `citation_type` | `Optional[str]` | `None` | Resource type (`'BOOK'`, `'JOURNAL'`) |
| `mms_id` | `Optional[str]` | `None` | Alma MMS ID if resource exists |

**Optional Fields:**
- `author`: str
- `isbn`: str
- `issn`: str
- `publisher`: str
- `year`: str
- `volume`: str
- `issue`: str
- `pages`: str
- `doi`: str
- `pmid`: str
- `status`: Dict[str, str]
- `level_of_service`: Dict[str, str]
- `rs_note`: List[Dict]

**Returns:** Created lending request dictionary with `request_id`

**Example:**

```python
request = rs.create_lending_request(
    partner_code="PARTNER_01",
    external_id="EXT-2025-001",
    owner="MAIN",
    format_type="PHYSICAL",
    title="Introduction to Library Science",
    citation_type="BOOK",
    author="Smith, John",
    isbn="978-0-123456-78-9"
)
print(f"Request ID: {request['request_id']}")
```

##### get_lending_request()

```python
def get_lending_request(
    self,
    partner_code: str,
    request_id: str
) -> Dict[str, Any]
```

Retrieve a lending request by ID.

**Returns:** Lending request data dictionary

##### create_lending_request_from_citation()

```python
def create_lending_request_from_citation(
    self,
    partner_code: str,
    external_id: str,
    owner: str,
    format_type: str,
    pmid: Optional[str] = None,
    doi: Optional[str] = None,
    source_type: Optional[str] = None,
    **override_fields
) -> Dict[str, Any]
```

Create a lending request with metadata auto-populated from PubMed or Crossref.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `partner_code` | `str` | Required | Partner institution code |
| `external_id` | `str` | Required | External identifier |
| `owner` | `str` | Required | Resource sharing library code |
| `format_type` | `str` | Required | Request format |
| `pmid` | `Optional[str]` | `None` | PubMed ID |
| `doi` | `Optional[str]` | `None` | Digital Object Identifier |
| `source_type` | `Optional[str]` | `None` | Explicit source: `'pmid'` or `'doi'` |

**Example:**

```python
# Using PubMed ID
request = rs.create_lending_request_from_citation(
    partner_code="RELAIS",
    external_id="ILL-2025-001",
    owner="MAIN",
    format_type="DIGITAL",
    pmid="33219451",
    source_type='pmid'
)
```

##### get_request_summary()

```python
def get_request_summary(self, request_data: Dict[str, Any]) -> Dict[str, str]
```

Extract key information from a lending request for display.

**Returns:** Summary dictionary with key fields

---

## Utilities

### TSVGenerator

Config-driven utility for creating TSV files from Alma sets.

#### Constructor

```python
TSVGenerator(config_path: str)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `config_path` | `str` | Path to JSON configuration file |

#### Methods

##### generate_tsv()

```python
def generate_tsv(
    self,
    set_id_override: str = None,
    environment_override: str = None
) -> str
```

Generate TSV file based on configuration.

**Returns:** Path to the created TSV file

##### preview_config()

```python
def preview_config(self) -> None
```

Print a preview of the current configuration.

#### Configuration File Structure

```json
{
    "input": {
        "alma_set_id": "25793308630004146",
        "environment": "SANDBOX"
    },
    "columns": [
        {
            "name": "MMS_ID",
            "source": "alma_set"
        },
        {
            "name": "Library_Code",
            "default_value": "LGBTQ"
        }
    ],
    "output_settings": {
        "file_prefix": "alma_input",
        "include_headers": false,
        "output_directory": "./output"
    }
}
```

#### Convenience Functions

```python
from almaapitk import TSVGenerator

# Create TSV from config
tsv_path = create_tsv_from_config('config.json')

# Preview configuration
preview_config('config.json')

# Create sample config
create_sample_config('sample_config.json')
```

---

### Citation Metadata

Fetch article metadata from PubMed and Crossref.

#### CitationMetadataError

```python
class CitationMetadataError(Exception):
    """Base exception for citation metadata errors."""
    pass
```

#### Functions

##### get_pubmed_metadata()

```python
def get_pubmed_metadata(pmid: str) -> Dict[str, Any]
```

Fetch article metadata from PubMed using PubMed ID.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `pmid` | `str` | PubMed ID (e.g., `'12345678'`) |

**Returns:** Dictionary with:
- `title`: Article title
- `authors`: List of author names
- `author`: Comma-separated author string
- `journal`: Journal name
- `year`: Publication year
- `volume`: Journal volume
- `issue`: Journal issue
- `pages`: Page range
- `doi`: DOI if available
- `pmid`: PubMed ID
- `issn`: ISSN
- `publication_date`: Full publication date

**Raises:**
- `PubMedError`: If API request fails
- `ValueError`: If PMID is invalid format

##### get_crossref_metadata()

```python
def get_crossref_metadata(doi: str) -> Dict[str, Any]
```

Fetch article metadata from Crossref using DOI.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `doi` | `str` | Digital Object Identifier |

**Returns:** Dictionary with same fields as PubMed, plus:
- `publisher`: Publisher name
- `type`: Work type

**Raises:**
- `CrossrefError`: If API request fails
- `ValueError`: If DOI is invalid

##### enrich_citation_metadata()

```python
def enrich_citation_metadata(
    pmid: Optional[str] = None,
    doi: Optional[str] = None,
    source_type: Optional[str] = None
) -> Dict[str, Any]
```

Fetch citation metadata from PubMed or Crossref with fallback support.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pmid` | `Optional[str]` | `None` | PubMed ID |
| `doi` | `Optional[str]` | `None` | Digital Object Identifier |
| `source_type` | `Optional[str]` | `None` | Explicit source: `'pmid'`, `'doi'`, or `None` for auto-detect |

**Returns:** Metadata dictionary with `source` field indicating which API was used

**Example:**

```python
from almaapitk.utils.citation_metadata import enrich_citation_metadata

# Explicit source
metadata = enrich_citation_metadata(pmid="33219451", source_type='pmid')
print(f"Source: {metadata['source']}")  # 'pubmed'

# Auto-detect with fallback
metadata = enrich_citation_metadata(pmid="33219451", doi="10.1038/example")
```

---

## See Also

- [Getting Started Guide](getting-started.md)
- [API Contract](API_CONTRACT.md)
- [Resource Sharing Guide](RESOURCE_SHARING_GUIDE.md)
- [CLAUDE.md](../CLAUDE.md) - Project guidelines and architecture
