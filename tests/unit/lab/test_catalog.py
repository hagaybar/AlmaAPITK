"""Alma Lab operation catalog (issue #230)."""
import inspect

from almaapitk.lab.catalog import DOMAINS, discover_operations, find_operation


def _public_count():
    return sum(
        1
        for cls in DOMAINS.values()
        for name, _ in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_")
    )


def test_discovers_every_public_domain_method():
    ops = discover_operations()
    assert len(ops) == _public_count()
    assert len(ops) >= 150
    assert [o.qualname for o in ops] == sorted(o.qualname for o in ops)


def test_get_record_params():
    op = find_operation("BibliographicRecords.get_record")
    mms = next(p for p in op.params if p.name == "mms_id")
    assert mms.kind == "str"
    assert mms.required is True
    assert mms.help  # taken from the Args: docstring line
    view = next(p for p in op.params if p.name == "view")
    assert view.required is False and view.default == "full"
    assert op.verbs == frozenset({"GET"})
    assert op.writes is False


def test_every_operation_is_classified():
    unknown = [o.qualname for o in discover_operations() if "UNKNOWN" in o.verbs]
    assert unknown == []


def test_create_invoice_with_lines_is_multi_write():
    op = find_operation("Acquisitions.create_invoice_with_lines")
    assert op.writes is True
    assert op.multi_write is True


def test_callable_param_is_unsupported():
    op = find_operation("Analytics.fetch_report_rows")
    cb = next(p for p in op.params if p.name == "progress_callback")
    assert cb.kind == "unsupported"
    assert op.sendable is True  # optional, so the call can still be sent


def test_required_unsupported_param_blocks_send():
    op = find_operation("Users.remove_user_notes")
    assert next(p for p in op.params if p.name == "predicate").kind == "unsupported"
    assert op.sendable is False


def test_find_operation_alias():
    assert find_operation("bibs.get_record").qualname == "BibliographicRecords.get_record"


def test_sequence_or_mapping_param_is_json():
    op = find_operation("BibliographicRecords.update_marc_field")
    assert next(p for p in op.params if p.name == "subfields").kind == "json"
    assert op.sendable is True
