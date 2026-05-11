# Admin Domain Guide

Comprehensive guide for the `Admin` domain class in AlmaAPITK.

## Overview

The Admin domain class handles Alma Configuration API operations, primarily focused on **Sets** management. Sets are collections of records used for batch operations, reports, and workflow automation.

### What This Domain Handles

- **BIB_MMS sets**: Collections of bibliographic records (identified by MMS IDs)
- **USER sets**: Collections of user records (identified by User Primary IDs)
- **Set validation**: Verifying set type and membership
- **Set metadata**: Retrieving set information, member counts, and processing estimates
- **Set listing**: Searching and filtering available sets
- **Set CRUD** (0.4.0): Creating, updating, and deleting sets
- **Member management** (0.4.0): Adding and removing members in an existing set

### When to Use It

| Use Case | Example |
|----------|---------|
| Process batch of users | Email update workflow for expired users |
| Process batch of bib records | Collection assessment, metadata cleanup |
| Validate set before processing | Ensure set type matches expected operation |
| Estimate processing time | Large set handling with progress tracking |
| Find available sets | List USER or BIB_MMS sets for selection |

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Set** | A collection of record IDs (like a saved search result) |
| **Set ID** | Unique identifier for the set (e.g., "25793308630004146") |
| **Set Type** | ITEMIZED (static list) or LOGICAL (dynamic query) |
| **Content Type** | Type of records: BIB_MMS, USER, ITEM, HOLDING, PORTFOLIO |
| **Member** | Individual record ID within a set |

## Initialization

### Basic Setup

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.admin import Admin

# Create API client
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'

# Initialize Admin domain
admin = Admin(client)

# Optional: Test connection
if admin.test_connection():
    print("Admin API connection successful")
```

### With Logging

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.admin import Admin
from almaapitk.alma_logging import get_logger

# Create client and admin domain
client = AlmaAPIClient('SANDBOX')
admin = Admin(client)

# Admin inherits logger from client
# Logs go to logs/api_requests/YYYY-MM-DD/admin.log
```

## Methods Reference

### get_set_members

Retrieves all member IDs from an Alma set using automatic pagination.

**Signature:**
```python
def get_set_members(
    self,
    set_id: str,
    expected_type: Optional[str] = None
) -> List[str]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The Alma set ID (e.g., "25793308630004146") |
| `expected_type` | str | No | Validate set type: "BIB_MMS", "USER", or None for auto-detect |

**Returns:** `List[str]` - List of member IDs (MMS IDs for BIB sets, User IDs for USER sets)

**Raises:**
- `AlmaValidationError` - If set_id is empty or set type doesn't match expected
- `AlmaAPIError` - If the API request fails

**Example:**
```python
# Auto-detect set type
member_ids = admin.get_set_members("25793308630004146")
print(f"Retrieved {len(member_ids)} members")

# Validate set type
try:
    user_ids = admin.get_set_members("25793308630004146", expected_type="USER")
except AlmaValidationError as e:
    print(f"Set type mismatch: {e}")
```

---

### get_user_set_members

Convenience method to extract all user IDs from a USER set with type validation.

**Signature:**
```python
def get_user_set_members(self, set_id: str) -> List[str]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The Alma USER set ID |

**Returns:** `List[str]` - List of user IDs from the set

**Raises:**
- `AlmaValidationError` - If set is not a USER set
- `AlmaAPIError` - If the API request fails

**Example:**
```python
# Get all users from a USER set
user_ids = admin.get_user_set_members("25793308630004146")

# Process each user
for user_id in user_ids:
    print(f"Processing user: {user_id}")
```

---

### get_bib_set_members

Convenience method to extract all MMS IDs from a BIB_MMS set with type validation.

**Signature:**
```python
def get_bib_set_members(self, set_id: str) -> List[str]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The Alma BIB_MMS set ID |

**Returns:** `List[str]` - List of MMS IDs from the set

**Raises:**
- `AlmaValidationError` - If set is not a BIB_MMS set
- `AlmaAPIError` - If the API request fails

**Example:**
```python
# Get all bibs from a BIB_MMS set
mms_ids = admin.get_bib_set_members("25793308630004146")

# Process each bib record
for mms_id in mms_ids:
    print(f"Processing bib: {mms_id}")
```

---

### validate_user_set

Validates that a set exists and is of USER type. Returns detailed set information.

**Signature:**
```python
def validate_user_set(self, set_id: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The set ID to validate |

**Returns:** `Dict[str, Any]` - Set information dictionary:
```python
{
    "id": "25793308630004146",
    "name": "Expired Users Q1 2025",
    "content_type": "USER",
    "total_members": 150,
    "status": "ACTIVE",
    "created_date": "2025-01-15Z"
}
```

**Raises:**
- `AlmaValidationError` - If set doesn't exist or is not USER type
- `AlmaAPIError` - If API request fails

**Example:**
```python
try:
    set_info = admin.validate_user_set("25793308630004146")
    print(f"Valid USER set: {set_info['name']}")
    print(f"Members: {set_info['total_members']}")
except AlmaValidationError as e:
    print(f"Invalid set: {e}")
```

---

### get_set_info

Retrieves detailed information about any set (public method).

**Signature:**
```python
def get_set_info(self, set_id: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The set ID |

**Returns:** `Dict[str, Any]` - Set information summary:
```python
{
    "id": "25793308630004146",
    "name": "My Set Name",
    "description": "Set description text",
    "content_type": "USER",  # or "BIB_MMS", etc.
    "status": "ACTIVE",
    "total_members": 100,
    "created_date": "2025-01-15Z",
    "created_by": "admin"
}
```

**Raises:**
- `AlmaValidationError` - If set_id is empty
- `AlmaAPIError` - If API request fails

**Example:**
```python
set_info = admin.get_set_info("25793308630004146")
print(f"Set: {set_info['name']}")
print(f"Type: {set_info['content_type']}")
print(f"Members: {set_info['total_members']}")
```

---

### get_set_metadata_and_member_count

Retrieves enhanced set metadata including processing time estimates and warnings.

**Signature:**
```python
def get_set_metadata_and_member_count(self, set_id: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The set ID |

**Returns:** `Dict[str, Any]` - Enhanced metadata:
```python
{
    "basic_info": {
        "id": "25793308630004146",
        "name": "Large User Set",
        "description": "...",
        "content_type": "USER",
        "status": "ACTIVE"
    },
    "member_info": {
        "total_members": 5000,
        "estimated_processing_time_minutes": 250,
        "pages_required": 50
    },
    "creation_info": {
        "created_date": "2025-01-15Z",
        "created_by": "admin"
    },
    "processing_warnings": [
        "Very large set. Consider running during off-peak hours.",
        "Large user set. Email updates will require careful rate limiting."
    ]
}
```

**Raises:**
- `AlmaValidationError` - If set_id is empty
- `AlmaAPIError` - If API request fails

**Example:**
```python
metadata = admin.get_set_metadata_and_member_count("25793308630004146")

print(f"Set: {metadata['basic_info']['name']}")
print(f"Members: {metadata['member_info']['total_members']}")
print(f"Est. time: {metadata['member_info']['estimated_processing_time_minutes']} minutes")

# Check for warnings
if metadata['processing_warnings']:
    print("Warnings:")
    for warning in metadata['processing_warnings']:
        print(f"  - {warning}")
```

---

### list_sets

Lists sets with optional filtering by content type.

**Signature:**
```python
def list_sets(
    self,
    limit: int = 25,
    offset: int = 0,
    content_type: str = None,
    include_member_counts: bool = False
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | No | Max results (default 25, max 100) |
| `offset` | int | No | Starting position for pagination |
| `content_type` | str | No | Filter by type: "BIB_MMS", "USER", etc. |
| `include_member_counts` | bool | No | Fetch member counts (slower) |

**Returns:** `AlmaResponse` - Response containing list of sets

**Raises:**
- `AlmaAPIError` - If API request fails

**Example:**
```python
# List USER sets
response = admin.list_sets(limit=10, content_type="USER")
sets_data = response.json()

for set_info in sets_data.get('set', []):
    print(f"Set: {set_info['name']} (ID: {set_info['id']})")

# With member counts (slower but complete)
response = admin.list_sets(
    limit=10,
    content_type="USER",
    include_member_counts=True
)
```

**Note:** The Alma list API does NOT include member counts by default. Set `include_member_counts=True` to fetch them via individual API calls (slower but provides complete information).

---

### Set Lifecycle (Create / Update / Delete)

The methods in this sub-section provide full CRUD on the set record itself. Shipped in 0.4.0 (issue #23). Each method wraps a single Alma endpoint and forwards the payload through verbatim, so callers can build any set Alma accepts without waiting for explicit keyword arguments.

---

#### create_set

Creates a new itemized or logical set.

**Signature:**
```python
def create_set(self, set_data: Dict[str, Any]) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_data` | Dict[str, Any] | Yes | Set object payload. Must include `name` (str) and `type` (e.g. `{"value": "ITEMIZED"}` or `{"value": "LOGICAL"}`). Almost every real call also wants `content` (e.g. `{"value": "BIB_MMS"}` or `{"value": "USER"}`). The body is forwarded to Alma verbatim — extra keys (description, query, status, etc.) are passed through. |

**Returns:** `AlmaResponse` — wraps the create response. The created set's identifier lives at `response.data["id"]`.

**Raises:**
- `AlmaValidationError` — If `set_data` is not a non-empty dict, or if `name` / `type` are missing or malformed. `type` accepts either the bare string code (`"ITEMIZED"`) or the canonical `{"value": "ITEMIZED"}` dict shape Alma returns on reads.
- `AlmaAPIError` — On API failure (typed subclasses surfaced when the Alma error code or HTTP status maps to one).

**Endpoint:** `POST /almaws/v1/conf/sets`

**Example:**
```python
response = admin.create_set({
    "name": "<set_name>",
    "description": "Records flagged for review",
    "type": {"value": "ITEMIZED"},
    "content": {"value": "BIB_MMS"},
})
set_id = response.data["id"]
print(f"Created set with id={set_id}")
```

---

#### update_set

Updates an existing set's metadata. Alma expects a complete set object, so the typical pattern is "read, mutate, write back" using `get_set_info` (or the raw `_get_set_info` payload) as the starting point.

**Signature:**
```python
def update_set(self, set_id: str, set_data: Dict[str, Any]) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The Alma set identifier to update. |
| `set_data` | Dict[str, Any] | Yes | Full set object payload (non-empty dict). |

**Returns:** `AlmaResponse` — wraps the updated set object.

**Raises:**
- `AlmaValidationError` — If `set_id` is empty or `set_data` is empty / not a dict.
- `AlmaAPIError` — On API failure.

**Endpoint:** `PUT /almaws/v1/conf/sets/{set_id}`

**Example:**
```python
info = admin.get_set_info("<set_id>")
info["description"] = "Updated description"
response = admin.update_set("<set_id>", info)
```

---

#### delete_set

Deletes a set. Removes the set record from Alma; the underlying member records (bibs, users, etc.) are untouched.

**Signature:**
```python
def delete_set(self, set_id: str) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The Alma set identifier to delete. |

**Returns:** `AlmaResponse` — wraps the delete response. Alma typically returns an empty body on a successful delete.

**Raises:**
- `AlmaValidationError` — If `set_id` is empty.
- `AlmaAPIError` — On API failure.

**Endpoint:** `DELETE /almaws/v1/conf/sets/{set_id}`

**Example:**
```python
admin.delete_set("<set_id>")
print("Set deleted")
```

---

### Set Member Management (Add / Remove)

Add or remove members from an existing set. Both methods share an internal helper, so validation, body construction, logging, and error handling are identical. The body shape Alma expects is `{"members": {"member": [{"id": "<member_id>"}, ...]}}`.

Caller-side ID-shape validation is intentionally NOT performed — Alma owns the rule that a `BIB_MMS` set takes MMS IDs and a `USER` set takes user primary IDs, and will reject mismatched IDs server-side with a typed error code.

---

#### add_members_to_set

Adds members to an existing itemized set.

**Signature:**
```python
def add_members_to_set(
    self,
    set_id: str,
    member_ids: List[str]
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The Alma set identifier to extend. |
| `member_ids` | List[str] | Yes | Non-empty list of member IDs to add. Each entry must be a non-empty string. |

**Returns:** `AlmaResponse` — wraps the updated set object.

**Raises:**
- `AlmaValidationError` — If `set_id` is empty, `member_ids` is empty / not a list, or any entry is empty / not a string.
- `AlmaAPIError` — On API failure.

**Endpoint:** `POST /almaws/v1/conf/sets/{set_id}?op=add_members`

**Example:**
```python
# Add bib records to a BIB_MMS set
admin.add_members_to_set(
    "<set_id>",
    ["<bib_mms_id_1>", "<bib_mms_id_2>", "<bib_mms_id_3>"],
)

# Add users to a USER set
admin.add_members_to_set(
    "<set_id>",
    ["<user_primary_id_1>", "<user_primary_id_2>"],
)
```

---

#### remove_members_from_set

Removes members from an existing itemized set. Body shape and validation match `add_members_to_set`.

**Signature:**
```python
def remove_members_from_set(
    self,
    set_id: str,
    member_ids: List[str]
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `set_id` | str | Yes | The Alma set identifier to shrink. |
| `member_ids` | List[str] | Yes | Non-empty list of member IDs to remove. Each entry must be a non-empty string. |

**Returns:** `AlmaResponse` — wraps the updated set object.

**Raises:**
- `AlmaValidationError` — If `set_id` is empty, `member_ids` is empty / not a list, or any entry is empty / not a string.
- `AlmaAPIError` — On API failure.

**Endpoint:** `POST /almaws/v1/conf/sets/{set_id}?op=delete_members`

**Example:**
```python
# Prune a USER set down
admin.remove_members_from_set(
    "<set_id>",
    ["<user_primary_id_1>", "<user_primary_id_2>"],
)
```

---

### test_connection

Tests if the admin/configuration endpoints are accessible.

**Signature:**
```python
def test_connection(self) -> bool
```

**Returns:** `bool` - True if connection successful, False otherwise

**Example:**
```python
if admin.test_connection():
    print(f"Connected to {admin.get_environment()} environment")
else:
    print("Connection failed - check API key and network")
```

---

### get_environment

Gets the current environment from the client.

**Signature:**
```python
def get_environment(self) -> str
```

**Returns:** `str` - "SANDBOX" or "PRODUCTION"

**Example:**
```python
env = admin.get_environment()
print(f"Current environment: {env}")
```

## Common Workflows

### Process Set Members Workflow

Complete workflow for processing all members of a set with progress tracking and error handling.

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.admin import Admin
from almaapitk.domains.users import Users
import time

def process_user_set(set_id: str, dry_run: bool = True):
    """Process all users in a USER set."""

    # Initialize
    client = AlmaAPIClient('SANDBOX')
    admin = Admin(client)
    users = Users(client)

    # Step 1: Validate set
    print(f"Validating set {set_id}...")
    try:
        set_info = admin.validate_user_set(set_id)
    except AlmaValidationError as e:
        print(f"ERROR: {e}")
        return

    print(f"Set: {set_info['name']}")
    print(f"Members: {set_info['total_members']}")

    # Step 2: Get metadata and check warnings
    metadata = admin.get_set_metadata_and_member_count(set_id)

    if metadata['processing_warnings']:
        print("\nWarnings:")
        for warning in metadata['processing_warnings']:
            print(f"  - {warning}")

    print(f"\nEstimated time: {metadata['member_info']['estimated_processing_time_minutes']} minutes")

    # Step 3: Get all member IDs
    print("\nRetrieving member IDs...")
    user_ids = admin.get_user_set_members(set_id)
    print(f"Retrieved {len(user_ids)} user IDs")

    # Step 4: Process each user
    results = {"success": 0, "failed": 0, "errors": []}

    for i, user_id in enumerate(user_ids, 1):
        # Progress indicator
        if i % 50 == 0 or i == len(user_ids):
            print(f"Progress: {i}/{len(user_ids)} ({i*100//len(user_ids)}%)")

        try:
            # Get user data
            user_response = users.get_user(user_id)
            user_data = user_response.json()

            if dry_run:
                print(f"  [DRY RUN] Would process user: {user_id}")
            else:
                # Perform actual operation here
                # Example: Update user email
                pass

            results["success"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"user_id": user_id, "error": str(e)})

        # Rate limiting
        if i % 25 == 0:
            time.sleep(1)

    # Step 5: Report results
    print(f"\n=== Results ===")
    print(f"Total: {len(user_ids)}")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")

    if results["errors"]:
        print("\nErrors:")
        for err in results["errors"][:10]:  # Show first 10
            print(f"  {err['user_id']}: {err['error']}")

    return results

# Run
process_user_set("25793308630004146", dry_run=True)
```

### End-to-End Set Lifecycle Workflow

Build a set from scratch, populate it, inspect it, and tear it down. Useful for ad-hoc batch jobs where the set should not outlive the operation.

```python
from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError, AlmaValidationError
from almaapitk.domains.admin import Admin


def run_one_shot_set(client: AlmaAPIClient, mms_ids: list[str]) -> dict:
    """Create a BIB_MMS set, add members, list them back, then delete the set."""
    admin = Admin(client)

    # Step 1: Create the (initially empty) set.
    create_response = admin.create_set({
        "name": "<set_name>",
        "description": "One-shot working set; safe to delete after run.",
        "type": {"value": "ITEMIZED"},
        "content": {"value": "BIB_MMS"},
    })
    set_id = create_response.data["id"]
    print(f"Created set id={set_id}")

    try:
        # Step 2: Add members. Alma validates ID shape against the set's
        # content_type and will reject mismatched IDs server-side.
        admin.add_members_to_set(set_id, mms_ids)
        print(f"Added {len(mms_ids)} member(s)")

        # Step 3: List members back, with type validation.
        retrieved = admin.get_bib_set_members(set_id)
        print(f"Set now reports {len(retrieved)} member(s)")

        # Step 4 (optional): Update set metadata after the fact.
        info = admin.get_set_info(set_id)
        info["description"] = (
            f"{info.get('description', '')} (members={len(retrieved)})"
        ).strip()
        admin.update_set(set_id, info)

        return {"set_id": set_id, "members": retrieved}

    finally:
        # Step 5: Always tear the working set down, even on errors.
        try:
            admin.delete_set(set_id)
            print(f"Deleted set id={set_id}")
        except (AlmaAPIError, AlmaValidationError) as cleanup_err:
            # Surface but do not mask the original failure.
            print(f"Warning: could not delete set {set_id}: {cleanup_err}")


# Run
client = AlmaAPIClient("SANDBOX")
result = run_one_shot_set(client, ["<bib_mms_id_1>", "<bib_mms_id_2>"])
```

**Key points:**

- The `finally` block ensures the working set is cleaned up even if member-add or read-back fails — important when the set is only created to support a single batch operation.
- `get_bib_set_members` re-validates `content_type` on read, so it doubles as a sanity check that the set really did end up as BIB_MMS.
- For long-lived sets used across many operations, skip the `delete_set` step and keep the set in Alma.

### Validate Set Workflow

Complete validation workflow before processing.

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.admin import Admin

def validate_set_for_processing(set_id: str, expected_type: str = "USER"):
    """Validate a set is ready for processing."""

    client = AlmaAPIClient('SANDBOX')
    admin = Admin(client)

    # Test connection first
    if not admin.test_connection():
        return {"valid": False, "error": "API connection failed"}

    try:
        # Get set info
        set_info = admin.get_set_info(set_id)

        # Validate content type
        if set_info['content_type'] != expected_type:
            return {
                "valid": False,
                "error": f"Expected {expected_type} set, got {set_info['content_type']}"
            }

        # Check status
        if set_info['status'] != "ACTIVE":
            return {
                "valid": False,
                "error": f"Set status is {set_info['status']}, expected ACTIVE"
            }

        # Check member count
        if set_info['total_members'] == 0:
            return {
                "valid": False,
                "error": "Set is empty"
            }

        # Get processing estimates
        metadata = admin.get_set_metadata_and_member_count(set_id)

        return {
            "valid": True,
            "set_info": set_info,
            "estimated_minutes": metadata['member_info']['estimated_processing_time_minutes'],
            "warnings": metadata['processing_warnings']
        }

    except AlmaAPIError as e:
        return {"valid": False, "error": f"API error: {e}"}
    except AlmaValidationError as e:
        return {"valid": False, "error": f"Validation error: {e}"}

# Usage
result = validate_set_for_processing("25793308630004146", "USER")

if result["valid"]:
    print(f"Set is valid: {result['set_info']['name']}")
    print(f"Processing time: ~{result['estimated_minutes']} minutes")
else:
    print(f"Set validation failed: {result['error']}")
```

## Best Practices and Gotchas

### Best Practices

1. **Always validate set type before processing**
   ```python
   # Good: Validate type matches expected
   set_info = admin.validate_user_set(set_id)

   # Or use expected_type parameter
   user_ids = admin.get_set_members(set_id, expected_type="USER")
   ```

2. **Use pagination-aware methods for large sets**
   ```python
   # Good: Built-in pagination
   all_members = admin.get_set_members(set_id)  # Handles pagination internally

   # The method automatically:
   # - Retrieves in 100-member batches
   # - Logs progress
   # - Handles single-member edge case
   ```

3. **Implement rate limiting for batch operations**
   ```python
   for i, user_id in enumerate(user_ids):
       # Process user...

       # Rate limit every 25 users
       if i % 25 == 0 and i > 0:
           time.sleep(1)
   ```

4. **Check processing warnings for large sets**
   ```python
   metadata = admin.get_set_metadata_and_member_count(set_id)

   if metadata['processing_warnings']:
       for warning in metadata['processing_warnings']:
           logger.warning(warning)
   ```

5. **Test in SANDBOX before PRODUCTION**
   ```python
   # Development
   client = AlmaAPIClient('SANDBOX')

   # Only after validation
   client = AlmaAPIClient('PRODUCTION')
   ```

### Gotchas

1. **Member counts not included in list view**

   The `list_sets()` API does NOT return member counts by default. You must either:
   - Use `include_member_counts=True` (slower - makes individual API calls)
   - Call `get_set_info()` for each set you need counts for

2. **Single member returned as dict, not list**

   The API returns a single member as a dict instead of a one-item list. The `get_set_members()` method handles this automatically.

3. **Member IDs extracted from links**

   Set members don't have a direct ID field. The ID is extracted from the `link` field:
   - BIB_MMS: `.../almaws/v1/bibs/{mms_id}`
   - USER: `.../almaws/v1/users/{user_id}`

4. **Set status affects processing**

   Only ACTIVE sets should be processed. Check `set_info['status']` before processing.

5. **Large sets require careful planning**
   - 1000+ members: Consider running during off-peak hours
   - 5000+ members: Very long processing time, may need batch approach
   - Rate limiting is essential to avoid API throttling

## Alma API Reference

### Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `GET /almaws/v1/conf/sets` | List sets with filtering |
| `GET /almaws/v1/conf/sets/{set_id}` | Get set metadata |
| `GET /almaws/v1/conf/sets/{set_id}/members` | Get set members with pagination |
| `POST /almaws/v1/conf/sets` | Create a new set |
| `PUT /almaws/v1/conf/sets/{set_id}` | Update an existing set |
| `DELETE /almaws/v1/conf/sets/{set_id}` | Delete a set |
| `POST /almaws/v1/conf/sets/{set_id}?op=add_members` | Add members to a set |
| `POST /almaws/v1/conf/sets/{set_id}?op=delete_members` | Remove members from a set |

### Official Documentation

- **Configuration API**: https://developers.exlibrisgroup.com/alma/apis/conf/
- **Sets Documentation**: See `alma-api-expert` skill → `references/admin_api.md`

### API Quirks

1. **Pagination limits**: Maximum 100 members per request
2. **Member counts**: Only available in individual set GET, not in list
3. **Date format**: Uses ISO 8601 with Z suffix (e.g., "2025-01-15Z")

### Error Codes

| Code | Message | Solution |
|------|---------|----------|
| 401861 | Set not found | Verify set ID exists |
| 401862 | Input validation error | Check required fields (`name`, `type`) on create / update |
| 401869 | Member not found | Verify member ID exists |
| 401871 | Set type not supported | Use ITEMIZED or LOGICAL |
| 60116  | Member ID does not match set content type | Verify member IDs match the set's `content` (MMS IDs for BIB_MMS, primary IDs for USER) |
| 60120  | Invalid member ID format | Confirm each entry in `member_ids` is a non-empty string in the format Alma expects |

### Related Resources

- **Error Codes Reference**: `alma-api-expert` skill → `references/error_codes_and_solutions.md`
- **Pagination Patterns**: `alma-api-expert` skill → `references/pagination_and_queries.md`
- **Users API** (for processing USER sets): `references/users_api.md`
- **Bibs API** (for processing BIB_MMS sets): `references/bibs_api.md`

---

**Source file**: `/home/hagaybar/projects/AlmaAPITK/src/almaapitk/domains/admin.py`

**Last updated**: 2026-05-11
