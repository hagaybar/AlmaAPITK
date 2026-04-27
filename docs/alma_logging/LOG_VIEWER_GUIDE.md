# Log Viewer Utility Guide

The `view_logs.py` script helps you query and view the detailed JSON logs from AlmaAPITK.

## Quick Start

```bash
# View latest 20 entries from today
python3 view_logs.py

# Show help with all options
python3 view_logs.py --help
```

## Common Use Cases

### 1. View Logs by Domain

```bash
# View only acquisitions logs
python3 view_logs.py --domain acquisitions

# View only API client logs (HTTP layer)
python3 view_logs.py --domain api_client

# View users domain logs
python3 view_logs.py --domain users
```

### 2. Filter by Log Level

```bash
# Show only errors
python3 view_logs.py --level ERROR

# Show only warnings and above
python3 view_logs.py --level WARNING

# Show debug entries
python3 view_logs.py --level DEBUG
```

### 3. Search for Specific Content

```bash
# Search for POL number in any field
python3 view_logs.py --search "POL-12350"

# Search for invoice operations
python3 view_logs.py --search "invoice"

# Search for specific error messages
python3 view_logs.py --search "License Term Type"
```

### 4. Filter by API Endpoint

```bash
# Show all invoice-related API calls
python3 view_logs.py --endpoint "invoices"

# Show POL operations
python3 view_logs.py --endpoint "po-lines"

# Show item operations
python3 view_logs.py --endpoint "items"
```

### 5. Filter by HTTP Method

```bash
# Show only POST requests (creates/updates)
python3 view_logs.py --method POST

# Show only GET requests (reads)
python3 view_logs.py --method GET

# Show only PUT requests (updates)
python3 view_logs.py --method PUT
```

### 6. Filter by HTTP Status Code

```bash
# Show failed requests (400 errors)
python3 view_logs.py --status 400

# Show successful requests
python3 view_logs.py --status 200

# Combine with other filters
python3 view_logs.py --status 400 --endpoint "invoices"
```

### 7. View Full Request/Response Bodies

```bash
# Show complete request/response objects
python3 view_logs.py --show-bodies --limit 5

# Show full response for specific POL
python3 view_logs.py --search "POL-12350" --show-bodies --tail --limit 1

# Show full request body for POST operations
python3 view_logs.py --method POST --show-bodies --limit 3
```

### 8. View Logs from Specific Date

```bash
# View logs from specific date
python3 view_logs.py --date 2025-10-22

# Combine with other filters
python3 view_logs.py --date 2025-10-22 --level ERROR
```

### 9. Control Output Size

```bash
# Show only last 10 entries (most recent)
python3 view_logs.py --tail --limit 10

# Show first 50 entries
python3 view_logs.py --limit 50

# Show all matching entries (careful with large logs!)
python3 view_logs.py --limit 999999
```

### 10. Export Results to File

```bash
# Export filtered logs to JSON file
python3 view_logs.py --search "POL-12350" --output results.json

# Export all errors to file
python3 view_logs.py --level ERROR --output errors.json

# Export specific date range
python3 view_logs.py --date 2025-10-22 --output oct22.json
```

## Advanced Examples

### Debug Failed Invoice Creation

```bash
# Find all invoice operations that failed
python3 view_logs.py --endpoint "invoices" --level ERROR

# Show full request/response for failed invoice POST
python3 view_logs.py --method POST --status 400 --endpoint "invoices" --show-bodies
```

### Track Specific POL Workflow

```bash
# Find all operations for a specific POL
python3 view_logs.py --search "POL-12350"

# Show complete POL data from last retrieval
python3 view_logs.py --search "POL-12350" --show-bodies --tail --limit 1

# Export all POL operations to file for analysis
python3 view_logs.py --search "POL-12350" --output pol_5992_history.json
```

### Review API Performance

```bash
# View all API calls (shows duration_ms in context)
python3 view_logs.py --domain api_client --limit 50

# Find slow operations (search for specific endpoints)
python3 view_logs.py --endpoint "invoices" --domain api_client
```

### Monitor Specific Test Run

```bash
# View all logs from test run (by date and domain)
python3 view_logs.py --date 2025-10-23 --domain acquisitions

# Show errors during test
python3 view_logs.py --date 2025-10-23 --level ERROR

# Export complete test log
python3 view_logs.py --date 2025-10-23 --output test_run.json
```

## Output Format

### Default View (No Bodies)

Shows:
- Timestamp
- Log level (colored)
- Logger name
- Message
- Context summary (without full request/response bodies)

Example:
```
[2025-10-23T12:52:23.564982+00:00] DEBUG    almapi.api_client    API Request: GET almaws/v1/acq/po-lines/POL-12350
  Context: {
    "method": "GET",
    "endpoint": "almaws/v1/acq/po-lines/POL-12350",
    "params": null
  }
```

### With Bodies (`--show-bodies`)

Shows everything including:
- Complete request_data (POST/PUT bodies)
- Complete response_data (full JSON objects)
- Exception tracebacks

Example:
```
[2025-10-23T12:59:42.428284+00:00] DEBUG    almapi.api_client    Response body from almaws/v1/acq/po-lines/POL-12350
  Context: {
    "endpoint": "almaws/v1/acq/po-lines/POL-12350",
    "status_code": 200,
    "response_data": {
      "number": "POL-12350",
      "status": {"value": "SENT", "desc": "Sent"},
      "price": {"sum": "10.0", "currency": {"value": "ILS"}},
      // ... complete POL object with all fields
    }
  }
```

## Color Coding

When output to terminal (not piped or redirected):
- **DEBUG**: Cyan
- **INFO**: Green
- **WARNING**: Yellow
- **ERROR**: Red
- **CRITICAL**: Red background with white text

To disable colors:
```bash
python3 view_logs.py --no-color
```

## Finding Available Dates

If no logs found for today:
```bash
python3 view_logs.py
```

Output shows:
```
No log files found for today (2025-10-23)

Available dates:
  - 2025-10-23
  - 2025-10-22
  - 2025-10-21
```

Then view specific date:
```bash
python3 view_logs.py --date 2025-10-22
```

## Combining Filters

All filters can be combined:

```bash
# Find failed POST operations to invoices endpoint
python3 view_logs.py --method POST --endpoint "invoices" --status 400

# Show last 5 errors from acquisitions domain
python3 view_logs.py --domain acquisitions --level ERROR --tail --limit 5

# Export all POL operations from specific date
python3 view_logs.py --date 2025-10-23 --search "POL" --output pol_ops.json

# Debug specific invoice creation with full bodies
python3 view_logs.py --search "35925542400004146" --show-bodies --output invoice_debug.json
```

## Tips and Best Practices

1. **Start Broad, Then Narrow**
   ```bash
   # First, see what's in the logs
   python3 view_logs.py --limit 50

   # Then filter to what you need
   python3 view_logs.py --search "POL-12350"
   ```

2. **Use `--tail` for Recent Issues**
   ```bash
   # Show last 20 entries (most recent events)
   python3 view_logs.py --tail --limit 20
   ```

3. **Export Before Detailed Analysis**
   ```bash
   # Export filtered logs, then analyze JSON file
   python3 view_logs.py --search "invoice" --output invoice_logs.json
   ```

4. **Check Errors First**
   ```bash
   # Quick error check
   python3 view_logs.py --level ERROR
   ```

5. **Use `--show-bodies` Sparingly**
   - Bodies can be very large
   - Use small limits: `--limit 5`
   - Or export to file: `--output debug.json`

## Integration with Other Tools

### Use with jq for Advanced Queries

```bash
# Extract all endpoints called
python3 view_logs.py --output all.json
cat all.json | jq '.[].context.endpoint' | sort | uniq

# Find slowest operations
cat all.json | jq '.[] | select(.context.duration_ms > 5000)'

# Extract all status codes
cat all.json | jq '.[].context.status_code' | sort | uniq -c
```

### Use with grep for Quick Search

```bash
# Quick text search in log files
grep -r "POL-12350" logs/api_requests/

# Count occurrences
grep -r "invoice" logs/api_requests/ | wc -l
```

### Pipe to less for Browsing

```bash
# Browse large output
python3 view_logs.py --limit 100 | less

# Search within output
python3 view_logs.py --show-bodies | less
# Then press '/' to search in less
```

## Troubleshooting

### No logs found

**Problem**: "No log files found for today"

**Solutions**:
1. Check if any API calls were made today
2. View available dates: `python3 view_logs.py`
3. Check specific date: `python3 view_logs.py --date 2025-10-22`

### Output too large

**Problem**: Too many entries to read

**Solutions**:
1. Use `--limit` to show fewer entries
2. Use filters to narrow results
3. Export to file: `--output results.json`
4. Use `--tail` to show most recent entries

### Colors not showing

**Problem**: Output not colored in terminal

**Solutions**:
1. Colors only work in interactive terminal (not when piped)
2. Check if your terminal supports ANSI colors
3. Disable with `--no-color` if needed

### Missing data in output

**Problem**: Request/response bodies not showing

**Solutions**:
1. Add `--show-bodies` flag
2. Check if data was actually logged (some errors don't have bodies)
3. View raw log file: `cat logs/api_requests/2025-10-23/api_client.log`

## Log File Locations

Logs are organized by date:
```
logs/api_requests/
├── 2025-10-23/
│   ├── api_client.log      # HTTP layer logs
│   ├── acquisitions.log    # Acquisitions domain logs
│   ├── users.log           # Users domain logs
│   └── bibs.log            # Bibs domain logs
├── 2025-10-22/
│   └── ...
└── 2025-10-21/
    └── ...
```

View raw JSON:
```bash
# View raw log file
cat logs/api_requests/2025-10-23/api_client.log

# Pretty print specific entry
cat logs/api_requests/2025-10-23/api_client.log | head -1 | jq .

# Count entries
wc -l logs/api_requests/2025-10-23/api_client.log
```
