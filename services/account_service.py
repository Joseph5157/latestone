"""Account lifecycle for application-local authentication (ADR-033).

Owns everything an Administrator does to an account and the two token flows a
user completes themselves:

    create (Pending) -> issue setup link -> user sets password -> Active
    Active -> issue reset link -> user sets password       (sessions revoked)
    Active/Pending -> Disabled -> re-enable (Active if it has a password,
                                              otherwise Pending)

Rules that hold everywhere in this module:

* Only an Active Administrator may run an administrative operation; the service
  checks the actor itself, in addition to the route policy and the callback
  guard (the same layering as `rtl_assignment_service`, ADR-032).
* Every state change and its audit row commit in ONE transaction: a failed
  audit rolls the change back (AUD-1).
* Any security-relevant change — password set/reset, disable, role, client
  person link, rename — bumps `users.session_version` (every existing session
  of that user dies) and revokes that user's open setup/reset tokens.
* A raw token exists exactly once, in the `IssuedLink` returned to the
  Administrator. Only its SHA-256 is stored; nothing here logs or audits it.
* An Administrator cannot disable or re-role their own account, so the
  actor (who must be an Active Administrator) is always a remaining one: the
  application can never be locked out of administration by this service.
* Disabling an account NEVER touches its Technician assignments (ADR-032):
  account state and assignment state are separate facts.
* `client_person_id` is an explicit, validated link to a client `persons` row
  (read-only lookup by stable id): the client role must agree, the person must
  not already belong to another account, and nothing is ever matched by name.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.exc import IntegrityError

from config import audit as audit_cfg
from config.settings import auth_settings
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from repositories.rtl_assignment_source_repository import RTLAssignmentSourceRepository
from services import audit_service
from services import credentials as credentials_mod
from services.prototype_users import CONFIRMED_ROLES

logger = logging.getLogger(__name__)

PENDING = "pending_activation"
ACTIVE = "active"
DISABLED = "disabled"

PURPOSE_SETUP = "setup"
PURPOSE_RESET = "reset"

#: The single message for every unusable token: expired, used, revoked, unknown,
#: or belonging to an account that can no longer use it. It must not say which.
INVALID_LINK_MESSAGE = "This link is invalid or has expired. Ask an Administrator for a new one."

#: Application role -> the client `roles.role_name` a linked person must hold.
#: General Users have no client counterpart, so they cannot be linked.
_CLIENT_ROLE_FOR = {"technician": "Technician", "administrator": "Administrator"}

PersonRoleSource = Callable[[], dict[int, str]]


class AccountError(ValueError):
    """A refusal whose message is safe to show an Administrator."""


@dataclass(frozen=True)
class IssuedLink:
    """A one-time provisioning link. Shown once, never stored in the clear."""

    url: str
    purpose: str
    expires_at: datetime
    username: str


@dataclass(frozen=True)
class SetupOutcome:
    ok: bool
    error: str | None = None


def _default_person_roles() -> dict[int, str]:
    return RTLAssignmentSourceRepository().get_person_roles()


def _fields(user: repo.UserRecord) -> dict:
    """Audit-safe view of an account: no credential material of any kind."""
    return {
        "username": user.username,
        "full_name": user.full_name,
        "email_address": user.email_address,
        "role": user.role,
        "status": user.status,
        "client_person_id": user.client_person_id,
    }


def _require_admin(session, actor_user_id: int) -> repo.UserRecord:
    if not isinstance(actor_user_id, int) or isinstance(actor_user_id, bool):
        raise AccountError("Administrator privileges are required.")
    actor = repo.read_user_by_id(session, actor_user_id)
    if actor is None or actor.role != "administrator" or actor.status != ACTIVE:
        raise AccountError("Administrator privileges are required.")
    return actor


def _validate_link(
    session, *, role: str, client_person_id: int | None, exclude_user_id: int | None,
    person_roles: PersonRoleSource,
) -> None:
    if client_person_id is None:
        return
    if role not in _CLIENT_ROLE_FOR:
        raise AccountError("A General User cannot be linked to a client person.")
    try:
        client_roles = person_roles()
    except Exception as exc:  # source unreachable: fail closed, say nothing internal
        logger.warning("Client person lookup failed: %s", type(exc).__name__)
        raise AccountError(
            "The client person directory is unavailable, so the link was not changed."
        ) from exc
    client_role = client_roles.get(client_person_id)
    if client_role is None:
        raise AccountError(f"No client person with ID {client_person_id} exists.")
    expected = _CLIENT_ROLE_FOR[role]
    if client_role != expected:
        raise AccountError(
            f"Client person {client_person_id} is a {client_role}; "
            f"that does not match the {expected} role."
        )
    owner = repo.get_user_by_client_person_id(client_person_id, session=session)
    if owner is not None and owner.user_id != exclude_user_id:
        raise AccountError(
            f"Client person {client_person_id} is already linked to account "
            f"'{owner.username}'."
        )


def _issue_token(session, user: repo.UserRecord, *, created_by: int | None) -> tuple[str, str, datetime]:
    """Revoke earlier open tokens, mint a new one. Returns (raw, purpose, expiry)."""
    if user.status == DISABLED:
        raise AccountError("A disabled account cannot be issued a link. Re-enable it first.")
    purpose = PURPOSE_SETUP if user.status == PENDING else PURPOSE_RESET
    ttl = (
        auth_settings.setup_token_ttl_hours * 3600
        if purpose == PURPOSE_SETUP
        else auth_settings.reset_token_ttl_minutes * 60
    )
    raw = credentials_mod.new_token()
    repo.revoke_open_auth_tokens(session, user.user_id)
    repo.insert_auth_token(
        session, user_id=user.user_id, purpose=purpose,
        token_hash=credentials_mod.hash_token(raw), ttl_seconds=ttl, created_by=created_by,
    )
    return raw, purpose, datetime.now(timezone.utc) + timedelta(seconds=ttl)


def setup_url(raw_token: str) -> str:
    return f"{auth_settings.public_base_url}/set-password?token={raw_token}"


# ---------------------------------------------------------------------------
# Administrator operations
# ---------------------------------------------------------------------------

def list_accounts(*, actor_user_id: int) -> list[repo.UserRecord]:
    with session_scope() as session:
        _require_admin(session, actor_user_id)
    return repo.list_users()


def create_account(
    *, actor_user_id: int, username: str, full_name: str | None, email_address: str | None,
    role: str, client_person_id: int | None = None,
    person_roles: PersonRoleSource = _default_person_roles,
) -> repo.UserRecord:
    """A new account in Pending activation. It has no credential: a setup link
    must be issued and completed before anyone can sign in to it."""
    error = credentials_mod.username_error(username)
    if error:
        raise AccountError(error)
    name = credentials_mod.normalize_username(username)
    if role not in CONFIRMED_ROLES:
        raise AccountError("Choose a valid role.")
    try:
        with session_scope() as session:
            _require_admin(session, actor_user_id)
            if repo.get_user_by_username(name) is not None:
                raise AccountError("Username already exists.")
            _validate_link(
                session, role=role, client_person_id=client_person_id,
                exclude_user_id=None, person_roles=person_roles,
            )
            created = repo.insert_user_account(
                session, username=name, full_name=(full_name or "").strip() or name,
                email_address=(email_address or "").strip() or None, role=role,
                status=PENDING, client_person_id=client_person_id,
            )
            audit_service.record(
                session, operation=audit_cfg.USER_CREATED, entity_type=audit_cfg.ENTITY_USER,
                entity_id=str(created.user_id), new_values=_fields(created),
                actor_user_id=actor_user_id,
            )
            if client_person_id is not None:
                audit_service.record(
                    session, operation=audit_cfg.CLIENT_PERSON_LINK_CHANGED,
                    entity_type=audit_cfg.ENTITY_USER, entity_id=str(created.user_id),
                    old_values={"client_person_id": None},
                    new_values={"client_person_id": client_person_id},
                    actor_user_id=actor_user_id,
                )
    except IntegrityError as exc:
        raise AccountError("Username or client person link is already in use.") from exc
    return created


def update_account(
    *, actor_user_id: int, user_id: int, username: str, full_name: str | None,
    email_address: str | None, role: str, client_person_id: int | None,
    person_roles: PersonRoleSource = _default_person_roles,
) -> repo.UserRecord:
    """Edit identity fields. Sets the DESIRED state; only differences are
    written and audited. Security-relevant differences revoke sessions/tokens."""
    if role not in CONFIRMED_ROLES:
        raise AccountError("Choose a valid role.")
    try:
        with session_scope() as session:
            _require_admin(session, actor_user_id)
            before = repo.lock_user_by_id(session, user_id)
            if before is None:
                raise AccountError("No such account.")

            new_username = credentials_mod.normalize_username(username)
            fields: dict = {}
            if new_username != before.username:
                error = credentials_mod.username_error(new_username)
                if error:
                    raise AccountError(error)
                if repo.get_user_by_username(new_username) is not None:
                    raise AccountError("Username already exists.")
                fields["username"] = new_username
            new_name = (full_name or "").strip() or before.full_name
            if new_name != before.full_name:
                fields["full_name"] = new_name
            new_email = (email_address or "").strip() or None
            if new_email != before.email_address:
                fields["email_address"] = new_email

            role_changed = role != before.role
            link_changed = client_person_id != before.client_person_id
            if role_changed:
                if user_id == actor_user_id:
                    raise AccountError("You cannot change your own role.")
                if before.role == "technician" and repo.count_open_rtl_assignments_for_user(user_id):
                    raise AccountError(
                        "This Technician still has assigned RTLs. Reassign or end "
                        "them before changing the role."
                    )
                fields["role"] = role
            if role_changed or link_changed:
                _validate_link(
                    session, role=role, client_person_id=client_person_id,
                    exclude_user_id=user_id, person_roles=person_roles,
                )
            if link_changed:
                fields["client_person_id"] = client_person_id

            if not fields:
                return before

            after = repo.update_user_fields(session, user_id, fields)
            if {"username", "role", "client_person_id"} & set(fields):
                repo.bump_session_version(session, user_id)
                repo.revoke_open_auth_tokens(session, user_id)

            if {"username", "full_name", "email_address"} & set(fields):
                audit_service.record(
                    session, operation=audit_cfg.USER_UPDATED, entity_type=audit_cfg.ENTITY_USER,
                    entity_id=str(user_id), old_values=_fields(before), new_values=_fields(after),
                    actor_user_id=actor_user_id,
                )
            if role_changed:
                audit_service.record(
                    session, operation=audit_cfg.USER_ROLE_CHANGED, entity_type=audit_cfg.ENTITY_USER,
                    entity_id=str(user_id), old_values={"role": before.role},
                    new_values={"role": after.role}, actor_user_id=actor_user_id,
                )
            if link_changed:
                audit_service.record(
                    session, operation=audit_cfg.CLIENT_PERSON_LINK_CHANGED,
                    entity_type=audit_cfg.ENTITY_USER, entity_id=str(user_id),
                    old_values={"client_person_id": before.client_person_id},
                    new_values={"client_person_id": after.client_person_id},
                    actor_user_id=actor_user_id,
                )
    except IntegrityError as exc:
        raise AccountError("Username or client person link is already in use.") from exc
    return after


def disable_account(*, actor_user_id: int, user_id: int) -> repo.UserRecord:
    """Refuse further sign-in and kill existing sessions. Assignments are untouched."""
    with session_scope() as session:
        _require_admin(session, actor_user_id)
        before = repo.lock_user_by_id(session, user_id)
        if before is None:
            raise AccountError("No such account.")
        if before.status == DISABLED:
            return before
        if user_id == actor_user_id:
            raise AccountError("You cannot disable your own account.")
        after = repo.update_user_fields(session, user_id, {"status": DISABLED})
        repo.bump_session_version(session, user_id)
        repo.revoke_open_auth_tokens(session, user_id)
        audit_service.record(
            session, operation=audit_cfg.ACCOUNT_DISABLED, entity_type=audit_cfg.ENTITY_USER,
            entity_id=str(user_id), old_values={"status": before.status},
            new_values={"status": DISABLED}, actor_user_id=actor_user_id,
        )
    return after


def enable_account(*, actor_user_id: int, user_id: int) -> repo.UserRecord:
    """Re-enable a Disabled account: Active if it already has a password,
    otherwise Pending activation (a setup link is still required)."""
    with session_scope() as session:
        _require_admin(session, actor_user_id)
        before = repo.lock_user_by_id(session, user_id)
        if before is None:
            raise AccountError("No such account.")
        if before.status != DISABLED:
            raise AccountError("Only a disabled account can be re-enabled.")
        target = ACTIVE if before.has_password else PENDING
        after = repo.update_user_fields(session, user_id, {"status": target})
        repo.bump_session_version(session, user_id)
        audit_service.record(
            session, operation=audit_cfg.ACCOUNT_REENABLED, entity_type=audit_cfg.ENTITY_USER,
            entity_id=str(user_id), old_values={"status": before.status},
            new_values={"status": target}, actor_user_id=actor_user_id,
        )
    return after


def issue_link(*, actor_user_id: int, user_id: int) -> IssuedLink:
    """Issue the one-time setup (Pending) or reset (Active) link.

    This is the controlled administrative provisioning workflow: no email or
    SMS is sent (none exists yet). The Administrator receives the URL once and
    hands it to the user through a channel they trust.
    """
    with session_scope() as session:
        _require_admin(session, actor_user_id)
        user = repo.lock_user_by_id(session, user_id)
        if user is None:
            raise AccountError("No such account.")
        if user.role == "technician" and user.client_person_id is None:
            raise AccountError(
                "Link this Technician to a client person before issuing a setup link."
            )
        raw, purpose, expires_at = _issue_token(session, user, created_by=actor_user_id)
        audit_service.record(
            session,
            operation=(
                audit_cfg.PASSWORD_SETUP_ISSUED if purpose == PURPOSE_SETUP
                else audit_cfg.PASSWORD_RESET_INITIATED
            ),
            entity_type=audit_cfg.ENTITY_USER, entity_id=str(user_id),
            new_values={"purpose": purpose, "expires_at": expires_at},
            actor_user_id=actor_user_id,
        )
    return IssuedLink(setup_url(raw), purpose, expires_at, user.username)


# ---------------------------------------------------------------------------
# User-completed token flows (no signed-in identity: the token is the proof)
# ---------------------------------------------------------------------------

def token_is_usable(raw_token: str | None) -> bool:
    """Whether the link would currently be accepted. Says nothing about whom."""
    if not raw_token:
        return False
    with session_scope() as session:
        record = repo.lock_auth_token(session, credentials_mod.hash_token(raw_token))
        if record is None or not record.usable:
            return False
        user = repo.read_user_by_id(session, record.user_id)
    return user is not None and user.status in (PENDING, ACTIVE)


def complete_password_setup(raw_token: str | None, new_password: str | None) -> SetupOutcome:
    """Consume a setup/reset token and set the password.

    Single-use: the token is marked used in the same transaction that stores the
    hash, and every other open token of that user is revoked. A weak password is
    refused BEFORE anything is consumed, so the user can try again with the same
    link. The account becomes Active if it was Pending; existing sessions die.
    """
    if not raw_token:
        return SetupOutcome(False, INVALID_LINK_MESSAGE)
    with session_scope() as session:
        record = repo.lock_auth_token(session, credentials_mod.hash_token(raw_token))
        if record is None or not record.usable:
            return SetupOutcome(False, INVALID_LINK_MESSAGE)
        user = repo.lock_user_by_id(session, record.user_id)
        if user is None or user.status not in (PENDING, ACTIVE):
            return SetupOutcome(False, INVALID_LINK_MESSAGE)

        problem = credentials_mod.password_policy_error(new_password, username=user.username)
        if problem:
            return SetupOutcome(False, problem)

        was_pending = user.status == PENDING
        repo.set_password_hash(
            session, user.user_id, credentials_mod.hash_password(new_password), activate=True
        )
        repo.mark_auth_token_used(session, record.token_id)
        repo.revoke_open_auth_tokens(session, user.user_id)
        audit_service.record(
            session,
            operation=(
                audit_cfg.PASSWORD_SETUP_COMPLETED if was_pending
                else audit_cfg.PASSWORD_RESET_COMPLETED
            ),
            entity_type=audit_cfg.ENTITY_USER, entity_id=str(user.user_id),
            new_values={"purpose": record.purpose}, actor_user_id=user.user_id,
        )
        if was_pending:
            audit_service.record(
                session, operation=audit_cfg.ACCOUNT_ACTIVATED,
                entity_type=audit_cfg.ENTITY_USER, entity_id=str(user.user_id),
                old_values={"status": PENDING}, new_values={"status": ACTIVE},
                actor_user_id=user.user_id,
            )
    return SetupOutcome(True)


# ---------------------------------------------------------------------------
# Initial Administrator bootstrap (operator command, never at start-up)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BootstrapResult:
    link: IssuedLink
    created: bool


def bootstrap_administrator(
    *, username: str, full_name: str | None, email_address: str | None = None,
    allow_additional: bool = False,
) -> BootstrapResult:
    """Create (or re-issue the setup link for) one Pending Administrator.

    Refuses when an Active Administrator with a password already exists unless
    ``allow_additional``. Safe to repeat: a Pending Administrator of that
    username simply gets a fresh link (the previous one is revoked). It writes
    only to the application PostgreSQL; it never touches the client SQL Server
    and never sets, prints or stores a password.
    """
    error = credentials_mod.username_error(username)
    if error:
        raise AccountError(error)
    name = credentials_mod.normalize_username(username)
    try:
        with session_scope() as session:
            existing = repo.get_user_by_username(name)
            if existing is None:
                if (
                    repo.count_active_administrators(session=session, with_password=True) > 0
                    and not allow_additional
                ):
                    raise AccountError(
                        "An active Administrator with a password already exists. "
                        "Use User Administration, or pass --allow-additional."
                    )
                user = repo.insert_user_account(
                    session, username=name, full_name=(full_name or "").strip() or name,
                    email_address=(email_address or "").strip() or None,
                    role="administrator", status=PENDING, client_person_id=None,
                )
                created = True
            else:
                if existing.role != "administrator" or existing.status != PENDING:
                    raise AccountError(
                        f"'{name}' already exists and is not a Pending Administrator; "
                        "nothing was changed."
                    )
                user = repo.lock_user_by_id(session, existing.user_id)
                created = False
            raw, purpose, expires_at = _issue_token(session, user, created_by=None)
            audit_service.record(
                session, operation=audit_cfg.ADMIN_BOOTSTRAPPED,
                entity_type=audit_cfg.ENTITY_USER, entity_id=str(user.user_id),
                new_values={"created": created, "purpose": purpose, "expires_at": expires_at},
                actor_user_id=None, system_originated=True,
            )
    except IntegrityError as exc:
        raise AccountError("That username is already in use.") from exc
    return BootstrapResult(IssuedLink(setup_url(raw), purpose, expires_at, name), created)
