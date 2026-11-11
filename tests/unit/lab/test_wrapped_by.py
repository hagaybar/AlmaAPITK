"""Tests for marking raw endpoints that almaapitk domain methods already call."""
import ast

from almaapitk.lab.catalog import _function_calls, discover_operations
from almaapitk.lab.endpoints import get_endpoint, load_endpoints, wrapped_by


# Real count when written: 161 marks on 103 endpoints (unchanged by the
# resolver hardening); the floor is ~80% of it.
MARK_FLOOR = 128


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


def test_known_endpoint_to_method_pairs():
    # Read from the domain code: delete_user / delete_record call client.delete
    # with an f-string; list_libraries calls client.get with a plain literal.
    for method, path, qualname in [
        ("DELETE", "/almaws/v1/users/{user_id}", "Users.delete_user"),
        ("DELETE", "/almaws/v1/bibs/{mms_id}", "BibliographicRecords.delete_record"),
        ("GET", "/almaws/v1/conf/libraries", "Configuration.list_libraries"),
        ("PUT", "/almaws/v1/bibs/{mms_id}", "BibliographicRecords.update_record"),
    ]:
        assert qualname in wrapped_by(get_endpoint(method, path))


def test_wrong_verb_is_not_marked():
    assert "Users.delete_user" not in wrapped_by(get_endpoint("GET", "/almaws/v1/users/{user_id}"))


def test_parameter_reassigned_gives_no_mark():
    src = '''def m(self, p):
    if not p:
        p = "bibs/x"
    return self.client.get(p)
'''
    assert _calls(src) == set()


def test_tuple_unpacking_gives_no_mark():
    src = '''def m(self, x):
    ep = "bibs/a"
    ep, y = self._f(x)
    return self.client.get(ep)
'''
    assert _calls(src) == set()


def test_with_as_gives_no_mark():
    src = '''def m(self, x):
    ep = "bibs/a"
    with self._o() as ep:
        pass
    return self.client.get(ep)
'''
    assert _calls(src) == set()


def test_walrus_gives_no_mark():
    src = '''def m(self, x):
    ep = "bibs/a"
    if (ep := self._f(x)):
        pass
    return self.client.get(ep)
'''
    assert _calls(src) == set()


def test_except_as_gives_no_mark():
    src = '''def m(self, x):
    ep = "bibs/a"
    try:
        x()
    except ValueError as ep:
        pass
    return self.client.get(ep)
'''
    assert _calls(src) == set()


def test_nested_function_assignment_is_not_the_outer_binding():
    src = '''def m(self, x):
    def inner():
        ep = "bibs/a"
        return ep
    return self.client.get(ep)
'''
    assert _calls(src) == set()


def test_call_inside_nested_function_is_not_the_outer_call():
    src = '''def m(self, x):
    def inner():
        return self.client.get("bibs/a")
    return inner
'''
    assert _calls(src) == set()


def test_all_literal_reassignments_give_every_template():
    src = '''def m(self, x):
    ep = "bibs/a"
    if x:
        ep = f"bibs/{x}"
    return self.client.get(ep)
'''
    assert _calls(src) == {("GET", "/bibs/a"), ("GET", "/bibs/{}")}
