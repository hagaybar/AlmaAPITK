"""R10 regression test for issue #119 — user_note write shape.

Bug discovered 2026-05-13 during live SANDBOX testing of the
``users-notes`` chunk: ``Users.add_user_note`` (and the matching
``Users.remove_user_notes``) wrote back the modified user object with
``user_note`` wrapped as ``{'user_note': [...]}``. Alma's JSON schema
for the user object declares ``user_note`` as a flat
``List<UserNote>`` — sending a dict where Jackson expects an
``ArrayList`` produces a 400 response with body::

    Cannot deserialize value of type
    `java.util.ArrayList<com.exlibris.alma.ws.jaxb.userwebservice.UserNote>`

The wrapping assumption came from the issue body's claim that the
shape is ``user.user_note.user_note``. The defensive read in
``Users._normalize_user_notes`` happens to handle both forms (so
``list_user_notes`` worked); the write side did not.

These tests pin the *symptom* — the captured PUT body's ``user_note``
field must be a flat ``list[dict]`` whose elements look like
individual note objects. A regression to a wrapper shape is caught by
the type / structure assertions.

Pattern source: ``tests/unit/regressions/test_issue_114.py`` — same
``MockAlmaAPIClient`` / ``MockAlmaResponse`` shape, trimmed to what
these tests need (mocked ``get`` + ``put``).
"""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock


class MockAlmaResponse:
    """Minimal stand-in for ``almaapitk.AlmaResponse``."""

    def __init__(
        self,
        body: Optional[Dict[str, Any]] = None,
        status_code: int = 200,
        success: bool = True,
    ):
        self._body = body if body is not None else {}
        self.status_code = status_code
        self.success = success

    def json(self) -> Dict[str, Any]:
        return self._body

    @property
    def data(self) -> Dict[str, Any]:
        return self._body


class MockAlmaAPIClient:
    """Mock ``AlmaAPIClient`` recording GET + PUT calls for assertion."""

    def __init__(self, environment: str = "SANDBOX") -> None:
        self.environment = environment
        self.logger = MagicMock()
        self.get_response: MockAlmaResponse = MockAlmaResponse()
        self.put_response: MockAlmaResponse = MockAlmaResponse()
        self.calls: Dict[str, list] = {"get": [], "put": []}

    def get_environment(self) -> str:
        return self.environment

    def test_connection(self) -> bool:
        return True

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> MockAlmaResponse:
        self.calls["get"].append({"endpoint": endpoint, "params": params})
        return self.get_response

    def put(
        self,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> MockAlmaResponse:
        self.calls["put"].append(
            {
                "endpoint": endpoint,
                "data": data,
                "params": params,
                "content_type": content_type,
                "custom_headers": custom_headers,
            }
        )
        return self.put_response


def _make_user(notes: Any) -> Dict[str, Any]:
    """Return a minimal user-record dict with the given ``user_note`` shape."""
    return {
        "primary_id": "tau-test-119",
        "first_name": "Test",
        "last_name": "User",
        "user_note": notes,
    }


def test_add_user_note_writes_flat_list_shape_regression_119() -> None:
    """R10: ``add_user_note`` must PUT ``user_note`` as a flat list.

    Alma's JSON schema is ``user_note: ArrayList<UserNote>``. Sending
    a dict wrapper triggers ``Cannot deserialize value of type
    java.util.ArrayList<...UserNote>`` and a 400. This test pins the
    fix: the body captured by the mocked PUT must have ``user_note``
    as a flat list of note dicts.
    """
    from almaapitk.domains.users import Users

    client = MockAlmaAPIClient()
    # Alma's GET returns the empty-notes case as a flat list (empirical).
    client.get_response = MockAlmaResponse(body=_make_user(notes=[]))
    users = Users(client)

    users.add_user_note("tau-test-119", note_text="hello", note_type="CIRCULATION")

    assert len(client.calls["put"]) == 1, "expected exactly one PUT call"
    put_body = client.calls["put"][0]["data"]
    assert isinstance(put_body, dict), "PUT body must be a dict"
    assert "user_note" in put_body, "PUT body must carry user_note key"

    notes_field = put_body["user_note"]
    # The whole point of the regression: must be a list, not a dict wrapper.
    assert isinstance(notes_field, list), (
        f"user_note must be a flat list, got {type(notes_field).__name__}: "
        f"{notes_field!r}"
    )
    assert len(notes_field) == 1, "expected one appended note"

    note = notes_field[0]
    assert isinstance(note, dict)
    assert note.get("note_text") == "hello"
    # note_type stays in Alma's value-wrapper form
    nt = note.get("note_type")
    assert isinstance(nt, dict) and nt.get("value") == "CIRCULATION"


def test_add_user_note_preserves_existing_notes_in_flat_list_regression_119() -> None:
    """R10: appending to a user that already has notes preserves them.

    Same write-shape pin, but the input already has notes — confirms
    the fix doesn't accidentally wipe the existing list.
    """
    from almaapitk.domains.users import Users

    existing_notes = [
        {
            "note_type": {"value": "OTHER"},
            "note_text": "earlier note",
            "user_viewable": False,
            "popup_note": False,
        }
    ]
    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_user(notes=existing_notes))
    users = Users(client)

    users.add_user_note("tau-test-119", note_text="appended note")

    put_body = client.calls["put"][0]["data"]
    notes_field = put_body["user_note"]
    assert isinstance(notes_field, list), (
        f"user_note must remain a flat list after append, "
        f"got {type(notes_field).__name__}"
    )
    assert len(notes_field) == 2
    assert notes_field[0].get("note_text") == "earlier note"
    assert notes_field[1].get("note_text") == "appended note"


def test_remove_user_notes_writes_flat_list_shape_regression_119() -> None:
    """R10: ``remove_user_notes`` must PUT ``user_note`` as a flat list.

    Same Jackson rejection applies if the wrapper shape leaks back in
    on the removal path.
    """
    from almaapitk.domains.users import Users

    existing_notes = [
        {
            "note_type": {"value": "CIRCULATION"},
            "note_text": "keep me",
            "user_viewable": False,
            "popup_note": False,
        },
        {
            "note_type": {"value": "CIRCULATION"},
            "note_text": "remove me",
            "user_viewable": False,
            "popup_note": False,
        },
    ]
    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=_make_user(notes=existing_notes))
    users = Users(client)

    users.remove_user_notes(
        "tau-test-119",
        predicate=lambda n: n.get("note_text") == "remove me",
    )

    put_body = client.calls["put"][0]["data"]
    notes_field = put_body["user_note"]
    assert isinstance(notes_field, list), (
        f"user_note must be a flat list after removal, "
        f"got {type(notes_field).__name__}: {notes_field!r}"
    )
    assert len(notes_field) == 1
    assert notes_field[0].get("note_text") == "keep me"


def test_add_user_note_handles_legacy_wrapped_get_shape_regression_119() -> None:
    """Defensive read still works when Alma returns the wrapped shape.

    Some Alma endpoints / older serialisations DO use
    ``user_note: {user_note: [...]}``. The read path
    (``_normalize_user_notes``) must unwrap it, and the write path
    must STILL emit a flat list. This test covers the asymmetric
    case so the write shape never depends on the GET shape.
    """
    from almaapitk.domains.users import Users

    wrapped_get = _make_user(notes={"user_note": [
        {
            "note_type": {"value": "OTHER"},
            "note_text": "legacy note",
            "user_viewable": False,
            "popup_note": False,
        }
    ]})
    client = MockAlmaAPIClient()
    client.get_response = MockAlmaResponse(body=wrapped_get)
    users = Users(client)

    users.add_user_note("tau-test-119", note_text="new")

    put_body = client.calls["put"][0]["data"]
    notes_field = put_body["user_note"]
    assert isinstance(notes_field, list), (
        f"write shape must be flat list even when GET returned wrapped, "
        f"got {type(notes_field).__name__}"
    )
    assert len(notes_field) == 2
