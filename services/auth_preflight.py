"""Production authentication preflight (ADR-033).

Two independent halves:

* CONFIGURATION — no demo credentials, no demo login, a session secret. These
  are enforced at import by `config.settings` (a production process holding
  them cannot even start); `configuration_problems()` re-states them so the
  operator command reports every defect in one place.
* DATA — at least one Active Administrator with a real password who is not a
  synthetic/demo identity. Without one nobody can manage users and the app
  cannot be safely operated; the fix is the explicit bootstrap command, which
  this module names in its message.

Never prints a secret: only setting NAMES and counts.
"""
from __future__ import annotations

import os

from config import settings
from repositories import plant_monitoring_repository as repo

BOOTSTRAP_HINT = (
    "Run: python -m scripts.bootstrap_admin --username <name> --full-name \"<name>\" "
    "(it prints a one-time setup link; no password is ever created for you)."
)


def is_synthetic_account(user: repo.UserRecord) -> bool:
    """Development/demo identities that must never be the only production Administrator."""
    email = (user.email_address or "").lower()
    return (
        user.username.startswith("demo.")
        or email.endswith(".invalid")
        or email == "demo@local"
    )


def configuration_problems() -> list[str]:
    problems: list[str] = []
    try:
        settings.validate_production_auth_config(
            "production",
            demo_username=os.getenv("DEMO_USERNAME", ""),
            demo_password=os.getenv("DEMO_PASSWORD", ""),
            demo_credentials=os.getenv("DEMO_CREDENTIALS", ""),
        )
    except RuntimeError as exc:
        problems.append(str(exc))
    if os.getenv("AUTH_DEMO_LOGIN_ENABLED", "").strip().lower() in settings._TRUTHY_VALUES:
        problems.append("AUTH_DEMO_LOGIN_ENABLED must be unset in production.")
    if not os.getenv("FLASK_SECRET_KEY", "").strip():
        problems.append("FLASK_SECRET_KEY must be set in production.")
    return problems


def data_problems() -> list[str]:
    usable = [
        u for u in repo.list_users()
        if u.role == "administrator" and u.status == "active" and u.has_password
        and not is_synthetic_account(u)
    ]
    if usable:
        return []
    return ["No active, non-demo Administrator with a password exists. " + BOOTSTRAP_HINT]


def production_problems() -> list[str]:
    return configuration_problems() + data_problems()
