"""Administration summary cards for the Fleet Overview.

Presentation only. Every figure is read off one `AdminOverviewSummary` built
once per render by `admin_overview_service.get_admin_overview()` — this module
never queries, never counts, and never derives a figure the service did not
already state. It is the administration counterpart to `fleet_summary`, and
follows the same card language so the two rows read as one screen.

POPULATION. Everything here counts **Managed RTLs**. The Fleet Overview's own
"Devices" card counts **Monitoring Devices** — a different population (see
`admin_overview_service`). Both are 120 on development data, which is when a
swap is least likely to be noticed, so this module never uses the word
"device" and never renders the managed total as a bare headline. The total
appears once, inside the assignment card, attached to the word "RTLs":
"115 of 120 RTLs assigned". Two labelled figures, never one reconciled figure.
"""
from __future__ import annotations

from dash import html

from components.kpi_card import kpi_card
from services.admin_overview_service import (
    RECENT_REGISTRATION_WINDOW,
    AdminOverviewSummary,
)


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def assignment_summary(summary: AdminOverviewSummary) -> tuple[str, str]:
    """(value, secondary) for the RTL Assignment card.

    The headline names the state that needs action, the same rule the Data
    Health card applies to freshness — leading with the assigned count would
    make a fleet with five orphaned RTLs read as reassuring.

    An empty population is not a solved one. "All assigned" over zero managed
    RTLs would be literally true and completely misleading, so it gets its own
    wording, matching how `fleet_summary._health_summary` refuses to call an
    empty device population healthy.
    """
    if summary.total_devices == 0:
        return "No managed RTLs", "Nothing to assign"

    context = f"{summary.assigned_devices} of {summary.total_devices} RTLs assigned"

    if summary.unassigned_devices == 0:
        return "All assigned", context
    return f"{summary.unassigned_devices} unassigned", context


def technician_summary(summary: AdminOverviewSummary) -> tuple[str, str]:
    """(value, secondary) for the Active Technicians card.

    Zero gets its consequence spelled out rather than a label that reads the
    same as four: with no active technician, nothing on the unassigned list can
    be actioned at all, which is a different situation from merely being busy.
    """
    if summary.active_technicians == 0:
        return "0", "No technician can take an assignment"
    return str(summary.active_technicians), "Available for RTL assignment"


def recent_registration_summary(summary: AdminOverviewSummary) -> tuple[str, str]:
    """(value, secondary) for the Recently Registered card.

    The window wording is derived from `RECENT_REGISTRATION_WINDOW`, never
    written as a literal: it is a documented development value, and a card that
    hardcoded "7 days" would keep saying so after the service counted something
    else. The population is named for the same reason the total is — "2" alone
    invites the reader to scope it to whichever device count is nearest.
    """
    days = RECENT_REGISTRATION_WINDOW.days
    return (
        str(summary.recently_registered_devices),
        f"RTLs added in the last {days} {_plural(days, 'day')}",
    )


def admin_summary_cards(summary: AdminOverviewSummary) -> html.Div:
    """The administration card row, heading included.

    The heading is part of this component rather than the page layout on
    purpose. The callback leaves this slot empty when the summary cannot be
    read, and a heading living in the page would survive that — leaving an
    "Administration" title standing over nothing, which reads as a section
    that loaded and found zero of everything rather than one that failed.
    """
    return html.Div(
        className="admin-summary",
        children=[
            html.H2("Administration", className="admin-summary__heading"),
            html.Div(
                className="kpi-row kpi-row--admin",
                children=[
                    kpi_card("RTL Assignment", *assignment_summary(summary)),
                    kpi_card("Active Technicians", *technician_summary(summary)),
                    kpi_card(
                        "Recently Registered", *recent_registration_summary(summary)
                    ),
                ],
            ),
        ],
    )
