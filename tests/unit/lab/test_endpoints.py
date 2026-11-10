"""Tests for the bundled Alma endpoint index."""
import json
from collections import Counter
from importlib import resources
from pathlib import Path

from almaapitk.lab.endpoints import (
    Endpoint,
    _match_in,
    build_index,
    custom_endpoint,
    get_endpoint,
    get_twin,
    load_endpoints,
    match,
)

SWAGGER = Path(__file__).resolve().parents[3] / "docs" / "alma-swagger"


def test_bundled_index_matches_snapshot():
    bundled = json.loads(
        resources.files("almaapitk.lab.data").joinpath("alma_endpoints.json").read_text("utf-8")
    )
    assert bundled == build_index(SWAGGER)


def test_counts():
    eps = load_endpoints()
    assert len(eps) == 304
    assert Counter(e.area for e in eps)["courses"] == 29
    assert sum(e.method == "PUT" for e in eps) == 43
    assert sum(e.method == "PUT" and get_twin(e) is not None for e in eps) == 42
    assert sum(e.body_formats == ("xml",) for e in eps) == 5


def test_courses_list_params():
    ep = get_endpoint("GET", "/almaws/v1/courses")
    q = {p.name: p for p in ep.query_params}
    assert q["limit"].type == "integer" and q["limit"].default == "10" and not q["limit"].required
    assert "Brief Search" in q["q"].description
    assert ep.source_fetched.startswith("2026-05-29")


def test_match_concrete_path():
    ep, values = match("GET", "almaws/v1/bibs/990000000000001")
    assert ep.path == "/almaws/v1/bibs/{mms_id}" and values == {"mms_id": "990000000000001"}
    assert match("GET", "/almaws/v1/nope/1") is None


def test_match_unquotes_values():
    _, values = match("GET", "/bibs/a%20b")
    assert values == {"mms_id": "a b"}


def test_match_prefers_literal():
    def ep(path):
        return custom_endpoint("GET", path)

    templ = ep("/almaws/v1/things/{id}")
    literal = ep("/almaws/v1/things/special")
    for order in ((templ, literal), (literal, templ)):
        found, values = _match_in(order, "GET", "/things/special")
        assert found.path.endswith("/special") and values == {}
    found, values = _match_in((templ, literal), "GET", "/things/other")
    assert found is templ and values == {"id": "other"}


def test_confirm_word_and_slug():
    ep = get_endpoint("PUT", "/almaws/v1/courses/{course_id}")
    assert ep.confirm_word == "PUT courses"
    assert ep.slug == "raw-PUT-courses-course_id"


def test_put_bibs_is_xml_only():
    assert get_endpoint("PUT", "/almaws/v1/bibs/{mms_id}").body_formats == ("xml",)


def test_custom_endpoint():
    post = custom_endpoint("post", "/almaws/v1/x")
    assert isinstance(post, Endpoint) and post.custom and post.area == "custom"
    assert post.body_formats == ("json", "xml") and post.writes
    assert custom_endpoint("GET", "/almaws/v1/x").body_formats == ()
