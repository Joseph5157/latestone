"""ADR-033 (AUTHENTICATION-LOCAL-HARDENING-01), pure-logic half.

No database: the credential verdict, password/token primitives, production
configuration guards, session security metadata and the sign-in orchestration
are tested with the repository read patched, exactly as the existing
credential tests do. The database-backed lifecycle is in
`test_local_auth_db.py`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

from callbacks import auth as auth_callbacks
from callbacks import set_password as set_password_callbacks
from config import settings
from repositories import plant_monitoring_repository as repo
from routes import SET_PASSWORD_ROUTE, parse_pathname
from services import account_service, auth_service, credentials, login_service, login_security
from services.authorization import ROUTE_POLICY
from tests.auth_test_support import fake_user_row, no_trusted_session

GOOD = "correct horse battery staple"


# ---------------------------------------------------------------------------
# Password hashing and policy
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_is_scrypt_salted_and_never_the_plaintext(self):
        first, second = credentials.hash_password(GOOD), credentials.hash_password(GOOD)
        assert first.startswith("scrypt:")
        assert GOOD not in first
        assert first != second, "each hash carries its own random salt"

    def test_correct_password_verifies_and_wrong_does_not(self):
        stored = credentials.hash_password(GOOD)
        assert credentials.verify_password(stored, GOOD) is True
        assert credentials.verify_password(stored, GOOD + "x") is False

    def test_a_malformed_stored_value_fails_closed(self):
        assert credentials.verify_password("not-a-hash", GOOD) is False
        assert credentials.verify_password("", GOOD) is False

    def test_verification_uses_the_framework_helper_not_direct_comparison(self, monkeypatch):
        calls = []
        real = credentials.check_password_hash
        monkeypatch.setattr(
            credentials, "check_password_hash", lambda h, p: calls.append(1) or real(h, p)
        )
        assert credentials.verify_password(credentials.hash_password(GOOD), GOOD)
        assert calls == [1]


class TestPasswordPolicy:
    def test_twelve_characters_is_the_floor(self):
        assert credentials.password_policy_error("a" * 11) is not None
        assert credentials.password_policy_error("a" * 12) is None

    def test_passphrases_with_spaces_are_welcome_and_no_composition_rules(self):
        assert credentials.password_policy_error(GOOD) is None
        assert credentials.password_policy_error("alllowercaseletters") is None

    @pytest.mark.parametrize("bad", [None, "", "   ", " " * 20])
    def test_blank_is_refused(self, bad):
        assert credentials.password_policy_error(bad) is not None

    def test_absurdly_long_input_is_refused(self):
        assert credentials.password_policy_error("a" * 257) is not None

    def test_the_username_is_not_an_acceptable_password(self):
        assert credentials.password_policy_error("technician.person", username="Technician.Person") is not None


class TestTokensAndUsernames:
    def test_tokens_are_random_and_only_a_hash_is_derivable(self):
        a, b = credentials.new_token(), credentials.new_token()
        assert a != b and len(a) >= 40
        digest = credentials.hash_token(a)
        assert digest != a and len(digest) == 64
        assert digest == credentials.hash_token(a)

    def test_usernames_have_one_canonical_form(self):
        assert credentials.normalize_username("  Admin ") == "admin"
        assert credentials.throttle_key("ADMIN") == credentials.throttle_key(" admin")

    @pytest.mark.parametrize("bad", ["", "ab", "has space", "-lead", "x" * 51, "semi;colon"])
    def test_bad_usernames_are_refused(self, bad):
        assert credentials.username_error(bad) is not None

    @pytest.mark.parametrize("good", ["abc", "demo.tech01", "client-person-2", "a_b@c"])
    def test_good_usernames_pass(self, good):
        assert credentials.username_error(good) is None


# ---------------------------------------------------------------------------
# Production configuration guards
# ---------------------------------------------------------------------------


class TestProductionGuards:
    def test_demo_login_is_default_off(self):
        assert settings.resolve_demo_login_enabled("development", "") is False
        assert settings.resolve_demo_login_enabled("development", "no") is False

    def test_demo_login_can_be_enabled_outside_production_only(self):
        assert settings.resolve_demo_login_enabled("development", "true") is True
        with pytest.raises(RuntimeError, match="AUTH_DEMO_LOGIN_ENABLED"):
            settings.resolve_demo_login_enabled("production", "true")

    @pytest.mark.parametrize(
        "kwargs, named",
        [
            ({"demo_username": "admin"}, "DEMO_USERNAME"),
            ({"demo_password": "x"}, "DEMO_PASSWORD"),
            ({"demo_credentials": '{"a": "b"}'}, "DEMO_CREDENTIALS"),
        ],
    )
    def test_production_refuses_demo_credential_configuration_by_name(self, kwargs, named):
        base = {"demo_username": "", "demo_password": "", "demo_credentials": ""}
        base.update(kwargs)
        with pytest.raises(RuntimeError) as excinfo:
            settings.validate_production_auth_config("production", **base)
        assert named in str(excinfo.value)

    def test_the_refusal_never_contains_a_secret_value(self):
        with pytest.raises(RuntimeError) as excinfo:
            settings.validate_production_auth_config(
                "production", demo_username="admin", demo_password="hunter2-secret",
                demo_credentials="",
            )
        assert "hunter2-secret" not in str(excinfo.value)

    def test_clean_production_and_any_development_pass(self):
        settings.validate_production_auth_config(
            "production", demo_username="", demo_password="", demo_credentials=" "
        )
        settings.validate_production_auth_config(
            "development", demo_username="admin", demo_password="pw", demo_credentials="{}"
        )

    def test_demo_credentials_are_empty_unless_explicitly_enabled(self):
        off = settings.DemoAuthSettings(
            username="admin", password="pw", extra_credentials="", login_enabled=False
        )
        on = settings.DemoAuthSettings(
            username="admin", password="pw", extra_credentials="", login_enabled=True
        )
        assert off.credentials == {} and off.is_configured is False
        assert on.credentials == {"admin": "pw"}


@dataclass(frozen=True)
class _Creds:
    username: str
    password: str
    config_error = None

    @property
    def credentials(self) -> dict:
        return {self.username: self.password}

    @property
    def is_configured(self) -> bool:
        return True


class TestDemoSeparation:
    def test_production_never_consults_demo_credentials(self, monkeypatch):
        monkeypatch.setattr(auth_service, "demo_auth", _Creds("operator", "s3cret"))
        monkeypatch.setattr(auth_service._settings, "IS_PRODUCTION", True)
        assert auth_service.verify_credentials("operator", "s3cret") is False

    def test_production_never_provisions_the_demo_administrator(self, monkeypatch):
        from services import prototype_users

        created = []
        monkeypatch.setattr(prototype_users.repo, "create_or_update_user", lambda **k: created.append(k))
        monkeypatch.setattr(prototype_users.repo, "get_user_by_username", lambda u: None)
        monkeypatch.setattr(settings, "demo_auth", _Creds("operator", "s3cret"))
        monkeypatch.setattr(settings, "IS_PRODUCTION", True)
        prototype_users.seed_demo_user()
        assert created == []

    def test_a_correct_demo_password_in_production_yields_no_identity(self, monkeypatch):
        monkeypatch.setattr(auth_service, "demo_auth", _Creds("operator", "s3cret"))
        monkeypatch.setattr(auth_service._settings, "IS_PRODUCTION", True)
        monkeypatch.setattr(auth_service.repo, "get_user_by_username", lambda u: fake_user_row(5, "administrator", username="operator"))
        assert auth_service.authenticate("operator", "s3cret") is None

    def test_development_fixture_still_works_when_enabled(self, monkeypatch):
        monkeypatch.setattr(auth_service, "demo_auth", _Creds("operator", "s3cret"))
        monkeypatch.setattr(auth_service.repo, "get_user_by_username", lambda u: fake_user_row(5, "administrator", username="operator"))
        assert auth_service.authenticate("operator", "s3cret").user_id == 5

    def test_a_hashed_account_ignores_the_demo_password(self, monkeypatch):
        """Once an account has its own hash, only the hash is accepted."""
        monkeypatch.setattr(auth_service, "demo_auth", _Creds("operator", "s3cret"))
        row = _with_hash(fake_user_row(5, "administrator", username="operator"))
        monkeypatch.setattr(auth_service.repo, "get_user_by_username", lambda u: row)
        monkeypatch.setattr(auth_service.repo, "get_password_hash", lambda uid: credentials.hash_password(GOOD))
        assert auth_service.authenticate("operator", "s3cret") is None
        assert auth_service.authenticate("operator", GOOD).user_id == 5


def _with_hash(row: repo.UserRecord, **changes) -> repo.UserRecord:
    from dataclasses import replace

    return replace(row, has_password=True, **changes)


# ---------------------------------------------------------------------------
# The credential verdict against a hashed account
# ---------------------------------------------------------------------------


@pytest.fixture
def hashed_account(monkeypatch):
    """One account whose row/status the test may change; production-like (no demo)."""
    state = {"row": _with_hash(fake_user_row(7, "technician", username="tech.one"))}
    stored = credentials.hash_password(GOOD)
    monkeypatch.setattr(auth_service, "demo_auth", _NoDemo())
    monkeypatch.setattr(auth_service.repo, "get_user_by_username", lambda u: state["row"] if u == "tech.one" else None)
    monkeypatch.setattr(auth_service.repo, "get_password_hash", lambda uid: stored)
    return state


class _NoDemo:
    credentials: dict = {}
    config_error = None
    is_configured = False


class TestCredentialVerdict:
    def test_active_account_with_the_right_password_signs_in(self, hashed_account):
        result = auth_service.check_credentials("Tech.One", GOOD)
        assert result.reason == "ok" and result.user.user_id == 7 and result.user.role == "technician"

    def test_wrong_password_fails(self, hashed_account):
        assert auth_service.check_credentials("tech.one", "wrong-password-value").reason == "invalid"

    def test_pending_account_cannot_password_login_even_with_the_right_password(self, hashed_account):
        hashed_account["row"] = _with_hash(hashed_account["row"], status="pending_activation")
        result = auth_service.check_credentials("tech.one", GOOD)
        assert result.user is None and result.reason == "pending"

    def test_disabled_account_cannot_login(self, hashed_account):
        hashed_account["row"] = _with_hash(hashed_account["row"], status="disabled")
        result = auth_service.check_credentials("tech.one", GOOD)
        assert result.user is None and result.reason == "disabled"

    def test_an_active_account_with_no_credential_cannot_login_without_demo(self, hashed_account):
        from dataclasses import replace

        hashed_account["row"] = replace(hashed_account["row"], has_password=False)
        assert auth_service.check_credentials("tech.one", GOOD).user is None

    def test_unknown_name_and_blank_input_fail(self, hashed_account):
        assert auth_service.check_credentials("nobody", GOOD).reason == "unknown"
        assert auth_service.check_credentials("", GOOD).user is None
        assert auth_service.check_credentials("tech.one", "").user is None

    def test_a_role_outside_the_vocabulary_is_refused(self, hashed_account):
        hashed_account["row"] = _with_hash(hashed_account["row"], role="superuser")
        assert auth_service.check_credentials("tech.one", GOOD).user is None

    def test_the_hash_path_never_compares_passwords_directly(self, hashed_account, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("direct comparison on the hashed path")

        # Replace only auth_service's own `hmac` name: werkzeug's verifier
        # legitimately uses the real one internally.
        import types

        monkeypatch.setattr(auth_service, "hmac", types.SimpleNamespace(compare_digest=boom))
        assert auth_service.check_credentials("tech.one", GOOD).user is not None
        assert auth_service.check_credentials("tech.one", "x" * 13).user is None

    def test_every_refusal_costs_a_verification(self, hashed_account, monkeypatch):
        """Unknown, pending, disabled and wrong-password all spend hashing work,
        so response time does not say which one happened."""
        burned = []
        monkeypatch.setattr(credentials, "burn_verification_time", lambda p: burned.append(1))
        auth_service.check_credentials("nobody", GOOD)
        hashed_account["row"] = _with_hash(hashed_account["row"], status="pending_activation")
        auth_service.check_credentials("tech.one", GOOD)
        hashed_account["row"] = _with_hash(hashed_account["row"], status="disabled")
        auth_service.check_credentials("tech.one", GOOD)
        assert len(burned) == 3


class TestGenericLoginResponse:
    def test_every_refusal_shows_the_same_message(self, hashed_account):
        messages = set()
        messages.add(auth_callbacks.login_outputs("nobody", GOOD)[0])
        messages.add(auth_callbacks.login_outputs("tech.one", "wrong-password-value")[0])
        hashed_account["row"] = _with_hash(hashed_account["row"], status="pending_activation")
        messages.add(auth_callbacks.login_outputs("tech.one", GOOD)[0])
        hashed_account["row"] = _with_hash(hashed_account["row"], status="disabled")
        messages.add(auth_callbacks.login_outputs("tech.one", GOOD)[0])
        assert messages == {auth_callbacks.LOGIN_FAILED_MESSAGE}

    def test_success_returns_an_identity_and_no_error(self, hashed_account):
        error, payload = auth_callbacks.login_outputs("tech.one", GOOD)
        assert error == "" and payload["user_id"] == 7
        assert "password" not in " ".join(map(str, payload.keys())).lower()


# ---------------------------------------------------------------------------
# Sign-in orchestration (throttle -> verdict -> bookkeeping)
# ---------------------------------------------------------------------------


class TestLoginOrchestration:
    def test_a_locked_name_is_refused_without_being_checked(self, monkeypatch):
        monkeypatch.setattr(login_security, "locked_seconds", lambda u: 42)
        monkeypatch.setattr(
            auth_service, "check_credentials",
            lambda *a: pytest.fail("a throttled attempt must not verify a password"),
        )
        outcome = login_service.attempt_login("anyone", GOOD)
        assert outcome.throttled and outcome.user is None
        error, payload = auth_callbacks.login_outputs("anyone", GOOD)
        assert error == auth_callbacks.LOGIN_THROTTLED_MESSAGE
        assert "42" not in error and "attempt" in error.lower()

    def test_a_failure_is_recorded_with_its_reason_but_shown_generically(self, monkeypatch):
        seen = []
        monkeypatch.setattr(
            login_security, "register_failure",
            lambda username, user_id, reason: seen.append((username, user_id, reason)),
        )
        monkeypatch.setattr(
            auth_service, "check_credentials",
            lambda u, p: auth_service.CredentialCheck(None, "pending", 9),
        )
        assert login_service.attempt_login("someone", "pw").user is None
        assert seen == [("someone", 9, "pending")]

    def test_success_records_and_returns_the_identity(self, monkeypatch):
        recorded = []
        user = auth_service.AuthenticatedUser(3, "u", "U", "general")
        monkeypatch.setattr(auth_service, "check_credentials", lambda u, p: auth_service.CredentialCheck(user, "ok", 3))
        monkeypatch.setattr(login_security, "register_success", lambda name, uid: recorded.append((name, uid)))
        assert login_service.attempt_login("u", "pw").user == user
        assert recorded == [("u", 3)]

    def test_a_bookkeeping_fault_on_success_refuses_the_login(self, monkeypatch):
        user = auth_service.AuthenticatedUser(3, "u", "U", "general")
        monkeypatch.setattr(auth_service, "check_credentials", lambda u, p: auth_service.CredentialCheck(user, "ok", 3))

        def boom(*a):
            raise RuntimeError("audit down")

        monkeypatch.setattr(login_security, "register_success", boom)
        assert login_service.attempt_login("u", "pw").user is None

    def test_an_unreadable_throttle_fails_closed(self, monkeypatch):
        def boom(u):
            raise RuntimeError("db down")

        monkeypatch.setattr(login_security, "locked_seconds", boom)
        monkeypatch.setattr(auth_service, "check_credentials", lambda *a: pytest.fail("must not verify"))
        assert login_service.attempt_login("u", "pw").user is None


# ---------------------------------------------------------------------------
# Session security metadata
# ---------------------------------------------------------------------------


@pytest.fixture
def account_row(monkeypatch):
    state = {"row": fake_user_row(11, "general", username="gen.user")}
    monkeypatch.setattr(repo, "get_user_by_id", lambda uid: state["row"] if uid == 11 else None)
    return state


def _flask_session():
    import flask

    return flask.session


class TestSessionSecurity:
    def test_a_fresh_session_resolves_and_carries_security_metadata(self, account_row):
        import app as app_module

        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(11)
            sess = _flask_session()
            assert sess["uid"] == 11 and sess["sv"] == 1 and isinstance(sess["iat"], int)
            assert sess["sid"] and sess.permanent is True
            assert auth_service.current_identity().user_id == 11

    def test_each_login_rotates_the_session_payload(self, account_row):
        import app as app_module

        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(11)
            first = _flask_session()["sid"]
            auth_service.start_trusted_session(11)
            assert _flask_session()["sid"] != first

    def test_a_security_version_bump_kills_the_old_session(self, account_row):
        from dataclasses import replace
        import app as app_module

        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(11)
            assert auth_service.current_identity() is not None
            account_row["row"] = replace(account_row["row"], session_version=2)
            assert auth_service.current_identity() is None

    def test_a_non_active_account_kills_the_session(self, account_row):
        from dataclasses import replace
        import app as app_module

        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(11)
            account_row["row"] = replace(account_row["row"], status="disabled")
            assert auth_service.current_identity() is None

    def test_the_absolute_lifetime_ends_a_session(self, account_row, monkeypatch):
        import app as app_module

        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(11)
            later = time.time() + settings.auth_settings.session_absolute_hours * 3600 + 5
            monkeypatch.setattr(auth_service.time, "time", lambda: later)
            assert auth_service.current_identity() is None

    def test_a_cookie_without_security_metadata_is_refused(self, account_row):
        """A pre-ADR-033 cookie (uid only) must not be trusted forever."""
        import app as app_module

        with app_module.app.server.test_request_context():
            _flask_session()["uid"] = 11
            assert auth_service.current_identity() is None

    def test_logout_clears_the_session(self, account_row):
        import app as app_module

        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(11)
            auth_service.end_trusted_session()
            assert auth_service.current_identity() is None
            assert dict(_flask_session()) == {}

    def test_cookie_policy_and_lifetime_are_configured(self):
        import app as app_module

        config = app_module.app.server.config
        assert config["SESSION_COOKIE_HTTPONLY"] is True
        assert config["SESSION_COOKIE_SAMESITE"] == "Lax"
        assert config["PERMANENT_SESSION_LIFETIME"].total_seconds() == settings.auth_settings.session_absolute_hours * 3600
        # A refreshed cookie would let an in-flight request resurrect a
        # session that a logout had just cleared.
        assert config["SESSION_REFRESH_EACH_REQUEST"] is False


class TestLogoutAudit:
    def test_signing_out_audits_who_signed_out_before_clearing(self, account_row, monkeypatch):
        import app as app_module

        logged = []
        monkeypatch.setattr(login_security, "register_logout", lambda uid: logged.append(uid))
        app = _Capturing()
        auth_callbacks.register(app)
        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(11)
            app.functions["_path_command"]("/logout")
            assert logged == [11]
            assert auth_service.current_identity() is None

    def test_signing_out_with_no_session_still_completes(self, monkeypatch):
        logged = []
        monkeypatch.setattr(login_security, "register_logout", lambda uid: logged.append(uid))
        app = _Capturing()
        auth_callbacks.register(app)
        with no_trusted_session():
            app.functions["_path_command"]("/logout")
        assert logged == []


class _Capturing:
    def __init__(self):
        self.functions = {}

    def callback(self, *a, **k):
        def deco(fn):
            self.functions[fn.__name__] = fn
            return fn

        return deco


# ---------------------------------------------------------------------------
# Routing and the public set-password page
# ---------------------------------------------------------------------------


class TestSetPasswordRoute:
    def test_the_path_parses_to_a_public_route_outside_the_policy_table(self):
        assert parse_pathname("/set-password").name == SET_PASSWORD_ROUTE
        assert SET_PASSWORD_ROUTE not in ROUTE_POLICY

    def test_token_is_read_only_when_exactly_one_is_present(self):
        assert set_password_callbacks.token_from_search("?token=abc") == "abc"
        assert set_password_callbacks.token_from_search("?token=a&token=b") is None
        assert set_password_callbacks.token_from_search("") is None
        assert set_password_callbacks.token_from_search(None) is None

    def test_mismatched_passwords_never_reach_the_service(self, monkeypatch):
        monkeypatch.setattr(
            account_service, "complete_password_setup",
            lambda *a: pytest.fail("mismatch must not consume the link"),
        )
        _body, message = set_password_callbacks.submit_outputs("?token=t", GOOD, GOOD + "x")
        assert message == set_password_callbacks.MISMATCH

    def test_outcomes_map_to_success_invalid_and_retry(self, monkeypatch):
        outcomes = iter([
            account_service.SetupOutcome(True),
            account_service.SetupOutcome(False, account_service.INVALID_LINK_MESSAGE),
            account_service.SetupOutcome(False, "Password must be at least 12 characters."),
        ])
        monkeypatch.setattr(account_service, "complete_password_setup", lambda t, p: next(outcomes))
        body, message = set_password_callbacks.submit_outputs("?token=t", GOOD, GOOD)
        assert "Password set" in str(body) and message == ""
        body, message = set_password_callbacks.submit_outputs("?token=t", GOOD, GOOD)
        assert "Link not valid" in str(body)
        body, message = set_password_callbacks.submit_outputs("?token=t", "short", "short")
        assert message == "Password must be at least 12 characters."

    def test_the_page_never_renders_a_password_or_token(self):
        from pages import set_password as page

        text = str(page.layout(True)) + str(page.layout(False))
        assert "token" not in text.lower()


# ---------------------------------------------------------------------------
# Structural guards
# ---------------------------------------------------------------------------


class TestNoDirectPasswordComparisonOutsideTheDemoFixture:
    def test_only_the_demo_fixture_compares_passwords_directly(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        offenders = []
        for folder in ("services", "callbacks", "pages", "components", "repositories"):
            for path in (root / folder).rglob("*.py"):
                if "compare_digest" in path.read_text(encoding="utf-8"):
                    offenders.append(path.relative_to(root).as_posix())
        assert offenders == ["services/auth_service.py"], offenders
