"""Alma Lab runner (issue #230)."""
import pytest

from almaapitk.lab import catalog
from almaapitk.lab.catalog import Operation, Param, find_operation
from almaapitk.lab.evidence import load_record
from almaapitk.lab.runner import InputError, Session, coerce_inputs


@pytest.fixture
def session(lab_client, monkeypatch, tmp_path):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    return Session("SANDBOX", evidence_dir=tmp_path, gate=None, source="headless", command="test")


def test_get_operation_writes_record_with_checks(session, lab_client, tmp_path):
    lab_client.http.answers = [{"body": {"mms_id": "990000000000001", "title": "Sample title"}}]
    rec = session.run(find_operation("bibs.get_record"), {"mms_id": "990000000000001"},
                      ["status == 200", "title == Sample title", "title contains Nope"])
    assert rec.error is None
    assert rec.result["title"] == "Sample title"
    assert [e["outcome"] for e in rec.expectations] == ["passed", "passed", "failed"]
    assert rec.requests[0].url.endswith("/almaws/v1/bibs/990000000000001?view=full")
    assert load_record(rec.id, tmp_path).to_dict() == rec.to_dict()
    assert rec.source == "headless" and rec.environment == "SANDBOX"


def test_coerce_rejects_bad_int_with_field_name():
    op = find_operation("Acquisitions.list_invoices")
    with pytest.raises(InputError) as exc:
        coerce_inputs(op, {"limit": "abc"})
    assert exc.value.field == "limit"


def test_coerce_kinds_and_required():
    op = find_operation("bibs.get_record")
    assert coerce_inputs(op, {"mms_id": " 99 ", "view": "", "expand": ""}) == {"mms_id": "99"}
    with pytest.raises(InputError, match="required") as exc:
        coerce_inputs(op, {})
    assert exc.value.field == "mms_id"
    with pytest.raises(InputError) as exc:
        coerce_inputs(op, {"mms_id": "1", "nope": "x"})
    assert exc.value.field == "nope"


class _TwoWrites:
    def __init__(self, client):
        self.client = client

    def two_posts(self):
        self.client.post("almaws/v1/acq/invoices", data={"n": 1})
        self.client.post("almaws/v1/acq/invoices/1", params={"op": "process_invoice"}, data={})
        return "done"


def test_cancel_second_write_records_first_as_sent(lab_client, monkeypatch, tmp_path):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    monkeypatch.setitem(catalog.DOMAINS, "Fake", _TwoWrites)
    answers = iter([True, False])
    session = Session("SANDBOX", evidence_dir=tmp_path, gate=lambda m, u, b: next(answers))
    lab_client.http.answers = [{"body": {"id": "1"}}]
    op = Operation(domain="Fake", name="two_posts", params=(), verbs=frozenset({"POST"}), multi_write=True, doc="")
    rec = session.run(op, {})
    assert [r.sent for r in rec.requests] == [True, False]
    assert rec.error.startswith("WriteCancelled")
    assert len(rec.cancelled_writes) == 1 and "process_invoice" in rec.cancelled_writes[0]["url"]
    assert len(lab_client.http.calls) == 1


def test_incomplete_flag_for_citation_method(session, lab_client, monkeypatch):
    def no_network(*a, **k):
        raise RuntimeError("no network in unit tests")

    monkeypatch.setattr("almaapitk.utils.citation_metadata.requests.get", no_network)
    op = find_operation("ResourceSharing.create_lending_request_from_citation")
    rec = session.run(op, {"partner_code": "P", "external_id": "E", "owner": "O", "format_type": "PHYSICAL",
                           "pmid": "1"})
    assert rec.incomplete is True and "PubMed" in rec.incomplete_reason


def test_error_is_recorded_not_raised(session, lab_client):
    lab_client.http.answers = [{"status": 500, "body": {"errorList": {"error": [{"errorCode": "x", "trackingId": "E01-T"}]}}}]
    rec = session.run(find_operation("bibs.get_record"), {"mms_id": "1"}, ["error == AlmaServerError"])
    assert rec.error.startswith("AlmaServerError")
    assert rec.expectations[0]["outcome"] == "passed"
    assert rec.requests[0].tracking_id == "E01-T"


def test_bad_expectation_is_an_input_error(session):
    with pytest.raises(InputError) as exc:
        session.run(find_operation("bibs.get_record"), {"mms_id": "1"}, ["status is 200"])
    assert exc.value.field == "expect"


def test_rerun_uses_same_inputs(session, lab_client):
    lab_client.http.answers = [{"body": {"title": "a"}}, {"body": {"title": "a"}}]
    first = session.run(find_operation("bibs.get_record"), {"mms_id": "1", "view": "brief"}, ["status == 200"])
    second = session.rerun(first)
    assert second.inputs == first.inputs and second.id != first.id
    assert second.expectations[0]["outcome"] == "passed"
