"""Tools for harvesting Alma error codes from per-domain swagger.

See ``fetch_domain_codes.py`` for the CLI. The harvested JSON is consumed
by ``.a5c/processes/chunk-template-impl.js`` so each coverage chunk has
documented-error context attached to the implement-agent prompt.

Scoped, internal: the chunk pipeline is the only consumer.
"""
