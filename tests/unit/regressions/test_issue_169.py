"""R10 regression test for issue #169.

``create_sample_config()`` is a module-level function but logged through
``self.logger``. With no ``self`` in scope it wrote the file, then raised
``NameError`` (re-wrapped as ``RuntimeError``), so the success path was
unreachable.
"""
import json

from almaapitk.utils.tsv_generator import create_sample_config


def test_create_sample_config_returns_path_without_raising(tmp_path):
    out = tmp_path / "sample.json"

    result = create_sample_config(str(out))

    assert result == str(out)
    assert "input" in json.loads(out.read_text(encoding="utf-8"))
