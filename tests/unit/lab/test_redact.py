"""Alma Lab redacted export (issue #230)."""
import json

from almaapitk.lab.redact import redact

MMS = "990000000000001"
MARC = f'<bib><record><controlfield tag="001">{MMS}</controlfield><datafield tag="505"><subfield code="a">Part one</subfield></datafield></record></bib>'


def _record():
    return {
        "operation": "BibliographicRecords.get_record",
        "inputs": {"mms_id": MMS, "view": "full"},
        "command": f"call bibs.get_record --mms-id {MMS}",
        "requests": [{
            "method": "GET", "url": f"https://h/almaws/v1/bibs/{MMS}?view=full", "body": None,
            "status": 200, "headers": {"Authorization": "apikey ***"},
            "response_body": json.dumps({"mms_id": MMS, "anies": [MARC], "total_record_count": 3,
                                         "user": {"primary_id": "tau123456", "first_name": "Dana",
                                                  "contact_info": {"email": [{"email_address": "dana@example.org"}]}}}),
        }],
        "result": {"mms_id": MMS, "anies": [MARC], "total_record_count": 3, "status": {"value": "ACTIVE"},
                   "note": "contact dana@example.org or the desk"},
        "expectations": [{"text": "status == 200", "outcome": "passed", "actual": 200}],
    }


def test_input_id_replaced_everywhere():
    out, reps = redact(_record())
    text = json.dumps(out)
    assert MMS not in text
    assert "<mms_id_1>" in out["requests"][0]["url"]
    assert out["inputs"]["mms_id"] == "<mms_id_1>"
    assert "<mms_id_1>" in out["command"]
    assert any(r["placeholder"] == "<mms_id_1>" for r in reps)


def test_status_and_counts_kept():
    out, _ = redact(_record())
    assert out["result"]["total_record_count"] == 3
    assert out["result"]["status"]["value"] == "ACTIVE"
    assert out["inputs"]["view"] == "full"
    assert out["requests"][0]["status"] == 200
    assert "Part one" in json.dumps(out)


def test_personal_data_in_response_replaced():
    out, _ = redact(_record())
    text = json.dumps(out)
    for secret in ("tau123456", "Dana", "dana@example.org"):
        assert secret not in text


def test_same_value_same_placeholder():
    out, reps = redact(_record())
    placeholders = {r["placeholder"] for r in reps}
    assert len([p for p in placeholders if p.startswith("<mms_id")]) == 1


def test_keep_value():
    out, reps = redact(_record(), keep=frozenset({MMS}))
    assert out["inputs"]["mms_id"] == MMS
    kept = [r for r in reps if r["value_kept"]]
    assert len(kept) == 1 and kept[0]["kind"] == "mms_id" and kept[0]["placeholder"] is None


def test_email_pattern_in_free_text():
    out, _ = redact(_record())
    assert out["result"]["note"] == "contact <email_1> or the desk"


def test_find_sensitive_lists_values_with_kinds():
    from almaapitk.lab.redact import find_sensitive

    found = dict(find_sensitive(_record()))
    assert found[MMS] == "mms_id" and found["dana@example.org"] == "email"


def test_raw_inputs_redacted():
    code_value, q_value = "LOCAL_TABLE_X", "primary_id~sample_person"
    rec = {
        "operation": "raw GET /almaws/v1/conf/code-tables/{codeTableName}",
        "raw": True,
        "inputs": {"path": {"codeTableName": code_value},
                   "query": {"q": q_value, "limit": 250, "lang": "en"},
                   "format": "json", "body": None},
        "requests": [{
            "method": "GET",
            "url": f"https://h/almaws/v1/conf/code-tables/{code_value}?q=primary_id~sample_person&limit=250&lang=en",
            "body": None, "status": 200,
            "response_body": json.dumps({"name": code_value, "note": q_value}),
        }],
        "result": {"name": code_value, "note": q_value},
    }
    out, reps = redact(rec)
    text = json.dumps(out)
    assert code_value not in text and q_value not in text
    assert out["inputs"]["path"]["codeTableName"] == "<codeTableName_1>"
    assert out["inputs"]["query"]["q"] == "<q_1>"
    assert out["inputs"]["query"]["limit"] == 250
    assert "limit=250" in out["requests"][0]["url"]
    assert {r["kind"] for r in reps} >= {"codeTableName", "q"}
