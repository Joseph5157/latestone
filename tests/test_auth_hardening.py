"""Placeholder auth must fail closed, and unsafe settings must be opt-in.

Covers the security items the second-pass audit parked as "intentional demo
limitations". This is the primary development application heading for a
government client's environment, so an unconfigured deployment must be the safe
one — nothing risky may be the default.

The two architectural items (browser-held auth state, data callbacks not
enforcing a session) are *not* fixed here; they depend on the client's
authentication mechanism. They are recorded under "Security posture" in
docs/CODE_AUDIT.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from config import settings
from services import auth_service


@dataclass(frozen=True)
class _Creds:
    username: str
    password: str

    @property
    def is_configured(self) -> bool:
        return bool(self.username) and bool(self.password)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(auth_service, "demo_auth", _Creds("operator", "s3cret"))


class TestFailsClosedWhenUnconfigured:
    @pytest.mark.parametrize(
        "creds",
        [_Creds("", ""), _Creds("operator", ""), _Creds("", "s3cret")],
    )
    def test_no_login_succeeds_without_configuration(self, monkeypatch, creds):
        """The regression: a hard-coded fallback password used to make this work."""
        monkeypatch.setattr(auth_service, "demo_auth", creds)
        assert auth_service.verify_credentials("operator", "s3cret") is False
        assert auth_service.verify_credentials("admin", "demo1234") is False

    def test_the_old_published_default_is_not_accepted(self, monkeypatch):
        monkeypatch.setattr(auth_service, "demo_auth", _Creds("", ""))
        assert auth_service.verify_credentials("admin", "demo1234") is False

    def test_refusal_is_logged_so_it_is_diagnosable(self, monkeypatch, caplog):
        import logging

        monkeypatch.setattr(auth_service, "demo_auth", _Creds("", ""))
        with caplog.at_level(logging.ERROR):
            auth_service.verify_credentials("operator", "s3cret")
        assert "not configured" in caplog.text


class TestCredentialChecking:
    def test_correct_pair_is_accepted(self, configured):
        assert auth_service.verify_credentials("operator", "s3cret") is True

    def test_wrong_password_is_rejected(self, configured):
        assert auth_service.verify_credentials("operator", "wrong") is False

    def test_wrong_username_is_rejected(self, configured):
        assert auth_service.verify_credentials("someone", "s3cret") is False

    @pytest.mark.parametrize(
        "user,pwd", [("", "s3cret"), ("operator", ""), ("", ""), (None, None)]
    )
    def test_blank_input_is_rejected(self, configured, user, pwd):
        assert auth_service.verify_credentials(user, pwd) is False

    def test_a_matching_prefix_is_not_enough(self, configured):
        assert auth_service.verify_credentials("operator", "s3cre") is False


class TestUnsafeSettingsAreOptIn:
    def test_debug_is_off_by_default(self):
        """Debug mode exposes the interactive debugger; never a default."""
        assert settings.DEFAULT_DASH_DEBUG is False

    def test_host_binds_loopback_by_default(self):
        """0.0.0.0 publishes the app on every interface; must be asked for."""
        assert settings.DEFAULT_DASH_HOST == "127.0.0.1"

    def test_no_fallback_credentials_exist_in_code(self):
        """`.env.example` values must not also work as code defaults."""
        source = (settings.__file__ or "")
        assert source
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
        assert 'os.getenv("DEMO_PASSWORD", "")' in text
        assert '"demo1234"' not in text
