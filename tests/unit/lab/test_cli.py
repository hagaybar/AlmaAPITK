"""Alma Lab headless command (issue #230)."""
import builtins
import json

import pytest

from almaapitk.lab.cli import main


@pytest.fixture
def cli_env(lab_client, monkeypatch, tmp_path):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    monkeypatch.chdir(tmp_path)
    return lab_client


def test_call_get_summary_and_exit_0(cli_env, capsys, tmp_path):
    cli_env.http.answers = [{"body": {"title": "Sample title"}}]
    code = main(["call", "bibs.get_record", "--mms-id", "990000000000001", "--expect", "status == 200",
                 "--evidence-dir", str(tmp_path / "ev")])
    out = capsys.readouterr().out
    assert code == 0
    assert "BibliographicRecords.get_record" in out and "200" in out and "✓ status == 200" in out
    assert "evidence " in out
    assert list((tmp_path / "ev").glob("*/*.json"))


def test_param_flag_form(cli_env, capsys):
    cli_env.http.answers = [{"body": {}}]
    assert main(["call", "bibs.get_record", "--param", "mms_id=1", "--param", "view=brief"]) == 0
    assert cli_env.http.calls[0][2]["params"]["view"] == "brief"


def test_failed_expect_exit_1(cli_env, capsys):
    cli_env.http.answers = [{"body": {"title": "a"}}]
    assert main(["call", "bibs.get_record", "--mms-id", "1", "--expect", "title == b"]) == 1
    assert "✗ title == b" in capsys.readouterr().out


def test_bad_input_exit_2(cli_env, capsys):
    assert main(["call", "acq.list_invoices", "--limit", "abc"]) == 2
    assert "limit" in capsys.readouterr().err


def test_sandbox_write_refused_without_allow_writes(cli_env, capsys):
    code = main(["call", "bibs.delete_record", "--mms-id", "1"])
    assert code == 1 and cli_env.http.calls == []
    assert "--allow-writes" in capsys.readouterr().err


def test_sandbox_write_with_allow_writes(cli_env):
    cli_env.http.answers = [{"status": 204, "body": b""}]
    assert main(["call", "bibs.delete_record", "--mms-id", "1", "--allow-writes"]) == 0
    assert cli_env.http.calls[0][0] == "DELETE"


def test_production_write_refused_without_matching_confirm(cli_env, capsys):
    cli_env.environment = "PRODUCTION"
    code = main(["call", "bibs.delete_record", "--mms-id", "1", "--env", "PRODUCTION", "--confirm-write", "get_record"])
    assert code == 1 and cli_env.http.calls == []
    assert "--confirm-write delete_record" in capsys.readouterr().err


def test_production_write_with_matching_confirm(cli_env):
    cli_env.http.answers = [{"status": 204, "body": b""}]
    assert main(["call", "bibs.delete_record", "--mms-id", "1", "--env", "PRODUCTION",
                 "--confirm-write", "delete_record"]) == 0


def test_list_json(capsys):
    assert main(["list", "--domain", "bibs", "--json"]) == 0
    ops = json.loads(capsys.readouterr().out)
    get = next(o for o in ops if o["operation"] == "BibliographicRecords.get_record")
    assert get["writes"] is False and "mms_id" in [p["name"] for p in get["params"]]


def test_run_steps_file(cli_env, capsys, tmp_path):
    cli_env.http.answers = [{"body": {"title": "a"}}, {"body": {"title": "b"}}]
    steps = tmp_path / "steps.json"
    steps.write_text(json.dumps([
        {"operation": "bibs.get_record", "inputs": {"mms_id": "1"}, "expect": ["title == a"]},
        {"operation": "bibs.get_record", "inputs": {"mms_id": "2"}, "expect": ["title == a"]},
    ]))
    assert main(["run", str(steps)]) == 1
    out = capsys.readouterr().out
    assert sum(line.startswith("BibliographicRecords.get_record") for line in out.splitlines()) == 2


def test_show_and_export_redacted(cli_env, capsys, tmp_path):
    cli_env.http.answers = [{"body": {"mms_id": "990000000000001"}}]
    main(["call", "bibs.get_record", "--mms-id", "990000000000001", "--json"])
    rec = json.loads(capsys.readouterr().out)
    assert main(["show", rec["id"]]) == 0
    assert rec["id"] in capsys.readouterr().out
    out_file = tmp_path / "x.json"
    assert main(["export", rec["id"], "--out", str(out_file)]) == 0
    assert "990000000000001" not in out_file.read_text()


def test_evidence_not_writable_exit_2(cli_env, capsys, tmp_path):
    blocker = tmp_path / "f"
    blocker.write_text("x")
    cli_env.http.answers = [{"body": {}}]
    assert main(["call", "bibs.get_record", "--mms-id", "1", "--evidence-dir", str(blocker / "ev")]) == 2
    assert "evidence" in capsys.readouterr().err


def test_no_textual_message(monkeypatch, capsys):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("almaapitk.lab.app") or name.startswith("textual"):
            raise ImportError("No module named 'textual'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert main([]) == 2
    assert "pip install almaapitk[lab]" in capsys.readouterr().err


def test_headless_silences_library_logs(cli_env, capsys):
    """Library log lines go to stdout and would corrupt --json output for agents."""
    import logging

    seen = []

    class Collect(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    handler = Collect()
    logger = logging.getLogger("almapi.api_client")
    logger.addHandler(handler)
    before = logging.getLogger("almapi").level
    try:
        cli_env.http.answers = [{"body": {"title": "a"}}]
        assert main(["call", "bibs.get_record", "--mms-id", "1", "--json"]) == 0
        assert seen == []
        assert json.loads(capsys.readouterr().out)["operation"] == "BibliographicRecords.get_record"
    finally:
        logger.removeHandler(handler)
        logging.getLogger("almapi").setLevel(before)
