"""Single source of truth for Freshness -> presentation tokens.

`freshness_badge.py` renders a real DOM badge; `entity_table.py` can only
style a DataTable cell with CSS, never mount a component into it. Both need
the same state -> {label, colour token} mapping, so it is written once here
and each renderer decides how to apply it.

NO_DATA intentionally maps to the neutral `none` text token, not `no_data`:
the enum's value and the CSS token name are allowed to differ, which is
exactly why this is a table rather than an f-string built from the enum.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.monitoring_service import Freshness


@dataclass(frozen=True)
class FreshnessPresentation:
    label: str
    #: Name of the `--state-{text_token}-text` CSS custom property.
    text_token: str


FRESHNESS_PRESENTATION: dict[Freshness, FreshnessPresentation] = {
    Freshness.FRESH: FreshnessPresentation("Fresh", "fresh"),
    Freshness.STALE: FreshnessPresentation("Stale", "stale"),
    Freshness.NO_DATA: FreshnessPresentation("No data", "none"),
}
