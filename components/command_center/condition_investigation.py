"""Persisted-condition occurrence investigation for Command Center."""
from __future__ import annotations

from dash import dcc, html

from components.command_center.primitives import cc_card

PANEL_ID = "command-center-condition-investigation"
SCROLL_AFTER_ROWS = 5


def _row(event) -> html.Li:
    identity = [
        html.Span(event.asset_label, className="command-center__priority-device")
    ]
    if event.context_label:
        identity.append(
            html.Span(
                event.context_label,
                className="command-center__priority-context",
            )
        )

    detail = event.detail or "No battery reading was included with this occurrence."
    return html.Li(
        className="command-center__priority-row",
        children=[
            html.Div(
                className="command-center__priority-head",
                children=[
                    html.Span(
                        className=(
                            "command-center__tone-dot "
                            f"command-center__tone--{event.tone}"
                        ),
                        **{"aria-hidden": "true"},
                    ),
                    html.Span(
                        event.display_label,
                        className=(
                            "command-center__priority-badge "
                            f"command-center__condition-badge--{event.tone}"
                        ),
                    ),
                    html.Time(
                        event.time_label,
                        dateTime=event.occurred_at.isoformat(),
                        title=event.time_title,
                        className="command-center__condition-time",
                    ),
                ],
            ),
            html.Div(
                className="command-center__priority-identity",
                children=identity,
            ),
            html.P(
                f"Latest recorded occurrence · {detail}",
                className="command-center__priority-reason",
            ),
            dcc.Link(
                "Open RTL →",
                href=event.asset_href,
                className="command-center__priority-action",
                title=f"Open RTL {event.asset_label}",
            ),
        ],
    )


def condition_investigation_card(label: str, rows) -> html.Section:
    """Render matching RTLs without implying the occurrence is still active."""
    if not rows:
        body = [
            html.P(
                f"No {label} occurrences were found for RTLs in your current access scope.",
                className="command-center__empty-note",
            )
        ]
    else:
        listing = html.Ol(
            className="command-center__priorities",
            children=[_row(row) for row in rows],
        )
        body = [
            html.P(
                f"{len(rows)} affected RTL{'s' if len(rows) != 1 else ''}",
                className="command-center__priority-summary",
            ),
            (
                html.Div(
                    listing,
                    className="command-center__priority-scroll",
                    tabIndex="0",
                    role="region",
                    **{"aria-label": f"{label} affected RTLs"},
                )
                if len(rows) > SCROLL_AFTER_ROWS
                else listing
            ),
        ]
    return cc_card(
        f"Affected RTLs · {label}",
        body,
        subtitle="Latest persisted occurrence per RTL · times in UTC · not current-state status",
    )


def investigation_prompt() -> html.Section:
    return cc_card(
        "Affected RTLs",
        [
            html.P(
                "Select Power Down or Battery Low to view matching RTL occurrences.",
                className="command-center__empty-note",
            )
        ],
        subtitle="Scoped event investigation",
    )
