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
from callbacks.auth import (
    LOGIN_PATH,
    LOGOUT_PATH,
    login_path_redirect,
    sign_out_outputs,
)
from services.auth_service import AuthenticatedUser
from tests.dash_tree import find_by_id

#: Any active identity will do — the helper branches on presence, not
#: on role: every role lands somewhere, and `landing_route_name` is
#: what decides where.
_SIGNED_IN = AuthenticatedUser(
    user_id=1, username="demo.admin01", full_name="Demo Admin", role="administrator"
)


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
    def test_the_sidebar_offers_logout(self):
        """Moved out of app_header: that is rendered per page, and Command
        Center renders none at all, so a header-only sign-out was present
        or absent depending on the route. The sidebar is mounted once
        globally and hidden wholesale when signed out."""
        from components.app_sidebar import app_sidebar

        hrefs = [
            n.href for n in __import__("tests.dash_tree", fromlist=["walk"]).walk(app_sidebar())
            if getattr(n, "href", None) == LOGOUT_PATH
        ]
        assert hrefs == [LOGOUT_PATH]

    def test_logout_is_a_plain_anchor_not_a_client_side_link(self):
        """A dcc.Link would route client-side. The full page load is what
        lets callbacks.auth._sign_out fire on its initial call, and what
        makes a bookmarked /logout sign out rather than render nothing."""
        from dash import html

        from components.app_sidebar import app_sidebar

        anchors = [
            n for n in __import__("tests.dash_tree", fromlist=["walk"]).walk(app_sidebar())
            if getattr(n, "href", None) == LOGOUT_PATH
        ]
        assert [type(a) for a in anchors] == [html.A]


class TestStoreFollowsTheTrustedSession:
    """AUTH-SIDEBAR-1: the router trusts the server session, the sidebar
    trusts `auth-store`. When they drift the login page renders beside a
    signed-in sidebar, so the store is rewritten from the server's answer."""

    @staticmethod
    def _user(role="administrator"):
        from services.auth_service import AuthenticatedUser

        return AuthenticatedUser(user_id=7, username="op", full_name="Op", role=role)

    def test_a_lost_server_session_signs_the_store_out(self):
        """App restart (new secret key) or a logout in another tab: the
        cookie is gone but this tab's store still claims a user."""
        from callbacks.auth import reconciled_auth_store
        from services.auth_service import to_session

        stale = to_session(self._user())
        assert reconciled_auth_store("/plants", stale, None) == {"authenticated": False}

    def test_a_valid_cookie_fills_an_empty_store(self):
        """A new tab starts with an empty store but shares the cookie; the
        router shows the page, so the sidebar must show too."""
        from callbacks.auth import reconciled_auth_store
        from services.auth_service import to_session

        user = self._user()
        assert reconciled_auth_store("/", {"authenticated": False}, user) == to_session(user)

    def test_a_role_change_reaches_the_store(self):
        from callbacks.auth import reconciled_auth_store
        from services.auth_service import to_session

        stale = to_session(self._user("administrator"))
        fresh = self._user("technician")
        assert reconciled_auth_store("/", stale, fresh) == to_session(fresh)

    @pytest.mark.parametrize("signed_in", [True, False])
    def test_an_agreeing_store_is_left_alone(self, signed_in):
        """Also what stops the callback re-firing on its own output."""
        from callbacks.auth import reconciled_auth_store
        from services.auth_service import to_session

        user = self._user() if signed_in else None
        store = to_session(user) if signed_in else {"authenticated": False}
        assert reconciled_auth_store("/plants", store, user) is no_update

    def test_logout_is_left_to_sign_out(self):
        """The /logout request may still carry the cookie `_sign_out` is
        clearing; writing it back would undo the logout."""
        from callbacks.auth import reconciled_auth_store

        assert reconciled_auth_store(LOGOUT_PATH, {"authenticated": False}, self._user()) is no_update

    def test_it_runs_on_a_cold_load(self):
        """A restart's drift appears on the very next full page load."""
        reconcile = next(
            c for c in app_module.app._callback_list
            if "auth-store.data" in c["output"]
            and len(c["inputs"]) == 2
            and {i["id"] for i in c["inputs"]} == {"url", "auth-store"}
        )
        assert reconcile["prevent_initial_call"] is False


class TestLoginPathWhenAlreadySignedIn:
    """`/login` is not a route (`parse_pathname` returns `unknown`), so a
    signed-in user asking for it fell through the router's whole dispatch
    chain to `not_found_panel("page")` — the same answer a typo'd URL gets.

    Signed out, every path renders the login form, `/login` included, which
    is what teaches an operator that `/login` is a real address. Answering
    that same address with "Not found" once they are signed in is the
    contradiction being closed here. The destination is `/`, not a named
    page: `landing_route_name` already decides where each role lands, and a
    second place deciding that is a second place for it to drift.
    """

    def test_a_signed_in_user_is_sent_to_their_landing_page(self):
        assert login_path_redirect(LOGIN_PATH, _SIGNED_IN) == "/"

    def test_a_signed_out_visitor_still_sees_the_form(self):
        """`no_update`, not `/`: the router renders the login form for this
        path already. Redirecting here would bounce a visitor off the very
        page they need."""
        assert login_path_redirect(LOGIN_PATH, None) is no_update

    @pytest.mark.parametrize("pathname", ["/", "/plants", "/admin/devices", "/logout", None])
    def test_every_other_route_is_untouched(self, pathname):
        assert login_path_redirect(pathname, _SIGNED_IN) is no_update

    def test_deep_links_still_survive_login(self):
        """The router substitutes the login form for whatever path was
        asked for rather than redirecting to `/login`, so a deep link is
        still there after signing in. Only the literal `/login` moves."""
        assert login_path_redirect("/plants/3/transformers/7", None) is no_update


class TestTheRedirectIsActuallyWired:
    """The helper above is pure, so it passes whether or not anything calls
    it. These check the app really registered it."""

    def _path_command(self):
        """The one callback driven by `url.pathname` alone that rewrites it.

        Every other `url.pathname` writer is a table-click handler driven by
        a cell, not by the URL."""
        matches = [
            c
            for c in app_module.app._callback_list
            if [i["id"] + "." + i["property"] for i in c["inputs"]] == ["url.pathname"]
            and "url.pathname" in str(c["output"])
        ]
        assert len(matches) == 1, f"expected exactly one, found {len(matches)}"
        return matches[0]

    def test_one_callback_owns_both_path_commands(self):
        """/logout and /login share a callback because Dash forces it: an
        `allow_duplicate` output id is a hash of the INPUTS alone
        (`dash/_utils.py:create_callback_id`), so a second callback writing
        `url.pathname` off this same lone input collides byte-for-byte.
        Splitting them again reintroduces "Duplicate callback outputs"."""
        assert "auth-store.data" in str(self._path_command()["output"])

    def test_it_fires_on_a_cold_load(self):
        """Both paths are typed or bookmarked, so they arrive as fresh page
        loads rather than as route changes. Dash records the source's
        "initial_duplicate" as False here; False is the meaning that
        matters — it fires on the first render."""
        assert self._path_command()["prevent_initial_call"] is False


class TestNoDuplicateCallbackOutputs:
    def test_every_output_id_is_unique(self):
        """A regression guard, not a style check. Dash raises "Duplicate
        callback outputs" at import when two `allow_duplicate` outputs hash
        to the same id, and because the hash covers only the inputs, that is
        easy to do by accident: any new callback writing an existing
        duplicate-output prop from the same single input trips it. The app
        serves a broken page rather than failing loudly in the suite."""
        seen = {}
        for callback in app_module.app._callback_list:
            for output_id in str(callback["output"]).strip(".").split("..."):
                if not output_id:
                    continue
                assert output_id not in seen, (
                    f"two callbacks both write {output_id!r}"
                )
                seen[output_id] = callback
