"""
Placeholder authentication for the development application.

Intentionally isolated so it can be swapped for the client's real
authentication (API/session/SSO) without touching UI code — callbacks should
only ever call `verify_credentials()`.

**This is not an authorization boundary.** It checks a credential pair and
nothing more. The result is held in a browser-side `dcc.Store`, and the data
callbacks do not independently verify a session, so anyone able to set that
store can reach the data callbacks. Replacing this module is necessary but not
sufficient — see docs/CODE_AUDIT.md, "Security posture".
"""
from __future__ import annotations

import hmac
import logging

from config.settings import demo_auth

logger = logging.getLogger(__name__)


def verify_credentials(username: str, password: str) -> bool:
    """Check the configured credential pair. Fails closed when unconfigured.

    There is no fallback credential: if `DEMO_USERNAME`/`DEMO_PASSWORD` are not
    set, every login is refused rather than silently accepting a well-known
    default that is published in `.env.example`.
    """
    if not username or not password:
        return False

    if not demo_auth.is_configured:
        logger.error(
            "Login refused: DEMO_USERNAME/DEMO_PASSWORD are not configured. "
            "Set them in .env (see .env.example)."
        )
        return False

    # Compared with compare_digest so the check does not leak length or a
    # matching prefix through timing. Cheap here, and the habit matters more
    # once this is swapped for something real.
    return hmac.compare_digest(username, demo_auth.username) and hmac.compare_digest(
        password, demo_auth.password
    )
