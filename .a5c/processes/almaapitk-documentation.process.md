# AlmaAPITK Documentation Process

## Overview

This process generates comprehensive documentation for the AlmaAPITK Python library, covering all public API classes, domain-specific guides, code examples, and operational guides.

## Process ID
`almaapitk-documentation`

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `outputDir` | string | `"docs"` | Output directory for documentation |
| `includeAlmaApiReference` | boolean | `true` | Include Alma API reference links and quirks |
| `targetAudience` | string | `"library-developers"` | Target audience for documentation |

## Outputs

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether documentation was generated successfully |
| `documentationPath` | string | Path to generated documentation |
| `sections` | array | List of documentation sections created |
| `qualityScore` | number | Documentation quality score (0-100) |
| `artifacts` | array | List of generated files |

## Phases

### Phase 1: Codebase Analysis
Analyzes the AlmaAPITK codebase to understand:
- Package structure and version
- Public API exports from `__init__.py`
- Domain classes and their methods
- Configuration requirements

### Phase 2: Getting Started Guide
Creates `getting-started.md` with:
- Prerequisites (Python 3.12+, API keys)
- Installation methods (pip, poetry, GitHub)
- Environment configuration
- Quick start tutorial (5 minutes to first API call)

### Phase 3: API Reference
Creates `api-reference.md` documenting:
- AlmaAPIClient class and methods
- AlmaResponse wrapper class
- Exception classes (AlmaAPIError, AlmaValidationError)
- Utility classes (TSVGenerator)

### Phase 4: Domain Guides (Parallel)
Creates guides for each domain class:
- **Acquisitions** - POL operations, invoicing, item receiving
- **Users** - User management, email operations
- **BibliographicRecords** - Bib records, holdings, items
- **Admin** - Sets management
- **ResourceSharing** - Lending/borrowing requests

Each guide includes method reference, code examples, and Alma API quirks.

**Breakpoint**: Review domain guides before continuing.

### Phase 5: Code Examples
Creates `examples.md` with:
- Basic operations (connect, request, handle response)
- Acquisitions workflows (invoice creation, receiving)
- User operations
- Bibliographic record operations
- Resource sharing examples

### Phase 6: Error Handling Guide
Creates `error-handling.md` covering:
- Exception hierarchy
- HTTP status codes and their meanings
- Alma-specific error codes (from alma-api-expert skill)
- Error handling patterns with code examples

### Phase 7: Logging Configuration
Creates `logging.md` documenting:
- Logger initialization and usage
- Log levels and when to use them
- Log file structure
- Security (API key redaction)

### Phase 8: Quality Validation
Validates documentation quality:
- Completeness (all symbols documented)
- Code examples (runnable, with error handling)
- Clarity (appropriate for developers)
- Technical accuracy (matches actual code)

**Breakpoint**: Review quality score before finalizing.

### Phase 9: Documentation Index
Creates `index.md` as documentation home page with:
- Package overview
- Quick links to all sections
- External links (GitHub, Alma API docs)
- Internal link validation

## Dependencies

### Skills
- `python-dev-expert` - Python coding standards

### Knowledge Sources
- `alma-api-expert` skill - Alma API quirks, error codes, workflows
- Alma Developer Network - Official API documentation

## Quality Gates

1. **Domain Guides Review** (after Phase 4)
   - All 5 domain classes documented
   - Methods include signatures and examples

2. **Quality Score** (after Phase 8)
   - Target: 80+ overall score
   - Completeness: All public API documented
   - Code examples: Runnable and complete
   - Accuracy: Matches source code

## Usage

```bash
# Create and run the process
npx babysitter run:create \
  --process-id almaapitk-documentation \
  --entry ".a5c/processes/almaapitk-documentation.js#process" \
  --inputs ".a5c/processes/almaapitk-documentation-inputs.json" \
  --harness claude-code \
  --json
```
