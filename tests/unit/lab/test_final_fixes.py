"""Alma Lab raw calls: final-review fixes (secrets in query, wrapped-by order, custom
"Load from GET", body rules, short path values, baseline mismatch messages)."""
import json

import pytest

from almaapitk.lab.catalog import discover_operations
from almaapitk.lab.cli import main
from almaapitk.lab.endpoints import custom_endpoint, get_endpoint, wrapped_by
from almaapitk.lab.redact import redact
from almaapitk.lab.runner import InputError, RawRequest, Session

SECRET = "<password_value>"
USER = "/almaws/v1/users/{user_id}"
COURSE = "/almaws/v1/courses/{course_id}"
COURSE_PATH = "almaws/v1/courses/<course_id>"
TASK_LIST = "almaws/v1/task-lists/requested-resources"


def _session(lab_client, monkeypatch, tmp_path, gate=None):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    return Session("SANDBOX", evidence_dir=tmp_path, gate=gate, source="headless", command="test")


@pytest.fixture
def cli_env(lab_client, monkeypatch, tmp_path):
    from almaapitk import AlmaAPIClient
    from tests.unit.lab.conftest import TEST_KEY

    def fresh(env):
        client = AlmaAPIClient(lab_client.environment, api_key=TEST_KEY)
        client._session.request = lab_client.http
        return client

    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", fresh)
    monkeypatch.chdir(tmp_path)
    return lab_client


def _all_evidence(folder):
    return "\n".join(p.read_text() for p in folder.glob("**/*.json"))


# --- 1. secrets typed into query fields -------------------------------------------

def test_secret_query_value_sent_but_masked_in_evidence(lab_client, monkeypatch, tmp_path):
    session = _session(lab_client, monkeypatch, tmp_path, gate=lambda *a: True)
    lab_client.http.answers = [{"body": {}}]
    req = RawRequest(endpoint=get_endpoint("POST", USER), path_params={"user_id": "<user_id>"},
                     query={"op": "auth", "password": SECRET})
    rec = session.run_raw(req)
    [(method, _url, kwargs)] = lab_client.http.calls
    assert method == "POST" and kwargs["params"]["password"] == SECRET  # still sent to Alma
    assert rec.inputs["query"] == {"op": "auth", "password": "***"}
    assert SECRET not in session.last_path.read_text()


def test_secret_in_baseline_query_masked(lab_client, monkeypatch, tmp_path):
    session = _session(lab_client, monkeypatch, tmp_path, gate=lambda *a: True)
    lab_client.http.answers = [{"body": {"a": 1}}, {"body": {"a": 1}}, {"body": {}}]
    put = RawRequest(endpoint=custom_endpoint("PUT", TASK_LIST), path_params={}, query={},
                     body='{"a": 2}', baseline_query={"ApiKey": SECRET})
    base = session.fetch_baseline(put)
    rec = session.run_raw(put, baseline=base)
    assert rec.error is None and rec.refused is None
    assert [c[0] for c in lab_client.http.calls] == ["GET", "GET", "PUT"]
    assert lab_client.http.calls[1][2]["params"]["ApiKey"] == SECRET
    assert rec.inputs["baseline_query"] == {"ApiKey": "***"}
    assert SECRET not in _all_evidence(tmp_path)


def test_rerun_of_masked_secret_asks_to_retype(lab_client, monkeypatch, tmp_path):
    session = _session(lab_client, monkeypatch, tmp_path, gate=lambda *a: True)
    lab_client.http.answers = [{"body": {}}]
    rec = session.run_raw(RawRequest(endpoint=get_endpoint("POST", USER),
                                     path_params={"user_id": "<user_id>"},
                                     query={"op": "auth", "password": SECRET}))
    with pytest.raises(InputError) as exc:
        session.rerun(rec)
    assert exc.value.field == "password"
    assert len(lab_client.http.calls) == 1


@pytest.mark.parametrize("form", ["separate", "joined"])
def test_cli_secret_query_masked_in_json_and_command(cli_env, capsys, tmp_path, form):
    cli_env.http.answers = [{"body": {}}]
    pair = "password=" + SECRET
    flags = ["--query", pair] if form == "separate" else ["--query=" + pair]
    code = main(["raw", "POST", "almaws/v1/users/<user_id>", "--query", "op=auth", *flags,
                 "--allow-writes", "--json", "--evidence-dir", str(tmp_path / "ev")])
    out, err = capsys.readouterr()
    assert code == 0, err
    assert cli_env.http.calls[0][2]["params"]["password"] == SECRET
    record = json.loads(out)
    assert SECRET not in out and SECRET not in err
    assert "password=***" in record["command"]
    assert SECRET not in _all_evidence(tmp_path / "ev")


# --- 2. wrapped-by order ------------------------------------------------------------

def test_wrapped_by_leads_with_the_plain_reader():
    assert wrapped_by(get_endpoint("GET", "/almaws/v1/bibs/{mms_id}"))[0] == \
        "BibliographicRecords.get_record"
    ops = {o.qualname: o for o in discover_operations()}
    first = wrapped_by(get_endpoint("GET", USER))[0]
    assert ops[first].verbs == {"GET"}


# --- 3. query in the path -----------------------------------------------------------

def test_cli_query_in_path_exit_2(cli_env, capsys):
    assert main(["raw", "GET", "almaws/v1/courses?limit=5"]) == 2
    assert "put query parameters in --query, not in the path" in capsys.readouterr().err
    assert cli_env.http.calls == []


# --- 4. custom paths: Load from GET (headless) -------------------------------------

def test_cli_custom_post_baseline_out_then_informational_baseline(cli_env, capsys, tmp_path):
    ev = str(tmp_path / "ev")
    base = tmp_path / "current.json"
    cli_env.http.answers = [{"body": {"a": 1}}]
    assert main(["raw", "POST", TASK_LIST, "--baseline-out", str(base), "--evidence-dir", ev]) == 0
    assert [c[0] for c in cli_env.http.calls] == ["GET"]
    assert cli_env.http.calls[0][1].endswith("/" + TASK_LIST)
    assert json.loads(base.read_text()) == {"a": 1}
    assert (tmp_path / "current.json.evidence").is_file()
    edited = tmp_path / "edited.json"
    edited.write_text('{"a": 2}', encoding="utf-8")
    cli_env.http.answers = [{"body": {"a": 1}}, {"body": {}}]
    capsys.readouterr()
    code = main(["raw", "POST", TASK_LIST, "--body-file", str(edited), "--baseline", str(base),
                 "--allow-writes", "--json", "--evidence-dir", ev])
    out, err = capsys.readouterr()
    assert code == 0, err
    assert [c[0] for c in cli_env.http.calls] == ["GET", "GET", "POST"]
    record = json.loads(out)
    assert record["baseline"]["body"] == json.dumps({"a": 1})
    assert '+  "a": 2' in record["body_diff"]


def test_cli_custom_post_without_baseline_still_sends(cli_env, tmp_path):
    cli_env.http.answers = [{"body": {}}]
    assert main(["raw", "POST", TASK_LIST, "--allow-writes",
                 "--evidence-dir", str(tmp_path / "ev")]) == 0
    assert [c[0] for c in cli_env.http.calls] == ["POST"]


def test_cli_custom_delete_baseline_out_refused(cli_env, capsys, tmp_path):
    assert main(["raw", "DELETE", TASK_LIST, "--baseline-out", str(tmp_path / "b.json")]) == 2
    assert cli_env.http.calls == [] and "baseline" in capsys.readouterr().err


# --- 5. bodies on GET and DELETE ------------------------------------------------------

def test_get_with_body_refused(lab_client, monkeypatch, tmp_path):
    session = _session(lab_client, monkeypatch, tmp_path)
    req = RawRequest(endpoint=get_endpoint("GET", "/almaws/v1/courses"), path_params={},
                     query={}, body='{"a": 1}')
    with pytest.raises(InputError) as exc:
        session.run_raw(req)
    assert exc.value.field == "body" and "GET takes no body" in exc.value.message
    assert lab_client.http.calls == []


def test_delete_with_undeclared_body_refused(lab_client, monkeypatch, tmp_path):
    session = _session(lab_client, monkeypatch, tmp_path, gate=lambda *a: True)
    req = RawRequest(endpoint=get_endpoint("DELETE", COURSE), path_params={"course_id": "<course_id>"},
                     query={}, body='{"a": 1}')
    with pytest.raises(InputError) as exc:
        session.run_raw(req)
    assert exc.value.field == "body"
    assert lab_client.http.calls == []


# --- 6. short path values are redacted ------------------------------------------------

def test_two_char_path_value_redacted(lab_client, monkeypatch, tmp_path):
    session = _session(lab_client, monkeypatch, tmp_path)
    lab_client.http.answers = [{"body": {"code": "AB"}}]
    rec = session.run_raw(RawRequest(endpoint=get_endpoint("GET", COURSE),
                                     path_params={"course_id": "AB"}, query={}))
    out, _ = redact(rec.to_dict())
    text = json.dumps(out)
    assert out["inputs"]["path"]["course_id"].startswith("<course_id_")
    assert "/courses/AB" not in text and '"AB"' not in text


# --- 7. baseline mismatch names the item ---------------------------------------------

def test_cli_baseline_format_mismatch_named(cli_env, capsys, tmp_path):
    ev = str(tmp_path / "ev")
    base = tmp_path / "current.json"
    cli_env.http.answers = [{"body": {"code": "X"}}]
    assert main(["raw", "PUT", COURSE_PATH, "--baseline-out", str(base), "--evidence-dir", ev]) == 0
    edited = tmp_path / "edited.xml"
    edited.write_text("<course><code>X</code></course>", encoding="utf-8")
    cli_env.http.calls.clear()
    capsys.readouterr()
    code = main(["raw", "PUT", COURSE_PATH, "--format", "xml", "--body-file", str(edited),
                 "--baseline", str(base), "--allow-writes", "--evidence-dir", ev])
    err = capsys.readouterr().err
    assert code == 2 and cli_env.http.calls == []
    assert "format" in err and "xml" in err and "json" in err


# --- 9. a failed --baseline-out writes nothing ----------------------------------------

def test_cli_failed_baseline_out_writes_no_file(cli_env, capsys, tmp_path):
    cli_env.http.answers = [{"status": 404, "body": {"errorsExist": True}}]
    base = tmp_path / "b.json"
    code = main(["raw", "PUT", COURSE_PATH, "--baseline-out", str(base),
                 "--evidence-dir", str(tmp_path / "ev")])
    assert code == 1
    assert not base.exists() and not (tmp_path / "b.json.evidence").exists()
    assert "404" in capsys.readouterr().err
