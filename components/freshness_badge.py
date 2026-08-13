"""Freshness badge.

Renders DATA FRESHNESS only - how recently this device/metric delivered a
reading. It does NOT indicate database or network connectivity, and it is
NOT an electrical warning condition. Application/database errors use
components.status_panels.error_panel instead.
"""
from __future__ import annotations

from dash import html

from components.freshness_presentation import FRESHNESS_PRESENTATION
from services.monitoring_service import Freshness

#: Kept as a public name: components.app_header imports it directly.
FRESHNESS_LABELS = {state: p.label for state, p in FRESHNESS_PRESENTATION.items()}


def freshness_class(freshness: Freshness) -> str:
    return f"freshness-badge freshness-badge--{freshness.value}"


def freshness_badge(freshness: Freshness, component_id: str | None = None):
    props = {"id": component_id} if component_id else {}
    return html.Span(
        FRESHNESS_LABELS[freshness], className=freshness_class(freshness), **props
    )


UTC_FORMAT = "%d %b %Y %H:%M"


def format_age(age) -> str:
    """A timedelta as a compact operator-facing age: `8 min`, `2h 17m`, `5d 3h`."""
    if age is None:
        return "—"
    seconds = max(int(age.total_seconds()), 0)
    minutes, hours = seconds // 60, seconds // 3600
    days = seconds // 86400
    if days:
        return f"{days}d {hours % 24}h"
    if hours:
        return f"{hours}h {minutes % 60:02d}m"
    return f"{minutes} min"


def format_last_reading(last_updated, age) -> str:
    """Paired relative + absolute, per spec section 21.

    Relative alone drifts between refreshes; absolute alone is hard to scan. The
    absolute half always carries UTC, because the hierarchy spans ~30 countries
    and an unlabelled instant is ambiguous.

        2h 17m ago · 09 Aug 2026 05:43 UTC
    """
    if last_updated is None:
        return "No readings"
    return f"{format_age(age)} ago · {last_updated.strftime(UTC_FORMAT)} UTC"
