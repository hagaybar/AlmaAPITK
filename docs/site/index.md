# AlmaAPITK

**A Python toolkit for the Ex Libris Alma ILS REST API.**

AlmaAPITK gives you a clean, typed, domain-oriented client for Alma: a single
`AlmaAPIClient` for transport, focused domain classes for operations, a
consistent `AlmaResponse` wrapper, a structured error hierarchy, and built-in
logging with automatic credential and PII redaction.

[Get started](getting-started.md){ .md-button .md-button--primary }
[API Reference](reference/index.md){ .md-button }

## Install

```bash
pip install almaapitk
```

## Quick example

```python
from almaapitk import AlmaAPIClient, Users

client = AlmaAPIClient("SANDBOX")          # reads ALMA_SB_API_KEY
users = Users(client)

user = users.get_user("<user_primary_id>")
print(user.data["first_name"])
```

## Where to go next

- **[Getting Started](getting-started.md)** — install, configure credentials, make your first calls.
- **[Examples](guides/examples.md)** — runnable snippets for every domain.
- **[Error Handling](guides/error-handling.md)** — the exception hierarchy and Alma error codes.
- **[Logging](guides/logging.md)** — structured logs with automatic redaction.
- **[API Reference](reference/index.md)** — every public class and method, generated from the source docstrings.

## Why AlmaAPITK

- **Client–Domain design** — `AlmaAPIClient` owns transport (sessions, retries, rate limiting); domain classes own operations.
- **Environment-aware** — first-class SANDBOX and PRODUCTION support with per-environment credentials.
- **Consistent responses** — `AlmaResponse` exposes `.data`, `.json()`, and `.success` everywhere.
- **Typed errors** — catch `AlmaValidationError`, `AlmaRateLimitError`, `AlmaAuthenticationError`, and more — all under `AlmaAPIError`.
- **Safe by default** — request/response logging redacts API keys and personal data automatically.
