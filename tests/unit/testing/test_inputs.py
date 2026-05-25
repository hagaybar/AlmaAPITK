import json

import pytest

from almaapitk.testing.inputs import MissingTestInput, smoke_input


def test_reads_value(tmp_path, monkeypatch):
    f = tmp_path / "smoke-data.json"
    f.write_text(json.dumps({"analytics_report_path": "/shared/Placeholder/Reports/Demo"}))
    monkeypatch.setenv("ALMA_SMOKE_DATA", str(f))
    assert smoke_input("analytics_report_path") == "/shared/Placeholder/Reports/Demo"


def test_missing_key_raises_clear_error(tmp_path, monkeypatch):
    f = tmp_path / "smoke-data.json"
    f.write_text("{}")
    monkeypatch.setenv("ALMA_SMOKE_DATA", str(f))
    with pytest.raises(MissingTestInput) as exc_info:
        smoke_input("nope")
    assert "nope" in str(exc_info.value)


def test_missing_file_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("ALMA_SMOKE_DATA", str(tmp_path / "does-not-exist.json"))
    with pytest.raises(MissingTestInput) as exc_info:
        smoke_input("anything")
    assert "not found" in str(exc_info.value)
