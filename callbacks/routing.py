"""Route registration.

URL parsing/building lives in the top-level `routes` module so components can
share it; the names are re-exported here for existing callers.
"""
from __future__ import annotations

import logging

from dash import Input, Output, html

from components.status_panels import error_panel, forbidden_panel, not_found_panel
from pages import audit_log, plants_overview, plant_detail, transformer_detail, device_dashboard, device_admin, device_register, technician_devices, admin_assignments, notifications, user_admin, report_center, command_center, command_center_locations
from pages.placeholder import placeholder_layout
from routes import (
    Route,
    device_href,
    parse_custom_range,
    parse_pathname,
    parse_plant_selection,
    parse_query,
)
from services import hierarchy_service
from services.hierarchy_service import entity_in_scope
from services.auth_service import AuthenticatedUser, current_identity
from services.authorization import ROUTE_POLICY, may_access_route
from services.device_scope import DeviceScope, current_device_scope

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

            # AUTH-HARDEN-1: resolved ONCE, from the trusted server session —
            # never from `auth_data`, which stays an Input only so this
            # callback still re-renders the instant login/logout happens.
            # Both the route decision and the scope below reason about this
            # SAME identity, so they cannot disagree about who is asking.
            user = current_identity()

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
                return plants_overview.layout(), ctx

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

            if route.name == "admin_devices":
                ctx = {"route": "admin_devices"}
                return device_admin.layout(), ctx

            if route.name == "technician_devices":
                ctx = {"route": "technician_devices"}
                return technician_devices.layout(), ctx

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

            if route.name == "reports":
                ctx = {"route": "reports"}
                return report_center.layout(), ctx

            if route.name == "notifications":
                ctx = {"route": "notifications"}
                return notifications.layout(), ctx

            if route.name == "command_center":
                # The selected plant rides in page-context alongside the
                # route, the same way metric/period do for a device. The
                # panel callback then needs one input, not two, and cannot
                # fire for a search change on some other route.
                ctx = {
                    "route": "command_center",
                    "plant_id": parse_plant_selection(search),
                }
                return command_center.layout(), ctx

            if route.name == "command_center_locations":
                ctx = {"route": "command_center_locations"}
                return command_center_locations.layout(), ctx

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
