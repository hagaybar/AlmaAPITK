"""Generated SANDBOX test t-39-3 - Users.upload_user_attachment live
round-trip with real mutation (issue #39). STATE-CHANGING — operator-
authorized.

Maps to AC #39 facets:
  - ``upload_user_attachment`` exercised end-to-end against live SANDBOX
    (POST /users/{user_id}/attachments).
  - Round-trip read-after-write: the uploaded attachment is observable
    on the subsequent ``list_user_attachments`` GET, and the returned
    AlmaResponse exposes a non-empty attachment ``id`` on its data
    payload.
  - Wire-shape conformance — the live POST only succeeds end-to-end if
    the wrapper's serialized body shape is what Alma actually accepts.

Operator-authorized live ``upload_user_attachment`` round-trip on the
SANDBOX user supplied via the ``existing_user_primary_id`` fixture.
Generates a tiny, human-recognisable probe HTML file with a UUID-
suffixed marker (so concurrent runs do not collide and so the operator
can identify the artifact in the Alma UI), POSTs it, asserts the
returned ``AlmaResponse`` reports success and exposes an ``id`` on its
data payload, then calls ``list_user_attachments`` and asserts the list
contains an entry whose id matches the upload response's id.

WARNING — STATE-CHANGING WITH NO AUTO-CLEANUP:
   Alma's user-attachments API has no DELETE endpoint (verified live
   2026-05-08). This test uploads a fresh probe attachment on every
   invocation. The operator must manually delete the attachment via
   the Alma staff UI after each run (or accept the accumulation).

   Each run will print the attachment id and file_name at runtime so
   the regression-smoke output makes the cleanup target visible. The
   probe payload is intentionally tiny and human-recognisable
   ("AlmaAPITK regression-smoke probe <UUID>") to make manual deletion
   safe and unambiguous.

The ``try/finally`` in this test is ONLY to clean up the local
temporary file we created on the test runner's disk. The remote Alma
attachment is intentionally NOT cleaned up — there is no API call that
would do so.

Fixture (``existing_user_primary_id``) is loaded at runtime from
``chunks/users-grab-bag-1/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).

DO NOT EDIT by hand. Generated from
``chunks/users-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import uuid

from almaapitk import AlmaAPIClient
from almaapitk.domains.users import Users

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_39_3():
    user_id = _TEST_DATA["existing_user_primary_id"]
    marker = uuid.uuid4().hex[:8]

    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)

    # --- Step 1: synthesise the probe payload -----------------------------
    html_payload = (
        f"<!-- AlmaAPITK regression-smoke probe {marker} - safe to delete -->\n"
        f"<html><body>probe {marker}</body></html>\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=f"_almaapitk_probe_{marker}.html",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(html_payload)
        file_path = tmp.name
    file_basename = os.path.basename(file_path)

    try:
        # --- Step 2: live POST upload ------------------------------------
        upload_response = users.upload_user_attachment(
            user_id,
            file_path,
            attachment_data={
                "type": "GENERAL",
                "note": f"AlmaAPITK regression-smoke probe {marker}",
            },
        )
        assert upload_response is not None
        assert getattr(upload_response, "success", False) is True
        assert upload_response.status_code in (200, 201)
        assert isinstance(upload_response.data, dict)

        attachment_id = upload_response.data.get("id")
        assert attachment_id, (
            "expected an attachment id in the upload response data payload"
        )

        # Print the cleanup target prominently so regression-smoke output
        # makes the operator's manual-delete target unambiguous.
        print(
            f"\n[t-39-3] LEFTOVER ATTACHMENT: user_id={user_id} "
            f"attachment_id={attachment_id} marker={marker} "
            f"file_basename={file_basename}"
        )
        print(
            f"[t-39-3] Manual cleanup required via Alma staff UI; "
            f"file name will contain '{marker}'. "
            f"Alma exposes no DELETE endpoint for user attachments."
        )

        # --- Step 3: read back via list, assert presence -----------------
        attachments = users.list_user_attachments(user_id)
        assert isinstance(attachments, list)

        ids = []
        for entry in attachments:
            if isinstance(entry, dict):
                entry_id = entry.get("id")
                if entry_id is not None:
                    ids.append(str(entry_id))

        assert str(attachment_id) in ids, (
            f"uploaded attachment id {attachment_id!r} not found in list "
            f"of {len(attachments)} attachments — read-after-write "
            f"round-trip failed"
        )
    finally:
        # Local-disk cleanup ONLY. The remote Alma attachment is
        # intentionally NOT cleaned up here — no DELETE endpoint exists.
        try:
            os.unlink(file_path)
        except OSError:
            pass
