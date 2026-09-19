"""Plant and transformer KPI cards, including Data Health.

Presentation only. Every number here is read off a single `FleetHealth` built
once per render by `monitoring_service.get_fleet_health()` — this module never
queries and never recomputes freshness, so the card cannot drift from the plant
table beside it.
"""
from __future__ import annotations

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


