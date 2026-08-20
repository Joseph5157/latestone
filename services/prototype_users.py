"""Persistent user store — backed by plant_monitoring.users (DB-2).

Public contract (function signatures and returned dict shape) is unchanged
from the DB-1-era in-memory prototype store, so callers in
callbacks/user_admin.py and callbacks/device_assign.py need no changes.
Storage moved from a module-level dict to repositories/plant_monitoring_repository.py;
nothing above this module should know that happened.

Field mapping notes (see repository UserRecord for the full column set):
    identifier  <-> users.email_address
        Verified, not assumed. Four independent sources agree this field is
        an email/contact identifier, not e.g. an employee ID:
          - UI label (components/user_form_drawer.py): "Identifier / Email"
          - UI placeholder on that same input: "e.g. user@example.com"
          - The original design doc, written before this UI existed
            (docs/planning/06_PHASE_5_USER_ADMINISTRATION.md): "Identifier/
            email only if existing auth/domain model safely supports it"
          - Every seed/test value is email-shaped ("demo@local",
            "alice@example.com", ...)
        No source anywhere in the repo (functional spec extract, PAD audit,
        planning docs) names this field as anything else. mobile_number has
        no source in the current contract and stays NULL.
    full_name
        Not part of the current dict contract at all. Defaulted to
        username, since that is the only human-readable identifier the
        contract carries.

Only technician/device assignment, RTL programming requests, message
forwarding, RTL active state, device events and audit logging remain
unwired — DB-2 is users only.
"""
from __future__ import annotations

import logging

from repositories import plant_monitoring_repository as repo

logger = logging.getLogger(__name__)

# Confirmed runtime roles from Functional Specification
CONFIRMED_ROLES = ("administrator", "technician", "general")


def _to_dict(user: repo.UserRecord) -> dict:
    """Convert a repository UserRecord to the contract callers already expect."""
    return {
        "username": user.username,
        "identifier": user.email_address or "",
        "role": user.role,
        "status": user.status,
    }


def seed_demo_user() -> None:
    """Ensure the demo user from config exists. Idempotent: never overwrites
    an existing row (an admin may have since edited it via the UI), and does
    nothing when no demo credential is configured.
    """
    from config.settings import demo_auth
    if not demo_auth.is_configured:
        return
    if repo.get_user_by_username(demo_auth.username) is not None:
        return
    repo.create_or_update_user(
        username=demo_auth.username,
        full_name=demo_auth.username,
        role="general",
        status="active",
        email_address="demo@local",
    )


def get_all_users() -> list[dict]:
    """Return all users as a list."""
    seed_demo_user()
    return [_to_dict(u) for u in repo.list_users()]


def get_user(username: str) -> dict | None:
    """Return a single user by username, or None."""
    seed_demo_user()
    user = repo.get_user_by_username(username)
    return _to_dict(user) if user else None


def upsert_user(username: str, identifier: str = "", role: str = "general",
                status: str = "active") -> None:
    """Add or update a user. Validates role against CONFIRMED_ROLES."""
    role = role if role in CONFIRMED_ROLES else "general"
    repo.create_or_update_user(
        username=username,
        full_name=username,
        role=role,
        status=status,
        email_address=identifier or None,
    )


def remove_user(username: str) -> None:
    """Remove a user if present."""
    repo.delete_user_by_username(username)


def clear_all_users() -> None:
    """Reset the user store (for testing)."""
    repo.delete_all_users()


def get_technicians() -> list[dict]:
    """Return all users with role='technician' and status='active'."""
    seed_demo_user()
    return [
        _to_dict(u) for u in repo.list_users()
        if u.role == "technician" and u.status == "active"
    ]


def get_technician_options() -> list[dict]:
    """Dropdown options for technician assignment — only active technicians.

    Returns empty list when no technicians exist (honest empty state).
    """
    return [
        {"label": u["username"], "value": u["username"]}
        for u in get_technicians()
    ]
