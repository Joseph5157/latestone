"""Command Center page — layout only, no queries.

Phase 3+4 (foundation and shell, docs/context/CC1_ROADMAP.md): the six
named panel slots exist and render an honest "not built yet" state; only
the header's scope indicator carries real data, filled in post-mount by
callbacks/command_center.py (matches pages/report_center.py's and
pages/notifications.py's own layout-then-callback convention). Fresh
presentation throughout — no imports from Fleet Overview components
(ADR-008).
"""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.command_center.primitives import panel_not_yet_built

#: (component id, panel title) — the shell's six named slots
#: (docs/context/CC1_ROADMAP.md Phase 4). Content lands Phase 5 onward.
_PANEL_SLOTS: tuple[tuple[str, str], ...] = (
    ("command-center-situation-summary", "Situation Summary"),
    ("command-center-exception-intelligence", "Exception Intelligence"),
    ("command-center-recent-events", "Recent Operational Events"),
    ("command-center-affected-locations", "Affected Locations"),
    ("command-center-selected-location", "Selected Location / Transformer Concentration"),
    ("command-center-priority-investigation", "Priority Investigation"),
)


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--command-center",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("Command Center", None)]),
            ),
            html.H1("Command Center"),
            html.P(
                "Exception-first operational view across the monitored fleet.",
                className="page__subtitle",
            ),
            html.Div(
                id="command-center-scope-indicator",
                className="command-center__scope-indicator",
            ),
            html.Div(id="command-center-error"),
            html.Div(
                className="command-center__panels",
                children=[
                    html.Div(id=slot_id, children=[panel_not_yet_built(title)])
                    for slot_id, title in _PANEL_SLOTS
                ],
            ),
        ],
    )
