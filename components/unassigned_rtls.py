"""Unassigned RTLs panel — the actionable half of the Administration block.

Presentation only. Every value here is read off the one `AdminOverviewSummary`
the Fleet Overview callback already built for the cards above; this module
issues no query, counts nothing and derives no figure the service did not
already state. The RTL Assignment card says *how many* RTLs nobody is
responsible for — this panel says *which*, and hands each one to the
assignment workflow that already exists.

IT OWNS NO ASSIGNMENT WORKFLOW. The Assign action is a link into Device
Management's existing drawer (see `routes.device_assign_href`), not a second
implementation of technician loading, persistence or reassignment semantics.
Everything about actually making an assignment stays where it already lives.

POPULATION. These are **Managed RTLs** — administratively active devices,
whatever their transformer's status. An RTL under a decommissioned transformer
is still a unit nobody is responsible for, so it belongs on this list even
though the Fleet Overview's Monitoring Devices count excludes it. The panel
therefore says "RTLs" throughout; the only place the word "devices" appears is
the link to Device Management, which names a destination page rather than a
population.

A SAMPLE, NOT AN INVENTORY. `unassigned_rows` is capped by the service. The
summary line states the real total and says when the list beneath it is
shorter, because five rows presented as the whole problem is the misreading
this panel invites.
"""
from __future__ import annotations

from dash import dcc, html

from routes import ADMIN_DEVICES_PATH, device_assign_href
from services.admin_overview_service import AdminOverviewSummary

#: Column labels, in render order. `RTL UID` is the client's business
#: identifier for a logger and maps to `device_code`; the internal `device_id`
#: is a hierarchy path and never appears as text an operator is asked to read.
UNASSIGNED_COLUMNS: tuple[str, ...] = (
    "RTL UID",
    "Plant",
    "Transformer",
    "Status",
    "Action",
)

#: What a fully assigned fleet says. Deliberately neutral: zero unassigned
#: RTLs is a good outcome, not an empty result and not a failure to load.
EMPTY_MESSAGE = "All managed RTLs are currently assigned."

_ASSIGN_LABEL = "Assign"
_VIEW_ALL_LABEL = "View all devices"


def _status_label(status: str) -> str:
    """Administrative status, title-cased. Never a data-freshness judgement.

    Blank falls back to an em dash rather than an empty cell, so a missing
    status reads as unknown instead of as a rendering fault.
    """
    return status.capitalize() if status else "—"


def unassigned_summary_text(summary: AdminOverviewSummary) -> str:
    """The one line under the heading, from the service's own count.

    The count is `unassigned_devices`, never `len(unassigned_rows)`: the rows
    are a capped sample, and counting them would report five unassigned RTLs
    on a fleet that has twenty-four. When the sample is shorter than the total,
    the line says so.
    """
    total = summary.unassigned_devices
    if total == 0:
        return EMPTY_MESSAGE

    noun = "RTL requires" if total == 1 else "RTLs require"
    text = f"{total} {noun} assignment"

    shown = len(summary.unassigned_rows)
    if shown and shown < total:
        text = f"{text} · showing the first {shown}"
    return text


def _row(row) -> html.Tr:
    """One unassigned RTL. `row` is an `AdminDeviceRow`.

    The same row shape the Device Management table consumes, so the two
    screens cannot drift apart on what a device's plant or transformer is.
    """
    return html.Tr(
        className="unassigned-rtls__row",
        children=[
            html.Td(row.device_code, className="unassigned-rtls__cell unassigned-rtls__cell--uid"),
            html.Td(row.plant_name, className="unassigned-rtls__cell"),
            html.Td(row.transformer_code, className="unassigned-rtls__cell"),
            html.Td(
                _status_label(row.status),
                className="unassigned-rtls__cell unassigned-rtls__cell--status",
            ),
            html.Td(
                dcc.Link(
                    _ASSIGN_LABEL,
                    href=device_assign_href(row.device_id),
                    className="unassigned-rtls__assign",
                ),
                className="unassigned-rtls__cell unassigned-rtls__cell--action",
            ),
        ],
    )


def _table(rows) -> html.Div:
    """A plain HTML table, not a `dash_table.DataTable`.

    The rows arrive already built, already limited and already ordered; a
    DataTable would add sorting, paging and a second component id to a page
    that has one exception sample of at most five rows. The wrapper carries the
    horizontal-overflow guard so a narrow viewport scrolls the table, never
    the page.
    """
    return html.Div(
        className="unassigned-rtls__table-wrap",
        children=[
            html.Table(
                className="unassigned-rtls__table",
                children=[
                    html.Thead(
                        html.Tr(
                            [
                                html.Th(label, className="unassigned-rtls__th")
                                for label in UNASSIGNED_COLUMNS
                            ]
                        )
                    ),
                    html.Tbody([_row(r) for r in rows]),
                ],
            )
        ],
    )


def unassigned_rtl_panel(summary: AdminOverviewSummary) -> html.Div:
    """The exception list under the Administration cards.

    With no rows to show, the table is omitted entirely rather than rendered
    empty: a header row over nothing looks like a list that failed to load.
    The summary line carries the outcome either way.

    "View all devices" always renders, including on an empty panel — the route
    out of an exception list should not depend on the list having anything in
    it.
    """
    rows = summary.unassigned_rows
    children: list = [
        html.H3("Unassigned RTLs", className="unassigned-rtls__title"),
        html.P(unassigned_summary_text(summary), className="unassigned-rtls__summary"),
    ]
    if rows:
        children.append(_table(rows))
    children.append(
        dcc.Link(
            _VIEW_ALL_LABEL,
            href=ADMIN_DEVICES_PATH,
            className="unassigned-rtls__all",
        )
    )
    return html.Div(className="unassigned-rtls", children=children)
