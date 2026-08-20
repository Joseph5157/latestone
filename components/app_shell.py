"""Application-shell / content-region wrapper.

The one structural change this phase makes to the page-rendering path: a
flex row of [sidebar, content region] replaces page-content being a direct
child of the layout root. Page width behaviour (`.page` / `.page--monitoring`
and their `margin: 0 auto` centering) is untouched — those rules centre
within whatever block contains them, and that block is now `.app-shell__content`
(width = viewport minus the sidebar) instead of the full viewport. No page
module, and no per-page CSS, changes for this.

Deliberately not solved with a global `margin-left` on `.page`: that would
require every current and future page to carry a sidebar-shaped assumption.
The shell owns the layout split; pages stay ignorant of the sidebar.
"""
from __future__ import annotations

from dash import html

CONTENT_ID = "app-shell-content"


def app_shell(sidebar, content) -> html.Div:
    return html.Div(
        className="app-shell",
        children=[
            sidebar,
            html.Div(id=CONTENT_ID, className="app-shell__content", children=[content]),
        ],
    )
