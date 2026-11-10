"""Regression tests for the final-review findings on Alma Lab (issue #230)."""
import asyncio
import json
import os
import threading
from urllib.parse import quote

import pytest

from almaapitk.lab.capture import Recorder
from almaapitk.lab.catalog import find_operation
from almaapitk.lab.cli import main
from almaapitk.lab.evidence import EvidenceError
from almaapitk.lab.redact import redact
from almaapitk.lab.runner import Session


@pytest.fixture
def patched(lab_client, monkeypatch, tmp_path):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    monkeypatch.chdir(tmp_path)
    return lab_client


# 1 (critical): concurrent sends must not share one recording ---------------
def test_second_run_while_first_is_running_is_refused(patched, tmp_path):
    gate_open = threading.Event()
    started = threading.Event()

    def slow():
        started.set()
        gate_open.wait(5)

    patched.http.before_answer = slow
    session = Session("SANDBOX", evidence_dir=tmp_path / "ev")
    op = find_operation("bibs.get_record")
    results = {}
    t = threading.Thread(target=lambda: results.setdefault("first", session.run(op, {"mms_id": "111"})))
    t.start()
    assert started.wait(5)
    with pytest.raises(RuntimeError, match="already running"):
        session.run(op, {"mms_id": "222"})
    gate_open.set()
    t.join(5)
    first = results["first"]
    assert first.inputs == {"mms_id": "111"} and "/bibs/111?" in first.requests[0].url


# 2: optional bool with default None must load and may stay unset -----------
def test_optional_bool_default_none_loads_and_stays_unset(patched, tmp_path):
    pytest.importorskip("textual")
    from almaapitk.lab.app.app import LabApp
    from almaapitk.lab.app.inputs import InputsPane

    async def main_():
        app = LabApp(Session("SANDBOX", evidence_dir=tmp_path / "ev"))
        async with app.run_test(size=(120, 30)) as pilot:
            app.select_operation("Users.cancel_user_rs_request")
            await pilot.pause()
            values = app.query_one(InputsPane).values()
            bools = [p.name for p in app.current_operation.params if p.kind == "bool" and p.default is None]
            assert bools and all(values[b] == "" for b in bools)
    asyncio.run(main_())


# 3: quitting with a confirmation open must not hang ------------------------
def test_quit_during_write_confirmation_does_not_hang(patched, tmp_path):
    pytest.importorskip("textual")
    from almaapitk.lab.app.app import LabApp

    async def main_():
        app = LabApp(Session("SANDBOX", evidence_dir=tmp_path / "ev"))
        async with app.run_test(size=(120, 30)) as pilot:
            app.select_operation("BibliographicRecords.delete_record")
            await pilot.pause()
            app.query_one("#field-mms_id").value = "1"
            app.action_send()
            await pilot.pause(0.3)
            await pilot.press("ctrl+q")
    asyncio.run(asyncio.wait_for(main_(), timeout=10))
    assert patched.http.calls == []


# 4: redaction of common Alma shapes ----------------------------------------
def test_redact_invoice_loan_user_and_url_encoded():
    record = {
        "inputs": {"user_id": "jdoe@example.org"},
        "requests": [{"url": f"https://h/almaws/v1/users/{quote('jdoe@example.org', safe='')}/loans", "body": None,
                      "response_body": json.dumps({"item_loan": [{"loan_id": "L1", "item_barcode": "BC123456"}]})}],
        "result": {"id": "35000000000000001", "number": "INV-2026-77", "vendor": {"value": "VEND1", "desc": "Vendor Ltd"},
                   "invoice_lines": {"invoice_line": [{"id": "35000000000000002"}]},
                   "job_description": "Senior librarian", "status": {"value": "ACTIVE"}},
    }
    out, _ = redact(record)
    text = json.dumps(out)
    for secret in ("35000000000000001", "INV-2026-77", "VEND1", "Vendor Ltd", "35000000000000002",
                   "BC123456", "Senior librarian", "jdoe", "example.org"):
        assert secret not in text, secret
    assert out["result"]["status"]["value"] == "ACTIVE"


# 5: evidence folder problems are caught before anything is sent -----------
def test_unwritable_evidence_dir_sends_nothing(patched, tmp_path):
    blocker = tmp_path / "f"
    blocker.write_text("x")
    session = Session("SANDBOX", evidence_dir=blocker / "ev", gate=lambda *a: True)
    with pytest.raises(EvidenceError):
        session.run(find_operation("bibs.delete_record"), {"mms_id": "1"})
    assert patched.http.calls == []


def test_evidence_write_failure_after_send_still_prints_result(patched, monkeypatch, capsys):
    def boom(record, d):
        raise EvidenceError("disk full")

    monkeypatch.setattr("almaapitk.lab.runner.write_record", boom)
    patched.http.answers = [{"status": 204, "body": b""}]
    code = main(["call", "bibs.delete_record", "--mms-id", "1", "--allow-writes"])
    captured = capsys.readouterr()
    assert code == 2
    assert "BibliographicRecords.delete_record" in captured.out and "204" in captured.out
    assert "disk full" in captured.err


# 6: --confirm-write covers one call, not a whole steps file ----------------
def test_run_refuses_confirm_write(patched, tmp_path, capsys):
    steps = tmp_path / "s.json"
    steps.write_text(json.dumps([{"operation": "bibs.delete_record", "inputs": {"mms_id": "1"}}]))
    assert main(["run", str(steps), "--env", "PRODUCTION", "--confirm-write", "delete_record"]) == 2
    assert patched.http.calls == []
    assert "call" in capsys.readouterr().err


# 7: global options before the subcommand are honoured ---------------------
def test_env_before_subcommand_is_honoured(patched, tmp_path, capsys):
    patched.http.answers = [{"body": {}}]
    ev = tmp_path / "chosen"
    assert main(["--env", "PRODUCTION", "--evidence-dir", str(ev), "call", "bibs.get_record", "--mms-id", "1",
                 "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["environment"] == "PRODUCTION"
    assert list(ev.glob("*/*.json"))


# 8: the recorded body is the body that was sent ---------------------------
def test_recorded_body_is_exactly_what_was_sent(lab_client):
    lab_client.http.answers = [{"body": {}}]
    rec = Recorder(lab_client, gate=lambda *a: True)
    rec.install()
    rec.start()
    lab_client.post("almaws/v1/bibs", data={"title": "ספר"})
    sent = lab_client.http.calls[0][2]
    prepared = __import__("requests").Request("POST", "http://x", data=sent.get("data"), json=sent.get("json")).prepare()
    expected = prepared.body.decode() if isinstance(prepared.body, bytes) else prepared.body
    assert rec.requests[0].body == expected


# 10: export errors are reported, not crashes ------------------------------
def test_export_to_missing_folder_exit_2(patched, tmp_path, capsys):
    patched.http.answers = [{"body": {}}]
    main(["call", "bibs.get_record", "--mms-id", "1", "--json"])
    rec_id = json.loads(capsys.readouterr().out)["id"]
    assert main(["export", rec_id, "--out", str(tmp_path / "no" / "such" / "x.json")]) == 2
    assert "cannot write" in capsys.readouterr().err
