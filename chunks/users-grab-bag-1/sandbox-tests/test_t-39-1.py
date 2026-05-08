"""Generated SANDBOX test t-39-1 - Users user-attachments read smoke
(issue #39).

Maps to AC #39 facets:
  - ``list_user_attachments`` exercised against live SANDBOX, returns a
    List[Dict] envelope (Alma's ``user_attachment`` wrapper unwrapped).
  - ``get_user_attachment`` (without ``expand``) exercised against live
    SANDBOX when the user has at least one attachment, returns a
    Dict[str, Any] containing an ``id`` key.
  - Methods exist on the existing ``Users`` class (importable / bound).

Calls the read-only attachment methods shipped in issue #39 against
live SANDBOX. Confirms ``list_user_attachments`` returns a list and, if
the list is non-empty, that ``get_user_attachment`` round-trips the
first attachment's id and returns a non-empty Dict[str, Any] containing
an ``id`` key. If the list is empty (the SANDBOX user has no
attachments), the get-step is skipped and only the list-shape assertion
is verified -- the test is still considered pass because the list
endpoint itself responded correctly.

NB: after t-39-3 runs, the list will likely contain the probe upload —
that is fine; this read smoke is shape-only.

No state is mutated. The ``expand`` query-param variants and the upload
round-trip are exercised by t-39-3 / unit tests.

Fixture (``existing_user_primary_id``) is loaded at runtime from
``chunks/users-grab-bag-1/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/users-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_39_1():
    existing_user_primary_id = _TEST_DATA["existing_user_primary_id"]

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)

    # --- list_user_attachments ------------------------------------------
    attachments = users.list_user_attachments(existing_user_primary_id)
    assert isinstance(attachments, list)

    # --- get_user_attachment (only when the list is non-empty) ----------
    if len(attachments) > 0:
        first_attachment = attachments[0]
        assert isinstance(first_attachment, dict)
        attachment_id = first_attachment.get("id")
        if attachment_id:
            attachment_detail = users.get_user_attachment(
                existing_user_primary_id, str(attachment_id)
            )
            assert isinstance(attachment_detail, dict)
            assert "id" in attachment_detail
