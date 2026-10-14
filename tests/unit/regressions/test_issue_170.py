"""R10 regression test for issue #170.

``TSVGenerator._load_config`` had a half-built "direct TSV" mode: with
``use_direct_tsv`` / ``skip_tsv_generation`` set it stopped requiring
``alma_set_id``, but nothing downstream read those flags, so ``generate_tsv``
crashed later with ``KeyError: 'alma_set_id'``. No consumer used the mode, so
it was removed: ``alma_set_id`` is required unconditionally.
"""
import json

import pytest

from almaapitk.utils.tsv_generator import TSVGenerator


@pytest.mark.parametrize("flag", ["use_direct_tsv", "skip_tsv_generation"])
def test_config_without_set_id_fails_at_load(tmp_path, flag):
    tsv = tmp_path / "input.tsv"
    tsv.write_text("x\n", encoding="utf-8")
    config = {
        "input": {flag: True, "direct_tsv_path": str(tsv), "environment": "SANDBOX"},
        "columns": [{"name": "MMS_ID", "source": "alma_set"}],
        "output_settings": {"output_directory": str(tmp_path)},
    }
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="alma_set_id"):
        TSVGenerator(str(cfg))
