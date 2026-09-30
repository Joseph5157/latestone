"""Route registration.

URL parsing/building lives in the top-level `routes` module so components can
share it; the names are re-exported here for existing callers.
"""
from __future__ import annotations

import logging

from dash import Input, Output, html, no_update
from flask import redirect, request

from components.status_panels import error_panel, forbidden_panel, not_found_panel
from pages import admin_settings, audit_log, plants_overview, plant_detail, transformer_detail, device_dashboard, device_admin, device_register, technician_devices, admin_assignments, notifications, user_admin, report_center, command_center, rtl_detail, rtl_network, rtl_dashboard, historical_events, rtl_assignments
from pages.placeholder import placeholder_layout
from routes import (
    LEGACY_RTL_LIST_PATH,
    RTL_LIST_ALIAS_ROUTE,
    Route,
    device_href,
    parse_custom_range,
    parse_pathname,
    parse_query, parse_rtl_uid,
    rtl_list_href,
)
from services import hierarchy_service
from services.hierarchy_service import entity_in_scope
from callbacks.auth import LOGIN_PATH
from services.auth_service import AuthenticatedUser, current_identity
from services.authorization import (
    ADMINISTRATOR,
    ROUTE_POLICY,
    TECHNICIAN,
    may_access_route,
)
from services.device_scope import DeviceScope, current_device_scope
from services.rtl_fleet_service import may_view_real_fleet
from services.rtl_scope import current_rtl_scope, is_assigned_only

#: What the router should do with a request, decided before anything renders.
DECISION_LOGIN = "login"
DECISION_FORBIDDEN = "forbidden"
DECISION_ALLOW = "allow"

#: Routes whose destination page is not built yet. Each renders the same
#: minimal placeholder with its title and a one-sentence purpose. Purpose text
#: stays neutral on purpose: no report types, notification behaviours, roles or
#: device fields are asserted until the client approves the frontend scope.
PLACEHOLDER_PAGES: dict[str, tuple[str, str]] = {}

__all__ = [
    "Route", "parse_pathname", "parse_query", "parse_custom_range",
    "device_href", "register",
]

logger = logging.getLogger(__name__)


def build_device_context(device_path, metric_key: str, period_value: str) -> dict:
    """page-context for a device route.

    Carries the full `DevicePath`, not just the display names. The parent ids
    were previously dropped here, which is why the device breadcrumb could not
    link back up the hierarchy and the equipment context bar could not show
    administrative status.
    """
    return {
        "route": "device",
        "device_id": device_path.device_id,
        "plant_id": device_path.plant_id,
        "plant_name": device_path.plant_name,
        "transformer_id": device_path.transformer_id,
        "transformer_code": device_path.transformer_code,
        "device_code": device_path.device_code,
        "device_status": device_path.device_status,
        "metric_key": metric_key,
        "period": period_value,
    }


def route_decision(user: AuthenticatedUser | None, route_name: str) -> str:
    """Login, forbidden, or allow — decided before any page is built (ROLE-2).

    AUTH-HARDEN-1: takes the CURRENT TRUSTED identity directly, never the
    browser's `auth-store` payload. `route_to_page` below resolves it exactly
    once, via `current_identity()`, and passes it in — the same identity the
    scope calculation for this render uses, so the two cannot disagree about
    who is asking.

    THREE OUTCOMES, KEPT APART ON PURPOSE:

    * No trusted identity -> login. This covers a visitor who never signed in
      AND a session the server no longer recognises (deleted, deactivated, or
      simply expired) — both read the same way to the operator: sign in
      (again). Neither has been refused anything they asked for.
    * A real identity, route not permitted -> forbidden. Explicit, per the
      ROLE-1 decision that an authenticated user reaching for a resource they
      are not entitled to must never be folded into the same silent outcome as
      a bad identifier.
    * Anything else -> allow, including `unknown`. A route the policy does not
      mention is not the policy's business here: `unknown` means no such page,
      and refusing it would make every typo'd URL imply something exists behind
      it. Application routes are all in `ROUTE_POLICY`, and one missing from it
      is denied — the test suite fails when a route ships without an entry, so
      the omission is caught before it can widen access.

    A browser-edited `role` cannot reach here at all: there is no `role` field
    on `user` that came from anywhere but the CURRENT `users` row.
    """
    if user is None:
        return DECISION_LOGIN
    if route_name not in ROUTE_POLICY:
        return DECISION_ALLOW

    if may_access_route(user.role, route_name):
        return DECISION_ALLOW

    logger.warning(
        "Route %r refused for session role %r",
        route_name,
        user.role,
    )
    return DECISION_FORBIDDEN


#: AUTH-HARDEN-1R: moved to `services/hierarchy_service.py` so
#: `callbacks/listings.py` can reuse the SAME predicate for its own
#: independently-invokable plant/transformer detail callbacks, rather than
#: a second implementation. Re-exported here unchanged — `routing.
#: entity_in_scope(...)` and every call site below still work exactly as
#: before.


#: Roles whose landing page is the Command Center (redesign decision D3).
_COMMAND_CENTER_LANDING_ROLES = frozenset({ADMINISTRATOR, TECHNICIAN})


def landing_route_name(route_name: str, pathname: str | None, role: str | None) -> str:
    """The route a landing path renders for this role (CC-NEW-1, redesign D3).

    Two paths are landing paths and nothing else changes: the bare root, and
    `/login`. Administrators and Technicians land on the Command Center,
    everyone else on Fleet Overview. `/rtls` is Registered RTLs for every
    role, so the sidebar's Registered RTLs link always works.

    Signing in still does not redirect, so a deep link survives it — this is
    what "after login" means only for someone who signed in at one of those
    two paths, which are the two that name no page of their own.
    """
    if role is not None and pathname == LOGIN_PATH:
        # `/login` is not a route — `parse_pathname` returns `unknown` — so
        # without this an operator who signs in AT `/login` is answered with
        # the not-found panel for succeeding. `callbacks.auth`'s redirect
        # cannot cover this one: signing in changes `auth-store`, not the
        # pathname, so a URL-driven callback never fires. Different event,
        # not the same bug twice.
        #
        # Falls through to Fleet Overview rather than `route_name` for a
        # General User: they have no Command Center, but they do have
        # somewhere to land.
        if role in _COMMAND_CENTER_LANDING_ROLES:
            return "command_center"
        return "overview"
    if pathname in (None, "", "/") and role in _COMMAND_CENTER_LANDING_ROLES:
        return "command_center"
    return route_name


def legacy_rtl_list_redirect():
    """HTTP 302 from the legacy list address to the canonical one.

    RTL-LIST-ROUTE-01. A full page load of `/plants` — a bookmark, a typed
    address, a shared link — is answered by the server before Dash renders
    anything, so the client RTL source is never read on the way through.

    An HTTP redirect rather than only Dash's in-page one: `dcc.Location`
    (Dash 2.17) can only `pushState`, never `replaceState`, so a Dash-side
    rewrite leaves `/plants` in the history and Back returns to it — which
    redirects forward again. A 302 replaces the entry, so Back leaves.
    Temporary (302), not permanent: a browser caches a 301/308 indefinitely,
    and a later gate may yet need this address for something else.

    Authorization is not decided here and cannot be bypassed here: this only
    names an address. `/rtls` is then routed like any other request, through
    `route_decision` and the Fleet page's own scope check.
    """
    return redirect(rtl_list_href(request.query_string.decode("latin-1")), code=302)


def register_legacy_redirects(server) -> None:
    """Attach the compatibility redirects to the Flask server Dash runs on.

    Both spellings are registered explicitly. A static Werkzeug rule outranks
    Dash's own `/<path:path>` catch-all, so neither reaches Dash's index.
    """
    for rule in (LEGACY_RTL_LIST_PATH, f"{LEGACY_RTL_LIST_PATH}/"):
        server.add_url_rule(
            rule,
            endpoint=f"legacy_rtl_list{rule.count('/')}",
            view_func=legacy_rtl_list_redirect,
        )


def register(app) -> None:
    """Register the top-level router callback on the Dash app."""

    @app.callback(
        Output("page-content", "children"),
        Output("page-context", "data"),
        Input("url", "pathname"),
        Input("url", "search"),
        Input("auth-store", "data"),
    )
    def route_to_page(pathname, search, auth_data):
        try:
            route = parse_pathname(pathname)

            # RTL-LIST-ROUTE-01. The legacy list address renders nothing and
            # reads nothing — not even the session. It only arrives here on
            # an in-app navigation (a full load is redirected by the server
            # first), and `callbacks.auth._path_command` is rewriting the URL
            # to `/rtls` in the same round trip; this callback then runs again
            # for `/rtls`, where authorization and the one Fleet load happen.
            # Rendering the list here too would load the fleet twice.
            if route.name == RTL_LIST_ALIAS_ROUTE:
                return no_update, no_update

            # AUTH-HARDEN-1: resolved ONCE, from the trusted server session —
            # never from `auth_data`, which stays an Input only so this
            # callback still re-renders the instant login/logout happens.
            # Both the route decision and the scope below reason about this
            # SAME identity, so they cannot disagree about who is asking.
            user = current_identity()
            route = Route(
                name=landing_route_name(
                    route.name, pathname, user.role if user is not None else None
                ),
                plant_id=route.plant_id,
                transformer_id=route.transformer_id,
                device_id=route.device_id,
                # Every identity field the parser set must be carried through
                # this rebuild. Omitting one silently blanks it — `rtl_uid`
                # was dropped here once and the detail page rendered
                # "RTL UID None" with no error anywhere.
                rtl_uid=route.rtl_uid,
            )

            # Authorization runs here, BEFORE any hierarchy lookup below. A
            # refused page must do no data work on the way to being refused:
            # queries run on behalf of someone not entitled to ask are each a
            # place a partial result can reach a log or an error message.
            decision = route_decision(user, route.name)
            if decision == DECISION_LOGIN:
                from pages.login import login_layout
                return login_layout(), {}
            if decision == DECISION_FORBIDDEN:
                # `{"route": "forbidden"}` rather than the real route name, so
                # every listing callback — all of which branch on this key —
                # simply never fires for a page that was refused.
                return forbidden_panel(), {"route": "forbidden"}

            # Resolved ONCE per render and passed down. `current_device_scope`
            # performs an assignment read for technicians, so calling it per
            # entity would turn one render into a query storm.
            scope = current_device_scope()

            metric_key, period_value = parse_query(search)
            custom_start, custom_end = parse_custom_range(search)

            if route.name == "overview":
                ctx = {"route": "overview", "metric_key": metric_key, "period": period_value}
                # ADR-032: a Technician's list is "Assigned RTLs"; the data
                # itself is scoped by the callback, not by this label.
                return plants_overview.layout(
                    assigned_only=user.role == TECHNICIAN
                ), ctx

            if route.name == "plant":
                # AUTH-HARDEN-1R2: scope is checked BEFORE the existence
                # lookup. `entity_in_scope` runs a scope-FILTERED query, so a
                # nonexistent plant and a real-but-out-of-scope plant both
                # simply come back False — a restricted (Technician) caller
                # gets the identical `forbidden_panel` for either, with no
                # unrestricted lookup ever run to tell the two apart. For an
                # unrestricted scope (Administrator/General) this check is a
                # free no-op (`entity_in_scope` short-circuits True without a
                # query), so their behaviour is unchanged.
                if not entity_in_scope(scope, plant_id=route.plant_id):
                    logger.warning(
                        "Plant %r refused: not visible in the session's device scope",
                        route.plant_id,
                    )
                    return forbidden_panel(), {"route": "forbidden"}

                plant = hierarchy_service.get_plant_or_none(route.plant_id)
                if plant is None:
                    return not_found_panel("plant"), {"route": "unknown"}

                ctx = {
                    "route": "plant",
                    "plant_id": plant.plant_id,
                    "plant_name": plant.name,
                    "metric_key": metric_key,
                    "period": period_value,
                }
                return plant_detail.layout(plant.name, status=plant.status), ctx

            if route.name == "transformer":
                # AUTH-HARDEN-1R2: same reorder as the plant branch above —
                # scope first, on the URL's own transformer_id, before any
                # unrestricted plant/transformer lookup. `entity_in_scope`'s
                # transformer branch is itself scope-filtered, so it cannot
                # be used to probe whether an out-of-scope transformer (or
                # its parent plant) exists.
                if not entity_in_scope(scope, transformer_id=route.transformer_id):
                    logger.warning(
                        "Transformer %r refused: not visible in the session's device scope",
                        route.transformer_id,
                    )
                    return forbidden_panel(), {"route": "forbidden"}

                plant = hierarchy_service.get_plant_or_none(route.plant_id)
                if plant is None:
                    return not_found_panel("plant"), {"route": "unknown"}

                transformer = hierarchy_service.get_transformer_in_plant(
                    route.plant_id, route.transformer_id
                )
                if transformer is None:
                    return not_found_panel("transformer"), {"route": "unknown"}

                ctx = {
                    "route": "transformer",
                    "plant_id": plant.plant_id,
                    "plant_name": plant.name,
                    "transformer_id": transformer.transformer_id,
                    "transformer_code": transformer.transformer_code,
                    "metric_key": metric_key,
                    "period": period_value,
                }
                return (
                    transformer_detail.layout(
                        plant.name, transformer.transformer_code, plant.plant_id,
                        status=transformer.status,
                    ),
                    ctx,
                )

            if route.name == "device":
                # AUTH-HARDEN-1R2: same reorder. For a device, the scope
                # check is a pure in-memory membership test against the
                # Technician's assigned-device set (`DeviceScope.allows`) —
                # no query at all — so checking it first costs nothing and
                # closes the same oracle for device IDs.
                if not entity_in_scope(scope, device_id=route.device_id):
                    logger.warning(
                        "Device %r refused: not visible in the session's device scope",
                        route.device_id,
                    )
                    return forbidden_panel(), {"route": "forbidden"}

                device_ctx = hierarchy_service.get_device_context(route.device_id)
                if device_ctx is None:
                    return not_found_panel("device"), {"route": "unknown"}

                ctx = build_device_context(device_ctx, metric_key, period_value)
                rtl_uid = parse_rtl_uid(search)
                # There is no approved raw-UID-to-app-device authorization map.
                # Restrict this temporary vertical slice to Administrators on an
                # already in-scope dashboard route; never widen technician scope.
                if rtl_uid is not None and user.role == ADMINISTRATOR:
                    ctx["rtl_uid"] = rtl_uid
                return (
                    device_dashboard.layout(
                        plant_name=device_ctx.plant_name,
                        transformer_code=device_ctx.transformer_code,
                        device_code=device_ctx.device_code,
                        metric_key=metric_key,
                        period=period_value,
                        custom_start=custom_start,
                        custom_end=custom_end,
                        plant_id=device_ctx.plant_id,
                        transformer_id=device_ctx.transformer_id,
                        device_status=device_ctx.device_status,
                    ),
                    ctx,
                )

            if route.name == "rtl_detail":
                # RTL-UID-DETAIL-01. Two independent gates, both already
                # passed before a single client SQL Server row is read:
                #
                # 1. `route_decision` above, against ROUTE_POLICY — which
                #    excludes the Technician, so typing a UID cannot be used
                #    to get around the Fleet page's restriction.
                # 2. The same device-scope predicate the Fleet page itself
                #    uses, below. It is not redundant: the policy answers "may
                #    this ROLE open the route", the scope answers "may THIS
                #    SESSION see raw client RTL facts". A future scope change
                #    must not silently widen this page.
                #
                # Registration is checked after both, inside the service, and
                # is what decides between a real RTL and not-found.
                #
                # ADR-032: the RTL UID scope is checked here, BEFORE the page
                # is built or any client SQL Server row is read. A Technician
                # reaches only a UID currently assigned to them; an
                # unassigned, another Technician's, an unregistered and a
                # malformed-but-numeric UID are all the same "forbidden".
                rtl_scope = current_rtl_scope()
                if not may_view_real_fleet(rtl_scope) or not rtl_scope.allows(route.rtl_uid):
                    logger.warning("RTL detail refused: UID outside the session's RTL scope")
                    return forbidden_panel(), {"route": "forbidden"}
                ctx = {"route": "rtl_detail", "rtl_uid": route.rtl_uid}
                return rtl_detail.layout(route.rtl_uid), ctx

            if route.name == "rtl_network":
                # LATEST-NETWORK-CONTEXT-01. Same two gates as rtl_detail: the
                # role policy above, then the device scope that decides who
                # may read raw client RTL facts. A Technician gets neither.
                if not may_view_real_fleet(current_rtl_scope()):
                    logger.warning(
                        "RTL network refused: session scope may not view client RTL facts"
                    )
                    return forbidden_panel(), {"route": "forbidden"}
                return rtl_network.layout(), {"route": "rtl_network"}

            if route.name == "historical_events":
                # HISTORICAL-EVENTS-01. Same two gates as rtl_network: the role
                # policy, then the device scope that decides who may read raw
                # client RTL facts. No event source is read before both pass.
                if not may_view_real_fleet(current_rtl_scope()):
                    logger.warning(
                        "Historical events refused: session scope may not view client RTL facts"
                    )
                    return forbidden_panel(), {"route": "forbidden"}
                return historical_events.layout(), {"route": "historical_events"}

            if route.name == "admin_devices":
                ctx = {"route": "admin_devices"}
                return device_admin.layout(), ctx

            if route.name == "technician_devices":
                ctx = {"route": "technician_devices"}
                return technician_devices.layout(), ctx

            if route.name == "rtl_assignments":
                return rtl_assignments.layout(), {"route": "rtl_assignments"}

            if route.name == "admin_assignments":
                ctx = {"route": "admin_assignments"}
                return admin_assignments.layout(), ctx

            if route.name == "device_register":
                ctx = {"route": "device_register"}
                return device_register.layout(), ctx

            if route.name == "admin_users":
                ctx = {"route": "admin_users"}
                return user_admin.layout(), ctx

            if route.name == "audit_log":
                ctx = {"route": "audit_log"}
                return audit_log.layout(), ctx

            if route.name == "admin_settings":
                ctx = {"route": "admin_settings"}
                return admin_settings.layout(), ctx

            if route.name == "reports":
                ctx = {"route": "reports"}
                return report_center.layout(), ctx

            if route.name == "notifications":
                ctx = {"route": "notifications"}
                return notifications.layout(), ctx

            if route.name == "command_center":
                # FACTUAL-DASHBOARD-01 / ADR-032. Administrator and Technician
                # both land on the factual dashboard; a Technician's counts
                # cover their assigned RTLs only (the callback scopes them).
                # The synthetic Command Center below is no longer reachable
                # from production routing for either role (legacy debt).
                rtl_scope = current_rtl_scope()
                if may_view_real_fleet(rtl_scope):
                    return (
                        rtl_dashboard.layout(assigned_only=is_assigned_only(rtl_scope)),
                        {"route": "rtl_dashboard"},
                    )
                return command_center.layout(), {"route": "command_center"}

            if route.name in PLACEHOLDER_PAGES:
                title, purpose = PLACEHOLDER_PAGES[route.name]
                ctx = {"route": route.name}
                return placeholder_layout(title, purpose), ctx

            return not_found_panel("page"), {"route": "unknown"}

        except Exception:
            # Logged in full so programming errors are diagnosable; the UI panel
            # stays generic and never exposes internals.
            logger.exception("Routing failed for pathname=%r search=%r", pathname, search)
            return error_panel(), {"route": "unknown"}
