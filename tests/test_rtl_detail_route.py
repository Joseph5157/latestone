"""RTL-UID-DETAIL-01 — `/rtls/<uid>` parsing, identity and authorization.

The canonical real-client RTL detail route. Its identity is the numeric client
RTL UID from `dbo.device_list` — never a synthetic PostgreSQL `device_id`,
never a positional index, never a fuzzy mapping.

Two boundaries are asserted here and they are deliberately separate:

* **Parsing** decides whether a path names this route at all. A non-numeric or
  out-of-range segment is not a refused RTL, it is not this route — it must
  fall through to `unknown` so a typo keeps rendering not-found.
* **Authorization** decides whether the asking role may open it. It is
  `ROUTE_POLICY`, evaluated before any client SQL Server read, so a Technician
  typing a UID cannot use the route as an existence oracle for RTL facts.
"""
from __future__ import annotations

import pytest

from routes import Route, parse_pathname, rtl_detail_href
from services.authorization import (
    ADMINISTRATOR,
    GENERAL,
    ROUTE_POLICY,
    TECHNICIAN,
    may_access_route,
)

ROUTE_NAME = "rtl_detail"

#: A UID that exists in the registered directory today. Used only as a
#: well-formed path segment — nothing here reads the source.
A_UID = 29006


class TestPathParsing:
    def test_the_canonical_path_parses_to_the_rtl_detail_route(self):
        route = parse_pathname(f"/rtls/{A_UID}")
        assert route.name == ROUTE_NAME
        assert route.rtl_uid == A_UID

    def test_the_uid_is_an_integer_not_a_string(self):
        """The identity is numeric. A string would silently re-admit the
        synthetic `device_id` shape (`plant-01-t1-d1`) into this route."""
        route = parse_pathname(f"/rtls/{A_UID}")
        assert isinstance(route.rtl_uid, int)
        assert not isinstance(route.rtl_uid, bool)

    def test_a_trailing_slash_is_the_same_route(self):
        assert parse_pathname(f"/rtls/{A_UID}/").rtl_uid == A_UID

    @pytest.mark.parametrize(
        "path",
        [
            "/rtls/abc",
            "/rtls/29006abc",
            "/rtls/29006.5",
            "/rtls/-29006",
            "/rtls/ 29006",
            "/rtls/29006/history",
            "/rtls/plant-01-t1-d1",
            "/rtls/%2e%2e",
        ],
    )
    def test_a_malformed_uid_is_not_this_route(self, path):
        """Not "a refused RTL" — not this route at all, so the router keeps
        answering not-found rather than implying something exists behind it."""
        assert parse_pathname(path).name == "unknown"

    @pytest.mark.parametrize("path", ["/rtls/0", "/rtls/2147483648", "/rtls/99999999999"])
    def test_a_uid_outside_the_source_integer_range_is_not_this_route(self, path):
        """`device_uid` is a SQL Server `int`. A value it cannot hold can
        never name a registered RTL, so it is rejected before any query."""
        assert parse_pathname(path).name == "unknown"

    def test_unicode_digits_are_refused(self):
        """`str.isdigit()` accepts Arabic-Indic and superscript digits; `int()`
        accepts some of them too. The UID must be plain ASCII decimal."""
        assert parse_pathname("/rtls/٢٩").name == "unknown"
        assert parse_pathname("/rtls/29006²").name == "unknown"

    def test_the_bare_path_is_the_registered_directory(self):
        """Was `unknown` when this gate closed. RTL-LIST-ROUTE-01 made the
        bare `/rtls` the canonical list — the same `overview` route the
        directory always was — and it carries no UID."""
        for path in ("/rtls", "/rtls/"):
            route = parse_pathname(path)
            assert route.name == "overview"
            assert route.rtl_uid is None


class TestHrefBuilding:
    def test_the_href_is_the_canonical_path(self):
        assert rtl_detail_href(A_UID) == f"/rtls/{A_UID}"

    def test_the_href_round_trips_through_the_parser(self):
        assert parse_pathname(rtl_detail_href(A_UID)).rtl_uid == A_UID

    @pytest.mark.parametrize("bad", ["29006", None, 0, -1, 2**31, True, 1.0])
    def test_the_href_refuses_anything_that_is_not_a_source_uid(self, bad):
        """A link is built from a UID the source gave us. Accepting a string
        here is how a synthetic device id would end up in an /rtls URL."""
        with pytest.raises((TypeError, ValueError)):
            rtl_detail_href(bad)


class TestAuthorizationBoundary:
    """The Fleet restriction must not be bypassable by typing a detail URL."""

    def test_the_route_is_in_the_policy(self):
        """A route the router can produce but the policy never mentions is
        denied to everyone the moment it ships."""
        assert ROUTE_NAME in ROUTE_POLICY

    def test_administrator_may_open_it(self):
        assert may_access_route(ADMINISTRATOR, ROUTE_NAME) is True

    def test_general_user_may_open_it(self):
        assert may_access_route(GENERAL, ROUTE_NAME) is True

    def test_technician_passes_the_route_gate_but_only_the_scope_grants_a_uid(self):
        """ADR-032: the role gate admits a Technician; `services.rtl_scope`
        then admits only a UID currently assigned to them (before any read)."""
        assert may_access_route(TECHNICIAN, ROUTE_NAME) is True

    @pytest.mark.parametrize("role", [None, "", "superuser", "Administrator", 7, {}])
    def test_no_unrecognised_role_opens_it(self, role):
        assert may_access_route(role, ROUTE_NAME) is False

    def test_it_matches_the_fleet_page_visibility_rule(self):
        """The detail route and the Fleet page must agree about who sees
        client RTL facts, or one of them is the hole in the other."""
        from services.rtl_scope import DENIED as EMPTY, UNRESTRICTED, scope_for
        from services.auth_service import AuthenticatedUser
        from services.rtl_fleet_service import may_view_real_fleet

        for role in (ADMINISTRATOR, GENERAL):
            user = AuthenticatedUser(user_id=1, username="u", full_name="U", role=role)
            assert may_view_real_fleet(scope_for(user)) is True
            assert may_access_route(role, ROUTE_NAME) is True

        assert may_view_real_fleet(EMPTY) is False
        assert may_view_real_fleet(UNRESTRICTED) is True


class TestRouteIdentityIsNotTheSyntheticDevice:
    def test_the_legacy_device_route_is_retired_not_redirected(self):
        """LEGACY-SYNTHETIC-UX-CLEANUP-01: `/devices/<app-device-id>` is retired
        to the legacy panel. There is no approved synthetic-id-to-client-UID
        mapping, so it is NOT redirected to an RTL and resolves no identity —
        the synthetic device id is dropped and no `rtl_uid` is invented."""
        route = parse_pathname("/devices/plant-01-t1-d1")
        assert route.name == "legacy_retired"
        assert route.device_id is None
        assert route.rtl_uid is None

    def test_the_fleet_list_route_is_the_canonical_list(self):
        assert parse_pathname("/rtls").name == "overview"

    def test_an_rtl_route_carries_no_synthetic_hierarchy_identity(self):
        route = parse_pathname(f"/rtls/{A_UID}")
        assert route.plant_id is None
        assert route.transformer_id is None
        assert route.device_id is None

    def test_the_default_route_has_no_rtl_uid(self):
        assert Route(name="overview").rtl_uid is None


class TestTheRouterPreservesEveryIdentityField:
    """`route_to_page` rebuilds the parsed Route to apply landing-page rules.

    That rebuild lists its fields explicitly, so a new identity field is
    silently blanked unless it is added there too. `rtl_uid` was dropped on
    the first attempt and the page rendered "RTL UID None" — no exception, no
    failing unit test, because `parse_pathname` itself was correct. This pins
    the rebuild rather than the parser.
    """

    @staticmethod
    def _rebuilt(path: str) -> Route:
        from callbacks.routing import landing_route_name

        parsed = parse_pathname(path)
        return Route(
            name=landing_route_name(parsed.name, path, ADMINISTRATOR),
            plant_id=parsed.plant_id,
            transformer_id=parsed.transformer_id,
            device_id=parsed.device_id,
            rtl_uid=parsed.rtl_uid,
        )

    def test_the_rebuild_in_the_router_matches_this_field_list(self):
        """If `Route` gains a field, this test fails until the router's
        rebuild is updated — which is the failure that was missed."""
        import ast
        import inspect
        from dataclasses import fields

        import callbacks.routing as routing

        tree = ast.parse(inspect.getsource(routing))
        rebuilt_kwargs = {
            kw.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Route"
            for kw in node.keywords
        }
        assert rebuilt_kwargs == {f.name for f in fields(Route)}

    def test_a_rebuilt_rtl_route_keeps_its_uid(self):
        assert self._rebuilt(f"/rtls/{A_UID}").rtl_uid == A_UID

    def test_a_rebuilt_retired_device_route_carries_no_synthetic_identity(self):
        """LEGACY-SYNTHETIC-UX-CLEANUP-01: `/devices/<id>` parses to
        `legacy_retired` with the synthetic device id dropped, and the rebuild
        carries that through — no synthetic identity survives to a live page."""
        route = self._rebuilt("/devices/plant-01-t1-d1")
        assert route.name == "legacy_retired"
        assert route.device_id is None and route.rtl_uid is None

    def test_a_rebuilt_retired_transformer_route_carries_no_synthetic_identity(self):
        route = self._rebuilt("/plants/plant-01/plant-01-t1")
        assert route.name == "legacy_retired"
        assert (route.plant_id, route.transformer_id) == (None, None)
