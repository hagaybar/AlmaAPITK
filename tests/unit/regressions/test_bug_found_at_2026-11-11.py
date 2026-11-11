"""Regression: Alma Lab's Raw console missed wrappers for paths with a trailing slash.

Alma's definition lists ``GET /conf/libraries/{libraryCode}/circ-desks/`` (trailing
slash), while ``Configuration.list_circ_desks`` calls the path without it, so the
endpoint was shown as uncovered. Found by hand on 2026-11-11 in the Raw console.
"""
from almaapitk.lab.endpoints import get_endpoint, wrapped_by


def test_trailing_slash_endpoint_is_marked_wrapped():
    ep = get_endpoint("GET", "/almaws/v1/conf/libraries/{libraryCode}/circ-desks/")
    assert "Configuration.list_circ_desks" in wrapped_by(ep)
