"""Fleet KPI cards, including Data Health.

Presentation only. Every number here is read off a single `FleetHealth` built
once per render by `monitoring_service.get_fleet_health()` — this module never
queries and never recomputes freshness, so the card cannot drift from the plant
table beside it.
"""
from __future__ import annotations

from datetime import datetime

from dash import html

from components.kpi_card import kpi_card
from services.monitoring_service import FleetHealth, Freshness, severity_rank

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


def fleet_kpi_cards(
    plants: int, transformers: int, devices: int, health: FleetHealth
) -> html.Div:
    """The four cards from spec section 9.

    Hierarchy totals are passed in from the hierarchy counts rather than derived
    from `health`, so the population shown here is the same one the plant table
    lists even if a device has no freshness row at all.
    """
    value, secondary = fleet_health_summary(health)
    return html.Div(
        className="kpi-row kpi-row--fleet",
        children=[
            kpi_card("Plants", str(plants)),
            kpi_card("Transformers", str(transformers)),
            kpi_card("Devices", str(devices)),
            # No accent: --color-accent is selection colour (app.css §tokens),
            # and a permanently accented card spends the selection signal on
            # something that is never selected. State reads from the dot and
            # the wording instead.
            kpi_card("Data Health", value, secondary=secondary),
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
    value, secondary = _health_summary(counts)
    return html.Div(
        className="kpi-row kpi-row--fleet",
        children=[
            kpi_card("Devices", str(devices)),
            # No accent: --color-accent is selection colour (app.css §tokens),
            # and a permanently accented card spends the selection signal on
            # something that is never selected. State reads from the dot and
            # the wording instead.
            kpi_card("Data Health", value, secondary=secondary),
        ],
    )


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
    value, secondary = _health_summary(health.device_counts_for_plant(plant_id))
    return html.Div(
        className="kpi-row kpi-row--fleet",
        children=[
            kpi_card("Transformers", str(transformers)),
            kpi_card("Devices", str(devices)),
            # No accent: --color-accent is selection colour (app.css §tokens),
            # and a permanently accented card spends the selection signal on
            # something that is never selected. State reads from the dot and
            # the wording instead.
            kpi_card("Data Health", value, secondary=secondary),
        ],
    )
