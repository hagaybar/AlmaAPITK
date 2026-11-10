"""Alma Lab evidence records (issue #230)."""
import json
import subprocess

import pytest

from almaapitk.lab.capture import CapturedRequest
from almaapitk.lab.evidence import (
    EvidenceError,
    EvidenceRecord,
    add_to_gitignore,
    gitignore_status,
    list_records,
    load_record,
    new_record,
    write_record,
)
from tests.unit.lab.conftest import TEST_KEY


def _record(op="BibliographicRecords.get_record"):
    rec = new_record(operation=op, inputs={"mms_id": "990000000000001"}, environment="SANDBOX",
                     base_url_host="api-eu.hosted.exlibrisgroup.com", source="headless", command="call bibs.get_record")
    rec.requests = [CapturedRequest(method="GET", url="https://h/almaws/v1/bibs/990000000000001",
                                    headers={"Authorization": "apikey ***"}, body=None, status=200,
                                    response_body='{"title": "t"}')]
    rec.result = {"title": "t"}
    return rec


def test_new_record_has_versions_and_time():
    rec = _record()
    assert rec.almaapitk_version and rec.python_version and rec.tool_version
    assert "T" in rec.created_at and ("+" in rec.created_at or "-" in rec.created_at[10:])


def test_round_trip(tmp_path):
    rec = _record()
    path = write_record(rec, tmp_path)
    loaded = load_record(path, tmp_path)
    assert loaded.to_dict() == rec.to_dict()
    assert load_record(rec.id, tmp_path).to_dict() == rec.to_dict()
    assert isinstance(loaded.requests[0], CapturedRequest)


def test_file_layout_and_collision_suffix(tmp_path):
    a, b = _record(), _record()
    b.created_at = a.created_at
    b.id = a.id
    pa, pb = write_record(a, tmp_path), write_record(b, tmp_path)
    assert pa.parent.name == a.created_at[:10]
    assert pa.name.endswith("-BibliographicRecords.get_record.json")
    assert pb.name.endswith("-BibliographicRecords.get_record-2.json")
    assert a.id != b.id
    assert list_records(tmp_path)[0] == pb


def test_no_key_in_written_file(tmp_path):
    path = write_record(_record(), tmp_path)
    assert TEST_KEY not in path.read_text()
    json.loads(path.read_text())


def test_write_record_unwritable_dir_raises_evidence_error(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(EvidenceError, match="file"):
        write_record(_record(), blocker / "evidence")


def test_gitignore_status_in_temp_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    ev = tmp_path / "alma-lab-evidence"
    assert gitignore_status(ev) == "not-ignored"
    add_to_gitignore(ev)
    assert gitignore_status(ev) == "ignored"
    assert gitignore_status(tmp_path.parent / "elsewhere-no-repo" / "ev") in ("no-repo", "not-ignored", "ignored")


def test_list_records_skips_redacted_exports(tmp_path):
    path = write_record(_record(), tmp_path)
    (path.parent / (path.stem + ".redacted.json")).write_text("{}")
    assert list_records(tmp_path) == [path]
