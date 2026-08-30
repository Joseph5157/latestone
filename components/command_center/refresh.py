"""Command Center auto-refresh — the interval, and its honest status line
(CC-1 Phase 12, ADR-005).

POLLING, NOT A FEED. The words matter and are constrained by ADR-005: this
page asks the database again every N seconds. It is never "live",
"streaming" or "pushed", because those imply a delivery guarantee nothing
here provides — if the poll fails, nothing arrives and nothing announces
itself. Saying "live" over a failed poll is how a stale screen becomes a
trusted one.

The status line therefore states three separate facts rather than one
reassuring one:

    Auto refresh · On          the mechanism is running
    Last updated · 14:31:07    when the data on screen was fetched
    Refresh failed · …         the last attempt did not land

`Last updated` is the time of the last SUCCESSFUL snapshot, never of the
last attempt. That is the whole point of keeping it separate: an operator
reading a screen needs to know how old what they are reading is, and a
timestamp that advanced on a failed poll would say the opposite of the
truth at exactly the moment it mattered.

THE INTERVAL IS PAGE-OWNED. It is mounted in the Command Center layout, so
navigating away destroys it — there is no app-wide interval, and adding one
would change Fleet Overview's deliberately-tested absence of refresh to
serve a page that does not need it to (ADR-005).
"""
from __future__ import annotations

from datetime import datetime

from dash import dcc, html

from config.settings import monitoring

INTERVAL_ID = "command-center-refresh-interval"
STORE_ID = "command-center-refresh-store"
STATUS_ID = "command-center-refresh-status"
MANUAL_ID = "command-center-refresh-now"

#: The mechanism, stated plainly. Not "Live" (ADR-005).
AUTO_REFRESH_ON = "Auto refresh · On"

#: A failed attempt over data that IS still true. Deliberately not "No Data"
#: and not "Unavailable": both are evaluated states this application derives
#: from readings (ADR-002/ADR-001), and borrowing either word would report a
#: fact about the fleet when what happened was a fact about the query.
REFRESH_FAILED = "Refresh failed · showing last successful data"

#: Before any snapshot has ever landed. Not a dash and not "just now" — the
#: absence of a fetch is not a fetch that returned nothing.
NEVER_UPDATED = "Last updated · not yet"

#: Times are UTC everywhere in this application (the hierarchy spans ~30
#: countries; an unlabelled instant is ambiguous). Seconds are shown because
#: the whole question this line answers is "how old is this".
TIME_FORMAT = "%H:%M:%S"


def interval_ms() -> int:
    """The cadence, in milliseconds, from the ONE configured source.

    `monitoring.refresh_interval_seconds` (`UI_REFRESH_INTERVAL_SECONDS`) is
    the same setting the device dashboard's interval reads. A literal here
    would silently diverge the first time an operator retuned it.
    """
    return monitoring.refresh_interval_seconds * 1000


def refresh_interval() -> dcc.Interval:
    return dcc.Interval(id=INTERVAL_ID, interval=interval_ms())


def refresh_store() -> dcc.Store:
    """What the refresh cycle remembers between ticks.

    Deliberately NOT the snapshot. Retaining the last good DATA is done by
    leaving the rendered panels alone (`no_update`), so nothing large is
    serialised into the browser and back on every poll. What must be
    remembered is only the two facts the DOM cannot answer: when the last
    SUCCESSFUL fetch happened, and whether the most recent attempt failed.

    `storage_type="memory"`, not session: this describes the state of one
    open cockpit, and a refresh of the browser starts a genuinely new first
    load whose failure is the initial-load case, not a stale-data case.
    """
    return dcc.Store(
        id=STORE_ID,
        storage_type="memory",
        data={"last_success_at": None, "failed": False},
    )


def format_last_updated(moment: datetime | None) -> str:
    if moment is None:
        return NEVER_UPDATED
    return f"Last updated · {moment.strftime(TIME_FORMAT)} UTC"


def refresh_status(last_success_at: datetime | None, *, failed: bool) -> html.Div:
    """The status line beside the title.

    Three facts, never merged into one mood. A failure does not remove the
    `Last updated` time — an operator deciding whether to trust the screen
    needs to know how old it is, and that is exactly when the number gets
    withheld if the two are collapsed into a single indicator.
    """
    children: list = [
        html.Span(AUTO_REFRESH_ON, className="command-center__refresh-mode"),
        html.Span(
            format_last_updated(last_success_at),
            className="command-center__refresh-time",
        ),
    ]
    if failed:
        children.append(
            html.Span(
                REFRESH_FAILED,
                className="command-center__refresh-failed",
                # Announced when it appears: an operator watching the panels
                # would otherwise never learn the numbers stopped advancing.
                role="status",
            )
        )
    return html.Div(className="command-center__refresh", children=children)


def manual_refresh_button() -> html.Button:
    """Optional per ADR-005, and offered because the alternative to a manual
    refresh is an operator reloading the whole page — which throws away the
    selected Plant and the chosen appearance to get something the interval
    was already going to do.
    """
    return html.Button(
        "Refresh now",
        id=MANUAL_ID,
        className="command-center__refresh-now",
        type="button",
        n_clicks=0,
    )
