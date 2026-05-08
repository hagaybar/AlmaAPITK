"""Generated SANDBOX test t-33-3 - Configuration.update_letter live
round-trip with real mutation (issue #33). STATE-CHANGING — operator-
authorized.

Maps to AC #33 facets:
  - ``update_letter`` exercised end-to-end against live SANDBOX.
  - AlmaResponse return-value contract on PUT (``.success`` flag).
  - Round-trip read-after-write semantics: mutation is observable on
    the subsequent GET, then restored.

Operator-authorized live ``update_letter`` round-trip on the DISABLED
letter ``<disabled_letter_code>``. Reads the original payload, injects
an XML comment (``<!-- AlmaAPITK probe: <UUID> -->``) into the XSL
template body, PUTs the mutated payload, reads back and asserts the
comment is present, then explicitly restores the original payload via
a second PUT and asserts the XSL matches the original byte-for-byte.

Why an XML comment in the XSL body:
  - XML comments are inert at XSL transform time, so even a worst-
    case "restore fails permanently" outcome on the disabled letter
    has zero rendered impact (a disabled letter never emits, and a
    comment doesn't change rendered output anyway).
  - Mutating the comment produces a clearly observable byte-level
    change on the GET response (the marker UUID), so we prove Alma
    actually APPLIED our PUT rather than only accepting a 200.
  - ``description`` looks tempting but is sourced from the labels
    code-table mapping — Alma silently ignores PUTs against it
    (verified live 2026-05-07). The XSL body is genuinely mutable.

Cleanup discipline:
  - The happy path performs an explicit restore (step 5) and asserts
    the XSL matches the original.
  - The ``finally`` block is a mandatory safety net: if the explicit
    restore was not reached (assertion failure mid-test) it retries
    the restore. A failure to restore is re-raised as a HARD test
    failure — permanent mutation of the letter is unacceptable.
  - If ``original`` failed to read in step 1, the test ``assert``
    raises before we enter the ``try`` block — there is nothing to
    restore. That is fine.

History (issue #114):
  - 2026-05-07: original test attempted a description-only mutation
    + try/finally restore. Both PUTs failed with 400 + Alma error
    60105 ('JSON is not supported for this API.'). Test held with
    @pytest.mark.skip pointing to issue #114.
  - 2026-05-08 (issue #114): ``update_letter`` rewritten to send XML
    body and force ``Accept: application/json`` on the response. Live
    PUT works. Skip removed; round-trip upgraded from no-mutation
    re-PUT to a real comment-injection mutation now that Alma
    actually applies our changes.

Fixture (``disabled_letter_code``) is loaded at runtime from
``chunks/config-grab-bag-1/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).
"""
from __future__ import annotations

import json
import pathlib
import re
import uuid

from almaapitk import AlmaAPIClient
from almaapitk.client.AlmaAPIClient import AlmaAPIError
from almaapitk.domains.configuration import Configuration

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_33_3():
    disabled_letter_code = _TEST_DATA["disabled_letter_code"]

    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # --- Step 1: read original (snapshot) --------------------------------
    original = config.get_letter(disabled_letter_code)
    assert isinstance(original, dict) and len(original) > 0
    original_xsl = original.get("xsl") or ""
    assert isinstance(original_xsl, str) and len(original_xsl) > 0, (
        "expected the disabled letter to have a non-empty XSL body"
    )

    # --- Step 2: build mutated payload — inject an XML comment after
    #            the <xsl:stylesheet ...> opening tag ---------------------
    marker = uuid.uuid4().hex[:8]
    probe_comment = f"\n  <!-- AlmaAPITK probe: {marker} -->\n"
    open_tag = re.search(r"<xsl:stylesheet[^>]*>", original_xsl)
    assert open_tag is not None, (
        "expected the XSL body to start with an <xsl:stylesheet ...> tag"
    )
    mutated_xsl = (
        original_xsl[: open_tag.end()]
        + probe_comment
        + original_xsl[open_tag.end() :]
    )
    mutated = dict(original)
    mutated["xsl"] = mutated_xsl

    restored = False
    try:
        # --- Step 3: PUT mutation ---------------------------------------
        update_response = config.update_letter(disabled_letter_code, mutated)
        assert update_response is not None
        assert getattr(update_response, "success", False) is True
        assert update_response.status_code == 200
        assert isinstance(update_response.data, dict)
        assert update_response.data.get("code") == disabled_letter_code

        # --- Step 4: read back, assert marker landed --------------------
        post_update = config.get_letter(disabled_letter_code)
        post_update_xsl = post_update.get("xsl") or ""
        assert isinstance(post_update_xsl, str)
        assert marker in post_update_xsl, (
            "Alma did not apply the XML-comment mutation: probe marker "
            f"{marker!r} absent from the XSL after PUT"
        )

        # --- Step 5: explicit restore (happy path) ----------------------
        restore_response = config.update_letter(
            disabled_letter_code, original
        )
        assert restore_response is not None
        assert getattr(restore_response, "success", False) is True

        # Confirm the XSL matches the original byte-for-byte after
        # restore. Alma normalises some whitespace (e.g. \r\n → \n),
        # so we compare on a trimmed-line basis to tolerate that.
        post_restore = config.get_letter(disabled_letter_code)
        post_restore_xsl = post_restore.get("xsl") or ""
        assert marker not in post_restore_xsl, (
            "Restore did not remove the probe marker — letter may still "
            "carry the AlmaAPITK XML comment"
        )
        # Whitespace-normalise both sides for the equality check.
        def _norm(s: str) -> str:
            return s.replace("\r\n", "\n").replace("\r", "\n")
        assert _norm(post_restore_xsl) == _norm(original_xsl), (
            "post-restore XSL does not match original XSL byte-for-byte "
            "(after CRLF normalisation)"
        )
        restored = True
    finally:
        # MANDATORY safety net: if the explicit restore in the happy
        # path was not reached (a mid-test assertion raised) or failed,
        # retry the restore here. A failure to restore is re-raised as a
        # HARD test failure — permanent mutation of the letter is
        # unacceptable.
        if not restored:
            try:
                config.update_letter(disabled_letter_code, original)
            except AlmaAPIError:
                # Re-raise — failure to restore is a HARD test failure.
                raise
