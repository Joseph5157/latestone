"""
Application entry point.

Callbacks stay thin: gather inputs -> call service -> format outputs.
No SQL, no raw string parsing, and no KPI math happens in this file.
"""
from __future__ import annotations

import dash
from dash import dcc, html

from callbacks import auth, routing, listings, device, equipment_selector
from components.equipment_selector import equipment_selector_shell
from config.logging_config import configure_logging

configure_logging()

app = dash.Dash(__name__, suppress_callback_exceptions=True, title="Power Plant Monitoring")
server = app.server

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="auth-store", storage_type="memory", data={"authenticated": False}),
    dcc.Store(id="page-context", storage_type="memory", data={}),
    # Mounted globally and hidden on the login route rather than rendered per
    # page: its callbacks fire on every route, so their targets must always
    # exist. See docs/CODE_AUDIT.md finding 2.
    equipment_selector_shell(),
    html.Div(id="page-content"),
])

auth.register(app)
routing.register(app)
listings.register(app)
device.register(app)
equipment_selector.register(app)

if __name__ == "__main__":
    from config.settings import dash_settings

    app.run(
        debug=dash_settings.debug,
        host=dash_settings.host,
        port=dash_settings.port,
    )
