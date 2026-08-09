"""Route registration.

URL parsing/building lives in the top-level `routes` module so components can
share it; the names are re-exported here for existing callers.
"""
from __future__ import annotations

import logging

from dash import Input, Output, html

from components.status_panels import error_panel, not_found_panel
from pages import plants_overview, plant_detail, transformer_detail, device_dashboard
from routes import Route, device_href, parse_custom_range, parse_pathname, parse_query
from services import hierarchy_service

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
        if not auth_data or not auth_data.get("authenticated"):
            from pages.login import login_layout
            return login_layout(), {}

        try:
            route = parse_pathname(pathname)
            metric_key, period_value = parse_query(search)
            custom_start, custom_end = parse_custom_range(search)

            if route.name == "overview":
                ctx = {"route": "overview", "metric_key": metric_key, "period": period_value}
                return plants_overview.layout(), ctx

            if route.name == "plant":
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

            return not_found_panel("page"), {"route": "unknown"}

        except Exception:
            # Logged in full so programming errors are diagnosable; the UI panel
            # stays generic and never exposes internals.
            logger.exception("Routing failed for pathname=%r search=%r", pathname, search)
            return error_panel(), {"route": "unknown"}
