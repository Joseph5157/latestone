"""
URL parsing and building — the single source of truth for application routes.

Lives at the top level rather than under `callbacks/` because both callbacks
and components build device links. Components importing from `callbacks/`
would invert the layering, and duplicating the link format is what previously
let the metric snapshot strip drop the selected period.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs

from config.metrics import DEFAULT_METRIC_KEY, METRIC_KEYS

DEFAULT_PERIOD = "24h"
VALID_PERIODS = ("24h", "7d", "30d", "custom")


@dataclass(frozen=True)
class Route:
    name: str  # "overview" | "plant" | "transformer" | "device" |
               # "admin_devices" | "admin_users" | "reports" | "notifications" |
               # "unknown"
    plant_id: str | None = None
    transformer_id: str | None = None
    device_id: str | None = None


def parse_pathname(pathname: str | None) -> Route:
    if not pathname or pathname in ("/", "/plants", "/plants/"):
        return Route(name="overview")

    parts = [p for p in pathname.strip("/").split("/") if p]

    if len(parts) == 1 and parts[0] == "plants":
        return Route(name="overview")

    if len(parts) == 1 and parts[0] == "reports":
        return Route(name="reports")

    if len(parts) == 1 and parts[0] == "notifications":
        return Route(name="notifications")

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

    if len(parts) == 2 and parts[0] == "admin":
        if parts[1] == "devices":
            return Route(name="admin_devices")
        if parts[1] == "users":
            return Route(name="admin_users")

    return Route(name="unknown")


def parse_query(search: str | None) -> tuple[str, str]:
    """Extract metric_key and period from query string, with defaults."""
    if not search:
        return DEFAULT_METRIC_KEY, DEFAULT_PERIOD

    params = parse_qs(search.lstrip("?"))
    metric = params.get("metric", [DEFAULT_METRIC_KEY])[0]
    period = params.get("period", [DEFAULT_PERIOD])[0]

    if metric not in METRIC_KEYS:
        metric = DEFAULT_METRIC_KEY
    if period not in VALID_PERIODS:
        period = DEFAULT_PERIOD

    return metric, period


def parse_custom_range(search: str | None) -> tuple[str | None, str | None]:
    """Extract the custom range bounds as ISO date strings, if present.

    Kept separate from `parse_query` so that function keeps its two-value
    contract. Values are returned as strings because they feed straight into
    `dcc.DatePickerRange`, which expects ISO dates rather than datetimes.
    Anything unparseable is discarded rather than raised — a hand-edited URL
    must not break the page.
    """
    if not search:
        return None, None

    params = parse_qs(search.lstrip("?"))

    def _valid(key: str) -> str | None:
        raw = params.get(key, [None])[0]
        if not raw:
            return None
        try:
            datetime.fromisoformat(raw)
        except ValueError:
            return None
        return raw

    return _valid("start"), _valid("end")


def device_href(
    device_id: str,
    metric_key: str | None = None,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> str:
    """Build a device dashboard URL, omitting defaults.

    `start`/`end` are only meaningful alongside `period="custom"`; without them
    a shared custom-range link opens on an empty dashboard.
    """
    parts = [f"/devices/{device_id}"]
    params = []

    if metric_key and metric_key != DEFAULT_METRIC_KEY:
        params.append(f"metric={metric_key}")
    if period and period != DEFAULT_PERIOD:
        params.append(f"period={period}")
    if period == "custom":
        if start:
            params.append(f"start={start}")
        if end:
            params.append(f"end={end}")

    if params:
        parts.append("?" + "&".join(params))

    return "".join(parts)
