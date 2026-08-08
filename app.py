"""
Application entry point.

Callbacks stay thin: gather inputs -> call service -> format outputs.
No SQL, no raw string parsing, and no KPI math happens in this file.
"""
from __future__ import annotations

import dash
from dash import dcc, html

from callbacks import auth, routing, listings, device

app = dash.Dash(__name__, suppress_callback_exceptions=True, title="Power Plant Monitoring")
server = app.server

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="auth-store", storage_type="memory", data={"authenticated": False}),
    dcc.Store(id="page-context", storage_type="memory", data={}),
    html.Div(id="page-content"),
])

auth.register(app)
routing.register(app)
listings.register(app)
device.register(app)

if __name__ == "__main__":
    from config.settings import dash_settings

    app.run(
        debug=dash_settings.debug,
        host=dash_settings.host,
        port=dash_settings.port,
    )
