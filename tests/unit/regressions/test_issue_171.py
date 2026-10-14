"""R10 regression test for issue #171.

``ResourceSharing.get_request_summary`` read ``owner`` as a nested ``{value}``
object, but Alma returns it as a plain string (library code), so the summary
always reported ``'N/A'``.
"""
from almaapitk.domains.resource_sharing import ResourceSharing


class _StubClient:
    def get_environment(self):
        return "SANDBOX"


def test_get_request_summary_reads_plain_string_owner():
    rs = ResourceSharing(_StubClient())

    summary = rs.get_request_summary({"request_id": "1", "owner": "LIB_A"})

    assert summary["owner"] == "LIB_A"
