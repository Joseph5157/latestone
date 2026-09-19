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
from urllib.parse import parse_qs, quote

from config.metrics import DEFAULT_METRIC_KEY, METRIC_KEYS

DEFAULT_PERIOD = "24h"
VALID_PERIODS = ("24h", "7d", "30d", "custom")

#: Device Management. Named once here because two screens now link to it.
ADMIN_DEVICES_PATH = "/admin/devices"

#: `Route.name` -> sidebar item key. A routing fact, shared by the sidebar
#: (which highlights the current item) and by `services.authorization` (which
#: derives visible navigation from the route policy). It lives here rather
#: than in `callbacks/navigation.py` for the same reason `device_href` does:
#: a service reaching into `callbacks/` to borrow it would invert the layering.
#:
#: "unknown" deliberately has no entry: no page rendered, no item highlighted.
#: The monitoring drill-down (plant, transformer, device) has no top-level
#: destination of its own — it is the workflow that lives inside Overview — so
#: those routes keep the Overview item highlighted. Assignments has no entry
#: because it has no route, so it can never become active.
NAV_KEY_BY_ROUTE: dict[str, str] = {
    "overview": "overview",
    "plant": "overview",
    "transformer": "overview",
    "device": "overview",
    "admin_devices": "devices",
    "technician_devices": "technician_devices",
    "admin_assignments": "assignments",
    "device_register": "registration",
    "notifications": "notifications",
    "reports": "reports",
    "admin_users": "users",
    "audit_log": "audit_log",
    "admin_settings": "settings",
    "command_center": "command_center",
    # The full locations view is the same destination one level deeper,
    # so the sidebar keeps Command Center highlighted rather than losing
    # its active item while the operator is still inside it.
    "command_center_locations": "command_center",
    # CC-NEW-1: the redesigned Command Center, built beside the old one until
    # the switch-over (redesign Phase 6).
    "command_center_new": "command_center",
}

#: Query parameter naming the device whose assignment drawer should open on
#: arrival at Device Management. A query parameter rather than a route: the
#: destination is the existing page in its existing state, with one drawer
#: already open. A `/admin/assignments` route would be a second place
#: assignment lives, and the drawer is not a page.
ASSIGN_PARAM = "assign"

#: Command Center path, and the query parameter naming the Plant whose
#: transformer concentration is shown.
#:
#: A query parameter for the same reason ASSIGN_PARAM is one: the
#: destination is the existing page in its existing state, with one plant
#: selected. Two further properties matter here specifically — selection
#: survives a polling refresh by construction, since no callback owns or can
#: clear it, and the selected view is bookmarkable and shareable. A
#: `dcc.Store` would give neither and would need protecting from every
#: refresh callback added later.
COMMAND_CENTER_PATH = "/command-center"
PLANT_PARAM = "plant"

#: The redesigned Command Center (CC-NEW-1). Temporary path: it moves to
#: COMMAND_CENTER_PATH when the old page is removed (redesign Phase 6).
COMMAND_CENTER_NEW_PATH = "/command-center-new"


@dataclass(frozen=True)
class Route:
    name: str  # "overview" | "plant" | "transformer" | "device" |
               # "admin_devices" | "technician_devices" | "admin_assignments" |
               # "admin_users" | "reports" | "notifications" |
               # "command_center" | "command_center_locations" | "unknown"
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

    if len(parts) == 1 and parts[0] == "command-center":
        return Route(name="command_center")

    if len(parts) == 1 and parts[0] == "command-center-new":
        return Route(name="command_center_new")

    # Only "locations" is a child of Command Center; anything else under it
    # falls through to `unknown`, so a typo'd subpath reads as "no such page"
    # rather than being swallowed by the parent.
    if len(parts) == 2 and parts[0] == "command-center" and parts[1] == "locations":
        return Route(name="command_center_locations")

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

    # A Technician's own assigned-devices page — deliberately a different
    # path from ADMIN_DEVICES_PATH ("/admin/devices"), not a role-conditional
    # rendering of it (ADR-016: fleet administration and operating equipment
    # you are responsible for are different jobs, kept at different paths).
    if len(parts) == 1 and parts[0] == "devices":
        return Route(name="technician_devices")

    if len(parts) == 2 and parts[0] == "admin":
        if parts[1] == "devices":
            return Route(name="admin_devices")
        if parts[1] == "assignments":
            return Route(name="admin_assignments")
        if parts[1] == "users":
            return Route(name="admin_users")
        if parts[1] == "audit-log":
            return Route(name="audit_log")
        if parts[1] == "settings":
            return Route(name="admin_settings")

    if len(parts) == 3 and parts[0] == "admin" and parts[1] == "devices" and parts[2] == "new":
        return Route(name="device_register")

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


def device_assign_href(device_id: str) -> str:
    """Device Management, with this device's assignment drawer opened.

    The Unassigned RTLs panel on the Fleet Overview does not own an assignment
    workflow; it hands a device to the one Device Management already has. This
    link is the whole handoff, which is why the format lives here beside
    `device_href` rather than being spelled out in a component.

    The identifier is percent-encoded. It is validated on arrival — only a
    device already listed on the destination page can open the drawer — but
    encoding it first means a value carrying `&` or `?` cannot append
    parameters of its own on the way there.
    """
    return f"{ADMIN_DEVICES_PATH}?{ASSIGN_PARAM}={quote(str(device_id), safe='')}"


def parse_assign_request(search: str | None) -> str | None:
    """The device id an `?assign=` link names, or None.

    Returns the raw value. It is a browser-supplied string and this function
    makes no claim that it names a real device — the caller resolves it against
    rows already on the page, and an unknown value simply opens nothing.
    """
    if not search:
        return None
    params = parse_qs(search.lstrip("?"))
    value = params.get(ASSIGN_PARAM, [None])[0]
    return value or None


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


def command_center_href(plant_id: str | None) -> str:
    """Command Center, with `plant_id` selected. No plant -> the bare route.

    The identifier is percent-encoded so a value carrying `&` or `?` cannot
    append parameters of its own, the same guard `device_assign_href`
    applies. It is validated on arrival: an id naming no visible plant
    simply selects nothing.
    """
    if not plant_id:
        return COMMAND_CENTER_PATH
    return f"{COMMAND_CENTER_PATH}?{PLANT_PARAM}={quote(str(plant_id), safe='')}"


def parse_plant_selection(search: str | None) -> str | None:
    """The plant id a `?plant=` link names, or None.

    Returns the raw value and makes no claim that it names a visible plant —
    the caller resolves it against the freshness snapshot it already has, and
    an unknown or out-of-scope value selects nothing rather than erroring.
    """
    if not search:
        return None
    params = parse_qs(search.lstrip("?"))
    value = params.get(PLANT_PARAM, [None])[0]
    return value or None
