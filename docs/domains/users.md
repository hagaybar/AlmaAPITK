# Users Domain Class Reference

## Overview

The **Users** domain class provides comprehensive operations for managing patron records in the Alma ILS (Integrated Library System). It is specifically designed for user management workflows with a focus on email operations for expired user accounts.

### What This Domain Handles

- **User Retrieval**: Fetch complete user records by primary ID or other identifiers
- **User Updates**: Modify user information including contact details
- **Email Operations**: Extract, validate, generate, and update email addresses
- **Expiry Date Analysis**: Determine user account expiration status
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
| Get User | `/almaws/v1/users/{user_id}` | GET |
| Update User | `/almaws/v1/users/{user_id}` | PUT |
| List Users | `/almaws/v1/users` | GET |

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

3. **Error Codes**

   | Code | Meaning | Resolution |
   |------|---------|------------|
   | 401861 | User not found | Verify user ID exists |
   | 401862 | Input validation error | Check required fields and formats |
   | 401868 | User already exists | Use different primary_id |
   | 401863 | Cannot delete user | Clear loans/fees first |
   | 401890 | User group not found | Verify user group in config |

4. **Rate Limits**
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
