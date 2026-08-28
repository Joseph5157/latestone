"""
Application entry point.

Callbacks stay thin: gather inputs -> call service -> format outputs.
No SQL, no raw string parsing, and no KPI math happens in this file.
"""
from __future__ import annotations

import dash
from dash import dcc, html

from callbacks import auth, routing, listings, device, equipment_selector, navigation, device_admin, device_register, device_assign, device_manage, user_admin, report_center, notifications
from components.app_shell import app_shell
from components.app_sidebar import app_sidebar_shell
from components.equipment_selector import equipment_selector_shell
from config.logging_config import configure_logging

configure_logging()

app = dash.Dash(__name__, suppress_callback_exceptions=True, title="Power Plant Monitoring")
server = app.server

# The login card is CSS/JS-rendered, so the browser doesn't discover the hero
# background-image until Dash's client bundle has parsed and rendered
# `.login-page` — well after the form itself is already visible (measured:
# ~400ms in, on top of whatever the image weighs). A `<link rel=preload>`
# lets the browser start fetching the image in parallel with the JS bundle
# instead of only after it, closing that gap. Unconditional rather than
# login-route-scoped: the preload is cheap and the login page is still the
# first paint of any new session. A signed-in refresh now restores its route
# instead of landing on login, so the hint is occasionally spent on an image
# that render does not use.
app.index_string = app.index_string.replace(
    "{%favicon%}",
    '{%favicon%}\n        <link rel="preload" as="image" '
    'href="/assets/login-powerplant-hero.jpg">',
)

# className="app-root": a one-column flex ancestor of [app shell] so the
# shell can claim the full viewport via CSS flex sizing — see .app-root in
# assets/app.css.
app.layout = html.Div(
    className="app-root",
    children=[
        dcc.Location(id="url", refresh=False),
        # Session-scoped, not memory: a memory store is discarded by every full
        # page load, so an ordinary refresh signed the user out. Session
        # storage survives a reload and still ends with the tab. Signing out
        # is therefore a deliberate action now — see callbacks.auth.sign_out_outputs.
        dcc.Store(id="auth-store", storage_type="session", data={"authenticated": False}),
        dcc.Store(id="page-context", storage_type="memory", data={}),
        # The sidebar is the primary application navigation (replaces the former
        # horizontal app-navigation bar). It, page-content and the utility column
        # are wrapped in the app-shell so the content region's width — and
        # therefore where .page/.page--monitoring center themselves — reserves
        # the sidebar's and utility column's width without any page needing to
        # know either exists.
        app_shell(
            app_sidebar_shell(),
            html.Div(id="page-content"),
            utility=html.Div(
                className="app-shell__utility-inner",
                children=[
                    # Layer 1: structurally reserved primary page-action slot.
                    # No current page has a valid primary action, so it stays
                    # empty (CSS collapses an empty slot to nothing) rather
                    # than render invented behaviour.
                    html.Div(id="page-action-area", className="page-action-area"),
                    # Mounted globally and hidden on the login route rather than
                    # rendered per page: its callbacks fire on every route, so
                    # their targets must always exist. See
                    # docs/CODE_AUDIT.md finding 2.
                    equipment_selector_shell(),
                ],
            ),
        ),
    ],
)

auth.register(app)
routing.register(app)
listings.register(app)
device.register(app)
equipment_selector.register(app)
navigation.register(app)
device_admin.register(app)
device_register.register(app)
device_assign.register(app)
device_manage.register(app)
user_admin.register(app)
report_center.register(app)
notifications.register(app)

if __name__ == "__main__":
    from config.settings import dash_settings

    app.run(
        debug=dash_settings.debug,
        host=dash_settings.host,
        port=dash_settings.port,
    )
