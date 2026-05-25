"""R10 regression tests for issue #143 — api_key constructor injection.

``AlmaAPIClient`` historically read the API key *only* from environment
variables (``ALMA_SB_API_KEY`` / ``ALMA_PROD_API_KEY``) inside the
constructor, raising a bare ``ValueError`` when unset. #143 adds the
OpenAI/Anthropic SDK pattern:

- an explicit ``api_key=`` constructor argument takes precedence,
- the environment variable remains a fallback (existing callers unchanged),
- a clear ``CredentialError`` is raised when neither is available, and it
  stays a ``ValueError`` subclass so code that caught the old bare
  ``ValueError`` keeps working.

All key values here are synthetic (R9) — never a real tenant key.
"""
from __future__ import annotations

import pytest

from almaapitk import AlmaAPIClient, CredentialError

SANDBOX_ENV = "ALMA_SB_API_KEY"
PROD_ENV = "ALMA_PROD_API_KEY"


def test_explicit_api_key_used_without_env(monkeypatch):
    """An explicit api_key works even when the env var is unset."""
    monkeypatch.delenv(SANDBOX_ENV, raising=False)
    client = AlmaAPIClient("SANDBOX", api_key="explicit-sb-key")
    assert client.api_key == "explicit-sb-key"


def test_explicit_api_key_flows_into_auth_header(monkeypatch):
    """The injected key is the one actually used for auth."""
    monkeypatch.delenv(SANDBOX_ENV, raising=False)
    client = AlmaAPIClient("SANDBOX", api_key="explicit-sb-key")
    assert client.default_headers["Authorization"] == "apikey explicit-sb-key"


def test_env_var_fallback_when_no_arg(monkeypatch):
    """No api_key arg -> fall back to the env var (backwards compatible)."""
    monkeypatch.setenv(SANDBOX_ENV, "env-sb-key")
    client = AlmaAPIClient("SANDBOX")
    assert client.api_key == "env-sb-key"


def test_explicit_arg_overrides_env(monkeypatch):
    """When both are present the explicit arg wins."""
    monkeypatch.setenv(SANDBOX_ENV, "env-sb-key")
    client = AlmaAPIClient("SANDBOX", api_key="explicit-wins")
    assert client.api_key == "explicit-wins"


def test_production_env_var_fallback(monkeypatch):
    """Fallback resolves the correct env var per environment."""
    monkeypatch.setenv(PROD_ENV, "env-prod-key")
    client = AlmaAPIClient("PRODUCTION", api_key=None)
    assert client.api_key == "env-prod-key"


def test_two_clients_different_keys_one_process(monkeypatch):
    """Explicit injection lets two clients hold different keys at once —
    impossible with the env-var-only design."""
    monkeypatch.delenv(SANDBOX_ENV, raising=False)
    a = AlmaAPIClient("SANDBOX", api_key="key-a")
    b = AlmaAPIClient("SANDBOX", api_key="key-b")
    assert a.api_key == "key-a"
    assert b.api_key == "key-b"


def test_missing_both_raises_credential_error(monkeypatch):
    """Neither arg nor env var -> CredentialError, not a silent surprise."""
    monkeypatch.delenv(SANDBOX_ENV, raising=False)
    with pytest.raises(CredentialError):
        AlmaAPIClient("SANDBOX")


def test_credential_error_message_names_both_options(monkeypatch):
    """The error must tell the caller *both* ways to supply the key."""
    monkeypatch.delenv(SANDBOX_ENV, raising=False)
    with pytest.raises(CredentialError) as exc_info:
        AlmaAPIClient("SANDBOX")
    message = str(exc_info.value)
    assert "api_key" in message
    assert SANDBOX_ENV in message


def test_credential_error_is_value_error_backcompat(monkeypatch):
    """Existing callers caught the old bare ValueError; preserve that."""
    assert issubclass(CredentialError, ValueError)
    monkeypatch.delenv(SANDBOX_ENV, raising=False)
    with pytest.raises(ValueError):
        AlmaAPIClient("SANDBOX")
