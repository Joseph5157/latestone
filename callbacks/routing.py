"""URL parsing, building, and route registration."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs

from config.metrics import DEFAULT_METRIC_KEY, METRIC_KEYS


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
    """Register routing-related callbacks on the Dash app."""
    pass
