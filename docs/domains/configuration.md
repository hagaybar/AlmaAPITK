# Configuration Domain Guide

Comprehensive guide for the `Configuration` domain class in AlmaAPITK (introduced in 0.4.0).

## Overview

The Configuration domain class handles Alma Configuration API operations across the institution's organizational, lookup-table, notification, and utility surfaces. It is the foundation class introduced in issue #22 and extended by sibling tickets #24–#35.

### What This Domain Handles

- **Organizational structure**: Libraries, departments, and circulation desks
- **Locations**: Full CRUD for per-library locations (open stacks, closed stacks, reserves, etc.)
- **Code tables**: List, fetch, and replace institution-wide code tables
- **Mapping tables**: List, fetch, and replace institution-wide mapping tables
- **Deposit and import profiles**: Read-only coverage of deposit profiles and metadata-import (md-import) profiles
- **Letters and printers**: Notification templates (XSL bodies) and printer configuration
- **Utilities**: Workflow runner, fee-transactions report, and general institutional configuration

### When to Use It

| Use Case | Example |
|----------|---------|
| Discover libraries before drilling into locations | List `MAIN`, `LAW`, `MEDICAL`, etc. before reading locations per library |
| Drive a deposit ingest workflow | Look up the deposit profile id, then submit to the deposit API |
| Toggle a code-table row | Disable an obsolete `AcqInvoiceLineType` entry without touching the rest |
| Edit a notification template | Update the XSL body of an overdue-loan letter |
| Audit fee transactions | Pull a per-library / per-date-range report for finance reconciliation |
| Bootstrap institutional config | Read `default_language`, `default_currency`, `timezone` for environment-aware tooling |

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Library code** | Stable opaque identifier for a library (e.g. `<library_code>`). Drives most org-scoped endpoints. |
| **Location code** | Identifier for a shelving location. **Unique per library, not globally** — the same `<location_code>` may be reused across libraries. |
| **Circ desk code** | Identifier for a circulation desk within a library. Scoped by `<library_code>`. |
| **Code table** | An enumeration of codes (e.g. invoice line types). Identified by `<code_table_name>`. |
| **Mapping table** | A key→value lookup table. Structurally identical to a code table at the API surface but semantically distinct. |
| **Letter** | A notification template (subject + XSL body) identified by `<letter_code>`. |
| **Deposit profile / import profile** | Configured ingest profiles, each identified by an opaque id. |
| **Workflow id** | Opaque identifier for a configured Alma workflow. Side effects depend entirely on the workflow's configuration. |

## Initialization

### Basic Setup

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration

# Create API client
client = AlmaAPIClient('SANDBOX')  # or 'PRODUCTION'

# Initialize Configuration domain
config = Configuration(client)

# Optional: Test connection
if config.test_connection():
    print("Configuration API connection successful")
```

### With Logging

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration
from almaapitk.alma_logging import get_logger

# Create client and configuration domain
client = AlmaAPIClient('SANDBOX')
config = Configuration(client)

# Configuration constructs its own logger keyed to ``'configuration'``
# Logs go to logs/api_requests/YYYY-MM-DD/configuration.log
```

## Methods Reference

### test_connection

Tests if the Alma API connection is working. Delegates to `AlmaAPIClient.test_connection` — at the foundation level we simply confirm the client itself can reach the API rather than hit a domain-specific endpoint.

**Signature:**
```python
def test_connection(self) -> bool
```

**Returns:** `bool` — True if the underlying client connection succeeds, False otherwise.

**Example:**
```python
if config.test_connection():
    print(f"Connected to {config.get_environment()} environment")
else:
    print("Connection failed - check API key and network")
```

---

### get_environment

Gets the current environment from the underlying client.

**Signature:**
```python
def get_environment(self) -> str
```

**Returns:** `str` — `"SANDBOX"` or `"PRODUCTION"`

**Example:**
```python
env = config.get_environment()
print(f"Current environment: {env}")
```

---

### Organizational Structure (issue #24)

#### list_libraries

Lists all libraries configured in the Alma institution. Always call this first to discover the `<library_code>` values your tooling will pass to the per-library endpoints.

**Signature:**
```python
def list_libraries(self) -> List[Dict[str, Any]]
```

**Returns:** `List[Dict[str, Any]]` — List of library dicts as returned by Alma. Empty list when the institution has no libraries configured.

**Raises:**
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
libraries = config.list_libraries()
for lib in libraries:
    print(f"{lib.get('code')}: {lib.get('name')}")
```

---

#### get_library

Gets configuration details for a single library.

**Signature:**
```python
def get_library(self, library_code: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `library_code` | str | Yes | The Alma library code (e.g. `<library_code>`) |

**Returns:** `Dict[str, Any]` — The library configuration dict as returned by Alma.

**Raises:**
- `AlmaValidationError` — If `library_code` is empty or not a string.
- `AlmaAPIError` — If the API request fails (including 404 when the library code does not exist).

**Example:**
```python
library = config.get_library("<library_code>")
print(f"Name: {library.get('name')}")
print(f"Type: {library.get('type', {}).get('value')}")
```

---

#### list_departments

Lists all departments configured in the Alma institution.

**Signature:**
```python
def list_departments(self) -> List[Dict[str, Any]]
```

**Returns:** `List[Dict[str, Any]]` — List of department dicts. Empty list when none are configured.

**Raises:**
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
departments = config.list_departments()
print(f"Configured departments: {len(departments)}")
```

---

#### list_circ_desks

Lists circulation desks configured for a given library.

**Signature:**
```python
def list_circ_desks(self, library_code: str) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `library_code` | str | Yes | The Alma library code whose circ desks to list |

**Returns:** `List[Dict[str, Any]]` — List of circ-desk dicts. Empty list when the library has no circ desks configured.

**Raises:**
- `AlmaValidationError` — If `library_code` is empty or not a string.
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
desks = config.list_circ_desks("<library_code>")
for desk in desks:
    print(f"{desk.get('code')}: {desk.get('name')}")
```

---

#### get_circ_desk

Gets configuration details for a single circulation desk.

**Signature:**
```python
def get_circ_desk(
    self, library_code: str, circ_desk_code: str
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `library_code` | str | Yes | The Alma library code that owns the circ desk |
| `circ_desk_code` | str | Yes | The circulation-desk code |

**Returns:** `Dict[str, Any]` — The circ-desk configuration dict as returned by Alma.

**Raises:**
- `AlmaValidationError` — If either code is empty or not a string.
- `AlmaAPIError` — If the API request fails (including 404 when the circ desk does not exist).

**Example:**
```python
desk = config.get_circ_desk("<library_code>", "<circ_desk_code>")
print(f"Desk: {desk.get('name')}")
```

---

### Locations CRUD (issue #25)

#### list_locations

Lists all locations configured for a given library.

**Signature:**
```python
def list_locations(self, library_code: str) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `library_code` | str | Yes | The Alma library code whose locations to list |

**Returns:** `List[Dict[str, Any]]` — List of location dicts as returned by Alma. Empty list when the library has no locations configured.

**Raises:**
- `AlmaValidationError` — If `library_code` is empty or not a string.
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
locations = config.list_locations("<library_code>")
for loc in locations:
    print(f"{loc.get('code')}: {loc.get('name')}")
```

---

#### get_location

Gets configuration details for a single location. **Location codes are unique per library, not globally** — always supply both codes.

**Signature:**
```python
def get_location(
    self, library_code: str, location_code: str
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `library_code` | str | Yes | The Alma library code that owns the location |
| `location_code` | str | Yes | The location code (unique within `library_code`) |

**Returns:** `Dict[str, Any]` — The location configuration dict as returned by Alma.

**Raises:**
- `AlmaValidationError` — If either code is empty or not a string.
- `AlmaAPIError` — If the API request fails (including 404 when the location does not exist within the library).

**Example:**
```python
location = config.get_location("<library_code>", "<location_code>")
print(f"Name: {location.get('name')}")
print(f"Type: {location.get('type', {}).get('value')}")
```

---

#### create_location

Creates a new location within a library. The body Alma expects is the location object directly (not wrapped). Required keys: `code`, `name`, `type`.

**Signature:**
```python
def create_location(
    self, library_code: str, location_data: Dict[str, Any]
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `library_code` | str | Yes | The Alma library code the new location will belong to |
| `location_data` | Dict[str, Any] | Yes | Location object payload — must include `code`, `name`, `type` |

The `type` field may be either a bare string (`"OPEN"`) or the canonical `{"value": "OPEN"}` dict shape Alma returns on reads.

**Returns:** `AlmaResponse` — Response wrapping the create response. The created location body lives on `response.data`.

**Raises:**
- `AlmaValidationError` — If `library_code` is empty / not a string, or `location_data` is empty / not a dict / missing any required field.
- `AlmaAPIError` — On API failure.

**Example:**
```python
response = config.create_location(
    "<library_code>",
    {
        "code": "<location_code>",
        "name": "Main Stacks",
        "type": {"value": "OPEN"},
    },
)
created_code = response.data.get("code")
```

---

#### update_location

Updates an existing location's metadata. **Alma expects a complete location object** — read the current location with `get_location`, mutate the fields you want to change, and pass the whole dict here.

**Signature:**
```python
def update_location(
    self,
    library_code: str,
    location_code: str,
    location_data: Dict[str, Any],
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `library_code` | str | Yes | The Alma library code that owns the location |
| `location_code` | str | Yes | The location code to update |
| `location_data` | Dict[str, Any] | Yes | Full location object payload |

**Returns:** `AlmaResponse` — Response wrapping the updated location object.

**Raises:**
- `AlmaValidationError` — If either code is empty / not a string, or `location_data` is empty / not a dict.
- `AlmaAPIError` — On API failure.

**Example:**
```python
info = config.get_location("<library_code>", "<location_code>")
info["name"] = "Main Stacks (renamed)"
response = config.update_location(
    "<library_code>", "<location_code>", info
)
```

---

#### delete_location

Deletes a location. Alma rejects the delete with a typed 4xx error when the location still has linked items (or holdings).

**Signature:**
```python
def delete_location(
    self, library_code: str, location_code: str
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `library_code` | str | Yes | The Alma library code that owns the location |
| `location_code` | str | Yes | The location code to delete |

**Returns:** `AlmaResponse` — Response wrapping the delete response. Alma typically returns an empty body on a successful delete.

**Raises:**
- `AlmaValidationError` — If either code is empty / not a string.
- `AlmaAPIError` — On API failure (e.g. when the location has linked items the API surface refuses to orphan).

**Example:**
```python
try:
    config.delete_location("<library_code>", "<location_code>")
    print("Location deleted")
except AlmaAPIError as e:
    print(f"Delete refused: {e}")
```

---

### Code Tables (issue #26)

#### list_code_tables

Lists all code tables configured in the Alma institution.

**Signature:**
```python
def list_code_tables(self) -> List[Dict[str, Any]]
```

**Returns:** `List[Dict[str, Any]]` — List of code-table summary dicts (typically containing `name`, `description`, `sub_system`, etc.).

**Raises:**
- `AlmaAPIError` — If the API request fails.

**Note:** The endpoint takes no `scope` filter — the Alma documentation does not advertise one, so this method intentionally exposes no filter parameters.

**Example:**
```python
tables = config.list_code_tables()
for table in tables:
    print(f"{table.get('name')}: {table.get('description')}")
```

---

#### get_code_table

Gets a single code table including all of its rows.

**Signature:**
```python
def get_code_table(self, code_table_name: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code_table_name` | str | Yes | The Alma code-table name (e.g. `<code_table_name>`) |

**Returns:** `Dict[str, Any]` — The full code-table object as returned by Alma. Includes metadata (`name`, `description`, `sub_system`, etc.) and a top-level `row` array of entries.

**Response-shape note:** The entries live at the top-level `row` key (singular), NOT wrapped in `rows.row`. Access via `table["row"]`.

**Raises:**
- `AlmaValidationError` — If `code_table_name` is empty or not a string.
- `AlmaAPIError` — If the API request fails (including 400 with Alma error code `90101` for an unknown table name).

**Example:**
```python
table = config.get_code_table("<code_table_name>")
for row in table.get("row", []):
    print(f"{row.get('code')}: {row.get('description')}")
```

---

#### update_code_table

Replaces an entire code table. **The PUT replaces the entire table — it is NOT a partial update.** Rows omitted from the request body are dropped from the table.

**Signature:**
```python
def update_code_table(
    self, code_table_name: str, code_table_data: Dict[str, Any]
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code_table_name` | str | Yes | The Alma code-table name |
| `code_table_data` | Dict[str, Any] | Yes | Full code-table object payload |

**Returns:** `AlmaResponse` — Response wrapping the updated code-table object.

**Raises:**
- `AlmaValidationError` — If `code_table_name` is empty / not a string, or `code_table_data` is empty / not a dict.
- `AlmaAPIError` — On API failure (notable codes: `90100`, `90101`, `90102`, `90121`, `90122`, `90123`).

**Example:**
```python
table = config.get_code_table("<code_table_name>")
# Mutate rows in place — e.g. flip a row's enabled flag.
for row in table.get("row", []):
    if row.get("code") == "<row_code>":
        row["enabled"] = {"value": "false"}
response = config.update_code_table("<code_table_name>", table)
```

---

### Mapping Tables (issue #27)

#### list_mapping_tables

Lists all mapping tables configured in the Alma institution.

**Signature:**
```python
def list_mapping_tables(self) -> List[Dict[str, Any]]
```

**Returns:** `List[Dict[str, Any]]` — List of mapping-table summary dicts.

**Raises:**
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
tables = config.list_mapping_tables()
print(f"Configured mapping tables: {len(tables)}")
```

---

#### get_mapping_table

Gets a single mapping table including all of its rows.

**Signature:**
```python
def get_mapping_table(self, mapping_table_name: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mapping_table_name` | str | Yes | The Alma mapping-table name |

**Returns:** `Dict[str, Any]` — The full mapping-table object as returned by Alma. Includes metadata and a top-level `row` array of entries.

**Response-shape note:** Entries live at the top-level `row` key (singular). Access via `table["row"]`.

**Raises:**
- `AlmaValidationError` — If `mapping_table_name` is empty or not a string.
- `AlmaAPIError` — If the API request fails (including 400 with Alma error code `90101` for an unknown table name).

**Example:**
```python
table = config.get_mapping_table("<mapping_table_name>")
for row in table.get("row", []):
    print(f"{row.get('column0')} -> {row.get('column1')}")
```

---

#### update_mapping_table

Replaces an entire mapping table. **The PUT replaces the entire table — it is NOT a partial update.** Rows omitted from the request body are dropped from the table.

**Signature:**
```python
def update_mapping_table(
    self,
    mapping_table_name: str,
    mapping_table_data: Dict[str, Any],
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mapping_table_name` | str | Yes | The Alma mapping-table name |
| `mapping_table_data` | Dict[str, Any] | Yes | Full mapping-table object payload |

**Returns:** `AlmaResponse` — Response wrapping the updated mapping-table object.

**Raises:**
- `AlmaValidationError` — If `mapping_table_name` is empty / not a string, or `mapping_table_data` is empty / not a dict.
- `AlmaAPIError` — On API failure (notable codes: `90101`, `90102`, `90121`, `90123`, `90126`, `90127`).

**Example:**
```python
table = config.get_mapping_table("<mapping_table_name>")
for row in table.get("row", []):
    if row.get("column0") == "<row_key>":
        row["enabled"] = {"value": "false"}
response = config.update_mapping_table("<mapping_table_name>", table)
```

---

### Deposit + Import Profiles (issue #30)

#### list_deposit_profiles

Lists all deposit profiles configured in the Alma institution.

**Signature:**
```python
def list_deposit_profiles(self) -> List[Dict[str, Any]]
```

**Returns:** `List[Dict[str, Any]]` — List of deposit-profile dicts as returned by Alma.

**Raises:**
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
profiles = config.list_deposit_profiles()
for profile in profiles:
    print(f"{profile.get('id')}: {profile.get('name')}")
```

---

#### get_deposit_profile

Gets configuration details for a single deposit profile.

**Signature:**
```python
def get_deposit_profile(self, deposit_profile_id: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `deposit_profile_id` | str | Yes | The Alma deposit-profile identifier |

**Returns:** `Dict[str, Any]` — The deposit-profile configuration dict.

**Raises:**
- `AlmaValidationError` — If `deposit_profile_id` is empty or not a string.
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
profile = config.get_deposit_profile("<deposit_profile_id>")
print(f"Profile name: {profile.get('name')}")
```

---

#### list_import_profiles

Lists all metadata-import profiles configured in the institution.

**Signature:**
```python
def list_import_profiles(self) -> List[Dict[str, Any]]
```

**Returns:** `List[Dict[str, Any]]` — List of import-profile dicts as returned by Alma.

**Raises:**
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
profiles = config.list_import_profiles()
for profile in profiles:
    print(f"{profile.get('id')}: {profile.get('name')}")
```

---

#### get_import_profile

Gets configuration details for a single metadata-import profile.

**Signature:**
```python
def get_import_profile(self, profile_id: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `profile_id` | str | Yes | The Alma metadata-import-profile identifier |

**Returns:** `Dict[str, Any]` — The import-profile configuration dict.

**Raises:**
- `AlmaValidationError` — If `profile_id` is empty or not a string.
- `AlmaAPIError` — If the API request fails (notable code: `401871`, "Failed to find the Profile ID.").

**Example:**
```python
profile = config.get_import_profile("<import_profile_id>")
print(f"Profile name: {profile.get('name')}")
```

---

### Letters + Printers (issue #33)

#### list_letters

Lists all letters configured in the Alma institution. Letters define the templates Alma uses to render notifications (overdue, hold-pickup, fulfillment, etc.).

**Signature:**
```python
def list_letters(self) -> List[Dict[str, Any]]
```

**Returns:** `List[Dict[str, Any]]` — List of letter dicts as returned by Alma.

**Raises:**
- `AlmaAPIError` — If the API request fails (notable code: `60344`, "Problem retrieving letter data.").

**Example:**
```python
letters = config.list_letters()
for letter in letters:
    print(f"{letter.get('code')}: {letter.get('description')}")
```

---

#### get_letter

Gets a single letter's full configuration including its template.

**Signature:**
```python
def get_letter(self, letter_code: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `letter_code` | str | Yes | The Alma letter code (e.g. `<letter_code>`) |

**Returns:** `Dict[str, Any]` — The full letter object as returned by Alma. Includes `subject`, `body`, `description`, `enabled`, `letter_name`, and the `letter_template_xsl` payload that holds the XSL template.

**Raises:**
- `AlmaValidationError` — If `letter_code` is empty or not a string.
- `AlmaAPIError` — If the API request fails (notable codes: `60344`, `40166411`).

**Example:**
```python
letter = config.get_letter("<letter_code>")
print(f"Subject: {letter.get('subject')}")
print(f"Enabled: {letter.get('enabled', {}).get('value')}")
```

---

#### update_letter

Replaces an entire letter template. **The PUT replaces the entire letter — it is NOT a partial update.** Fields omitted from the request body are dropped from the letter.

**Signature:**
```python
def update_letter(
    self, letter_code: str, letter_data: Dict[str, Any]
) -> AlmaResponse
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `letter_code` | str | Yes | The Alma letter code |
| `letter_data` | Dict[str, Any] | Yes | Full letter object payload |

**Returns:** `AlmaResponse` — Response wrapping the updated letter object.

**Raises:**
- `AlmaValidationError` — If `letter_code` is empty / not a string, or `letter_data` is empty / not a dict.
- `AlmaAPIError` — On API failure (notable codes: `60105`, `60343`, `60344`, `40166411`).

**XML-only endpoint:** The Alma letters PUT endpoint is XML-only — it rejects JSON with Alma error code `60105` ("JSON is not supported for this API."). This method serialises `letter_data` to XML internally before sending and forces an `application/json` `Accept` header so the response is still parsed as JSON into `AlmaResponse.data`. Callers pass and receive Python dicts; the XML conversion is an implementation detail. (Resolved by issue #114, 2026-05-08.)

**Derived/read-only fields:** Some letter fields are derived/read-only on Alma's side — notably `description`, which is sourced from the labels code-table mapping rather than stored on the letter object. Mutating such fields yields a `200` response but no observable change. The mutable surface includes `enabled`, `customized`, `channel`, and the XSL template body itself.

**Example:**
```python
letter = config.get_letter("<letter_code>")
letter["subject"] = "Overdue notice - please return"
response = config.update_letter("<letter_code>", letter)
```

---

#### list_printers

Lists all printers configured in the Alma institution.

**Signature:**
```python
def list_printers(self) -> List[Dict[str, Any]]
```

**Returns:** `List[Dict[str, Any]]` — List of printer dicts as returned by Alma.

**Raises:**
- `AlmaAPIError` — If the API request fails (notable codes: `402469`, `40166410`).

**Example:**
```python
printers = config.list_printers()
for printer in printers:
    print(f"{printer.get('id')}: {printer.get('name')}")
```

---

#### get_printer

Gets configuration details for a single printer.

**Signature:**
```python
def get_printer(self, printer_id: str) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `printer_id` | str | Yes | The Alma printer identifier |

**Returns:** `Dict[str, Any]` — The printer configuration dict.

**Raises:**
- `AlmaValidationError` — If `printer_id` is empty or not a string.
- `AlmaAPIError` — If the API request fails (notable code: `402899`, "Invalid Printer ID.").

**Example:**
```python
printer = config.get_printer("<printer_id>")
print(f"Printer: {printer.get('name')}")
```

---

### Workflows + Utilities (issue #35)

#### run_workflow

Executes a configured Alma workflow.

**Signature:**
```python
def run_workflow(
    self,
    workflow_id: str,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]
```

**WARNING:** This method actually triggers an Alma workflow. Side effects depend entirely on the workflow's configuration — a workflow can mutate records, send notifications, kick off long-running jobs, etc. Test against a known-safe `workflow_id` only; never bind this method to untrusted input.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workflow_id` | str | Yes | The Alma workflow identifier to execute |
| `parameters` | Dict[str, Any] | No | Workflow-specific parameter payload. When `None`, no body is sent. |

**Returns:** `Dict[str, Any]` — The parsed response dict from Alma. Typically a workflow-instance object containing at least an instance id and a status code.

**Raises:**
- `AlmaValidationError` — If `workflow_id` is empty or not a string.
- `AlmaAPIError` — On API failure (notable codes: `450001`, `450002`, `450003`, `450004`).

**Example:**
```python
result = config.run_workflow(
    "<workflow_id>",
    {"input_param": "value"},
)
instance_id = result.get("id")
```

---

#### get_fee_transactions_report

Fetches the Alma fee-transactions report. The endpoint accepts a flexible set of filters; rather than enumerate them in the signature this method forwards arbitrary keyword args verbatim as query parameters.

**Signature:**
```python
def get_fee_transactions_report(self, **filters: Any) -> List[Dict[str, Any]]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `**filters` | Any | No | Arbitrary query-parameter filters forwarded to Alma |

Common filters per the Alma docs:

- `status` (str): transaction status filter
- `library` (str): library code to scope the report
- `from_date` (str): inclusive lower bound (YYYY-MM-DD)
- `to_date` (str): inclusive upper bound (YYYY-MM-DD)
- `transaction_type` (str): transaction-type filter

**Returns:** `List[Dict[str, Any]]` — List of fee-transaction dicts as returned by Alma.

**Raises:**
- `AlmaAPIError` — If the API request fails (notable codes: `401652`, `40166410`, `40166413`).

**Example:**
```python
transactions = config.get_fee_transactions_report(
    library="<library_code>",
    from_date="2026-01-01",
    to_date="2026-01-31",
)
print(f"Found {len(transactions)} transactions")
```

---

#### get_general_configuration

Gets the institution's general configuration. Alma surfaces fields like `institution`, `default_language`, `default_currency`, `timezone`, etc. directly at the top level of the response.

**Signature:**
```python
def get_general_configuration(self) -> Dict[str, Any]
```

**Returns:** `Dict[str, Any]` — The general-configuration dict as returned by Alma. Returns an empty dict if Alma returns an empty body.

**Raises:**
- `AlmaAPIError` — If the API request fails.

**Example:**
```python
general = config.get_general_configuration()
print(f"Default language: {general.get('default_language', {}).get('value')}")
print(f"Default currency: {general.get('default_currency', {}).get('value')}")
print(f"Timezone: {general.get('timezone', {}).get('value')}")
```

## Common Workflows

### Discover Libraries Before Drilling Down

Always start by listing libraries so downstream code knows which `<library_code>` values to pass.

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration

client = AlmaAPIClient('SANDBOX')
config = Configuration(client)

# Step 1: List libraries to learn what codes exist
libraries = config.list_libraries()

# Step 2: For each library, fetch its locations and circ desks
for lib in libraries:
    lib_code = lib.get("code")
    lib_name = lib.get("name")
    print(f"\nLibrary: {lib_code} ({lib_name})")

    locations = config.list_locations(lib_code)
    print(f"  Locations: {len(locations)}")
    for loc in locations:
        print(f"    - {loc.get('code')}: {loc.get('name')}")

    desks = config.list_circ_desks(lib_code)
    print(f"  Circ desks: {len(desks)}")
    for desk in desks:
        print(f"    - {desk.get('code')}: {desk.get('name')}")
```

### Edit a Code-Table Row (Read-Modify-Write)

Code tables and mapping tables use the same read-modify-write pattern. **Never construct a fresh payload from scratch** — always start from a `get_code_table` / `get_mapping_table` response.

```python
from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.configuration import Configuration

def disable_code_table_row(
    table_name: str, row_code: str, dry_run: bool = True
):
    """Flip a single row's enabled flag without disturbing the rest."""
    client = AlmaAPIClient('SANDBOX')
    config = Configuration(client)

    # Step 1: Read the full table (including every row)
    table = config.get_code_table(table_name)

    # Step 2: Mutate the target row in place
    rows = table.get("row") or []
    target = None
    for row in rows:
        if row.get("code") == row_code:
            target = row
            break

    if target is None:
        print(f"Row '{row_code}' not found in table {table_name}")
        return

    current_state = target.get("enabled", {}).get("value")
    print(f"Row '{row_code}' currently enabled={current_state}")

    target["enabled"] = {"value": "false"}

    if dry_run:
        print(f"[DRY RUN] Would disable row '{row_code}' in {table_name}")
        return

    # Step 3: PUT the entire table back
    try:
        config.update_code_table(table_name, table)
        print(f"Disabled row '{row_code}' in {table_name}")
    except AlmaAPIError as e:
        print(f"Update failed: {e}")

# Run
disable_code_table_row("<code_table_name>", "<row_code>", dry_run=True)
```

### Update a Letter Template

Letters require the same read-modify-write discipline as code tables; on top of that, the PUT is XML-only — the domain class handles the serialisation transparently.

```python
from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.configuration import Configuration

def update_letter_subject(
    letter_code: str, new_subject: str, dry_run: bool = True
):
    """Change a letter's subject line, leaving the rest of the template alone."""
    client = AlmaAPIClient('SANDBOX')
    config = Configuration(client)

    # Step 1: Read the full letter (subject + XSL body + flags)
    letter = config.get_letter(letter_code)

    current_subject = letter.get("subject")
    print(f"Current subject: {current_subject}")

    letter["subject"] = new_subject

    if dry_run:
        print(f"[DRY RUN] Would set subject to: {new_subject}")
        return

    # Step 2: PUT the entire letter back (XML serialisation is automatic)
    try:
        config.update_letter(letter_code, letter)
        print(f"Updated letter {letter_code}")
    except AlmaAPIError as e:
        print(f"Update failed: {e}")

# Run
update_letter_subject(
    "<letter_code>",
    "Overdue notice - please return",
    dry_run=True,
)
```

### Audit Fee Transactions for a Date Range

```python
from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration

def audit_fees(library_code: str, from_date: str, to_date: str):
    """Pull a per-library, per-date-range fee-transactions report."""
    client = AlmaAPIClient('PRODUCTION')
    config = Configuration(client)

    transactions = config.get_fee_transactions_report(
        library=library_code,
        from_date=from_date,
        to_date=to_date,
    )

    print(f"Found {len(transactions)} transactions for {library_code}")
    total = 0.0
    for tx in transactions:
        amount = float(tx.get("amount") or 0.0)
        total += amount
    print(f"Total: {total:.2f}")

# Run
audit_fees("<library_code>", "2026-01-01", "2026-01-31")
```

## Best Practices and Gotchas

### Best Practices

1. **Discover libraries first**

   ```python
   # Good: List libraries so you know what codes exist
   libraries = config.list_libraries()
   library_codes = [lib.get("code") for lib in libraries]
   ```

2. **Always read-modify-write for tables and letters**

   ```python
   # Good: Start from the live shape
   table = config.get_code_table(table_name)
   table["row"][0]["enabled"] = {"value": "false"}
   config.update_code_table(table_name, table)

   # Bad: Construct a fresh payload from memory
   # config.update_code_table(table_name, {"row": [{"code": "X"}]})  # drops every other row
   ```

3. **Test in SANDBOX before PRODUCTION**

   ```python
   # Development
   client = AlmaAPIClient('SANDBOX')

   # Only after validation
   client = AlmaAPIClient('PRODUCTION')
   ```

4. **Treat `run_workflow` as a side-effecting operation**

   ```python
   # Good: Restrict to a known-safe workflow id from a whitelist
   SAFE_WORKFLOWS = {"<workflow_id>"}
   if workflow_id not in SAFE_WORKFLOWS:
       raise ValueError(f"Refusing to run unrecognised workflow {workflow_id}")
   config.run_workflow(workflow_id, parameters)
   ```

5. **Use the typed errors that come back**

   ```python
   from almaapitk.client.AlmaAPIClient import AlmaAPIError, AlmaValidationError

   try:
       config.get_location("<library_code>", "<location_code>")
   except AlmaValidationError as e:
       # Pre-flight validation: caller passed an empty code
       ...
   except AlmaAPIError as e:
       # Alma rejected the request; e.alma_code / e.tracking_id are populated
       ...
   ```

### Gotchas

1. **Location codes are unique per library, not globally**

   The same `<location_code>` may be reused across libraries. Always supply both `library_code` and `location_code` when reading, updating, or deleting a location.

2. **Letter updates are XML-only**

   The Alma letters PUT endpoint rejects JSON with Alma error code `60105`. `update_letter` handles the XML serialisation transparently — callers pass and receive Python dicts — but understand that under the hood the request body crosses the wire as XML.

3. **Some letter fields are derived/read-only**

   `description` is sourced from the labels code-table mapping, not stored on the letter object. Mutating it on the way in yields a `200` response but no observable change. The mutable surface is `enabled`, `customized`, `channel`, and the XSL template body itself.

4. **Code/mapping table PUTs are full replacements**

   The PUT replaces the entire table — Alma does not support partial updates. Rows omitted from the request body are dropped from the table. Always start from a `get_code_table` / `get_mapping_table` response.

5. **The code-table / mapping-table response shape is `row`, not `rows.row`**

   Entries live at the top-level `row` key (singular). Access via `table["row"]`. This differs from some other Alma list endpoints whose wrapper is `{"rows": {"row": [...]}}`.

6. **Location deletes fail when items are still linked**

   Alma rejects `delete_location` with a typed 4xx error when the location still has linked items or holdings. This method does NOT swallow that error — the `AlmaAPIError` propagates verbatim so callers can surface Alma's own diagnostic to the operator.

7. **`run_workflow` has real side effects**

   Workflows can mutate records, send notifications, and kick off long-running jobs. Never bind this method to untrusted input; restrict it to a whitelist of known-safe workflow ids.

8. **Single-record list responses normalise to a one-item list**

   Alma's list endpoints occasionally return a single record as a dict (rather than a one-item list). All `list_*` methods in this domain normalise that to `[<record>]` for caller convenience — you can always iterate the result.

## Alma API Reference

### Endpoints Used

| Endpoint | Description |
|----------|-------------|
| `GET /almaws/v1/conf/libraries` | List all libraries |
| `GET /almaws/v1/conf/libraries/{libraryCode}` | Get one library |
| `GET /almaws/v1/conf/departments` | List all departments |
| `GET /almaws/v1/conf/libraries/{libraryCode}/circ-desks` | List circ desks for a library |
| `GET /almaws/v1/conf/libraries/{libraryCode}/circ-desks/{circDeskCode}` | Get one circ desk |
| `GET /almaws/v1/conf/libraries/{libraryCode}/locations` | List locations for a library |
| `GET /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}` | Get one location |
| `POST /almaws/v1/conf/libraries/{libraryCode}/locations` | Create a location |
| `PUT /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}` | Update a location |
| `DELETE /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}` | Delete a location |
| `GET /almaws/v1/conf/code-tables` | List all code tables |
| `GET /almaws/v1/conf/code-tables/{codeTableName}` | Get one code table |
| `PUT /almaws/v1/conf/code-tables/{codeTableName}` | Replace a code table |
| `GET /almaws/v1/conf/mapping-tables` | List all mapping tables |
| `GET /almaws/v1/conf/mapping-tables/{mappingTableName}` | Get one mapping table |
| `PUT /almaws/v1/conf/mapping-tables/{mappingTableName}` | Replace a mapping table |
| `GET /almaws/v1/conf/deposit-profiles` | List all deposit profiles |
| `GET /almaws/v1/conf/deposit-profiles/{deposit_profile_id}` | Get one deposit profile |
| `GET /almaws/v1/conf/md-import-profiles` | List all metadata-import profiles |
| `GET /almaws/v1/conf/md-import-profiles/{profile_id}` | Get one metadata-import profile |
| `GET /almaws/v1/conf/letters` | List all letters |
| `GET /almaws/v1/conf/letters/{letterCode}` | Get one letter |
| `PUT /almaws/v1/conf/letters/{letterCode}` | Replace a letter (XML-only) |
| `GET /almaws/v1/conf/printers` | List all printers |
| `GET /almaws/v1/conf/printers/{printer_id}` | Get one printer |
| `POST /almaws/v1/conf/workflows/{workflow_id}` | Trigger a workflow |
| `GET /almaws/v1/conf/utilities/fee-transactions` | Fee-transactions report |
| `GET /almaws/v1/conf/general` | General institutional configuration |

### Official Documentation

- **Configuration API**: https://developers.exlibrisgroup.com/alma/apis/conf/
- **Foundation skeleton**: Issue #22 establishes the Configuration domain class.
- **Sibling tickets**: Issues #24–#35 layer concrete endpoint coverage on the foundation. Each method's docstring calls out which issue introduced it.

### API Quirks

1. **Letters PUT is XML-only.** Alma rejects JSON on `PUT /almaws/v1/conf/letters/{letterCode}` with code `60105` ("JSON is not supported for this API."). `update_letter` serialises the caller's dict to XML internally and forces an `Accept: application/json` response header so the dict-in / dict-out contract still holds. Resolved by issue #114 (2026-05-08).

2. **Code-table / mapping-table response shape: `row`, not `rows.row`.** Entries live at the top-level `row` key (singular). Verified live against SANDBOX 2026-05-07.

3. **Code-table / mapping-table list endpoints take no `scope` filter.** The Alma docs do not advertise one and an audit flagged it as undocumented — `list_code_tables` and `list_mapping_tables` intentionally expose no filter parameters.

4. **Location codes are unique per library, not institution-wide.** Always supply both codes when addressing a location.

5. **Some letter fields are derived/read-only.** Notably `description` (sourced from the labels code-table mapping). Mutating it on the way in produces a `200` response but no observable change. The mutable surface is `enabled`, `customized`, `channel`, and the XSL template body.

6. **PUTs replace entire objects.** This applies to code tables, mapping tables, locations, and letters — Alma does not support partial updates. Rows / fields omitted from the request body are dropped.

7. **Single-record list responses come back as a dict.** All `list_*` methods in this domain normalise that to `[<record>]` so callers can always iterate the result.

### Error Codes

| Code | Source | Message | Solution |
|------|--------|---------|----------|
| `60105` | Letters PUT | "JSON is not supported for this API." | Use the domain method — it serialises to XML automatically |
| `60343` | Letters PUT | "The update failed." | Inspect `tracking_id` and re-fetch the letter |
| `60344` | Letters GET / list | "Problem retrieving letter data." | Verify the letter code exists |
| `40166411` | Letters | "Letter code or other parameter is not valid." | Confirm the `<letter_code>` is correct |
| `90100` | Code tables PUT | "Code table name is empty." | Pass a non-empty `code_table_name` |
| `90101` | Code / mapping tables | "Table does not exist." | Confirm the table name |
| `90102` | Code / mapping tables | "Requested table is hidden." | Table is not exposed via the API surface |
| `90121` / `90127` | Code / mapping tables PUT | "Requested table scope is not legal." | Check the `scope` of the table you read back |
| `90122` | Code tables PUT | "Multiple default codes." | Only one row may be marked default |
| `90123` | Code / mapping tables PUT | "Requested table is not customizable." | The table is read-only on Alma's side |
| `90126` | Mapping tables PUT | "Mapping table name is empty." | Pass a non-empty `mapping_table_name` |
| `401652` | Fee-transactions | "An error has occurred in setting circ library or circ desk." | Check the `library` filter |
| `401871` | Import profiles GET | "Failed to find the Profile ID." | Confirm the profile id |
| `402469` | Printers list | "The library code is not valid." | Verify printer scoping params |
| `402899` | Printers GET | "Invalid Printer ID." | Confirm the `<printer_id>` |
| `40166410` | Fee-transactions / printers | "Invalid parameter." | Check date format / filter values |
| `40166413` | Fee-transactions | "An error has occurred in setting transaction type." | Validate `transaction_type` value |
| `450001` | Workflows | "Workflow not found." | Confirm the `<workflow_id>` |
| `450002` | Workflows | "Workflow inactive." | Activate the workflow in the Alma UI first |
| `450003` | Workflows | "Workflow missing trigger node." | Workflow config is incomplete |
| `450004` | Workflows | "Workflow missing trigger configuration." | Workflow config is incomplete |

### Related Resources

- **Error Codes Reference**: `alma-api-expert` skill → `references/error_codes_and_solutions.md`
- **Admin domain** (sets management — separate Configuration surface): `docs/domains/admin.md`
- **Issue #114** (XML body for letters PUT): bug-driven fix; regression test in the chunk that introduced `update_letter`.
- **Coverage expansion spec**: `docs/superpowers/specs/2026-04-30-coverage-expansion-design.md` §5.5 for the recommended pickup order across the Configuration sibling tickets.

---

**Source file**: `/home/hagaybar/projects/AlmaAPITK/src/almaapitk/domains/configuration.py`

**Introduced in**: 0.4.0 (foundation issue #22; concrete methods land in sibling tickets #24–#35)
