"""Tools for harvesting Alma error codes from per-domain swagger.

See ``fetch_domain_codes.py`` for the CLI. The harvested JSON lists the
documented error codes per domain; use it to cross-check
``ERROR_CODE_REGISTRY`` coverage when adding or changing domain methods.

Internal developer tooling; not part of the published package.
"""
