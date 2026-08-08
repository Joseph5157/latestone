"""URL parsing, building, and route registration."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs

from dash import Input, Output, html

from config.metrics import DEFAULT_METRIC_KEY, METRIC_KEYS
from components.status_panels import error_panel, not_found_panel
from pages import plants_overview, plant_detail, transformer_detail, device_dashboard
from services import hierarchy_service


@dataclass(frozen=True)
class Route:
    name: str                       # "overview" | "plant" | "transformer" | "device" | "unknown"
    plant_id: str | None = None
    transformer_id: str | None = None
    device_id: str | None = None


def parse_pathname(pathname: str | None) -> Route:
    if not pathname or pathname in ("/", "/plants", "/plants/"):
        return Route(name="overview")

    parts = [p for p in pathname.strip("/").split("/") if p]

    if len(parts) == 1 and parts[0] == "plants":
        return Route(name="overview")

    if len(parts) == 2 and parts[0] == "plants":
        return Route(name="plant", plant_id=parts[1])

    if len(parts) == 3 and parts[0] == "plants":
        return Route(
            name="transformer",
            plant_id=parts[1],
            transformer_id=parts[2],
        )

    if len(parts) == 2 and parts[0] == "devices":
        return Route(name="device", device_id=parts[1])

    return Route(name="unknown")


def parse_query(search: str | None) -> tuple[str, str]:
    """Extract metric_key and period from query string, with defaults."""
    if not search:
        return DEFAULT_METRIC_KEY, "24h"

    params = parse_qs(search.lstrip("?"))
    metric = params.get("metric", [DEFAULT_METRIC_KEY])[0]
    period = params.get("period", ["24h"])[0]

    if metric not in METRIC_KEYS:
        metric = DEFAULT_METRIC_KEY
    if period not in ("24h", "7d", "30d", "custom"):
        period = "24h"

    return metric, period


def device_href(
    device_id: str,
    metric_key: str | None = None,
    period: str | None = None,
) -> str:
    """Build a device dashboard URL, omitting defaults."""
    parts = [f"/devices/{device_id}"]
    params = []

    if metric_key and metric_key != DEFAULT_METRIC_KEY:
        params.append(f"metric={metric_key}")
    if period and period != "24h":
        params.append(f"period={period}")

    if params:
        parts.append("?" + "&".join(params))

    return "".join(parts)


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
                return plant_detail.layout(plant.name), ctx

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
                        plant.name, transformer.transformer_code, plant.plant_id
                    ),
                    ctx,
                )

            if route.name == "device":
                device_ctx = hierarchy_service.get_device_context(route.device_id)
                if device_ctx is None:
                    return not_found_panel("device"), {"route": "unknown"}

                plant_name = device_ctx.plant_name
                transformer_code = device_ctx.transformer_code
                device_code = device_ctx.device_code
                ctx = {
                    "route": "device",
                    "device_id": route.device_id,
                    "plant_name": plant_name,
                    "transformer_code": transformer_code,
                    "device_code": device_code,
                    "metric_key": metric_key,
                    "period": period_value,
                }
                return (
                    device_dashboard.layout(
                        plant_name, transformer_code, device_code, metric_key, period_value
                    ),
                    ctx,
                )

            return not_found_panel("page"), {"route": "unknown"}

        except Exception:
            return error_panel(), {"route": "unknown"}
