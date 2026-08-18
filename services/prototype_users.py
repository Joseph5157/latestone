"""Prototype user state — shared in-memory user store for device workflows.

This module owns the single source of truth for prototype user data. Other
modules (user_admin, device_assign, device_manage) import from here rather
than maintaining separate stores.

Prototype only: does not persist to any identity system.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# In-memory prototype user store: username -> {username, identifier, role, status}
_mock_users: dict[str, dict] = {}

# Confirmed runtime roles from Functional Specification
CONFIRMED_ROLES = ("administrator", "technician", "general")


def seed_demo_user() -> None:
    """Initialize mock users with the demo credential from config.

    Called once at startup; idempotent.
    """
    from config.settings import demo_auth
    if demo_auth.is_configured and demo_auth.username not in _mock_users:
        _mock_users[demo_auth.username] = {
            "username": demo_auth.username,
            "identifier": "demo@local",
            "role": "general",
            "status": "active",
        }


def get_all_users() -> list[dict]:
    """Return all mock users as a list."""
    seed_demo_user()
    return list(_mock_users.values())


def get_user(username: str) -> dict | None:
    """Return a single mock user by username, or None."""
    seed_demo_user()
    return _mock_users.get(username)


def upsert_user(username: str, identifier: str = "", role: str = "general",
                status: str = "active") -> None:
    """Add or update a mock user. Validates role against CONFIRMED_ROLES."""
    role = role if role in CONFIRMED_ROLES else "general"
    _mock_users[username] = {
        "username": username,
        "identifier": identifier,
        "role": role,
        "status": status,
    }


def remove_user(username: str) -> None:
    """Remove a mock user if present."""
    _mock_users.pop(username, None)


def clear_all_users() -> None:
    """Reset the mock store (for testing)."""
    _mock_users.clear()


def get_technicians() -> list[dict]:
    """Return all mock users with role='technician' and status='active'."""
    seed_demo_user()
    return [u for u in _mock_users.values()
            if u.get("role") == "technician" and u.get("status") == "active"]


def get_technician_options() -> list[dict]:
    """Dropdown options for technician assignment — only active technicians.

    Returns empty list when no technicians exist (honest empty state).
    """
    return [
        {"label": u["username"], "value": u["username"]}
        for u in get_technicians()
    ]
