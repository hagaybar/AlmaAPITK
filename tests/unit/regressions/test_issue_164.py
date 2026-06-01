"""Regression test for issue #164.

Alma serialises ``number_of_members.value`` as a **string** (per the committed
``rest_set.json`` swagger: ``{"type": "string", "example": "100"}``).
``Admin.get_set_members`` and ``Admin.get_set_metadata_and_member_count`` fed
that string straight into ``range()`` and integer arithmetic, raising
``TypeError`` on every real non-empty set; the empty-set guard ``"0" == 0`` also
silently failed. These tests feed the schema-correct string value and assert the
methods operate on it as an integer.
"""
import logging

from almaapitk.domains.admin import Admin


class _StubClient:
    """Minimal client so ``Admin()`` constructs without real HTTP."""

    def __init__(self):
        self.logger = logging.getLogger("test_issue_164")

    def get_environment(self):
        return "SANDBOX"


def _set_info(member_count_value, content="USER"):
    """A set-info payload shaped like a real Alma response (string count)."""
    return {
        "id": "12345",
        "name": "Test Set",
        "description": "",
        "content": {"value": content},
        "status": {"value": "ACTIVE"},
        # Schema-correct: the value is a STRING, not an int.
        "number_of_members": {"value": member_count_value},
        "created_date": "2026-01-01",
        "created_by": "system",
    }


def _make_admin(set_info, member_pages=None):
    admin = Admin(_StubClient())
    admin._get_set_info = lambda set_id: set_info
    if member_pages is not None:
        admin._get_set_members_page = (
            lambda set_id, offset, limit=100: member_pages[offset]
        )
    return admin


def test_get_set_members_paginates_with_string_count():
    """A non-empty set whose count is the string "5" must paginate, not crash."""
    members = [
        {"link": f"https://api/almaws/v1/users/tau00000{i}"} for i in range(1, 6)
    ]
    admin = _make_admin(_set_info("5"), member_pages={0: {"member": members}})

    result = admin.get_set_members("12345")

    assert result == [f"tau00000{i}" for i in range(1, 6)]


def test_get_set_members_empty_set_string_zero():
    """The empty-set guard must treat the string "0" as zero and return []."""
    admin = _make_admin(_set_info("0"))

    assert admin.get_set_members("12345") == []


def test_get_set_metadata_arithmetic_with_string_count():
    """Metadata math (pages, processing time) must run on the string count."""
    admin = _make_admin(_set_info("150"))

    metadata = admin.get_set_metadata_and_member_count("12345")
    member_info = metadata["member_info"]

    assert member_info["total_members"] == 150
    assert member_info["pages_required"] == 2  # ceil(150 / 100)
    assert isinstance(member_info["estimated_processing_time_minutes"], int)
    assert member_info["estimated_processing_time_minutes"] >= 1


def test_validate_user_set_returns_int_member_count():
    """validate_user_set must return total_members as an int, not a string."""
    admin = _make_admin(_set_info("42", content="USER"))

    result = admin.validate_user_set("12345")

    assert result["total_members"] == 42
    assert isinstance(result["total_members"], int)
