"""
Application entry point.

Callbacks stay thin: gather inputs -> call service -> format outputs.
No SQL, no raw string parsing, and no KPI math happens in this file.
"""
from __future__ import annotations

import dash
from dash import dcc, html

from callbacks import audit_log, auth, routing, listings, device, equipment_selector, navigation, device_admin, device_register, device_assign, device_manage, technician_devices, admin_assignments, programming_activity, user_admin, report_center, notifications, command_center, fleet_overview, rtl_detail, rtl_network, freshness_threshold, temperature_threshold, vibration_contract, rtl_programming_simulation
from components.app_shell import app_shell
from components.app_sidebar import app_sidebar_shell
from components.equipment_selector import equipment_selector_shell
from components import theme
from config.logging_config import configure_logging
from config.settings import flask_session

configure_logging()

#: APP-NAME-1: the browser tab title, and the same string the header brand
#: (components/app_header.py) and the login eyebrow (pages/login.py) show.
app = dash.Dash(__name__, suppress_callback_exceptions=True, title="RTL Monitoring")
server = app.server
# AUTH-HARDEN-1: signs the trusted server-side session `services.auth_service`
# uses to identify the logged-in user. Distinct from and more trustworthy than
# `auth-store`, the plain-JSON dcc.Store the browser can edit freely — see
# config.settings.FlaskSessionSettings for why an unset FLASK_SECRET_KEY is
# safe rather than a hole, and why it stops being safe once APP_ENV=production
# (AUTH-PROD-HARDEN-1).
server.secret_key = flask_session.secret_key

# AUTH-PROD-HARDEN-1: explicit session-cookie transport policy — see
# config.settings.FlaskSessionSettings for what each flag means and why.
#
# HTTPS enforcement itself is deliberately NOT handled here. This process is
# reached only through the deployment platform's own HTTPS edge (Railway:
# `railway.json` runs `gunicorn app:server` bound to a private-network port
# it assigns; there is no public listener this app owns to terminate TLS on
# or redirect from). Nothing in this codebase reads an `X-Forwarded-*` header
# to make a security decision, so there is no proxy chain here for the app to
# interpret, and no bounded hop count to trust one against — adding
# `ProxyFix`-style header trust without that would let a client spoof its own
# scheme. If that deployment topology ever changes (a proxy this app itself
# must trust), this is the boundary to revisit, not `SESSION_COOKIE_SECURE`.
server.config.update(
    SESSION_COOKIE_SECURE=flask_session.cookie_secure,
    SESSION_COOKIE_HTTPONLY=flask_session.cookie_httponly,
    SESSION_COOKIE_SAMESITE=flask_session.cookie_samesite,
)

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
    # ADR-025: the appearance class lives here, set by
    # callbacks.navigation from the browser-local theme store.
    id=theme.ROOT_ID,
    className=theme.root_class_name(None),
    children=[
        dcc.Location(id="url", refresh=False),
        # Remembered on this computer across sign-outs (ADR-025).
        dcc.Store(id=theme.STORE_ID, storage_type="local"),
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
# RTL-LIST-ROUTE-01: `/plants` -> `/rtls` for full page loads, answered by the
# server before Dash renders anything.
routing.register_legacy_redirects(server)
listings.register(app)
device.register(app)
equipment_selector.register(app)
navigation.register(app)
device_admin.register(app)
device_register.register(app)
device_assign.register(app)
device_manage.register(app)
technician_devices.register(app)
admin_assignments.register(app)
programming_activity.register(app)
user_admin.register(app)
audit_log.register(app)
report_center.register(app)
notifications.register(app)
command_center.register(app)
fleet_overview.register(app)
rtl_detail.register(app)
rtl_network.register(app)
freshness_threshold.register(app)
temperature_threshold.register(app)
vibration_contract.register(app)
# RTL-PROG-SIM-1: registers NOTHING unless the development simulator is
# explicitly enabled for a non-production environment — the module itself
# owns that decision, so there is one place it is made.
rtl_programming_simulation.register(app)

if __name__ == "__main__":
    from config.settings import dash_settings

    app.run(
        debug=dash_settings.debug,
        host=dash_settings.host,
        port=dash_settings.port,
    )
