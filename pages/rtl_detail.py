"""RTL Details - layout only, no queries (RTL-UID-DETAIL-01).

The canonical real-client RTL detail page, at ``/rtls/<uid>``. Its identity is
the client RTL UID from ``dbo.device_list``; no synthetic application
``device_id`` is involved, and none is inferred.

Filled once per page load by ``callbacks/rtl_detail.py``, plus once per
history-window change. No polling: refreshing is a full reload of this route.

Deliberately not reused from the synthetic device dashboard: the metric
selector, the eight-metric snapshot strip, the readings table, the freshness
badge and the operations drawer. Temperature is the only confirmed continuous
telemetry in this source, and every one of those carries a claim it cannot
support.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from routes import FLEET_OVERVIEW_PATH
from services.rtl_detail_service import DEFAULT_WINDOW_KEY, HISTORY_WINDOWS

BODY_ID = "rtl-detail-body"
CONTEXT_ID = "rtl-detail-context"
HISTORY_ID = "rtl-detail-history"
HISTORY_SECTION_ID = "rtl-detail-history-section"
WINDOW_ID = "rtl-detail-window"
ERROR_ID = "rtl-detail-error"

#: The history section is hidden wholesale when there is no RTL to have a
#: history — an unregistered UID, or an unreachable source. The window control
#: must stay MOUNTED (it is an Input of the page's own callback, so rendering
#: it conditionally would make the callback recreate its own trigger), which
#: is why this is a style toggle rather than conditional children.
HIDDEN_STYLE = {"display": "none"}
VISIBLE_STYLE: dict = {}


def layout(device_uid: int) -> html.Div:
    return html.Div(
        className="page page--monitoring page--rtl-detail",
        children=[
            app_header(breadcrumb_children=breadcrumb([
                ("Registered RTLs", FLEET_OVERVIEW_PATH),
                (f"RTL {device_uid}", None),
            ])),
            html.H1("RTL Details"),
            html.P(f"RTL UID {device_uid}", className="page__subtitle rtl-detail-uid"),
            html.Div(id=ERROR_ID, className="listing-error"),
            html.Div(id=BODY_ID),
            html.Div(id=CONTEXT_ID),
            html.Section(id=HISTORY_SECTION_ID, className="rtl-detail-history-section", children=[
                html.H2("Temperature history", className="rtl-detail-section__title"),
                # The window ends at this RTL's own last reading (ADR-030), so
                # the control names a span, not a distance from today.
                dcc.RadioItems(
                    id=WINDOW_ID,
                    options=[{"label": w.label, "value": w.key} for w in HISTORY_WINDOWS],
                    value=DEFAULT_WINDOW_KEY,
                    inline=True,
                    className="fleet-overview-chips",
                    labelClassName="fleet-overview-chip-option",
                ),
                html.Div(id=HISTORY_ID),
            ]),
        ],
    )
