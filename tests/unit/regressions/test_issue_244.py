"""R10 regression test for issue #244.

Alma returns ``contact_info.email[].email_type`` as a **list** of
``{value, desc}`` objects (one email can carry several types). The old
``Users._extract_email_type`` expected a dict, so
``Users.extract_user_emails`` reported ``type`` as the stringified list
(``"[{'value': 'work', ...}]"``).

Fix (owner's choice, option 2): each extracted email is Alma's own entry,
unchanged, plus one compatibility key ``address`` (copy of
``email_address``), which ``Users.process_users_batch`` consumers read.
The reshaped ``type`` and the redundant ``original_entry`` are gone.
"""

from unittest.mock import MagicMock

from almaapitk.domains.users import Users

WORK = {"value": "work", "desc": "Work"}
PERSONAL = {"value": "personal", "desc": "Personal"}


def _users() -> Users:
    return Users(MagicMock())


def _user(*emails):
    return {"contact_info": {"email": list(emails)}}


def test_email_type_list_is_kept_as_alma_sends_it():
    entry = {
        "email_address": "name@example.org",
        "preferred": True,
        "segment_type": "Internal",
        "email_type": [WORK, PERSONAL],
    }
    [email] = _users().extract_user_emails(_user(entry))

    assert email["email_type"] == [WORK, PERSONAL]
    assert "type" not in email


def test_entry_is_alma_entry_plus_address_alias():
    entry = {
        "email_address": "name@example.org",
        "preferred": False,
        "description": "secondary",
        "email_type": [WORK],
    }
    [email] = _users().extract_user_emails(_user(entry))

    assert email == {**entry, "address": "name@example.org"}
    assert "original_entry" not in email


def test_caller_input_is_not_mutated():
    entry = {"email_address": "name@example.org", "email_type": [WORK]}
    user = _user(entry)
    _users().extract_user_emails(user)

    assert user["contact_info"]["email"][0] == {
        "email_address": "name@example.org",
        "email_type": [WORK],
    }


def test_single_email_as_dict_still_normalised_to_list():
    entry = {"email_address": "name@example.org", "preferred": True, "email_type": [WORK]}
    emails = _users().extract_user_emails({"contact_info": {"email": entry}})

    assert emails == [{**entry, "address": "name@example.org"}]


def test_entries_without_address_are_skipped():
    emails = _users().extract_user_emails(
        _user({"email_address": "  ", "email_type": [WORK]}, {"email_type": [WORK]})
    )
    assert emails == []
