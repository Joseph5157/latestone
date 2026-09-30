"""The user save callback, at the boundary where it actually failed (FIX-1A / AUTH-HARDEN-1).

`confirm_user_form` had two original defects that 2,464 passing tests said
nothing about, because no test had ever called it:

  - it read `user.user_id` while binding `user` nowhere, so every save raised
    `NameError`;
  - it validated a username against the whole store without knowing which
    record was being edited, so re-saving a user under their own unchanged
    name was refused as a duplicate.

AUTH-HARDEN-1 added a third, more serious one (P0-2): the guard checked only
"is someone signed in", not "is that someone an Administrator". A Technician
or General User invoking this callback directly, with `role="administrator"`
among the form fields, could grant themselves the administrator role.
`test_a_non_administrator_cannot_save_a_user` is that attack, run against the
real registered callback.

Two of the original tests fail before that first fix (add, and
edit-unchanged) and two are guards that must stay green through it (a real
duplicate is still refused, an absent session still fails closed). A fix that
turns a refusal into a pass is not a fix.

Role-pure and store-pure: the user service is replaced by a spy, so nothing
here opens a database connection. Identity is now established the AUTH-HARDEN-1
way — a real Flask request context and a real trusted session, backed by a
patched `get_user_by_id` rather than a `dict` handed to the callback — so
these tests exercise the same `current_identity()` path the app uses, not a
browser payload the callback no longer trusts.
"""
from __future__ import annotations

import pytest

from callbacks import user_admin
from components.status_panels import ACTION_REFUSED_CLASS
from tests.auth_test_support import no_trusted_session, trusted_session

ADMIN_USER_ID = 1
TECHNICIAN_USER_ID = 42


class _CapturingApp:
    """Collects callbacks by function name instead of registering them."""

    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


def _handler():
    app = _CapturingApp()
    user_admin.register(app)
    return app.functions["confirm_user_form"]


class _UpsertSpy:
    """Stands in for the account service's write calls and records how each
    was invoked (ADR-033 routed the drawer through `account_service`)."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


@pytest.fixture
def store(monkeypatch):
    """A fake user store: `existing` maps username -> record."""
    existing: dict[str, dict] = {}
    spy = _UpsertSpy()

    from types import SimpleNamespace

    monkeypatch.setattr(user_admin, "get_user", lambda name: existing.get(name))
    monkeypatch.setattr(user_admin.account_service, "create_account", spy)
    monkeypatch.setattr(user_admin.account_service, "update_account", spy)
    monkeypatch.setattr(
        user_admin.account_service,
        "list_accounts",
        lambda actor_user_id: [
            SimpleNamespace(user_id=100 + i, username=name)
            for i, name in enumerate(existing)
        ],
    )
    return existing, spy


def _save(existing_username, username, role="technician"):
    """Click Confirm on the user drawer, as whoever is CURRENTLY trusted.

    The callback takes no `auth-store` argument: AUTH-HARDEN-1 removed the
    browser payload from authorization, and ADR-033 dropped the parameter.
    Args: n_clicks, existing username, username, full name, identifier, role,
    client person id, refresh counter.
    """
    return _handler()(
        1, existing_username, username, "", "person@example.com",
        role, None, 0,
    )


# --------------------------------------------------------------------------
# The two original defects — as an Administrator, the only role that could
# ever legitimately reach a successful save
# --------------------------------------------------------------------------


def test_add_user_persists_with_the_actor_from_the_session(store, monkeypatch):
    """Defect 2: this raised NameError on every save."""
    _existing, spy = store

    with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
        username_error, _result, drawer_style, hidden, _refresh, _cell = _save(None, "newbie")

    assert len(spy.calls) == 1, "the new user must reach persistence"
    _args, kwargs = spy.calls[0]
    assert kwargs["actor_user_id"] == ADMIN_USER_ID, (
        "the write must be attributed to the CURRENT trusted identity, not to "
        "an unbound name and not to anything the browser supplied"
    )
    assert username_error == ""
    assert drawer_style == {"display": "none"}, "a successful save closes the drawer"
    assert hidden is None, "the drawer state is reset after a create"
    assert kwargs["username"] == "newbie"


def test_editing_a_user_under_their_own_unchanged_username_is_allowed(store, monkeypatch):
    """Defect 3: the record being edited was counted as a rival."""
    existing, spy = store
    existing["tech1"] = {"username": "tech1", "role": "technician"}

    with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
        username_error, _result, drawer_style, _hidden, _refresh, _cell = _save("tech1", "tech1")

    assert username_error == "", (
        "an unchanged username belongs to the user being edited and is not a "
        "duplicate"
    )
    assert len(spy.calls) == 1, "the edit must be persisted"
    assert drawer_style == {"display": "none"}


# --------------------------------------------------------------------------
# Guards — green before the fix, and required to stay green through it
# --------------------------------------------------------------------------


def test_taking_another_users_username_is_still_refused(store, monkeypatch):
    """The fix must not turn every duplicate check off."""
    existing, spy = store
    existing["tech1"] = {"username": "tech1", "role": "technician"}
    existing["tech2"] = {"username": "tech2", "role": "technician"}

    with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
        username_error, _result, _style, _hidden, _refresh, _cell = _save("tech1", "tech2")

    assert username_error, "renaming onto an existing username must be refused"
    assert spy.calls == [], "a refused save must not reach persistence"


def test_no_session_at_all_fails_closed(store):
    """AUD-1: no actor, no write. A real Flask request context with nobody
    signed in — `current_identity()` returns None, exactly as it would for an
    unauthenticated direct callback invocation (AUTH-HARDEN-14)."""
    _existing, spy = store

    with no_trusted_session():
        _error, result, _style, _hidden, _refresh, _cell = _save(None, "newbie")

    assert getattr(result, "className", "") == ACTION_REFUSED_CLASS
    assert spy.calls == []


# --------------------------------------------------------------------------
# P0-2 — the defect AUTH-HARDEN-1 exists to close
# --------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["technician", "general"])
def test_a_non_administrator_cannot_save_a_user(store, monkeypatch, role):
    """AUTH-HARDEN-04 / AUTH-HARDEN-05, against the real callback.

    Before this gate, `confirm_user_form` checked only `user is not None` —
    ANY signed-in identity, not specifically an Administrator. A Technician or
    General User invoking this callback directly, supplying
    role="administrator" as one of the form fields, could grant themselves
    (or anyone) the administrator role. This is that exact attack: a REAL
    trusted non-admin session, attempting to write role="administrator".
    """
    _existing, spy = store

    with trusted_session(monkeypatch, user_id=TECHNICIAN_USER_ID, role=role):
        _error, result, _style, _hidden, _refresh, _cell = _save(
            None, "self-promoted", role="administrator"
        )

    assert getattr(result, "className", "") == ACTION_REFUSED_CLASS
    assert spy.calls == [], (
        f"a {role} must not be able to create/edit a user, least of all one "
        f"granting the administrator role"
    )


def test_a_forged_administrator_role_in_the_form_does_not_help(store, monkeypatch):
    """The role field being saved is irrelevant to whether the SAVE is
    allowed — only the trusted CALLER's role decides that. A technician
    proposing role="technician" for someone else is refused exactly the same
    as one proposing role="administrator"."""
    _existing, spy = store

    with trusted_session(monkeypatch, user_id=TECHNICIAN_USER_ID, role="technician"):
        _error, result, _style, _hidden, _refresh, _cell = _save(
            None, "someone-else", role="technician"
        )

    assert getattr(result, "className", "") == ACTION_REFUSED_CLASS
    assert spy.calls == []
