"""Alma Lab app: fill inputs, send, confirm writes, read results, history, export (issue #230)."""
import asyncio
import json

import pytest

pytest.importorskip("textual")

from textual.widgets import Input, TextArea, Tree  # noqa: E402

from almaapitk.lab.app.app import LabApp  # noqa: E402
from almaapitk.lab.app.confirm import ConfirmWrite  # noqa: E402
from almaapitk.lab.app.export import ExportScreen  # noqa: E402
from almaapitk.lab.app.history import HistoryScreen  # noqa: E402
from almaapitk.lab.runner import Session  # noqa: E402


@pytest.fixture
def make_app(lab_client, monkeypatch, tmp_path):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)

    def factory(env="SANDBOX"):
        return LabApp(Session(env, evidence_dir=tmp_path / "ev"))
    return factory


def _run(app, scenario):
    async def main():
        async with app.run_test(size=(120, 30)) as pilot:
            await scenario(pilot)
    asyncio.run(main())


async def _open(pilot, qualname, **values):
    app = pilot.app
    app.select_operation(qualname)
    await pilot.pause()
    for name, value in values.items():
        app.query_one(f"#field-{name}", Input).value = value
    await pilot.pause()


async def _send(pilot):
    pilot.app.action_send()
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def _status(app):
    return str(app.query_one("#status-line").render())


def test_send_get_shows_status_and_saves_record(make_app, lab_client, tmp_path):
    lab_client.http.answers = [{"body": {"mms_id": "990000000000001", "title": "Sample title"}}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.get_record", mms_id="990000000000001")
        pilot.app.query_one("#expect", TextArea).text = "status == 200\ntitle exists"
        await _send(pilot)
        assert "200" in _status(pilot.app)
        assert "2/2 checks" in _status(pilot.app)
        assert list((tmp_path / "ev").glob("*/*.json"))
    _run(make_app(), scenario)


def test_changed_value_resend_keeps_other_values(make_app, lab_client):
    lab_client.http.answers = [{"body": {}}, {"body": {}}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.get_record", mms_id="1", view="brief")
        await _send(pilot)
        pilot.app.query_one("#field-mms_id", Input).value = "2"
        await _send(pilot)
        (_, url1, kw1), (_, url2, kw2) = lab_client.http.calls
        assert url1.endswith("/bibs/1") and url2.endswith("/bibs/2")
        assert kw2["params"]["view"] == "brief"
    _run(make_app(), scenario)


def test_input_error_shown_on_field(make_app, lab_client):
    async def scenario(pilot):
        await _open(pilot, "Acquisitions.list_invoices", limit="abc")
        await _send(pilot)
        assert "whole number" in str(pilot.app.query_one("#error-limit").render())
        assert lab_client.http.calls == []
    _run(make_app(), scenario)


def test_sandbox_write_confirm_and_cancel(make_app, lab_client):
    lab_client.http.answers = [{"status": 204, "body": b""}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.delete_record", mms_id="1")
        pilot.app.action_send()
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, ConfirmWrite)
        await pilot.press("escape")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert lab_client.http.calls == []
        assert "WriteCancelled" in _status(pilot.app)
        pilot.app.action_send()
        await pilot.pause(0.3)
        await pilot.press("enter")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert [c[0] for c in lab_client.http.calls] == ["DELETE"]
    _run(make_app(), scenario)


def test_production_write_needs_typed_name(make_app, lab_client):
    lab_client.http.answers = [{"status": 204, "body": b""}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.delete_record", mms_id="1")
        pilot.app.action_send()
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, ConfirmWrite)
        await pilot.press("enter")  # nothing typed: refused
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert lab_client.http.calls == []
        pilot.app.action_send()
        await pilot.pause(0.3)
        await pilot.press(*"delete_record", "enter")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert [c[0] for c in lab_client.http.calls] == ["DELETE"]
    _run(make_app("PRODUCTION"), scenario)


def test_large_response_tree_is_lazy(make_app, lab_client):
    lab_client.http.answers = [{"body": {"rows": [{"n": i, "x": "y"} for i in range(5000)]}}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.get_record", mms_id="1")
        await _send(pilot)
        tree = pilot.app.query_one("#response-tree", Tree)
        count = sum(1 for _ in _walk(tree.root))
        assert count < 200
        rows = next(n for n in tree.root.children if str(n.label).startswith("rows"))
        rows.expand()
        await pilot.pause()
        assert 100 <= len(rows.children) <= 101  # first page + "… more"
    _run(make_app(), scenario)


def test_result_pane_scrolls_independently(make_app, lab_client):
    lab_client.http.answers = [{"body": {f"k{i}": i for i in range(300)}}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.get_record", mms_id="1")
        await _send(pilot)
        tree = pilot.app.query_one("#response-tree", Tree)
        tree.focus()
        await pilot.press("pagedown", "pagedown")
        await pilot.pause()
        assert tree.scroll_y > 0
        assert pilot.app.query_one("#inputs").scroll_y == 0
    _run(make_app(), scenario)


def test_xml_marc_shown_as_fields(make_app, lab_client):
    marc = ('<bib><record><datafield tag="505" ind1="0" ind2="0">'
            '<subfield code="a">Part one</subfield></datafield></record></bib>')
    lab_client.http.answers = [{"body": {"anies": [marc]}}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.get_record", mms_id="1")
        await _send(pilot)
        tree = pilot.app.query_one("#response-tree", Tree)
        for _ in range(6):  # each level's children appear only once expanded
            for node in list(_walk(tree.root)):
                node.expand()
            await pilot.pause()
        labels = [str(n.label) for n in _walk(tree.root)]
        assert any("505" in label for label in labels)
        assert any("Part one" in label for label in labels)
    _run(make_app(), scenario)


def test_history_loads_record_into_panes(make_app, lab_client):
    lab_client.http.answers = [{"body": {"title": "a"}}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.get_record", mms_id="990000000000001", view="brief")
        await _send(pilot)
        pilot.app.query_one("#field-mms_id", Input).value = "other"
        pilot.app.select_operation("Users.get_user")
        await pilot.pause()
        pilot.app.query_one("#op-tree").focus()
        await pilot.press("h")
        await pilot.pause()
        assert isinstance(pilot.app.screen, HistoryScreen)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert pilot.app.current_operation.qualname == "BibliographicRecords.get_record"
        assert pilot.app.query_one("#field-mms_id", Input).value == "990000000000001"
        assert pilot.app.query_one("#field-view", Input).value == "brief"
        assert "200" in _status(pilot.app)
    _run(make_app(), scenario)


def test_export_preview_lists_replacements(make_app, lab_client, tmp_path):
    lab_client.http.answers = [{"body": {"mms_id": "990000000000001"}}]

    async def scenario(pilot):
        await _open(pilot, "BibliographicRecords.get_record", mms_id="990000000000001")
        await _send(pilot)
        pilot.app.query_one("#op-tree").focus()
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(pilot.app.screen, ExportScreen)
        assert "<mms_id_1>" in str(pilot.app.screen.query_one("#export-preview").render())
        await pilot.press("ctrl+s")
        await pilot.pause()
        [out] = list((tmp_path / "ev").glob("*/*.redacted.json"))
        assert "990000000000001" not in out.read_text()
        json.loads(out.read_text())
    _run(make_app(), scenario)


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)
