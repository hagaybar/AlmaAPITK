"""Alma Lab expectations (issue #230)."""
import pytest

from almaapitk.lab.capture import CapturedRequest
from almaapitk.lab.expect import evaluate, parse_expectation


def _req(status, body="{}"):
    return CapturedRequest(method="GET", url="u", headers={}, body=None, status=status, response_body=body)


def test_parse_forms():
    assert parse_expectation("status == 200").op == "=="
    e = parse_expectation("title exists")
    assert (e.target, e.op, e.value) == ("title", "exists", None)
    e = parse_expectation('note contains "two words"')
    assert (e.target, e.op, e.value) == ("note", "contains", "two words")


def test_bad_expectation_raises_with_hint():
    with pytest.raises(ValueError, match="status == 200"):
        parse_expectation("status is 200")


def test_status_uses_last_request():
    out = evaluate(parse_expectation("status == 200"), result=None, requests=[_req(404), _req(200)], error=None)
    assert out["outcome"] == "passed" and out["actual"] == 200


def test_http_index_body_path():
    reqs = [_req(200, '{"total_record_count": 3}'), _req(200, "{}")]
    out = evaluate(parse_expectation("http[0].body.total_record_count == 3"), result=None, requests=reqs, error=None)
    assert out["outcome"] == "passed"


def test_result_path_and_numbers():
    res = {"payment": {"payment_status": {"value": "PAID"}}, "count": "3"}
    assert evaluate(parse_expectation("payment.payment_status.value == PAID"), result=res, requests=[], error=None)["outcome"] == "passed"
    assert evaluate(parse_expectation("count == 3.0"), result=res, requests=[], error=None)["outcome"] == "passed"


def test_error_expectation():
    out = evaluate(parse_expectation("error == AlmaServerError"), result=None, requests=[], error="AlmaServerError")
    assert out["outcome"] == "passed"


def test_missing_path_fails_with_reason():
    out = evaluate(parse_expectation("title exists"), result={}, requests=[], error=None)
    assert out["outcome"] == "failed" and "title" in str(out["actual"])
