"""
Application entry point.

Callbacks stay thin: gather inputs -> call service -> format outputs.
No SQL, no raw string parsing, and no KPI math happens in this file.
"""
from __future__ import annotations

import dash
from dash import dcc, html

from callbacks import auth, routing, listings, device, equipment_selector, navigation
from components.app_navigation import app_navigation_shell
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
# login-route-scoped: auth-store is memory-only, so every full page load
# (including an ordinary refresh) lands back on login regardless of route.
app.index_string = app.index_string.replace(
    "{%favicon%}",
    '{%favicon%}\n        <link rel="preload" as="image" '
    'href="/assets/login-powerplant-hero.jpg">',
)

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="auth-store", storage_type="memory", data={"authenticated": False}),
    dcc.Store(id="page-context", storage_type="memory", data={}),
    # Mounted globally and hidden on the login route rather than rendered per
    # page: its callbacks fire on every route, so their targets must always
    # exist. See docs/CODE_AUDIT.md finding 2.
    equipment_selector_shell(),
    # Same global-mount rule as the equipment selector, for the same reason.
    # Rendered above it: application navigation is the primary top-level
    # structure; the equipment jump tool is secondary to it.
    app_navigation_shell(),
    html.Div(id="page-content"),
])

auth.register(app)
routing.register(app)
listings.register(app)
device.register(app)
equipment_selector.register(app)
navigation.register(app)

if __name__ == "__main__":
    from config.settings import dash_settings

    app.run(
        debug=dash_settings.debug,
        host=dash_settings.host,
        port=dash_settings.port,
    )
