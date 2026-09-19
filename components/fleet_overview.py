"""The Fleet Overview's rendering (FO-NEW-1).

Pure render functions over `services.fleet_overview_service` values. Plants
expand inline with the browser's own disclosure element (`<details>`), so
opening a plant costs no callback and no query.
"""
from __future__ import annotations

from datetime import datetime

from dash import dcc, html

from components.kpi_card import kpi_card

from routes import device_href
from services.attention_service import format_limit
from services.fleet_overview_service import (
    FILTER_ALL,
    FILTER_HOT,
    FILTER_NO_DATA,
    FILTER_NORMAL,
    SORT_HOTTEST,
    SORT_NAME,
    FleetOverview,
    PlantView,
    TransformerView,
    filter_counts,
    fleet_stats,
    rtl_condition_counts,
)
from services.temperature_condition_service import (
    CONDITION_LABELS,
    LIMIT_SOURCE_NOTE,
    DeviceTemperature,
    TemperatureCondition,
    TemperatureLimits,
)

_TONE = {
    TemperatureCondition.CRITICAL: "critical",
    TemperatureCondition.WARNING: "warning",
    TemperatureCondition.NORMAL: "normal",
    TemperatureCondition.LIMITS_NOT_SET: "none",
    TemperatureCondition.NO_RECENT_DATA: "none",
}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def temperature(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f} °C"


def ago(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "never"
    seconds = (now - moment).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    return f"{int(seconds // 86400)} d ago"


def when(moment: datetime | None) -> str:
    return "—" if moment is None else moment.strftime("%d %b %H:%M UTC")


def condition_chip(condition: TemperatureCondition) -> html.Span:
    return html.Span(
        CONDITION_LABELS[condition],
        className=f"fleet-overview-chip fleet-overview-chip--{_TONE[condition]}",
    )


def limits_line(limits: TemperatureLimits | None) -> html.P:
    if limits is None:
        return html.P(
            "Temperature limits are not set, so no RTL can be rated Normal, "
            "Warning or Critical. An administrator sets them under Settings.",
            className="fleet-overview-limits fleet-overview-limits--unset",
        )
    return html.P(
        f"Warning at {format_limit(limits.warning_c)} °C · Critical at "
        f"{format_limit(limits.critical_c)} °C · {LIMIT_SOURCE_NOTE}",
        className="fleet-overview-limits",
    )


def counts_text(counts, *, limits_set: bool) -> str:
    parts = []
    if limits_set:
        parts.append(f"{counts.normal} normal")
        parts.append(f"{counts.hot} hot")
    if counts.no_recent_data:
        parts.append(f"{counts.no_recent_data} without recent data")
    return " · ".join(parts)


def _logger_row(t: DeviceTemperature, now: datetime) -> html.Tr:
    return html.Tr([
        html.Td(dcc.Link(t.device_code, href=device_href(t.device_id),
                         className="fleet-overview-link"), **{"data-label": "RTL"}),
        html.Td(temperature(t.value), className="fleet-overview-num",
                **{"data-label": "Latest"}),
        html.Td(condition_chip(t.condition), **{"data-label": "Condition"}),
        html.Td(ago(t.reading_ts, now), **{"data-label": "Last reading"}),
        html.Td(dcc.Link("Electrical readings →", href=device_href(t.device_id),
                         className="fleet-overview-electrical")),
    ])


def transformer_block(tv: TransformerView, now: datetime) -> html.Div:
    if tv.max_30d is None:
        peak = "No temperature reading in the last 30 days"
    else:
        by = f" (RTL {tv.max_30d_device_code})" if tv.max_30d_device_code else ""
        peak = f"30-day max {temperature(tv.max_30d)} on {when(tv.max_30d_at)}{by}"
    return html.Div(className="fleet-overview-transformer", children=[
        html.Div(className="fleet-overview-transformer__head", children=[
            html.H4(f"Transformer {tv.transformer_code}"),
            html.Span(peak, className="fleet-overview-transformer__peak"),
        ]),
        html.Table(className="fleet-overview-table", children=[
            html.Thead(html.Tr([html.Th("RTL"), html.Th("Latest"), html.Th("Condition"),
                                html.Th("Last reading"), html.Th("")])),
            html.Tbody([_logger_row(t, now) for t in tv.loggers]),
        ]),
    ])


def plant_row(plant: PlantView, now: datetime, *, limits_set: bool) -> html.Details:
    top = plant.hottest
    hottest = (
        [html.Span(temperature(top.value), className="fleet-overview-plant__temp"),
         condition_chip(top.condition)]
        if top else [html.Span("No recent reading", className="fleet-overview-plant__temp--none")]
    )
    return html.Details(className="fleet-overview-plant", children=[
        html.Summary(className="fleet-overview-plant__summary", children=[
            html.Span(className="fleet-overview-plant__name", children=[
                html.Strong(plant.name),
                html.Span(plant.country or "", className="fleet-overview-plant__country"),
            ]),
            html.Span(
                f"{_plural(len(plant.transformers), 'transformer')} · "
                f"{_plural(plant.logger_count, 'RTL')}",
                className="fleet-overview-plant__size",
            ),
            html.Span(className="fleet-overview-plant__hottest", children=hottest),
            html.Span(counts_text(plant.counts, limits_set=limits_set),
                      className="fleet-overview-plant__counts"),
        ]),
        html.Div(className="fleet-overview-plant__body",
                 children=[transformer_block(tv, now) for tv in plant.transformers]),
    ])


FILTER_LABELS = {
    FILTER_ALL: "All",
    FILTER_HOT: "Hot",
    FILTER_NO_DATA: "No recent data",
    FILTER_NORMAL: "Normal",
}

SORT_OPTIONS = [
    {"label": "Name", "value": SORT_NAME},
    {"label": "Hottest first", "value": SORT_HOTTEST},
]


def filter_options(view: FleetOverview) -> list[dict]:
    """Chip options with the number of plants each would show."""
    return [
        {"label": f"{FILTER_LABELS[key]} · {count}", "value": key}
        for key, count in filter_counts(view).items()
    ]


def plant_list(view: FleetOverview, plants=None):
    """`plants` is the filtered, sorted subset; None means every plant."""
    if not view.plants:
        return html.P("No plants to show for your account.", className="fleet-overview-empty")
    shown = view.plants if plants is None else plants
    if not shown:
        return html.P("No plants match this filter.", className="fleet-overview-empty")
    limits_set = view.limits is not None
    return html.Div(className="fleet-overview-plants", children=[
        plant_row(p, view.generated_at, limits_set=limits_set) for p in shown
    ])


#: Pattern-matching id type for anything that sets the chips / sort when
#: clicked (CLICK-FILTER-1). "" in `filter` or `sort` means "leave it".
JUMP = "fleet-overview-jump"

#: Which plant chip a condition selects. Chips are per plant, so Warning and
#: Critical both select Hot (plants with any Warning or Critical RTL).
_CONDITION_FILTER = {
    TemperatureCondition.CRITICAL: FILTER_HOT,
    TemperatureCondition.WARNING: FILTER_HOT,
    TemperatureCondition.NORMAL: FILTER_NORMAL,
    TemperatureCondition.NO_RECENT_DATA: FILTER_NO_DATA,
}


def _jump_id(part: str, *, filter_key: str = "", sort_key: str = "") -> dict:
    return {"type": JUMP, "part": part, "filter": filter_key, "sort": sort_key}


def _card_button(label, value, secondary, jump_id, *, hint, accent=False) -> html.Button:
    """A stat card that is also a filter control. Same classes as `kpi_card`,
    spans instead of divs so it is valid button content."""
    return html.Button(
        type="button", n_clicks=0, id=jump_id, title=f"{secondary} — {hint}",
        className="kpi-card kpi-card--action" + (" kpi-card--accent" if accent else ""),
        children=[
            html.Span(label, className="kpi-card__label"),
            html.Span(value, className="kpi-card__value"),
            html.Span(secondary, className="kpi-card__secondary"),
        ],
    )


def stat_cards(view: FleetOverview) -> html.Div:
    """Temperature at a glance (STATS-CARDS-1). Every count is RTLs.
    Hottest, Hot RTLs and Reporting also set the list below (CLICK-FILTER-1)."""
    s = fleet_stats(view)
    limits_set = view.limits is not None
    if s.hottest is None:
        hottest = kpi_card("Hottest now", "—", "No recent reading")
    else:
        hottest = _card_button(
            "Hottest now", temperature(s.hottest.value),
            f"RTL {s.hottest.device_code} · {s.hottest_plant}",
            _jump_id("hottest", sort_key=SORT_HOTTEST),
            hint="Sort plants hottest first", accent=True,
        )
    if limits_set:
        hot = _card_button(
            "Hot RTLs", str(s.warning + s.critical),
            f"{s.critical} Critical · {s.warning} Warning",
            _jump_id("hot", filter_key=FILTER_HOT), hint="Show plants with hot RTLs",
        )
    else:
        hot = kpi_card("Hot RTLs", "—", "Temperature limits not set")
    if s.peak_value is None:
        peak = kpi_card("30-day peak", "—", "No reading in the last 30 days")
    else:
        detail = f"{when(s.peak_at)} · RTL {s.peak_device_code} · {s.peak_plant}"
        peak = kpi_card("30-day peak", temperature(s.peak_value), detail)
        peak.title = detail  # the full text when the card truncates it
    reporting = _card_button(
        "Reporting", f"{s.reporting} of {s.total}",
        "RTLs with a recent temperature reading",
        _jump_id("reporting", filter_key=FILTER_NO_DATA),
        hint="Show plants with RTLs that are not reporting",
    )
    return html.Div(className="kpi-row fleet-overview-stats",
                    children=[hottest, hot, peak, reporting])


def condition_bar(view: FleetOverview):
    """One stacked bar of RTLs per temperature condition, with a legend.
    Segments and legend entries set the matching chip (CLICK-FILTER-1)."""
    counts = rtl_condition_counts(view)
    total = sum(counts.values())
    if not total:
        return None
    segments, legend = [], []
    for condition, n in counts.items():
        tone = _TONE[condition]
        label = f"{CONDITION_LABELS[condition]} {n}"
        target = _CONDITION_FILTER.get(condition)
        if target:
            segments.append(html.Button(
                type="button", n_clicks=0, id=_jump_id(f"seg-{condition.value}", filter_key=target),
                className=f"fleet-overview-condition__seg fleet-overview-condition__seg--{tone}",
                style={"flexGrow": n}, title=f"{label} — show these plants",
                **{"aria-label": f"{label}, show these plants"},
            ))
            legend.append(html.Button(
                type="button", n_clicks=0, id=_jump_id(f"legend-{condition.value}", filter_key=target),
                className=f"fleet-overview-legend fleet-overview-legend--{tone}", children=label,
            ))
        else:
            segments.append(html.Span(
                className=f"fleet-overview-condition__seg fleet-overview-condition__seg--{tone}",
                style={"flexGrow": n}, title=label,
            ))
            legend.append(html.Span(label, className=f"fleet-overview-legend fleet-overview-legend--{tone}"))
    return html.Div(className="fleet-overview-condition", children=[
        html.Div(className="fleet-overview-condition__head", children=[
            html.Span("Temperature condition", className="fleet-overview-condition__title"),
            html.Span(_plural(total, "RTL"), className="fleet-overview-condition__total"),
        ]),
        html.Div(className="fleet-overview-condition__bar", children=segments),
        html.Div(className="fleet-overview-condition__legend", children=legend),
    ])
