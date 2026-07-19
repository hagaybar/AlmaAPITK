"""R10 regression test for issue #188 — DEFAULT_LEADER descriptive form.

Assessment (issue #188): the default "new textual monograph" leader was
structurally valid but shipped **Ldr/18 = u** (descriptive cataloging form
*unknown*). For current RDA cataloguing the expected value is **i** (ISBD
punctuation included). Decision recorded: change the default Ldr/18 u -> i.

These tests pin the decision: the shared default leader (and any record built
without an explicit leader) must carry Ldr/18 = 'i'. They fail against the
pre-fix default ('u') and pass after the change. The leader stays 24 chars with
Ldr/09 = 'a' (Unicode/UTF-8) unchanged.
"""

import xml.etree.ElementTree as ET

from almaapitk.domains.bibs import DEFAULT_LEADER, build_alma_bib_xml

_LDR_18_DESCRIPTIVE_FORM = 18
_LDR_09_CHARSET = 9


def test_default_leader_is_24_chars():
    assert len(DEFAULT_LEADER) == 24


def test_default_leader_ldr18_is_rda_isbd_i_not_unknown_u():
    # The whole point of #188: 'i' (ISBD), never the old 'u' (unknown).
    assert DEFAULT_LEADER[_LDR_18_DESCRIPTIVE_FORM] == "i"
    assert DEFAULT_LEADER[_LDR_18_DESCRIPTIVE_FORM] != "u"


def test_default_leader_still_unicode_ldr09_a():
    # UTF-8 marker must be intact (matches the UTF-8 XML the builder emits).
    assert DEFAULT_LEADER[_LDR_09_CHARSET] == "a"


def test_built_record_without_leader_uses_isbd_default():
    spec = {"fields": [{"tag": "245", "subfields": [["a", "X"]]}]}
    leader = ET.fromstring(build_alma_bib_xml(spec)).find("./record/leader").text
    assert leader == DEFAULT_LEADER
    assert leader[_LDR_18_DESCRIPTIVE_FORM] == "i"
