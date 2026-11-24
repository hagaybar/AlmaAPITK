"""Issue #256 round 3: fill-back of updates, <ask>, and the never-send rule.

Saved baselines are masked. An edited copy is applied field by field onto the
record as it is in Alma now, so masked fields the user left alone keep their
real values, and no placeholder ever reaches Alma. Fake data only (R9).
"""
from __future__ import annotations

import json

import pytest

from almaapitk import AlmaAPIClient
from almaapitk.lab.capture import MaskedValueRefused
from almaapitk.lab.endpoints import custom_endpoint, get_endpoint
from almaapitk.lab.fillback import ASK, merge, render
from almaapitk.lab.runner import InputError, RawRequest, Session
from tests.unit.lab.conftest import TEST_KEY
from tests.unit.test_issue_256_one_mask import (
    BARCODE,
    EMAIL,
    FIRST,
    LAST,
    PRIMARY_ID,
    STREET,
    USER_NOTE,
    assert_clean,
    fake_user,
)

USER = f"almaws/v1/users/{PRIMARY_ID}"
NEW_EMAIL = "new.address@example.org"
PLACEHOLDERS = ("<redacted>", "<...>", "***REDACTED***", "<ask>", "<asked>")


@pytest.fixture
def lab_cli(lab_client, monkeypatch, tmp_path):
    def fresh(env):
        client = AlmaAPIClient(lab_client.environment, api_key=TEST_KEY)
        client._session.request = lab_client.http
        return client

    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", fresh)
    monkeypatch.chdir(tmp_path)
    return lab_client


def _files(folder) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(folder.rglob("*")) if p.is_file())


def _baseline_out(main, tmp_path):
    base = tmp_path / "current.json"
    assert main(["raw", "PUT", USER, "--baseline-out", str(base),
                 "--evidence-dir", str(tmp_path / "ev")]) == 0
    return base


def _put(main, tmp_path, edited, *extra):
    return main(["raw", "PUT", USER, "--body-file", str(edited), "--baseline",
                 str(tmp_path / "current.json"), "--allow-writes",
                 "--evidence-dir", str(tmp_path / "ev"), *extra])


def _edit(base, tmp_path, change) -> object:
    data = json.loads(base.read_text(encoding="utf-8"))
    change(data)
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return edited


def _sent_put(http) -> dict:
    method, _, kwargs = http.calls[-1]
    assert method == "PUT"
    return kwargs["json"] if kwargs.get("json") is not None else json.loads(kwargs["data"])


def _set_email(value):
    def change(data):
        data["contact_info"]["email"][0]["email_address"] = value
    return change


# --- the owner's walkthrough: change a user's email from the command line ---

def test_email_change_from_a_masked_baseline_sends_real_values(lab_cli, capsys, tmp_path):
    from almaapitk.lab.cli import main

    lab_cli.http.answers = [{"body": fake_user()}, {"body": fake_user()}, {"body": fake_user()}]
    base = _baseline_out(main, tmp_path)
    assert_clean(base.read_text(encoding="utf-8"))  # the file is masked
    edited = _edit(base, tmp_path, _set_email(NEW_EMAIL))
    capsys.readouterr()

    assert _put(main, tmp_path, edited) == 0
    sent = _sent_put(lab_cli.http)
    expected = fake_user()
    expected["contact_info"]["email"][0]["email_address"] = NEW_EMAIL
    assert sent == expected  # only the email changed; every masked field is real again
    for marker in PLACEHOLDERS:
        assert marker not in json.dumps(sent)
    err = capsys.readouterr().err
    assert f'contact_info.email[0].email_address: "{EMAIL}" → "{NEW_EMAIL}"' in err  # raw on screen
    saved = _files(tmp_path / "ev")
    assert_clean(saved)
    assert NEW_EMAIL not in saved  # the new email is personal data too


def test_ask_prompts_sends_and_never_saves(lab_cli, capsys, tmp_path, monkeypatch):
    from almaapitk.lab import cli

    asked = []
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: asked.append(prompt) or "2031-12-31Z")
    lab_cli.http.answers = [{"body": fake_user()}, {"body": fake_user()},
                            {"body": {**fake_user(), "expiry_date": "2031-12-31Z"}}]
    base = _baseline_out(cli.main, tmp_path)
    edited = _edit(base, tmp_path, lambda d: d.update(expiry_date=ASK))  # a non-personal field
    capsys.readouterr()

    assert _put(cli.main, tmp_path, edited) == 0
    assert asked == ["value for expiry_date (<ask>): "]
    assert _sent_put(lab_cli.http)["expiry_date"] == "2031-12-31Z"
    err = capsys.readouterr().err
    assert '"2030-01-01Z" → "2031-12-31Z"' in err  # the value is shown before sending
    saved = _files(tmp_path / "ev")
    assert "2031-12-31Z" not in saved  # sent, never saved
    assert "<asked>" in saved and "<ask>" in saved  # the edit as typed, the answer hidden


def test_cancelled_ask_sends_nothing(lab_cli, capsys, tmp_path, monkeypatch):
    from almaapitk.lab import cli

    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "")
    lab_cli.http.answers = [{"body": fake_user()}]
    base = _baseline_out(cli.main, tmp_path)
    edited = _edit(base, tmp_path, _set_email(ASK))
    assert _put(cli.main, tmp_path, edited) == 2
    assert "no value given" in capsys.readouterr().err
    assert [c[0] for c in lab_cli.http.calls] == ["GET"]  # only the baseline-out GET


def test_record_changed_in_alma_is_refused(lab_cli, capsys, tmp_path):
    from almaapitk.lab.cli import main

    changed = {**fake_user(), "user_group": {"value": "OTHERGROUP", "desc": "Other"}}
    lab_cli.http.answers = [{"body": fake_user()}, {"body": changed}]
    base = _baseline_out(main, tmp_path)
    edited = _edit(base, tmp_path, _set_email(NEW_EMAIL))
    assert _put(main, tmp_path, edited) == 1
    assert "the record changed in Alma since --baseline-out" in capsys.readouterr().err
    assert [c[0] for c in lab_cli.http.calls] == ["GET", "GET"]  # no PUT


@pytest.mark.parametrize("change, where", [
    # a changed partial ID is still a placeholder
    (lambda d: d.update(primary_id="<...>999"), "primary_id"),
    # a new entry copied from a masked one
    (lambda d: d["contact_info"]["phone"].append({"phone_number": "<redacted>"}),
     "contact_info.phone[1].phone_number"),
    # a placeholder inside a changed value
    (lambda d: d.update(comment="see <redacted>"), "comment"),
])
def test_hard_rule_no_placeholder_is_ever_sent(lab_cli, capsys, tmp_path, change, where):
    from almaapitk.lab.cli import main

    lab_cli.http.answers = [{"body": fake_user()}, {"body": fake_user()}]
    base = _baseline_out(main, tmp_path)
    edited = _edit(base, tmp_path, change)
    assert _put(main, tmp_path, edited) == 1
    err = capsys.readouterr().err
    assert "a masked value would be sent" in err and where in err
    assert [c[0] for c in lab_cli.http.calls] == ["GET", "GET"]  # no PUT


def test_new_list_entry_is_sent_as_typed_and_old_ones_filled_back(lab_cli, tmp_path):
    from almaapitk.lab.cli import main

    lab_cli.http.answers = [{"body": fake_user()}, {"body": fake_user()}, {"body": fake_user()}]
    base = _baseline_out(main, tmp_path)
    extra = {"email_address": NEW_EMAIL, "preferred": False, "email_type": [{"value": "work"}]}
    edited = _edit(base, tmp_path, lambda d: d["contact_info"]["email"].append(extra))
    assert _put(main, tmp_path, edited) == 0
    emails = _sent_put(lab_cli.http)["contact_info"]["email"]
    assert emails == [fake_user()["contact_info"]["email"][0], extra]


def test_untouched_masked_fields_keep_values_from_alma_now(lab_client, tmp_path, monkeypatch):
    """Fill-back uses the fresh record, not the baseline: a masked field Alma
    changed meanwhile (invisible in the masked compare) is not overwritten."""
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    session = Session("SANDBOX", evidence_dir=tmp_path, gate=lambda *a: True)
    later = fake_user()
    later["contact_info"]["phone"][0]["phone_number"] = "+972-3-555-0199"
    lab_client.http.answers = [{"body": fake_user()}, {"body": later}, {"body": later}]
    put = RawRequest(endpoint=get_endpoint("PUT", "/almaws/v1/users/{user_id}"),
                     path_params={"user_id": PRIMARY_ID}, query={}, body=None)
    base = session.fetch_baseline(put)
    edit = fake_user()  # the app's baseline is raw
    edit["contact_info"]["email"][0]["email_address"] = NEW_EMAIL
    rec = session.run_raw(RawRequest(endpoint=put.endpoint, path_params=put.path_params, query={},
                                     body=json.dumps(edit)), baseline=base)
    assert rec.refused is None and rec.error is None
    sent = _sent_put(lab_client.http)
    assert sent["contact_info"]["phone"][0]["phone_number"] == "+972-3-555-0199"
    assert sent["contact_info"]["email"][0]["email_address"] == NEW_EMAIL
    assert "contact_info.email[0].email_address" in rec.body_diff
    for value in (FIRST, LAST, BARCODE, STREET, USER_NOTE):
        assert value in json.dumps(sent)


def test_placeholder_in_a_non_update_body_is_refused(lab_client, tmp_path, monkeypatch):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    session = Session("SANDBOX", evidence_dir=tmp_path, gate=lambda *a: True)
    req = RawRequest(endpoint=custom_endpoint("POST", "almaws/v1/users"), path_params={},
                     query={}, body=json.dumps({"primary_id": "<...>123", "note": ASK}))
    with pytest.raises(InputError, match="masked value"):
        session.run_raw(req)
    assert lab_client.http.calls == []


@pytest.mark.parametrize("method, path, data", [
    ("POST", "almaws/v1/users", {"first_name": "<redacted>"}),
    ("PUT", "almaws/v1/users/x", "<user><first_name>&lt;redacted&gt;</first_name></user>"),
    ("GET", "almaws/v1/users/<...>123", None),
    ("PUT", "almaws/v1/users/x", {"email": "<asked>"}),
])
def test_transport_backstop_never_sends_a_placeholder(lab_client, tmp_path, monkeypatch,
                                                      method, path, data):
    """Below the runner: whatever calls the Lab's client, a placeholder is not sent."""
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    session = Session("SANDBOX", evidence_dir=tmp_path, gate=lambda *a: True)
    client = session.client
    session._recorder.start()
    with pytest.raises(MaskedValueRefused):
        client.raw_request(method, path, data=data)
    assert lab_client.http.calls == []
    assert session._recorder.requests[-1].sent is False


def test_merge_reports_set_add_and_remove():
    base = {"a": 1, "b": "<redacted>", "c": [1, 2], "d": "x"}
    fresh = {"a": 1, "b": "real", "c": [1, 2], "d": "x"}
    edit = {"a": 2, "b": "<redacted>", "c": [1, 2, 3], "e": "new"}
    merged, changes = merge(edit, base, fresh)
    assert merged == {"a": 2, "b": "real", "c": [1, 2, 3], "e": "new"}
    text = render(changes)
    assert "  a: 1 → 2" in text and "+ c[2]: 3" in text and '+ e: "new"' in text
    assert '- d: "x"' in text
    assert not any(line.lstrip("+- ").startswith("b:") for line in text.splitlines())
