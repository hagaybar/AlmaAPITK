"""Alma Lab headless ``endpoints`` and ``raw`` commands."""
import json

import pytest

from almaapitk.lab.cli import main

COURSE_PATH = "almaws/v1/courses/<course_id>"
COURSE_BODY = {"code": "X", "name": "Old"}


@pytest.fixture
def cli_env(lab_client, monkeypatch, tmp_path):
    """Every command closes its client, so each ``main`` call gets a fresh one on the shared script."""
    from almaapitk import AlmaAPIClient
    from tests.unit.lab.conftest import TEST_KEY

    def fresh(env):
        client = AlmaAPIClient(lab_client.environment, api_key=TEST_KEY)
        client._session.request = lab_client.http
        return client

    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", fresh)
    monkeypatch.chdir(tmp_path)
    return lab_client


def _baseline(cli_env, tmp_path, *extra, body=COURSE_BODY):
    cli_env.http.answers = [{"body": body}]
    base = tmp_path / "current.json"
    code = main(["raw", "PUT", COURSE_PATH, "--baseline-out", str(base),
                 "--evidence-dir", str(tmp_path / "ev"), *extra])
    return code, base


def _edited(tmp_path, name="New"):
    f = tmp_path / "edited.json"
    f.write_text(json.dumps({"code": "X", "name": name}), encoding="utf-8")
    return f


def test_endpoints_area_lists_one_line_each(capsys):
    assert main(["endpoints", "--area", "courses"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 29
    assert any(l.startswith("GET /courses") for l in lines)


def test_endpoints_unknown_area_exit_2(capsys):
    assert main(["endpoints", "--area", "nope"]) == 2
    assert "nope" in capsys.readouterr().err


def test_endpoints_search_json_has_wrapped_by(capsys):
    assert main(["endpoints", "--search", "bibs/{mms_id}", "--json"]) == 0
    items = json.loads(capsys.readouterr().out)
    assert items and {"method", "path", "area", "summary", "writes", "wrapped_by", "params"} <= set(items[0])
    get = next(i for i in items if i["method"] == "GET" and i["path"] == "/bibs/{mms_id}")
    assert any(w.startswith("BibliographicRecords.") for w in get["wrapped_by"])


def test_raw_get_summary_and_exit_0(cli_env, capsys, tmp_path):
    cli_env.http.answers = [{"body": {"course": []}}]
    code = main(["raw", "GET", "almaws/v1/courses", "--query", "limit=5", "--expect", "status == 200",
                 "--evidence-dir", str(tmp_path / "ev")])
    out = capsys.readouterr().out
    assert code == 0
    assert "raw GET /almaws/v1/courses" in out and "✓ status == 200" in out
    assert cli_env.http.calls[0][2]["params"] == {"limit": 5}


def test_raw_unknown_path_is_custom(cli_env, capsys):
    cli_env.http.answers = [{"body": {}}]
    assert main(["raw", "GET", "almaws/v1/not-a-real-thing"]) == 0
    assert "not in the Alma API definitions; sending as a custom path" in capsys.readouterr().err


def test_raw_path_without_fixed_segment_exit_2(cli_env, capsys):
    assert main(["raw", "GET", "{x}"]) == 2
    assert cli_env.http.calls == []


def test_put_without_baseline_exit_2_nothing_sent(cli_env, capsys, tmp_path):
    code = main(["raw", "PUT", COURSE_PATH, "--body-file", str(_edited(tmp_path)), "--allow-writes"])
    assert code == 2 and cli_env.http.calls == []
    assert "baseline" in capsys.readouterr().err


def test_baseline_out_writes_body_and_sidecar(cli_env, capsys, tmp_path):
    code, base = _baseline(cli_env, tmp_path)
    assert code == 0 and len(cli_env.http.calls) == 1 and cli_env.http.calls[0][0] == "GET"
    assert json.loads(base.read_text()) == COURSE_BODY
    evid = (tmp_path / "current.json.evidence").read_text().strip()
    assert evid and evid in capsys.readouterr().out


def test_baseline_out_failed_get_exit_1(cli_env, tmp_path):
    cli_env.http.answers = [{"status": 404, "body": {"errorsExist": True}}]
    code = main(["raw", "PUT", COURSE_PATH, "--baseline-out", str(tmp_path / "b.json")])
    assert code == 1


def test_full_put_with_allow_writes(cli_env, capsys, tmp_path):
    _, base = _baseline(cli_env, tmp_path)
    cli_env.http.calls.clear()
    cli_env.http.answers = [{"body": COURSE_BODY}, {"body": {"code": "X", "name": "New"}}]
    code = main(["raw", "PUT", COURSE_PATH, "--body-file", str(_edited(tmp_path)),
                 "--baseline", str(base), "--allow-writes", "--evidence-dir", str(tmp_path / "ev")])
    assert code == 0, capsys.readouterr()
    assert [c[0] for c in cli_env.http.calls] == ["GET", "PUT"]


def test_sandbox_put_refused_without_allow_writes(cli_env, capsys, tmp_path):
    _, base = _baseline(cli_env, tmp_path)
    cli_env.http.calls.clear()
    cli_env.http.answers = [{"body": COURSE_BODY}]
    code = main(["raw", "PUT", COURSE_PATH, "--body-file", str(_edited(tmp_path)),
                 "--baseline", str(base), "--evidence-dir", str(tmp_path / "ev")])
    assert code == 1 and [c[0] for c in cli_env.http.calls] == ["GET"]
    assert "--allow-writes" in capsys.readouterr().err


def test_production_put_needs_confirm_word(cli_env, capsys, tmp_path):
    cli_env.environment = "PRODUCTION"
    _, base = _baseline(cli_env, tmp_path, "--env", "PRODUCTION")
    cli_env.http.calls.clear()
    cli_env.http.answers = [{"body": COURSE_BODY}]
    args = ["raw", "PUT", COURSE_PATH, "--body-file", str(_edited(tmp_path)), "--baseline", str(base),
            "--env", "PRODUCTION", "--evidence-dir", str(tmp_path / "ev")]
    assert main(args) == 1
    assert "PUT courses" in capsys.readouterr().err
    assert [c[0] for c in cli_env.http.calls] == ["GET"]
    cli_env.http.calls.clear()
    cli_env.http.answers = [{"body": COURSE_BODY}, {"body": {}}]
    assert main(args + ["--confirm-write", "PUT courses"]) == 0
    assert [c[0] for c in cli_env.http.calls] == ["GET", "PUT"]


def test_changed_record_refused_exit_1(cli_env, capsys, tmp_path):
    _, base = _baseline(cli_env, tmp_path)
    cli_env.http.calls.clear()
    cli_env.http.answers = [{"body": {"code": "X", "name": "Someone else edited"}}]
    code = main(["raw", "PUT", COURSE_PATH, "--body-file", str(_edited(tmp_path)),
                 "--baseline", str(base), "--allow-writes", "--evidence-dir", str(tmp_path / "ev")])
    assert code == 1 and [c[0] for c in cli_env.http.calls] == ["GET"]
    assert "changed" in capsys.readouterr().err


def test_baseline_without_sidecar_exit_2(cli_env, capsys, tmp_path):
    f = tmp_path / "hand.json"
    f.write_text(json.dumps(COURSE_BODY))
    code = main(["raw", "PUT", COURSE_PATH, "--body-file", str(_edited(tmp_path)),
                 "--baseline", str(f), "--allow-writes"])
    assert code == 2 and cli_env.http.calls == []
    assert "--baseline-out" in capsys.readouterr().err


def test_edited_baseline_file_exit_2(cli_env, capsys, tmp_path):
    _, base = _baseline(cli_env, tmp_path)
    base.write_text(json.dumps({"code": "X", "name": "hand edit"}))
    cli_env.http.calls.clear()
    code = main(["raw", "PUT", COURSE_PATH, "--body-file", str(_edited(tmp_path)),
                 "--baseline", str(base), "--allow-writes", "--evidence-dir", str(tmp_path / "ev")])
    assert code == 2 and cli_env.http.calls == []
    assert "unedited --baseline-out file" in capsys.readouterr().err
