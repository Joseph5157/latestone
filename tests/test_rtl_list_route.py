"""RTL-LIST-ROUTE-01 — `/rtls` is the canonical Registered RTLs list.

The directory moved address and nothing else. These tests pin both halves of
that sentence:

* what moved — `/rtls` renders the directory, every in-app link points there,
  and the legacy `/plants` redirects there without rendering or reading
  anything on the way;
* what must not have moved with it — the route name, the role policy, the
  Technician restriction, the single Fleet data path, the detail route and the
  synthetic `/devices` and `/plants/<id>` routes.
"""
from __future__ import annotations

import ast
import inspect
from dataclasses import fields
from pathlib import Path

import pytest
from dash import no_update

import app as app_module
from callbacks import auth as auth_callbacks
from callbacks import fleet_overview
from callbacks import routing
from components import rtl_detail as rtl_detail_ui
from components import rtl_fleet
from components.app_sidebar import SIDEBAR_SECTIONS
from components.status_panels import forbidden_panel, not_found_panel
from pages import (
    device_dashboard,
    plant_detail,
    plants_overview,
    rtl_detail,
    transformer_detail,
)
from routes import (
    FLEET_OVERVIEW_PATH,
    LEGACY_RTL_LIST_PATH,
    NAV_KEY_BY_ROUTE,
    RTL_DETAIL_PATH_PREFIX,
    RTL_LIST_ALIAS_ROUTE,
    RTL_LIST_PATH,
    Route,
    legacy_redirect_path,
    parse_pathname,
    rtl_detail_href,
    rtl_list_href,
)
from services.auth_service import AuthenticatedUser
from services.authorization import (
    ADMINISTRATOR,
    GENERAL,
    ROUTE_POLICY,
    TECHNICIAN,
    may_access_route,
)
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from tests.dash_tree import walk

ROOT = Path(__file__).resolve().parents[1]
A_UID = 29042


def _user(role: str) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=7, username=role, full_name=role, role=role)


class _CapturingApp:
    """Collects callbacks by function name instead of registering them."""

    def __init__(self):
        self.functions: dict[str, object] = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


def _handler(module, name):
    app = _CapturingApp()
    module.register(app)
    return app.functions[name]


def _hrefs(component) -> list[str]:
    return [n.href for n in walk(component) if isinstance(getattr(n, "href", None), str)]


def _is_legacy(href: str) -> bool:
    path = href.split("?", 1)[0]
    return legacy_redirect_path(path) is not None


# ---------------------------------------------------------------------------
# The route model
# ---------------------------------------------------------------------------


class TestRouteModel:
    def test_the_canonical_list_is_rtls(self):
        assert RTL_LIST_PATH == "/rtls"
        # Every existing importer of the old constant now gets the canonical
        # address, so no caller can keep building `/plants`.
        assert FLEET_OVERVIEW_PATH == RTL_LIST_PATH

    def test_detail_lives_under_the_list(self):
        assert RTL_DETAIL_PATH_PREFIX == RTL_LIST_PATH
        assert rtl_detail_href(A_UID) == f"/rtls/{A_UID}"

    @pytest.mark.parametrize("path", ["/rtls", "/rtls/"])
    def test_rtls_parses_as_the_registered_directory(self, path):
        """The SAME route name the directory always had — so the role policy,
        the nav key and the Fleet callback all apply to it unchanged."""
        route = parse_pathname(path)
        assert route == Route(name="overview")

    def test_the_detail_route_is_unchanged(self):
        route = parse_pathname(f"/rtls/{A_UID}")
        assert route.name == "rtl_detail"
        assert route.rtl_uid == A_UID
        assert route.device_id is None

    @pytest.mark.parametrize("path", ["/rtls/abc", "/rtls/0", "/rtls/-1", "/rtls/29042/x"])
    def test_malformed_detail_paths_stay_unknown(self, path):
        assert parse_pathname(path).name == "unknown"

    @pytest.mark.parametrize("path", ["/plants", "/plants/"])
    def test_plants_is_the_compatibility_alias(self, path):
        route = parse_pathname(path)
        assert route == Route(name=RTL_LIST_ALIAS_ROUTE)

    def test_the_alias_carries_no_identity(self):
        route = parse_pathname("/plants")
        for field in fields(Route):
            if field.name != "name":
                assert getattr(route, field.name) is None, field.name

    def test_the_synthetic_plant_drill_down_is_untouched(self):
        """Only the bare legacy address is an alias. `/plants/<id>` is the
        synthetic Plant route and has no client equivalent to redirect to."""
        assert parse_pathname("/plants/plant-01") == Route(name="plant", plant_id="plant-01")
        assert parse_pathname("/plants/plant-01/plant-01-t1") == Route(
            name="transformer", plant_id="plant-01", transformer_id="plant-01-t1"
        )

    def test_the_root_landing_is_unchanged(self):
        assert parse_pathname("/").name == "overview"
        assert parse_pathname(None).name == "overview"


class TestLegacyDevicesRoutesAreUnchanged:
    def test_device_dashboard_route(self):
        route = parse_pathname("/devices/plant-01-t1-d1")
        assert route == Route(name="device", device_id="plant-01-t1-d1")

    def test_technician_devices_route(self):
        assert parse_pathname("/devices") == Route(name="technician_devices")

    @pytest.mark.parametrize("path", ["/devices", "/devices/plant-01-t1-d1"])
    def test_devices_are_not_redirected(self, path):
        """No approved synthetic-device-id-to-client-UID mapping exists."""
        assert legacy_redirect_path(path) is None


# ---------------------------------------------------------------------------
# The compatibility mapping
# ---------------------------------------------------------------------------


class TestLegacyRedirectPath:
    @pytest.mark.parametrize("path", ["/plants", "/plants/"])
    def test_the_legacy_list_maps_to_the_canonical_list(self, path):
        assert legacy_redirect_path(path) == RTL_LIST_PATH

    @pytest.mark.parametrize(
        "path",
        [None, "", "/", "/rtls", "/rtls/", "/plants/plant-01", "/plants/p/t",
         "/plantsx", "/PLANTS", "/admin/devices", "/login", "/logout"],
    )
    def test_nothing_else_is_rewritten(self, path):
        assert legacy_redirect_path(path) is None


class TestQueryPreservation:
    @pytest.mark.parametrize("search", [None, "", "?"])
    def test_no_query_gives_the_bare_path(self, search):
        assert rtl_list_href(search) == "/rtls"

    @pytest.mark.parametrize(
        "search,expected",
        [
            ("filter=mapped", "/rtls?filter=mapped"),
            ("?filter=mapped", "/rtls?filter=mapped"),
            ("a=1&b=2", "/rtls?a=1&b=2"),
        ],
    )
    def test_a_query_is_carried_verbatim(self, search, expected):
        assert rtl_list_href(search) == expected

    def test_a_query_cannot_change_the_destination_path(self):
        for hostile in ("//evil.example", "/../admin", "https://evil.example/"):
            assert rtl_list_href(hostile).startswith("/rtls?")


# ---------------------------------------------------------------------------
# HTTP redirect — full page loads of the legacy address
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    return app_module.server.test_client()


class TestHttpRedirect:
    @pytest.mark.parametrize("path", ["/plants", "/plants/"])
    def test_a_full_load_of_plants_redirects_to_rtls(self, client, path):
        response = client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"] == "/rtls"

    def test_the_query_string_survives_the_redirect(self, client):
        response = client.get("/plants?filter=mapped&x=1")
        assert response.status_code == 302
        assert response.headers["Location"] == "/rtls?filter=mapped&x=1"

    def test_the_redirect_is_temporary(self, client):
        """A browser caches 301/308 indefinitely; a later gate may need the
        address back."""
        assert client.get("/plants").status_code not in (301, 308)

    @pytest.mark.parametrize(
        "path", ["/rtls", f"/rtls/{A_UID}", "/plants/plant-01", "/devices/plant-01-t1-d1"]
    )
    def test_other_paths_are_served_by_dash(self, client, path):
        response = client.get(path)
        assert response.status_code == 200
        assert "Location" not in response.headers

    def test_the_redirect_reads_no_session_and_no_data(self, client, monkeypatch):
        """It only names an address; `/rtls` is authorized when it is routed."""
        def _forbidden(*_a, **_k):
            raise AssertionError("the legacy redirect must do no identity or data work")

        monkeypatch.setattr(routing, "current_identity", _forbidden)
        monkeypatch.setattr(routing, "current_device_scope", _forbidden)
        monkeypatch.setattr(fleet_overview, "get_real_fleet", _forbidden)
        assert client.get("/plants").status_code == 302

    def test_app_registers_the_redirect(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        assert "routing.register_legacy_redirects(server)" in source


# ---------------------------------------------------------------------------
# In-app compatibility — the Dash-side rewrite
# ---------------------------------------------------------------------------


class TestPathCommand:
    @pytest.fixture()
    def path_command(self, monkeypatch):
        def _forbidden(*_a, **_k):
            raise AssertionError("rewriting an address must consult no identity")

        monkeypatch.setattr(auth_callbacks.auth_service, "current_identity", _forbidden)
        monkeypatch.setattr(auth_callbacks.auth_service, "end_trusted_session", _forbidden)
        return _handler(auth_callbacks, "_path_command")

    @pytest.mark.parametrize("path", ["/plants", "/plants/"])
    def test_plants_is_rewritten_to_rtls(self, path_command, path):
        """Only the path is written. `url.search` is left as it was, so a
        query the legacy link carried is still on the URL at `/rtls`."""
        assert path_command(path) == (no_update, "/rtls")

    @pytest.mark.parametrize(
        "path", ["/rtls", f"/rtls/{A_UID}", "/plants/plant-01", "/devices/x", "/"]
    )
    def test_other_paths_are_left_alone(self, path_command, path):
        assert path_command(path) == (no_update, no_update)


class TestRouterIgnoresTheAlias:
    @pytest.fixture()
    def route_to_page(self, monkeypatch):
        return _handler(routing, "route_to_page")

    @pytest.mark.parametrize("path", ["/plants", "/plants/"])
    def test_the_alias_renders_nothing_and_reads_nothing(self, route_to_page, monkeypatch, path):
        """No page, no page-context, no session, no scope. With no
        page-context written, the Fleet callback cannot fire for `/plants`,
        so the redirect cannot cause a second Fleet load."""
        def _forbidden(*_a, **_k):
            raise AssertionError("the alias must do no identity, scope or data work")

        monkeypatch.setattr(routing, "current_identity", _forbidden)
        monkeypatch.setattr(routing, "current_device_scope", _forbidden)
        monkeypatch.setattr(routing, "may_view_real_fleet", _forbidden)
        assert route_to_page(path, "?filter=x", {}) == (no_update, no_update)

    @pytest.mark.parametrize("role", [ADMINISTRATOR, GENERAL, TECHNICIAN])
    def test_rtls_renders_the_directory_for_every_role_as_before(
        self, route_to_page, monkeypatch, role
    ):
        """`overview` was open to every role, and the Technician's restriction
        is applied inside the page by scope (see TestTechnicianRestriction).
        Both are exactly as they were at `/plants`."""
        monkeypatch.setattr(routing, "current_identity", lambda: _user(role))
        monkeypatch.setattr(routing, "current_device_scope", lambda: UNRESTRICTED)
        layout, context = route_to_page("/rtls", "", {})
        assert context["route"] == "overview"
        assert "page--fleet-overview" in layout.className

    def test_rtls_needs_a_session(self, route_to_page, monkeypatch):
        monkeypatch.setattr(routing, "current_identity", lambda: None)
        layout, context = route_to_page("/rtls", "", {})
        assert context == {}
        assert "page--fleet-overview" not in (getattr(layout, "className", "") or "")

    def test_an_unsupported_role_is_forbidden_at_rtls(self, route_to_page, monkeypatch):
        monkeypatch.setattr(routing, "current_identity", lambda: _user("superuser"))
        _layout, context = route_to_page("/rtls", "", {})
        assert context == {"route": "forbidden"}

    def test_the_technician_is_still_refused_the_detail(self, route_to_page, monkeypatch):
        monkeypatch.setattr(routing, "current_identity", lambda: _user(TECHNICIAN))
        monkeypatch.setattr(routing, "current_device_scope", lambda: DeviceScope(frozenset()))
        _layout, context = route_to_page(f"/rtls/{A_UID}", "", {})
        assert context == {"route": "forbidden"}

    def test_the_rebuild_still_carries_every_route_field(self):
        """RTL-UID-DETAIL-01's safeguard, restated for this gate: the router's
        `Route(...)` rebuild names every dataclass field, so the alias check
        added before it cannot have hidden a dropped identity."""
        tree = ast.parse(inspect.getsource(routing))
        rebuilds = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "Route"
        ]
        assert rebuilds, "the router no longer rebuilds Route — update this guard"
        expected = {f.name for f in fields(Route)}
        for call in rebuilds:
            assert {kw.arg for kw in call.keywords} == expected


# ---------------------------------------------------------------------------
# Authorization — identical to the directory's policy before the move
# ---------------------------------------------------------------------------


class TestAuthorizationUnchanged:
    def test_rtls_uses_the_existing_overview_policy(self):
        route = parse_pathname(RTL_LIST_PATH).name
        assert route == "overview"
        for role in (ADMINISTRATOR, GENERAL, TECHNICIAN):
            assert may_access_route(role, route) is True
        assert may_access_route(None, route) is False
        assert may_access_route("superuser", route) is False

    def test_the_alias_is_not_an_application_route(self):
        """Like `unknown`, it names no page, so the policy never mentions it —
        there is nothing behind it to authorize."""
        assert RTL_LIST_ALIAS_ROUTE not in ROUTE_POLICY
        assert RTL_LIST_ALIAS_ROUTE not in NAV_KEY_BY_ROUTE

    def test_no_new_policy_entry_was_added(self):
        assert set(ROUTE_POLICY) == {
            "overview", "plant", "transformer", "device", "rtl_detail",
            "notifications", "reports", "admin_devices", "technician_devices",
            "admin_assignments", "device_register", "admin_users", "audit_log",
            "admin_settings", "command_center",
        }


class TestTechnicianRestriction:
    """The Technician's restriction on the directory is the Fleet callback's
    scope check. It keys on page-context, not on the address, so it applies
    at `/rtls` exactly as it did at `/plants`."""

    def _context_for(self, path: str) -> dict:
        return {"route": parse_pathname(path).name}

    def test_technician_at_rtls_gets_the_restricted_panel_and_no_read(self):
        def _no_read():
            raise AssertionError("the client RTL source must not be read for a Technician")

        outputs = fleet_overview.populate(
            self._context_for("/rtls"), fetch=_no_read, scope_for=lambda: EMPTY
        )
        stats, refreshed, listing, error, options = outputs
        assert (stats, refreshed, error, options) == (None, None, None, [])
        assert listing is not no_update

    def test_the_alias_context_never_reaches_the_fleet_callback(self):
        """If `/plants` ever produced page-context it would be this — and the
        Fleet callback would ignore it, reading nothing."""
        def _no_read():
            raise AssertionError("the alias must not load the fleet")

        outputs = fleet_overview.populate(
            self._context_for("/plants"), fetch=_no_read, scope_for=lambda: UNRESTRICTED
        )
        assert outputs == (no_update,) * fleet_overview.OUTPUTS


# ---------------------------------------------------------------------------
# One Fleet data path
# ---------------------------------------------------------------------------


class TestOneFleetPath:
    def test_the_fleet_callback_serves_the_canonical_route(self):
        assert fleet_overview.ROUTE == parse_pathname(RTL_LIST_PATH).name

    def test_rtls_loads_the_fleet_exactly_once(self):
        calls = []

        def _fetch():
            calls.append(1)
            raise RuntimeError("stop after counting")

        fleet_overview.populate(
            {"route": parse_pathname("/rtls").name}, fetch=_fetch, scope_for=lambda: UNRESTRICTED
        )
        assert len(calls) == 1

    def test_one_page_module_and_one_callback_own_the_directory(self):
        """No second list page or callback was created for the new address."""
        owners = [
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / "callbacks").glob("*.py")
            if "get_real_fleet" in p.read_text(encoding="utf-8")
        ]
        assert owners == ["callbacks/fleet_overview.py"]
        pages_with_list = [
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / "pages").glob("*.py")
            if '"Registered RTLs"' in p.read_text(encoding="utf-8")
            and "fleet-overview-list" in p.read_text(encoding="utf-8")
        ]
        assert pages_with_list == ["pages/plants_overview.py"]


# ---------------------------------------------------------------------------
# Navigation and links — nothing new points at the legacy address
# ---------------------------------------------------------------------------


class TestNavigationAndLinks:
    def test_the_sidebar_item_points_at_rtls(self):
        items = {key: (label, href) for _t, group in SIDEBAR_SECTIONS for key, label, href, _i in group}
        assert items["overview"] == ("Registered RTLs", "/rtls")

    def test_no_other_sidebar_item_changed_destination(self):
        items = {key: href for _t, group in SIDEBAR_SECTIONS for key, _l, href, _i in group}
        assert items["devices"] == "/admin/devices"
        assert items["technician_devices"] == "/devices"
        assert items["command_center"] == "/command-center"

    def test_the_rtls_path_highlights_registered_rtls(self):
        from callbacks.navigation import active_nav_key

        assert active_nav_key("/rtls", GENERAL) == "overview"
        assert active_nav_key("/rtls/", GENERAL) == "overview"

    def test_detail_breadcrumb_returns_to_rtls(self):
        from tests.dash_tree import find_by_class

        crumb = find_by_class(rtl_detail.layout(A_UID), "breadcrumb")[0]
        assert "/rtls" in _hrefs(crumb)

    def test_the_not_registered_panel_returns_to_rtls(self):
        assert _hrefs(rtl_detail_ui.not_registered_panel(A_UID)) == ["/rtls"]

    def test_the_refresh_link_reloads_rtls(self):
        assert "/rtls" in _hrefs(plants_overview.layout())

    def test_fleet_rows_link_to_rtls_uid(self):
        from datetime import datetime
        from decimal import Decimal

        from repositories.rtl_temperature_repository import RTLLatestTemperature
        from services.rtl_fleet_service import FleetStatus, RealFleet, build_rows, summarise

        rows = build_rows(
            [A_UID],
            {A_UID: RTLLatestTemperature(
                A_UID, datetime(2022, 9, 18, 20, 20), Decimal("29.0"), 1, (Decimal("29.0"),)
            )},
            {},
            {},
        )
        fleet = RealFleet(FleetStatus.DATA, rows, summarise(rows))
        hrefs = _hrefs(rtl_fleet.fleet_table(rtl_fleet.filter_rows(fleet, rtl_fleet.FILTER_ALL)))
        assert hrefs == [f"/rtls/{A_UID}"]

    @pytest.mark.parametrize(
        "layout",
        [
            pytest.param(lambda: plants_overview.layout(), id="registered-rtls"),
            pytest.param(lambda: rtl_detail.layout(A_UID), id="rtl-detail"),
            pytest.param(lambda: rtl_detail_ui.not_registered_panel(A_UID), id="not-registered"),
            pytest.param(forbidden_panel, id="forbidden"),
            pytest.param(lambda: not_found_panel("page"), id="not-found"),
            pytest.param(lambda: plant_detail.layout("P"), id="plant"),
            pytest.param(lambda: transformer_detail.layout("P", "T", "p1"), id="transformer"),
            pytest.param(lambda: transformer_detail.layout("P", "T", None), id="transformer-no-plant"),
            pytest.param(lambda: device_dashboard.layout(plant_name="P", transformer_code="T", device_code="D"), id="device"),
        ],
    )
    def test_no_rendered_link_targets_the_legacy_address(self, layout):
        assert not any(_is_legacy(h) for h in _hrefs(layout()))

    def test_no_application_source_builds_the_legacy_address(self):
        """`/plants` may be spelled exactly once — as the compatibility
        constant. Any other string equal to it is a new link to an old path.
        Checked on string constants, so the synthetic `/plants/<id>` f-strings
        (a different route) are not caught by it."""
        offenders = []
        for directory in ("components", "pages", "callbacks", "services"):
            for path in (ROOT / directory).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                fstring_parts = {
                    id(part)
                    for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)
                    for part in node.values
                }
                for node in ast.walk(tree):
                    if id(node) in fstring_parts:
                        continue
                    if isinstance(node, ast.Constant) and node.value in ("/plants", "/plants/"):
                        offenders.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
        assert offenders == []

    def test_the_sidebar_imports_the_canonical_constant(self):
        source = (ROOT / "components" / "app_sidebar.py").read_text(encoding="utf-8")
        assert "RTL_LIST_PATH" in source


# ---------------------------------------------------------------------------
# Terminology at the canonical address
# ---------------------------------------------------------------------------


class TestTerminology:
    def test_the_canonical_page_is_registered_rtls(self):
        from tests.dash_tree import text_of

        text = text_of(plants_overview.layout())
        assert "Registered RTLs" in text
        for word in ("Plant Overview", "Plants", "Fleet Overview"):
            assert word not in text
