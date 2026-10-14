"""R10 regression tests for issue #196.

A ``create_user_rs_request`` call hit the client's 60 s read timeout while
Alma went on to create the request. The caller got a raw ``requests``
``ReadTimeout`` (not an ``AlmaAPIError``), could not raise the timeout for
that one call, and had no way to tell whether the request existed.

Covered here:

* ``_request`` wraps ``requests`` timeouts in ``AlmaTimeoutError``, which is
  both an ``AlmaAPIError`` and still a ``requests.exceptions.Timeout``, and
  says whether the request reached Alma (read timeout) or not (connect).
* ``post(..., timeout=)`` and ``create_user_rs_request(..., timeout=)``
  pass a per-call timeout through.
* ``create_user_rs_request(..., reconcile=True)`` adds a marker to the
  request ``note`` and, after a read timeout or a ``402362`` duplicate error,
  finds the request through the linked hold that carries that note; if
  nothing is found, the original error is raised.
"""
import logging
from unittest.mock import MagicMock

import pytest
import requests

from almaapitk import AlmaAPIError, AlmaTimeoutError, AlmaValidationError
from almaapitk.client.AlmaAPIClient import AlmaAPIClient
from almaapitk.domains import users as users_module
from almaapitk.domains.users import Users

_USER = "tau000000"
_BODY = {"title": "T"}


# --- client ------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ALMA_SB_API_KEY", "test-sandbox-key")
    return AlmaAPIClient("SANDBOX")


def test_read_timeout_becomes_alma_timeout_error(client):
    client._session.request = MagicMock(
        side_effect=requests.exceptions.ReadTimeout("read timed out")
    )

    with pytest.raises(AlmaTimeoutError) as excinfo:
        client.post("almaws/v1/users/x/resource-sharing-requests", data={"a": 1})

    err = excinfo.value
    assert isinstance(err, AlmaAPIError)
    assert isinstance(err, requests.exceptions.Timeout)  # old handlers still work
    assert err.request_sent is True
    assert err.method == "POST"


def test_connect_timeout_reports_request_not_sent(client):
    client._session.request = MagicMock(
        side_effect=requests.exceptions.ConnectTimeout("connect timed out")
    )

    with pytest.raises(AlmaTimeoutError) as excinfo:
        client.get("almaws/v1/users/x")

    assert excinfo.value.request_sent is False


def _retries_exhausted(reason):
    """What requests raises when urllib3 retried a GET until it gave up."""
    from urllib3.exceptions import MaxRetryError
    return requests.exceptions.ConnectionError(
        MaxRetryError(None, "/x", reason=reason)
    )


def test_get_read_timeout_after_retries_becomes_alma_timeout_error(client):
    # Found with a live probe: retried GETs surface as ConnectionError,
    # not Timeout, so they slipped past the first version of the wrap.
    from urllib3.exceptions import ReadTimeoutError
    client._session.request = MagicMock(
        side_effect=_retries_exhausted(ReadTimeoutError(None, "/x", "timed out"))
    )

    with pytest.raises(AlmaTimeoutError) as excinfo:
        client.get("almaws/v1/users/x")

    assert excinfo.value.request_sent is True


def test_get_connect_timeout_after_retries_reports_not_sent(client):
    from urllib3.exceptions import ConnectTimeoutError
    client._session.request = MagicMock(
        side_effect=_retries_exhausted(ConnectTimeoutError("timed out"))
    )

    with pytest.raises(AlmaTimeoutError) as excinfo:
        client.get("almaws/v1/users/x")

    assert excinfo.value.request_sent is False


def test_refused_connection_after_retries_is_not_a_timeout(client):
    # urllib3's NewConnectionError subclasses ConnectTimeoutError.
    from urllib3.exceptions import NewConnectionError
    client._session.request = MagicMock(
        side_effect=_retries_exhausted(NewConnectionError(None, "refused"))
    )

    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        client.get("almaws/v1/users/x")

    assert not isinstance(excinfo.value, AlmaTimeoutError)


def test_other_connection_errors_are_left_alone(client):
    client._session.request = MagicMock(
        side_effect=requests.exceptions.ConnectionError("refused")
    )

    with pytest.raises(requests.exceptions.ConnectionError) as excinfo:
        client.get("almaws/v1/users/x")

    assert not isinstance(excinfo.value, AlmaTimeoutError)


def test_post_passes_per_call_timeout(client):
    response = MagicMock(status_code=200, ok=True)
    response.json.return_value = {}
    client._session.request = MagicMock(return_value=response)
    client._handle_response = lambda r: r

    client.post("almaws/v1/x", data={"a": 1}, timeout=180)

    assert client._session.request.call_args.kwargs["timeout"] == 180


# --- create_user_rs_request ---------------------------------------------------
#
# Reconciliation by external_id was dropped: SANDBOX showed Alma replaces the
# POSTed external_id with its own (2026-07-20, re-checked 2026-10-14). What
# does work: every borrowing request creates a linked hold in
# GET /users/{id}/requests whose ``comment`` is the request ``note`` verbatim
# and whose ``resource_sharing.id`` is the borrowing request id.

_RS_ID = "9001"


class _StubClient:
    def __init__(self):
        self.logger = logging.getLogger("test_issue_196")
        self.post = MagicMock()
        self.get = MagicMock()
        self.iter_paged = MagicMock(return_value=iter([]))

    def get_environment(self):
        return "SANDBOX"


def _rs_response(request_id=_RS_ID):
    resp = MagicMock()
    resp.data = {"request_id": request_id}
    return resp


def _hold(comment, rs_id=_RS_ID):
    return {"request_id": "hold-1", "request_type": "HOLD", "comment": comment,
            "resource_sharing": {"id": rs_id}}


def _read_timeout():
    return AlmaTimeoutError("timed out", method="POST",
                            endpoint="e", timeout=60, request_sent=True)


def _sent_note(users):
    return users.client.post.call_args.kwargs["data"]["note"]


@pytest.fixture
def users(monkeypatch):
    monkeypatch.setattr(users_module.time, "sleep", lambda s: None)
    return Users(_StubClient())


def test_create_passes_per_call_timeout(users):
    users.client.post.return_value = _rs_response()

    users.create_user_rs_request(_USER, dict(_BODY), timeout=180)

    assert users.client.post.call_args.kwargs["timeout"] == 180


def test_reconcile_adds_a_marker_to_the_note_without_mutating_input(users):
    users.client.post.return_value = _rs_response()
    body = {"title": "T", "note": "requester note"}

    users.create_user_rs_request(_USER, body, reconcile=True)

    sent = _sent_note(users)
    assert sent.startswith("requester note ")
    assert "almaapitk-" in sent
    assert body["note"] == "requester note"


def test_caller_marker_already_in_note_is_not_added_twice(users):
    users.client.post.return_value = _rs_response()

    users.create_user_rs_request(_USER, {"title": "T", "note": "ref ORD-7"},
                                 reconcile=True, reconcile_marker="ORD-7")

    assert _sent_note(users) == "ref ORD-7"


def test_without_reconcile_body_is_untouched_and_nothing_looked_up(users):
    users.client.post.side_effect = _read_timeout()
    body = dict(_BODY)

    with pytest.raises(AlmaTimeoutError):
        users.create_user_rs_request(_USER, body)

    assert users.client.post.call_args.kwargs["data"] == _BODY
    users.client.iter_paged.assert_not_called()


def test_reconcile_after_read_timeout_returns_the_created_request(users):
    users.client.post.side_effect = _read_timeout()
    # First lookup: Alma still finishing. Second: the linked hold is there.
    users.client.iter_paged.side_effect = lambda *a, **k: iter(
        [_hold(_sent_note(users))] if users.client.iter_paged.call_count > 1 else []
    )
    users.client.get.return_value = _rs_response()

    response = users.create_user_rs_request(_USER, dict(_BODY), reconcile=True)

    assert response.data["request_id"] == _RS_ID
    assert users.client.iter_paged.call_args.args[0] == f"almaws/v1/users/{_USER}/requests"
    assert users.client.get.call_args.args[0].endswith(
        f"/resource-sharing-requests/{_RS_ID}")


def test_reconcile_ignores_holds_with_other_markers(users):
    users.client.post.side_effect = _read_timeout()
    users.client.iter_paged.side_effect = lambda *a, **k: iter(
        [_hold("someone else's note", rs_id="1"), {"comment": None}])

    with pytest.raises(AlmaTimeoutError):
        users.create_user_rs_request(_USER, dict(_BODY), reconcile=True)
    users.client.get.assert_not_called()


def test_reconcile_raises_original_timeout_with_marker_when_never_found(users):
    original = _read_timeout()
    users.client.post.side_effect = original
    users.client.iter_paged.side_effect = lambda *a, **k: iter([])

    with pytest.raises(AlmaTimeoutError) as excinfo:
        users.create_user_rs_request(_USER, dict(_BODY), reconcile=True)

    assert excinfo.value is original
    assert excinfo.value.reconcile_marker in _sent_note(users)
    assert users.client.iter_paged.call_count == users_module.RS_RECONCILE_ATTEMPTS


def test_reconcile_lookup_failure_keeps_the_original_error(users):
    original = _read_timeout()
    users.client.post.side_effect = original
    users.client.iter_paged.side_effect = requests.exceptions.ConnectionError("refused")

    with pytest.raises(AlmaTimeoutError) as excinfo:
        users.create_user_rs_request(_USER, dict(_BODY), reconcile=True)

    assert excinfo.value is original


def test_reconcile_skips_lookup_when_request_never_sent(users):
    users.client.post.side_effect = AlmaTimeoutError(
        "connect", method="POST", endpoint="e", timeout=60, request_sent=False
    )

    with pytest.raises(AlmaTimeoutError):
        users.create_user_rs_request(_USER, dict(_BODY), reconcile=True)
    users.client.iter_paged.assert_not_called()


def test_reconcile_on_duplicate_finds_earlier_attempt_with_same_marker(users):
    users.client.post.side_effect = AlmaAPIError("dup", status_code=400,
                                                 alma_code="402362")
    users.client.iter_paged.side_effect = lambda *a, **k: iter(
        [_hold("earlier attempt ORD-7")])
    users.client.get.return_value = _rs_response()

    response = users.create_user_rs_request(
        _USER, dict(_BODY), reconcile=True, reconcile_marker="ORD-7")

    assert response.data["request_id"] == _RS_ID
    assert users.client.iter_paged.call_count == 1


def test_duplicate_of_someone_elses_request_is_raised(users):
    duplicate = AlmaAPIError("dup", status_code=400, alma_code="402362")
    users.client.post.side_effect = duplicate
    users.client.iter_paged.side_effect = lambda *a, **k: iter([])

    with pytest.raises(AlmaAPIError) as excinfo:
        users.create_user_rs_request(_USER, dict(_BODY), reconcile=True,
                                     reconcile_marker="ORD-7")

    assert excinfo.value is duplicate


def test_find_by_marker_returns_the_rs_request_or_none(users):
    users.client.iter_paged.side_effect = lambda *a, **k: iter([_hold("x ORD-7")])
    users.client.get.return_value = MagicMock(**{"json.return_value": {"request_id": _RS_ID}})

    assert users.find_user_rs_request_by_marker(_USER, "ORD-7")["request_id"] == _RS_ID
    assert users.find_user_rs_request_by_marker(_USER, "ORD-8") is None
