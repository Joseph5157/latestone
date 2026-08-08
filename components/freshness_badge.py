"""Freshness badge.

Renders DATA FRESHNESS only - how recently this device/metric delivered a
reading. It does NOT indicate database or network connectivity, and it is
NOT an electrical warning condition. Application/database errors use
components.status_panels.error_panel instead.
"""
from __future__ import annotations

from dash import html

from services.monitoring_service import Freshness

FRESHNESS_LABELS = {
    Freshness.FRESH: "Fresh",
    Freshness.STALE: "Stale",
    Freshness.NO_DATA: "No data",
}


def freshness_class(freshness: Freshness) -> str:
    return f"freshness-badge freshness-badge--{freshness.value}"


def freshness_badge(freshness: Freshness, component_id: str | None = None):
    props = {"id": component_id} if component_id else {}
    return html.Span(
        FRESHNESS_LABELS[freshness], className=freshness_class(freshness), **props
    )
