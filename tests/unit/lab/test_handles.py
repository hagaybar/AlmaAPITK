"""Issue #256 round 3: user ID handles (@u1, ...) in the full-screen app.

Handles live in memory while the app is open; requests swap them for the real
ID at send time; evidence, baselines and logs never hold them. Single CLI
commands do not share handles and refuse them. Fake data only (R9).
"""
from __future__ import annotations

import asyncio
import json
import logging

import pytest

from almaapitk.lab.handles import HANDLE, Handles, UnknownHandle, holds_handle
from tests.unit.test_issue_256_one_mask import BARCODE, PRIMARY_ID, fake_user

NEW_EMAIL = "new.address@example.org"


# --- the handle book -----------------------------------------------------

def test_collect_gives_each_user_id_one_handle_in_order():
    h = Handles()
    h.collect(fake_user())
    h.collect(json.dumps({"requester": {"value": "FAKEREQ0000456", "desc": "Fake Name"},
                          "user_primary_id": PRIMARY_ID}))
    h.collect_path({"user_id": "FAKEPATH000789", "mms_id": "990000000000000001"})
    assert h.items() == [("@u1", PRIMARY_ID), ("@u2", BARCODE), ("@u3", "FAKEREQ0000456"),
                         ("@u4", "FAKEPATH000789")]
    assert h.handle_for(PRIMARY_ID) == "@u1"
    assert h.handle_for("990000000000000001") is None  # an MMS ID is not a user ID
    assert repr(h) == "Handles(4)" and PRIMARY_ID not in repr(h)


def test_resolve_swaps_handles_but_not_emails_or_words():
    h = Handles()
    h.add(PRIMARY_ID)
    assert h.resolve("almaws/v1/users/@u1") == f"almaws/v1/users/{PRIMARY_ID}"
    assert h.resolve('{"user_primary_id": "@u1"}') == f'{{"user_primary_id": "{PRIMARY_ID}"}}'
    for text in ("see @u1.txt", "fake.patron@example.org", "x@u1", "@u1x", "foo@u1-bar"):
        assert h.resolve(text) == text and not holds_handle(text)
    with pytest.raises(UnknownHandle, match="@u2 is not a handle"):
        h.resolve("users/@u2")
    assert HANDLE.pattern  # exported for the docs


def test_cli_refuses_handles_and_sends_nothing(lab_client, monkeypatch, tmp_path, capsys):
    from almaapitk.lab.cli import main

    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    code = main(["raw", "GET", "almaws/v1/users/@u1", "--evidence-dir", str(tmp_path / "ev")])
    assert code == 2
    assert "only inside the full-screen app" in capsys.readouterr().err
    code = main(["call", "users.get_user", "--user-id", "@u1", "--evidence-dir", str(tmp_path / "ev")])
    assert code == 2
    assert "only inside the full-screen app" in capsys.readouterr().err
    assert lab_client.http.calls == []


def test_cli_help_says_handles_are_app_only(capsys):
    from almaapitk.lab.cli import main

    with pytest.raises(SystemExit):
        main(["raw", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "ID handles (@u1) work only inside the full-screen app" in out
    assert "single commands do not share them" in out


# --- in the app ------------------------------------------------------------

pytest.importorskip("textual")

from textual.widgets import Input, TextArea, Tree  # noqa: E402

from almaapitk.lab.app.app import LabApp  # noqa: E402
from almaapitk.lab.app.confirm import ConfirmWrite  # noqa: E402
from almaapitk.lab.app.handles import AskValue, HandlePicker  # noqa: E402
from almaapitk.lab.app.inputs import InputsPane  # noqa: E402
from almaapitk.lab.runner import Session  # noqa: E402

USER_GET = "/almaws/v1/users/{user_id}"


@pytest.fixture
def make_app(lab_client, monkeypatch, tmp_path):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    return lambda: LabApp(Session("SANDBOX", evidence_dir=tmp_path / "ev"))


def _run(app, scenario):
    async def main():
        async with app.run_test(size=(140, 40)) as pilot:
            await scenario(pilot)
    asyncio.run(main())


async def _open(pilot, method, path, **values):
    pilot.app.select_endpoint(method, path)
    await pilot.pause()
    pane = pilot.app.query_one(InputsPane)
    for name, value in values.items():
        pane.query_one(f"#raw-{name}", Input).value = value
    await pilot.pause()


async def _settle(pilot):
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def _tree_labels(app) -> str:
    tree = app.query_one("#response-tree", Tree)
    out = []

    def walk(node):
        for child in node.children:
            out.append(str(child.label))
            child.expand()
            walk(child)
    walk(tree.root)
    return "\n".join(out)


def _files(folder) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(folder.rglob("*")) if p.is_file())


def test_app_shows_handles_and_sends_the_real_id(make_app, lab_client, tmp_path):
    lab_client.http.answers = [{"body": fake_user()}, {"body": fake_user()}]

    async def scenario(pilot):
        await _open(pilot, "GET", USER_GET, **{"path-user_id": PRIMARY_ID})
        pilot.app.action_send()
        await _settle(pilot)
        assert pilot.app.handles.items()[:2] == [("@u1", PRIMARY_ID), ("@u2", BARCODE)]
        pilot.app.query_one("#response-tree", Tree).root.expand_all()
        await pilot.pause()
        labels = _tree_labels(pilot.app)
        assert f"primary_id: {PRIMARY_ID}  @u1" in labels  # beside the real ID

        # the next request uses the handle; Alma gets the real ID
        await _open(pilot, "GET", USER_GET, **{"path-user_id": "@u1"})
        pilot.app.action_send()
        await _settle(pilot)
        assert lab_client.http.calls[-1][1].endswith(f"/users/{PRIMARY_ID}")
    _run(make_app(), scenario)
    saved = _files(tmp_path / "ev")
    assert "@u1" not in saved and "@u2" not in saved  # evidence holds the masked ID
    assert "<...>123" in saved and PRIMARY_ID not in saved


def test_app_unknown_handle_is_not_sent(make_app, lab_client):
    async def scenario(pilot):
        await _open(pilot, "GET", USER_GET, **{"path-user_id": "@u7"})
        pilot.app.action_send()
        await _settle(pilot)
        assert "@u7 is not a handle" in str(pilot.app.query_one("#status-line").render())
        assert lab_client.http.calls == []
    _run(make_app(), scenario)


def test_picker_inserts_the_handle_into_the_focused_field(make_app, lab_client):
    lab_client.http.answers = [{"body": fake_user()}]

    async def scenario(pilot):
        await _open(pilot, "GET", USER_GET, **{"path-user_id": PRIMARY_ID})
        pilot.app.action_send()
        await _settle(pilot)
        await _open(pilot, "GET", USER_GET)
        field = pilot.app.query_one(InputsPane).query_one("#raw-path-user_id", Input)
        field.value = ""
        field.focus()
        await pilot.pause()
        await pilot.press("ctrl+o")
        await pilot.pause()
        assert isinstance(pilot.app.screen, HandlePicker)
        await pilot.press("down", "enter")  # the second handle: the barcode
        await pilot.pause()
        assert field.value == "@u2"
    _run(make_app(), scenario)


def test_app_update_with_handle_and_ask(make_app, lab_client, tmp_path, caplog):
    """The owner's walkthrough in the app: load, set the email to <ask>, type it
    at the prompt, see it in the confirmation, send; nothing saved holds it."""
    after = fake_user()
    after["contact_info"]["email"][0]["email_address"] = NEW_EMAIL
    lab_client.http.answers = [{"body": fake_user()}, {"body": fake_user()},
                               {"body": fake_user()}, {"body": after}]
    caplog.set_level(logging.DEBUG)

    async def scenario(pilot):
        await _open(pilot, "GET", USER_GET, **{"path-user_id": PRIMARY_ID})
        pilot.app.action_send()
        await _settle(pilot)
        await _open(pilot, "PUT", USER_GET, **{"path-user_id": "@u1"})
        pane = pilot.app.query_one(InputsPane)
        pilot.app.load_baseline()
        await _settle(pilot)
        body = pane.query_one("#raw-req-body", TextArea)
        data = json.loads(body.text)
        data["contact_info"]["email"][0]["email_address"] = "<ask>"
        body.text = json.dumps(data, indent=2)
        await pilot.pause()
        pilot.app.action_send()
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, AskValue)
        pilot.app.screen.query_one(Input).value = NEW_EMAIL
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert isinstance(pilot.app.screen, ConfirmWrite)
        changes = str(pilot.app.screen.query_one("#confirm-changes").render())
        assert NEW_EMAIL in changes and "contact_info.email[0].email_address" in changes
        await pilot.press("enter")
        await _settle(pilot)
        method, url, sent = lab_client.http.calls[-1]
        assert method == "PUT" and url.endswith(f"/users/{PRIMARY_ID}")
        assert sent["json"] == after  # real values everywhere, the typed email in place
    _run(make_app(), scenario)
    saved = _files(tmp_path / "ev")
    assert NEW_EMAIL not in saved and "@u1" not in saved and PRIMARY_ID not in saved
    assert "@u1" not in caplog.text and NEW_EMAIL not in caplog.text
