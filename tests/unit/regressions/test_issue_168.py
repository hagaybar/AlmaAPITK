"""R10 regression tests for issue #168 — email PII leaks via f-string log messages.

``Users.update_user_email`` and ``Users.bulk_update_emails`` interpolated the
email address (and raw user_id) straight into the log **message** via f-strings.
The redactor (``alma_logging`` formatters) only scrubs structured ``extra=``
kwargs and the ``users/<id>`` URL form in the message text, so a bare email in
prose bypasses redaction and reaches the default-on console handler and the JSON
file handler verbatim. Email is named PII under R9. Same bug class as #154.

These tests drive the real methods and assert the email never appears in any
emitted log record's message string. The email is allowed to ride along as a
structured kwarg (where the redactor blanks it); it must not be in the message.
"""
import logging
import unittest
from unittest.mock import MagicMock

from almaapitk.domains.users import Users


# Synthetic, RFC-2606 example domain — never a real address (R9).
SENTINEL_EMAIL = "f168sentinel@example.com"


class _RecordingHandler(logging.Handler):
    """Capture every emitted record for message-string inspection."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class _StubClient:
    """Minimal client so ``Users()`` constructs without real HTTP."""

    def get_environment(self):
        return "SANDBOX"


class TestEmailNotLeakedIntoLogMessage(unittest.TestCase):
    def _make_users(self):
        users = Users(_StubClient())
        handler = _RecordingHandler()
        handler.setLevel(logging.DEBUG)
        underlying = users.logger.logger  # AlmaLogger wraps stdlib logger
        underlying.addHandler(handler)
        underlying.setLevel(logging.DEBUG)
        self.addCleanup(lambda: underlying.removeHandler(handler))
        return users, handler

    @staticmethod
    def _user_response_with_email():
        resp = MagicMock()
        resp.json.return_value = {
            "contact_info": {
                "email": [{"email_address": "old@example.com", "preferred": True}]
            }
        }
        return resp

    @staticmethod
    def _leaking(handler):
        return [
            r.getMessage() for r in handler.records if SENTINEL_EMAIL in r.getMessage()
        ]

    def test_update_user_email_does_not_leak_email(self):
        users, handler = self._make_users()
        users.get_user = MagicMock(return_value=self._user_response_with_email())
        users.update_user = MagicMock(return_value=MagicMock())

        users.update_user_email("tau000000", SENTINEL_EMAIL)

        self.assertEqual(self._leaking(handler), [])

    def test_bulk_update_emails_dry_run_does_not_leak_email(self):
        users, handler = self._make_users()
        users.get_user = MagicMock(return_value=MagicMock())

        users.bulk_update_emails(
            [{"user_id": "tau000000", "new_email": SENTINEL_EMAIL}], dry_run=True
        )

        self.assertEqual(self._leaking(handler), [])

    def test_bulk_update_emails_live_does_not_leak_email(self):
        users, handler = self._make_users()
        users.get_user = MagicMock(return_value=self._user_response_with_email())
        users.update_user = MagicMock(return_value=MagicMock())

        users.bulk_update_emails(
            [{"user_id": "tau000000", "new_email": SENTINEL_EMAIL}], dry_run=False
        )

        self.assertEqual(self._leaking(handler), [])

    def test_invalid_email_error_path_does_not_leak_value(self):
        """A validation failure must not echo the supplied address into the
        error log (the exception message feeds an f-string logger call)."""
        users, handler = self._make_users()
        users.get_user = MagicMock(return_value=MagicMock())
        bad_email = "f168sentinel_no_at_sign.example.com"  # invalid: no '@'

        users.bulk_update_emails(
            [{"user_id": "tau000000", "new_email": bad_email}], dry_run=True
        )

        leaking = [r.getMessage() for r in handler.records if bad_email in r.getMessage()]
        self.assertEqual(leaking, [])


class TestUserIdNotInLogMessage(unittest.TestCase):
    """The lower-severity #168 follow-up: user_id must ride as a structured
    kwarg (partial-redacted by the redactor), never interpolated whole into the
    log message string."""

    SENTINEL_ID = "tau_f168_sentinel_user_id"

    def _users(self):
        client = MagicMock()
        client.get_environment.return_value = "SANDBOX"
        users = Users(client)
        handler = _RecordingHandler()
        handler.setLevel(logging.DEBUG)
        underlying = users.logger.logger
        underlying.addHandler(handler)
        underlying.setLevel(logging.DEBUG)
        self.addCleanup(lambda: underlying.removeHandler(handler))
        return users, client, handler

    def test_get_user_does_not_put_full_user_id_in_message(self):
        users, client, handler = self._users()
        client.get.return_value = MagicMock()

        users.get_user(self.SENTINEL_ID)

        leaking = [
            r.getMessage() for r in handler.records if self.SENTINEL_ID in r.getMessage()
        ]
        self.assertEqual(leaking, [])


if __name__ == "__main__":
    unittest.main()
