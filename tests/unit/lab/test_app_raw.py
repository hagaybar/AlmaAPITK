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
        body = pane.query_one("#raw-req-body", TextArea)
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
        assert pane.query_one("#raw-req-body", TextArea).text.strip()
        assert not pane.query_one("#raw-req-body", TextArea).read_only
        assert not pane.query_one("#send", Button).disabled
    _run(make_app(), scenario)


def test_sandbox_raw_post_confirmed_and_sent(make_app, lab_client):
    lab_client.http.answers = [{"body": {"code": "X"}}]

    async def scenario(pilot):
        await _open(pilot, "POST", COURSES)
        pane = _pane(pilot.app)
        if pane.query("#raw-format"):
            pane.query_one("#raw-format", Select).value = "json"
        pane.query_one("#raw-req-body", TextArea).text = '{"code": "X", "name": "Sample"}'
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


# --- Task 6: baseline flow for updates ---------------------------------------

USER = "/almaws/v1/users/{user_id}"
RECORD = {"id": "1", "code": "SAMPLE", "name": "Sample course"}


async def _press(pilot, selector):
    pilot.app.query_one(selector, Button).press()
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _load_baseline(pilot):
    await _press(pilot, "#load-baseline")


def _body(app) -> TextArea:
    return _pane(app).query_one("#raw-req-body", TextArea)


def _send_button(app) -> Button:
    return _pane(app).query_one("#send", Button)


def test_put_form_has_baseline_section(make_app):
    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        pane = _pane(pilot.app)
        assert pane.query_one("#raw-bq-view", Input).value == "brief"  # the GET's own default
        assert str(pane.query_one("#load-baseline", Button).label) == "Load current record"
        assert pane.query("#body-from-file") and pane.query("#body-from-last")
        assert pane.baseline is None and pane.needs_baseline
        assert len(pilot.app.query("#raw-body")) == 1  # only the result pane's
    _run(make_app(), scenario)


def test_load_current_record_fills_body_and_enables_send(make_app, lab_client):
    lab_client.http.answers = [{"body": RECORD}]

    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        assert _send_button(pilot.app).disabled
        await _load_baseline(pilot)
        assert not isinstance(pilot.app.screen, ConfirmWrite)  # a read: no confirmation
        [(method, url, kwargs)] = lab_client.http.calls
        assert method == "GET" and url.endswith("/courses/1") and kwargs["params"]["view"] == "brief"
        body = _body(pilot.app)
        assert not body.read_only and json.loads(body.text) == RECORD
        assert not _send_button(pilot.app).disabled
        assert _pane(pilot.app).baseline is not None
        assert "200" in _text(pilot.app, "#status-line")  # shown like any call
        assert "raw: GET /almaws/v1/courses/{course_id}" in _text(pilot.app, "#evidence-body")
    _run(make_app(), scenario)


def test_changing_path_or_baseline_query_disables_send_again(make_app, lab_client):
    lab_client.http.answers = [{"body": RECORD}, {"body": RECORD}]

    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        await _load_baseline(pilot)
        pane = _pane(pilot.app)
        pane.query_one("#raw-path-course_id", Input).value = "2"
        await pilot.pause()
        assert pane.baseline is None and _send_button(pilot.app).disabled and _body(pilot.app).read_only
        pane.query_one("#raw-path-course_id", Input).value = "1"
        await pilot.pause()
        await _load_baseline(pilot)
        assert not _send_button(pilot.app).disabled
        pane.query_one("#raw-bq-view", Input).value = "full"
        await pilot.pause()
        assert pane.baseline is None and _send_button(pilot.app).disabled
        await _send(pilot)
        assert [c[0] for c in lab_client.http.calls] == ["GET", "GET"]
    _run(make_app(), scenario)


def test_send_stays_locked_after_failed_baseline(make_app, lab_client):
    lab_client.http.answers = [{"status": 404, "body": {"errorsExist": True}}]

    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        await _load_baseline(pilot)
        assert _pane(pilot.app).baseline is None
        assert _body(pilot.app).read_only and _body(pilot.app).text == ""
        assert _send_button(pilot.app).disabled
        assert "could not be loaded" in _text(pilot.app, "#raw-body-note")
        await _send(pilot)
        assert [c[0] for c in lab_client.http.calls] == ["GET"]
    _run(make_app(), scenario)


def test_baseline_needs_path_values(make_app, lab_client):
    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE)
        await _load_baseline(pilot)
        assert "required" in _text(pilot.app, "#error-path-course_id")
        assert lab_client.http.calls == []
    _run(make_app(), scenario)


def _edited(text):
    data = json.loads(text)
    data["name"] = "Changed course"
    return json.dumps(data, indent=2)


def test_sandbox_put_confirmed_and_evidence_shows_diff(make_app, lab_client, tmp_path):
    lab_client.http.answers = [{"body": RECORD}, {"body": RECORD}, {"body": {**RECORD, "name": "Changed course"}}]

    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        await _load_baseline(pilot)
        _body(pilot.app).text = _edited(_body(pilot.app).text)
        await pilot.pause()
        pilot.app.action_send()
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, ConfirmWrite)
        await pilot.press("enter")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert [c[0] for c in lab_client.http.calls] == ["GET", "GET", "PUT"]
        evidence = _text(pilot.app, "#evidence-body")
        assert '-  "name": "Sample course"' in evidence and '+  "name": "Changed course"' in evidence
        assert "baseline: " in evidence
    _run(make_app(), scenario)


def test_production_put_confirmation_asks_for_put_courses(make_app, lab_client):
    lab_client.http.answers = [{"body": RECORD}, {"body": RECORD}, {"body": RECORD}]

    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        await _load_baseline(pilot)
        _body(pilot.app).text = _edited(_body(pilot.app).text)
        await pilot.pause()
        pilot.app.action_send()
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, ConfirmWrite)
        assert pilot.app.screen.op_name == "PUT courses"
        await pilot.press(*"PUT", "space", *"courses", "enter")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert [c[0] for c in lab_client.http.calls] == ["GET", "GET", "PUT"]
    _run(make_app("PRODUCTION"), scenario)


def test_changed_record_not_sent_and_reload_offered(make_app, lab_client):
    newer = {**RECORD, "name": "Someone else's edit"}
    lab_client.http.answers = [{"body": RECORD}, {"body": newer}, {"body": newer}]

    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        reload = pilot.app.query_one("#reload-baseline", Button)
        assert not reload.display
        await _load_baseline(pilot)
        _body(pilot.app).text = _edited(_body(pilot.app).text)
        await _send(pilot)
        assert not isinstance(pilot.app.screen, ConfirmWrite)
        assert [c[0] for c in lab_client.http.calls] == ["GET", "GET"]
        assert "Not sent: the record changed since you loaded it" in _text(pilot.app, "#status-line")
        assert reload.display
        assert _send_button(pilot.app).disabled and _pane(pilot.app).baseline is None
        await _press(pilot, "#reload-baseline")
        assert json.loads(_body(pilot.app).text)["name"] == "Someone else's edit"
        assert not _send_button(pilot.app).disabled and not reload.display
    _run(make_app(), scenario)


def test_baseline_query_follows_put_query_until_edited(make_app, lab_client):
    lab_client.http.answers = [{"body": {"primary_id": "x"}}]

    async def scenario(pilot):
        await _open(pilot, "PUT", USER, **{"path-user_id": "u1"})
        pane = _pane(pilot.app)
        pane.query_one("#raw-query-user_id_type", Input).value = "all_unique"
        await pilot.pause()
        assert pane.query_one("#raw-bq-user_id_type", Input).value == "all_unique"
        pane.query_one("#raw-bq-user_id_type", Input).value = "other"
        await pilot.pause()
        pane.query_one("#raw-query-user_id_type", Input).value = "all_unique2"
        await pilot.pause()
        assert pane.query_one("#raw-bq-user_id_type", Input).value == "other"
        assert pane.raw_request().baseline_query["user_id_type"] == "other"
        await _load_baseline(pilot)
        [(_, url, kwargs)] = lab_client.http.calls
        assert url.endswith("/users/u1") and kwargs["params"]["user_id_type"] == "other"
    _run(make_app(), scenario)


def test_custom_put_on_indexed_path_switches_to_its_form(make_app, lab_client):
    async def scenario(pilot):
        pilot.app.select_custom()
        await pilot.pause()
        pane = _pane(pilot.app)
        pane.query_one("#raw-method", Select).value = "PUT"
        pane.query_one("#raw-custom-path", Input).value = "almaws/v1/users/u1"
        pane.query_one("#raw-custom-query", TextArea).text = "user_id_type=all_unique"
        await pilot.pause()
        await _send(pilot)
        assert lab_client.http.calls == []
        assert pilot.app.current_endpoint.key == f"PUT {USER}"
        pane = _pane(pilot.app)
        assert pane.query_one("#raw-path-user_id", Input).value == "u1"
        assert pane.query_one("#raw-query-user_id_type", Input).value == "all_unique"
        assert pane.needs_baseline and _send_button(pilot.app).disabled
        assert "switched to its form so the update can start from the current record" in _text(
            pilot.app, "#status-line")
    _run(make_app(), scenario)


def test_history_reopens_put_locked_with_baseline_query(make_app, lab_client):
    lab_client.http.answers = [{"body": RECORD}, {"body": RECORD}, {"body": RECORD}]

    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1", "bq-view": "full"})
        await _load_baseline(pilot)
        _body(pilot.app).text = _edited(_body(pilot.app).text)
        pilot.app.action_send()
        await pilot.pause(0.3)
        await pilot.press("enter")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        put = next(p for p in pilot.app.session.evidence_dir.glob("*/*.json")
                   if json.loads(p.read_text())["endpoint"]["method"] == "PUT")
        pilot.app.select_operation("Users.get_user")
        await pilot.pause()
        await pilot.app.load_record(put)
        await pilot.pause()
        pane = _pane(pilot.app)
        assert pilot.app.current_endpoint.key == f"PUT {COURSE}"
        assert pane.query_one("#raw-path-course_id", Input).value == "1"
        assert pane.query_one("#raw-bq-view", Input).value == "full"
        assert _body(pilot.app).read_only and _body(pilot.app).text == ""
        assert _send_button(pilot.app).disabled and pane.baseline is None
    _run(make_app(), scenario)


def test_post_example_follows_format_until_edited(make_app):
    async def scenario(pilot):
        await _open(pilot, "POST", "/almaws/v1/bibs/authorities")  # json + xml; the example is XML
        pane = _pane(pilot.app)
        fmt = pane.query_one("#raw-format", Select)
        assert fmt.value == "json" and _body(pilot.app).text == ""
        fmt.value = "xml"
        await pilot.pause()
        assert _body(pilot.app).text.lstrip().startswith("<authority>")
        fmt.value = "json"
        await pilot.pause()
        assert _body(pilot.app).text == ""
        fmt.value = "xml"
        await pilot.pause()
        _body(pilot.app).text = "<authority>mine</authority>"
        await pilot.pause()
        fmt.value = "json"
        await pilot.pause()
        assert _body(pilot.app).text == "<authority>mine</authority>"
    _run(make_app(), scenario)


def test_body_from_file_and_from_last_response(make_app, lab_client, tmp_path):
    lab_client.http.answers = [{"body": {"code": "FROM-LAST"}}, {"body": RECORD}]
    source = tmp_path / "body.json"
    source.write_text('{"code": "FROM-FILE"}', encoding="utf-8")

    async def scenario(pilot):
        await _open(pilot, "GET", COURSES)
        await _send(pilot)
        await _open(pilot, "POST", COURSES)
        await _press(pilot, "#body-from-last")
        assert json.loads(_body(pilot.app).text) == {"code": "FROM-LAST"}
        _pane(pilot.app).query_one("#body-from-file", Button).press()
        await pilot.pause()
        prompt = pilot.app.screen.query_one("#body-file-path", Input)
        prompt.value = str(source)
        await pilot.press("enter")
        await pilot.pause()
        assert _body(pilot.app).text == '{"code": "FROM-FILE"}'
        # an update's body is replaced only after its baseline is loaded
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        await _press(pilot, "#body-from-last")
        assert _body(pilot.app).text == "" and _body(pilot.app).read_only
        await _load_baseline(pilot)
        _pane(pilot.app).query_one("#body-from-file", Button).press()
        await pilot.pause()
        pilot.app.screen.query_one("#body-file-path", Input).value = str(source)
        await pilot.press("enter")
        await pilot.pause()
        assert _body(pilot.app).text == '{"code": "FROM-FILE"}'
    _run(make_app(), scenario)


# --- round 1 ---------------------------------------------------------------------

LIB_HOURS = "almaws/v1/conf/libraries/MAIN/open-hours"  # GET in the index, no PUT


async def _custom_put(pilot, path, query=""):
    pilot.app.select_custom()
    await pilot.pause()
    pane = _pane(pilot.app)
    pane.query_one("#raw-method", Select).value = "PUT"
    pane.query_one("#raw-custom-path", Input).value = path
    pane.query_one("#raw-custom-query", TextArea).text = query
    await pilot.pause()


def test_custom_put_on_get_only_path_needs_current_record(make_app, lab_client):
    lab_client.http.answers = [{"body": {"day": []}}, {"body": {"day": []}}, {"body": {}}]

    async def scenario(pilot):
        await _custom_put(pilot, LIB_HOURS)
        await _send(pilot)
        assert lab_client.http.calls == []
        pane = _pane(pilot.app)
        ep = pilot.app.current_endpoint
        assert ep.custom and ep.method == "PUT" and pane.needs_baseline
        assert pane.query_one("#raw-path-libraryCode", Input).value == "MAIN"
        assert pane.query("#raw-bq-from") and pane.query("#load-baseline")
        assert _send_button(pilot.app).disabled and _body(pilot.app).read_only
        await _send(pilot)
        assert lab_client.http.calls == []
        await _load_baseline(pilot)
        _body(pilot.app).text = '{"day": [1]}'
        await pilot.pause()
        pilot.app.action_send()
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, ConfirmWrite)
        await pilot.press("enter")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert [c[0] for c in lab_client.http.calls] == ["GET", "GET", "PUT"]
        assert lab_client.http.calls[2][1].endswith("/" + LIB_HOURS)
        put = next(p for p in pilot.app.session.evidence_dir.glob("*/*.json")
                   if json.loads(p.read_text())["endpoint"]["method"] == "PUT")
        await pilot.app.load_record(put)
        await pilot.pause()
        reopened = _pane(pilot.app)
        assert pilot.app.current_endpoint.custom and reopened.needs_baseline
        assert reopened.query_one("#raw-path-libraryCode", Input).value == "MAIN"
        assert _send_button(pilot.app).disabled and _body(pilot.app).read_only
    _run(make_app(), scenario)


def test_baseline_query_values_stripped_like_the_runner(make_app, lab_client):
    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1", "bq-view": " full "})
        assert _pane(pilot.app).raw_request().baseline_query == {"view": "full"}
        assert _pane(pilot.app).baseline_key()[1] == (("view", "full"),)
    _run(make_app(), scenario)


def test_double_send_switches_once(make_app, lab_client, monkeypatch):
    loads = []
    original = InputsPane.load_raw

    async def counting(self, endpoint):
        loads.append(endpoint.key)
        await original(self, endpoint)
    monkeypatch.setattr(InputsPane, "load_raw", counting)

    async def scenario(pilot):
        await _custom_put(pilot, "almaws/v1/users/u1")
        loads.clear()
        pilot.app.action_send()
        pilot.app.action_send()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert loads == [f"PUT {USER}"]
        assert lab_client.http.calls == []
    _run(make_app(), scenario)


# --- final review ----------------------------------------------------------------

def test_custom_post_load_from_get_fills_body(make_app, lab_client):
    lab_client.http.answers = [{"body": {"a": 1}}]

    async def scenario(pilot):
        pilot.app.select_custom()
        await pilot.pause()
        pane = _pane(pilot.app)
        pane.query_one("#raw-method", Select).value = "POST"
        pane.query_one("#raw-custom-path", Input).value = TASK_LIST
        await pilot.pause()
        await _press(pilot, "#body-from-get")
        assert not isinstance(pilot.app.screen, ConfirmWrite)  # a read: no confirmation
        [(method, url, _kw)] = lab_client.http.calls
        assert method == "GET" and url.endswith("/" + TASK_LIST)
        body = _body(pilot.app)
        assert json.loads(body.text) == {"a": 1} and not body.read_only
        assert pilot.app.current_endpoint.custom and not pane.needs_baseline
    _run(make_app(), scenario)


def test_custom_get_load_from_get_refused(make_app, lab_client):
    async def scenario(pilot):
        pilot.app.select_custom()
        await pilot.pause()
        _pane(pilot.app).query_one("#raw-custom-path", Input).value = TASK_LIST
        await pilot.pause()
        await _press(pilot, "#body-from-get")
        assert lab_client.http.calls == []
    _run(make_app(), scenario)


def test_stale_refusal_keeps_the_edit_after_reload(make_app, lab_client):
    newer = {**RECORD, "name": "Someone else's edit"}
    lab_client.http.answers = [{"body": RECORD}, {"body": newer}, {"body": newer}]

    async def scenario(pilot):
        await _open(pilot, "PUT", COURSE, **{"path-course_id": "1"})
        await _load_baseline(pilot)
        mine = _edited(_body(pilot.app).text)
        _body(pilot.app).text = mine
        await _send(pilot)
        await _press(pilot, "#reload-baseline")
        assert json.loads(_body(pilot.app).text)["name"] == "Someone else's edit"
        kept = _pane(pilot.app).query_one("#raw-prev-edit", TextArea)
        assert kept.read_only and kept.text == mine
    _run(make_app(), scenario)
