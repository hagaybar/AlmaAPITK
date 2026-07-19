"""R10 regression test for issue #197 — user RS request body wrapping.

Bug (ergonomics defect): ``Users.create_user_rs_request`` forwards
``request_data`` verbatim, so every caller had to re-derive Alma's
plain-vs-``{"value": ...}`` wrapping by hand. The wrapping is asymmetric in a
way that is impossible to guess:

* ``owner`` and ``pickup_location_type`` are **plain strings**;
* ``format``, ``citation_type`` and ``pickup_location`` — sitting right next to
  them in the same body — are **wrapped** ``{"value": "<code>"}``.

Getting it backwards produces the cryptic Alma ``Invalid field value … Value:
{1}`` error, which cost a long trial-and-error loop while building a borrowing
request. ``build_user_rs_request`` encodes the rules exactly once.

Ground truth for the wrapping is the POST body schema
``rest_user_resource_sharing_request-post.json`` (the ``requestBody`` ``$ref``
of ``POST /almaws/v1/users/{user_id}/resource-sharing-requests`` in
``docs/alma-swagger/users.json``): properties typed ``object`` with a single
``value`` key wrap, ``string`` properties do not.

These tests fail before the fix (the builder does not exist) and pin the exact
wire shape afterwards. The raw-dict path is pinned too — the builder must not
have changed it.
"""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from almaapitk.domains.users import Users, build_user_rs_request


class _MockResponse:
    def __init__(self, body: Optional[Dict[str, Any]] = None):
        self._body = body or {}
        self.success = True
        self.status_code = 200

    def json(self) -> Dict[str, Any]:
        return self._body

    @property
    def data(self) -> Dict[str, Any]:
        return self._body


class _MockClient:
    """Records POST calls so the wire body can be asserted."""

    def __init__(self):
        self.environment = "SANDBOX"
        self.logger = MagicMock()
        self.calls: Dict[str, list] = {"post": []}

    def get_environment(self) -> str:
        return self.environment

    def post(self, endpoint, data=None, params=None):
        self.calls["post"].append(
            {"endpoint": endpoint, "data": data, "params": params}
        )
        return _MockResponse({"request_id": "rs-197"})


def test_owner_is_a_plain_string_not_wrapped():
    body = build_user_rs_request(
        owner="RS_LIB", format="DIGITAL", citation_type="CR"
    )

    assert body["owner"] == "RS_LIB", (
        "owner must be a plain string — wrapping it in {'value': ...} is the "
        "mistake that yields Alma's 'Invalid field value ... Value: {1}'"
    )
    assert not isinstance(body["owner"], dict)


@pytest.mark.parametrize(
    "field,code",
    [
        ("format", "DIGITAL"),
        ("citation_type", "CR"),
        ("pickup_location", "PICKUP_LIB"),
    ],
)
def test_code_table_fields_are_wrapped(field, code):
    body = build_user_rs_request(
        owner="RS_LIB",
        format="DIGITAL",
        citation_type="CR",
        pickup_location="PICKUP_LIB",
    )

    assert body[field] == {"value": code}, (
        f"{field} is typed object{{value}} in "
        "rest_user_resource_sharing_request-post.json and must be wrapped"
    )


def test_pickup_location_type_is_a_plain_string():
    body = build_user_rs_request(
        owner="RS_LIB",
        format="PHYSICAL",
        citation_type="BK",
        pickup_location="PICKUP_LIB",
        pickup_location_type="LIBRARY",
    )

    assert body["pickup_location_type"] == "LIBRARY"
    assert not isinstance(body["pickup_location_type"], dict)


def test_agree_to_copyright_terms_defaults_to_true_as_a_bool():
    # Mandatory on the borrowing surface; a missing/typed-as-string value is
    # rejected by Alma's deserializer.
    body = build_user_rs_request("RS_LIB", "DIGITAL", "CR")

    assert body["agree_to_copyright_terms"] is True


def test_built_body_reaches_alma_verbatim():
    client = _MockClient()
    users = Users(client)

    body = build_user_rs_request(
        owner="RS_LIB",
        format="DIGITAL",
        citation_type="CR",
        title="Sample title",
        pickup_location="PICKUP_LIB",
        pickup_location_type="LIBRARY",
        external_id="caller-app:42",
    )
    users.create_user_rs_request("u1", request_data=body)

    call = client.calls["post"][0]
    assert call["endpoint"] == "almaws/v1/users/u1/resource-sharing-requests"
    assert call["data"] == {
        "owner": "RS_LIB",
        "format": {"value": "DIGITAL"},
        "citation_type": {"value": "CR"},
        "external_id": "caller-app:42",
        "pickup_location_type": "LIBRARY",
        "title": "Sample title",
        "pickup_location": {"value": "PICKUP_LIB"},
        "agree_to_copyright_terms": True,
    }


def test_raw_dict_path_still_forwarded_untouched():
    # Back-compat: callers that hand-assemble a body must be unaffected by the
    # new builder — no normalisation, no re-wrapping.
    client = _MockClient()
    users = Users(client)

    raw = {"citation_type": "BK", "owner": {"value": "RS_LIB"}}
    users.create_user_rs_request("u1", request_data=raw)

    assert client.calls["post"][0]["data"] == raw
