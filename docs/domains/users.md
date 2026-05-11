# Users Domain Class Reference

## Overview

The **Users** domain class provides comprehensive operations for managing patron records in the Alma ILS (Integrated Library System). It is specifically designed for user management workflows with a focus on email operations for expired user accounts.

### What This Domain Handles

- **User Retrieval**: Fetch complete user records by primary ID or other identifiers
- **User Listing / Search**: Page through users with Alma's SRU-style query syntax
- **User CRUD**: Create new users and delete existing ones
- **User Updates**: Modify user information including contact details
- **GDPR Personal-Data Export**: Pull the per-user data-portability export
- **Email Operations**: Extract, validate, generate, and update email addresses
- **Expiry Date Analysis**: Determine user account expiration status
- **Attachments**: List, retrieve, and upload patron-record attachments
- **Fines & Fees**: List, create, pay (single / all), waive, dispute, restore
- **Deposits**: List, create, retrieve, and perform op-driven actions
- **Loans**: List, create, retrieve, renew, and update (e.g. change due date)
- **Requests**: List, create, retrieve, cancel, update, and advance holds / bookings / digitization
- **Batch Processing**: Process multiple users efficiently with rate limiting
- **Bulk Email Updates**: Update emails for multiple users with dry-run support

### When to Use This Domain

Use the `Users` domain class when you need to:

- Retrieve user information from Alma
- Update user contact information (especially email addresses)
- Process users from Alma sets for bulk operations
- Check if users have expired accounts (2+ years expired)
- Migrate or update email addresses for expired patrons
- Validate email formats before updates

### Key Concepts

| Concept | Description |
|---------|-------------|
| **User Primary ID** | Unique identifier for a user in Alma (up to 255 characters) |
| **Expiry Date** | Date when user account expires (YYYY-MM-DDZ format) |
| **Contact Info** | Nested structure containing emails, phones, addresses |
| **Email Array** | Users can have multiple emails; one marked as `preferred` |
| **User Set** | Collection of users managed via Admin domain |

---

## Initialization

### Creating a Users Instance

The Users class requires an initialized `AlmaAPIClient` instance:

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

# Initialize the API client
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'

# Create Users domain instance
users = Users(client)

# Verify connection
if users.test_connection():
    print(f"Connected to Users API ({users.get_environment()})")
else:
    print("Connection failed")
```

### Environment Setup

Ensure environment variables are configured:

```bash
# For Sandbox
export ALMA_SB_API_KEY="your_sandbox_api_key"

# For Production
export ALMA_PROD_API_KEY="your_production_api_key"
```

### Logging

The Users domain automatically configures logging with both console and file handlers:

- **Console**: INFO level and above
- **File**: DEBUG level (captures all events)
- Log files: `sb_log_file.log` (Sandbox) or `prod_log_file.log` (Production)

---

## Methods Reference

### Core User Operations

#### `get_user(user_id, expand="none")`

Retrieves a complete user record from Alma.

**Signature:**
```python
def get_user(self, user_id: str, expand: str = "none") -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier (primary ID, barcode, etc.) |
| `expand` | str | No | Additional data to include: "loans", "requests", "fees", or "none" (default) |

**Returns:** `AlmaResponse` containing user data

**Raises:**
- `AlmaValidationError`: If `user_id` is empty
- `AlmaAPIError`: If API request fails (e.g., 404 if user not found)

**Example:**
```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

client = AlmaAPIClient('SANDBOX')
users = Users(client)

# Get basic user info
response = users.get_user("123456789")
user_data = response.json()

print(f"Name: {user_data['first_name']} {user_data['last_name']}")
print(f"Primary ID: {user_data['primary_id']}")
print(f"Expiry Date: {user_data.get('expiry_date', 'Not set')}")

# Get user with loan information
response = users.get_user("123456789", expand="loans")
user_data = response.json()
```

**Common Errors:**

| Error Code | Meaning | Solution |
|------------|---------|----------|
| 401861 | User not found | Verify user ID exists in Alma |
| 401 | Unauthorized | Check API key configuration |

---

#### `update_user(user_id, user_data)`

Updates a user record in Alma.

**Signature:**
```python
def update_user(self, user_id: str, user_data: Dict[str, Any]) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `user_data` | dict | Yes | Complete user data object to update |

**Returns:** `AlmaResponse` containing updated user data

**Raises:**
- `AlmaValidationError`: If `user_id` is empty or `user_data` is invalid
- `AlmaAPIError`: If API request fails

**Example:**
```python
# First, get the current user data
response = users.get_user("123456789")
user_data = response.json()

# Modify the data
user_data['first_name'] = "Updated Name"

# Update the user
response = users.update_user("123456789", user_data)

if response.success:
    print("User updated successfully")
```

**Important Note:** You must send the complete user object when updating. Partial updates are not supported by the Alma API.

---

#### `test_connection()`

Tests if the Users API endpoints are accessible.

**Signature:**
```python
def test_connection(self) -> bool
```

**Returns:** `True` if connection successful, `False` otherwise

**Example:**
```python
users = Users(client)

if users.test_connection():
    print("Users API is accessible")
else:
    print("Cannot connect to Users API")
```

---

#### `get_environment()`

Gets the current environment from the client.

**Signature:**
```python
def get_environment(self) -> str
```

**Returns:** Environment string ("SANDBOX" or "PRODUCTION")

**Example:**
```python
env = users.get_environment()
print(f"Currently using: {env}")
```

---

### User Listing and Search

These methods cover the `GET /almaws/v1/users` endpoint and the GDPR personal-data export.

#### `list_users(limit=10, offset=0, q=None, order_by=None, expand=None, source_user_id=None, source_institution_code=None)`

Lists / searches users with optional filters.

**Signature:**
```python
def list_users(
    self,
    limit: int = 10,
    offset: int = 0,
    q: Optional[str] = None,
    order_by: Optional[str] = None,
    expand: Optional[str] = None,
    source_user_id: Optional[str] = None,
    source_institution_code: Optional[str] = None,
) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | No | Max records per page (Alma caps at 100). Default 10. |
| `offset` | int | No | Zero-based offset. Default 0. |
| `q` | str | No | Alma SRU-style query, e.g. `last_name~Smith` |
| `order_by` | str | No | Sort field (e.g. `last_name`) |
| `expand` | str | No | Additional data (e.g. `loans,requests`) |
| `source_user_id` | str | No | Fulfillment-network source user id filter |
| `source_institution_code` | str | No | Fulfillment-network source institution filter |

**Returns:** List of user dicts (envelope unwrapped from `{"user": [...], "total_record_count": N}`). Empty list when no users match.

**Raises:** `AlmaAPIError` on API failure.

**Example:**
```python
recent_staff = users.list_users(
    q="user_group~STAFF",
    order_by="last_name",
    limit=50,
)
for u in recent_staff:
    print(u.get("primary_id"), u.get("last_name"))
```

---

#### `search_users(q, limit=10, offset=0, **kwargs)`

Thin convenience wrapper around `list_users` that requires a non-empty query string.

**Signature:**
```python
def search_users(
    self,
    q: str,
    limit: int = 10,
    offset: int = 0,
    **kwargs: Any,
) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | str | Yes | Alma query string. Empty / non-string raises `AlmaValidationError`. |
| `limit` | int | No | Max records per page. Default 10. |
| `offset` | int | No | Zero-based offset. Default 0. |
| `**kwargs` | — | No | Forwarded to `list_users` (`order_by`, `expand`, etc.) |

**Returns:** List of user dicts matching the query.

**Raises:**
- `AlmaValidationError`: If `q` is empty or not a string
- `AlmaAPIError`: On API failure

**Example:**
```python
hits = users.search_users("primary_id~<user_primary_id>", limit=10)
print(f"Found {len(hits)} matching users")
```

---

#### `get_user_personal_data(user_id)`

Fetches the GDPR data-portability export for a single user. The response body is sensitive and is **never logged** — only the user id and top-level key count reach the audit trail.

**Signature:**
```python
def get_user_personal_data(self, user_id: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |

**Returns:** Raw personal-data export dict from Alma.

**Raises:**
- `AlmaValidationError`: Empty / non-string `user_id`
- `AlmaAPIError`: On API failure (404 / 401890 when user does not exist)

**Example:**
```python
export = users.get_user_personal_data("<user_primary_id>")
# Write to a controlled-access location; do NOT log or commit
```

---

### User CRUD

The full lifecycle for user records — create new accounts and delete existing ones.

#### `create_user(user_data)`

Creates a new Alma user. The body is passed through verbatim; the client validates only the four core fields Alma requires (`primary_id`, `account_type`, `status`, `user_group`). The three code-table fields accept either a bare string (`"INTERNAL"`) or the canonical `{"value": "INTERNAL"}` wrapper Alma returns on reads — both round-trip cleanly.

**Signature:**
```python
def create_user(self, user_data: Dict[str, Any]) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_data` | dict | Yes | Non-empty user payload with the four required fields below. |

**Required keys in `user_data`:**

| Key | Accepted forms |
|-----|----------------|
| `primary_id` | non-empty string |
| `account_type` | `"INTERNAL"` or `{"value": "INTERNAL"}` |
| `status` | `"ACTIVE"` or `{"value": "ACTIVE"}` |
| `user_group` | `"STAFF"` or `{"value": "STAFF"}` |

**Returns:** `AlmaResponse`; created user's id at `response.data["primary_id"]`.

**Raises:**
- `AlmaValidationError`: Missing / empty required field
- `AlmaAPIError`: On API failure (typed subclass when applicable)

**Example:**
```python
response = users.create_user({
    "primary_id": "<user_primary_id>",
    "account_type": {"value": "INTERNAL"},
    "status": {"value": "ACTIVE"},
    "user_group": {"value": "STAFF"},
    "first_name": "Ada",
    "last_name": "Lovelace",
})
created_primary_id = response.data["primary_id"]
```

---

#### `delete_user(user_id)`

Deletes a user by primary id. Alma rejects the delete when the user has active loans, requests, or unpaid fees — those rejections surface as `AlmaAPIError` with the Alma error code intact.

**Signature:**
```python
def delete_user(self, user_id: str) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User primary id (or any Alma-accepted id type) |

**Returns:** `AlmaResponse`.

**Important — response body:** Alma returns **204 No Content** on a successful delete. There is no body to inspect. If you need an audit snapshot of the user record, call `get_user(user_id)` **before** deleting and persist that payload yourself.

**Raises:**
- `AlmaValidationError`: Empty / non-string `user_id`
- `AlmaAPIError`: On API failure — `alma_code` and `tracking_id` are populated for active-loans / outstanding-fee rejections, so callers can branch on them.

**Example:**
```python
# Snapshot first for the audit trail
audit_snapshot = users.get_user("<user_primary_id>").json()
audit_log_write(audit_snapshot)

# Then delete
users.delete_user("<user_primary_id>")
```

---

### User Attachments

Attachments live under `/almaws/v1/users/{user_id}/attachments`. Alma exposes list, get, and upload — there is **no documented DELETE** for user attachments. Upload uses a JSON body with the file's base64-encoded contents (NOT multipart). File bytes and the base64 payload are never logged.

#### `list_user_attachments(user_id)`

Lists every attachment on a user record.

**Signature:**
```python
def list_user_attachments(self, user_id: str) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |

**Returns:** List of attachment dicts (envelope unwrapped from `user_attachment`, with a defensive fall-back to `attachment`).

**Raises:**
- `AlmaValidationError`: Empty `user_id`
- `AlmaAPIError`: On API failure

**Example:**
```python
attachments = users.list_user_attachments("<user_primary_id>")
for att in attachments:
    print(att["id"], att.get("file_name"), att.get("type"))
```

---

#### `get_user_attachment(user_id, attachment_id, expand=None)`

Retrieves one attachment's metadata (or, with `expand="content"`, its base64-encoded contents inline).

**Signature:**
```python
def get_user_attachment(
    self,
    user_id: str,
    attachment_id: str,
    expand: Optional[str] = None,
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `attachment_id` | str | Yes | Attachment id (key `id` from `list_user_attachments`) |
| `expand` | str | No | `"content"` returns base64-encoded bytes inline; `"content_no_encoding"` returns raw bytes; `None` (default) is metadata-only. |

**Returns:** Attachment dict from Alma. Callers that request `expand="content"` must base64-decode `result["content"]` themselves.

**Raises:**
- `AlmaValidationError`: Empty user id / attachment id
- `AlmaAPIError`: On API failure (404 if user / attachment missing)

**Example:**
```python
import base64

meta = users.get_user_attachment(
    "<user_primary_id>",
    "<attachment_id>",
    expand="content",
)
file_bytes = base64.b64decode(meta["content"])
Path(meta["file_name"]).write_bytes(file_bytes)
```

---

#### `upload_user_attachment(user_id, file_path, attachment_data=None)`

Uploads a file as a new attachment. The body shape verified on live SANDBOX (2026-05-08) is:

```json
{
  "type": "GENERAL",
  "note": "<description>",
  "file_name": "<filename>",
  "content": "<base64-encoded file bytes>"
}
```

**Gotcha:** `type` is a **plain string**, not the `{"value": "GENERAL"}` wrapper used elsewhere in Alma. Wrapping it triggers a 400 — "Cannot deserialize value of type java.lang.String from Object value".

**Signature:**
```python
def upload_user_attachment(
    self,
    user_id: str,
    file_path: str,
    attachment_data: Optional[Dict[str, Any]] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `file_path` | str | Yes | Path to an existing file on disk |
| `attachment_data` | dict | No | Body overrides (e.g. `{"note": "..."}`). Shallow-copied; `type` defaults to `"GENERAL"`, `file_name` defaults to the file basename, and `content` is always overridden with the freshly-read base64 payload. |

**Returns:** `AlmaResponse`; created attachment id at `response.data["id"]`.

**Raises:**
- `AlmaValidationError`: Empty user id / file path; file path does not exist
- `AlmaAPIError`: On API failure

**Example:**
```python
response = users.upload_user_attachment(
    "<user_primary_id>",
    "/tmp/student-id-card.pdf",
    attachment_data={"note": "Renewed photo ID 2026"},
)
print("Attachment id:", response.data["id"])
```

---

### User Fines & Fees

Five op-driven operations on a single fee plus list, create, and pay-all helpers. Op-driven endpoints follow Alma's documented convention: `op`, `amount`, `method`, `reason`, `comment`, etc. travel as **query parameters**, not in the request body.

#### `list_user_fees(user_id, status=None)`

Lists a user's fines and fees. By default Alma returns `ACTIVE` fees; supply `status` to override.

**Signature:**
```python
def list_user_fees(
    self,
    user_id: str,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `status` | str | No | Filter by status (`"ACTIVE"`, `"INDISPUTE"`, `"CLOSED"`) |

**Returns:** List of fee dicts (envelope unwrapped from `fee`).

**Raises:** `AlmaValidationError` (empty `user_id`); `AlmaAPIError` on API failure.

**Example:**
```python
active_fees = users.list_user_fees("<user_primary_id>")
total_balance = sum(float(f.get("balance", 0)) for f in active_fees)
```

---

#### `create_user_fee(user_id, fee_data)`

Creates a new fee on a user record. `fee_data` is passed through verbatim — supply the Alma-required fields yourself (`type`, `original_amount`, `owner`, etc.).

**Signature:**
```python
def create_user_fee(
    self,
    user_id: str,
    fee_data: Dict[str, Any],
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `fee_data` | dict | Yes | Non-empty fee body |

**Returns:** `AlmaResponse`; created fee id at `response.data["id"]`.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

**Example:**
```python
response = users.create_user_fee("<user_primary_id>", {
    "type": {"value": "REPLACEMENT"},
    "original_amount": "25.00",
    "balance": "25.00",
    "owner": {"value": "<library_code>"},
    "comment": "Lost item replacement",
})
fee_id = response.data["id"]
```

---

#### `get_user_fee(user_id, fee_id)`

Retrieves a single fee's details.

**Signature:**
```python
def get_user_fee(self, user_id: str, fee_id: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `fee_id` | str | Yes | Fee identifier |

**Returns:** Fee dict from Alma.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

#### `pay_all_user_fees(user_id, amount="ALL", method="CASH", external_transaction_id=None)`

Pays all outstanding fees in one operation.

**Signature:**
```python
def pay_all_user_fees(
    self,
    user_id: str,
    amount: str = "ALL",
    method: str = "CASH",
    external_transaction_id: Optional[str] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `amount` | str | No | `"ALL"` (sentinel; default) or a numeric string like `"12.50"` |
| `method` | str | No | `"CASH"` (default), `"CREDIT"`, `"CHECK"`, `"ONLINE"`, `"WIRE"` |
| `external_transaction_id` | str | No | Payment-gateway transaction id |

**Note:** `amount` is a **string** (`"ALL"` sentinel or numeric string). Numeric values are validated client-side; non-conforming values raise `AlmaValidationError` before any HTTP call.

**Returns:** `AlmaResponse`.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

**Example:**
```python
users.pay_all_user_fees(
    "<user_primary_id>",
    amount="ALL",
    method="ONLINE",
    external_transaction_id="GW-2026-00001",
)
```

---

#### `pay_user_fee(user_id, fee_id, amount, method="CASH", external_transaction_id=None)`

Pays (in full or in part) a single fee.

**Signature:**
```python
def pay_user_fee(
    self,
    user_id: str,
    fee_id: str,
    amount: str,
    method: str = "CASH",
    external_transaction_id: Optional[str] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `fee_id` | str | Yes | Fee identifier |
| `amount` | str | Yes | `"ALL"` or a numeric string |
| `method` | str | No | Payment method. Default `"CASH"`. |
| `external_transaction_id` | str | No | Optional gateway transaction id |

**Returns:** `AlmaResponse`.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

#### `waive_user_fee(user_id, fee_id, reason, amount=None, comment=None)`

Waives (in full or in part) a single fee.

**Signature:**
```python
def waive_user_fee(
    self,
    user_id: str,
    fee_id: str,
    reason: str,
    amount: Optional[str] = None,
    comment: Optional[str] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `fee_id` | str | Yes | Fee identifier |
| `reason` | str | **Yes** | Waiver reason. Required by Alma's `op=waive` endpoint. |
| `amount` | str | No | Partial-waive amount as a string. `None` waives the full balance. |
| `comment` | str | No | Free-text comment |

**Audit fix:** Only `waive` requires `reason`. `method` is NOT sent on waive — only on pay / pay_all.

**Returns:** `AlmaResponse`.

**Raises:** `AlmaValidationError` (any missing required field), `AlmaAPIError`.

---

#### `dispute_user_fee(user_id, fee_id, reason=None, comment=None)`

Marks a single fee as disputed.

**Signature:**
```python
def dispute_user_fee(
    self,
    user_id: str,
    fee_id: str,
    reason: Optional[str] = None,
    comment: Optional[str] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `fee_id` | str | Yes | Fee identifier |
| `reason` | str | No | **Optional** (audit-corrected — was previously documented as required). Forwarded only when non-empty. |
| `comment` | str | No | Free-text comment |

**Returns:** `AlmaResponse`.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

#### `restore_user_fee(user_id, fee_id, comment=None)`

Restores a previously-disputed fee to active status. Only `op` and (optionally) `comment` are sent — no reason, amount, or method.

**Signature:**
```python
def restore_user_fee(
    self,
    user_id: str,
    fee_id: str,
    comment: Optional[str] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `fee_id` | str | Yes | Fee identifier |
| `comment` | str | No | Free-text comment |

**Returns:** `AlmaResponse`.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

### User Deposits

Endpoints under `/almaws/v1/users/{user_id}/deposits`. The wrapper exposes three reads (list, get, create) and one op-driven action endpoint. The op-action wrapper is deliberately op-agnostic — Alma documents `"pay"` / `"refund"` / `"dispute"` / `"restore"`, but invalid ops are rejected by Alma with its own error response (a future Alma release may add new ops).

#### `list_user_deposits(user_id)`

**Signature:**
```python
def list_user_deposits(self, user_id: str) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |

**Returns:** List of deposit dicts.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

#### `create_user_deposit(user_id, deposit_data)`

**Signature:**
```python
def create_user_deposit(
    self,
    user_id: str,
    deposit_data: Dict[str, Any],
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `deposit_data` | dict | Yes | Non-empty deposit body; passed through verbatim |

**Returns:** `AlmaResponse`; deposit id at `response.data["id"]`.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

#### `get_user_deposit(user_id, deposit_id)`

**Signature:**
```python
def get_user_deposit(self, user_id: str, deposit_id: str) -> Dict[str, Any]
```

**Returns:** Deposit dict.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

#### `perform_user_deposit_action(user_id, deposit_id, op)`

**Signature:**
```python
def perform_user_deposit_action(
    self,
    user_id: str,
    deposit_id: str,
    op: str,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `deposit_id` | str | Yes | Deposit identifier |
| `op` | str | Yes | Action to perform. Alma docs: `"pay"`, `"refund"`, `"dispute"`, `"restore"`. Not enumerated client-side. |

**Returns:** `AlmaResponse`.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

### User Loans

Loans live under `/almaws/v1/users/{user_id}/loans`. The wrapper covers list, create (loan an item), retrieve, renew (op-driven), and update (typically due-date change).

#### `list_user_loans(user_id, limit=10, offset=0, expand=None, order_by=None)`

Lists a user's active loans.

**Signature:**
```python
def list_user_loans(
    self,
    user_id: str,
    limit: int = 10,
    offset: int = 0,
    expand: Optional[str] = None,
    order_by: Optional[str] = None,
) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `limit` | int | No | Page size (0–100). Default 10. |
| `offset` | int | No | Page offset. Default 0. |
| `expand` | str | No | E.g. `"renewable"` |
| `order_by` | str | No | `"due_date"`, `"loan_date"`, `"barcode"`, `"title"` |

**Returns:** List of loan dicts (envelope unwrapped from `item_loan`).

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

**Example:**
```python
overdue = users.list_user_loans(
    "<user_primary_id>",
    expand="renewable",
    order_by="due_date",
    limit=100,
)
```

---

#### `create_user_loan(user_id, item_barcode=None, item_pid=None, user_id_type=None, loan_data=None)`

Loans an item to a user. **Important gotcha — query/body split:** per the Alma OpenAPI spec, `item_barcode`, `item_pid`, and `user_id_type` are **query parameters**, while `circ_desk` / `library` and any other loan-object fields live in the JSON request **body**. The wrapper enforces "exactly one of `item_barcode` or `item_pid`".

Inside the body, `circ_desk` and `library` follow Alma's canonical `{"value": "<code>"}` wrapper shape — passing bare strings will fail validation server-side.

**Signature:**
```python
def create_user_loan(
    self,
    user_id: str,
    item_barcode: Optional[str] = None,
    item_pid: Optional[str] = None,
    user_id_type: Optional[str] = None,
    loan_data: Optional[Dict[str, Any]] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `item_barcode` | str | One of these two | Item barcode. Forwarded as a **query** parameter. |
| `item_pid` | str | One of these two | Item PID. Forwarded as a **query** parameter. |
| `user_id_type` | str | No | E.g. `"all_unique"`, `"BARCODE"`. **Query** parameter. |
| `loan_data` | dict | No | Loan body (e.g. `{"circ_desk": {"value": "<circ_desk_code>"}, "library": {"value": "<library_code>"}}`). When `None`, Alma applies its defaults. |

**Returns:** `AlmaResponse`; loan id at `response.data["loan_id"]`.

**Raises:**
- `AlmaValidationError`: Empty `user_id`; neither or both of `item_barcode`/`item_pid` supplied; `loan_data` not a dict
- `AlmaAPIError`: On API failure

**Example:**
```python
response = users.create_user_loan(
    user_id="<user_primary_id>",
    item_barcode="<item_barcode>",
    loan_data={
        "circ_desk": {"value": "<circ_desk_code>"},
        "library": {"value": "<library_code>"},
    },
)
loan_id = response.data["loan_id"]
```

---

#### `get_user_loan(user_id, loan_id)`

Retrieves a single loan's details.

**Signature:**
```python
def get_user_loan(self, user_id: str, loan_id: str) -> Dict[str, Any]
```

**Returns:** Loan dict.

**Raises:**
- `AlmaValidationError`: Empty `user_id` / `loan_id`
- `AlmaAPIError`: On API failure (e.g. `401823` "Loan ID does not exist")

---

#### `renew_user_loan(user_id, loan_id)`

Renews a single loan (`POST .../loans/{loan_id}?op=renew`).

**Signature:**
```python
def renew_user_loan(self, user_id: str, loan_id: str) -> AlmaResponse
```

**Returns:** `AlmaResponse`; the renewed loan body includes the new `due_date`.

**Raises:**
- `AlmaValidationError`: Empty `user_id` / `loan_id`
- `AlmaAPIError`: On API failure (e.g. `401822` "Cannot renew loan", `401823` "Loan ID does not exist")

**Example:**
```python
response = users.renew_user_loan("<user_primary_id>", "<loan_id>")
print("New due date:", response.data.get("due_date"))
```

---

#### `update_user_loan(user_id, loan_id, loan_data)`

Updates a loan (typically to change the due date).

**Signature:**
```python
def update_user_loan(
    self,
    user_id: str,
    loan_id: str,
    loan_data: Dict[str, Any],
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `loan_id` | str | Yes | Loan identifier |
| `loan_data` | dict | Yes | Non-empty loan body — typically `{"due_date": "<ISO-8601>"}` |

**Returns:** `AlmaResponse` (the updated loan body).

**Raises:**
- `AlmaValidationError`: Empty ids; `loan_data` empty / not a dict
- `AlmaAPIError`: On API failure (e.g. `401824` "Due date is not in loan object", `401681` "Due date cannot be in the past")

---

### User Requests

Endpoints under `/almaws/v1/users/{user_id}/requests` cover HOLD, BOOKING, and DIGITIZATION requests. Pickup rules and the request types a tenant accepts vary per institution — **HOLD on an unavailable item is the only common test scenario**.

#### `list_user_requests(user_id, request_type=None, status=None, limit=10, offset=0)`

Lists a user's requests.

**Signature:**
```python
def list_user_requests(
    self,
    user_id: str,
    request_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `request_type` | str | No | `"HOLD"`, `"DIGITIZATION"`, `"BOOKING"` |
| `status` | str | No | `"active"` (default) or `"history"` (only available when tenant `should_anonymize_requests` is `false` at completion time) |
| `limit` | int | No | Page size (0–100). Default 10. |
| `offset` | int | No | Page offset. Default 0. |

**Returns:** List of request dicts (envelope unwrapped from `user_request`).

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

#### `create_user_request(user_id, request_data, mms_id=None, item_pid=None, holding_id=None, user_id_type=None)`

Creates a request for a user. **Important gotcha — query/body split:** the resource identifiers (`mms_id`, `item_pid`, `holding_id`, `user_id_type`) are **query parameters**, while `request_type`, `pickup_location_*`, and other request-object fields live in the JSON **body**.

At least one of `mms_id` / `item_pid` / `holding_id` must be supplied. The wrapper accepts **`mms_id` OR `item_pid`** as the common resource identifier; `holding_id` is forwarded too for institutions that rely on it. (Only `mms_id` and `item_pid` are documented in the public swagger; `holding_id` is forwarded transparently for institution-specific handling.)

**Signature:**
```python
def create_user_request(
    self,
    user_id: str,
    request_data: Dict[str, Any],
    mms_id: Optional[str] = None,
    item_pid: Optional[str] = None,
    holding_id: Optional[str] = None,
    user_id_type: Optional[str] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `request_data` | dict | Yes | Non-empty request body (e.g. `{"request_type": "HOLD", "pickup_location_type": "LIBRARY", "pickup_location_library": "<library_code>"}`) |
| `mms_id` | str | One of these three | Title MMS id. **Query** parameter. |
| `item_pid` | str | One of these three | Item PID. **Query** parameter. |
| `holding_id` | str | One of these three | Holding id. **Query** parameter (transparent forward). |
| `user_id_type` | str | No | E.g. `"all_unique"`. **Query** parameter. |

**Returns:** `AlmaResponse`; new `request_id` at `response.data["request_id"]`.

**Raises:**
- `AlmaValidationError`: Empty `user_id`; empty `request_data`; none of `mms_id`/`item_pid`/`holding_id` supplied
- `AlmaAPIError`: On API failure (e.g. `401129` "No items can fulfill the submitted request", `401694` pickup-location-related errors)

**Example — title-level HOLD on an unavailable item:**
```python
response = users.create_user_request(
    user_id="<user_primary_id>",
    request_data={
        "request_type": "HOLD",
        "pickup_location_type": "LIBRARY",
        "pickup_location_library": "<library_code>",
    },
    mms_id="<mms_id>",
)
request_id = response.data["request_id"]
```

---

#### `get_user_request(user_id, request_id)`

Retrieves a single request's details.

**Signature:**
```python
def get_user_request(self, user_id: str, request_id: str) -> Dict[str, Any]
```

**Returns:** Request dict.

**Raises:** `AlmaValidationError`, `AlmaAPIError`.

---

#### `cancel_user_request(user_id, request_id, reason, note=None)`

Cancels a single request (`DELETE .../requests/{request_id}?reason=...`). Returns 204 No Content on success — `response.data` will typically be empty.

**Important — `reason` is required:** the audit (2026-05-08) corrected the original "optional reason" bug. Alma's cancel-request endpoint rejects DELETE without a `reason` query parameter. The wrapper raises `AlmaValidationError` before issuing the HTTP call when `reason` is empty / whitespace / non-string. Valid values come from the `RequestCancellationReasons` code table — common entries include `"PatronRequest"` (patron asked to cancel) and `"LibraryCancelled"`.

**Signature:**
```python
def cancel_user_request(
    self,
    user_id: str,
    request_id: str,
    reason: str,
    note: Optional[str] = None,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `request_id` | str | Yes | Request identifier |
| `reason` | str | **Yes** | Non-empty cancellation reason code (from `RequestCancellationReasons`) |
| `note` | str | No | Optional free-text note |

**Returns:** `AlmaResponse` (empty body on 204).

**Raises:**
- `AlmaValidationError`: Any missing required field, including empty / whitespace `reason`
- `AlmaAPIError`: On API failure (e.g. `401694` request id not found, `401890` user not found)

**Example:**
```python
users.cancel_user_request(
    user_id="<user_primary_id>",
    request_id="<request_id>",
    reason="PatronRequest",
    note="Cancelled by phone",
)
```

---

#### `update_user_request(user_id, request_id, request_data)`

Updates a request (e.g. change pickup location, edit partial-digitization volume/issue).

**Signature:**
```python
def update_user_request(
    self,
    user_id: str,
    request_id: str,
    request_data: Dict[str, Any],
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `request_id` | str | Yes | Request identifier |
| `request_data` | dict | Yes | Non-empty request body — passed through verbatim |

**Returns:** `AlmaResponse` (updated request body).

**Raises:**
- `AlmaValidationError`: Empty ids; `request_data` empty / not a dict
- `AlmaAPIError`: On API failure (e.g. `60330` "Invalid partial digitization volume or issue")

---

#### `perform_user_request_action(user_id, request_id, op)`

Performs an op-driven action on a single request. Per the current swagger, only `op="next_step"` is documented — used to advance a digitization request through its workflow. The wrapper is deliberately op-agnostic so future Alma op additions do not require a wrapper update.

**Signature:**
```python
def perform_user_request_action(
    self,
    user_id: str,
    request_id: str,
    op: str,
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `request_id` | str | Yes | Request identifier |
| `op` | str | Yes | Action to perform. Currently `"next_step"` per Alma docs. |

**Returns:** `AlmaResponse`.

**Raises:**
- `AlmaValidationError`: Any empty / non-string input
- `AlmaAPIError`: On API failure (e.g. `401907` "Failed to find a request for the given request ID", `401932` "Request is not a Digitization request")

---

### Expiry Date Analysis Methods

#### `get_user_expiry_date(user_data)`

Extracts the expiry date from user data.

**Signature:**
```python
def get_user_expiry_date(self, user_data: Dict[str, Any]) -> Optional[str]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_data` | dict | Yes | User data from Alma API |

**Returns:** Expiry date as string (YYYY-MM-DDZ format) or `None` if not found

**Example:**
```python
response = users.get_user("123456789")
user_data = response.json()

expiry_date = users.get_user_expiry_date(user_data)
if expiry_date:
    print(f"User expires: {expiry_date}")
else:
    print("No expiry date set")
```

---

#### `parse_expiry_date(expiry_date_str)`

Parses an Alma expiry date string to a datetime object.

**Signature:**
```python
def parse_expiry_date(self, expiry_date_str: str) -> Optional[datetime]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `expiry_date_str` | str | Yes | Expiry date string from Alma (YYYY-MM-DDZ format) |

**Returns:** `datetime` object or `None` if parsing fails

**Example:**
```python
expiry_str = "2022-06-15Z"
expiry_dt = users.parse_expiry_date(expiry_str)

if expiry_dt:
    print(f"Parsed date: {expiry_dt.strftime('%B %d, %Y')}")
```

---

#### `is_user_expired_years(user_data, years_threshold=2)`

Checks if a user account has been expired for the specified number of years or more.

**Signature:**
```python
def is_user_expired_years(
    self,
    user_data: Dict[str, Any],
    years_threshold: int = 2
) -> Tuple[bool, Optional[int]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_data` | dict | Yes | User data from Alma API |
| `years_threshold` | int | No | Minimum years expired to return True (default: 2) |

**Returns:** Tuple of `(is_expired_enough, years_expired)`
- `is_expired_enough`: True if expired >= years_threshold
- `years_expired`: Number of years expired (None if no expiry date)

**Example:**
```python
response = users.get_user("123456789")
user_data = response.json()

is_expired, years = users.is_user_expired_years(user_data, years_threshold=2)

if is_expired:
    print(f"User has been expired for {years} years - qualifies for email update")
else:
    print(f"User not expired long enough (only {years} years)")
```

---

### Email Management Methods

#### `extract_user_emails(user_data)`

Extracts all email addresses from user data.

**Signature:**
```python
def extract_user_emails(self, user_data: Dict[str, Any]) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_data` | dict | Yes | User data from Alma API |

**Returns:** List of email dictionaries with structure:
```python
{
    'address': str,        # Email address
    'type': str,           # Email type (personal, work, etc.)
    'preferred': bool,     # Is this the preferred email?
    'original_entry': dict # Original email entry for updates
}
```

**Example:**
```python
response = users.get_user("123456789")
user_data = response.json()

emails = users.extract_user_emails(user_data)

for email in emails:
    preferred = "(preferred)" if email['preferred'] else ""
    print(f"  {email['type']}: {email['address']} {preferred}")
```

---

#### `validate_email(email)`

Validates an email address format.

**Signature:**
```python
def validate_email(self, email: str) -> bool
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | str | Yes | Email address to validate |

**Returns:** `True` if valid format, `False` otherwise

**Example:**
```python
# Valid emails
print(users.validate_email("user@example.com"))      # True
print(users.validate_email("user.name@domain.org")) # True

# Invalid emails
print(users.validate_email("not-an-email"))         # False
print(users.validate_email(""))                     # False
print(users.validate_email(None))                   # False
```

---

#### `generate_new_email(user_data, email_pattern)`

Generates a new email address using a pattern and user data.

**Signature:**
```python
def generate_new_email(
    self,
    user_data: Dict[str, Any],
    email_pattern: str
) -> str
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_data` | dict | Yes | User data from Alma API |
| `email_pattern` | str | Yes | Email pattern with placeholders |

**Available Placeholders:**
- `{user_id}` - User's primary ID (required in pattern)
- `{first_name}` - User's first name (lowercase)
- `{last_name}` - User's last name (lowercase)

**Returns:** Generated email address

**Raises:** `AlmaValidationError` if pattern is invalid or required data is missing

**Example:**
```python
response = users.get_user("123456789")
user_data = response.json()

# Generate expiry email
new_email = users.generate_new_email(
    user_data,
    "expired-{user_id}@institution.edu"
)
print(f"Generated: {new_email}")  # expired-123456789@institution.edu

# Use first/last name
new_email = users.generate_new_email(
    user_data,
    "{first_name}.{last_name}.expired@institution.edu"
)
```

---

#### `update_user_email(user_id, new_email, email_type="personal")`

Updates a user's primary email address.

**Signature:**
```python
def update_user_email(
    self,
    user_id: str,
    new_email: str,
    email_type: str = 'personal'
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `new_email` | str | Yes | New email address |
| `email_type` | str | No | Type of email: "personal", "work", etc. (default: "personal") |

**Returns:** `AlmaResponse` containing updated user data

**Raises:**
- `AlmaValidationError`: If email format is invalid
- `AlmaAPIError`: If API request fails

**Behavior:**
1. Retrieves current user data
2. Updates the preferred email or first email in the list
3. If no emails exist, adds a new email entry
4. Sends the update to Alma

**Example:**
```python
# Update a user's email
response = users.update_user_email(
    user_id="123456789",
    new_email="expired.user@institution.edu",
    email_type="personal"
)

if response.success:
    print("Email updated successfully")
```

---

### Batch Processing Methods

#### `process_user_for_expiry(user_id, years_threshold=2)`

Processes a single user to determine if they qualify for email update based on expiry status.

**Signature:**
```python
def process_user_for_expiry(
    self,
    user_id: str,
    years_threshold: int = 2
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | str | Yes | User identifier |
| `years_threshold` | int | No | Minimum years expired to qualify (default: 2) |

**Returns:** Dictionary with processing results:
```python
{
    'user_id': str,              # The user ID processed
    'success': bool,             # True if API call succeeded
    'qualifies_for_update': bool, # True if user meets update criteria
    'error': Optional[str],      # Error message if failed
    'user_data': Optional[dict], # Full user data if successful
    'emails': List[dict],        # Extracted email addresses
    'years_expired': Optional[int], # Number of years expired
    'expiry_date': Optional[str]    # Raw expiry date string
}
```

**Example:**
```python
result = users.process_user_for_expiry("123456789", years_threshold=2)

if result['success']:
    if result['qualifies_for_update']:
        print(f"User qualifies: expired {result['years_expired']} years")
        print(f"Current emails: {result['emails']}")
    else:
        print("User does not qualify for email update")
else:
    print(f"Error: {result['error']}")
```

---

#### `process_users_batch(user_ids, years_threshold=2, max_workers=5)`

Processes multiple users for expiry qualification in batch.

**Signature:**
```python
def process_users_batch(
    self,
    user_ids: List[str],
    years_threshold: int = 2,
    max_workers: int = 5
) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_ids` | List[str] | Yes | List of user IDs to process |
| `years_threshold` | int | No | Minimum years expired to qualify (default: 2) |
| `max_workers` | int | No | Reserved for future concurrent processing (default: 5) |

**Returns:** List of processing results (same structure as `process_user_for_expiry`)

**Features:**
- Progress logging every 10 users
- Built-in rate limiting (1 second pause every 50 requests)
- Summary statistics logged at completion

**Example:**
```python
# List of users from a set
user_ids = ['222333444', '987654321', '333444555', '012345678']

# Process all users
results = users.process_users_batch(user_ids, years_threshold=2)

# Analyze results
qualified = [r for r in results if r['qualifies_for_update']]
failed = [r for r in results if not r['success']]

print(f"Processed: {len(results)}")
print(f"Qualified for update: {len(qualified)}")
print(f"Failed: {len(failed)}")
```

---

#### `bulk_update_emails(email_updates, dry_run=True)`

Updates multiple users' emails in bulk with safety controls.

**Signature:**
```python
def bulk_update_emails(
    self,
    email_updates: List[Dict[str, str]],
    dry_run: bool = True
) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_updates` | List[dict] | Yes | List of update dictionaries |
| `dry_run` | bool | No | If True, validates without updating (default: True) |

**Update Dictionary Structure:**
```python
{
    'user_id': str,      # Required: User identifier
    'new_email': str,    # Required: New email address
    'email_type': str    # Optional: Email type (default: "personal")
}
```

**Returns:** List of update results:
```python
{
    'user_id': str,     # User ID
    'new_email': str,   # Email that was/would be set
    'success': bool,    # True if operation succeeded
    'error': Optional[str], # Error message if failed
    'dry_run': bool     # Whether this was a dry run
}
```

**Features:**
- **Dry-run by default** for safety
- Progress logging every 5 users
- Rate limiting (2 second pause every 25 requests)
- Summary statistics at completion

**Example:**
```python
# Prepare updates
email_updates = [
    {'user_id': '123456789', 'new_email': 'expired-123456789@institution.edu'},
    {'user_id': '987654321', 'new_email': 'expired-987654321@institution.edu'},
]

# First, do a dry run to validate
dry_results = users.bulk_update_emails(email_updates, dry_run=True)

successful_dry = sum(1 for r in dry_results if r['success'])
print(f"Dry run: {successful_dry}/{len(email_updates)} would succeed")

# If satisfied, run for real
if successful_dry == len(email_updates):
    live_results = users.bulk_update_emails(email_updates, dry_run=False)
    successful = sum(1 for r in live_results if r['success'])
    print(f"Live update: {successful}/{len(email_updates)} succeeded")
```

---

## Common Workflows

### Workflow 1: User Email Update for Expired Users

This workflow identifies users expired for 2+ years and updates their email addresses.

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users
from almaapitk.domains.admin import Admin

# Initialize
client = AlmaAPIClient('SANDBOX')  # Start with SANDBOX!
users = Users(client)
admin = Admin(client)

# Step 1: Get users from a set
set_id = "12345678900001234"  # Your expired users set ID
set_data = admin.get_set(set_id)
members = admin.get_set_members(set_id)

# Extract user IDs from set members
user_ids = []
for member in members:
    # Extract ID from member link
    user_id = member.get('link', '').split('/')[-1]
    if user_id:
        user_ids.append(user_id)

print(f"Found {len(user_ids)} users in set")

# Step 2: Process users to find those qualifying for update
results = users.process_users_batch(user_ids, years_threshold=2)

# Step 3: Filter qualified users
qualified_users = [r for r in results if r['qualifies_for_update']]
print(f"{len(qualified_users)} users qualify for email update")

# Step 4: Prepare email updates
email_pattern = "expired-{user_id}@yourinstitution.edu"
email_updates = []

for result in qualified_users:
    user_data = result['user_data']
    try:
        new_email = users.generate_new_email(user_data, email_pattern)
        email_updates.append({
            'user_id': result['user_id'],
            'new_email': new_email
        })
    except Exception as e:
        print(f"Could not generate email for {result['user_id']}: {e}")

# Step 5: Dry run first!
print("\nPerforming dry run...")
dry_results = users.bulk_update_emails(email_updates, dry_run=True)

successful = sum(1 for r in dry_results if r['success'])
failed = [r for r in dry_results if not r['success']]

print(f"Dry run results: {successful} would succeed, {len(failed)} would fail")

# Show any failures
for failure in failed:
    print(f"  Would fail: {failure['user_id']} - {failure['error']}")

# Step 6: If satisfied, run live (uncomment when ready)
# print("\nPerforming live update...")
# live_results = users.bulk_update_emails(email_updates, dry_run=False)
# print(f"Updated {sum(1 for r in live_results if r['success'])} users")
```

### Workflow 2: Batch Processing with TSV Output

This workflow processes users and generates a TSV report.

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users
from datetime import datetime
import csv

# Initialize
client = AlmaAPIClient('SANDBOX')
users = Users(client)

# User IDs to process (could come from file, set, etc.)
user_ids = ['123456789', '987654321', '333444555']

# Process all users
results = users.process_users_batch(user_ids, years_threshold=2)

# Generate TSV report
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = f"user_processing_results_{timestamp}.tsv"

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')

    # Header
    writer.writerow([
        'user_id', 'success', 'qualifies', 'years_expired',
        'expiry_date', 'current_email', 'error'
    ])

    # Data rows
    for result in results:
        current_email = ''
        if result['emails']:
            preferred = [e for e in result['emails'] if e.get('preferred')]
            if preferred:
                current_email = preferred[0]['address']
            else:
                current_email = result['emails'][0]['address']

        writer.writerow([
            result['user_id'],
            result['success'],
            result['qualifies_for_update'],
            result.get('years_expired', ''),
            result.get('expiry_date', ''),
            current_email,
            result.get('error', '')
        ])

print(f"Results written to {output_file}")

# Summary
total = len(results)
successful = sum(1 for r in results if r['success'])
qualified = sum(1 for r in results if r['qualifies_for_update'])

print(f"\nSummary:")
print(f"  Total processed: {total}")
print(f"  Successfully retrieved: {successful}")
print(f"  Qualified for update: {qualified}")
```

### Workflow 3: Create User, Loan an Item, then Return (Renew)

This workflow walks the full new-user lifecycle: create the patron, loan them a starting item, renew once, and update the due date.

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

client = AlmaAPIClient('SANDBOX')
users = Users(client)

# Step 1: Create the user (four required fields + optional metadata)
created = users.create_user({
    "primary_id": "<user_primary_id>",
    "account_type": {"value": "INTERNAL"},
    "status": {"value": "ACTIVE"},
    "user_group": {"value": "STAFF"},
    "first_name": "Ada",
    "last_name": "Lovelace",
})
new_user_id = created.data["primary_id"]
print(f"Created user {new_user_id}")

# Step 2: Loan an item to the new user
# Reminder: item_barcode is a QUERY param; library/circ_desk go in the BODY
# and must use the {"value": "<code>"} wrapper.
loan_resp = users.create_user_loan(
    user_id=new_user_id,
    item_barcode="<item_barcode>",
    loan_data={
        "circ_desk": {"value": "<circ_desk_code>"},
        "library": {"value": "<library_code>"},
    },
)
loan_id = loan_resp.data["loan_id"]
print(f"Loan {loan_id} created (due {loan_resp.data.get('due_date')})")

# Step 3: Renew the loan once
renewed = users.renew_user_loan(new_user_id, loan_id)
print(f"Renewed; new due date: {renewed.data.get('due_date')}")

# Step 4: Push the due date to a specific value
from datetime import datetime, timedelta, timezone
new_due = (datetime.now(timezone.utc) + timedelta(days=14)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)
users.update_user_loan(new_user_id, loan_id, {"due_date": new_due})
print(f"Due date pushed to {new_due}")

# Step 5: When the user is no longer needed, delete (no body returned — 204)
# audit_snapshot = users.get_user(new_user_id).json()  # save audit trail first
# users.delete_user(new_user_id)
```

### Workflow 4: Hold-Request Lifecycle

Place a HOLD against an unavailable title (the only common test scenario — rules vary per tenant), inspect it, then cancel.

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

client = AlmaAPIClient('SANDBOX')
users = Users(client)

# Step 1: Place a title-level HOLD
create_resp = users.create_user_request(
    user_id="<user_primary_id>",
    request_data={
        "request_type": "HOLD",
        "pickup_location_type": "LIBRARY",
        "pickup_location_library": "<library_code>",
    },
    mms_id="<mms_id>",  # OR pass item_pid="<item_pid>" for an item-level hold
)
request_id = create_resp.data["request_id"]
print(f"Placed HOLD {request_id}")

# Step 2: List active requests for this patron
active_requests = users.list_user_requests(
    user_id="<user_primary_id>",
    request_type="HOLD",
    status="active",
)
print(f"User has {len(active_requests)} active HOLD requests")

# Step 3: Retrieve the new request's details
details = users.get_user_request("<user_primary_id>", request_id)
print(f"Pickup location: {details.get('pickup_location_library')}")

# Step 4: Cancel the request — reason is REQUIRED
users.cancel_user_request(
    user_id="<user_primary_id>",
    request_id=request_id,
    reason="PatronRequest",       # from the RequestCancellationReasons code table
    note="Patron found a copy elsewhere",
)
print("HOLD cancelled (204 No Content)")
```

**Common HOLD errors:**

| Error code | Meaning |
|------------|---------|
| 401129 | No items can fulfill the submitted request |
| 401136 | Patron already has an active request on this item |
| 401119 | User not eligible to place this request |
| 401694 | Pickup location invalid (or request id not found on cancel) |
| 401907 | Request type not supported / request id not found |

---

## Best Practices and Gotchas

### Best Practices

1. **Always Use Dry-Run First**
   ```python
   # ALWAYS test with dry_run=True before live updates
   results = users.bulk_update_emails(updates, dry_run=True)
   # Review results, then run with dry_run=False if satisfied
   ```

2. **Test in SANDBOX Before PRODUCTION**
   ```python
   # Start with SANDBOX
   client = AlmaAPIClient('SANDBOX')
   # Only switch to PRODUCTION when fully tested
   # client = AlmaAPIClient('PRODUCTION')
   ```

3. **Handle Rate Limiting**
   - The batch methods include built-in rate limiting
   - For custom loops, add delays:
     ```python
     import time
     for user_id in user_ids:
         result = users.get_user(user_id)
         # Process result...
         time.sleep(0.1)  # 100ms delay between requests
     ```

4. **Validate Emails Before Updating**
   ```python
   if users.validate_email(new_email):
       users.update_user_email(user_id, new_email)
   else:
       print(f"Invalid email format: {new_email}")
   ```

5. **Log All Operations**
   - The Users class includes comprehensive logging
   - Review logs for debugging and audit trails

### Common Gotchas

1. **Email Array Structure**

   Emails are stored in an array, even for single emails. Handle both single dict and list:
   ```python
   # The class handles this internally, but be aware when working with raw data
   email_list = contact_info.get('email', [])
   if isinstance(email_list, dict):
       email_list = [email_list]  # Normalize to list
   ```

2. **Complete User Object Required for Updates**

   The Alma API requires the complete user object for PUT requests:
   ```python
   # CORRECT: Get full object, modify, send back
   response = users.get_user(user_id)
   user_data = response.json()
   user_data['first_name'] = "New Name"
   users.update_user(user_id, user_data)

   # WRONG: Partial update (will fail or cause data loss)
   # users.update_user(user_id, {'first_name': 'New Name'})
   ```

3. **Date Format**

   Alma uses ISO 8601 format with timezone indicator:
   ```python
   # Correct format
   expiry_date = "2026-12-31Z"

   # The parse_expiry_date method handles the Z suffix
   ```

4. **Expiry vs Active Status**

   A user can have `status = ACTIVE` but still be expired:
   ```python
   # Check BOTH fields
   is_active = user_data.get('status', {}).get('value') == 'ACTIVE'
   expiry_date = user_data.get('expiry_date')
   # User may be "active" but with a past expiry date
   ```

5. **Empty Email Lists**

   Some users may have no email addresses:
   ```python
   emails = users.extract_user_emails(user_data)
   if not emails:
       print(f"User {user_id} has no email addresses")
       # Handle appropriately - may not qualify for email update workflow
   ```

---

## Alma API Reference

### Endpoints Used

| Operation | Endpoint | HTTP Method |
|-----------|----------|-------------|
| List / search users | `/almaws/v1/users` | GET |
| Create user | `/almaws/v1/users` | POST |
| Get user | `/almaws/v1/users/{user_id}` | GET |
| Update user | `/almaws/v1/users/{user_id}` | PUT |
| Delete user | `/almaws/v1/users/{user_id}` | DELETE |
| Personal-data export | `/almaws/v1/users/{user_id}/personal-data` | GET |
| List attachments | `/almaws/v1/users/{user_id}/attachments` | GET |
| Upload attachment | `/almaws/v1/users/{user_id}/attachments` | POST |
| Get attachment | `/almaws/v1/users/{user_id}/attachments/{attachment_id}` | GET |
| List fees | `/almaws/v1/users/{user_id}/fees` | GET |
| Create fee | `/almaws/v1/users/{user_id}/fees` | POST |
| Pay all fees | `/almaws/v1/users/{user_id}/fees/all?op=pay&...` | POST |
| Get fee | `/almaws/v1/users/{user_id}/fees/{fee_id}` | GET |
| Pay / waive / dispute / restore fee | `/almaws/v1/users/{user_id}/fees/{fee_id}?op=<op>&...` | POST |
| List deposits | `/almaws/v1/users/{user_id}/deposits` | GET |
| Create deposit | `/almaws/v1/users/{user_id}/deposits` | POST |
| Get deposit | `/almaws/v1/users/{user_id}/deposits/{deposit_id}` | GET |
| Perform deposit action | `/almaws/v1/users/{user_id}/deposits/{deposit_id}?op=<op>` | POST |
| List loans | `/almaws/v1/users/{user_id}/loans` | GET |
| Create loan | `/almaws/v1/users/{user_id}/loans` | POST |
| Get loan | `/almaws/v1/users/{user_id}/loans/{loan_id}` | GET |
| Renew loan | `/almaws/v1/users/{user_id}/loans/{loan_id}?op=renew` | POST |
| Update loan (due date) | `/almaws/v1/users/{user_id}/loans/{loan_id}` | PUT |
| List requests | `/almaws/v1/users/{user_id}/requests` | GET |
| Create request | `/almaws/v1/users/{user_id}/requests` | POST |
| Get request | `/almaws/v1/users/{user_id}/requests/{request_id}` | GET |
| Update request | `/almaws/v1/users/{user_id}/requests/{request_id}` | PUT |
| Cancel request | `/almaws/v1/users/{user_id}/requests/{request_id}?reason=...` | DELETE |
| Perform request action | `/almaws/v1/users/{user_id}/requests/{request_id}?op=<op>` | POST |

### Official Documentation

- **Users API**: https://developers.exlibrisgroup.com/alma/apis/users/
- **API Console**: https://developers.exlibrisgroup.com/console/

### API Quirks and Notes

1. **Email Structure Variations**
   - Emails are stored as an array in `contact_info.email`
   - Each email has `email_address`, `preferred`, and `email_types` fields
   - The `email_types` field may be nested differently in responses vs requests

2. **User Identifiers**
   - `user_id` parameter accepts multiple identifier types:
     - Primary ID (most common)
     - Barcode
     - Other configured identifiers
   - The API automatically resolves the identifier type

3. **Query/Body Split — Easy to Misuse**
   - `create_user_loan`: `item_barcode` / `item_pid` are **query** params; `library` / `circ_desk` go in the **body** wrapped as `{"value": "<code>"}` dicts. Bare strings fail validation server-side.
   - `create_user_request`: `mms_id` / `item_pid` / `holding_id` / `user_id_type` are **query** params; `request_type`, `pickup_location_*` go in the **body**. Pass exactly one of `mms_id` OR `item_pid` (HOLDs typically use `mms_id` for title-level; `item_pid` for item-level).
   - Op-driven fee endpoints (pay / waive / dispute / restore): `op`, `amount`, `method`, `reason`, `comment` all travel as **query** params; the body is empty.

4. **Attachment Upload — Plain-String `type`**
   The user-attachment POST body uses a plain string for `type` (e.g. `"GENERAL"`), NOT the `{"value": "GENERAL"}` wrapper Alma uses elsewhere. Wrapping it returns 400 ("Cannot deserialize value of type java.lang.String from Object value"). There is no DELETE endpoint documented for user attachments.

5. **`cancel_user_request.reason` is Required**
   Earlier versions of this doc listed `reason` as optional — it is **required** (audit-corrected). Alma's cancel endpoint rejects DELETE without it. Use a value from the `RequestCancellationReasons` code table.

6. **HOLD Test Scenarios Vary By Tenant**
   The only common, broadly portable test scenario for `create_user_request` is `request_type="HOLD"` against an **unavailable** item. Tenant-specific configuration controls which pickup locations, user groups, and item statuses make a HOLD placeable; expect 401129 / 401119 / 401694 on tenants where the test fixture does not match local rules.

7. **`delete_user` Returns 204 No Content**
   No body is returned on a successful delete. If you need an audit snapshot of the user, call `get_user(user_id)` first and persist that payload.

8. **Error Codes**

   | Code | Meaning | Resolution |
   |------|---------|------------|
   | 401861 | User not found | Verify user ID exists |
   | 401862 | Input validation error | Check required fields and formats |
   | 401868 | User already exists | Use different `primary_id` |
   | 401863 | Cannot delete user | Clear loans/fees first |
   | 401890 | User group / user not found | Verify user group in config |
   | 401168 | Patron card expired | Renew patron account before retry |
   | 401119 | User not eligible | Check user group / loan-policy rules |
   | 401129 | No items can fulfill the submitted request | Item-level HOLD against an unavailable item, or tenant rules block the request type |
   | 401136 | Patron already has an active request on this item | List existing requests; cancel before retry |
   | 401694 | Pickup location invalid / request id not found | Verify `pickup_location_library` or request id |
   | 401822 | Cannot renew loan | Loan exceeds renewal limit / blocked by policy |
   | 401823 | Loan ID does not exist | Re-fetch loans list |
   | 401824 | Due date is not in loan object | Include `due_date` in `update_user_loan` body |
   | 401681 | Due date cannot be in the past | Push due date forward |
   | 401907 | Request type not supported / request id not found | Verify request id; check tenant config for the request type |
   | 401932 | Request is not a Digitization request | `next_step` only applies to DIGITIZATION |
   | 60330 | Invalid partial digitization volume or issue | Fix body before re-PUT |

9. **Rate Limits**
   - Default: 100 requests per minute
   - Exceeding limit returns HTTP 429
   - Built-in batch methods include rate limiting

### Related API References

- [Admin API](admin_api.md) - For user set operations
- [Error Codes](../api-reference.md) - Complete error reference

---

## Source Code Location

**File:** `/home/hagaybar/projects/AlmaAPITK/src/almaapitk/domains/users.py`

---

## See Also

- [Getting Started Guide](../getting-started.md) - Initial setup
- [API Reference](../api-reference.md) - Complete API documentation
- [Alma API Expert Skill](../../.claude/skills/alma-api-expert/) - Detailed API knowledge
