"""Application-shell / content-region wrapper.

A flex row of [sidebar, content region, utility column] — page-content is
never a direct child of the layout root. `.app-shell__content` reserves the
sidebar and optional utility column before pages are sized. Fleet Overview
fills that region with its existing gutters; other pages retain their
reading/monitoring max-widths and `margin: 0 auto` centering. These width
policies live in the shell CSS, not in page rendering or callbacks.

Deliberately not solved with a global `margin-left` on `.page`: that would
require every current and future page to carry a sidebar-shaped assumption.
The shell owns the layout split; pages stay ignorant of the sidebar.

`utility` (Layer 1 — Global Shell) is the right-hand docked column: the
cross-plant equipment selector lives there now instead of the former
full-width bar above the shell. It stays optional and defaults to nothing
rendered, so a caller with no utility content is unaffected.
"""
from __future__ import annotations

from dash import dcc, html

CONTENT_ID = "app-shell-content"
UTILITY_ID = "app-shell-utility"
UTILITY_BODY_ID = "app-shell-utility-body"
UTILITY_TOGGLE_ID = "app-shell-utility-toggle"
UTILITY_STORE_ID = "app-shell-utility-collapse"


def app_shell(sidebar, content, utility=None) -> html.Div:
    children = [
        sidebar,
        html.Div(id=CONTENT_ID, className="app-shell__content", children=[content]),
    ]
    if utility is not None:
        children.append(
            html.Div(
                id=UTILITY_ID,
                className="app-shell__utility",
                children=[
                    # Global and independent of the left sidebar. Keep the
                    # preference across route changes and reloads in this tab.
                    dcc.Store(
                        id=UTILITY_STORE_ID,
                        storage_type="session",
                        data={"collapsed": False},
                    ),
                    html.Button(
                        html.Span(
                            className="app-shell__utility-toggle-icon",
                            **{"aria-hidden": "true"},
                        ),
                        id=UTILITY_TOGGLE_ID,
                        className="app-shell__utility-toggle",
                        type="button",
                        n_clicks=0,
                        title="Collapse Asset Navigator",
                        **{
                            "aria-label": "Collapse Asset Navigator",
                            "aria-expanded": "true",
                            "aria-controls": UTILITY_BODY_ID,
                        },
                    ),
                    # Hidden, never unmounted: dropdown state and callback
                    # targets survive every collapse/expand cycle.
                    html.Div(id=UTILITY_BODY_ID, hidden=False, children=[utility]),
                ],
            )
        )
    return html.Div(className="app-shell", children=children)
