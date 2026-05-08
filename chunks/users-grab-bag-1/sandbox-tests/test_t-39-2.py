"""Generated SANDBOX test t-39-2 - Users user-attachments validation smoke
(issue #39).

Maps to AC #39:
  - "Unit tests cover ... upload with missing file" / input-validation
    contract for the list / get / upload public API surface.
  - "Errors raise ``AlmaValidationError`` (input)..." -- input-
    validation half.

Confirms every input-validation guard added in issue #39 raises
``AlmaValidationError`` BEFORE any HTTP call is issued. Exercises:

  - ``list_user_attachments``  on empty / whitespace / None / non-string
    user_id.
  - ``get_user_attachment``    on empty / None user_id and attachment_id,
    plus non-string attachment_id.
  - ``upload_user_attachment`` on empty / None user_id and file_path,
    plus a path that points at a real, non-existent location on disk
    (which must be rejected with ``AlmaValidationError`` before any
    network call).

The "non-existent file" check creates a real path that does not exist
(``/tmp/almaapitk-nonexistent-<UUID>.bin``) and asserts
``AlmaValidationError`` is raised.

Pure runtime guard exercise; no SANDBOX state is read or mutated.

DO NOT EDIT by hand. Generated from
``chunks/users-grab-bag-1/test-recommendation.json``.
"""
from __future__ import annotations

import os
import uuid

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users


def test_t_39_2():
    client = AlmaAPIClient(environment="SANDBOX")
    users = Users(client)
    errors = {}

    # ---- list_user_attachments guards ---------------------------------
    try:
        users.list_user_attachments("")
    except AlmaValidationError as e:
        errors["list_attachments_empty"] = e

    try:
        users.list_user_attachments("   ")
    except AlmaValidationError as e:
        errors["list_attachments_whitespace"] = e

    try:
        users.list_user_attachments(None)
    except AlmaValidationError as e:
        errors["list_attachments_none"] = e

    try:
        users.list_user_attachments(123)
    except AlmaValidationError as e:
        errors["list_attachments_nonstring"] = e

    # ---- get_user_attachment guards -----------------------------------
    try:
        users.get_user_attachment("", "A")
    except AlmaValidationError as e:
        errors["get_attachment_empty_user"] = e

    try:
        users.get_user_attachment("U", "")
    except AlmaValidationError as e:
        errors["get_attachment_empty_id"] = e

    try:
        users.get_user_attachment(None, "A")
    except AlmaValidationError as e:
        errors["get_attachment_none_user"] = e

    try:
        users.get_user_attachment("U", None)
    except AlmaValidationError as e:
        errors["get_attachment_none_id"] = e

    try:
        users.get_user_attachment("U", 123)
    except AlmaValidationError as e:
        errors["get_attachment_nonstring_id"] = e

    # ---- upload_user_attachment guards --------------------------------
    try:
        users.upload_user_attachment("", "/tmp/probe.html")
    except AlmaValidationError as e:
        errors["upload_empty_user"] = e

    try:
        users.upload_user_attachment(None, "/tmp/probe.html")
    except AlmaValidationError as e:
        errors["upload_none_user"] = e

    try:
        users.upload_user_attachment("U", "")
    except AlmaValidationError as e:
        errors["upload_empty_path"] = e

    try:
        users.upload_user_attachment("U", None)
    except AlmaValidationError as e:
        errors["upload_none_path"] = e

    # Non-existent file path must be rejected by the file-exists guard
    # BEFORE any HTTP call. Build a real path that genuinely does not
    # exist on disk so the guard fires deterministically.
    nonexistent_path = os.path.join(
        "/tmp", f"almaapitk-nonexistent-{uuid.uuid4().hex}.bin"
    )
    assert not os.path.exists(nonexistent_path), (
        "expected the synthesised probe path to not exist on disk"
    )
    try:
        users.upload_user_attachment("U", nonexistent_path)
    except AlmaValidationError as e:
        errors["upload_missing_file"] = e

    # ---- pass-criteria assertions --------------------------------------
    assert "list_attachments_empty" in errors and isinstance(
        errors["list_attachments_empty"], AlmaValidationError
    )
    assert "list_attachments_whitespace" in errors and isinstance(
        errors["list_attachments_whitespace"], AlmaValidationError
    )
    assert "list_attachments_none" in errors and isinstance(
        errors["list_attachments_none"], AlmaValidationError
    )
    assert "list_attachments_nonstring" in errors and isinstance(
        errors["list_attachments_nonstring"], AlmaValidationError
    )
    assert "get_attachment_empty_user" in errors and isinstance(
        errors["get_attachment_empty_user"], AlmaValidationError
    )
    assert "get_attachment_empty_id" in errors and isinstance(
        errors["get_attachment_empty_id"], AlmaValidationError
    )
    assert "get_attachment_none_user" in errors and isinstance(
        errors["get_attachment_none_user"], AlmaValidationError
    )
    assert "get_attachment_none_id" in errors and isinstance(
        errors["get_attachment_none_id"], AlmaValidationError
    )
    assert "get_attachment_nonstring_id" in errors and isinstance(
        errors["get_attachment_nonstring_id"], AlmaValidationError
    )
    assert "upload_empty_user" in errors and isinstance(
        errors["upload_empty_user"], AlmaValidationError
    )
    assert "upload_none_user" in errors and isinstance(
        errors["upload_none_user"], AlmaValidationError
    )
    assert "upload_empty_path" in errors and isinstance(
        errors["upload_empty_path"], AlmaValidationError
    )
    assert "upload_none_path" in errors and isinstance(
        errors["upload_none_path"], AlmaValidationError
    )
    assert "upload_missing_file" in errors and isinstance(
        errors["upload_missing_file"], AlmaValidationError
    )
