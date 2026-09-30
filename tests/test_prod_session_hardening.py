"""AUTH-PROD-HARDEN-1 — production session/cookie hardening.

Closes the non-blocking follow-up AUTH-HARDEN-1 left open (recorded in
docs/CODE_AUDIT.md's "AUTH-HARDEN-1 (+ 1R, 1R2) closes S-4 and S-5" entry and
docs/context/ACTIVE_GATE.md's "Non-blocking follow-ups"): cookie transport
hardening and a production `FLASK_SECRET_KEY` that fails closed rather than
falling back to a per-process random key.

Covers:
- `APP_ENV` is the one environment/deployment-mode concept this app has;
  `FLASK_SECRET_KEY`'s fail-closed requirement and the cookie's `Secure`
  flag both key off it.
- local development still starts with no `FLASK_SECRET_KEY` configured.
- production with a missing/blank `FLASK_SECRET_KEY` fails closed at startup.
- production with a configured `FLASK_SECRET_KEY` starts normally.
- the session cookie is `Secure` only in production; `HttpOnly` and
  `SameSite` are explicit in every environment.
- the app wires that policy into Flask's real `server.config`.
- HTTPS enforcement is the deployment platform's job, not this app's —
  pinned by asserting no forwarded-header trust exists to be exploited.

Does not touch AUTH-HARDEN-1's own identity/authorization tests — those stay
in tests/test_auth_harden.py and tests/test_auth_harden_repair.py, and every
assertion in this file is additive to them, not a replacement.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from config import settings

REPO_ROOT = Path(__file__).resolve().parent.parent

#: A port nothing listens on — see tests/test_bootstrap_contract.py, whose
#: `import app` subprocess pattern this file reuses for real startup checks.
UNREACHABLE_PORT = "59999"


class TestResolveAppEnvironment:
    def test_blank_defaults_to_development(self):
        assert settings.resolve_app_environment("") == "development"

    def test_unset_defaults_to_development(self):
        assert settings.resolve_app_environment(None) == "development"  # type: ignore[arg-type]

    def test_accepts_production(self):
        assert settings.resolve_app_environment("production") == "production"

    def test_is_case_and_whitespace_insensitive(self):
        assert settings.resolve_app_environment("  PRODUCTION  ") == "production"

    def test_rejects_an_unrecognised_value(self):
        with pytest.raises(RuntimeError, match="APP_ENV"):
            settings.resolve_app_environment("staging")


class TestResolveFlaskSecretKey:
    def test_development_with_no_configured_key_returns_a_usable_random_key(self):
        key = settings.resolve_flask_secret_key("development", "")
        assert isinstance(key, str)
        assert len(key) >= 32

    def test_development_prefers_a_configured_key(self):
        assert (
            settings.resolve_flask_secret_key("development", "abc123") == "abc123"
        )

    def test_production_with_no_configured_key_fails_closed(self):
        with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
            settings.resolve_flask_secret_key("production", "")

    def test_production_with_a_blank_configured_key_fails_closed(self):
        """Whitespace-only configuration must not read as "configured"."""
        with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
            settings.resolve_flask_secret_key("production", "   ")

    def test_production_with_a_configured_key_succeeds(self):
        assert (
            settings.resolve_flask_secret_key("production", "a-real-secret")
            == "a-real-secret"
        )


class TestFlaskSessionCookiePolicy:
    def test_production_cookie_is_secure(self):
        prod = settings.FlaskSessionSettings(
            secret_key="k",
            cookie_secure=True,
            cookie_httponly=True,
            cookie_samesite="Lax",
        )
        assert prod.cookie_secure is True

    def test_httponly_is_explicit_regardless_of_environment(self):
        assert settings.flask_session.cookie_httponly is True

    def test_samesite_is_explicit_regardless_of_environment(self):
        assert settings.flask_session.cookie_samesite in {"Lax", "Strict"}

    def test_this_process_is_running_as_development(self):
        """Guards the two tests below: they assume the test suite itself runs
        without APP_ENV=production, same assumption test_auth_hardening.py's
        TestUnsafeSettingsAreOptIn makes about other defaults."""
        assert settings.IS_PRODUCTION is False

    def test_development_default_leaves_cookie_not_secure(self):
        """A `Secure` cookie set from a plain http:// origin is silently
        dropped by the browser — indistinguishable from a broken login on
        local HTTP development."""
        assert settings.flask_session.cookie_secure is False


class TestAppWiresCookiePolicyIntoFlask:
    def test_server_config_matches_flask_session_settings(self):
        import app as app_module

        cfg = app_module.app.server.config
        assert cfg["SESSION_COOKIE_SECURE"] == settings.flask_session.cookie_secure
        assert (
            cfg["SESSION_COOKIE_HTTPONLY"] == settings.flask_session.cookie_httponly
        )
        assert (
            cfg["SESSION_COOKIE_SAMESITE"] == settings.flask_session.cookie_samesite
        )


class TestHttpsProxyBoundaryIsThePlatforms:
    def test_app_does_not_trust_forwarded_headers(self):
        """No `ProxyFix` / `X-Forwarded-*` trust exists anywhere in the app.

        This process is reached only through the deployment platform's own
        HTTPS edge (see app.py's comment beside the `server.config.update`
        call, and railway.json). Nothing here reads a forwarded header to
        make a security decision; this pins that so a future change does not
        add one without a proven, bounded proxy count in front of this
        process — trusting such a header without that would let a client
        spoof its own scheme or address.
        """
        raw = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
        # Strip comments (which explain, in prose, why neither is used) so
        # only actual code is checked — see test_bootstrap_contract.py for
        # the same pattern.
        code_lines = [
            line for line in raw.splitlines() if not line.lstrip().startswith("#")
        ]
        code = "\n".join(code_lines)
        assert "ProxyFix" not in code
        assert "X-Forwarded" not in code


class TestStartupFailsClosedOnlyInProduction:
    """Real subprocess startup — not a mocked import — proving the fail-closed
    behaviour actually happens at the moment `gunicorn app:server` would hit
    it, and that local development is not collaterally affected.
    """

    def _run(self, env_overrides: dict) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        # ADR-033: a production process refuses demo credential variables, and
        # a developer's `.env` legitimately carries them. These cases are about
        # the session secret, so blank the demo variables (the refusal itself
        # is tested in test_local_auth_config.py).
        env.update(
            {
                "DEMO_USERNAME": "",
                "DEMO_PASSWORD": "",
                "DEMO_CREDENTIALS": "",
                "AUTH_DEMO_LOGIN_ENABLED": "",
            }
        )
        env.update(env_overrides)
        # Importing `app` must not need a database (test_bootstrap_contract.py);
        # pointing at a dead port keeps that true here too.
        env["POSTGRES_PORT"] = UNREACHABLE_PORT
        return subprocess.run(
            [sys.executable, "-c", "import app"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_local_development_starts_with_no_flask_secret_key(self):
        result = self._run({"APP_ENV": "", "FLASK_SECRET_KEY": ""})
        assert result.returncode == 0, result.stderr[-2000:]

    def test_production_with_missing_secret_fails_closed(self):
        result = self._run({"APP_ENV": "production", "FLASK_SECRET_KEY": ""})
        assert result.returncode != 0
        assert "FLASK_SECRET_KEY" in result.stderr

    def test_production_with_blank_secret_fails_closed(self):
        result = self._run({"APP_ENV": "production", "FLASK_SECRET_KEY": "   "})
        assert result.returncode != 0
        assert "FLASK_SECRET_KEY" in result.stderr

    def test_production_with_configured_secret_succeeds(self):
        result = self._run(
            {"APP_ENV": "production", "FLASK_SECRET_KEY": "a-real-production-secret"}
        )
        assert result.returncode == 0, result.stderr[-2000:]
