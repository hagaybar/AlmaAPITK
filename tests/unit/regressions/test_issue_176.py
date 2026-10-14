"""R10 regression test for issue #176.

``Admin._extract_member_ids_from_members`` derived each id only by splitting
``link`` and silently skipped members without one; the canonical ``id`` field
was never read.
"""
import logging

from almaapitk.domains.admin import Admin


class _StubClient:
    def __init__(self):
        self.logger = logging.getLogger("test_issue_176")

    def get_environment(self):
        return "SANDBOX"


def test_members_without_link_are_extracted_by_id():
    admin = Admin(_StubClient())
    members = [
        {"id": "tau000001"},
        {"link": "https://api/almaws/v1/users/tau000002"},
        {"id": "tau000003", "link": "https://api/almaws/v1/users/tau000003"},
    ]

    result = admin._extract_member_ids_from_members(members, "USER")

    assert result == ["tau000001", "tau000002", "tau000003"]
