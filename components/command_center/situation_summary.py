"""Situation Summary — the top operational row (CC-1 Phase 5).

Four cards over one already-composed `CommandCenterSnapshot`. Nothing here
reads `FleetHealth`, counts devices, or evaluates freshness: the facade
decided every figure (services/command_center_service.py), and these
functions render it. That is what keeps one freshness interpretation in
Command Center rather than two that pass their own tests separately.

Vocabulary discipline (ADR-001): these cards describe DATA DELIVERY. Fresh,
Stale and No Data are the whole vocabulary. Critical and Warning name
already-classified event types and belong to a later phase's cards; a
"Healthy" rollup is not a thing this domain defines at all. None of those
words may appear here.
"""
from __future__ import annotations

from dash import dcc, html

from components.command_center.primitives import cc_card
from services.command_center_service import NO_DATA_EXPLANATION

#: Re-exported, not redefined. The sentence moved down to the facade in
#: Phase 10 because the Priority Investigation ROWS carry it too, and a
#: service may not import a component (AGENTS.md rule 8). Two copies of the
#: one honest description of NO_DATA is exactly the drift ADR-002 forbids.
__all__ = ["NO_DATA_EXPLANATION", "INVENTORY_SUBTITLE", "situation_summary_panels"]

#: Frozen by the user. Deliberately not "Total Assets" or "Registered
#: Assets": both would name the Managed-RTL administrative population
#: (services/admin_overview_service.py:15-20), a different set from the one
#: every other card on this row is counting.
INVENTORY_SUBTITLE = "Monitored assets in your current access scope"


def _stat(value: str, label: str, *, tone: str = "neutral") -> html.Div:
    """One number over its label.

    `tone` styles the marker only; the label always states the meaning, so
    the card never depends on colour alone to be read (the same rule the
    rest of the application follows).
    """
    return html.Div(
        className=f"command-center__stat command-center__tone--{tone}",
        children=[
            html.Span(value, className="command-center__stat-value"),
            html.Span(label, className="command-center__stat-label"),
        ],
    )


def _percent_text(percent: float) -> str:
    return f"{percent:.1f}% of monitored RTLs"


def fleet_health_card(snapshot) -> html.Section:
    """Freshness composition across the monitored population.

    Fresh is deliberately quiet — it carries the `fresh` tone but no
    emphasis — so a healthy fleet reads calm and the eye lands on the states
    that need someone (HMI_UI_UX_SPEC.md §6.3: colour is reserved for state).
    """
    rows = (
        ("Fresh", snapshot.fresh_rtls, "fresh"),
        ("Stale", snapshot.stale_rtls, "stale"),
        ("No Data", snapshot.no_data_rtls, "none"),
    )
    return cc_card(
        "Fleet Health",
        [
            html.P(
                f"{snapshot.monitored_device_count} monitored RTLs",
                className="command-center__card-total",
            ),
            html.Dl(
                className="command-center__composition",
                children=[
                    html.Div(
                        className=f"command-center__composition-row command-center__tone--{tone}",
                        children=[
                            html.Dt(label, className="command-center__composition-label"),
                            html.Dd(str(count), className="command-center__composition-count"),
                        ],
                    )
                    for label, count, tone in rows
                ],
            ),
        ],
        subtitle="Data delivery across the monitored fleet",
    )


def needs_attention_card(snapshot) -> html.Section:
    """Stale + No Data. Never event occurrences (ADR-002)."""
    body: list = [_stat(str(snapshot.attention_rtls), "affected RTLs", tone="stale")]
    if snapshot.has_monitored_devices:
        body.append(
            html.P(
                _percent_text(snapshot.attention_percent),
                className="command-center__stat-share",
            )
        )
    else:
        body.append(
            html.P(
                "No monitored RTLs in your current access scope.",
                className="command-center__empty-note",
            )
        )
    body.append(
        html.P("Stale + No Data", className="command-center__definition")
    )
    body.append(
        dcc.Link(
            "View affected RTLs →",
            href="#command-center-priority-investigation",
            className="command-center__card-action",
        )
    )
    return cc_card("Needs Attention", body, subtitle="RTLs requiring operator attention")


def communication_card(snapshot) -> html.Section:
    """No Data — monitoring blindness, not proof of equipment failure.

    Shows the count, its share, and the affected Plant count. No `>24h` /
    `>48h` / `>72h` buckets and no "never reported": there is no per-metric
    missing-since fact to derive a duration from, and `device_last_updated`
    describes whichever metric IS reporting (ADR-002).
    """
    body: list = [_stat(str(snapshot.no_data_rtls), "No Data RTLs", tone="none")]
    if snapshot.has_monitored_devices:
        body.append(
            html.P(
                _percent_text(snapshot.no_data_percent),
                className="command-center__stat-share",
            )
        )
    body.append(
        html.P(
            f"Across {snapshot.no_data_affected_plants} plants",
            className="command-center__stat-context",
        )
    )
    body.append(html.P(NO_DATA_EXPLANATION, className="command-center__explanation"))
    body.append(
        dcc.Link(
            "View affected RTLs →",
            href="#command-center-priority-investigation",
            className="command-center__card-action",
        )
    )
    return cc_card("Communication", body, subtitle="RTLs with an incomplete data picture")


def inventory_card(snapshot) -> html.Section:
    """The monitoring population at each level of the hierarchy.

    "RTL Devices" is the same number Fleet Health totals and every
    percentage above divides by — one field on the snapshot, so the card
    cannot drift from the population its subtitle promises.
    """
    levels = (
        ("Plants", snapshot.plant_count),
        ("Transformers", snapshot.transformer_count),
        ("RTL Devices", snapshot.monitored_device_count),
    )
    return cc_card(
        "Inventory",
        [
            html.Dl(
                className="command-center__inventory",
                children=[
                    html.Div(
                        className="command-center__inventory-row",
                        children=[
                            html.Dt(label, className="command-center__inventory-label"),
                            html.Dd(str(count), className="command-center__inventory-count"),
                        ],
                    )
                    for label, count in levels
                ],
            ),
        ],
        subtitle=INVENTORY_SUBTITLE,
    )


def situation_summary_panels(snapshot) -> list:
    """The four Situation Summary cards, in operator reading order:
    what is the fleet doing, what needs me, what can I not see, what is there.
    """
    return [
        fleet_health_card(snapshot),
        needs_attention_card(snapshot),
        communication_card(snapshot),
        inventory_card(snapshot),
    ]
