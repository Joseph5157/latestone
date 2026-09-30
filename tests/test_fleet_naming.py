"""The Fleet vocabulary.

The route stays /plants and every domain identifier is unchanged — this is a
presentation rename only. These tests pin the boundary so a future edit cannot
quietly turn a label change into a routing change.

CLIENT-TERMINOLOGY-NAV-01 moved the /plants page itself off the "Fleet"
vocabulary: it lists the client's registered RTLs, so it is called "Registered
RTLs" (asserted in tests/test_client_terminology.py, which owns that wording).
The synthetic drill-down pages below still read "Fleet" at the root of their
breadcrumb, deliberately — they show the legacy synthetic Plant model, and
relabelling their root "Registered RTLs" would assert that a synthetic plant
sits underneath the client RTL directory, which is false. Retiring those pages
is a later gate; until then "Fleet" is the vaguer and more honest word.
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
    assert headings[0].children == "Registered RTLs"


def test_fleet_page_subtitle_slot_is_present():
    """The subtitle is static layout; the page performs no queries."""
    layout = plants_overview.layout()
    assert find_by_class(layout, "page__subtitle")


def test_breadcrumb_root_names_the_registered_rtl_directory():
    """The one breadcrumb that is NOT "Fleet": this page is the real client
    directory, and its crumb must agree with its heading."""
    assert _breadcrumb_labels(plants_overview.layout())[0] == "Registered RTLs"


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
