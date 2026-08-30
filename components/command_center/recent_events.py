"""Recent Operational Events — what just happened? (CC-1 Phase 9)

The fourth question in the Command Center's investigation chain:

    How much?  ->  Where?  ->  Which transformer?  ->  What just happened?

Persisted events only. Every row is an OCCURRENCE — "this happened at
14:02" — never a current state. That distinction is the reason the Phase 6
card beside it still reads `Unavailable`: a recent Power Down event and an
RTL currently in Critical are different claims, and only the first has
evidence behind it (ADR-001 — no closure/resolve contract exists).

Which is also why this panel has no Acknowledge, Clear, Resolve, Silence or
Escalate control. None of them has a persisted workflow, and a button that
looks like it acknowledges an alarm and does nothing is worse than no
button. The one action here is to go and look: "Open asset →".

Renders what the service decided. It does not classify event types, order
rows, or format times — `services/command_center_service.py` owns all three,
so this panel and the Notification Center cannot come to mean different
things by the same persisted row.
"""
from __future__ import annotations

from dash import dcc, html

from components.command_center.primitives import cc_card

#: The deeper destination. Command Center holds recent context; the
#: Notification Center is where an operator investigates the full history.
NOTIFICATIONS_PATH = "/notifications"

#: Rows shown before the list becomes a scroll region. Same rule as Affected
#: Locations: bound the panel's HEIGHT, never its DATA. A "+12 more" cap
#: would hide exactly the recent activity this panel exists to surface, and
#: the fetch is already bounded at the service (RECENT_EVENT_ROWS) — capping
#: twice would just be capping arbitrarily.
SCROLL_AFTER_ROWS = 5

#: Says only what the database supports. Deliberately NOT "No problems" or
#: "System healthy": an empty event log is not a clean bill of health, it is
#: the absence of recorded events, and the two are not the same claim.
EMPTY_TEXT = "No recent operational events are available."

#: Distinct from the above, and never collapsed into it. "Nothing happened"
#: and "we could not look" are different facts (ADR-008's events failure
#: boundary), and an operator acting on the first when the second is true is
#: acting on a silence that was never verified.
ERROR_TEXT = "Recent operational events could not be loaded."


def _event_row(event) -> html.Li:
    """One event. Severity and time on top, then what it was and what it
    happened to, then the way in."""
    head = html.Div(
        className="command-center__event-head",
        children=[
            html.Div(
                className=(
                    "command-center__event-category "
                    f"command-center__tone--{event.tone}"
                ),
                children=[
                    html.Span(
                        className="command-center__event-marker",
                        **{"aria-hidden": "true"},
                    ),
                    # The marker is decoration; this label is the meaning.
                    # Colour never carries it alone.
                    html.Span(
                        event.tone_label,
                        className="command-center__event-severity",
                    ),
                ],
            ),
            # The full timestamp rides along as a title: the visible label is
            # compact for scanning, and the exact moment stays one hover away
            # rather than being lost.
            html.Time(
                event.time_label,
                className="command-center__event-time",
                title=event.time_title,
            ),
        ],
    )

    # What it was, and what it happened to — one line. Two would double the
    # row height for a panel that has a fixed vertical budget in the cockpit.
    title = html.Div(
        className="command-center__event-title",
        children=[
            html.Span(event.display_label, className="command-center__event-label"),
            html.Span(event.asset_label, className="command-center__event-asset"),
        ],
    )

    foot_children: list = []
    if event.context_label:
        foot_children.append(
            html.Span(event.context_label, className="command-center__event-context")
        )
    if event.asset_href:
        # Present only where the asset actually resolved. A greyed-out
        # control would still be claiming the asset exists (ADR-008).
        foot_children.append(
            dcc.Link(
                "Open asset →",
                href=event.asset_href,
                className="command-center__event-action",
                title=f"Open {event.asset_label}",
            )
        )

    body: list = [title]
    if foot_children:
        body.append(
            html.Div(className="command-center__event-foot", children=foot_children)
        )
    if event.detail:
        # Only when there is one. An empty line would reserve space for a
        # value that does not exist, which reads as a failed load.
        body.append(
            html.P(event.detail, className="command-center__event-detail")
        )

    return html.Li(
        className="command-center__event-row",
        children=[head, html.Div(className="command-center__event-body", children=body)],
    )


def _scrollable(listing) -> html.Div:
    """Bound the list's height, keeping every row reachable.

    Mirrors the Affected Locations region deliberately, down to the string
    `tabIndex="0"` — Dash types that prop as a STRING, and an int renders
    fine while logging an invalid-prop error on every callback fire.
    """
    return html.Div(
        className="command-center__event-scroll",
        tabIndex="0",
        role="region",
        **{"aria-label": "Recent operational events, scrollable list"},
        children=[listing],
    )


def recent_events_card(snapshot) -> html.Section:
    """The Recent Operational Events card.

    Three outcomes, kept apart: rows, nothing recorded, and a read that
    failed. The third is not the second — see ERROR_TEXT.
    """
    if snapshot.recent_events_failed:
        # No "View all" here: a link into the full history would promise
        # content this panel just failed to read.
        return cc_card(
            "Recent Operational Events",
            [html.P(ERROR_TEXT, className="command-center__empty-note")],
            subtitle="Persisted device events",
        )

    events = snapshot.recent_events
    if not events:
        return cc_card(
            "Recent Operational Events",
            [html.P(EMPTY_TEXT, className="command-center__empty-note")],
            subtitle="Persisted device events",
        )

    listing = html.Ol(
        className="command-center__events",
        children=[_event_row(event) for event in events],
    )
    body: list = [
        _scrollable(listing) if len(events) > SCROLL_AFTER_ROWS else listing,
        dcc.Link(
            "View all notifications →",
            href=NOTIFICATIONS_PATH,
            className="command-center__view-all",
        ),
    ]
    return cc_card(
        "Recent Operational Events",
        body,
        # Names the order and the clock once, so no row has to repeat "UTC".
        subtitle="Newest first · times in UTC",
    )
