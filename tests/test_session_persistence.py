"""The session survives a reload, and signing out is a real action.

`auth-store` was `storage_type="memory"`, so every full page load discarded
it. That made two things true at once: a browser refresh signed you out, and
`<a href="/logout">` "worked" precisely because it was a full page load. The
first is the bug; the second is the trap under the fix — persist the store
without replacing that mechanism and the Logout link becomes inert.

Session storage, not local: the sign-in should not outlive the tab.
"""
import pytest
from dash import no_update

import app as app_module
from callbacks.auth import LOGOUT_PATH, sign_out_outputs
from tests.dash_tree import find_by_id


class TestStoreLifetime:
    def test_the_session_survives_a_reload(self):
        store = find_by_id(app_module.app.layout, "auth-store")
        assert store.storage_type == "session"

    def test_it_does_not_outlive_the_tab(self):
        """`local` would keep a demo sign-in on a shared machine
        indefinitely."""
        store = find_by_id(app_module.app.layout, "auth-store")
        assert store.storage_type != "local"

    def test_page_context_stays_in_memory(self):
        """It is derived from the URL on every render; persisting it would
        let a stale route context outlive the page it described."""
        assert find_by_id(app_module.app.layout, "page-context").storage_type == "memory"


class TestSignOut:
    def test_the_logout_path_clears_the_session(self):
        data, pathname = sign_out_outputs(LOGOUT_PATH)
        assert data == {"authenticated": False}
        assert pathname == "/"

    def test_it_clears_rather_than_merely_flagging(self):
        """Anything left behind — a role, a user id — is identity that
        outlives the session it belonged to."""
        data, _pathname = sign_out_outputs(LOGOUT_PATH)
        assert set(data) == {"authenticated"}

    @pytest.mark.parametrize("pathname", ["/", "/plants", "/admin/devices", None])
    def test_every_other_route_is_untouched(self, pathname):
        assert sign_out_outputs(pathname) == (no_update, no_update)

    def test_signing_out_is_reachable_on_a_cold_load(self):
        """Logout is a plain anchor, so /logout arrives as a fresh page load
        rather than as a route change. A callback that skips its initial call
        would never fire for it."""
        callbacks = app_module.app._callback_list
        sign_out = next(
            c for c in callbacks if "auth-store.data" in c["output"] and "url" in str(c["inputs"])
        )
        # The source declares "initial_duplicate" — Dash rejects
        # allow_duplicate with an unguarded initial call — and Dash records
        # that as False here. False is the meaning that matters: it fires on
        # the first render.
        assert sign_out["prevent_initial_call"] is False


class TestTheLinkStillWorks:
    def test_the_header_still_offers_logout(self):
        from components.app_header import app_header

        hrefs = [
            n.href for n in __import__("tests.dash_tree", fromlist=["walk"]).walk(app_header())
            if getattr(n, "href", None) == LOGOUT_PATH
        ]
        assert hrefs == [LOGOUT_PATH]
