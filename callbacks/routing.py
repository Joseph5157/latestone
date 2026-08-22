"""Route registration.

URL parsing/building lives in the top-level `routes` module so components can
share it; the names are re-exported here for existing callers.
"""
from __future__ import annotations

import logging

from dash import Input, Output, html

from components.status_panels import error_panel, forbidden_panel, not_found_panel
from pages import plants_overview, plant_detail, transformer_detail, device_dashboard, device_admin, device_register, notifications, user_admin, report_center
from pages.placeholder import placeholder_layout
from routes import Route, device_href, parse_custom_range, parse_pathname, parse_query
from services import hierarchy_service
from services.auth_service import from_session
from services.authorization import ROUTE_POLICY, may_access_route
from services.device_scope import DeviceScope, scope_from_session

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


def route_decision(auth_data, route_name: str) -> str:
    """Login, forbidden, or allow — decided before any page is built (ROLE-2).

    THREE OUTCOMES, KEPT APART ON PURPOSE:

    * Not signed in -> login. A visitor with no session has not been refused
      anything; they have not asked yet. "No access" would be both wrong and
      alarming.
    * Signed in, route not permitted -> forbidden. Explicit, per the ROLE-1
      decision that an authenticated user reaching for a resource they are not
      entitled to must never be folded into the same silent outcome as a bad
      identifier.
    * Anything else -> allow, including `unknown`. A route the policy does not
      mention is not the policy's business here: `unknown` means no such page,
      and refusing it would make every typo'd URL imply something exists behind
      it. Application routes are all in `ROUTE_POLICY`, and one missing from it
      is denied — the test suite fails when a route ships without an entry, so
      the omission is caught before it can widen access.

    A session that is authenticated but carries no usable identity (the
    pre-ROLE-1 `{"authenticated": True}` payload, or a tampered role) reaches
    the routes nobody may have: `from_session` returns None and every policied
    route is refused.
    """
    if not auth_data or not auth_data.get("authenticated"):
        return DECISION_LOGIN
    if route_name not in ROUTE_POLICY:
        return DECISION_ALLOW

    user = from_session(auth_data)
    if user is not None and may_access_route(user.role, route_name):
        return DECISION_ALLOW

    logger.warning(
        "Route %r refused for session role %r",
        route_name,
        user.role if user else None,
    )
    return DECISION_FORBIDDEN


def entity_in_scope(
    scope: DeviceScope,
    *,
    device_id: str | None = None,
    plant_id: str | None = None,
    transformer_id: str | None = None,
) -> bool:
    """Whether a resolved entity is visible to `scope`.

    EXISTENCE IS CHECKED FIRST, BY THE CALLER, AND MEMBERSHIP SECOND (ROLE-3
    invariant 5). Folding the two into one filtered lookup would make an
    out-of-scope device indistinguishable from a nonexistent one, which is
    exactly what ROLE-1 froze as unacceptable.

    A plant or transformer is visible when it holds at least one visible
    device, so a Technician cannot hand-type a path to an otherwise-valid
    plant containing none of their RTLs.

    The unrestricted short-circuit is first for cost, not just clarity: an
    Administrator would otherwise pay for a listing query on every plant and
    transformer render purely to discard the answer.

    Default-deny: called with no identifier, it refuses.
    """
    if scope.is_unrestricted:
        return True
    if device_id is not None:
        return scope.allows(device_id)
    if transformer_id is not None:
        return bool(hierarchy_service.list_devices(transformer_id, scope=scope))
    if plant_id is not None:
        return bool(hierarchy_service.list_transformers(plant_id, scope=scope))
    return False


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

            # Authorization runs here, BEFORE any hierarchy lookup below. A
            # refused page must do no data work on the way to being refused:
            # queries run on behalf of someone not entitled to ask are each a
            # place a partial result can reach a log or an error message.
            decision = route_decision(auth_data, route.name)
            if decision == DECISION_LOGIN:
                from pages.login import login_layout
                return login_layout(), {}
            if decision == DECISION_FORBIDDEN:
                # `{"route": "forbidden"}` rather than the real route name, so
                # every listing callback — all of which branch on this key —
                # simply never fires for a page that was refused.
                return forbidden_panel(), {"route": "forbidden"}

            # Resolved ONCE per render and passed down. `scope_from_session`
            # performs an assignment read for technicians, so calling it per
            # entity would turn one render into a query storm.
            scope = scope_from_session(auth_data)

            metric_key, period_value = parse_query(search)
            custom_start, custom_end = parse_custom_range(search)

            if route.name == "overview":
                ctx = {"route": "overview", "metric_key": metric_key, "period": period_value}
                return plants_overview.layout(), ctx

            if route.name == "plant":
                plant = hierarchy_service.get_plant_or_none(route.plant_id)
                if plant is None:
                    return not_found_panel("plant"), {"route": "unknown"}
                if not entity_in_scope(scope, plant_id=plant.plant_id):
                    logger.warning(
                        "Plant %r refused: outside the session's device scope",
                        plant.plant_id,
                    )
                    return forbidden_panel(), {"route": "forbidden"}

                ctx = {
                    "route": "plant",
                    "plant_id": plant.plant_id,
                    "plant_name": plant.name,
                    "metric_key": metric_key,
                    "period": period_value,
                }
                return plant_detail.layout(plant.name, status=plant.status), ctx

            if route.name == "transformer":
                plant = hierarchy_service.get_plant_or_none(route.plant_id)
                if plant is None:
                    return not_found_panel("plant"), {"route": "unknown"}

                transformer = hierarchy_service.get_transformer_in_plant(
                    route.plant_id, route.transformer_id
                )
                if transformer is None:
                    return not_found_panel("transformer"), {"route": "unknown"}
                if not entity_in_scope(
                    scope, transformer_id=transformer.transformer_id
                ):
                    logger.warning(
                        "Transformer %r refused: outside the session's device scope",
                        transformer.transformer_id,
                    )
                    return forbidden_panel(), {"route": "forbidden"}

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
                device_ctx = hierarchy_service.get_device_context(route.device_id)
                if device_ctx is None:
                    return not_found_panel("device"), {"route": "unknown"}
                if not entity_in_scope(scope, device_id=route.device_id):
                    logger.warning(
                        "Device %r refused: outside the session's device scope",
                        route.device_id,
                    )
                    return forbidden_panel(), {"route": "forbidden"}

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

            if route.name == "device_register":
                ctx = {"route": "device_register"}
                return device_register.layout(), ctx

            if route.name == "admin_users":
                ctx = {"route": "admin_users"}
                return user_admin.layout(), ctx

            if route.name == "reports":
                ctx = {"route": "reports"}
                return report_center.layout(), ctx

            if route.name == "notifications":
                ctx = {"route": "notifications"}
                return notifications.layout(), ctx

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
