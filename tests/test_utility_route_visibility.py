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

**`/` is not one route.** ADR-024 makes it the Command Center for an
Administrator or Technician and the Fleet Overview for a General User, so
every assertion about `/` has to name a role or it is asserting about
whichever page the reader happened to have in mind. A role-blind check
passes for both answers and therefore proves neither — which is how the
navigator came to be painted on the Command Center at `/` while
`/command-center` hid it.
"""
from pathlib import Path
import re

import pytest

from callbacks import navigation as nav
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN

HIDDEN_CLASS = "app-shell__utility--hidden"

#: Routes that mean the same page for every role. `/` is deliberately absent
#: — see `TestTheRootPath`.
MONITORING_ROUTES = [
    "/plants/plant-01",
    "/plants/plant-01/plant-01-t1",
    "/devices/plant-01-t1-d1",
]

#: SATURDAY-REAL-FLEET-01: `/plants` is the real client-RTL Fleet Overview. The
#: navigator cascades over the synthetic PostgreSQL Plant -> Transformer ->
#: Device model, so it is hidden there rather than shown beside client data.
NON_MONITORING_ROUTES = [
    "/plants",
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


def class_name_for(pathname, collapse_data=None, role=None) -> list[str]:
    class_name, *_rest = nav.utility_presentation(collapse_data, pathname, role)
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
    """`parse_pathname(None)` is the overview, which now hides the navigator
    (real client-RTL data); the first paint is the login page anyway."""
    assert HIDDEN_CLASS in class_name_for(None)


@pytest.mark.parametrize("collapse_data", [None, {}, {"collapsed": False}, {"collapsed": True}])
def test_hidden_route_wins_over_every_collapse_state(collapse_data):
    assert HIDDEN_CLASS in class_name_for("/admin/devices", collapse_data)


@pytest.mark.parametrize("collapse_data", [None, {}, {"collapsed": False}, {"collapsed": True}])
def test_collapse_still_works_where_the_column_is_shown(collapse_data):
    collapsed = bool(collapse_data and collapse_data.get("collapsed"))
    classes = class_name_for("/plants/plant-01", collapse_data)
    assert ("app-shell__utility--collapsed" in classes) == collapsed


def test_accessible_outputs_are_unchanged_by_route():
    """Route decides allocation, never the toggle's meaning — a hidden column
    must not start describing itself as expanded when it is collapsed."""
    for pathname in ("/plants", "/admin/devices"):  # both hidden routes
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


class TestTheRootPath:
    """ASSET-NAV-ROUTE-1.

    `parse_pathname("/")` is `overview`, but `callbacks.routing`'s
    `landing_route_name` renders the Command Center there for the two
    operational roles. The column has to ask the same question the router
    asked, exactly as `active_nav_key` already does for the sidebar
    highlight, or the two disagree about which page is on screen.
    """

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN])
    @pytest.mark.parametrize("pathname", ["/", "", None])
    def test_root_hides_it_for_roles_that_land_on_the_command_center(
        self, pathname, role
    ):
        assert HIDDEN_CLASS in class_name_for(pathname, role=role)

    @pytest.mark.parametrize("pathname", ["/", "", None])
    def test_root_hides_it_for_a_general_user(self, pathname):
        """A General User lands on the Fleet Overview at `/`, which now shows
        real client-RTL data, so the synthetic-model navigator stays hidden."""
        assert HIDDEN_CLASS in class_name_for(pathname, role=GENERAL)

    @pytest.mark.parametrize("pathname", ["/", "", None])
    def test_root_hides_it_with_no_role(self, pathname):
        """Signed out, `landing_route_name` leaves the route alone (the
        overview, now hidden); the shell also hides the column in CSS behind
        `:has(.login-page)`."""
        assert HIDDEN_CLASS in class_name_for(pathname, role=None)

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN, GENERAL, None])
    def test_command_center_path_hides_it_for_everyone(self, role):
        """The explicit path was always right; `/` is what drifted."""
        assert HIDDEN_CLASS in class_name_for("/command-center", role=role)

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN, GENERAL, None])
    def test_the_landing_correction_does_not_leak_to_other_routes(self, role):
        """Only `/` (and the bare login path) are rewritten. Every explicit
        monitoring path keeps the navigator for every role."""
        for pathname in MONITORING_ROUTES:
            assert HIDDEN_CLASS not in class_name_for(pathname, role=role), pathname

    @pytest.mark.parametrize("role", [ADMINISTRATOR, TECHNICIAN])
    def test_signing_in_at_the_login_path_hides_it_too(self, role):
        """`/login` renders the Command Center for these roles once signed
        in (`landing_route_name`), and the pathname never changes — so the
        column must read that landing too, not the `unknown` beneath it."""
        assert HIDDEN_CLASS in class_name_for("/login", role=role)
