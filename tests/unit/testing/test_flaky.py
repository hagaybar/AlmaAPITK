import pytest

from almaapitk import AlmaServerError
from almaapitk.testing.flaky import TransientAPIError, run_with_flaky_tolerance


def test_passes_through_success():
    assert run_with_flaky_tolerance(lambda: 42, retries=2, delay=0) == 42


def test_retries_then_skips_on_transient():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        raise AlmaServerError("boom", status_code=503)

    with pytest.raises(TransientAPIError):
        run_with_flaky_tolerance(flaky, retries=2, delay=0)
    assert calls["n"] == 3  # initial attempt + 2 retries


def test_real_error_propagates():
    def boom():
        raise ValueError("real bug")

    with pytest.raises(ValueError):
        run_with_flaky_tolerance(boom, retries=2, delay=0)
