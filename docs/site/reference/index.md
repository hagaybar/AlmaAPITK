# API Reference

Everything below is generated directly from the source docstrings, so it
**always matches the installed version** of `almaapitk` — no hand-maintained
signatures to drift out of date.

Every symbol is importable from the top-level package:

```python
from almaapitk import AlmaAPIClient, Users, ResourceSharing, AlmaAPIError
```

## Core

- **[Client & Response](client.md)** — `AlmaAPIClient`, `AlmaResponse`
- **[Exceptions](exceptions.md)** — the `AlmaAPIError` hierarchy

## Domains

- **[Users](users.md)** — user records, loans, requests, fees, email updates
- **[Bibliographic Records](bibs.md)** — bibs, holdings, items, collections
- **[Acquisitions](acquisitions.md)** — POLs, invoices, item receiving
- **[Admin (Sets)](admin.md)** — itemized/logical set management
- **[Resource Sharing](resource-sharing.md)** — lending requests via the Partners API
- **[Analytics](analytics.md)** — Analytics report headers and rows
- **[Configuration](configuration.md)** — Configuration API surface

## Utilities

- **[Utilities](utilities.md)** — `TSVGenerator`, citation-metadata enrichment
