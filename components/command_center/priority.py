"""Priority Investigation — the ranked RTL list (CC-1 Phase 10, ADR-009).

The last panel in the investigation chain, and the only one that names
individual devices. Everything it renders was decided by
`services/command_center_service.py`: the order, the badge word, the
hierarchy label, the age sentence and the link. Nothing here sorts, counts
ages, or looks at `FleetHealth` — that is what keeps one freshness
interpretation in Command Center instead of two that pass their own tests
separately (AGENTS.md rule 8).

Vocabulary discipline, same as the Situation Summary's: these rows describe
DATA DELIVERY. `Stale` and `No Data` are the whole vocabulary. `Critical`
and `Warning` name already-classified EVENT types and belong to the
Electrical Conditions card — a blind RTL is not "Critical", and giving it
that word is how a freshness panel turns into the alarm queue ADR-009
exists to prevent.
"""
from __future__ import annotations

from dash import dcc, html

from components.command_center.primitives import cc_card

#: Names the investigation population without turning either constituent
#: freshness state into a headline. ADR-009 still owns the service order.
SUBTITLE = "Freshness exceptions requiring investigation"

#: A calm fleet. Deliberately not "System healthy" / "No problems" / "All
#: clear": freshness establishes that data is arriving, which is not the
#: same claim as equipment being well (ADR-001/ADR-002). It states the
#: absence of an investigation target and stops there.
NOTHING_TO_INVESTIGATE = "No RTLs currently require investigation."

#: Structurally different from the line above. "Nothing to watch" and
#: "nothing wrong" are different facts, and a technician with no assignments
#: must not be told the fleet is fine.
NOTHING_MONITORED = "No monitored RTLs in your current access scope."

#: Rows shown before the list becomes a scroll region. The service already
#: caps at PRIORITY_ROWS, so this only decides when the cell scrolls rather
#: than how much data exists — the same split Recent Events uses.
SCROLL_AFTER_ROWS = 5


def _summary_text(shown: int, total: int) -> str:
    """How many of the population these rows are.

    Says "Top N of M" only when the cap actually hid something. Saying it
    when N == M would imply a remainder that does not exist.
    """
    noun = "RTL" if total == 1 else "RTLs"
    if shown < total:
        return f"Top {shown} of {total} {noun} requiring attention"
    return f"{total} {noun} requiring attention"


def _priority_row(row) -> html.Li:
    """One RTL, as the operator reads it.

    Order on screen mirrors the question being answered: what state, which
    device, where it is, why it is here, and the way in.
    """
    head = html.Div(
        className="command-center__priority-head",
        children=[
            html.Span(
                className=(
                    "command-center__tone-dot "
                    f"command-center__tone--{row.tone}"
                )
            ),
            # The word beside the colour, never the colour alone.
            html.Span(
                row.badge_label,
                className=(
                    "command-center__priority-badge "
                    f"command-center__priority-badge--{row.tone}"
                ),
            ),
        ],
    )

    identity: list = [
        html.Span(row.device_label, className="command-center__priority-device")
    ]
    if row.context_label:
        # Only when the label resolved. The device itself is never dropped —
        # it is by definition one the panel just said to open first.
        identity.append(
            html.Span(
                row.context_label, className="command-center__priority-context"
            )
        )

    return html.Li(
        className="command-center__priority-row",
        children=[
            head,
            html.Div(className="command-center__priority-identity", children=identity),
            # The service built this sentence, including whether an age
            # belongs in it at all (ADR-009 D3 — a NO_DATA RTL has no age to
            # state, and this panel has no way to invent one).
            html.P(row.reason, className="command-center__priority-reason"),
            dcc.Link(
                "Open asset →",
                href=row.asset_href,
                className="command-center__priority-action",
                title=f"Open {row.device_label}",
            ),
        ],
    )


def _scrollable(listing) -> html.Div:
    """Bound the height, keep every row reachable.

    `tabIndex` is the STRING "0" deliberately: Dash types the prop as a
    string, and an int renders fine while logging an invalid-prop error on
    every callback fire (the same note Recent Events carries).
    """
    return html.Div(
        className="command-center__priority-scroll",
        tabIndex="0",
        role="region",
        **{"aria-label": "Priority investigation list, scrollable"},
        children=[listing],
    )


def priority_investigation_card(snapshot) -> html.Section:
    """The Priority Investigation card.

    Three outcomes, kept apart: ranked rows, a calm fleet, and a scope with
    nothing in it. The last two are different sentences on purpose.

    No footer link (ADR-009 D5). The only deeper destination that exists is
    `/command-center/locations`, which is the ranked PLANT list — linking it
    here would promise a population this panel does not show.
    """
    rows = snapshot.priority_rtls

    if not rows:
        message = (
            NOTHING_TO_INVESTIGATE
            if snapshot.has_monitored_devices
            else NOTHING_MONITORED
        )
        return cc_card(
            "Priority Investigation",
            [html.P(message, className="command-center__empty-note")],
            subtitle=SUBTITLE,
        )

    listing = html.Ol(
        className="command-center__priorities",
        children=[_priority_row(row) for row in rows],
    )
    return cc_card(
        "Priority Investigation",
        [
            html.P(
                _summary_text(len(rows), snapshot.priority_total),
                className="command-center__priority-summary",
            ),
            _scrollable(listing) if len(rows) > SCROLL_AFTER_ROWS else listing,
        ],
        subtitle=SUBTITLE,
    )
