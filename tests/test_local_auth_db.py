"""ADR-033 (AUTHENTICATION-LOCAL-HARDENING-01), database-backed half.

Runs against the disposable `isolated_schema` (never the real schema, never the
client SQL Server — a fake person directory stands in for it). Covers the
account lifecycle, setup/reset tokens, throttling, audit content, the
Administrator bootstrap and preflight, and the five-Technician transition with
ADR-032 scope left untouched.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config import audit as audit_cfg
from config.settings import auth_settings
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import account_service as svc
from services import auth_preflight, auth_service, credentials, login_service, rtl_scope
from services.account_service import AccountError

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

GOOD = "correct horse battery staple"
OTHER = "another sufficiently long passphrase"
PERSONS = {1: "Administrator", 2: "Technician", 3: "Technician", 4: "Technician", 5: "Technician",
           6: "Technician", 7: "Administrator"}


def persons() -> dict[int, str]:
    return dict(PERSONS)


@pytest.fixture(autouse=True)
def clean():
    repo.delete_all_users()
    yield
    repo.delete_all_users()


def _sql(sql: str, **params):
    with session_scope() as s:
        result = s.execute(text(sql.replace("SCHEMA.", f"{repo._SCHEMA}.")), params)
        return result.all() if result.returns_rows else None


def _make_admin(username="root.admin", password=GOOD, email="root@example.org") -> int:
    with session_scope() as s:
        user = repo.insert_user_account(
            s, username=username, full_name="Root Admin", email_address=email,
            role="administrator", status="active", client_person_id=None,
        )
        repo.set_password_hash(s, user.user_id, credentials.hash_password(password), activate=False)
    return user.user_id


def _account(admin_id, username="tech.one", role="technician", person=2, **kw):
    return svc.create_account(
        actor_user_id=admin_id, username=username, full_name=kw.get("full_name", "Tech One"),
        email_address=None, role=role, client_person_id=person, person_roles=persons,
    )


def _activate(admin_id, user, password=GOOD):
    link = svc.issue_link(actor_user_id=admin_id, user_id=user.user_id)
    token = link.url.split("token=")[1]
    assert svc.complete_password_setup(token, password).ok
    return token


def _audit_ops():
    return [r[0] for r in _sql("SELECT operation FROM SCHEMA.audit_log ORDER BY audit_id")]


def _row(user_id):
    return repo.get_user_by_id(user_id)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_status_vocabulary_is_enforced(self):
        with pytest.raises(IntegrityError):
            _sql("INSERT INTO SCHEMA.users (username, full_name, role, status) "
                 "VALUES ('x1x', 'X', 'general', 'inactive')")

    def test_usernames_must_be_lower_case(self):
        with pytest.raises(IntegrityError):
            _sql("INSERT INTO SCHEMA.users (username, full_name, role, status) "
                 "VALUES ('MixedCase', 'X', 'general', 'active')")

    def test_repository_normalises_username_case(self):
        rec = repo.create_or_update_user("MixedCase", "X", "general", "active")
        assert rec.username == "mixedcase"
        assert repo.get_user_by_username("MIXEDCASE").user_id == rec.user_id

    def test_token_hash_is_unique_and_purpose_checked(self):
        admin = _make_admin()
        with session_scope() as s:
            repo.insert_auth_token(s, user_id=admin, purpose="setup", token_hash="h" * 64,
                                   ttl_seconds=60, created_by=None)
        with pytest.raises(IntegrityError), session_scope() as s:
            repo.insert_auth_token(s, user_id=admin, purpose="setup", token_hash="h" * 64,
                                   ttl_seconds=60, created_by=None)
        with pytest.raises(IntegrityError), session_scope() as s:
            repo.insert_auth_token(s, user_id=admin, purpose="other", token_hash="i" * 64,
                                   ttl_seconds=60, created_by=None)


# ---------------------------------------------------------------------------
# Create / link / authorization of the operations themselves
# ---------------------------------------------------------------------------


class TestCreateAndLink:
    def test_a_new_account_is_pending_with_no_credential(self):
        admin = _make_admin()
        user = _account(admin)
        assert user.status == "pending_activation" and user.has_password is False
        assert repo.get_password_hash(user.user_id) is None

    def test_only_an_active_administrator_may_manage_accounts(self):
        admin = _make_admin()
        tech = _account(admin)
        for actor in (tech.user_id, 999999, None, True):
            with pytest.raises(AccountError, match="Administrator"):
                svc.create_account(actor_user_id=actor, username="new.user", full_name="N",
                                   email_address=None, role="general")
        general = repo.create_or_update_user("gen.user", "G", "general", "active")
        with pytest.raises(AccountError):
            svc.disable_account(actor_user_id=general.user_id, user_id=admin)
        with pytest.raises(AccountError):
            svc.issue_link(actor_user_id=general.user_id, user_id=tech.user_id)
        with pytest.raises(AccountError):
            svc.list_accounts(actor_user_id=general.user_id)

    def test_a_disabled_administrator_can_no_longer_administer(self):
        admin, second = _make_admin(), _make_admin("second.admin")
        svc.disable_account(actor_user_id=admin, user_id=second)
        with pytest.raises(AccountError):
            svc.create_account(actor_user_id=second, username="n.user", full_name="N",
                               email_address=None, role="general")

    def test_duplicate_or_malformed_usernames_are_refused(self):
        admin = _make_admin()
        _account(admin)
        with pytest.raises(AccountError, match="already exists"):
            _account(admin, person=3)
        with pytest.raises(AccountError, match="already exists"):
            _account(admin, username="TECH.ONE", person=3)
        with pytest.raises(AccountError):
            _account(admin, username="no spaces", person=3)

    def test_the_same_client_person_cannot_link_two_accounts(self):
        admin = _make_admin()
        _account(admin, "tech.one", person=2)
        with pytest.raises(AccountError, match="already linked"):
            _account(admin, "tech.two", person=2)

    def test_a_technician_must_link_a_client_technician(self):
        admin = _make_admin()
        with pytest.raises(AccountError, match="does not match the Technician role"):
            _account(admin, "tech.bad", person=7)
        with pytest.raises(AccountError, match="No client person"):
            _account(admin, "tech.ghost", person=999)

    def test_an_administrator_must_link_a_client_administrator_and_general_cannot_link(self):
        admin = _make_admin()
        with pytest.raises(AccountError, match="does not match the Administrator role"):
            svc.create_account(actor_user_id=admin, username="adm.bad", full_name="A",
                               email_address=None, role="administrator", client_person_id=2,
                               person_roles=persons)
        with pytest.raises(AccountError, match="General User"):
            svc.create_account(actor_user_id=admin, username="gen.bad", full_name="G",
                               email_address=None, role="general", client_person_id=2,
                               person_roles=persons)
        ok = svc.create_account(actor_user_id=admin, username="adm.ok", full_name="A",
                                email_address=None, role="administrator", client_person_id=7,
                                person_roles=persons)
        assert ok.client_person_id == 7

    def test_an_unreachable_person_directory_fails_closed(self):
        admin = _make_admin()

        def down():
            raise RuntimeError("sql server down")

        with pytest.raises(AccountError, match="unavailable"):
            svc.create_account(actor_user_id=admin, username="tech.x", full_name="T",
                               email_address=None, role="technician", client_person_id=2,
                               person_roles=down)
        assert repo.get_user_by_username("tech.x") is None

    def test_link_change_and_role_change_are_audited_and_revoke_sessions(self):
        admin = _make_admin()
        user = _account(admin)
        before = _row(user.user_id).session_version
        svc.update_account(actor_user_id=admin, user_id=user.user_id, username="tech.one",
                           full_name="Tech One", email_address=None, role="technician",
                           client_person_id=3, person_roles=persons)
        assert _row(user.user_id).client_person_id == 3
        assert _row(user.user_id).session_version == before + 1
        svc.update_account(actor_user_id=admin, user_id=user.user_id, username="tech.one",
                           full_name="Tech One", email_address=None, role="general",
                           client_person_id=None, person_roles=persons)
        ops = _audit_ops()
        assert audit_cfg.CLIENT_PERSON_LINK_CHANGED in ops and audit_cfg.USER_ROLE_CHANGED in ops
        assert ops.count(audit_cfg.CLIENT_PERSON_LINK_CHANGED) == 3  # create, relink, unlink

    def test_rename_keeps_identity_and_revokes_open_links(self):
        admin = _make_admin()
        user = _account(admin, "client-person-2")
        link = svc.issue_link(actor_user_id=admin, user_id=user.user_id)
        svc.update_account(actor_user_id=admin, user_id=user.user_id, username="Senzo.M",
                           full_name="Senzo Mpungose", email_address=None, role="technician",
                           client_person_id=2, person_roles=persons)
        renamed = _row(user.user_id)
        assert renamed.username == "senzo.m" and renamed.client_person_id == 2
        assert svc.token_is_usable(link.url.split("token=")[1]) is False

    def test_role_guards(self):
        admin = _make_admin()
        with pytest.raises(AccountError, match="own role"):
            svc.update_account(actor_user_id=admin, user_id=admin, username="root.admin",
                               full_name="R", email_address=None, role="general",
                               client_person_id=None, person_roles=persons)
        other = _make_admin("other.admin")
        # not the last administrator, so a demotion of another is allowed
        svc.update_account(actor_user_id=admin, user_id=other, username="other.admin",
                           full_name="R", email_address=None, role="general",
                           client_person_id=None, person_roles=persons)
        assert _row(other).role == "general"

    def test_a_technician_with_assigned_rtls_cannot_change_role(self):
        admin = _make_admin()
        user = _account(admin)
        _sql("INSERT INTO SCHEMA.rtl_technician_assignments "
             "(device_uid, technician_user_id, provenance, imported_at) "
             "VALUES (29001, :u, 'LEGACY_IMPORT', now())", u=user.user_id)
        with pytest.raises(AccountError, match="assigned RTLs"):
            svc.update_account(actor_user_id=admin, user_id=user.user_id, username="tech.one",
                               full_name="T", email_address=None, role="general",
                               client_person_id=None, person_roles=persons)


# ---------------------------------------------------------------------------
# Setup and reset tokens
# ---------------------------------------------------------------------------


def _token_state(raw):
    return _sql("SELECT used_at IS NOT NULL, revoked_at IS NOT NULL, expires_at > now() "
                "FROM SCHEMA.auth_tokens WHERE token_hash = :h", h=credentials.hash_token(raw))[0]


class TestSetupTokens:
    def test_setup_activates_and_stores_only_a_hash(self):
        admin = _make_admin()
        user = _account(admin)
        link = svc.issue_link(actor_user_id=admin, user_id=user.user_id)
        raw = link.url.split("token=")[1]
        assert link.purpose == "setup" and "/set-password?token=" in link.url

        stored = _sql("SELECT token_hash FROM SCHEMA.auth_tokens")[0][0]
        assert stored == credentials.hash_token(raw) and stored != raw

        assert svc.complete_password_setup(raw, GOOD).ok
        after = _row(user.user_id)
        assert after.status == "active" and after.has_password and after.password_changed_at
        stored_hash = repo.get_password_hash(user.user_id)
        assert stored_hash.startswith("scrypt:") and GOOD not in stored_hash

    def test_a_setup_token_is_single_use(self):
        admin = _make_admin()
        user = _account(admin)
        raw = _activate(admin, user)
        assert _token_state(raw)[0] is True
        second = svc.complete_password_setup(raw, OTHER)
        assert not second.ok and second.error == svc.INVALID_LINK_MESSAGE
        # the first password is still the one in force
        assert auth_service.authenticate("tech.one", GOOD) is not None
        assert auth_service.authenticate("tech.one", OTHER) is None

    def test_an_expired_token_is_refused(self):
        admin = _make_admin()
        user = _account(admin)
        raw = svc.issue_link(actor_user_id=admin, user_id=user.user_id).url.split("token=")[1]
        _sql("UPDATE SCHEMA.auth_tokens SET expires_at = now() - interval '1 second'")
        assert svc.token_is_usable(raw) is False
        outcome = svc.complete_password_setup(raw, GOOD)
        assert not outcome.ok and outcome.error == svc.INVALID_LINK_MESSAGE
        assert _row(user.user_id).status == "pending_activation"

    def test_a_weak_password_does_not_consume_the_link(self):
        admin = _make_admin()
        user = _account(admin)
        raw = svc.issue_link(actor_user_id=admin, user_id=user.user_id).url.split("token=")[1]
        weak = svc.complete_password_setup(raw, "short")
        assert not weak.ok and "12" in weak.error
        assert _token_state(raw)[0] is False
        assert svc.complete_password_setup(raw, GOOD).ok

    def test_unknown_and_blank_tokens_are_refused_identically(self):
        for raw in ("nope", "", None):
            outcome = svc.complete_password_setup(raw, GOOD)
            assert outcome.error == svc.INVALID_LINK_MESSAGE

    def test_a_new_link_revokes_the_previous_one(self):
        admin = _make_admin()
        user = _account(admin)
        first = svc.issue_link(actor_user_id=admin, user_id=user.user_id).url.split("token=")[1]
        second = svc.issue_link(actor_user_id=admin, user_id=user.user_id).url.split("token=")[1]
        assert svc.token_is_usable(first) is False and svc.token_is_usable(second) is True

    def test_disabling_revokes_open_links_and_blocks_completion(self):
        admin = _make_admin()
        user = _account(admin)
        raw = svc.issue_link(actor_user_id=admin, user_id=user.user_id).url.split("token=")[1]
        svc.disable_account(actor_user_id=admin, user_id=user.user_id)
        assert svc.token_is_usable(raw) is False
        assert not svc.complete_password_setup(raw, GOOD).ok
        with pytest.raises(AccountError, match="disabled"):
            svc.issue_link(actor_user_id=admin, user_id=user.user_id)

    def test_a_technician_needs_a_client_link_before_a_setup_link(self):
        admin = _make_admin()
        unlinked = _account(admin, "tech.unlinked", person=None)
        with pytest.raises(AccountError, match="Link this Technician"):
            svc.issue_link(actor_user_id=admin, user_id=unlinked.user_id)


class TestResetTokens:
    def _active(self):
        admin = _make_admin()
        user = _account(admin)
        _activate(admin, user, GOOD)
        return admin, user

    def test_reset_sets_a_new_password_single_use_and_revokes_sessions(self):
        import app as app_module

        admin, user = self._active()
        link = svc.issue_link(actor_user_id=admin, user_id=user.user_id)
        assert link.purpose == "reset"
        raw = link.url.split("token=")[1]

        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(user.user_id)
            assert auth_service.current_identity() is not None
            assert svc.complete_password_setup(raw, OTHER).ok
            assert auth_service.current_identity() is None, "reset must kill the old session"

        assert auth_service.authenticate("tech.one", OTHER) is not None
        assert auth_service.authenticate("tech.one", GOOD) is None
        assert not svc.complete_password_setup(raw, GOOD).ok
        ops = _audit_ops()
        assert audit_cfg.PASSWORD_RESET_INITIATED in ops and audit_cfg.PASSWORD_RESET_COMPLETED in ops

    def test_a_reset_token_expires(self):
        admin, user = self._active()
        raw = svc.issue_link(actor_user_id=admin, user_id=user.user_id).url.split("token=")[1]
        _sql("UPDATE SCHEMA.auth_tokens SET expires_at = now() - interval '1 minute' WHERE used_at IS NULL")
        assert not svc.complete_password_setup(raw, OTHER).ok
        assert auth_service.authenticate("tech.one", GOOD) is not None


# ---------------------------------------------------------------------------
# Account state
# ---------------------------------------------------------------------------


class TestAccountState:
    def test_pending_cannot_login_active_can_disabled_cannot(self):
        admin = _make_admin()
        user = _account(admin)
        assert login_service.attempt_login("tech.one", GOOD).user is None  # pending, no password
        _activate(admin, user)
        assert login_service.attempt_login("tech.one", GOOD).user.user_id == user.user_id
        svc.disable_account(actor_user_id=admin, user_id=user.user_id)
        assert login_service.attempt_login("tech.one", GOOD).user is None

    def test_reenable_restores_active_when_a_password_exists_else_pending(self):
        admin = _make_admin()
        with_pw, without = _account(admin, "tech.a", person=2), _account(admin, "tech.b", person=3)
        _activate(admin, with_pw)
        svc.disable_account(actor_user_id=admin, user_id=with_pw.user_id)
        svc.disable_account(actor_user_id=admin, user_id=without.user_id)
        assert svc.enable_account(actor_user_id=admin, user_id=with_pw.user_id).status == "active"
        assert svc.enable_account(actor_user_id=admin, user_id=without.user_id).status == "pending_activation"
        assert login_service.attempt_login("tech.a", GOOD).user is not None
        assert login_service.attempt_login("tech.b", GOOD).user is None
        with pytest.raises(AccountError, match="disabled"):
            svc.enable_account(actor_user_id=admin, user_id=with_pw.user_id)

    def test_disabling_does_not_touch_assignments(self):
        admin = _make_admin()
        user = _account(admin)
        _sql("INSERT INTO SCHEMA.rtl_technician_assignments "
             "(device_uid, technician_user_id, provenance, imported_at) "
             "VALUES (29001, :u, 'LEGACY_IMPORT', now()), (29002, :u, 'LEGACY_IMPORT', now())",
             u=user.user_id)
        before = _sql("SELECT assignment_id, device_uid, ended_at FROM SCHEMA.rtl_technician_assignments ORDER BY 1")
        svc.disable_account(actor_user_id=admin, user_id=user.user_id)
        assert _sql("SELECT assignment_id, device_uid, ended_at FROM SCHEMA.rtl_technician_assignments ORDER BY 1") == before
        svc.enable_account(actor_user_id=admin, user_id=user.user_id)
        assert _sql("SELECT assignment_id, device_uid, ended_at FROM SCHEMA.rtl_technician_assignments ORDER BY 1") == before

    def test_disabling_kills_existing_sessions(self):
        import app as app_module

        admin = _make_admin()
        user = _account(admin)
        _activate(admin, user)
        with app_module.app.server.test_request_context():
            auth_service.start_trusted_session(user.user_id)
            assert auth_service.current_identity() is not None
            svc.disable_account(actor_user_id=admin, user_id=user.user_id)
            assert auth_service.current_identity() is None

    def test_an_administrator_cannot_disable_themselves(self):
        """The actor must be an Active Administrator, so refusing self-disable
        guarantees at least one Administrator always remains."""
        admin = _make_admin()
        with pytest.raises(AccountError, match="your own"):
            svc.disable_account(actor_user_id=admin, user_id=admin)
        assert _row(admin).status == "active"


# ---------------------------------------------------------------------------
# Login throttling and audit
# ---------------------------------------------------------------------------


class TestThrottleAndAudit:
    def test_repeated_failures_lock_the_name_then_recover(self):
        admin = _make_admin()
        user = _account(admin)
        _activate(admin, user)
        for _ in range(auth_settings.throttle_threshold):
            assert login_service.attempt_login("tech.one", "wrong-password-value").throttled is False
        locked = login_service.attempt_login("tech.one", GOOD)
        assert locked.throttled and locked.user is None, "even the right password waits"

        _sql("UPDATE SCHEMA.auth_login_throttle SET locked_until = now() - interval '1 second'")
        recovered = login_service.attempt_login("tech.one", GOOD)
        assert recovered.user is not None
        assert _sql("SELECT count(*) FROM SCHEMA.auth_login_throttle")[0][0] == 0

    def test_an_unknown_name_is_throttled_exactly_like_a_real_one(self):
        for _ in range(auth_settings.throttle_threshold):
            login_service.attempt_login("ghost.user", "wrong-password-value")
        assert login_service.attempt_login("ghost.user", GOOD).throttled is True

    def test_the_lock_is_bounded_and_the_count_forgets(self):
        key = credentials.throttle_key("someone")
        for _ in range(auth_settings.throttle_threshold + 30):
            repo.record_login_failure(key, threshold=5, base_seconds=60, max_seconds=900, forget_seconds=1800)
        assert 0 < repo.get_throttle_lock_seconds(key) <= 900
        _sql("UPDATE SCHEMA.auth_login_throttle SET last_failure_at = now() - interval '2 hours', "
             "locked_until = NULL")
        count, _ = repo.record_login_failure(key, threshold=5, base_seconds=60, max_seconds=900, forget_seconds=1800)
        assert count == 1

    def test_login_success_failure_logout_are_audited_without_secrets(self):
        admin = _make_admin()
        user = _account(admin)
        raw = svc.issue_link(actor_user_id=admin, user_id=user.user_id).url.split("token=")[1]
        svc.complete_password_setup(raw, GOOD)
        login_service.attempt_login("tech.one", "wrong-password-value")
        login_service.attempt_login("ghost", "typed-a-password-as-username")
        login_service.attempt_login("tech.one", GOOD)
        from services import login_security

        login_security.register_logout(user.user_id)

        ops = _audit_ops()
        for expected in (audit_cfg.USER_CREATED, audit_cfg.CLIENT_PERSON_LINK_CHANGED,
                         audit_cfg.PASSWORD_SETUP_ISSUED, audit_cfg.PASSWORD_SETUP_COMPLETED,
                         audit_cfg.ACCOUNT_ACTIVATED, audit_cfg.LOGIN_FAILED,
                         audit_cfg.LOGIN_SUCCEEDED, audit_cfg.LOGOUT):
            assert expected in ops, expected

        everything = json.dumps(
            [list(map(str, r)) for r in _sql(
                "SELECT operation, entity_type, entity_id, user_id, old_values, new_values "
                "FROM SCHEMA.audit_log")]
            + [list(map(str, r)) for r in _sql("SELECT * FROM SCHEMA.auth_tokens")]
            + [list(map(str, r)) for r in _sql("SELECT * FROM SCHEMA.auth_login_throttle")]
        )
        for secret in (GOOD, raw, "wrong-password-value", "typed-a-password-as-username"):
            assert secret not in everything, "a secret reached a stored audit/token/throttle row"
        assert "scrypt:" not in everything, "a password hash reached the audit log"

        failed = _sql("SELECT user_id, entity_id FROM SCHEMA.audit_log WHERE operation = 'LOGIN_FAILED' ORDER BY audit_id")
        assert all(row[0] is None for row in failed), "failures have no signed-in actor"
        assert {row[1] for row in failed} == {str(user.user_id), "unknown"}

    def test_the_throttle_row_holds_no_username(self):
        login_service.attempt_login("sensitive.name", "x" * 13)
        rows = _sql("SELECT key_hash FROM SCHEMA.auth_login_throttle")
        assert len(rows) == 1 and "sensitive" not in rows[0][0] and len(rows[0][0]) == 64

    def test_a_locked_burst_writes_one_throttle_event_not_one_per_attempt(self):
        for _ in range(auth_settings.throttle_threshold + 4):
            login_service.attempt_login("burst.name", "wrong-password-value")
        ops = _audit_ops()
        assert ops.count(audit_cfg.LOGIN_THROTTLED) == 1
        assert ops.count(audit_cfg.LOGIN_FAILED) == auth_settings.throttle_threshold

    def test_a_failed_audit_refuses_the_sign_in(self, monkeypatch):
        admin = _make_admin()
        user = _account(admin)
        _activate(admin, user)
        from services import audit_service

        def boom(*a, **k):
            raise audit_service.AuditError("down")

        monkeypatch.setattr(audit_service, "record", boom)
        assert login_service.attempt_login("tech.one", GOOD).user is None


# ---------------------------------------------------------------------------
# Bootstrap and preflight
# ---------------------------------------------------------------------------


class TestBootstrap:
    def test_creates_one_pending_administrator_with_a_setup_link_and_no_password(self):
        result = svc.bootstrap_administrator(username="First.Admin", full_name="First Admin")
        user = repo.get_user_by_username("first.admin")
        assert result.created and user.role == "administrator" and user.status == "pending_activation"
        assert user.has_password is False and result.link.purpose == "setup"
        assert audit_cfg.ADMIN_BOOTSTRAPPED in _audit_ops()
        row = _sql("SELECT user_id FROM SCHEMA.audit_log WHERE operation = 'ADMIN_BOOTSTRAPPED'")[0]
        assert row[0] is None, "no human actor exists yet; it is system-originated"

    def test_is_idempotent_and_reissues_the_link_for_a_pending_administrator(self):
        first = svc.bootstrap_administrator(username="first.admin", full_name="F")
        second = svc.bootstrap_administrator(username="first.admin", full_name="F")
        assert first.created and not second.created
        assert svc.token_is_usable(first.link.url.split("token=")[1]) is False
        assert svc.token_is_usable(second.link.url.split("token=")[1]) is True
        assert _sql("SELECT count(*) FROM SCHEMA.users")[0][0] == 1

    def test_completing_the_link_yields_a_working_administrator(self):
        result = svc.bootstrap_administrator(username="first.admin", full_name="F")
        assert svc.complete_password_setup(result.link.url.split("token=")[1], GOOD).ok
        assert login_service.attempt_login("first.admin", GOOD).user.role == "administrator"

    def test_refuses_when_an_active_administrator_with_a_password_exists(self):
        _make_admin()
        with pytest.raises(AccountError, match="already exists"):
            svc.bootstrap_administrator(username="another.admin", full_name="A")
        extra = svc.bootstrap_administrator(username="another.admin", full_name="A", allow_additional=True)
        assert extra.created

    def test_refuses_to_touch_an_existing_non_pending_account(self):
        _make_admin("live.admin")
        with pytest.raises(AccountError, match="not a Pending Administrator"):
            svc.bootstrap_administrator(username="live.admin", full_name="L", allow_additional=True)

    def test_the_cli_prints_a_link_and_never_a_password(self, capsys):
        from scripts import bootstrap_admin

        assert bootstrap_admin.main(["--username", "cli.admin", "--full-name", "Cli Admin"]) == 0
        out = capsys.readouterr().out
        assert "/set-password?token=" in out and "password" in out.lower()
        assert bootstrap_admin.main(["--username", "cli.admin", "--full-name", "Cli Admin"]) == 0
        _make_admin()
        assert bootstrap_admin.main(["--username", "x.admin"]) == 1


class TestPreflight:
    def test_no_usable_administrator_fails_with_the_bootstrap_instruction(self):
        problems = auth_preflight.data_problems()
        assert len(problems) == 1 and "bootstrap_admin" in problems[0]

    def test_a_demo_administrator_alone_is_not_enough(self):
        with session_scope() as s:
            demo = repo.insert_user_account(
                s, username="demo.admin", full_name="D", email_address="demo@example.invalid",
                role="administrator", status="active", client_person_id=None,
            )
            repo.set_password_hash(s, demo.user_id, credentials.hash_password(GOOD), activate=False)
        assert auth_preflight.data_problems()

    def test_a_real_administrator_with_a_password_passes(self):
        _make_admin()
        assert auth_preflight.data_problems() == []

    def test_an_administrator_with_no_password_does_not_count(self):
        with session_scope() as s:
            repo.insert_user_account(s, username="nopw.admin", full_name="N", email_address=None,
                                     role="administrator", status="active", client_person_id=None)
        assert auth_preflight.data_problems()


# ---------------------------------------------------------------------------
# The five existing Technicians: transition without touching assignments
# ---------------------------------------------------------------------------

FIVE = {  # user, client person, open UIDs
    "client-person-2": (2, {29001, 29002, 29003}),
    "client-person-3": (3, {29010, 29011}),
    "client-person-4": (4, {29020}),
    "client-person-5": (5, {29030}),
    "client-person-6": (6, set()),
}


class TestExistingTechnicianTransition:
    def _seed_login_less(self):
        admin = _make_admin()
        users = {}
        for username, (person, uids) in FIVE.items():
            # Exactly what the ADR-032 bootstrap produced, then what migration
            # 017 turns it into: a linked Technician with no credential.
            with session_scope() as s:
                uid = repo.provision_technician_user_for_person(
                    session=s, client_person_id=person, username=username, full_name=f"Person {person}",
                )
            users[username] = uid
            for device_uid in uids:
                _sql("INSERT INTO SCHEMA.rtl_technician_assignments "
                     "(device_uid, technician_user_id, provenance, imported_at) "
                     "VALUES (:d, :u, 'LEGACY_IMPORT', now())", d=device_uid, u=uid)
        return admin, users

    def test_they_start_pending_and_cannot_log_in(self):
        _admin, users = self._seed_login_less()
        for username, uid in users.items():
            assert _row(uid).status == "pending_activation"
            assert login_service.attempt_login(username, GOOD).user is None

    def test_setup_activate_login_and_scope_is_inherited_without_rewriting_assignments(self):
        admin, users = self._seed_login_less()
        before = _sql("SELECT assignment_id, device_uid, technician_user_id, provenance, imported_at, ended_at "
                      "FROM SCHEMA.rtl_technician_assignments ORDER BY assignment_id")

        senzo = users["client-person-2"]
        svc.update_account(actor_user_id=admin, user_id=senzo, username="senzo.m",
                           full_name="Senzo Mpungose", email_address=None, role="technician",
                           client_person_id=2, person_roles=persons)
        _activate(admin, _row(senzo))

        outcome = login_service.attempt_login("senzo.m", GOOD)
        assert outcome.user.user_id == senzo and outcome.user.role == "technician"

        scope = rtl_scope.scope_for(outcome.user)
        assert scope.uids == frozenset(FIVE["client-person-2"][1])
        assert scope.allows(29001) and scope.allows(29003)
        assert not scope.allows(29010), "another Technician's RTL is denied"
        assert not scope.allows(29099), "an unassigned RTL is denied"
        assert scope.restrict({29001, 29010, 29099, 29003}) == [29001, 29003]

        after = _sql("SELECT assignment_id, device_uid, technician_user_id, provenance, imported_at, ended_at "
                     "FROM SCHEMA.rtl_technician_assignments ORDER BY assignment_id")
        assert after == before, "authentication changes must not rewrite assignments"
        assert _row(senzo).client_person_id == 2, "the client link is unchanged"

    def test_an_activated_technician_with_no_assignments_gets_an_empty_not_unrestricted_scope(self):
        admin, users = self._seed_login_less()
        linda = users["client-person-6"]
        _activate(admin, _row(linda))
        scope = rtl_scope.scope_for(login_service.attempt_login("client-person-6", GOOD).user)
        assert scope.uids == frozenset() and scope.is_unrestricted is False

    def test_a_disabled_technician_keeps_history_and_regains_scope_on_reenable(self):
        admin, users = self._seed_login_less()
        senzo = users["client-person-2"]
        _activate(admin, _row(senzo))
        svc.disable_account(actor_user_id=admin, user_id=senzo)
        assert login_service.attempt_login("client-person-2", GOOD).user is None
        svc.enable_account(actor_user_id=admin, user_id=senzo)
        user = login_service.attempt_login("client-person-2", GOOD).user
        assert rtl_scope.scope_for(user).uids == frozenset(FIVE["client-person-2"][1])

    def test_authentication_is_orthogonal_to_general_user_and_administrator_scope(self):
        admin = _make_admin()
        general = repo.create_or_update_user("gen.user", "G", "general", "active")
        _sql("UPDATE SCHEMA.users SET password_hash = :h WHERE user_id = :u",
             h=credentials.hash_password(GOOD), u=general.user_id)
        assert rtl_scope.scope_for(login_service.attempt_login("gen.user", GOOD).user).is_unrestricted
        assert rtl_scope.scope_for(login_service.attempt_login("root.admin", GOOD).user).is_unrestricted
        assert admin
