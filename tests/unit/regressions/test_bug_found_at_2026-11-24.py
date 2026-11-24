"""Bug found 2026-11-24 (PR #257, round 3): the mask rewrote path templates.

``redact_text`` treated ``{user_id}`` in ``/almaws/v1/users/{user_id}`` as a
user ID and wrote ``users/<...>id}``. Alma Lab evidence records the endpoint
template, so a saved user GET no longer matched its PUT and every CLI update
of a user record was refused ("the baseline is not a GET of /users/{user_id}").
"""
from almaapitk.redaction import redact, redact_text


def test_path_template_is_not_masked():
    assert redact_text("/almaws/v1/users/{user_id}") == "/almaws/v1/users/{user_id}"
    assert redact_text("users/{user_id}/loans/{loan_id}") == "users/{user_id}/loans/{loan_id}"
    assert redact({"path": "/almaws/v1/users/{user_id}"}) == {"path": "/almaws/v1/users/{user_id}"}


def test_real_user_id_in_a_path_is_still_masked():
    assert redact_text("almaws/v1/users/FAKEPID0000123?view=full") == \
        "almaws/v1/users/<...>123?view=full"
