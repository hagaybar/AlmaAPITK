"""Alma Lab app: the Raw branch and the raw call form (reads, writes without a baseline)."""
import asyncio
import json

import pytest

pytest.importorskip("textual")

from textual.widgets import Button, Input, Select, Static, TextArea, Tree  # noqa: E402

from almaapitk.lab.app.app import LabApp  # noqa: E402
from almaapitk.lab.app.confirm import ConfirmWrite  # noqa: E402
from almaapitk.lab.app.history import HistoryScreen  # noqa: E402
from almaapitk.lab.app.inputs import InputsPane  # noqa: E402
from almaapitk.lab.endpoints import AREA_TITLES, Endpoint  # noqa: E402
from almaapitk.lab.runner import InputError, Session  # noqa: E402

COURSES = "/almaws/v1/courses"
COURSE = "/almaws/v1/courses/{course_id}"
TASK_LIST = "almaws/v1/task-lists/requested-resources"


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


def _pane(app) -> InputsPane:
    return app.query_one(InputsPane)


async def _open(pilot, method, path, **values):
    pilot.app.select_endpoint(method, path)
    await pilot.pause()
    for name, value in values.items():
        _pane(pilot.app).query_one(f"#raw-{name}", Input).value = value
    await pilot.pause()


async def _send(pilot):
    pilot.app.action_send()
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def _text(app, selector):
    return str(app.query_one(selector).render())


def _raw_node(app):
    tree = app.query_one("#op-tree", Tree)
    return tree.root.children[-1]


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def test_raw_branch_after_domains_with_areas_and_custom(make_app):
    async def scenario(pilot):
        raw = _raw_node(pilot.app)
        assert str(raw.label).startswith("Raw · all Alma endpoints")
        assert not raw.is_expanded
        labels = [str(c.label) for c in raw.children]
        assert len(labels) == 9 and labels[-1] == "custom path…"
        assert {lab.rsplit(" (", 1)[0] for lab in labels[:-1]} == set(AREA_TITLES.values())
        courses = next(c for c in raw.children if str(c.label).startswith("Courses ("))
        assert str(courses.label) == f"Courses ({len(courses.children)})"
        leaves = [str(n.label) for n in courses.children]
        assert "GET  /courses" in leaves
        assert any(lab.startswith("POST  /courses") and "✎" in lab for lab in leaves)
        bibs = next(c for c in raw.children if str(c.label).startswith("Bibs ("))
        bib = next(n for n in bibs.children if isinstance(n.data, Endpoint)
                   and n.data.key == "GET /almaws/v1/bibs/{mms_id}")
        assert "→ BibliographicRecords." in str(bib.label) and "+2" in str(bib.label)
    _run(make_app(), scenario)


def test_search_matches_raw_paths_and_summaries(make_app):
    async def scenario(pilot):
        pilot.app.query_one("#search", Input).value = "courses"
        await pilot.pause()
        raw = _raw_node(pilot.app)
        assert str(raw.label).startswith("Raw · all Alma endpoints") and raw.is_expanded
        endpoints = [n.data for n in _walk(raw) if isinstance(n.data, Endpoint)]
        assert endpoints and all("courses" in (e.short_path + e.summary).lower() for e in endpoints)
        assert any(e.key == f"GET {COURSES}" for e in endpoints)
    _run(make_app(), scenario)


def test_raw_get_sends_and_records_raw_evidence(make_app, lab_client, tmp_path):
    lab_client.http.answers = [{"body": {"course": [], "total_record_count": 0}}]

    async def scenario(pilot):
        await _open(pilot, "GET", COURSES, **{"query-limit": "5"})
        title = _text(pilot.app, "#inputs-title")
        assert f"RAW  GET {COURSES}" in title
        assert "from Alma API definitions, 2026-05-29" in title
        assert "No almaapitk method for this yet" in title
        pilot.app.query_one("#expect", TextArea).text = "status == 200"
        await _send(pilot)
        status = _text(pilot.app, "#status-line")
        assert "200" in status and "1/1 checks" in status
        [(method, url, kwargs)] = lab_client.http.calls
        assert method == "GET" and url.endswith("/courses") and kwargs["params"]["limit"] == 5
        assert "raw: GET /almaws/v1/courses" in _text(pilot.app, "#evidence-body")
        [saved] = list((tmp_path / "ev").glob("*/*.json"))
        assert json.loads(saved.read_text())["raw"] is True
    _run(make_app(), scenario)


def test_wrapped_endpoint_title_names_the_method(make_app):
    async def scenario(pilot):
        await _open(pilot, "GET", "/almaws/v1/bibs/{mms_id}")
        title = _text(pilot.app, "#inputs-title")
        assert "almaapitk: " in title and "BibliographicRecords.get_record" in title
        assert _pane(pilot.app).query("#raw-path-mms_id")
    _run(make_app(), scenario)


def test_raw_input_errors_shown_on_fields(make_app, lab_client):
    async def scenario(pilot):
        await _open(pilot, "GET", COURSES, **{"query-limit": "abc"})
        await _send(pilot)
        assert "whole number" in _text(pilot.app, "#error-query-limit")
        await _open(pilot, "GET", COURSE)
        await _send(pilot)
        assert "required" in _text(pilot.app, "#error-path-course_id")
        assert lab_client.http.calls == []
    _run(make_app(), scenario)


def test_custom_path_get_sends_to_typed_path(make_app, lab_client):
    lab_client.http.answers = [{"body": {}}]

    async def scenario(pilot):
        pilot.app.select_custom()
        await pilot.pause()
        pane = _pane(pilot.app)
        assert pilot.app.current_endpoint.custom
        pane.query_one("#raw-method", Select).value = "GET"
        pane.query_one("#raw-custom-path", Input).value = TASK_LIST
        pane.query_one("#raw-custom-query", TextArea).text = "library=MAIN\nlimit=3"
        await pilot.pause()
        await _send(pilot)
        [(method, url, kwargs)] = lab_client.http.calls
        assert method == "GET" and url.endswith("/" + TASK_LIST)
        assert kwargs["params"]["library"] == "MAIN"
    _run(make_app(), scenario)


def test_custom_path_errors(make_app, lab_client):
    async def scenario(pilot):
        pilot.app.select_custom()
        await pilot.pause()
        pane = _pane(pilot.app)
        pane.query_one("#raw-method", Select).value = "GET"
        pane.query_one("#raw-custom-path", Input).value = "/"
        await pilot.pause()
        await _send(pilot)
        assert "fixed segment" in _text(pilot.app, "#error-custom-path")
        pane.query_one("#raw-custom-path", Input).value = "almaws/v1/task-lists/{x}"
        await _send(pilot)
        assert "concrete path" in _text(pilot.app, "#error-custom-path")
        pane.query_one("#raw-custom-path", Input).value = TASK_LIST
        pane.query_one("#raw-custom-query", TextArea).text = "no equals sign"
        await _send(pilot)
        assert "name=value" in _text(pilot.app, "#error-custom-query")
        assert lab_client.http.calls == []
        with pytest.raises(InputError) as exc:
            pane.query_one("#raw-custom-query", TextArea).text = ""
            pane.query_one("#raw-custom-path", Input).value = ""
            pane.raw_request()
        assert exc.value.field == "custom-path"
    _run(make_app(), scenario)


def test_history_reopens_raw_record(make_app, lab_client):
    lab_client.http.answers = [{"body": {}}]

    async def scenario(pilot):
        await _open(pilot, "GET", COURSES, **{"query-limit": "5", "query-q": "name~sample"})
        pilot.app.query_one("#expect", TextArea).text = "status == 200"
        await _send(pilot)
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
        assert pilot.app.current_endpoint.key == f"GET {COURSES}"
        assert pilot.app.current_operation is None
        pane = _pane(pilot.app)
        assert pane.query_one("#raw-query-limit", Input).value == "5"
        assert pane.query_one("#raw-query-q", Input).value == "name~sample"
        assert pane.query_one("#expect", TextArea).text == "status == 200"
        assert "200" in _text(pilot.app, "#status-line")
    _run(make_app(), scenario)


def test_history_reopens_custom_record(make_app, lab_client):
    lab_client.http.answers = [{"body": {}}]

    async def scenario(pilot):
        pilot.app.select_custom()
        await pilot.pause()
        pane = _pane(pilot.app)
        pane.query_one("#raw-method", Select).value = "GET"
        pane.query_one("#raw-custom-path", Input).value = TASK_LIST
        pane.query_one("#raw-custom-query", TextArea).text = "library=MAIN"
        await _send(pilot)
        [path] = list(pilot.app.session.evidence_dir.glob("*/*.json"))
        await pilot.app.load_record(path)
        await pilot.pause()
        pane = _pane(pilot.app)
        assert pilot.app.current_endpoint.custom
        assert pane.query_one("#raw-method", Select).value == "GET"
        assert pane.query_one("#raw-custom-path", Input).value == "/" + TASK_LIST
        assert pane.query_one("#raw-custom-query", TextArea).text == "library=MAIN"
    _run(make_app(), scenario)


def test_put_with_get_twin_is_locked(make_app, lab_client):
    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        pane = _pane(pilot.app)
        body = pane.query_one("#raw-body", TextArea)
        assert body.read_only and body.text == ""
        assert "Fill the path fields, then load the current record" in _text(pilot.app, "#raw-body-note")
        assert pane.query_one("#send", Button).disabled
        await _send(pilot)
        assert lab_client.http.calls == []
    _run(make_app(), scenario)


def test_post_body_prefilled_from_example(make_app):
    async def scenario(pilot):
        await _open(pilot, "POST", "/almaws/v1/bibs")
        pane = _pane(pilot.app)
        assert pane.query_one("#raw-body", TextArea).text.strip()
        assert not pane.query_one("#raw-body", TextArea).read_only
        assert not pane.query_one("#send", Button).disabled
    _run(make_app(), scenario)


def test_sandbox_raw_post_confirmed_and_sent(make_app, lab_client):
    lab_client.http.answers = [{"body": {"code": "X"}}]

    async def scenario(pilot):
        await _open(pilot, "POST", COURSES)
        pane = _pane(pilot.app)
        if pane.query("#raw-format"):
            pane.query_one("#raw-format", Select).value = "json"
        pane.query_one("#raw-body", TextArea).text = '{"code": "X", "name": "Sample"}'
        await pilot.pause()
        pilot.app.action_send()
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, ConfirmWrite)
        await pilot.press("enter")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        [(method, url, kwargs)] = lab_client.http.calls
        assert method == "POST" and url.endswith("/courses")
    _run(make_app(), scenario)


def test_production_raw_delete_needs_confirm_word(make_app, lab_client):
    lab_client.http.answers = [{"status": 204, "body": b""}]

    async def scenario(pilot):
        await _open(pilot, "DELETE", COURSE, **{"path-course_id": "1"})
        pilot.app.action_send()
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, ConfirmWrite)
        assert pilot.app.screen.op_name == "DELETE courses"
        await pilot.press(*"delete_record", "enter")  # wrong word: refused
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert lab_client.http.calls == []
        pilot.app.action_send()
        await pilot.pause(0.3)
        await pilot.press(*"DELETE", "space", *"courses", "enter")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert [c[0] for c in lab_client.http.calls] == ["DELETE"]
    _run(make_app("PRODUCTION"), scenario)


def test_switching_back_to_typed_operation_still_works(make_app, lab_client):
    lab_client.http.answers = [{"body": {"title": "a"}}]

    async def scenario(pilot):
        await _open(pilot, "GET", COURSES)
        pilot.app.select_operation("BibliographicRecords.get_record")
        await pilot.pause()
        assert pilot.app.current_endpoint is None
        pilot.app.query_one("#field-mms_id", Input).value = "1"
        await _send(pilot)
        assert lab_client.http.calls[0][1].endswith("/bibs/1")
        assert isinstance(pilot.app.query_one("#status-line"), Static)
    _run(make_app(), scenario)
