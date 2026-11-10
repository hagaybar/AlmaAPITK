"""Alma Lab raw calls: runner, baseline-checked updates and raw evidence."""
import json
from urllib.parse import urlsplit

import pytest

from almaapitk.lab.endpoints import (
    custom_endpoint,
    get_endpoint,
    get_twin,
    load_endpoints,
    match,
)
from almaapitk.lab.evidence import EvidenceRecord, load_record
from almaapitk.lab.runner import (
    InputError,
    RawRequest,
    Session,
    body_diff,
    coerce_query,
    normalise_body,
    resolve_path,
)

COURSES = "/almaws/v1/courses"
COURSE = "/almaws/v1/courses/{course_id}"
BIB = "/almaws/v1/bibs/{mms_id}"


def _session(lab_client, monkeypatch, tmp_path, gate=None):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    return Session("SANDBOX", evidence_dir=tmp_path, gate=gate, source="headless", command="test")


@pytest.fixture
def session(lab_client, monkeypatch, tmp_path):
    return _session(lab_client, monkeypatch, tmp_path)


@pytest.fixture
def write_session(lab_client, monkeypatch, tmp_path):
    return _session(lab_client, monkeypatch, tmp_path, gate=lambda *a: True)


def _put_course(body='{"code": "X", "name": "New"}'):
    return RawRequest(endpoint=get_endpoint("PUT", COURSE), path_params={"course_id": "<course_id>"},
                      query={}, body=body, fmt="json")


def _get_course():
    return RawRequest(endpoint=get_endpoint("GET", COURSE), path_params={"course_id": "<course_id>"},
                      query={})


def test_raw_get_records_raw_evidence(session, lab_client, tmp_path):
    lab_client.http.answers = [{"body": {"course": [], "total_record_count": 0}}]
    req = RawRequest(endpoint=get_endpoint("GET", COURSES), path_params={}, query={"limit": "5"})
    rec = session.run_raw(req, ["status == 200"])
    assert rec.raw is True
    assert rec.endpoint["path"] == COURSES and rec.endpoint["custom"] is False
    assert rec.operation == f"raw GET {COURSES}"
    assert rec.inputs == {"path": {}, "query": {"limit": 5}, "format": "json", "body": None}
    assert rec.requests[0].url.endswith("/almaws/v1/courses?limit=5")
    assert [e["outcome"] for e in rec.expectations] == ["passed"]
    assert "raw-GET-courses" in session.last_path.name
    assert load_record(rec.id, tmp_path).to_dict() == rec.to_dict()


def test_query_type_errors_before_sending(session, lab_client):
    req = RawRequest(endpoint=get_endpoint("GET", COURSES), path_params={}, query={"limit": "abc"})
    with pytest.raises(InputError) as exc:
        session.run_raw(req)
    assert exc.value.field == "limit"
    assert lab_client.http.calls == []


def test_coerce_query_types_blanks_and_unknown_names():
    ep = get_endpoint("GET", COURSES)
    assert coerce_query(ep, {"limit": " 7 ", "exact_search": "yes", "q": "", "offset": None}) == {
        "limit": 7, "exact_search": True}
    with pytest.raises(InputError) as exc:
        coerce_query(ep, {"exact_search": "maybe"})
    assert exc.value.field == "exact_search"
    with pytest.raises(InputError) as exc:
        coerce_query(ep, {"nope": "1"})
    assert exc.value.field == "nope"
    assert coerce_query(custom_endpoint("GET", "almaws/v1/x"), {"nope": "1"}) == {"nope": "1"}


def test_missing_path_value(session, lab_client):
    req = RawRequest(endpoint=get_endpoint("GET", COURSE), path_params={"course_id": " "}, query={})
    with pytest.raises(InputError) as exc:
        session.run_raw(req)
    assert exc.value.field == "course_id"
    assert lab_client.http.calls == []


def test_path_values_are_quoted(session, lab_client):
    ep = get_endpoint("GET", COURSE)
    assert resolve_path(ep, {"course_id": "a/b c"}) == "almaws/v1/courses/a%2Fb%20c"
    lab_client.http.answers = [{"body": {"id": "1"}}]
    rec = session.run_raw(RawRequest(endpoint=ep, path_params={"course_id": "a/b c"}, query={}))
    assert "a%2Fb%20c" in rec.requests[0].url
    found = match("GET", urlsplit(rec.requests[0].url).path)
    assert found is not None and found[0] == ep and found[1] == {"course_id": "a/b c"}


def test_invalid_json_body_rejected_before_sending(write_session, lab_client):
    with pytest.raises(InputError) as exc:
        write_session.run_raw(RawRequest(endpoint=get_endpoint("POST", COURSES), path_params={},
                                         query={}, body="{not json"))
    assert exc.value.field == "body"
    assert lab_client.http.calls == []


def test_put_requires_baseline(write_session, lab_client):
    with pytest.raises(InputError) as exc:
        write_session.run_raw(_put_course())
    assert exc.value.field == "baseline"
    assert lab_client.http.calls == []


def test_put_with_baseline_sends_and_diffs(write_session, lab_client):
    lab_client.http.answers = [{"body": {"code": "X", "name": "Old"}},
                               {"body": {"name": "Old", "code": "X"}},
                               {"body": {"code": "X", "name": "New"}}]
    base = write_session.fetch_baseline(_put_course())
    assert base.raw and base.endpoint["method"] == "GET" and base.last_status == 200
    rec = write_session.run_raw(_put_course(), ["status == 200"], baseline=base)
    assert rec.refused is None and rec.error is None
    assert rec.baseline["evidence_id"] == base.id
    assert json.loads(rec.baseline["body"]) == {"code": "X", "name": "Old"}
    assert '-  "name": "Old"' in rec.body_diff and '+  "name": "New"' in rec.body_diff
    assert [r.method for r in rec.requests] == ["GET", "PUT"]
    assert len(lab_client.http.calls) == 3
    assert rec.wrapped_by == list(rec.wrapped_by)
    assert rec.slug == "raw-PUT-courses-course_id"


def test_put_refused_when_record_changed(write_session, lab_client):
    lab_client.http.answers = [{"body": {"code": "X", "name": "Old"}},
                               {"body": {"code": "X", "name": "Changed elsewhere"}}]
    base = write_session.fetch_baseline(_put_course())
    rec = write_session.run_raw(_put_course(), baseline=base)
    assert rec.refused == "baseline changed"
    assert [c[0] for c in lab_client.http.calls] == ["GET", "GET"]
    assert write_session.last_path.exists()


def test_failed_baseline_does_not_count(write_session, lab_client):
    lab_client.http.answers = [{"status": 404, "body": {"errorsExist": True}}]
    base = write_session.fetch_baseline(_put_course())
    assert base.last_status == 404
    with pytest.raises(InputError) as exc:
        write_session.run_raw(_put_course(), baseline=base)
    assert exc.value.field == "baseline"
    assert len(lab_client.http.calls) == 1


def test_baseline_for_other_path_values_does_not_count(write_session, lab_client):
    lab_client.http.answers = [{"body": {"code": "X"}}]
    other = RawRequest(endpoint=get_endpoint("PUT", COURSE), path_params={"course_id": "<other>"},
                       query={}, body="{}")
    base = write_session.fetch_baseline(other)
    with pytest.raises(InputError) as exc:
        write_session.run_raw(_put_course(), baseline=base)
    assert exc.value.field == "baseline"


def test_xml_put_baseline_and_diff(write_session, lab_client):
    old = "<bib><title>Old</title></bib>"
    new = "<bib><title>New</title></bib>"
    xml = {"content_type": "application/xml"}
    lab_client.http.answers = [{"body": old.encode(), **xml}, {"body": old.encode(), **xml},
                               {"body": new.encode(), **xml}]
    req = RawRequest(endpoint=get_endpoint("PUT", BIB), path_params={"mms_id": "<mms_id>"},
                     query={}, body=new, fmt="xml")
    base = write_session.fetch_baseline(req)
    assert lab_client.http.calls[0][2]["headers"]["Accept"] == "application/xml"
    rec = write_session.run_raw(req, baseline=base)
    assert lab_client.http.calls[1][2]["headers"]["Accept"] == "application/xml"
    method, _, sent = lab_client.http.calls[-1]
    assert method == "PUT" and sent["headers"]["Content-Type"] == "application/xml"
    assert sent["data"] == new and rec.requests[-1].method == "PUT"
    assert "-<bib><title>Old</title></bib>" in rec.body_diff
    assert "+<bib><title>New</title></bib>" in rec.body_diff
    # an unparsable baseline still diffs as text
    assert "-<bib><title>Old</title>" in body_diff("<bib><title>Old</title>  ", new, "xml")


def test_put_without_twin_needs_no_baseline(write_session, lab_client):
    ep = next(e for e in load_endpoints() if e.method == "PUT" and get_twin(e) is None)
    values = {p.name: f"<{p.name}>" for p in ep.path_params}
    lab_client.http.answers = [{"body": {}}]
    rec = write_session.run_raw(RawRequest(endpoint=ep, path_params=values, query={}, body="{}"))
    assert rec.error is None and rec.requests[0].method == "PUT"
    assert rec.baseline is None and rec.body_diff is None


def test_custom_path(session, lab_client):
    ep = custom_endpoint("GET", "almaws/v1/task-lists/requested-resources")
    lab_client.http.answers = [{"body": {}}]
    rec = session.run_raw(RawRequest(endpoint=ep, path_params={},
                                     query={"library": "<library>", "circ_desk": "DEFAULT_CIRC_DESK"}))
    assert rec.endpoint["custom"] is True
    assert rec.requests[0].url.endswith(
        "/almaws/v1/task-lists/requested-resources?library=%3Clibrary%3E&circ_desk=DEFAULT_CIRC_DESK")


def test_write_refused_by_gate_is_recorded(session, lab_client):
    rec = session.run_raw(RawRequest(endpoint=get_endpoint("POST", COURSES), path_params={},
                                     query={}, body='{"code": "X"}'))
    assert rec.error.startswith("WriteCancelled")
    assert len(rec.cancelled_writes) == 1
    assert lab_client.http.calls == []


def test_rerun_get_works(session, lab_client):
    lab_client.http.answers = [{"body": {"id": "1"}}, {"body": {"id": "1"}}]
    first = session.run_raw(_get_course(), ["status == 200"])
    again = session.rerun(first)
    assert again.raw and again.id != first.id
    assert again.inputs == first.inputs and again.endpoint == first.endpoint
    assert [e["outcome"] for e in again.expectations] == ["passed"]
    assert len(lab_client.http.calls) == 2


def test_rerun_custom_get_works(session, lab_client):
    ep = custom_endpoint("GET", "almaws/v1/task-lists/printouts")
    lab_client.http.answers = [{"body": {}}, {"body": {}}]
    first = session.run_raw(RawRequest(endpoint=ep, path_params={}, query={"letter": "ALL"}))
    again = session.rerun(first)
    assert again.endpoint["custom"] is True and again.inputs == first.inputs


def test_rerun_put_needs_fresh_baseline(write_session, lab_client):
    lab_client.http.answers = [{"body": {"code": "X"}}, {"body": {"code": "X"}}, {"body": {"code": "X"}}]
    base = write_session.fetch_baseline(_put_course())
    rec = write_session.run_raw(_put_course(), baseline=base)
    with pytest.raises(InputError) as exc:
        write_session.rerun(rec)
    assert exc.value.field == "baseline"
    assert "load the current record again" in exc.value.message
    assert len(lab_client.http.calls) == 3


def test_old_records_still_load():
    old = {"id": "20261101-101010-bibs.get_record", "created_at": "2026-11-01T10:10:10+00:00",
           "tool_version": "1", "almaapitk_version": "0.6.0", "python_version": "3.12",
           "environment": "SANDBOX", "base_url_host": "api.example", "operation": "bibs.get_record",
           "inputs": {"mms_id": "<mms_id>"}}
    rec = EvidenceRecord.from_dict(old)
    assert rec.raw is False and rec.endpoint is None and rec.wrapped_by == []
    assert rec.baseline is None and rec.body_diff is None and rec.refused is None and rec.slug is None


def test_normalise_body():
    assert normalise_body('{"b": 1, "a": "א"}', "json") == '{\n  "a": "א",\n  "b": 1\n}'
    assert normalise_body("<a>  \n<b/>\t\n", "xml") == "<a>\n<b/>"
    assert normalise_body("{broken  ", "json") == "{broken"


def test_put_not_sent_when_recheck_fails(write_session, lab_client):
    lab_client.http.answers = [{"body": {"code": "X"}}, {"status": 500, "body": {"errorsExist": True}}]
    base = write_session.fetch_baseline(_put_course())
    rec = write_session.run_raw(_put_course(), baseline=base)
    assert rec.refused == "baseline could not be checked" and rec.error
    assert [c[0] for c in lab_client.http.calls] == ["GET", "GET"]
