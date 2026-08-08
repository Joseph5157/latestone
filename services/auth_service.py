"""
Local/mock authentication service for the demo.

Intentionally isolated so it can be swapped for the client's real
authentication (API/session/SSO) without touching UI code - callbacks
should only ever call `verify_credentials()` and `is_authenticated()`.
"""
from __future__ import annotations

from config.settings import demo_auth


def verify_credentials(username: str, password: str) -> bool:
    """Check demo credentials. Local/mock only - not production auth."""
    if not username or not password:
        return False
    return username == demo_auth.username and password == demo_auth.password
