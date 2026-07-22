"""t-197-1: network-free smoke against the shipped build (issue #197).

Proves build_user_rs_request encodes Alma's plain-vs-{'value': ...}
asymmetry correctly: package-root export; owner plain / format,
citation_type, pickup_location wrapped / pickup_location_type plain;
plain-string text fields with int->str year coercion;
agree_to_copyright_terms defaulting to a real bool True; the 'extra'
escape hatch (wrap plain strings for wrapped fields, pass through
already-wrapped dicts, leave plain fields plain); required-argument
guards on owner/format/citation_type; and — via inspect — that
Users.create_user_rs_request keeps request_data as a required positional
(raw-dict path untouched) with validate keyword-only defaulting False.
The 'encoded exactly once' claim is asserted structurally via membership
of the single module-level frozenset _RS_REQUEST_WRAPPED_FIELDS.

The builder is a pure function: no HTTP request is issued and no SANDBOX
state is read or mutated. All values below are synthetic placeholders
('<RS_LIB>' etc.) exactly as prescribed by the test recommendation — no
operator-supplied fixture values are needed or used (R9).
"""

from __future__ import annotations

import inspect
import json
import pathlib

# Fixtures are loaded at RUNTIME from the gitignored test-data.json —
# never inlined at generation time (R9). This particular test is
# fixture-free (pure function under test); the loader is tolerant so the
# smoke stays runnable when the operator-filled file is absent.
_TEST_DATA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "test-data.json"
)
_TEST_DATA = (
    json.loads(_TEST_DATA_PATH.read_text()) if _TEST_DATA_PATH.exists() else {}
)

from almaapitk import build_user_rs_request
from almaapitk.client.AlmaAPIClient import AlmaValidationError
from almaapitk.domains.users import Users, _RS_REQUEST_WRAPPED_FIELDS

TEST_NAME = "t-197-1"


def test_t_197_1() -> None:
    # --- package-root export -------------------------------------------
    root_export_ok = callable(build_user_rs_request)
    assert root_export_ok is True

    # --- the wrapping asymmetry (the whole point of #197) --------------
    body = build_user_rs_request(
        owner="<RS_LIB>",
        format="DIGITAL",
        citation_type="CR",
        title="AlmaAPITK chunk-test RS builder",
        journal_title="AlmaAPITK test journal",
        author="AlmaAPITK",
        year=2026,
        pickup_location="<PICKUP_LIB>",
        pickup_location_type="LIBRARY",
        agree_to_copyright_terms=True,
        external_id="almaapitk-chunk-test-197",
    )
    print(f"[{TEST_NAME}] built body keys={sorted(body)}")

    owner_plain = isinstance(body["owner"], str) and body["owner"] == "<RS_LIB>"
    wrapped_ok = (
        body["format"] == {"value": "DIGITAL"}
        and body["citation_type"] == {"value": "CR"}
        and body["pickup_location"] == {"value": "<PICKUP_LIB>"}
    )
    pickup_type_plain = body["pickup_location_type"] == "LIBRARY"
    plain_text_ok = (
        body["title"] == "AlmaAPITK chunk-test RS builder"
        and body["journal_title"] == "AlmaAPITK test journal"
        and body["author"] == "AlmaAPITK"
        and body["external_id"] == "almaapitk-chunk-test-197"
        and body["year"] == "2026"
    )
    copyright_ok = body["agree_to_copyright_terms"] is True

    assert owner_plain is True
    assert wrapped_ok is True
    assert pickup_type_plain is True
    assert plain_text_ok is True
    assert copyright_ok is True

    # --- single definition site for the wrapping rule ------------------
    single_source_ok = (
        {"format", "citation_type", "pickup_location"}
        <= _RS_REQUEST_WRAPPED_FIELDS
        and "owner" not in _RS_REQUEST_WRAPPED_FIELDS
        and "pickup_location_type" not in _RS_REQUEST_WRAPPED_FIELDS
        and "external_id" not in _RS_REQUEST_WRAPPED_FIELDS
    )
    assert single_source_ok is True

    # --- the 'extra' escape hatch --------------------------------------
    extra_body = build_user_rs_request(
        owner="<RS_LIB>",
        format="PHYSICAL",
        citation_type="BK",
        title="AlmaAPITK chunk-test extra escape hatch",
        extra={
            "partner": "ILL_PARTNER",
            "pickup_location": {"value": "<PICKUP_LIB>"},
            "note": "plain note",
        },
    )
    extra_wraps = extra_body["partner"] == {"value": "ILL_PARTNER"}
    extra_passthrough = extra_body["pickup_location"] == {"value": "<PICKUP_LIB>"}
    extra_plain = extra_body["note"] == "plain note"

    assert extra_wraps is True
    assert extra_passthrough is True
    assert extra_plain is True

    # --- required-argument guards --------------------------------------
    guard_errors = {}
    for label, kwargs in (
        ("owner", {"owner": "", "format": "PHYSICAL", "citation_type": "BK"}),
        ("format", {"owner": "<RS_LIB>", "format": "", "citation_type": "BK"}),
        (
            "citation_type",
            {"owner": "<RS_LIB>", "format": "PHYSICAL", "citation_type": None},
        ),
    ):
        try:
            build_user_rs_request(**kwargs)
        except AlmaValidationError as e:
            guard_errors[label] = str(e)

    assert set(guard_errors) == {"owner", "format", "citation_type"}
    for label, msg in guard_errors.items():
        assert label in msg, f"guard error for {label!r} does not name the field"

    # --- raw-dict path untouched; builder/validation opt-in ------------
    sig = inspect.signature(Users.create_user_rs_request)
    raw_dict_path_ok = (
        "request_data" in sig.parameters
        and sig.parameters["request_data"].default is inspect.Parameter.empty
    )
    builder_is_opt_in = (
        sig.parameters["validate"].default is False
        and sig.parameters["validate"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    assert raw_dict_path_ok is True
    assert builder_is_opt_in is True

    # No client is ever constructed in this test: no HTTP request is
    # issued and no SANDBOX state is read or mutated.
    print(
        f"[{TEST_NAME}] owner_plain={owner_plain} wrapped_ok={wrapped_ok} "
        f"pickup_type_plain={pickup_type_plain} single_source_ok={single_source_ok}"
    )
