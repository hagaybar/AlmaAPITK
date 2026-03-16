# AlmaAPITK Code Examples

This document provides comprehensive, runnable code examples for all major operations in AlmaAPITK.

## Table of Contents

1. [Basic Operations](#basic-operations)
2. [Acquisitions Workflows](#acquisitions-workflows)
3. [User Operations](#user-operations)
4. [Bibliographic Records](#bibliographic-records)
5. [Resource Sharing](#resource-sharing)
6. [Admin Operations](#admin-operations)

---

## Basic Operations

### Initialize Client and Test Connection

```python
from almaapitk import AlmaAPIClient, AlmaAPIError

# Initialize client for SANDBOX environment
# Requires ALMA_SB_API_KEY environment variable
client = AlmaAPIClient('SANDBOX')
# Output: Configured for SANDBOX environment

# Test the connection
if client.test_connection():
    print("Successfully connected to Alma API")
    # Output: Successfully connected to Alma API (SANDBOX)
else:
    print("Connection failed")

# Initialize client for PRODUCTION environment
# Requires ALMA_PROD_API_KEY environment variable
prod_client = AlmaAPIClient('PRODUCTION')
# Output: Configured for PRODUCTION environment

# Switch environments at runtime
client.switch_environment('PRODUCTION')
# Output: Switched from SANDBOX to PRODUCTION
```

### Make Simple GET Request

```python
from almaapitk import AlmaAPIClient, AlmaAPIError

client = AlmaAPIClient('SANDBOX')

# Make a GET request to retrieve library configuration
response = client.get('almaws/v1/conf/libraries')

# Check if request was successful
if response.success:
    data = response.json()
    print(f"Found {data['total_record_count']} libraries")
    # Output: Found 5 libraries

    # Access individual libraries
    for library in data.get('library', []):
        print(f"  - {library['name']} ({library['code']})")
else:
    print(f"Request failed with status: {response.status_code}")
```

### Handle Responses and Errors

```python
from almaapitk import AlmaAPIClient, AlmaAPIError, AlmaValidationError

client = AlmaAPIClient('SANDBOX')

try:
    # Attempt to get a non-existent resource
    response = client.get('almaws/v1/bibs/99999999999999999')

    # Response wrapper provides convenient access
    print(f"Status Code: {response.status_code}")
    print(f"Success: {response.success}")

    # Access response data
    data = response.json()  # or response.data (property alias)
    print(f"Record title: {data.get('title')}")

except AlmaAPIError as e:
    # Handle API errors (404, 400, 500, etc.)
    print(f"API Error: {e}")
    print(f"Status Code: {e.status_code}")
    # Output: API Error: HTTP 404 - Record not found

except AlmaValidationError as e:
    # Handle validation errors (client-side)
    print(f"Validation Error: {e}")
```

---

## Acquisitions Workflows

### Get POL Information

```python
from almaapitk import AlmaAPIClient, Acquisitions, AlmaAPIError

client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

# Get a Purchase Order Line by ID
try:
    pol_data = acq.get_pol("POL-12345")

    # Extract key information
    print(f"POL Number: {pol_data.get('number')}")
    print(f"Title: {pol_data.get('title')}")
    print(f"Vendor: {pol_data.get('vendor', {}).get('desc')}")
    print(f"Price: {pol_data.get('price', {}).get('sum')} {pol_data.get('price', {}).get('currency', {}).get('value')}")
    # Output:
    # POL Number: POL-12345
    # Title: Introduction to Library Science
    # Vendor: Academic Books Inc.
    # Price: 45.99 USD

    # Get items associated with this POL
    items = acq.get_pol_items("POL-12345")
    print(f"Number of items: {len(items)}")
    for item in items:
        print(f"  - Item ID: {item.get('pid')}, Status: {item.get('receiving_status')}")

except AlmaAPIError as e:
    print(f"Error: {e}")
```

### Create and Pay Invoice

```python
from almaapitk import AlmaAPIClient, Acquisitions, AlmaAPIError
from datetime import datetime

client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

# Method 1: Create invoice with lines in one workflow
lines = [
    {"pol_id": "POL-12347", "amount": 50.00, "quantity": 1},
    {"pol_id": "POL-12348", "amount": 75.00, "quantity": 2}
]

try:
    result = acq.create_invoice_with_lines(
        invoice_number="INV-2025-001",
        invoice_date="2025-10-22",
        vendor_code="RIALTO",
        lines=lines,
        currency="ILS",
        auto_process=True,  # Automatically approve invoice
        auto_pay=True       # Automatically mark as paid
    )

    print(f"Invoice ID: {result['invoice_id']}")
    print(f"Lines Created: {len(result['line_ids'])}")
    print(f"Total Amount: {result['total_amount']}")
    print(f"Status: {result['status']}")
    print(f"Paid: {result['paid']}")
    # Output:
    # Invoice ID: 123456789
    # Lines Created: 2
    # Total Amount: 125.00
    # Status: CLOSED
    # Paid: True

except AlmaAPIError as e:
    print(f"Error: {e}")

# Method 2: Step-by-step invoice creation
try:
    # Step 1: Create the invoice
    invoice = acq.create_invoice_simple(
        invoice_number="INV-2025-002",
        invoice_date=datetime.now(),  # Accepts datetime objects
        vendor_code="RIALTO",
        total_amount=100.00,
        currency="ILS"
    )
    invoice_id = invoice['id']
    print(f"Created invoice: {invoice_id}")

    # Step 2: Add invoice line
    line = acq.create_invoice_line_simple(
        invoice_id=invoice_id,
        pol_id="POL-12349",
        amount=100.00,
        fund_code="LIBRARY_FUND"  # Optional - auto-detected from POL if not provided
    )
    print(f"Added line for POL-12349")

    # Step 3: Process (approve) the invoice
    processed = acq.approve_invoice(invoice_id)
    print(f"Invoice processed")

    # Step 4: Mark as paid
    paid = acq.mark_invoice_paid(invoice_id)
    print(f"Invoice marked as paid")

except AlmaAPIError as e:
    print(f"Error: {e}")
```

### Receive Items

```python
from almaapitk import AlmaAPIClient, Acquisitions, AlmaAPIError

client = AlmaAPIClient('SANDBOX')
acq = Acquisitions(client)

# Get items for a POL
pol_id = "POL-12345"
items = acq.get_pol_items(pol_id)

for item in items:
    item_id = item.get('pid')
    status = item.get('receiving_status')

    if status != 'RECEIVED':
        try:
            # Simple receive
            result = acq.receive_item(
                pol_id=pol_id,
                item_id=item_id,
                receive_date="2025-10-22Z"
            )
            print(f"Received item {item_id}")
            # Output: Received item 23435899800121

        except AlmaAPIError as e:
            print(f"Failed to receive item {item_id}: {e}")

# Receive and keep in department (prevents Transit status)
try:
    result = acq.receive_and_keep_in_department(
        pol_id="POL-12345",
        item_id="23123456789",
        mms_id="99123456789",
        holding_id="22123456789",
        library="MAIN",
        department="ACQ_DEPT",
        work_order_type="AcqWorkOrder",
        work_order_status="CopyCataloging"
    )
    print(f"Item received and kept in department")
    # Output: Item received and kept in department ACQ_DEPT with work order

except AlmaAPIError as e:
    print(f"Error: {e}")
```

---

## User Operations

### Get User by ID

```python
from almaapitk import AlmaAPIClient, Users, AlmaAPIError, AlmaValidationError

client = AlmaAPIClient('SANDBOX')
users = Users(client)

# Get user by primary ID
try:
    response = users.get_user("123456789")
    user_data = response.json()

    print(f"User ID: {user_data.get('primary_id')}")
    print(f"Name: {user_data.get('first_name')} {user_data.get('last_name')}")
    print(f"Status: {user_data.get('status', {}).get('value')}")
    print(f"Expiry Date: {user_data.get('expiry_date')}")
    # Output:
    # User ID: 123456789
    # Name: John Smith
    # Status: ACTIVE
    # Expiry Date: 2025-12-31Z

except AlmaValidationError as e:
    print(f"Validation error: {e}")
except AlmaAPIError as e:
    if e.status_code == 404:
        print("User not found")
    else:
        print(f"API error: {e}")

# Get user with expanded information
response = users.get_user("123456789", expand="loans,requests,fees")
user_data = response.json()
print(f"Active loans: {len(user_data.get('loans', {}).get('loan', []))}")
```

### Update User Email

```python
from almaapitk import AlmaAPIClient, Users, AlmaAPIError

client = AlmaAPIClient('SANDBOX')
users = Users(client)

# Update a user's email address
try:
    response = users.update_user_email(
        user_id="123456789",
        new_email="john.smith@newemail.edu",
        email_type="personal"  # Type: personal, work, school, etc.
    )
    print(f"Email updated successfully")
    # Output: Updated email for user 123456789 to john.smith@newemail.edu

except AlmaValidationError as e:
    print(f"Invalid email format: {e}")
except AlmaAPIError as e:
    print(f"Failed to update email: {e}")

# Extract and analyze user emails
response = users.get_user("123456789")
user_data = response.json()

emails = users.extract_user_emails(user_data)
for email in emails:
    print(f"  {email['address']} ({email['type']}) - Preferred: {email['preferred']}")
# Output:
#   john.smith@university.edu (personal) - Preferred: True
#   j.smith@work.com (work) - Preferred: False
```

### Batch Process Users

```python
from almaapitk import AlmaAPIClient, Users, AlmaAPIError

client = AlmaAPIClient('SANDBOX')
users = Users(client)

# Process multiple users from a set
user_ids = ['222333444', '987654321', '333444555']

# Check which users qualify for email update (expired 2+ years)
results = users.process_users_batch(user_ids, years_threshold=2)

# Analyze results
qualified_users = [r for r in results if r['qualifies_for_update']]
print(f"Qualified for email update: {len(qualified_users)}/{len(user_ids)}")

for result in results:
    if result['success']:
        print(f"User {result['user_id']}: expired {result['years_expired']} years")
        print(f"  Qualifies: {result['qualifies_for_update']}")
        print(f"  Emails: {len(result['emails'])}")
    else:
        print(f"User {result['user_id']}: Error - {result['error']}")

# Output:
# Qualified for email update: 2/3
# User 222333444: expired 3 years
#   Qualifies: True
#   Emails: 1
# ...

# Bulk email update (with dry run first!)
if qualified_users:
    # Generate new emails
    email_updates = []
    for result in qualified_users:
        new_email = users.generate_new_email(
            result['user_data'],
            "expired-{user_id}@institution.edu"
        )
        email_updates.append({
            'user_id': result['user_id'],
            'new_email': new_email
        })

    # DRY RUN first - validates without making changes
    dry_run_results = users.bulk_update_emails(email_updates, dry_run=True)
    successful_dry_run = sum(1 for r in dry_run_results if r['success'])
    print(f"Dry run: {successful_dry_run}/{len(email_updates)} would succeed")

    # If dry run looks good, perform actual update
    # live_results = users.bulk_update_emails(email_updates, dry_run=False)
```

---

## Bibliographic Records

### Get Bib Record

```python
from almaapitk import AlmaAPIClient, BibliographicRecords, AlmaAPIError, AlmaValidationError

client = AlmaAPIClient('SANDBOX')
bibs = BibliographicRecords(client)

# Get a bibliographic record by MMS ID
try:
    response = bibs.get_record("991234567890123456")
    bib_data = response.json()

    print(f"MMS ID: {bib_data.get('mms_id')}")
    print(f"Title: {bib_data.get('title')}")
    print(f"Author: {bib_data.get('author')}")
    # Output:
    # MMS ID: 991234567890123456
    # Title: Introduction to Library Science
    # Author: Smith, John

except AlmaValidationError as e:
    print(f"Invalid MMS ID: {e}")
except AlmaAPIError as e:
    print(f"Failed to retrieve record: {e}")

# Get record with availability information
response = bibs.get_record(
    mms_id="991234567890123456",
    view="full",
    expand="p_avail,e_avail,d_avail"  # physical, electronic, digital availability
)
bib_data = response.json()

# Search for bibliographic records
search_response = bibs.search_records(
    q="title~Harry Potter",
    limit=10,
    order_by="mms_id",
    direction="asc"
)
results = search_response.json()
print(f"Found {results.get('total_record_count')} records")
```

### Get Holdings and Items

```python
from almaapitk import AlmaAPIClient, BibliographicRecords, AlmaAPIError

client = AlmaAPIClient('SANDBOX')
bibs = BibliographicRecords(client)

mms_id = "991234567890123456"

# Get all holdings for a bib record
holdings_response = bibs.get_holdings(mms_id)
holdings_data = holdings_response.json()

holdings_list = holdings_data.get('holding', [])
print(f"Found {len(holdings_list)} holdings")

for holding in holdings_list:
    holding_id = holding.get('holding_id')
    library = holding.get('library', {}).get('value')
    location = holding.get('location', {}).get('value')
    print(f"  Holding {holding_id}: {library} / {location}")

    # Get items for this holding
    items_response = bibs.get_items(mms_id, holding_id)
    items_data = items_response.json()
    items_list = items_data.get('item', [])

    for item in items_list:
        barcode = item.get('item_data', {}).get('barcode')
        status = item.get('item_data', {}).get('base_status', {}).get('value')
        print(f"    Item {barcode}: {status}")
# Output:
# Found 2 holdings
#   Holding 22123456789: MAIN / STACKS
#     Item 12345678901: ITEM_IN_PLACE
#     Item 12345678902: ITEM_ON_LOAN
#   Holding 22123456790: BRANCH / RESERVE
#     Item 12345678903: ITEM_IN_PLACE

# Get a specific holding
specific_holding = bibs.get_holdings(mms_id, holding_id="22123456789")

# Get MARC subfield values
values = bibs.get_marc_subfield(mms_id, field="245", subfield="a")
print(f"Title from 245$a: {values[0] if values else 'Not found'}")
```

### Scan-In Operations

```python
from almaapitk import AlmaAPIClient, BibliographicRecords, AlmaAPIError

client = AlmaAPIClient('SANDBOX')
bibs = BibliographicRecords(client)

# Scan in an item to a department with work order
try:
    response = bibs.scan_in_item(
        mms_id="99123456789",
        holding_id="22123456789",
        item_pid="23123456789",
        library="MAIN",
        department="ACQ_DEPT",
        work_order_type="AcqWorkOrder",
        status="CopyCataloging",
        done=False  # Keep item in department
    )

    if response.success:
        print("Item scanned in successfully")
        item_data = response.json()
        print(f"Process type: {item_data.get('process_type', {}).get('value')}")
        # Output: Process type: Work Order

except AlmaAPIError as e:
    print(f"Scan-in failed: {e}")

# Complete work order (move item to next step)
try:
    response = bibs.scan_in_item(
        mms_id="99123456789",
        holding_id="22123456789",
        item_pid="23123456789",
        library="MAIN",
        department="ACQ_DEPT",
        done=True  # Complete the work order
    )
    print("Work order completed")

except AlmaAPIError as e:
    print(f"Failed to complete work order: {e}")
```

---

## Resource Sharing

### Create Lending Request

```python
from almaapitk import AlmaAPIClient, ResourceSharing, AlmaAPIError

client = AlmaAPIClient('SANDBOX')
rs = ResourceSharing(client)

# Create a basic lending request
try:
    request = rs.create_lending_request(
        partner_code="PARTNER_01",
        external_id="EXT-2025-001",
        owner="MAIN",  # Resource sharing library code (plain string)
        format_type="PHYSICAL",
        title="Introduction to Library Science",
        citation_type="BOOK",
        author="Smith, John",
        isbn="978-0-123456-78-9",
        publisher="Academic Press",
        year="2024"
    )

    print(f"Request created: {request['request_id']}")
    print(f"Status: {request['status']['value']}")
    # Output:
    # Request created: 12345678
    # Status: REQUEST_CREATED_LEN

except ValueError as e:
    print(f"Validation error: {e}")
except AlmaAPIError as e:
    print(f"API error: {e}")

# Create request for digital delivery
try:
    request = rs.create_lending_request(
        partner_code="PARTNER_02",
        external_id="EXT-2025-002",
        owner="MAIN",
        format_type="DIGITAL",
        title="Research Methods in Library Science",
        citation_type="JOURNAL",
        volume="45",
        issue="3",
        pages="125-140",
        level_of_service="Rush"  # Optional: will be wrapped as {"value": "Rush"}
    )
    print(f"Digital request created: {request['request_id']}")

except AlmaAPIError as e:
    print(f"Error: {e}")

# Retrieve an existing request
request = rs.get_lending_request(
    partner_code="PARTNER_01",
    request_id="12345678"
)

# Get summary of request
summary = rs.get_request_summary(request)
print(f"Title: {summary['title']}")
print(f"Status: {summary['status']}")
print(f"Format: {summary['format']}")
```

### Create Request with Citation Metadata

```python
from almaapitk import AlmaAPIClient, ResourceSharing, AlmaAPIError
from almaapitk.utils.citation_metadata import CitationMetadataError

client = AlmaAPIClient('SANDBOX')
rs = ResourceSharing(client)

# Create lending request with PubMed metadata auto-population
try:
    request = rs.create_lending_request_from_citation(
        partner_code="RELAIS",
        external_id="ILL-2025-001",
        owner="MAIN",
        format_type="DIGITAL",
        pmid="33219451",
        source_type='pmid'  # Explicit source type (recommended)
    )

    print(f"Request created from PubMed citation")
    print(f"Title: {request.get('title')}")
    print(f"Journal: {request.get('journal_title')}")
    print(f"DOI: {request.get('doi')}")
    # Output:
    # Request created from PubMed citation
    # Title: COVID-19 vaccine acceptance among healthcare workers
    # Journal: Nature Medicine
    # DOI: 10.1038/s41591-020-1124-9

except CitationMetadataError as e:
    print(f"Failed to fetch citation metadata: {e}")
except AlmaAPIError as e:
    print(f"API error: {e}")

# Create request with DOI metadata
try:
    request = rs.create_lending_request_from_citation(
        partner_code="RELAIS",
        external_id="ILL-2025-002",
        owner="MAIN",
        format_type="DIGITAL",
        doi="10.1038/s41591-020-1124-9",
        source_type='doi'
    )
    print(f"Request created from DOI")

except (CitationMetadataError, AlmaAPIError) as e:
    print(f"Error: {e}")

# Override auto-populated fields
try:
    request = rs.create_lending_request_from_citation(
        partner_code="RELAIS",
        external_id="ILL-2025-003",
        owner="MAIN",
        format_type="PHYSICAL",
        doi="10.1038/s41591-020-1124-9",
        source_type='doi',
        # Override auto-fetched values
        title="Custom Title Override",
        pages="10-25"
    )
    print(f"Request created with overridden fields")

except (CitationMetadataError, AlmaAPIError) as e:
    print(f"Error: {e}")
```

---

## Admin Operations

### Work with Sets (BIB_MMS, USER)

```python
from almaapitk import AlmaAPIClient, Admin, AlmaAPIError, AlmaValidationError

client = AlmaAPIClient('SANDBOX')
admin = Admin(client)

# Test connection to admin API
if admin.test_connection():
    print("Admin API connection successful")

# Get information about a set
try:
    set_info = admin.get_set_info("25793308630004146")

    print(f"Set Name: {set_info['name']}")
    print(f"Content Type: {set_info['content_type']}")  # BIB_MMS or USER
    print(f"Total Members: {set_info['total_members']}")
    print(f"Status: {set_info['status']}")
    # Output:
    # Set Name: Books 2024
    # Content Type: BIB_MMS
    # Total Members: 1500
    # Status: ACTIVE

except AlmaAPIError as e:
    print(f"Error: {e}")

# Validate a USER set (ensures set exists and is correct type)
try:
    user_set_info = admin.validate_user_set("25793308630004146")
    print(f"Valid USER set: {user_set_info['name']} ({user_set_info['total_members']} members)")

except AlmaValidationError as e:
    print(f"Set validation failed: {e}")

# Get detailed metadata with processing estimates
metadata = admin.get_set_metadata_and_member_count("25793308630004146")
print(f"Estimated processing time: {metadata['member_info']['estimated_processing_time_minutes']} minutes")
print(f"Pages required: {metadata['member_info']['pages_required']}")

if metadata['processing_warnings']:
    print("Warnings:")
    for warning in metadata['processing_warnings']:
        print(f"  - {warning}")

# List all sets
response = admin.list_sets(limit=10, content_type="USER")
sets_data = response.json()
print(f"Found {sets_data.get('total_record_count', 0)} USER sets")

# List sets with member counts (requires additional API calls)
response = admin.list_sets(limit=10, content_type="BIB_MMS", include_member_counts=True)
```

### Process Set Members

```python
from almaapitk import AlmaAPIClient, Admin, Users, AlmaAPIError

client = AlmaAPIClient('SANDBOX')
admin = Admin(client)
users = Users(client)

set_id = "25793308630004146"

# Get all member IDs from a set (handles pagination automatically)
try:
    # Auto-detect set type
    member_ids = admin.get_set_members(set_id)
    print(f"Retrieved {len(member_ids)} members")

    # Or specify expected type for validation
    user_ids = admin.get_user_set_members(set_id)  # Validates it's a USER set
    bib_ids = admin.get_bib_set_members(set_id)    # Validates it's a BIB_MMS set

except AlmaValidationError as e:
    print(f"Set type validation failed: {e}")
except AlmaAPIError as e:
    print(f"Failed to retrieve set members: {e}")

# Process USER set members
try:
    user_ids = admin.get_user_set_members(set_id)

    print(f"Processing {len(user_ids)} users from set...")

    # Process each user
    for user_id in user_ids[:10]:  # Process first 10 as example
        try:
            response = users.get_user(user_id)
            user_data = response.json()

            # Check expiry status
            is_expired, years = users.is_user_expired_years(user_data, years_threshold=2)

            print(f"User {user_id}: expired={is_expired}, years={years}")

        except AlmaAPIError as e:
            print(f"Error processing user {user_id}: {e}")

except AlmaAPIError as e:
    print(f"Failed to process set: {e}")

# Process BIB_MMS set members
from almaapitk import BibliographicRecords

bibs = BibliographicRecords(client)

try:
    mms_ids = admin.get_bib_set_members(set_id)

    print(f"Processing {len(mms_ids)} bibliographic records...")

    for mms_id in mms_ids[:5]:  # Process first 5 as example
        try:
            response = bibs.get_record(mms_id)
            bib_data = response.json()
            print(f"Record {mms_id}: {bib_data.get('title', 'No title')[:50]}")

        except AlmaAPIError as e:
            print(f"Error processing record {mms_id}: {e}")

except AlmaAPIError as e:
    print(f"Failed to process set: {e}")
```

---

## Error Handling Best Practices

```python
from almaapitk import (
    AlmaAPIClient,
    AlmaAPIError,
    AlmaValidationError,
    Acquisitions,
    Users
)

client = AlmaAPIClient('SANDBOX')

def safe_operation():
    """Example of comprehensive error handling."""
    try:
        # Your API operations here
        acq = Acquisitions(client)
        invoice = acq.get_invoice("123456")
        return invoice

    except AlmaValidationError as e:
        # Client-side validation errors (invalid parameters)
        print(f"Validation failed: {e}")
        # Log and handle - usually a programming error
        raise

    except AlmaAPIError as e:
        # API errors from Alma
        if e.status_code == 404:
            print(f"Resource not found")
            return None
        elif e.status_code == 401:
            print(f"Authentication failed - check API key")
            raise
        elif e.status_code == 429:
            print(f"Rate limited - wait and retry")
            import time
            time.sleep(60)
            return safe_operation()  # Retry
        else:
            print(f"API error {e.status_code}: {e}")
            raise

    except Exception as e:
        # Unexpected errors
        print(f"Unexpected error: {e}")
        raise

# Always use dry-run mode first for bulk operations
def safe_bulk_update():
    users = Users(client)

    email_updates = [
        {"user_id": "123", "new_email": "new@email.com"},
        # ... more updates
    ]

    # Step 1: Dry run
    dry_results = users.bulk_update_emails(email_updates, dry_run=True)

    failed = [r for r in dry_results if not r['success']]
    if failed:
        print(f"Dry run found {len(failed)} errors - review before proceeding")
        for r in failed:
            print(f"  {r['user_id']}: {r['error']}")
        return

    # Step 2: Actual update (only after dry run succeeds)
    confirm = input("Proceed with live update? (yes/no): ")
    if confirm.lower() == 'yes':
        live_results = users.bulk_update_emails(email_updates, dry_run=False)
        print(f"Updated {sum(1 for r in live_results if r['success'])} users")
```

---

## Environment Setup Reference

```bash
# Required environment variables
export ALMA_SB_API_KEY='your_sandbox_api_key'
export ALMA_PROD_API_KEY='your_production_api_key'

# Install dependencies
poetry install

# Test connection
python -c "from almaapitk import AlmaAPIClient; client = AlmaAPIClient('SANDBOX'); client.test_connection()"
```

---

## Additional Resources

- **Package Documentation**: See `docs/` directory
- **Domain Method Reference**: See `CLAUDE.md` for complete method signatures
- **Test Scripts**: See `src/tests/` for additional usage examples
- **Alma API Reference**: https://developers.exlibrisgroup.com/alma/apis/
