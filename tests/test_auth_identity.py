"""ROLE-1 — the session identity contract.

`verify_credentials` proves a credential pair and nothing else. ROLE-1 adds the
step after it: who that pair *is*, loaded from the persistent `users` table, and
carried in the session in a shape later phases can enforce against.

Everything here fails closed. A credential that checks out but names no user, a
deactivated account, a role nobody recognises and a session dict that has been
tampered with all produce "not authenticated" rather than a partial identity —
a half-built `AuthenticatedUser` is worse than none, because downstream code
would treat it as real.

WHAT THIS IS NOT. The session lives in a browser-side `dcc.Store`. ROLE-1 makes
identity *consistent*, not *unforgeable*: nothing here verifies a session
server-side, and the data callbacks still do not. That distinction is recorded
in docs/CODE_AUDIT.md and must survive ROLE-2.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest
from dash import no_update

from callbacks.auth import login_outputs
from config import settings
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import UserRecord
from services import auth_service, prototype_users
from services.auth_service import (
    AuthenticatedUser,
    authenticate,
    from_session,
    to_session,
)
from services.prototype_users import CONFIRMED_ROLES


@dataclass(frozen=True)
class _Creds:
    username: str
    password: str

    #: ROLE-4A widened the real settings object from one pair to a map. This
    #: double keeps its single-pair constructor — every test here is about the
    #: one-credential case — and derives the map the service now reads, so the
    #: assertions below still mean what they meant when they were written.
    config_error = None

    @property
    def credentials(self) -> dict:
        return {self.username: self.password} if self.is_configured else {}

    @property
    def is_configured(self) -> bool:
        return bool(self.username) and bool(self.password)


@pytest.fixture
def configured(monkeypatch):
    """Both bindings: `auth_service` imported `demo_auth` at module load, while
    `prototype_users.seed_demo_user` reads it off `config.settings` per call."""
    creds = _Creds("operator", "s3cret")
    monkeypatch.setattr(auth_service, "demo_auth", creds)
    monkeypatch.setattr(settings, "demo_auth", creds)


def record(
    user_id: int = 7,
    username: str = "operator",
    full_name: str = "Ada Operator",
    role: str = "administrator",
    status: str = "active",
) -> UserRecord:
    return UserRecord(
        user_id=user_id,
        username=username,
        full_name=full_name,
        email_address="operator@example.invalid",
        mobile_number=None,
        role=role,
        status=status,
        created_at=None,
        updated_at=None,
    )


@pytest.fixture
def user_row(monkeypatch):
    """Control what the user store returns, without touching a database."""
    holder = {"row": record()}
    monkeypatch.setattr(auth_service.prototype_users, "seed_demo_user", lambda: None)
    monkeypatch.setattr(
        auth_service.repo, "get_user_by_username", lambda username: holder["row"]
    )
    return holder


def session_of(**kwargs) -> dict:
    return to_session(
        AuthenticatedUser(
            user_id=kwargs.get("user_id", 7),
            username=kwargs.get("username", "operator"),
            full_name=kwargs.get("full_name", "Ada Operator"),
            role=kwargs.get("role", "administrator"),
        )
    )


class TestAuthenticatedUser:
    def test_carries_exactly_the_frozen_four_fields(self):
        user = AuthenticatedUser(7, "operator", "Ada Operator", "administrator")
        assert (user.user_id, user.username, user.full_name, user.role) == (
            7,
            "operator",
            "Ada Operator",
            "administrator",
        )

    def test_is_immutable(self):
        """A session identity that callbacks can edit in place is not an
        identity."""
        user = AuthenticatedUser(7, "operator", "Ada Operator", "administrator")
        with pytest.raises(Exception):
            user.role = "technician"  # type: ignore[misc]

    def test_carries_no_credential_material(self):
        fields = set(AuthenticatedUser.__dataclass_fields__)
        assert fields == {"user_id", "username", "full_name", "role"}


class TestAuthenticate:
    def test_returns_the_identity_behind_a_valid_credential(self, configured, user_row):
        user = authenticate("operator", "s3cret")
        assert user == AuthenticatedUser(7, "operator", "Ada Operator", "administrator")

    def test_identity_comes_from_the_user_store_not_the_credential(
        self, configured, user_row
    ):
        """The credential pair proves *a* login; the `users` row decides who
        that is and what role they hold. Deriving either from the typed
        username would make the role a client-supplied value."""
        user_row["row"] = record(user_id=42, full_name="Someone Else", role="technician")
        user = authenticate("operator", "s3cret")
        assert (user.user_id, user.full_name, user.role) == (42, "Someone Else", "technician")

    def test_wrong_password_is_refused(self, configured, user_row):
        assert authenticate("operator", "wrong") is None

    def test_wrong_username_is_refused(self, configured, user_row):
        assert authenticate("someone", "s3cret") is None

    def test_unconfigured_credentials_refuse_everything(self, monkeypatch, user_row):
        monkeypatch.setattr(auth_service, "demo_auth", _Creds("", ""))
        assert authenticate("operator", "s3cret") is None

    def test_valid_credential_with_no_user_row_is_refused(self, configured, user_row):
        """Fail closed rather than invent an identity. A credential that checks
        out but names nobody is a misconfiguration, not a login."""
        user_row["row"] = None
        assert authenticate("operator", "s3cret") is None

    def test_inactive_user_is_refused(self, configured, user_row):
        user_row["row"] = record(status="inactive")
        assert authenticate("operator", "s3cret") is None

    def test_unknown_role_is_refused(self, configured, user_row):
        """A role outside the confirmed vocabulary cannot be reasoned about, so
        it is not a usable identity."""
        user_row["row"] = record(role="superuser")
        assert authenticate("operator", "s3cret") is None

    def test_every_confirmed_role_can_authenticate(self, configured, user_row):
        for role in CONFIRMED_ROLES:
            user_row["row"] = record(role=role)
            assert authenticate("operator", "s3cret").role == role

    def test_a_wrong_credential_never_seeds_or_returns_an_identity(
        self, configured, monkeypatch
    ):
        """ADR-033 replaced credential-before-lookup: the per-user hash lives on
        the row, so the row is read first. What must still hold is that a wrong
        credential provisions nothing and yields no identity."""
        seeded = []
        monkeypatch.setattr(
            auth_service.prototype_users, "seed_demo_user", lambda: seeded.append(1)
        )
        monkeypatch.setattr(auth_service.repo, "get_user_by_username", lambda username: None)
        assert authenticate("operator", "wrong") is None
        assert seeded == []

    def test_refusal_reason_is_not_returned_to_the_caller(self, configured, user_row):
        """Every refusal is the same None. The caller cannot tell 'no such
        user' from 'deactivated' from 'wrong password', so the login form
        cannot leak it either."""
        user_row["row"] = None
        no_user = authenticate("operator", "s3cret")
        user_row["row"] = record(status="inactive")
        inactive = authenticate("operator", "s3cret")
        assert no_user is None and inactive is None


class TestToSession:
    def test_keeps_the_authenticated_flag_existing_consumers_read(self):
        """Four callbacks already branch on this key alone. Widening the store
        must not move it."""
        assert session_of()["authenticated"] is True

    def test_carries_the_identity_fields(self):
        assert session_of() == {
            "authenticated": True,
            "user_id": 7,
            "username": "operator",
            "full_name": "Ada Operator",
            "role": "administrator",
        }

    def test_carries_nothing_else(self):
        """The session is sent to the browser. It holds an identity, never a
        credential and never a row the user never asked to publish."""
        assert set(session_of()) == {
            "authenticated",
            "user_id",
            "username",
            "full_name",
            "role",
        }

    def test_round_trips_through_from_session(self):
        user = AuthenticatedUser(7, "operator", "Ada Operator", "administrator")
        assert from_session(to_session(user)) == user


class TestFromSession:
    def test_reads_back_a_well_formed_session(self):
        assert from_session(session_of()).username == "operator"

    @pytest.mark.parametrize("data", [None, {}, [], "operator", 0])
    def test_rejects_anything_that_is_not_a_session(self, data):
        assert from_session(data) is None

    def test_rejects_an_unauthenticated_session(self):
        data = session_of()
        data["authenticated"] = False
        assert from_session(data) is None

    def test_rejects_the_pre_role1_session_shape(self):
        """`{"authenticated": True}` is what every session looked like before
        ROLE-1. It is a valid flag and an invalid identity, and this function
        is the one that says so."""
        assert from_session({"authenticated": True}) is None

    @pytest.mark.parametrize(
        "field", ["user_id", "username", "full_name", "role"]
    )
    def test_rejects_a_session_missing_any_identity_field(self, field):
        data = session_of()
        del data[field]
        assert from_session(data) is None

    def test_rejects_an_unknown_role(self):
        data = session_of()
        data["role"] = "superuser"
        assert from_session(data) is None

    def test_rejects_a_blank_username(self):
        data = session_of()
        data["username"] = ""
        assert from_session(data) is None

    @pytest.mark.parametrize("value", ["7", 7.5, None, True])
    def test_rejects_a_user_id_that_is_not_an_integer(self, value):
        """`True` is included deliberately: it is an `int` in Python, and an
        identity whose user_id is a boolean would silently address user 1."""
        data = session_of()
        data["user_id"] = value
        assert from_session(data) is None

    def test_does_not_query_the_database(self, monkeypatch):
        """ROLE-1 guardrail. Every UI callback that reads the store would
        otherwise become an identity lookup. Revalidating a persisted role or
        status is a deliberate decision for the authorization phase, not a
        side effect of reading a session."""

        def explode(*args, **kwargs):
            raise AssertionError("from_session must not reach the database")

        monkeypatch.setattr(auth_service.repo, "get_user_by_username", explode)
        monkeypatch.setattr(auth_service.repo, "list_users", explode)
        monkeypatch.setattr(auth_service.prototype_users, "seed_demo_user", explode)
        assert from_session(session_of()).role == "administrator"

    def test_tolerates_extra_keys(self):
        """Forward compatibility: a later phase adding a session key must not
        invalidate every session written by this one."""
        data = session_of()
        data["issued_at"] = "2026-08-21T00:00:00Z"
        assert from_session(data) is not None


class TestExistingConsumersAreUnaffected:
    def test_the_new_session_still_reads_as_authenticated(self):
        """`routing`, `navigation` and `equipment_selector` all branch on
        `data.get("authenticated")` and nothing else."""
        data = session_of()
        assert bool(data and data.get("authenticated")) is True

    def test_the_default_store_still_reads_as_unauthenticated(self):
        data = {"authenticated": False}
        assert bool(data and data.get("authenticated")) is False

    def test_the_app_default_store_is_still_rejected_as_an_identity(self):
        from app import app  # noqa: F401  (registers nothing new; import is cheap)

        assert from_session({"authenticated": False}) is None


class TestLoginOutputs:
    """The callback's whole body, as a pure function."""

    def test_success_writes_the_full_identity_session(self, configured, user_row):
        error, session = login_outputs("operator", "s3cret")
        assert error == ""
        assert session == to_session(
            AuthenticatedUser(7, "operator", "Ada Operator", "administrator")
        )

    def test_failure_leaves_the_session_untouched(self, configured, user_row):
        error, session = login_outputs("operator", "wrong")
        assert session is no_update

    def test_failure_message_is_generic(self, configured, user_row):
        """Same message for every refusal. A deactivated account must not be
        distinguishable from a wrong password by the wording."""
        user_row["row"] = record(status="inactive")
        inactive_error, _ = login_outputs("operator", "s3cret")
        user_row["row"] = record()
        wrong_error, _ = login_outputs("operator", "wrong")
        assert inactive_error == wrong_error == "Invalid username or password."

    def test_message_names_no_account_detail(self, configured, user_row):
        """The generic wording says "username" as a field name; it must never
        say *which* username, nor the account's status or role."""
        user_row["row"] = record(status="inactive", role="technician")
        error, _ = login_outputs("operator", "s3cret")
        for leak in ("operator", "inactive", "technician", "ada"):
            assert leak not in error.lower()


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestAgainstThePersistentUserStore:
    """The real path: credentials in config, identity out of `users`."""

    def test_authenticates_a_real_row(self, configured):
        repo.create_or_update_user(
            username="operator",
            full_name="Ada Operator",
            role="administrator",
            status="active",
            email_address="operator@example.invalid",
        )
        user = authenticate("operator", "s3cret")
        assert user is not None
        assert (user.username, user.full_name, user.role) == (
            "operator",
            "Ada Operator",
            "administrator",
        )
        assert user.user_id == repo.get_user_by_username("operator").user_id

    def test_refuses_when_the_row_was_deactivated(self, configured):
        repo.create_or_update_user(
            username="operator",
            full_name="Ada Operator",
            role="administrator",
            status="inactive",
        )
        assert authenticate("operator", "s3cret") is None

    def test_refuses_when_no_row_exists_and_none_can_be_seeded(
        self, configured, monkeypatch
    ):
        """Seeding normally guarantees the demo row, so this pins the
        fail-closed branch behind it: a verified credential that resolves to no
        user must refuse, not invent an identity."""
        repo.delete_all_users()
        monkeypatch.setattr(
            auth_service.prototype_users, "seed_demo_user", lambda: None
        )
        assert authenticate("operator", "s3cret") is None


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestDemoUserIsSeededAsAdministrator:
    """The Administrator workflows are what this application is for, and the
    configured demo credential is the only login. Seeding it as `general`
    created a lockout the moment a role meant anything."""

    def test_seeded_demo_user_holds_the_administrator_role(self, configured):
        repo.delete_all_users()
        prototype_users.seed_demo_user()
        assert repo.get_user_by_username("operator").role == "administrator"

    def test_seeding_never_overwrites_an_existing_row(self, configured):
        """An administrator who deliberately demoted this account through User
        Administration must not have it silently restored on next read."""
        repo.delete_all_users()
        repo.create_or_update_user(
            username="operator", full_name="Ada", role="technician", status="active"
        )
        prototype_users.seed_demo_user()
        assert repo.get_user_by_username("operator").role == "technician"

    def test_the_seeded_demo_user_can_authenticate(self, configured):
        repo.delete_all_users()
        user = authenticate("operator", "s3cret")
        assert user is not None and user.role == "administrator"
