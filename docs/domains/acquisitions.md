# Acquisitions Domain Class

Comprehensive guide to the Acquisitions domain class for managing invoices, purchase order lines (POLs), and item receiving in the Alma ILS.

## Table of Contents

- [Overview](#overview)
- [Initialization](#initialization)
- [Methods Reference](#methods-reference)
  - [Invoice Operations](#invoice-operations)
  - [Invoice Line Operations](#invoice-line-operations)
  - [POL Operations](#pol-operations)
  - [Item Receiving](#item-receiving)
  - [POL Utility Methods](#pol-utility-methods)
  - [Workflow Methods](#workflow-methods)
  - [Utility Methods](#utility-methods)
- [Common Workflows](#common-workflows)
- [Alma API Reference](#alma-api-reference)
- [Best Practices and Gotchas](#best-practices-and-gotchas)

---

## Overview

### What This Domain Handles

The `Acquisitions` class provides a comprehensive interface for managing acquisition operations in Alma:

- **Invoice Management**: Create, retrieve, approve, pay, and reject invoices
- **Invoice Lines**: Add line items linking invoices to purchase order lines
- **Purchase Order Lines (POLs)**: Retrieve and update POL data, extract pricing and fund information
- **Item Receiving**: Receive physical items associated with POLs
- **Duplicate Prevention**: Check for existing invoices before creating new ones

### When to Use It

Use the Acquisitions class when you need to:

- Process invoices for library material purchases
- Automate invoice creation from vendor data (e.g., Rialto EDI files)
- Receive physical items and update inventory status
- Extract information from POLs for invoice creation
- Prevent duplicate invoicing for the same POLs

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Invoice** | A billing record from a vendor containing one or more lines |
| **Invoice Line** | A single item on an invoice, linked to a POL |
| **POL (Purchase Order Line)** | An order for library materials with pricing, fund, and vendor info |
| **Fund Distribution** | How payment for a line item is allocated across library funds |
| **Item** | A physical copy associated with a POL that can be received |

---

## Initialization

### Creating an Instance

The Acquisitions class requires an initialized `AlmaAPIClient` instance:

```python
from almaapitk import AlmaAPIClient, Acquisitions

# Initialize the API client (SANDBOX or PRODUCTION)
client = AlmaAPIClient('SANDBOX')

# Create the Acquisitions domain instance
acq = Acquisitions(client)

# Verify connection
if acq.test_connection():
    print(f"Connected to Acquisitions API ({acq.get_environment()})")
```

### Environment Variables Required

- `ALMA_SB_API_KEY`: For SANDBOX environment
- `ALMA_PROD_API_KEY`: For PRODUCTION environment

---

## Methods Reference

### Invoice Operations

#### `get_invoice(invoice_id, view="full")`

Retrieve an invoice by ID.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `invoice_id` | str | Yes | - | The invoice ID to retrieve |
| `view` | str | No | "full" | Level of detail ("brief" or "full") |

**Returns:** `Dict[str, Any]` - Invoice data dictionary

**Example:**
```python
invoice = acq.get_invoice("123456789")
print(f"Invoice Number: {invoice['number']}")
print(f"Status: {invoice['invoice_status']['value']}")
print(f"Payment Status: {invoice['payment']['payment_status']['value']}")
```

**Common Errors:**
- `AlmaAPIError`: Invoice not found or API request failed

---

#### `create_invoice(invoice_data)`

Create a new invoice (low-level method).

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invoice_data` | Dict | Yes | Complete invoice data dictionary |

**Returns:** `Dict[str, Any]` - Created invoice with ID

**Note:** Consider using `create_invoice_simple()` for a more user-friendly interface.

---

#### `create_invoice_simple(invoice_number, invoice_date, vendor_code, total_amount, currency="ILS", **optional_fields)`

Create an invoice with simplified parameters (recommended).

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `invoice_number` | str | Yes | - | Vendor invoice number |
| `invoice_date` | str/datetime | Yes | - | Invoice date (YYYY-MM-DD or datetime) |
| `vendor_code` | str | Yes | - | Vendor code from Alma |
| `total_amount` | float | Yes | - | Total invoice amount |
| `currency` | str | No | "ILS" | Currency code |
| `invoice_due_date` | str | No | - | Due date for payment |
| `vendor_account` | str | No | - | Vendor account code |
| `reference_number` | str | No | - | Reference number |
| `payment_method` | str | No | - | Payment method |
| `notes` | List[str] | No | - | Invoice notes |
| `payment` | Dict | No | - | Payment info (voucher, etc.) |
| `invoice_vat` | Dict | No | - | VAT details |
| `additional_charges` | Dict | No | - | Shipment, overhead, etc. |

**Returns:** `Dict[str, Any]` - Created invoice with ID

**Example:**
```python
# Simple invoice
invoice = acq.create_invoice_simple(
    invoice_number="INV-2025-001",
    invoice_date="2025-10-21",
    vendor_code="RIALTO",
    total_amount=100.00,
    currency="ILS"
)
print(f"Created invoice: {invoice['id']}")

# Invoice with optional fields
invoice = acq.create_invoice_simple(
    invoice_number="INV-2025-002",
    invoice_date="2025-10-21",
    vendor_code="RIALTO",
    total_amount=250.00,
    reference_number="PO-12345",
    payment={"voucher_number": "V-001"},
    notes=["Payment for books", "Rush order"]
)
```

**Common Errors:**
- `ValueError`: Missing or invalid required fields
- `AlmaAPIError`: API request failed

---

#### `approve_invoice(invoice_id)`

Process/approve an invoice. **This is MANDATORY before payment.**

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invoice_id` | str | Yes | The invoice ID to approve |

**Returns:** `Dict[str, Any]` - Updated invoice data

**Example:**
```python
# MANDATORY: Approve before paying
processed = acq.approve_invoice(invoice_id)
print(f"Invoice approved: {processed['invoice_approval_status']['value']}")
```

**API Endpoint:** `POST /almaws/v1/acq/invoices/{invoice_id}?op=process_invoice`

---

#### `mark_invoice_paid(invoice_id, force=False)`

Mark an invoice as paid with automatic duplicate payment protection.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `invoice_id` | str | Yes | - | The invoice ID to mark as paid |
| `force` | bool | No | False | Bypass duplicate payment protection (dangerous!) |

**Returns:** `Dict[str, Any]` - Updated invoice data

**Example:**
```python
# Safe payment with automatic protection
try:
    result = acq.mark_invoice_paid(invoice_id)
    print("Invoice paid successfully")
except AlmaAPIError as e:
    print(f"Payment prevented: {e}")

# Force payment (NOT RECOMMENDED)
result = acq.mark_invoice_paid(invoice_id, force=True)
```

**Common Errors:**
- `AlmaAPIError`: Invoice already paid, not approved, or closed

---

#### `check_invoice_payment_status(invoice_id)`

Check if an invoice has already been paid (duplicate payment protection).

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invoice_id` | str | Yes | The invoice ID to check |

**Returns:**
```python
{
    'is_paid': bool,           # Whether invoice is already paid
    'payment_status': str,     # PAID, NOT_PAID, FULLY_PAID, etc.
    'invoice_status': str,     # ACTIVE, CLOSED, etc.
    'approval_status': str,    # APPROVED, PENDING, etc.
    'can_pay': bool,           # Whether it's safe to mark as paid
    'warnings': List[str]      # Any warnings about payment
}
```

**Example:**
```python
check = acq.check_invoice_payment_status(invoice_id)
if check['is_paid']:
    print(f"Invoice already paid: {check['payment_status']}")
elif check['can_pay']:
    acq.mark_invoice_paid(invoice_id)
else:
    print(f"Cannot pay: {check['warnings']}")
```

---

#### `reject_invoice(invoice_id)`

Reject an invoice.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invoice_id` | str | Yes | The invoice ID to reject |

**Returns:** `Dict[str, Any]` - Updated invoice data

---

#### `mark_invoice_in_erp(invoice_id)`

Mark an invoice as sent to ERP system.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invoice_id` | str | Yes | The invoice ID to mark |

**Returns:** `Dict[str, Any]` - Updated invoice data

---

#### `get_invoice_summary(invoice_id)`

Get a formatted summary of key invoice information.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invoice_id` | str | Yes | The invoice ID |

**Returns:**
```python
{
    "invoice_id": str,
    "invoice_number": str,
    "vendor_code": str,
    "vendor_name": str,
    "invoice_date": str,
    "total_amount": str,
    "currency": str,
    "status": str,
    "payment_status": str
}
```

---

#### `list_invoices(limit=10, offset=0, status=None, vendor_code=None)`

List invoices with optional filtering.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | int | No | 10 | Maximum results to return |
| `offset` | int | No | 0 | Starting offset for pagination |
| `status` | str | No | None | Filter by invoice status |
| `vendor_code` | str | No | None | Filter by vendor code |

**Returns:** `Dict[str, Any]` - List response with `invoice` array and `total_record_count`

**Example:**
```python
# List all invoices
invoices = acq.list_invoices(limit=50)

# Filter by vendor
invoices = acq.list_invoices(vendor_code="RIALTO")

# Filter by status
invoices = acq.list_invoices(status="WAITING_TO_BE_SENT")
```

---

#### `search_invoices(query, limit=10, offset=0)`

Search invoices with a custom query.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | Yes | - | Search query string |
| `limit` | int | No | 10 | Maximum results |
| `offset` | int | No | 0 | Starting offset |

**Returns:** `Dict[str, Any]` - Search results

**Example:**
```python
# Search by vendor and status
results = acq.search_invoices("vendor~RIALTO AND invoice_status~WAITING_TO_BE_SENT")

# Search by POL number
results = acq.search_invoices("pol_number~POL-12347")
```

---

### Invoice Line Operations

#### `create_invoice_line(invoice_id, line_data)`

Create an invoice line (low-level method).

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `invoice_id` | str | Yes | Invoice ID |
| `line_data` | Dict | Yes | Complete line data dictionary |

**Returns:** `Dict[str, Any]` - Created line data

**Note:** Consider using `create_invoice_line_simple()` for a more user-friendly interface.

---

#### `create_invoice_line_simple(invoice_id, pol_id, amount, quantity=1, fund_code=None, currency="ILS", **optional_fields)`

Create an invoice line with simplified parameters (recommended).

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `invoice_id` | str | Yes | - | Invoice ID |
| `pol_id` | str | Yes | - | POL number (e.g., "POL-12349") |
| `amount` | float | Yes | - | Line amount |
| `quantity` | int | No | 1 | Line quantity |
| `fund_code` | str | No | None | Fund code (auto-extracted from POL if not provided) |
| `currency` | str | No | "ILS" | Currency code |
| `invoice_line_type` | str | No | "REGULAR" | Line type |
| `note` | str | No | - | Line note |
| `subscription_from_date` | str | No | - | Subscription start date |
| `subscription_to_date` | str | No | - | Subscription end date |
| `vat` | Dict | No | - | VAT details |

**Returns:** `Dict[str, Any]` - Created line data

**Example:**
```python
# Simple line
line = acq.create_invoice_line_simple(
    invoice_id="123456789",
    pol_id="POL-12349",
    amount=100.00,
    fund_code="LIBRARY_FUND"
)

# Auto-detect fund from POL
line = acq.create_invoice_line_simple(
    invoice_id="123456789",
    pol_id="POL-12349",
    amount=100.00
    # fund_code will be extracted from POL automatically
)

# With subscription dates
line = acq.create_invoice_line_simple(
    invoice_id="123456789",
    pol_id="POL-12352",
    amount=200.00,
    fund_code="JOURNAL_FUND",
    subscription_from_date="2025-01-01",
    subscription_to_date="2025-12-31"
)
```

**Common Errors:**
- `ValueError`: Missing fund_code and cannot extract from POL
- `AlmaAPIError`: API request failed

---

#### `get_invoice_lines(invoice_id, limit=100, offset=0)`

Get all invoice lines for a specific invoice.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `invoice_id` | str | Yes | - | The invoice ID |
| `limit` | int | No | 100 | Maximum lines to retrieve |
| `offset` | int | No | 0 | Starting offset |

**Returns:** `List[Dict[str, Any]]` - List of invoice line dictionaries

**Example:**
```python
lines = acq.get_invoice_lines(invoice_id)
for line in lines:
    print(f"POL: {line['po_line']}, Amount: {line['price']}")
```

---

### POL Operations

#### `get_pol(pol_id)`

Retrieve a Purchase Order Line by ID.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pol_id` | str | Yes | Purchase Order Line ID |

**Returns:** `Dict[str, Any]` - POL data dictionary

**Example:**
```python
pol = acq.get_pol("POL-12349")
print(f"Vendor: {pol['vendor']['value']}")
print(f"Status: {pol['status']['value']}")
```

---

#### `update_pol(pol_id, pol_data)`

Update a Purchase Order Line.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pol_id` | str | Yes | Purchase Order Line ID |
| `pol_data` | Dict | Yes | Updated POL data |

**Returns:** `Dict[str, Any]` - Updated POL data

---

#### `get_pol_items(pol_id)`

Get all items associated with a POL using the dedicated items endpoint.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pol_id` | str | Yes | Purchase Order Line ID |

**Returns:** `List[Dict[str, Any]]` - List of item dictionaries

**Example:**
```python
items = acq.get_pol_items("POL-12349")
for item in items:
    print(f"Item ID: {item['pid']}, Barcode: {item.get('barcode')}")
```

---

#### `extract_items_from_pol_data(pol_data)`

Extract items from POL data structure (avoids extra API call).

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pol_data` | Dict | Yes | POL data dictionary from `get_pol()` |

**Returns:** `List[Dict[str, Any]]` - List of item dictionaries

**Example:**
```python
pol_data = acq.get_pol("POL-12349")
items = acq.extract_items_from_pol_data(pol_data)

# Find unreceived items
unreceived = [item for item in items if not item.get('receive_date')]
```

**Note:** Items in POL data are nested in `location -> copy` structure. This method flattens that structure.

---

### Item Receiving

#### `receive_item(pol_id, item_id, receive_date=None, department=None, department_library=None)`

Receive an existing item in a POL (standard receiving).

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pol_id` | str | Yes | - | Purchase Order Line ID |
| `item_id` | str | Yes | - | Item ID to receive |
| `receive_date` | str | No | None | Date in format YYYY-MM-DDZ |
| `department` | str | No | None | Department code |
| `department_library` | str | No | None | Library code |

**Returns:** `Dict[str, Any]` - Updated item data

**Example:**
```python
# Standard receiving (item goes to "in transit")
result = acq.receive_item(
    pol_id="POL-12345",
    item_id="23435899800121",
    receive_date="2025-01-15Z"
)
```

**Note:** After standard receiving, items move to "in transit" status.

---

#### `receive_and_keep_in_department(pol_id, item_id, mms_id, holding_id, library, department, work_order_type="AcqWorkOrder", work_order_status="CopyCataloging", receive_date=None)`

Receive an item and keep it in department (prevents Transit status).

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pol_id` | str | Yes | - | Purchase Order Line ID |
| `item_id` | str | Yes | - | Item ID to receive |
| `mms_id` | str | Yes | - | Bibliographic record ID |
| `holding_id` | str | Yes | - | Holding ID |
| `library` | str | Yes | - | Library code |
| `department` | str | Yes | - | Department code |
| `work_order_type` | str | No | "AcqWorkOrder" | Work order type code |
| `work_order_status` | str | No | "CopyCataloging" | Work order status |
| `receive_date` | str | No | None | Receive date |

**Returns:** `Dict[str, Any]` - Final item data after scan-in

**Example:**
```python
# Get POL data first
pol_data = acq.get_pol("POL-12345")
items = acq.extract_items_from_pol_data(pol_data)
unreceived = [i for i in items if not i.get('receive_date')]

if unreceived:
    item = unreceived[0]
    mms_id = pol_data.get('resource_metadata', {}).get('mms_id', {}).get('value')
    holding_id = pol_data.get('location', [{}])[0].get('holding_id')

    result = acq.receive_and_keep_in_department(
        pol_id="POL-12345",
        item_id=item['pid'],
        mms_id=mms_id,
        holding_id=holding_id,
        library="MAIN",
        department="ACQ",
        work_order_type="AcqWorkOrder",
        work_order_status="CopyCataloging"
    )
```

**Note:** Work order types and statuses must be configured in Alma.

---

### POL Utility Methods

#### `get_vendor_from_pol(pol_id)`

Extract vendor code from a POL.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pol_id` | str | Yes | POL number |

**Returns:** `Optional[str]` - Vendor code or None

**Example:**
```python
vendor_code = acq.get_vendor_from_pol("POL-12349")
if vendor_code:
    invoice = acq.create_invoice_simple(
        invoice_number="INV-001",
        invoice_date="2025-10-22",
        vendor_code=vendor_code,
        total_amount=100.00
    )
```

---

#### `get_fund_from_pol(pol_id)`

Extract primary fund code from a POL.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pol_id` | str | Yes | POL number |

**Returns:** `Optional[str]` - Fund code or None

**Note:** If POL has multiple funds, only the first (primary) fund is returned.

---

#### `get_price_from_pol(pol_id)`

Extract price (list price) from a POL.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pol_id` | str | Yes | POL number |

**Returns:** `Optional[float]` - Price as float or None

**Example:**
```python
price = acq.get_price_from_pol("POL-12349")
if price:
    line = acq.create_invoice_line_simple(
        invoice_id="123456789",
        pol_id="POL-12349",
        amount=price  # Use POL's actual price
    )
```

---

#### `check_pol_invoiced(pol_id)`

Check if a POL is already linked to any invoice lines (prevents double-invoicing).

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pol_id` | str | Yes | POL number |

**Returns:**
```python
{
    'is_invoiced': bool,           # Has existing invoice(s)?
    'invoice_count': int,          # Number of invoices
    'invoices': [                  # List of existing invoices
        {
            'invoice_id': str,
            'invoice_number': str,
            'invoice_status': str,
            'payment_status': str,
            'line_id': str,
            'amount': str
        }
    ]
}
```

**Example:**
```python
check = acq.check_pol_invoiced("POL-12349")
if check['is_invoiced']:
    print(f"POL already has {check['invoice_count']} invoice(s)")
    for inv in check['invoices']:
        print(f"  - Invoice {inv['invoice_number']}: {inv['amount']}")
else:
    # Safe to create invoice line
    line = acq.create_invoice_line_simple(...)
```

---

### Workflow Methods

#### `create_invoice_with_lines(invoice_number, invoice_date, vendor_code, lines, currency="ILS", auto_process=True, auto_pay=False, check_duplicates=False, **invoice_kwargs)`

Create a complete invoice with lines in a single workflow.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `invoice_number` | str | Yes | - | Vendor invoice number |
| `invoice_date` | str/datetime | Yes | - | Invoice date |
| `vendor_code` | str | Yes | - | Vendor code |
| `lines` | List[Dict] | Yes | - | Line items (see below) |
| `currency` | str | No | "ILS" | Currency code |
| `auto_process` | bool | No | True | Automatically approve invoice |
| `auto_pay` | bool | No | False | Automatically mark as paid |
| `check_duplicates` | bool | No | False | Check for existing invoices first |

**Line Item Structure:**
```python
{
    "pol_id": str,      # Required - POL ID
    "amount": float,    # Required - Line amount
    "quantity": int,    # Optional - Default 1
    "fund_code": str,   # Optional - Auto-extracted if missing
    "note": str,        # Optional
    # ... other optional fields
}
```

**Returns:**
```python
{
    'invoice_id': str,        # Created invoice ID
    'invoice_number': str,    # Invoice number
    'line_ids': List[str],    # Created line IDs
    'total_amount': float,    # Calculated total
    'status': str,            # Final invoice status
    'processed': bool,        # Whether approved
    'paid': bool,             # Whether paid
    'errors': List[str]       # Any errors encountered
}
```

**Example:**
```python
lines = [
    {"pol_id": "POL-12347", "amount": 50.00},
    {"pol_id": "POL-12348", "amount": 75.00, "quantity": 2}
]

result = acq.create_invoice_with_lines(
    invoice_number="INV-2025-001",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    lines=lines,
    auto_process=True,
    auto_pay=True,
    check_duplicates=True
)

print(f"Invoice ID: {result['invoice_id']}")
print(f"Lines created: {len(result['line_ids'])}")
print(f"Paid: {result['paid']}")
```

---

### Utility Methods

#### `test_connection()`

Test if the acquisitions endpoints are accessible.

**Returns:** `bool` - True if connection successful

**Example:**
```python
if acq.test_connection():
    print("Connected successfully")
```

---

#### `get_environment()`

Get the current environment from the client.

**Returns:** `str` - "SANDBOX" or "PRODUCTION"

---

## Common Workflows

### Workflow 1: Create and Pay Invoice

The **mandatory** sequence for creating and paying an invoice:

```python
from almaapitk import AlmaAPIClient, Acquisitions

client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

# Step 1: Check for duplicates BEFORE creating
check = acq.check_pol_invoiced("POL-12347")
if check['is_invoiced']:
    print(f"POL already invoiced!")
    # Use existing invoice instead
else:
    # Step 2: Create invoice
    invoice = acq.create_invoice_simple(
        invoice_number="INV-2025-001",
        invoice_date="2025-01-08",
        vendor_code="RIALTO",
        total_amount=100.00
    )
    invoice_id = invoice['id']

    # Step 3: Add invoice lines
    line = acq.create_invoice_line_simple(
        invoice_id=invoice_id,
        pol_id="POL-12347",
        amount=100.00
    )

    # Step 4: MUST approve BEFORE paying
    acq.approve_invoice(invoice_id)

    # Step 5: Mark as paid (includes automatic duplicate protection)
    acq.mark_invoice_paid(invoice_id)
```

### Workflow 2: Complete Invoice with Lines

Use `create_invoice_with_lines()` for a simplified workflow:

```python
lines = [
    {"pol_id": "POL-12347", "amount": 50.00},
    {"pol_id": "POL-12348", "amount": 75.00, "quantity": 2},
    {"pol_id": "POL-12349", "amount": 25.00, "fund_code": "SPECIAL_FUND"}
]

result = acq.create_invoice_with_lines(
    invoice_number="INV-2025-002",
    invoice_date="2025-10-22",
    vendor_code="RIALTO",
    lines=lines,
    auto_process=True,
    auto_pay=True,
    check_duplicates=True
)

if result['errors']:
    print(f"Completed with {len(result['errors'])} errors")
else:
    print(f"Invoice {result['invoice_id']} created and paid successfully")
```

### Workflow 3: Receive Items

Standard receiving (items go to transit):

```python
# Get POL and find unreceived items
pol_data = acq.get_pol("POL-12345")
items = acq.extract_items_from_pol_data(pol_data)
unreceived = [item for item in items if not item.get('receive_date')]

if unreceived:
    item_id = unreceived[0]['pid']
    acq.receive_item("POL-12345", item_id)
```

Keep items in department (prevents transit):

```python
pol_data = acq.get_pol("POL-12345")
items = acq.extract_items_from_pol_data(pol_data)
unreceived = [item for item in items if not item.get('receive_date')]

if unreceived:
    item = unreceived[0]
    mms_id = pol_data.get('resource_metadata', {}).get('mms_id', {}).get('value')
    holding_id = pol_data.get('location', [{}])[0].get('holding_id')

    acq.receive_and_keep_in_department(
        pol_id="POL-12345",
        item_id=item['pid'],
        mms_id=mms_id,
        holding_id=holding_id,
        library="MAIN",
        department="ACQ",
        work_order_type="AcqWorkOrder",
        work_order_status="CopyCataloging"
    )
```

---

## Alma API Reference

### Relevant Endpoints

| Operation | Endpoint | Method |
|-----------|----------|--------|
| Get Invoice | `/almaws/v1/acq/invoices/{invoice_id}` | GET |
| Create Invoice | `/almaws/v1/acq/invoices` | POST |
| List Invoices | `/almaws/v1/acq/invoices` | GET |
| Invoice Service (approve/pay) | `/almaws/v1/acq/invoices/{invoice_id}?op={operation}` | POST |
| Get Invoice Lines | `/almaws/v1/acq/invoices/{invoice_id}/lines` | GET |
| Create Invoice Line | `/almaws/v1/acq/invoices/{invoice_id}/lines` | POST |
| Get POL | `/almaws/v1/acq/po-lines/{pol_id}` | GET |
| Update POL | `/almaws/v1/acq/po-lines/{pol_id}` | PUT |
| Get POL Items | `/almaws/v1/acq/po-lines/{pol_id}/items` | GET |
| Receive Item | `/almaws/v1/acq/po-lines/{pol_id}/items/{item_id}?op=receive` | POST |

### Official Documentation

- **Acquisitions API**: https://developers.exlibrisgroup.com/alma/apis/acq/
- **Schema Reference (XSD)**: https://developers.exlibrisgroup.com/alma/apis/xsd/

---

## Best Practices and Gotchas

### Critical Rules

1. **Always check for duplicates before creating invoices**
   ```python
   check = acq.check_pol_invoiced(pol_id)
   if check['is_invoiced']:
       # DO NOT create new invoice!
   ```

2. **Always approve invoices before paying**
   ```python
   acq.approve_invoice(invoice_id)  # MANDATORY!
   acq.mark_invoice_paid(invoice_id)
   ```

3. **Trust the automatic payment protection**
   - Don't bypass with `force=True` unless absolutely necessary
   - The protection prevents duplicate payments and invalid operations

### API Quirks

1. **Payment status is nested**, not at root level:
   ```python
   # WRONG
   status = invoice['payment_status']

   # CORRECT
   status = invoice['payment']['payment_status']['value']
   ```

2. **POL items are nested** in location -> copy structure:
   ```python
   # Items path: POL -> location (list) -> copy (list)
   # Use extract_items_from_pol_data() to flatten
   ```

3. **Fund distribution must use EITHER percent OR amount**, not both:
   ```python
   # CORRECT
   "fund_distribution": [{"fund_code": {"value": "FUND"}, "percent": 100}]

   # WRONG - both fields
   "fund_distribution": [{"fund_code": {"value": "FUND"}, "percent": 100, "amount": 50}]
   ```

4. **Date format**: Alma API expects `YYYY-MM-DDZ` format (with trailing Z)

5. **Query syntax for searching invoices**:
   ```python
   # CORRECT - tilde format
   query = f"pol_number~{pol_id}"

   # WRONG - colon format causes server error
   query = f"pol_number:{pol_id}"
   ```

### Common Errors

| Error Code | Meaning | Solution |
|------------|---------|----------|
| **402459** | Invoice retrieval error | Must approve invoice before paying |
| **40166411** | Invalid parameter | Check date format (YYYY-MM-DDZ) |
| **401875** | Department not found | Verify department code exists |
| **401871** | PO Line not found | Check POL ID, may be closed |
| **401877** | Failed to receive PO Line | Item may already be received |

### Performance Tips

1. **Extract fund code once** and reuse for multiple lines
2. **Use `extract_items_from_pol_data()`** if you already have POL data to avoid extra API calls
3. **Enable `check_duplicates`** in `create_invoice_with_lines()` only when necessary (causes extra API calls)

### Testing

- **Always test in SANDBOX first** before running in PRODUCTION
- Use `acq.test_connection()` to verify API access
- Check `acq.get_environment()` to confirm environment

---

## See Also

- [Alma API Expert Skill](../../.claude/skills/alma-api-expert/references/acquisitions_api.md) - Complete API reference
- [Error Codes & Solutions](../../.claude/skills/alma-api-expert/references/error_codes_and_solutions.md) - Error troubleshooting
- [API Quirks & Gotchas](../../.claude/skills/alma-api-expert/references/api_quirks_and_gotchas.md) - Known issues
