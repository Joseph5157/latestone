"""Fleet Layer 2: presentation over the existing scoped freshness snapshot.

Coverage means Fresh / monitored RTLs, never connectivity or historical
reporting. Attention remains Stale + No Data. No classification or queries
are performed here; the two ratios share the same device-count denominator.
"""
from __future__ import annotations

from urllib.parse import quote

from dash import html

from components.card import card_header
from config.settings import monitoring
from services.monitoring_service import Freshness


_STATES = (
    (Freshness.FRESH, "Fresh", "fresh"),
    (Freshness.STALE, "Stale", "stale"),
    (Freshness.NO_DATA, "No Data", "none"),
)


def _total(counts: dict[Freshness, int]) -> int:
    return sum(counts.get(state, 0) for state, _label, _token in _STATES)


def _percentage(count: int, total: int) -> float:
    return 100 * count / total if total else 0


def _threshold_label(minutes: int) -> str:
    if minutes % (24 * 60) == 0:
        days = minutes // (24 * 60)
        return "24 hours" if days == 1 else f"{days} days"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} min"


def _freshness_breakdown(counts: dict[Freshness, int]) -> list[tuple]:
    """Shared display rows, not a second classification of metric readings."""
    total = _total(counts)
    return [(state, label, token, counts.get(state, 0),
             _percentage(counts.get(state, 0), total))
            for state, label, token in _STATES]


def _state_details(counts: dict[Freshness, int]) -> html.Dl:
    return html.Dl(className="fleet-condition__details fleet-condition__state-details", children=[
        html.Div(className=f"fleet-condition__detail-row fleet-condition__tone--{token}", children=[
            html.Dt(label, className="fleet-condition__stat-label--state"),
            html.Dd(str(count), className="fleet-condition__detail-count"),
            html.Dd(f"{percentage:.1f}%", className="fleet-condition__detail-percent"),
        ]) for _state, label, token, count, percentage in _freshness_breakdown(counts)
    ])


def condition_wording(counts: dict[Freshness, int]) -> tuple[str, str, str]:
    """Conservative badge/headline/copy, based only on the supplied states."""
    total = _total(counts)
    fresh = counts.get(Freshness.FRESH, 0)
    stale = counts.get(Freshness.STALE, 0)
    missing = counts.get(Freshness.NO_DATA, 0)
    if not total:
        return "No monitored RTLs", "No RTLs to assess", "No monitored RTLs are available in the active fleet."
    if stale == total:
        return "Attention Required", "All RTLs are stale", f"All {total} monitored RTLs are stale across the active fleet."
    if missing == total:
        return "Attention Required", "All RTLs have no data", f"All {total} monitored RTLs have no data across the active fleet."
    if fresh == total:
        return "Fresh", "All RTLs are fresh", f"All {total} monitored RTLs are fresh across the active fleet."
    headline = "Some RTLs require attention" if stale else "Some RTLs have no data"
    return (
        "Attention Required", headline,
        f"Of {total} monitored RTLs, {stale} are stale, {missing} have no data and {fresh} are fresh.",
    )


def _arc_mask(percentage: float, *, semicircle: bool = False) -> str:
    """Exact path-length masks; foreground colours inherit existing tokens.

    The semicircle starts at the left (0%) and ends at the right (100%).
    Butt caps avoid overstating small values or leaving a dot at zero.
    """
    geometry = (
        '<path d="M 10 80 A 70 70 0 0 1 150 80"'
        if semicircle else
        '<circle cx="80" cy="80" r="70" transform="rotate(-90 80 80)"'
    )
    height = 90 if semicircle else 160
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 {height}">'
        f'{geometry} fill="none" stroke="black" stroke-width="12" '
        f'pathLength="100" stroke-dasharray="{percentage} 100"/></svg>'
    )
    return f'url("data:image/svg+xml,{quote(svg, safe="")}")'


def _heading(title: str, subtitle: str) -> html.Div:
    """The shared card header. Kept as a local alias so every card on this
    page states its title and subtitle the same way."""
    return card_header(title, subtitle)


def fleet_condition_summary(counts: dict[Freshness, int]) -> html.Section:
    total = _total(counts)
    affected = counts.get(Freshness.STALE, 0) + counts.get(Freshness.NO_DATA, 0)
    tone = "stale" if counts.get(Freshness.STALE, 0) else "none" if affected or not total else "fresh"
    badge, headline, detail = condition_wording(counts)
    return html.Section(
        className=f"card fleet-condition__card fleet-condition__summary fleet-condition__tone--{tone}",
        children=[
            _heading("Fleet Condition Summary", "Attention across the monitored RTL fleet"),
            html.Div(className="fleet-condition__chart-stage", children=[
                html.Div(className="fleet-condition__ring", role="img", **{
                    "aria-label": f"Attention Required: {affected} of {total} monitored RTLs (Stale or No Data)",
                }, children=[
                    html.Div(className="fleet-condition__arc fleet-condition__track",
                             style={"maskImage": _arc_mask(100)}, **{"aria-hidden": "true"}),
                    html.Div(className="fleet-condition__arc",
                             style={"maskImage": _arc_mask(_percentage(affected, total))},
                             **{"aria-hidden": "true"}),
                    html.Div(className="fleet-condition__center", **{"aria-hidden": "true"}, children=[
                        html.Strong(str(affected), className="fleet-condition__number"),
                        html.Span("RTLs require attention"),
                        html.Span(f"of {total} monitored RTLs", className="fleet-condition__center-total"),
                    ]),
                ]),
            ]),
            html.P(f"{affected} of {total} monitored RTLs require attention",
                   className="fleet-condition__ratio"),
            _state_details(counts),
            html.Div(className="fleet-condition__message", children=[
                html.P(
                    f"{_percentage(affected, total):.1f}% of monitored RTLs require attention"
                    if total else "No monitored RTLs to assess",
                    className="fleet-condition__insight",
                ),
                html.Span(badge, className="fleet-condition__badge"),
                html.P(headline, className="fleet-condition__headline", title=detail),
                html.A("View needs attention →", href="#needs-attention",
                       className="fleet-condition__link") if affected else None,
            ]),
        ],
    )


def fresh_data_coverage(counts: dict[Freshness, int]) -> html.Section:
    total = _total(counts)
    fresh = counts.get(Freshness.FRESH, 0)
    percentage = _percentage(fresh, total)
    return html.Section(
        className="card fleet-condition__card fleet-condition__coverage fleet-condition__tone--fresh",
        children=[
            _heading("Fresh Data Coverage", "RTLs with all monitored metrics within the freshness threshold"),
            html.Div(className="fleet-condition__chart-stage", children=[
                html.Div(className="fleet-condition__gauge", children=[
                    html.Div(className="fleet-condition__gauge-arc", role="img", **{
                        "aria-label": f"Fresh data coverage: {percentage:.1f}%, {fresh} of {total} monitored RTLs",
                    }, children=[
                        html.Div(className="fleet-condition__arc fleet-condition__track",
                                 style={"maskImage": _arc_mask(100, semicircle=True)},
                                 **{"aria-hidden": "true"}),
                        html.Div(className="fleet-condition__arc",
                                 style={"maskImage": _arc_mask(percentage, semicircle=True)},
                                 **{"aria-hidden": "true"}),
                        html.Div(className="fleet-condition__gauge-value", **{"aria-hidden": "true"}, children=[
                            html.Strong(f"{percentage:.1f}%", className="fleet-condition__number"),
                            html.Span("Fresh data"),
                        ]),
                    ]),
                    html.Div(className="fleet-condition__gauge-scale", **{"aria-hidden": "true"},
                             children=[html.Span("0%"), html.Span("100%")]),
                ]),
            ]),
            html.P(f"{fresh} of {total} monitored RTLs have fresh data",
                   className="fleet-condition__ratio"),
            html.Dl(className="fleet-condition__details fleet-condition__coverage-details", children=[
                html.Div(className="fleet-condition__detail-row", children=[
                    html.Dt("Fresh RTLs"),
                    html.Dd(str(fresh), className="fleet-condition__detail-count"),
                ]),
                html.Div(className="fleet-condition__detail-row", children=[
                    html.Dt(["Outside freshness threshold",
                             html.Small("Includes Stale and No Data", className="fleet-condition__detail-hint")]),
                    html.Dd(str(total - fresh), className="fleet-condition__detail-count"),
                ]),
            ]),
            html.Dl(className="fleet-condition__metadata", children=[
                html.Div(children=[html.Dt("Freshness target"), html.Dd(f"≤ {_threshold_label(monitoring.stale_after_minutes)}")]),
                html.Div(children=[html.Dt("Evaluation scope"), html.Dd("All monitored metrics must be fresh")]),
            ]),
            html.P("No monitored RTLs in your current scope." if not total else
                   "Uses the same classification as Data Freshness.",
                   className="fleet-condition__note fleet-condition__coverage-note"),
        ],
    )


def fleet_condition_panels(counts: dict[Freshness, int]) -> list:
    """Two upper panels in the existing output slot: no new callback or query."""
    return [fleet_condition_summary(counts), fresh_data_coverage(counts)]


def data_freshness(counts: dict[Freshness, int]) -> html.Section:
    total = _total(counts)
    threshold = _threshold_label(monitoring.stale_after_minutes)
    ranges = {
        Freshness.FRESH: f"All metrics ≤ {threshold}",
        Freshness.STALE: f"At least one metric > {threshold}",
        Freshness.NO_DATA: "At least one metric has no reading",
    }
    return html.Section(className="card fleet-condition__card fleet-condition__freshness", children=[
        _heading("Data Freshness", f"Recency of latest RTL data · global {threshold} operational threshold"),
        html.Div(className="fleet-condition__freshness-rows", children=[
            html.Div(className=f"fleet-condition__freshness-row fleet-condition__tone--{token}", children=[
                html.Div(className="fleet-condition__freshness-labels", children=[
                    html.Span(label, className="fleet-condition__stat-label fleet-condition__stat-label--state"),
                    html.Div(className="fleet-condition__freshness-values", children=[
                        html.Strong(str(count), className="fleet-condition__stat-value"),
                        html.Span(f"{percentage:.1f}%",
                                  className="fleet-condition__stat-meta"),
                    ]),
                ]),
                html.P(ranges[state], className="fleet-condition__range"),
                html.Div(className="fleet-condition__bar", **{"aria-hidden": "true"}, children=[
                    html.Div(className="fleet-condition__segment",
                             style={"width": f"{percentage}%"})
                ]),
            ]) for state, label, token, count, percentage in _freshness_breakdown(counts)
        ]),
        html.P(f"{total} monitored RTLs · worst state across metrics",
               className="fleet-condition__note"),
    ])


def fleet_inventory(plants: int, transformers: int, devices: int) -> html.Section:
    return html.Section(className="card fleet-condition__card fleet-condition__inventory", children=[
        _heading("Fleet Inventory", "Monitored assets in your current scope"),
        html.Div(className="fleet-condition__stats", children=[
            html.Div(className="fleet-condition__stat", children=[
                html.Span(label, className="fleet-condition__stat-label"),
                html.Strong(str(count), className="fleet-condition__stat-value"),
                html.Span("Monitored", className="fleet-condition__stat-meta"),
            ]) for label, count in (("Plants", plants), ("Transformers", transformers), ("RTL Devices", devices))
        ]),
    ])
