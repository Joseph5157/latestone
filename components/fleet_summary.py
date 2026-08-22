"""Fleet KPI cards, including Data Health.

Presentation only. Every number here is read off a single `FleetHealth` built
once per render by `monitoring_service.get_fleet_health()` — this module never
queries and never recomputes freshness, so the card cannot drift from the plant
table beside it.
"""
from __future__ import annotations

from datetime import datetime

from dash import html

from components.freshness_presentation import FRESHNESS_PRESENTATION
from components.kpi_card import kpi_card
from services.monitoring_service import FleetHealth, Freshness, severity_rank

#: Bar/legend order — worst-reassuring last, matching the KPI card's own
#: "fresh count always shown, worst state most prominent" convention.
_DISTRIBUTION_ORDER = (Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA)

#: Display noun per state. Separate from the enum values so wording can change
#: without touching the identity the styling layer joins on.
_HEALTH_NOUNS = {
    Freshness.FRESH: "fresh",
    Freshness.STALE: "stale",
    Freshness.NO_DATA: "no data",
}


def _health_summary(counts: dict[Freshness, int]) -> tuple[str, str]:
    """(value, secondary) for a Data Health card over any device population.

    The headline names the **worst state present**, walking `Freshness` in
    canonical severity order. That is the same rule as worst-of aggregation, so
    the card cannot develop a second opinion about which state matters most —
    leading with "stale" because stale is today's common case would be exactly
    that kind of drift.

    The supporting line carries the remaining states cheapest-first, always
    including the fresh count: "120 stale" alone does not tell an operator
    whether anything is still reporting.

    Shared by the fleet, plant and transformer cards so the three cannot drift
    apart in wording or in what counts as healthy.
    """
    total = sum(counts.values())

    # Zero devices is not zero problems. A population with nothing in it has
    # produced no evidence of health, and "0 fresh · no stale feeds" would be a
    # true sentence hiding the fact that nothing is monitored at all.
    if total == 0:
        return "No active devices", "No data available"

    worst_first = sorted(Freshness, key=severity_rank, reverse=True)
    present = [s for s in worst_first if counts.get(s, 0)]
    lead = present[0]
    value = f"{counts[lead]} {_HEALTH_NOUNS[lead]}"

    if lead is Freshness.FRESH:
        return value, "No stale or missing feeds"

    # Ascending severity: the reassuring number first, the worst remaining last.
    # FRESH is always shown even at zero — its absence is the point.
    rest = [
        f"{counts.get(s, 0)} {_HEALTH_NOUNS[s]}"
        for s in reversed(worst_first)
        if s is not lead and (counts.get(s, 0) or s is Freshness.FRESH)
    ]
    return value, " · ".join(rest)


def fleet_health_summary(health: FleetHealth) -> tuple[str, str]:
    """(value, secondary) for the fleet-wide Data Health card."""
    return _health_summary(health.counts)


def entity_summary_block(
    counts: list[tuple[str, int]], health_counts: dict[Freshness, int]
) -> html.Div:
    """The shared kpi-row: N count cards, then one Data Health card.

    Fleet, Plant and Transformer differ only in which counts they show and
    which device population Data Health is scoped to — `counts` and
    `health_counts` carry exactly that difference. Everything else (the
    wrapper class, the card language, the "no accent" rule) is one
    definition instead of three.
    """
    value, secondary = _health_summary(health_counts)
    return html.Div(
        className="kpi-row kpi-row--fleet",
        children=[
            *(kpi_card(label, str(n)) for label, n in counts),
            # No accent: --color-accent is selection colour (app.css §tokens),
            # and a permanently accented card spends the selection signal on
            # something that is never selected. State reads from the dot and
            # the wording instead.
            kpi_card("Data Health", value, secondary=secondary),
        ],
    )


def fleet_kpi_cards(
    plants: int, transformers: int, devices: int, health: FleetHealth
) -> html.Div:
    """The three structural fleet counts.

    Hierarchy totals are passed in from the hierarchy counts rather than derived
    from `health`, so the population shown here is the same one the plant table
    lists even if a device has no freshness row at all. Fleet freshness now has
    its own primary summary block below this row; Plant and Transformer detail
    pages continue to use ``entity_summary_block`` with a Data Health card.
    """
    return html.Div(
        className="kpi-row kpi-row--fleet kpi-row--fleet-structure",
        children=[
            kpi_card("Plants", str(plants)),
            kpi_card("Transformers", str(transformers)),
            kpi_card("Devices", str(devices)),
        ],
    )


def transformer_kpi_cards(
    transformer_id: str, devices: int, health: FleetHealth
) -> html.Div:
    """Summary for one transformer, scoped to its own devices.

    The transformer's rollup already tallies its devices by state, so the card
    reads straight off it — no third traversal and no third definition.
    """
    rollup = health.transformers.get(transformer_id)
    counts = rollup.counts if rollup else {}
    return entity_summary_block(counts=[("Devices", devices)], health_counts=counts)


def fleet_subtitle_text(plant_count: int) -> str:
    """Subtitle wording for the Fleet header.

    A pure string function so the wording is unit-testable on its own —
    `pages/plants_overview.layout()` performs no queries (it is layout only),
    so the plant count can only exist after the listing callback has run.
    The callback is the only caller; `plant_count` always comes from the same
    `hierarchy_service.list_plants()` call that feeds the Plants KPI card,
    never a literal.
    """
    return f"{plant_count} monitored plants across the active fleet"


def format_render_stamp(now: datetime) -> str:
    """When this Fleet snapshot was rendered — absolute, never relative.

    There is no `dcc.Interval` on the Fleet page, so a relative label would
    freeze at first render and quietly become wrong. Absolute UTC is honest
    about what it is.

    "Page refreshed" is deliberately not "Last updated": updated reads as
    sensor freshness, which the Data column already reports and which this
    line has nothing to do with.
    """
    return f"Page refreshed {now.strftime('%d %b %Y %H:%M')} UTC"


def plant_kpi_cards(
    plant_id: str, transformers: int, devices: int, health: FleetHealth
) -> html.Div:
    """Summary for one plant, in the same card language as Fleet and Device.

    Data Health is scoped to this plant's devices. Showing the fleet's counts on
    a plant page would be the same class of error as two independent freshness
    computations: numbers that are individually true and together misleading.
    """
    return entity_summary_block(
        counts=[("Transformers", transformers), ("Devices", devices)],
        health_counts=health.device_counts_for_plant(plant_id),
    )


def fleet_health_distribution(counts: dict[Freshness, int]) -> html.Div:
    """Primary fleet Data Health summary with subordinate state counts.

    Supporting information only — the KPI card stays the one authoritative
    Data Health figure; this renders `counts` the callback already built for
    that card, never a second computation and never a second query.

    Segment width is exactly proportional to device count. A zero-count state
    gets zero width rather than a minimum-visible sliver: a bar claiming a
    state is present when it is not would be a small lie in exchange for a
    tidier-looking bar. The legend row below is unconditional and always
    lists all three states with their counts, so a zero-width segment is
    still named in text rather than silently absent.

    Fill colour comes from `--state-*-text` (the saturated tokens already
    proven ≥8:1 legible, used elsewhere for badge text), not `--state-*-bg`
    (the pale tokens meant to sit behind dark text): `--state-none-bg`
    (#f1f3f5) is close enough to `--color-bg`/`--color-border` that a "No
    Data" segment filled with it would nearly disappear against the page.
    Both are existing tokens — no new colour is introduced.
    """
    total = sum(counts.get(state, 0) for state in _DISTRIBUTION_ORDER)
    value, secondary = _health_summary(counts)

    if total > 0:
        bar_children = [
            html.Div(
                className=f"health-distribution__segment health-distribution__segment--{state.value}",
                style={"width": f"{100 * counts.get(state, 0) / total}%"},
            )
            for state in _DISTRIBUTION_ORDER
            if counts.get(state, 0) > 0
        ]
        bar = html.Div(className="health-distribution__bar", children=bar_children)
    else:
        # Explicit empty state, matching the KPI card's own zero-population
        # wording — never a fake full-width "100% No Data" bar, which would
        # assert evidence (a device reporting nothing) that does not exist.
        bar = html.Div("No active devices", className="health-distribution__empty")

    legend = html.Div(
        className="health-distribution__legend",
        children=[
            html.Div(
                className=f"health-distribution__legend-item health-distribution__legend-item--{state.value}",
                children=[
                    html.Span(className="health-distribution__swatch"),
                    html.Span(
                        FRESHNESS_PRESENTATION[state].label,
                        className="health-distribution__legend-label",
                    ),
                    html.Span(
                        str(counts.get(state, 0)),
                        className="health-distribution__legend-count",
                    ),
                ],
            )
            for state in _DISTRIBUTION_ORDER
        ],
    )

    return html.Div(
        className="health-distribution health-distribution--primary",
        children=[
            html.Div(
                className="health-distribution__heading-row",
                children=[
                    html.Div(
                        children=[
                            html.H2("Data Health", className="health-distribution__title"),
                            html.P(value, className="health-distribution__primary-value"),
                        ]
                    ),
                    html.P(secondary, className="health-distribution__secondary"),
                ],
            ),
            bar,
            legend,
        ],
    )


def systemic_freshness_summary(counts: dict[Freshness, int]):
    """Fleet-wide summary for one exact, presentation-only condition.

    The rule is deliberately conservative: render only when every monitored
    device shares the same non-fresh state. There is no percentage threshold,
    severity judgement or domain-policy change. Counts come from the same
    ``FleetHealth.counts`` already used above.
    """
    total = sum(counts.get(state, 0) for state in _DISTRIBUTION_ORDER)
    if total <= 0:
        return None

    if counts.get(Freshness.STALE, 0) == total:
        condition = f"All {total} monitoring devices are stale."
    elif counts.get(Freshness.NO_DATA, 0) == total:
        condition = f"All {total} monitoring devices have no data."
    else:
        return None

    return html.Div(
        className="systemic-freshness",
        children=[
            html.Div(className="systemic-freshness__marker", **{"aria-hidden": "true"}),
            html.Div(
                children=[
                    html.H2(
                        "Fleet-wide freshness issue",
                        className="systemic-freshness__title",
                    ),
                    html.P(condition, className="systemic-freshness__detail"),
                ]
            ),
        ],
    )
