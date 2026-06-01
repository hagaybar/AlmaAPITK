"""R10 regression test for issue #166 — POST must not be auto-retried on 5xx.

The urllib3 ``Retry`` policy mounted on the persistent session (issue #5)
included ``POST`` in ``allowed_methods`` alongside a 5xx status forcelist. POST
is non-idempotent: a 5xx returned *after* Alma has committed a create, followed
by an automatic retry, can produce a duplicate create — e.g. a duplicate invoice,
a known costly Alma hazard already modelled here as ``AlmaDuplicateInvoiceError``
/ error 402459. urllib3's own default deliberately excludes POST.

These tests pin POST out of the retry policy while keeping the idempotent verbs
(GET/PUT/DELETE) retryable on the transient-error band.
"""
from almaapitk.client.AlmaAPIClient import (
    AlmaAPIClient,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_RETRY_TOTAL,
)


def _retry():
    # This is exactly the policy _setup_session mounts on the adapter.
    return AlmaAPIClient._build_retry(DEFAULT_RETRY_TOTAL, DEFAULT_RETRY_BACKOFF_FACTOR)


def test_post_not_retried_on_5xx():
    retry = _retry()
    for status in (500, 502, 503, 504):
        assert retry.is_retry("POST", status) is False, (
            f"POST must not be auto-retried on {status} — a retry after a "
            f"committed create risks a duplicate (issue #166)."
        )


def test_post_not_retried_on_429():
    # Even a rate-limit 429 must not auto-retry POST; the caller decides.
    assert _retry().is_retry("POST", 429) is False


def test_idempotent_verbs_still_retried_on_5xx():
    retry = _retry()
    assert retry.is_retry("GET", 503) is True
    assert retry.is_retry("PUT", 500) is True
    assert retry.is_retry("DELETE", 502) is True
