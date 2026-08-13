"""The Fleet vocabulary.

The route stays /plants and every domain identifier is unchanged — this is a
presentation rename only. These tests pin the boundary so a future edit cannot
quietly turn a label change into a routing change.
"""
import pytest

import pages.device_dashboard as device_dashboard
import pages.plant_detail as plant_detail
import pages.plants_overview as plants_overview
import pages.transformer_detail as transformer_detail
from tests.dash_tree import find_by_class, text_of, walk


def _breadcrumb_labels(layout):
    return [
        n.children
        for n in walk(layout)
        if isinstance(getattr(n, "className", None), str)
        and n.className in {"breadcrumb__link", "breadcrumb__current"}
    ]


def test_fleet_page_title():
    layout = plants_overview.layout()
    headings = [n for n in walk(layout) if type(n).__name__ == "H1"]
    assert headings[0].children == "Fleet Overview"


def test_fleet_page_subtitle_slot_is_present():
    """The slot itself is static layout; its text is filled by the listing
    callback (populate_overview), since layout() performs no queries."""
    layout = plants_overview.layout()
    assert find_by_class(layout, "page__subtitle")


def test_fleet_page_subtitle_wording():
    """The wording the callback writes into that slot.

    `fleet_subtitle_text` is the pure function the callback calls, so this
    proves the wording without needing a live query — the plant count itself
    is exercised in tests/test_fleet_overview.py alongside the rest of the
    freshness chain.
    """
    from components.fleet_summary import fleet_subtitle_text

    assert "monitored plants" in fleet_subtitle_text(30)


def test_breadcrumb_root_reads_fleet_on_the_fleet_page():
    assert _breadcrumb_labels(plants_overview.layout())[0] == "Fleet"


def test_breadcrumb_root_reads_fleet_on_plant_detail():
    labels = _breadcrumb_labels(plant_detail.layout("plant-01"))
    assert labels[0] == "Fleet"


def test_breadcrumb_root_reads_fleet_on_transformer_detail():
    labels = _breadcrumb_labels(
        transformer_detail.layout("plant-01-t1", plant_id="plant-01")
    )
    assert labels[0] == "Fleet"


def test_breadcrumb_root_reads_fleet_on_device_dashboard():
    labels = _breadcrumb_labels(
        device_dashboard.layout(plant_id="plant-01", transformer_id="plant-01-t1")
    )
    assert labels[0] == "Fleet"


def test_the_route_is_still_plants():
    """The rename is vocabulary only. /plants and every id are untouched."""
    links = [
        n.href for n in walk(plants_overview.layout())
        if getattr(n, "href", None)
    ] + [
        n.href for n in walk(plant_detail.layout("plant-01"))
        if getattr(n, "href", None)
    ]
    assert any(h == "/plants" for h in links)
    assert not any("/fleet" in h for h in links)


def test_the_plants_kpi_card_still_counts_plants():
    """The card label is a domain noun, not the page name. It does not change.

    Asserted on the rendered output rather than on source text: the label
    living inside a `counts=[("Plants", ...)]` list is exactly as valid a
    place for it as a literal `kpi_card("Plants", ...)` call, so pinning the
    source text would fail the moment the composition is refactored without
    the label itself ever changing.
    """
    from services.monitoring_service import fleet_health_from_rows
    from components.fleet_summary import fleet_kpi_cards

    health = fleet_health_from_rows([])
    cards = fleet_kpi_cards(plants=30, transformers=71, devices=120, health=health)
    labels = [text_of(el) for el in find_by_class(cards, "kpi-card__label")]
    assert "Plants" in labels
