---
layout: default
title: Home
---

# AlmaAPITK Documentation

**Version:** 0.2.0 | **Python:** >=3.12 | **License:** MIT

AlmaAPITK is a Python toolkit for interacting with the Ex Libris Alma ILS (Integrated Library System) API. It provides a structured approach to API operations with domain-specific classes, comprehensive error handling, and built-in logging.

---

## Quick Links

- [Getting Started](getting-started.md) - Installation, setup, and first steps
- [API Reference](api-reference.md) - Complete API documentation for all classes and methods

---

## Domain Guides

Detailed documentation for each domain module:

| Domain | Description | Documentation |
|--------|-------------|---------------|
| **Acquisitions** | Invoice management, POL operations, item receiving | [View Guide](domains/acquisitions.md) |
| **Admin** | Sets management (BIB_MMS, USER), full CRUD + member management | [View Guide](domains/admin.md) |
| **Analytics** | Analytics report headers and rows with built-in pagination | _no dedicated guide yet — see [api-reference.md](api-reference.md#analytics)_ |
| **BibliographicRecords** | Bib records, holdings, items, digital representations | [View Guide](domains/bibliographicrecords.md) |
| **Configuration** | Libraries/locations, code tables, letters, mapping tables, deposit/import profiles. **Active growth area** — more endpoints land in each 0.x release | [View Guide](domains/configuration.md) |
| **ResourceSharing** | Lending/borrowing requests via Partners API | [View Guide](domains/resourcesharing.md) |
| **Users** | User management, loans, requests, CRUD, search, email/expiry processing | [View Guide](domains/users.md) |

---

## Additional Resources

- [Code Examples](examples.md) - Runnable code examples for all major operations
- [Error Handling](error-handling.md) - Exception types, error codes, and debugging tips
- [Logging Configuration](logging.md) - Logging setup, configuration, and best practices

---

## External Links

- [GitHub Repository](https://github.com/hagaybar/AlmaAPITK)
- [Alma API Documentation](https://developers.exlibrisgroup.com/alma/apis/)
