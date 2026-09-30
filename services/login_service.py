"""The sign-in path the login form uses (ADR-033).

    throttle check -> credential verdict -> bookkeeping (throttle + audit)

`auth_service.check_credentials` answers who a credential belongs to;
`login_security` does the database side effects. This module is the one place
that orders them, and the one the login callback calls.

Every refusal that is not a throttle answers with the same generic result, so
the form cannot say whether a name exists, is Pending, is Disabled or had the
wrong password.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from services import auth_service, login_security

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoginOutcome:
    user: auth_service.AuthenticatedUser | None
    #: True only when the attempt was refused WITHOUT being checked because
    #: this login name is in a back-off window. Carries no counter and no
    #: remaining time: the user is told to wait, not how the limit works.
    throttled: bool = False


def attempt_login(username: str | None, password: str | None) -> LoginOutcome:
    try:
        if login_security.locked_seconds(username) > 0:
            return LoginOutcome(None, throttled=True)
    except Exception:
        # Cannot read the throttle: fail closed rather than let an unthrottled
        # guess through.
        logger.exception("Could not read the sign-in throttle; refusing the attempt")
        return LoginOutcome(None)

    check = auth_service.check_credentials(username or "", password or "")

    if check.user is None:
        login_security.register_failure(username, user_id=check.user_id, reason=check.reason)
        return LoginOutcome(None)

    try:
        login_security.register_success(username, check.user.user_id)
    except Exception:
        logger.exception("Sign-in bookkeeping failed for user_id=%s; refusing", check.user.user_id)
        return LoginOutcome(None)
    return LoginOutcome(check.user)
