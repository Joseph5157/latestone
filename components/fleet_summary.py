"""Fleet KPI cards, including Data Health.

Presentation only. Every number here is read off a single `FleetHealth` built
once per render by `monitoring_service.get_fleet_health()` — this module never
queries and never recomputes freshness, so the card cannot drift from the plant
table beside it.
"""
from __future__ import annotations

from dash import html

from components.kpi_card import kpi_card
from services.monitoring_service import FleetHealth, Freshness

#: Exception states in the order they are reported, worst last so the eye lands
#: on the count that matters most in a mixed fleet.
_EXCEPTION_STATES = [(Freshness.STALE, "stale"), (Freshness.NO_DATA, "no data")]


def _health_summary(counts: dict[Freshness, int]) -> tuple[str, str]:
    """(value, secondary) for a Data Health card over any device population.

    The headline is the fresh count; the supporting line carries the exceptions,
    because "118 fresh" alone does not tell an operator whether the other two
    devices are late or gone. States with no members are omitted rather than
    padded with zeros, which would make every healthy population read as a list
    of problems.

    Shared by the fleet and plant cards so the two cannot drift apart in
    wording or in what counts as healthy.
    """
    value = f"{counts.get(Freshness.FRESH, 0)} fresh"

    parts = [
        f"{counts.get(state, 0)} {noun}"
        for state, noun in _EXCEPTION_STATES
        if counts.get(state, 0)
    ]
    if parts:
        return value, " · ".join(parts)

    # No exceptions. Distinguish a healthy population from an empty one: zero
    # devices is not zero problems, and "No stale or missing feeds" would be a
    # true sentence hiding the fact that nothing is being monitored at all.
    if sum(counts.values()) == 0:
        return value, "No devices reporting"
    return value, "No stale or missing feeds"


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
            kpi_card("Data Health", value, secondary=secondary, accent=True),
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
            kpi_card("Data Health", value, secondary=secondary, accent=True),
        ],
    )


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
            kpi_card("Data Health", value, secondary=secondary, accent=True),
        ],
    )
