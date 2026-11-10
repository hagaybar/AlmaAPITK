"""Tests for marking raw endpoints that almaapitk domain methods already call."""
import ast

from almaapitk.lab.catalog import _function_calls, discover_operations
from almaapitk.lab.endpoints import get_endpoint, load_endpoints, wrapped_by


def _calls(src: str):
    return _function_calls(ast.parse(src).body[0])


def test_get_record_via_local_variable():
    assert "BibliographicRecords.get_record" in wrapped_by(
        get_endpoint("GET", "/almaws/v1/bibs/{mms_id}"))


def test_every_mark_is_a_real_method_with_that_verb():
    ops = {o.qualname: o for o in discover_operations()}
    marks = 0
    for ep in load_endpoints():
        for q in wrapped_by(ep):
            marks += 1
            assert q in ops and ep.method in ops[q].verbs
    # Real count when written: 161 marks on 103 endpoints; floor ~80%.
    assert marks >= MARK_FLOOR


MARK_FLOOR = 128


def test_literal_and_fstring_templates():
    src = '''def m(self, x):
    self.client.get("/almaws/v1/conf/libraries")
    ep = f"almaws/v1/bibs/{x}/holdings"
    return self.client.post(ep, data=x)
'''
    assert _calls(src) == {
        ("GET", "/almaws/v1/conf/libraries"),
        ("POST", "/almaws/v1/bibs/{}/holdings"),
    }


def test_non_literal_assignment_gives_no_mark():
    src = '''def m(self, x):
    endpoint = f"almaws/v1/bibs/{x}"
    if x:
        endpoint = self._build(x)
    return self.client.get(endpoint)
'''
    assert _calls(src) == set()


def test_parameter_or_unknown_name_gives_no_mark():
    assert _calls("def m(self, p):\n    return self.client.get(p)\n") == set()
