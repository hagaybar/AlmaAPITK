"""Regression: Alma Lab's Raw console missed wrappers for paths with a trailing slash.

Alma's definition lists ``GET /conf/libraries/{libraryCode}/circ-desks/`` (trailing
slash), while ``Configuration.list_circ_desks`` calls the path without it, so the
endpoint was shown as uncovered. Found by hand on 2026-11-11 in the Raw console.
"""
from almaapitk.lab.endpoints import get_endpoint, wrapped_by


def test_trailing_slash_endpoint_is_marked_wrapped():
    ep = get_endpoint("GET", "/almaws/v1/conf/libraries/{libraryCode}/circ-desks/")
    assert "Configuration.list_circ_desks" in wrapped_by(ep)


# --- found in the PR #239 review, fixed 2026-11-11 ---------------------------

import pytest  # noqa: E402

from almaapitk.lab.capture import SECRET_MASK, is_secret_param, mask_secret_params  # noqa: E402
from almaapitk.lab.runner import InputError, coerce_query  # noqa: E402


def test_masked_credential_is_refused_not_sent():
    """Reopening a call from History shows the password as ``***``; sending that
    would be a failed login at Alma. It must be refused before any request."""
    ep = get_endpoint("POST", "/almaws/v1/users/{user_id}")
    with pytest.raises(InputError) as exc:
        coerce_query(ep, {"op": "auth", "password": SECRET_MASK})
    assert exc.value.field == "password"


def test_analytics_paging_token_is_not_a_secret():
    """``token`` on /analytics/reports is a resumption token, not a credential:
    it must stay visible in evidence so a page can be fetched again."""
    assert not is_secret_param("token")
    assert mask_secret_params({"token": "PAGE-2"}) == {"token": "PAGE-2"}
    assert is_secret_param("password") and is_secret_param("apikey")
