"""The utility column is a monitoring surface, not a global one.

The Asset Navigator navigates to a device *dashboard*
(`callbacks.equipment_selector.device_navigation_target` -> `device_href`),
so on an administration or reporting route it is an exit door: completing
its cascade abandons the task on screen. The column is therefore hidden on
those routes rather than merely emptied — an empty column would still hold
its `calc(200px + var(--sp-4))` allocation and its collapse toggle.

Route policy only. Authentication remains
`callbacks.equipment_selector.selector_visibility`'s job: the two answer
different questions and are deliberately not merged.
"""
from pathlib import Path
import re

import pytest

from callbacks import navigation as nav

HIDDEN_CLASS = "app-shell__utility--hidden"

MONITORING_ROUTES = [
    "/",
    "/plants",
    "/plants/plant-01",
    "/plants/plant-01/plant-01-t1",
    "/devices/plant-01-t1-d1",
]

NON_MONITORING_ROUTES = [
    "/admin/devices",
    "/admin/devices/new",
    "/admin/users",
    "/reports",
    "/notifications",
]


@pytest.fixture(scope="module")
def css():
    text = (Path(__file__).resolve().parents[1] / "assets" / "app.css").read_text(
        encoding="utf-8"
    )
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def class_name_for(pathname, collapse_data=None) -> list[str]:
    class_name, *_rest = nav.utility_presentation(collapse_data, pathname)
    return class_name.split()


@pytest.mark.parametrize("pathname", NON_MONITORING_ROUTES)
def test_hidden_on_administration_and_reporting_routes(pathname):
    assert HIDDEN_CLASS in class_name_for(pathname)


@pytest.mark.parametrize("pathname", MONITORING_ROUTES)
def test_shown_on_the_monitoring_drill_down(pathname):
    assert HIDDEN_CLASS not in class_name_for(pathname)


def test_unrecognised_route_hides_rather_than_guesses():
    """An unknown path renders no page; a navigator beside nothing is noise."""
    assert HIDDEN_CLASS in class_name_for("/nowhere")


def test_absent_pathname_is_treated_as_the_overview():
    """`parse_pathname(None)` is the overview, and the first paint is the
    login page, which the shell already hides in CSS."""
    assert HIDDEN_CLASS not in class_name_for(None)


@pytest.mark.parametrize("collapse_data", [None, {}, {"collapsed": False}, {"collapsed": True}])
def test_hidden_route_wins_over_every_collapse_state(collapse_data):
    assert HIDDEN_CLASS in class_name_for("/admin/devices", collapse_data)


@pytest.mark.parametrize("collapse_data", [None, {}, {"collapsed": False}, {"collapsed": True}])
def test_collapse_still_works_where_the_column_is_shown(collapse_data):
    collapsed = bool(collapse_data and collapse_data.get("collapsed"))
    classes = class_name_for("/plants", collapse_data)
    assert ("app-shell__utility--collapsed" in classes) == collapsed


def test_accessible_outputs_are_unchanged_by_route():
    """Route decides allocation, never the toggle's meaning — a hidden column
    must not start describing itself as expanded when it is collapsed."""
    for pathname in ("/plants", "/admin/devices"):
        _class_name, hidden, expanded, label, title = nav.utility_presentation(
            {"collapsed": True}, pathname
        )
        assert hidden is True
        assert expanded == "false"
        assert label == "Expand Asset Navigator"
        assert title == label


def test_hidden_modifier_reserves_no_space(css):
    """`display: none`, not `visibility: hidden` — the latter would leave the
    216px allocation standing and reclaim nothing for the page."""
    match = re.search(re.escape(f".{HIDDEN_CLASS}") + r"\s*\{([^}]*)\}", css)
    assert match, f"Missing shell rule: .{HIDDEN_CLASS}"
    assert "display: none" in match.group(1)
