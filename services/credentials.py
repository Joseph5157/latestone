"""Credential primitives for application-local authentication (ADR-033).

Pure functions — no database, no Flask — so the security-critical rules are
testable in isolation and there is exactly one place each is defined:

* passwords are hashed with werkzeug's ``scrypt`` (per-user random salt, encoded
  into the stored string) and verified only with its ``check_password_hash``;
  nothing here ever compares a password directly;
* the password policy is a length floor (12) and nothing else — passphrases and
  password-manager output are welcome, arbitrary composition rules are not;
* setup/reset tokens are 256-bit random values; only their SHA-256 is stored;
* a login name has one canonical form (stripped, lower case).

Never logs, returns or persists a plaintext password or a raw token.
"""
from __future__ import annotations

import hashlib
import re
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from config.settings import auth_settings

HASH_METHOD = "scrypt"

#: 3-50 characters, lower-case letters, digits and `. _ - @`, starting with a
#: letter or digit. Applied to NEW and renamed accounts only: existing rows are
#: grandfathered (the database only insists on lower case).
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._@-]{2,49}$")


def normalize_username(raw: str | None) -> str:
    """The canonical login identifier: stripped and lower-cased.

    One rule, used at every lookup and write, so ``Admin`` and ``admin`` can
    never be two accounts. Never derived from a display name.
    """
    return (raw or "").strip().lower()


def username_error(raw: str | None) -> str | None:
    name = normalize_username(raw)
    if not name:
        return "Username is required."
    if not _USERNAME_RE.match(name):
        return (
            "Username must be 3-50 characters: letters, digits, and . _ - @ "
            "(starting with a letter or digit)."
        )
    return None


def password_policy_error(password: str | None, *, username: str | None = None) -> str | None:
    """Why ``password`` is unacceptable, or None. The whole policy."""
    if not password or not password.strip():
        return "Password is required."
    if len(password) < auth_settings.password_min_length:
        return f"Password must be at least {auth_settings.password_min_length} characters."
    if len(password) > auth_settings.password_max_length:
        return f"Password must be at most {auth_settings.password_max_length} characters."
    if username and password.strip().lower() == normalize_username(username):
        return "Password must not be the same as the username."
    return None


def hash_password(password: str) -> str:
    return generate_password_hash(password, method=HASH_METHOD)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return bool(check_password_hash(stored_hash, password))
    except (ValueError, TypeError):
        # A malformed stored value must fail closed, not raise a 500.
        return False


#: A real scrypt hash of a random throwaway value, built once on first use.
#: Verifying a typed password against it costs the same as a real check, so an
#: unknown, pending or disabled account answers no faster than a wrong
#: password — the difference would be a username oracle.
_DUMMY_HASH: str | None = None


def burn_verification_time(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(24))
    verify_password(_DUMMY_HASH, password or "")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex of a token. Adequate (not a password hash) because the
    input is 256 bits of randomness, not a human-chosen secret."""
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def throttle_key(username: str | None) -> str:
    """The throttle bucket for a typed login name: a hash, so the table holds
    no usernames (including mistyped passwords) and unknown names share the
    exact behaviour of real ones."""
    return hashlib.sha256(f"login:{normalize_username(username)}".encode("utf-8")).hexdigest()
