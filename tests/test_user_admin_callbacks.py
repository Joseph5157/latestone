"""The user save callback, at the boundary where it actually failed (FIX-1A).

`confirm_user_form` had two defects that 2,464 passing tests said nothing
about, because no test had ever called it:

  - it read `user.user_id` while binding `user` nowhere, so every save raised
    `NameError`;
  - it validated a username against the whole store without knowing which
    record was being edited, so re-saving a user under their own unchanged
    name was refused as a duplicate.

The second masked the first: validation returns before the `NameError` line,
so an edit-with-unchanged-name never reached it. Fixing either alone leaves a
misleading result, which is why they are one change.

Two of these tests fail before the fix (add, and edit-unchanged) and two are
guards that must stay green through it (a real duplicate is still refused, an
absent session still fails closed). A fix that turns a refusal into a pass is
not a fix.

Role-pure and store-pure: the user service is replaced by a spy, so nothing
here opens a database connection.
"""
from __future__ import annotations

import pytest

from callbacks import user_admin
from components.status_panels import ACTION_REFUSED_CLASS

ADMINISTRATOR_SESSION = {
    "authenticated": True,
    "user_id": 1,
    "username": "admin",
    "full_name": "Admin",
    "role": "administrator",
}

#: Authenticated flag, no usable identity — the pre-ROLE-1 payload.
STALE_SESSION = {"authenticated": True}


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
    """Stands in for the persistence call and records how it was invoked."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


@pytest.fixture
def store(monkeypatch):
    """A fake user store: `existing` maps username -> record."""
    existing: dict[str, dict] = {}
    spy = _UpsertSpy()

    monkeypatch.setattr(user_admin, "get_user", lambda name: existing.get(name))
    monkeypatch.setattr(user_admin, "upsert_user", spy)
    return existing, spy


def _save(existing_username, username, session):
    """Click Confirm on the user drawer."""
    return _handler()(
        1, existing_username, username, "person@example.com",
        "technician", "active", session,
    )


# --------------------------------------------------------------------------
# The two defects
# --------------------------------------------------------------------------


def test_add_user_persists_with_the_actor_from_the_session(store):
    """Defect 2: this raised NameError on every save."""
    _existing, spy = store

    username_error, _result, drawer_style, hidden = _save(
        None, "newbie", ADMINISTRATOR_SESSION
    )

    assert len(spy.calls) == 1, "the new user must reach persistence"
    _args, kwargs = spy.calls[0]
    assert kwargs["actor_user_id"] == ADMINISTRATOR_SESSION["user_id"], (
        "the write must be attributed to the acting session's identity, "
        "not to an unbound name"
    )
    assert username_error == ""
    assert drawer_style == {"display": "none"}, "a successful save closes the drawer"
    assert hidden == "newbie"


def test_editing_a_user_under_their_own_unchanged_username_is_allowed(store):
    """Defect 3: the record being edited was counted as a rival."""
    existing, spy = store
    existing["tech1"] = {"username": "tech1", "role": "technician"}

    username_error, _result, drawer_style, _hidden = _save(
        "tech1", "tech1", ADMINISTRATOR_SESSION
    )

    assert username_error == "", (
        "an unchanged username belongs to the user being edited and is not a "
        "duplicate"
    )
    assert len(spy.calls) == 1, "the edit must be persisted"
    assert drawer_style == {"display": "none"}


# --------------------------------------------------------------------------
# Guards — green before the fix, and required to stay green through it
# --------------------------------------------------------------------------


def test_taking_another_users_username_is_still_refused(store):
    """The fix must not turn every duplicate check off."""
    existing, spy = store
    existing["tech1"] = {"username": "tech1", "role": "technician"}
    existing["tech2"] = {"username": "tech2", "role": "technician"}

    username_error, _result, _style, _hidden = _save(
        "tech1", "tech2", ADMINISTRATOR_SESSION
    )

    assert username_error, "renaming onto an existing username must be refused"
    assert spy.calls == [], "a refused save must not reach persistence"


def test_a_session_without_identity_fails_closed(store):
    """AUD-1: no actor, no write."""
    _existing, spy = store

    _error, result, _style, _hidden = _save(None, "newbie", STALE_SESSION)

    assert getattr(result, "className", "") == ACTION_REFUSED_CLASS
    assert spy.calls == [], "an unattributable write must not happen"


def test_no_session_at_all_fails_closed(store):
    _existing, spy = store

    _error, result, _style, _hidden = _save(None, "newbie", None)

    assert getattr(result, "className", "") == ACTION_REFUSED_CLASS
    assert spy.calls == []
