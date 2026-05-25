import pytest
import requests

from almaapitk.testing.guards import ReadOnlyViolation, install_readonly_guard


def _session_that_never_calls_network():
    s = requests.Session()
    # Stand-in so a GET that passes the guard does not actually dial out.
    s.request = lambda method, url, **kw: "ok"
    return s


def test_get_is_allowed():
    s = _session_that_never_calls_network()
    install_readonly_guard(s)
    assert s.request("GET", "https://example.test/x") == "ok"


@pytest.mark.parametrize("verb", ["POST", "PUT", "DELETE", "PATCH"])
def test_writes_are_blocked(verb):
    s = _session_that_never_calls_network()
    install_readonly_guard(s)
    with pytest.raises(ReadOnlyViolation):
        s.request(verb, "https://example.test/x")
