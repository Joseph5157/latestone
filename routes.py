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
#: LEGACY-SYNTHETIC-UX-CLEANUP-01: the synthetic Plant -> Transformer -> Device
#: routes (`plant`, `transformer`, `device`), the synthetic Device Management
#: routes (`admin_devices`, `device_register`, `admin_assignments`) and the
#: denied technician `technician_devices` route were retired from navigation
#: and routing here. Their addresses now resolve to `legacy_retired` (a
#: not-found/legacy panel) and so name no sidebar item — none is present below.
#: The synthetic PAGE and CALLBACK code is retained, isolated and unrouted,
#: until the POSTGRESQL-RETIREMENT gate deletes the synthetic model wholesale
#: (plan §8: no big-bang deletion).
NAV_KEY_BY_ROUTE: dict[str, str] = {
    "overview": "overview",
    "rtl_network": "network",
    "historical_events": "events",
    # ADR-032: the client-RTL assignment workflow owns the sidebar's
    # Assignments item (its href is `/technicians/assignments`).
    "rtl_assignments": "assignments",
    "notifications": "notifications",
    "reports": "reports",
    "admin_users": "users",
    "audit_log": "audit_log",
    "admin_settings": "settings",
    "command_center": "command_center",
}

#: Query parameter naming the device whose assignment drawer should open on
#: arrival at Device Management. A query parameter rather than a route: the
#: destination is the existing page in its existing state, with one drawer
#: already open. A `/admin/assignments` route would be a second place
#: assignment lives, and the drawer is not a page.
ASSIGN_PARAM = "assign"

#: ADR-032. Administrator-only Technician assignment management for real
#: client RTL UIDs: current assignments, the Unassigned RTLs pool, assign,
#: reassign, history.
RTL_ASSIGNMENTS_PATH = "/technicians/assignments"

#: Command Center path (SWITCH-OVER-1: the redesigned page took it over from
#: the old one).
COMMAND_CENTER_PATH = "/command-center"
#: HISTORICAL-EVENTS-01. Recorded events from the client logs; filters and
#: paging live inside the page.
EVENTS_PATH = "/events"

#: RTL-LIST-ROUTE-01. The canonical Registered RTLs list — the real client RTL
#: directory. It is the same page, callback and service the directory has
#: always used; only its address changed. The route NAME stays `overview`, so
#: `ROUTE_POLICY`, `NAV_KEY_BY_ROUTE` and the Fleet callback are untouched and
#: authorization cannot have moved with the path.
RTL_LIST_PATH = "/rtls"

#: The name every existing caller already imports. Kept as an alias rather
#: than renamed across the codebase: it is internal, and it now says the
#: canonical address, which is all a caller needs from it.
FLEET_OVERVIEW_PATH = RTL_LIST_PATH

#: RTL-LIST-ROUTE-01. The directory's old address, kept so bookmarks and
#: shared links still arrive. It is compatibility only: it renders nothing of
#: its own and nothing in the application links to it.
LEGACY_RTL_LIST_PATH = "/plants"

#: ADR-033. The one-time password setup/reset page. A PUBLIC route: the
#: visitor has no session yet and the link's token is the whole proof. Like
#: `unknown` it is deliberately absent from `ROUTE_POLICY` — it grants no
#: application access, only the right to set one account's password.
SET_PASSWORD_PATH = "/set-password"
SET_PASSWORD_ROUTE = "set_password"

#: What `parse_pathname` calls the legacy address. Not an application route —
#: like `unknown` it is absent from `ROUTE_POLICY` — because nothing is ever
#: rendered for it: the router ignores it, and it is rewritten to
#: RTL_LIST_PATH before any page is built (see `legacy_redirect_path`).
RTL_LIST_ALIAS_ROUTE = "rtl_list_alias"

#: LEGACY-SYNTHETIC-UX-CLEANUP-01. The retired synthetic routes resolve here.
#: Like `unknown` and `rtl_list_alias` it is deliberately absent from
#: `ROUTE_POLICY`: it grants no application access and renders only the
#: legacy/not-found panel, which reads nothing and resolves no identifier. The
#: synthetic `/plants/<id>`, `/plants/<id>/<tf>`, `/devices/<id>`, `/devices`,
#: `/admin/devices`, `/admin/devices/new` and `/admin/assignments` addresses
#: all parse to this name so a bookmark or typed URL gets a clear "retired"
#: answer instead of a synthetic client screen — and never a fabricated
#: redirect to a real `/rtls/<uid>` (no such mapping exists).
LEGACY_RETIRED_ROUTE = "legacy_retired"

#: RTL-UID-DETAIL-01. The canonical real-client RTL detail route. Its identity
#: is the numeric client RTL UID from `dbo.device_list` — nothing synthetic.
#: Detail lives under the list it belongs to.
RTL_DETAIL_PATH_PREFIX = RTL_LIST_PATH

#: LATEST-NETWORK-CONTEXT-01. The current Network view of the registered RTLs.
#: A sibling of the list and detail routes under `/rtls`; drill and filter
#: state live inside the page, not in deeper routes. The word "network" can
#: never collide with a UID: `_as_rtl_uid` accepts ASCII digits only.
RTL_NETWORK_PATH = f"{RTL_LIST_PATH}/network"

#: `device_uid` is a SQL Server `int`. A value outside this range cannot name
#: a row in any source table, so it is rejected during parsing rather than
#: becoming a query that is guaranteed to find nothing.
_RTL_UID_MIN, _RTL_UID_MAX = 1, 2_147_483_647


def _as_rtl_uid(raw: str | None) -> int | None:
    """A strictly ASCII-decimal, in-range client RTL UID, or None.

    `str.isdigit()` is deliberately not used: it accepts Arabic-Indic digits
    and superscripts, several of which `int()` then happily converts, so a
    path segment that does not look like a UID to a human would parse as one.
    """
    if not raw or not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    return value if _RTL_UID_MIN <= value <= _RTL_UID_MAX else None


def rtl_detail_href(device_uid: int) -> str:
    """The canonical detail URL for one registered client RTL UID.

    Refuses anything that is not a source UID — notably a `str`, which is the
    shape a synthetic application `device_id` has. A link into this route is
    always built from a value the client source produced.
    """
    if isinstance(device_uid, bool) or not isinstance(device_uid, int):
        raise TypeError("an RTL detail link is built from an integer client RTL UID")
    if not _RTL_UID_MIN <= device_uid <= _RTL_UID_MAX:
        raise ValueError("RTL UID is outside the client source integer range")
    return f"{RTL_DETAIL_PATH_PREFIX}/{device_uid}"


def legacy_redirect_path(pathname: str | None) -> str | None:
    """The canonical path a compatibility address stands for, or None.

    Only the bare legacy list path qualifies. `/plants/<id>` and
    `/plants/<id>/<id>` are the synthetic Plant drill-down routes — still
    live, still synthetic — and are deliberately not touched: there is no
    approved mapping from a synthetic plant to anything in the client source.
    """
    if pathname in (LEGACY_RTL_LIST_PATH, f"{LEGACY_RTL_LIST_PATH}/"):
        return RTL_LIST_PATH
    return None


def rtl_list_href(search: str | None = None) -> str:
    """The canonical list URL, carrying a legacy request's query unchanged.

    The directory reads no query parameter today — its filter is page state,
    not URL state — so nothing here interprets the query. It is passed through
    verbatim only so a bookmarked `/plants?…` loses nothing on the way. The
    destination path is fixed, so no query value can change where it goes.
    """
    query = (search or "").lstrip("?")
    return f"{RTL_LIST_PATH}?{query}" if query else RTL_LIST_PATH


@dataclass(frozen=True)
class Route:
    name: str  # "overview" | "plant" | "transformer" | "device" |
               # "rtl_detail" | "rtl_network" | "historical_events" | "admin_devices" | "technician_devices" |
               # "admin_assignments" | "rtl_assignments" | "admin_users" | "reports" |
               # "notifications" | "command_center" | "rtl_list_alias" |
               # "unknown"
    plant_id: str | None = None
    transformer_id: str | None = None
    device_id: str | None = None
    #: Set only by the `rtl_detail` route. Deliberately a separate field from
    #: `device_id`: a client RTL UID and a synthetic application device id are
    #: different identities with no approved mapping between them, and sharing
    #: one field is how that mapping would get invented by accident.
    rtl_uid: int | None = None


def parse_pathname(pathname: str | None) -> Route:
    if not pathname or pathname == "/":
        return Route(name="overview")

    # RTL-LIST-ROUTE-01. Checked before the segment split so the legacy
    # address can only ever be the bare path — never swallow the synthetic
    # `/plants/<id>` routes below it.
    if legacy_redirect_path(pathname) is not None:
        return Route(name=RTL_LIST_ALIAS_ROUTE)

    parts = [p for p in pathname.strip("/").split("/") if p]

    if len(parts) == 1 and parts[0] == "set-password":
        return Route(name=SET_PASSWORD_ROUTE)

    if len(parts) == 1 and parts[0] == "rtls":
        return Route(name="overview")

    if len(parts) == 1 and parts[0] == "events":
        return Route(name="historical_events")

    if len(parts) == 1 and parts[0] == "reports":
        return Route(name="reports")

    if len(parts) == 1 and parts[0] == "notifications":
        return Route(name="notifications")

    if len(parts) == 1 and parts[0] == "command-center":
        return Route(name="command_center")

    if len(parts) == 2 and parts == ["technicians", "assignments"]:
        return Route(name="rtl_assignments")


    # LEGACY-SYNTHETIC-UX-CLEANUP-01. The synthetic Plant and Transformer
    # drill-down (`/plants/<id>`, `/plants/<id>/<tf>`) is retired: it resolves
    # to the legacy/not-found panel, not a synthetic page. The plant id is
    # deliberately dropped — nothing downstream resolves it, so there is no
    # scope-filtered lookup and no way to probe whether a synthetic plant
    # exists. (The bare `/plants` list address is handled above by
    # `legacy_redirect_path`, which still redirects to `/rtls`.)
    if len(parts) in (2, 3) and parts[0] == "plants":
        return Route(name=LEGACY_RETIRED_ROUTE)

    # RTL-UID-DETAIL-01. A segment that is not a well-formed client RTL UID
    # falls through to `unknown` rather than becoming a refused RTL: a typo
    # must keep rendering not-found, not imply something exists behind it.
    if len(parts) == 2 and parts[0] == "rtls" and parts[1] == "network":
        return Route(name="rtl_network")

    if len(parts) == 2 and parts[0] == "rtls":
        uid = _as_rtl_uid(parts[1])
        if uid is not None:
            return Route(name="rtl_detail", rtl_uid=uid)
        return Route(name="unknown")

    # LEGACY-SYNTHETIC-UX-CLEANUP-01. The synthetic device dashboard
    # (`/devices/<id>`) and the technician synthetic-device roster (`/devices`)
    # are retired to the legacy/not-found panel. The device id is dropped: it
    # is a synthetic application identifier with no approved mapping to a client
    # RTL UID, and nothing downstream resolves it. These addresses are NOT
    # redirected to `/rtls/<uid>` — no such mapping exists (§6, §22).
    if len(parts) in (1, 2) and parts[0] == "devices":
        return Route(name=LEGACY_RETIRED_ROUTE)

    if len(parts) == 2 and parts[0] == "admin":
        if parts[1] == "users":
            return Route(name="admin_users")
        if parts[1] == "audit-log":
            return Route(name="audit_log")
        if parts[1] == "settings":
            return Route(name="admin_settings")
        # LEGACY-SYNTHETIC-UX-CLEANUP-01. Synthetic Device Management
        # (`/admin/devices`) and the old app-device assignment surface
        # (`/admin/assignments`) are retired. Real client-RTL technician
        # assignment lives at `/technicians/assignments` (rtl_assignments).
        if parts[1] in ("devices", "assignments"):
            return Route(name=LEGACY_RETIRED_ROUTE)

    # LEGACY-SYNTHETIC-UX-CLEANUP-01. Synthetic device registration retired.
    if len(parts) == 3 and parts[0] == "admin" and parts[1] == "devices" and parts[2] == "new":
        return Route(name=LEGACY_RETIRED_ROUTE)

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


def parse_rtl_uid(search: str | None) -> int | None:
    """A strictly numeric, explicit raw RTL UID from an existing device URL.

    It is not a fleet lookup or a source-to-application mapping.
    """
    if not search:
        return None
    raw = parse_qs(search.lstrip("?")).get("rtl_uid", [None])[0]
    if raw is None or not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    return value if 0 < value <= 2_147_483_647 else None


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
    rtl_uid: int | None = None,
) -> str:
    """Build a device dashboard URL, omitting defaults.

    `start`/`end` are only meaningful alongside `period="custom"`; without them
    a shared custom-range link opens on an empty dashboard.  A validated raw
    RTL UID, when the authorized router has supplied one, must survive metric
    and period URL synchronization; it is never inferred from ``device_id``.
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
    if isinstance(rtl_uid, int) and not isinstance(rtl_uid, bool) and 0 < rtl_uid <= 2_147_483_647:
        params.append(f"rtl_uid={rtl_uid}")

    if params:
        parts.append("?" + "&".join(params))

    return "".join(parts)
