"""AUTH-HARDEN-1 test support — establishing a real trusted identity.

`current_identity()` (services/auth_service.py) reads exactly one thing from
Flask's signed session: a user_id. Everything else — role, status, name — is
re-read from `repo.get_user_by_id` on every call. So the correct way to test
code that calls `current_identity()` is not to monkeypatch `current_identity`
itself (that would test nothing about the real wiring) — it is to do what a
real login does: push a real Flask request context, patch the ONE database
read the identity is rebuilt from, and call the same
`auth_service.start_trusted_session()` the login callback calls.

`trusted_session()` below is that, for the pure-logic ("not db") suite, where
patching `get_user_by_id` is the established way to supply a user row without
a database (see tests/test_credentialed_personas.py for the same pattern
against `get_user_by_username`). A `db`-marked test that already has a real
`UserRecord` from a real insert does not need this: it can call
`auth_service.start_trusted_session(real_user_id)` directly inside
`app_module.app.server.test_request_context()`, exactly as
tests/test_route_scope_db.py does — patching a DB read that already has real
data behind it would be backwards.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone

import app as app_module
from repositories import plant_monitoring_repository as repo
from services import auth_service

_STAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


def fake_user_row(
    user_id: int,
    role: str,
    *,
    username: str | None = None,
    full_name: str | None = None,
    status: str = "active",
) -> repo.UserRecord:
    """A `UserRecord` for tests that need one without a database."""
    username = username or f"test.{role}"
    return repo.UserRecord(
        user_id=user_id,
        username=username,
        full_name=full_name or username,
        email_address=None,
        mobile_number=None,
        role=role,
        status=status,
        created_at=_STAMP,
        updated_at=_STAMP,
    )


@contextlib.contextmanager
def trusted_session(monkeypatch, *, user_id: int, role: str, status: str = "active", **row_kwargs):
    """Act as a real trusted `(user_id, role, status)` for the duration of the block.

    Patches `repo.get_user_by_id` to answer for this one user_id (no database
    needed) and pushes a real Flask request context with a real trusted
    session established the same way `callbacks.auth.handle_login` establishes
    one. Any code under test that calls `current_identity()` — directly, or
    through `current_device_scope()` / `require_action()` / `require_capability()`
    — sees exactly what it would see against a real database row.
    """
    row = fake_user_row(user_id, role, status=status, **row_kwargs)
    monkeypatch.setattr(
        repo, "get_user_by_id", lambda uid: row if uid == user_id else None
    )
    with app_module.app.server.test_request_context():
        auth_service.start_trusted_session(user_id)
        yield row


@contextlib.contextmanager
def no_trusted_session():
    """A real Flask request context with nobody signed in.

    For proving a callback fails closed rather than raising when
    `current_identity()` legitimately returns None — an unauthenticated direct
    invocation, or a session the server no longer recognises.
    """
    with app_module.app.server.test_request_context():
        yield


@contextlib.contextmanager
def as_session(monkeypatch, session: dict | None):
    """Establish the trusted identity an old `auth-store`-shaped `session`
    dict used to describe, for tests migrating off browser-trusted payloads.

    A real `{"authenticated": True, "user_id": ..., "role": ...}` dict becomes
    a real `trusted_session` for that user_id/role. Anything that is not a
    genuine identity — `None`, `{}`, `{"authenticated": False}`, or the
    pre-ROLE-1 `{"authenticated": True}` with no `user_id`/`role` — becomes
    `no_trusted_session()`, because none of those ever named a real signed-in
    user for `current_identity()` to find. This exists so a test file
    written against the old "hand the callback a session dict" shape can be
    migrated with the smallest possible diff; new tests should prefer
    `trusted_session`/`no_trusted_session` directly.
    """
    if not session or not session.get("authenticated") or "user_id" not in session:
        with no_trusted_session():
            yield
        return
    with trusted_session(monkeypatch, user_id=session["user_id"], role=session["role"]):
        yield
