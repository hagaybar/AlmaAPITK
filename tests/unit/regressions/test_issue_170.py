"""R10 regression test for issue #170.

``TSVGenerator._load_config`` accepted ``use_direct_tsv`` /
``skip_tsv_generation`` configs that omit ``alma_set_id``, but no execution
path ever reads those flags: ``generate_tsv`` then crashed with
``KeyError: 'alma_set_id'``. The half-wired mode is now rejected up front with
a clear error instead of passing validation.
"""
import json

import pytest

from almaapitk.utils.tsv_generator import TSVGenerator


@pytest.mark.parametrize("flag", ["use_direct_tsv", "skip_tsv_generation"])
def test_direct_tsv_mode_is_rejected_at_load(tmp_path, flag):
    tsv = tmp_path / "input.tsv"
    tsv.write_text("x\n", encoding="utf-8")
    config = {
        "input": {flag: True, "direct_tsv_path": str(tsv), "environment": "SANDBOX"},
        "columns": [{"name": "MMS_ID", "source": "alma_set"}],
        "output_settings": {"output_directory": str(tmp_path)},
    }
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="not supported"):
        TSVGenerator(str(cfg))
