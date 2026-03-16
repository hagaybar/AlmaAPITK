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
| **Users** | User management, email operations, batch processing | [View Guide](domains/users.md) |
| **BibliographicRecords** | Bib records, holdings, items, digital representations | [View Guide](domains/bibliographicrecords.md) |
| **Admin** | Sets management (BIB_MMS, USER) | [View Guide](domains/admin.md) |
| **ResourceSharing** | Lending/borrowing requests via Partners API | [View Guide](domains/resourcesharing.md) |

---

## Additional Resources

- [Code Examples](examples.md) - Runnable code examples for all major operations
- [Error Handling](error-handling.md) - Exception types, error codes, and debugging tips
- [Logging Configuration](logging.md) - Logging setup, configuration, and best practices

---

## External Links

- [GitHub Repository](https://github.com/hagaybar/AlmaAPITK)
- [Alma API Documentation](https://developers.exlibrisgroup.com/alma/apis/)
