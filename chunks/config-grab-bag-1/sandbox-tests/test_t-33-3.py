"""Generated SANDBOX test t-33-3 - Configuration.update_letter live PUT
verification (issue #33). STATE-CHANGING — operator-authorized.

Maps to AC #33 facets:
  - ``update_letter`` exercised end-to-end against live SANDBOX.
  - AlmaResponse return-value contract on PUT (``.success`` flag).

Operator-authorized live ``update_letter`` PUT against the DISABLED
letter ``<disabled_letter_code>``. Reads the letter, then re-PUTs the
exact same payload back and asserts a 200 success response. No fields
are mutated by the test — the substantive content (xsl template,
enabled flag, channel, description, etc.) round-trips intact. Alma's
internal bookkeeping (``customized``, ``updated_by``, ``update_date``)
will advance — that is Alma's expected behaviour for any letter PUT
and not a mutation caused by this test.

Why no-mutation:
  - The most semantically interesting fields (``xsl``, ``enabled``,
    ``channel``) are user-visible if the letter is ever re-enabled.
  - ``description`` looks tempting as a target but Alma sources it
    from the labels code-table mapping — PUTs against it are silently
    ignored (verified live 2026-05-07).
  - A no-op round-trip proves the wire works (XML serialization,
    Content-Type negotiation, AlmaResponse parsing) without depending
    on which Alma fields are mutable. The unit-test suite asserts the
    XML body shape and request envelope; this test asserts the live
    endpoint accepts our XML and returns a parseable JSON dict.

History (issue #114):
  - 2026-05-07: original test attempted a description-only mutation
    + try/finally restore. Both PUTs failed with 400 + Alma error
    60105 ("JSON is not supported for this API."). Test held with
    @pytest.mark.skip pointing to issue #114.
  - 2026-05-08 (issue #114): ``update_letter`` rewritten to send XML
    body and force ``Accept: application/json`` on the response. The
    live PUT succeeds. Skip removed; round-trip simplified to a
    no-mutation re-PUT now that the wire actually works.

Fixture (``disabled_letter_code``) is loaded at runtime from
``chunks/config-grab-bag-1/test-data.json`` so that no operator-supplied
identifier is committed to the public repository (R9).
"""
from __future__ import annotations

import json
import pathlib

from almaapitk import AlmaAPIClient
from almaapitk.domains.configuration import Configuration

_TEST_DATA_PATH = pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
_TEST_DATA = json.loads(_TEST_DATA_PATH.read_text())


def test_t_33_3():
    disabled_letter_code = _TEST_DATA["disabled_letter_code"]

    client = AlmaAPIClient(environment="SANDBOX")
    config = Configuration(client)

    # Read the disabled letter (snapshot what's currently on Alma).
    original = config.get_letter(disabled_letter_code)
    assert isinstance(original, dict) and len(original) > 0
    original_xsl = original.get("xsl")
    original_enabled = original.get("enabled")
    original_channel = original.get("channel")

    # Re-PUT the exact same payload — no mutation. Asserts that the
    # wire works (XML serialization, Content-Type, JSON response
    # parsing). Alma always 200s on a well-formed letter PUT even
    # without changes.
    update_response = config.update_letter(disabled_letter_code, original)
    assert update_response is not None
    assert getattr(update_response, "success", False) is True
    assert update_response.status_code == 200
    # The PUT response body should be a parseable JSON dict (because
    # update_letter sets Accept: application/json).
    assert isinstance(update_response.data, dict)
    assert update_response.data.get("code") == disabled_letter_code

    # Re-read and confirm the substantive content round-tripped.
    post_put = config.get_letter(disabled_letter_code)
    assert post_put.get("xsl") == original_xsl
    assert post_put.get("enabled") == original_enabled
    assert post_put.get("channel") == original_channel
