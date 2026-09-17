"""Listing callbacks — populate drill-down tables and handle row navigation.

Row builders and navigation targets are module-level functions so they can be
tested without a Dash runtime; `register()` only wires them up.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import Input, Output, State, no_update

from components.admin_summary import admin_summary_cards
from components.entity_context import entity_context
from components.fleet_condition import data_freshness, fleet_condition_panels, fleet_inventory
from components.fleet_summary import (
    fleet_subtitle_text,
    format_render_stamp,
    plant_kpi_cards,
    transformer_kpi_cards,
)
from components.metric_health import metric_health_overview
from components.my_rtls import my_rtls_panel
from components.needs_attention import needs_attention
from components.status_panels import empty_data_panel, error_panel
from components.temperature_attribution import temperature_attribution
from components.unassigned_rtls import unassigned_rtl_panel
from config.metrics import ATTRIBUTION_METRIC_KEY
from components.freshness_badge import format_last_reading
from components.freshness_presentation import FRESHNESS_PRESENTATION
from routes import device_href
from services import admin_overview_service, hierarchy_service, monitoring_service
from services.hierarchy_service import entity_in_scope
from services.auth_service import current_identity
from services.authorization import VIEW_ADMINISTRATION_OVERVIEW, may_perform_capability
from services.device_scope import DeviceScope, current_device_scope
from services.monitoring_service import Freshness, aggregate_freshness, reading_age, severity_rank

logger = logging.getLogger(__name__)

# The column whose cells are styled as links and whose clicks navigate.
PLANT_LINK_COLUMN = "plant"
TRANSFORMER_LINK_COLUMN = "transformer"
DEVICE_LINK_COLUMN = "device"

PLANT_COLUMNS = [
    {"name": "Plant", "id": "plant"},
    {"name": "Country", "id": "country"},
    {"name": "Transformers", "id": "transformers", "type": "numeric"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
    # Data-delivery freshness only, never an electrical condition (§21).
    {"name": "Data", "id": "freshness"},
]

TRANSFORMER_COLUMNS = [
    {"name": "Transformer", "id": "transformer"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
    # Administrative status (active/inactive) and data freshness are separate
    # concepts per AGENTS.md and stay separate columns. Merging them would let
    # an inactive transformer read as a data problem, or a dead feed read as an
    # administrative one.
    {"name": "Status", "id": "status"},
    {"name": "Data", "id": "freshness"},
]

DEVICE_COLUMNS = [
    {"name": "Device", "id": "device"},
    {"name": "Status", "id": "status"},
    {"name": "Data", "id": "freshness"},
]

# MOBBIN-UX-2: fixed operational wording — a fact about registration, not a
# guess at cause. The same sentence for every empty plant/transformer, no
# matter whether inventory is genuinely absent or merely invisible to this
# caller's DeviceScope; neither this module nor the message infers which.
NO_TRANSFORMERS_MESSAGE = "No transformers are registered for this plant."
NO_DEVICES_MESSAGE = "No RTL devices are registered for this transformer."


# --------------------------------------------------------------------------
# Row builders
#
# Every row carries an `id`. dash_table surfaces it as `active_cell["row_id"]`,
# which is what makes click navigation independent of sorting/filtering/paging.
# `id` is not listed in the column specs, so it is never rendered.
# --------------------------------------------------------------------------

def build_plant_rows(plants, counts: dict, health) -> list[dict]:
    """One row per plant, with its freshness read off the shared FleetHealth.

    `health` is passed in rather than fetched here so the whole screen is served
    by one query and one definition of freshness. A plant with no rollup is
    reported as NO_DATA over zero devices, never as a blank cell: an empty cell
    in a health column reads as "fine".
    """
    rows = []
    for p in plants:
        t_count, d_count = counts.get(p.plant_id, (0, 0))
        rollup = health.plants.get(p.plant_id) or aggregate_freshness([])
        rows.append({
            "id": p.plant_id,
            "plant": p.name,
            "country": p.country,
            "transformers": t_count,
            "devices": d_count,
            "freshness": rollup.label("devices"),
            # Sort key only. Carried on the row like `id`, absent from
            # PLANT_COLUMNS, so it orders rows without being rendered.
            "_severity": severity_rank(rollup.state),
            # Semantic identity for styling. `_severity` orders, `_state`
            # identifies, the label presents — three jobs, three keys.
            "_state": rollup.state.value,
        })
    return rows


def sort_plant_rows_exception_first(rows: list[dict]) -> list[dict]:
    """Exceptions above healthy rows, then alphabetical (§10).

    The operator's first question is which plant to inspect, and thirty
    alphabetical rows do not answer it. dash_table's own sorting still works and
    overrides this — it is the default order, not a lock.
    """
    return sorted(rows, key=lambda r: (-r["_severity"], r["plant"]))


def build_transformer_rows(transformers, device_counts: dict, health) -> list[dict]:
    """One row per transformer, freshness read off the shared FleetHealth.

    Same contract as `build_plant_rows`: `health` is passed in, a missing rollup
    is NO_DATA rather than blank, and the severity rank rides on the row.
    """
    rows = []
    for t in transformers:
        rollup = health.transformers.get(t.transformer_id) or aggregate_freshness([])
        rows.append({
            "id": t.transformer_id,
            "transformer": t.transformer_code,
            "devices": device_counts.get(t.transformer_id, 0),
            "status": t.status,
            "freshness": rollup.label("devices"),
            "_severity": severity_rank(rollup.state),
            # Semantic identity for styling. `_severity` orders, `_state`
            # identifies, the label presents — three jobs, three keys.
            "_state": rollup.state.value,
        })
    return rows


def sort_transformer_rows_exception_first(rows: list[dict]) -> list[dict]:
    """Exceptions first, then transformer code — same rule as the plant table."""
    return sorted(rows, key=lambda r: (-r["_severity"], r["transformer"]))


def build_device_rows(devices, health) -> list[dict]:
    """One row per device. The noun is `metrics`, not `devices`.

    A device is the level freshness is actually measured at, so its rollup is
    over its eight metrics. Reusing the parent nouns here would render
    "Stale · 1 of 8 devices" on a single device.
    """
    rows = []
    for d in devices:
        rollup = health.devices.get(d.device_id) or aggregate_freshness([])
        rows.append({
            "id": d.device_id,
            "device": d.device_code,
            "status": d.status,
            "freshness": rollup.label("metrics"),
            "_severity": severity_rank(rollup.state),
            # Semantic identity for styling. `_severity` orders, `_state`
            # identifies, the label presents — three jobs, three keys.
            "_state": rollup.state.value,
        })
    return rows


def sort_device_rows_exception_first(rows: list[dict]) -> list[dict]:
    """Exceptions first, then device code — same rule as the tables above it."""
    return sorted(rows, key=lambda r: (-r["_severity"], r["device"]))


# --------------------------------------------------------------------------
# My RTLs (TECH-WORKSPACE-1) — a Technician's own assignment work list.
#
# Renders ABOVE Fleet Condition, for a restricted scope only (ADR-004). No
# action controls (ADR-016): each row links to the existing device page, the
# sole authorized entry point to Program RTL / Message Forwarding /
# Deactivate.
# --------------------------------------------------------------------------

def build_my_rtls_rows(scope: DeviceScope, health) -> list[dict]:
    """One row per device in the caller's OWN scope. Uncapped (D3).

    Iterates `scope.device_ids`, never `health.devices`: an assigned RTL
    that has never reported (or sits under an inactive transformer) may be
    entirely absent from the freshness rollup, and a missing rollup still
    gets a row here, defaulted to NO_DATA (`aggregate_freshness([])`) — the
    same rule `build_plant_rows` already follows for a plant with nothing
    reporting under it.

    Labels come from ONE scoped `hierarchy_service.list_device_paths` call —
    never `list_all_devices`/`hierarchy_code_index`, both unscoped fleet-wide
    reads ADR-004 forbids a restricted caller's render from reaching. Skipped
    entirely when there are no ids to resolve, so an EMPTY scope costs zero
    label queries, matching the zero this function costs an UNRESTRICTED
    caller by never being called at all (`my_rtls_section` below).
    """
    device_ids = sorted(scope.device_ids or ())
    if not device_ids:
        return []
    paths = {
        p.device_id: p
        for p in hierarchy_service.list_device_paths(device_ids, scope=scope)
    }
    rows = []
    for device_id in device_ids:
        rollup = health.devices.get(device_id) or aggregate_freshness([])
        path = paths.get(device_id)
        rows.append({
            "id": device_id,
            "device": path.device_code if path else device_id,
            "plant": path.plant_name if path else "",
            "transformer": path.transformer_code if path else "",
            "freshness": rollup.label("metrics"),
            "_severity": severity_rank(rollup.state),
            "_state": rollup.state.value,
        })
    return rows


def sort_my_rtls_rows_exception_first(rows: list[dict]) -> list[dict]:
    """Exceptions first, then RTL code — same rule as every table on this page."""
    return sorted(rows, key=lambda r: (-r["_severity"], r["device"]))


def my_rtls_section(scope: DeviceScope, health):
    """The My RTLs panel, or None for an unrestricted role.

    ADR-004: the rendering condition is `not scope.is_unrestricted`, never a
    role comparison. Administrator and General both resolve to UNRESTRICTED
    and see no panel at all — not an empty one, which would misreport an
    unrestricted role as having a (empty) assignment set.

    A restricted scope always renders, including EMPTY (a technician with
    zero active assignments): that is a real, distinct fact from
    "unrestricted" and gets its own truthful empty state
    (`components.my_rtls.my_rtls_panel`), the same "show it, say nothing to
    show" rule `needs_attention`'s own empty state already follows.
    """
    if scope.is_unrestricted:
        return None
    rows = sort_my_rtls_rows_exception_first(build_my_rtls_rows(scope, health))
    return my_rtls_panel(rows)


# --------------------------------------------------------------------------
# Needs Attention exception queue
#
# ENT-2: the queue is a grouped Plant -> Transformer -> RTL tree rather than a
# flat plant list. Only NON-FRESH branches appear — a fresh transformer or
# fresh RTL is the absence of an exception and is omitted. Plant and
# transformer rows carry roll-up state as context; RTL rows are the actionable
# leaves. Every state, count and timestamp is read off the ONE FleetHealth the
# screen already fetched — this section issues no telemetry query at all.
# --------------------------------------------------------------------------

#: Cap on rendered ACTIONABLE RTL LEAVES. Plant and transformer headings are
#: hierarchy context and never consume it (ENT-2 gate decision), so five RTLs
#: may render under two or three automatically included parent rows instead of
#: the queue showing four headers and one exception while claiming five.
NEEDS_ATTENTION_MAX_RTLS = 5


def build_exception_queue(
    plants, health, rendered_at,
    device_codes: dict[str, str] | None = None,
    transformer_codes: dict[str, str] | None = None,
) -> dict:
    """The grouped exception tree, presentation-ready.

    `health` is the same single-fetch FleetHealth everything else on this page
    reads; this function performs no queries of its own. Operator-facing codes
    arrive as plain dicts (resolved once by the caller via one bulk hierarchy
    lookup) and fall back to raw ids when a code is unknown — an identifier is
    truthful where a guessed name would not be.

    Returns::

        {
          "groups": [ {plant row, "children": [ {transformer row, "children":
                      [RTL leaf rows]} ]} ],
          "total_rtls": int,   # affected RTLs across all affected plants
          "shown_rtls": int,   # after the leaf cap
          "plant_count": int,  # plants represented in "groups"
        }

    Ordering is exception-first at every level: NO_DATA before STALE, then
    name/code — the same rule as every listing on this page.
    """
    device_codes = device_codes or {}
    transformer_codes = transformer_codes or {}

    def _code(mapping: dict[str, str], key: str) -> str:
        return mapping.get(key) or key

    plant_groups: list[dict] = []
    total_rtls = 0

    affected_plants = []
    for p in plants:
        rollup = health.plants.get(p.plant_id) or aggregate_freshness([])
        if rollup.state is Freshness.FRESH:
            continue
        affected_plants.append((p, rollup))
    affected_plants.sort(key=lambda pair: (-severity_rank(pair[1].state), pair[0].name))

    for p, plant_rollup in affected_plants:
        last_updated = health.plant_last_updated.get(p.plant_id)
        group: dict = {
            "kind": "plant",
            "id": p.plant_id,
            "entity": p.name,
            "issue": plant_rollup.label("devices"),
            "last_update": format_last_reading(
                last_updated, reading_age(last_updated, rendered_at)
            ),
            "href": f"/plants/{p.plant_id}",
            "_state": plant_rollup.state.value,
            "_severity": severity_rank(plant_rollup.state),
            "children": [],
        }
        group_leaves = 0

        transformer_rollups = health.transformers_for_plant(p.plant_id)
        affected_transformers = [
            (tid, rollup)
            for tid, rollup in transformer_rollups.items()
            if rollup.state is not Freshness.FRESH
        ]
        # Codes may be absent (unscoped index misses); fall back to sorting by
        # whatever we would display.
        affected_transformers.sort(
            key=lambda pair: (
                -severity_rank(pair[1].state),
                transformer_codes.get(pair[0], pair[0]),
            )
        )

        for tid, t_rollup in affected_transformers:
            leaves = []
            device_rollups = health.devices_for_transformer(tid)
            affected_devices = [
                (did, rollup)
                for did, rollup in device_rollups.items()
                if rollup.state is not Freshness.FRESH
            ]
            affected_devices.sort(
                key=lambda pair: (
                    -severity_rank(pair[1].state),
                    device_codes.get(pair[0], pair[0]),
                )
            )

            for did, d_rollup in affected_devices:
                ts = health.device_last_updated.get(did)
                leaves.append({
                    "kind": "device",
                    "id": did,
                    "entity": _code(device_codes, did),
                    "issue": FRESHNESS_PRESENTATION[d_rollup.state].label,
                    "last_update": format_last_reading(
                        ts, reading_age(ts, rendered_at)
                    ),
                    "href": device_href(did),
                    "_state": d_rollup.state.value,
                    "_severity": severity_rank(d_rollup.state),
                })

            group_leaves += len(leaves)
            t_last = health.last_updated_for_transformer(tid)
            group["children"].append({
                "kind": "transformer",
                "id": tid,
                "entity": _code(transformer_codes, tid),
                "issue": t_rollup.label("devices"),
                "last_update": format_last_reading(
                    t_last, reading_age(t_last, rendered_at)
                ),
                "href": f"/plants/{p.plant_id}/{tid}",
                "_state": t_rollup.state.value,
                "_severity": severity_rank(t_rollup.state),
                "children": leaves,
            })

        total_rtls += group_leaves
        plant_groups.append(group)

    # Cap on leaves only. A plant with zero leaves (e.g. present in the plant
    # list but absent from the freshness tree — NO_DATA over zero devices) is
    # still an exception and renders as a header-only group without consuming
    # the cap.
    remaining = NEEDS_ATTENTION_MAX_RTLS
    shown_groups: list[dict] = []
    shown_rtls = 0
    for group in plant_groups:
        group_has_leaves = any(t["children"] for t in group["children"])
        shown_children = []
        for t in group["children"]:
            if remaining <= 0:
                break
            take = t["children"][:remaining]
            if take:
                shown_children.append({**t, "children": take})
                remaining -= len(take)
                shown_rtls += len(take)
        if shown_children or not group_has_leaves:
            shown_groups.append({**group, "children": shown_children})

    return {
        "groups": sort_needs_attention_tree(shown_groups),
        "total_rtls": total_rtls,
        "shown_rtls": shown_rtls,
        "plant_count": len(shown_groups),
    }


def sort_needs_attention_tree(groups: list[dict]) -> list[dict]:
    """Groups arrive in severity order from the builder; kept as a named hook
    so the ordering rule stays testable independently of tree construction."""
    return groups


def hierarchy_code_index(plants, health) -> dict:
    """Operator-facing codes for the exception queue, in ONE bulk read.

    Returns ``{"device_codes": ..., "transformer_codes": ...}``. Called only
    when at least one plant is non-FRESH — a healthy fleet pays nothing. The
    index is a superset of any scoped population's needs (active managed
    RTLs), and missing entries degrade to raw ids inside the builder, never to
    a fabricated name.
    """
    has_exceptions = any(
        (health.plants.get(p.plant_id) or aggregate_freshness([])).state
        is not Freshness.FRESH
        for p in plants
    )
    if not has_exceptions:
        return {"device_codes": {}, "transformer_codes": {}}
    device_codes: dict[str, str] = {}
    transformer_codes: dict[str, str] = {}
    for row in hierarchy_service.list_all_devices():
        device_codes.setdefault(row.device_id, row.device_code)
        transformer_codes.setdefault(row.transformer_id, row.transformer_code)
    return {"device_codes": device_codes, "transformer_codes": transformer_codes}


def sort_needs_attention_rows(rows: list[dict]) -> list[dict]:
    """NO_DATA before STALE before FRESH (if any), then alphabetical by
    entity name — same exception-first rule as every other listing."""
    return sorted(rows, key=lambda r: (-r["_severity"], r["entity"]))


# --------------------------------------------------------------------------
# Navigation targets
# --------------------------------------------------------------------------

def _clicked_row_id(active_cell, link_column: str) -> str | None:
    """The identity of the clicked row, or None if this click should be ignored.

    Deliberately reads `row_id` rather than indexing `data` by
    `active_cell["row"]`: that index refers to the sorted/filtered/paged
    viewport, so it points at the wrong entity as soon as the operator sorts a
    column.
    """
    if not active_cell or active_cell.get("column_id") != link_column:
        return None
    return active_cell.get("row_id") or None


def plant_row_target(active_cell):
    plant_id = _clicked_row_id(active_cell, PLANT_LINK_COLUMN)
    if not plant_id:
        return no_update
    return f"/plants/{plant_id}"


def transformer_row_target(active_cell, context):
    transformer_id = _clicked_row_id(active_cell, TRANSFORMER_LINK_COLUMN)
    if not transformer_id:
        return no_update
    plant_id = (context or {}).get("plant_id")
    if not plant_id:
        return no_update
    return f"/plants/{plant_id}/{transformer_id}"


def device_row_target(active_cell):
    device_id = _clicked_row_id(active_cell, DEVICE_LINK_COLUMN)
    if not device_id:
        return no_update
    return device_href(device_id)


def listing_outputs(build_rows, columns: list[dict], context_msg: str) -> tuple:
    """(rows, columns, error_children) for one listing table.

    The three listing callbacks previously called services with no boundary. The
    overview route does no database access itself, so an outage after login first
    surfaced here and raised through Dash, leaving a page that never filled in.

    An empty table alone is not enough: "no rows exist" and "we could not reach
    the database" must not look identical, hence the separate error slot. The
    cause is logged in full; the panel stays generic per AGENTS.md.
    """
    try:
        return build_rows(), columns, None
    except Exception:
        logger.exception("Listing failed while %s", context_msg)
        return [], columns, error_panel()


def inventory_empty_notice(rows: list[dict] | None, error, message: str):
    """A truthful "nothing here" panel for a hierarchy inventory table.

    Two rules, both load-bearing (MOBBIN-UX-2):

    - `error is not None` wins outright. A query failure and a genuinely
      empty result must never look the same — `listing_outputs` already owns
      the one explanation for a blank table when the query itself failed, so
      this returns None rather than layering a second, contradictory message
      under it.
    - Any row at all — however STALE or NO_DATA its freshness — means this
      is not empty. Telemetry absence is not inventory absence; only a
      genuinely zero-length result triggers the notice.
    """
    if error is not None:
        return None
    if rows:
        return None
    return empty_data_panel(message)


def admin_summary_output(now: datetime):
    """The administration block for the Fleet Overview, or None.

    Wrapped in its own boundary rather than sharing the listing's. Adminis-
    tration is a secondary axis on this page: an operator opens the Fleet
    Overview for the plant table and the freshness figures, and a failure to
    read assignment counts must not cost them any of that. So this fails to
    *nothing* — the row does not render — instead of raising through
    `listing_outputs` and blanking the table.

    It also fails quietly rather than to a second error panel. The listing
    already owns the one panel on this page; a competing panel for a
    supporting card row would imply the page as a whole is broken when only
    its administration half is. The cause is logged in full either way.

    `now` is the caller's render instant, threaded through so the registration
    window is evaluated against the same moment as the freshness figures
    beside it — not a second clock read a few milliseconds later.

    The cards and the Unassigned RTLs panel (ADMIN-3) are built from ONE
    `AdminOverviewSummary`. The exception list is already inside it, so the
    panel costs no extra query, and the card's unassigned count cannot
    disagree with the list rendered underneath it. They also share this one
    boundary: a failed read drops both, rather than leaving a list standing
    under no heading and no counts.
    """
    try:
        summary = admin_overview_service.get_admin_overview(now=now)
        return [admin_summary_cards(summary), unassigned_rtl_panel(summary)]
    except Exception:
        logger.exception("Administration summary unavailable for the Fleet Overview")
        return None


def administration_section(rendered_at: datetime):
    """The Administration block, or None when the role may not see it.

    AUTH-HARDEN-1: takes no identity argument at all — it asks
    `current_identity()` for the CURRENT trusted role rather than accepting
    one from a caller, so there is no `auth_data` parameter left to read a
    role out of by mistake.

    Gated on an explicit CAPABILITY rather than on
    `may_access_route(role, "admin_devices")`. Those two questions — may this
    user enter Device Management, and may this user see Administration
    overview content — happen to have the same answer today and may diverge.
    Navigation is derived from routes because it is the same question viewed
    twice; page content is not.

    Returns None WITHOUT calling `admin_summary_output`, so a denied role
    issues no administration query at all — the section is skipped, not built
    and discarded. That distinction is invisible in the rendered output,
    because `admin_summary_output` also returns None when its query fails,
    which is why the tests assert on the query rather than on the markup.

    NOT NARROWED BY DEVICE SCOPE. These figures count Managed RTLs across the
    whole estate. This is administrator-only content about the entire fleet,
    and passing a ROLE-3 scope here would silently change what the counts
    mean without changing their labels.
    """
    user = current_identity()
    role = user.role if user else None
    if not may_perform_capability(role, VIEW_ADMINISTRATION_OVERVIEW):
        return None
    return admin_summary_output(rendered_at)


# --------------------------------------------------------------------------
# Plant / Transformer detail data (Phase 5)
#
# Named module-level functions rather than closures, matching the row
# builders above: the query-count and one-render-timestamp behaviour these
# depend on becomes directly testable without the Dash callback machinery.
# --------------------------------------------------------------------------

def build_plant_detail_view(plant_id: str, rendered_at: datetime, *, scope: DeviceScope) -> dict:
    """Everything the Plant page needs, from one `latest_reading_rows()` fetch
    and one `latest_metric_readings()` fetch — never one query per section.

    `rendered_at` is threaded into every freshness-dependent piece (Data
    Health, Metric Health, the attribution card's freshness) so the whole
    render answers "as of one instant", the same rule `get_fleet_health`
    already applies on the Fleet screen.

    `scope` is resolved once by the enclosing callback and passed down —
    never re-resolved here — so every section of this one render agrees on
    which devices are visible.
    """
    plant = hierarchy_service.get_plant_or_none(plant_id)
    transformers = hierarchy_service.list_transformers(plant_id, scope=scope)
    device_counts = {
        t.transformer_id: len(
            hierarchy_service.list_devices(t.transformer_id, scope=scope)
        )
        for t in transformers
    }
    total_devices = sum(device_counts.values())

    # One fetch, two derivations: fleet_health_from_rows and
    # metric_health_from_rows both read this same result set rather than
    # each issuing their own latest_reading_times() query.
    rows = monitoring_service.latest_reading_rows(scope=scope)
    health = monitoring_service.fleet_health_from_rows(rows, rendered_at)
    metric_health_items = monitoring_service.metric_health_from_rows(
        rows, plant_id=plant_id, now=rendered_at
    )

    temperature_readings = monitoring_service.latest_metric_readings(
        ATTRIBUTION_METRIC_KEY, plant_id=plant_id, scope=scope
    )
    attribution = monitoring_service.hottest_temperature(temperature_readings, now=rendered_at)

    context_fields = [
        ("Country", plant.country if plant else None),
        ("Transformers", len(transformers)),
        ("Devices", total_devices),
    ]

    return {
        "table_rows": sort_transformer_rows_exception_first(
            build_transformer_rows(transformers, device_counts, health)
        ),
        "kpi_cards": plant_kpi_cards(
            plant_id=plant_id, transformers=len(transformers),
            devices=total_devices, health=health,
        ),
        "context_fields": context_fields,
        "metric_health_items": metric_health_items,
        "attribution": attribution,
    }


def build_transformer_detail_view(
    transformer_id: str, plant_name: str, transformer_code: str, rendered_at: datetime,
    *, scope: DeviceScope,
) -> dict:
    """Everything the Transformer page needs, from one `latest_reading_rows()`
    fetch and one `latest_metric_readings()` fetch.

    `plant_name`/`transformer_code` come from `page-context` (already resolved
    by the router) rather than a repository call — they are the two Entity
    Context fields that need no new query at all.

    `scope` is resolved once by the enclosing callback and passed down; see
    `build_plant_detail_view`.
    """
    devices = hierarchy_service.list_devices(transformer_id, scope=scope)

    rows = monitoring_service.latest_reading_rows(scope=scope)
    health = monitoring_service.fleet_health_from_rows(rows, rendered_at)
    metric_health_items = monitoring_service.metric_health_from_rows(
        rows, transformer_id=transformer_id, now=rendered_at
    )

    temperature_readings = monitoring_service.latest_metric_readings(
        ATTRIBUTION_METRIC_KEY, transformer_id=transformer_id, scope=scope
    )
    attribution = monitoring_service.hottest_temperature(temperature_readings, now=rendered_at)

    context_fields = [
        ("Plant", plant_name),
        ("Transformer", transformer_code),
        ("Devices", len(devices)),
    ]

    return {
        "table_rows": sort_device_rows_exception_first(build_device_rows(devices, health)),
        "kpi_cards": transformer_kpi_cards(transformer_id, len(devices), health),
        "context_fields": context_fields,
        "metric_health_items": metric_health_items,
        "attribution": attribution,
    }


def register(app) -> None:
    """Register listing callbacks on the Dash app."""

    @app.callback(
        Output("plants-table", "data"),
        Output("plants-table", "columns"),
        Output("plants-error", "children"),
        Output("fleet-kpis", "children"),
        Output("fleet-health-distribution", "children"),
        Output("fleet-systemic-state", "children"),
        Output("admin-summary", "children"),
        Output("needs-attention", "children"),
        Output("fleet-subtitle", "children"),
        Output("fleet-refreshed", "children"),
        Output("my-rtls", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_overview(context, auth_data):
        if not context or context.get("route") != "overview":
            return (no_update,) * 11

        # One instant for the whole render. Taken once here and passed to both
        # the freshness computation and the header, so the stamp cannot name a
        # moment different from the one the rows were evaluated at.
        rendered_at = datetime.now(timezone.utc)
        # Resolved once for the whole render — same reasoning as `rendered_at`.
        scope = current_device_scope()
        subtitle = []

        # One fetch, one FleetHealth, every output derived from it. Building the
        # cards (or the distribution bar) in a second callback would issue a
        # second query and let two parts of the screen answer "which devices
        # are stale?" differently.
        cards = []
        distribution = []
        systemic = []
        admin = []
        attention = []
        my_rtls = []

        def build():
            plants = hierarchy_service.list_plants(scope=scope)
            counts = hierarchy_service.get_plant_hierarchy_counts(scope=scope)
            health = monitoring_service.get_fleet_health(rendered_at, scope=scope)
            # My RTLs (TECH-WORKSPACE-1): reads the SAME shared FleetHealth
            # and scope as everything else on this render — no second query,
            # no second definition of freshness.
            my_rtls.append(my_rtls_section(scope, health))
            cards.append(
                fleet_inventory(
                    plants=len(plants),
                    transformers=sum(t for t, _d in counts.values()),
                    devices=sum(d for _t, d in counts.values()),
                )
            )
            # Layer 2 reads the same classified population as the plant table.
            # The condition card replaces the redundant all-stale/no-data
            # banner in its existing slot; callback IDs and queries stay fixed.
            distribution.append(data_freshness(health.counts))
            systemic.append(fleet_condition_panels(health.counts))
            # Administration figures, on `rendered_at` like everything else on
            # this page. These count Managed RTLs — a different population from
            # the Devices card built above, which counts Monitoring Devices.
            # The two are labelled, never reconciled; see admin_overview_service.
            #
            # Administrator-only content: `administration_section` returns None
            # for every other role WITHOUT issuing the query, so a denied role
            # does no administration work on the way to seeing nothing.
            admin.append(administration_section(rendered_at))
            attention.append(
                needs_attention(
                    build_exception_queue(
                        plants, health, rendered_at,
                        **hierarchy_code_index(plants, health),
                    )
                )
            )
            subtitle.append(fleet_subtitle_text(len(plants)))
            return sort_plant_rows_exception_first(
                build_plant_rows(plants, counts, health)
            )

        rows, columns, error = listing_outputs(
            build, PLANT_COLUMNS, "loading the plants overview"
        )
        # On failure the cards, distribution and plant count never got built,
        # so they are left blank rather than lying about data that was never
        # read — the error panel is what explains the empty screen. The
        # refresh stamp still reflects reality: the page itself rendered at
        # `rendered_at` even though the table query underneath it failed, so
        # it is not tied to `build()` succeeding.
        return (
            rows,
            columns,
            error,
            (cards[0] if cards else None),
            (distribution[0] if distribution else None),
            (systemic[0] if systemic else None),
            (admin[0] if admin else None),
            (attention[0] if attention else None),
            (subtitle[0] if subtitle else ""),
            format_render_stamp(rendered_at),
            (my_rtls[0] if my_rtls else None),
        )

    @app.callback(
        Output("transformers-table", "data"),
        Output("transformers-table", "columns"),
        Output("transformers-error", "children"),
        Output("plant-kpis", "children"),
        Output("plant-context", "children"),
        Output("plant-metric-health", "children"),
        Output("plant-attribution", "children"),
        Output("transformers-empty", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_plant_detail(context, auth_data):
        if not context or context.get("route") != "plant":
            return (no_update,) * 8
        plant_id = context.get("plant_id")

        # One instant for the whole render (§2): Data Health, Metric Health
        # and the attribution card's freshness must not disagree about which
        # instant "now" was.
        rendered_at = datetime.now(timezone.utc)
        # Resolved once for the whole render, same reasoning as `rendered_at`:
        # re-resolving per section could let two parts of one screen disagree
        # about which devices are visible.
        scope = current_device_scope()

        # AUTH-HARDEN-1R (blocker 2). `page-context` is Input, not State: this
        # callback is independently invokable with a forged plant_id, and the
        # router's own scope check (callbacks/routing.py) only ever ran for
        # the render that BUILT page-context, not for this one. Without this,
        # a Technician who fabricates {"route": "plant", "plant_id": "<not
        # theirs>"} gets that plant's context and transformer
        # rows — the same class of bypass P0-3 closed for device telemetry.
        # Checked BEFORE build(), so an out-of-scope plant never even reaches
        # get_plant_or_none()/list_transformers().
        if not entity_in_scope(scope, plant_id=plant_id):
            logger.warning(
                "Plant detail refused: plant %r outside the session's device "
                "scope",
                plant_id,
            )
            return ([], TRANSFORMER_COLUMNS, error_panel(), None, None, None, None, None)

        result: dict = {}

        def build():
            result.update(build_plant_detail_view(plant_id, rendered_at, scope=scope))
            return result["table_rows"]

        rows, columns, error = listing_outputs(
            build, TRANSFORMER_COLUMNS, f"loading transformers for plant_id={plant_id!r}"
        )
        # On failure `result` never got populated. The new sections render
        # blank rather than a second copy of the error message — the single
        # `transformers-error` slot above already says the page failed to
        # load; the existing plant-kpis output already follows this rule.
        return (
            rows,
            columns,
            error,
            result.get("kpi_cards"),
            entity_context(result["context_fields"]) if result else None,
            metric_health_overview(result["metric_health_items"]) if result else None,
            (
                temperature_attribution(result["attribution"], show_transformer=True)
                if result else None
            ),
            inventory_empty_notice(rows, error, NO_TRANSFORMERS_MESSAGE),
        )

    @app.callback(
        Output("devices-table", "data"),
        Output("devices-table", "columns"),
        Output("devices-error", "children"),
        Output("transformer-kpis", "children"),
        Output("transformer-context", "children"),
        Output("transformer-metric-health", "children"),
        Output("transformer-attribution", "children"),
        Output("devices-empty", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_transformer_detail(context, auth_data):
        if not context or context.get("route") != "transformer":
            return (no_update,) * 8
        transformer_id = context.get("transformer_id")
        plant_name = context.get("plant_name", "")
        transformer_code = context.get("transformer_code", "")

        rendered_at = datetime.now(timezone.utc)
        scope = current_device_scope()

        # AUTH-HARDEN-1R (blocker 2), same reasoning as populate_plant_detail
        # above: refused before build() reaches list_devices() for an
        # out-of-scope transformer.
        if not entity_in_scope(scope, transformer_id=transformer_id):
            logger.warning(
                "Transformer detail refused: transformer %r outside the "
                "session's device scope",
                transformer_id,
            )
            return ([], DEVICE_COLUMNS, error_panel(), None, None, None, None, None)

        result: dict = {}

        def build():
            result.update(
                build_transformer_detail_view(
                    transformer_id, plant_name, transformer_code, rendered_at,
                    scope=scope,
                )
            )
            return result["table_rows"]

        rows, columns, error = listing_outputs(
            build,
            DEVICE_COLUMNS,
            f"loading devices for transformer_id={transformer_id!r}",
        )
        return (
            rows,
            columns,
            error,
            result.get("kpi_cards"),
            entity_context(result["context_fields"]) if result else None,
            metric_health_overview(result["metric_health_items"]) if result else None,
            (
                # Transformer scope: the page header already names this
                # transformer, so the attribution card does not repeat it.
                temperature_attribution(result["attribution"], show_transformer=False)
                if result else None
            ),
            inventory_empty_notice(rows, error, NO_DEVICES_MESSAGE),
        )

    # Row-click navigation. dash_table has no non-markdown way to render a cell
    # as a link, and markdown-presentation links are hardcoded by dash_table to
    # target="_blank" (breaking in-app navigation) — so these tables render
    # plain text and a click on the identity column navigates via
    # `url.pathname`.

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("plants-table", "active_cell"),
        prevent_initial_call=True,
    )
    def navigate_from_plants_table(active_cell):
        return plant_row_target(active_cell)

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("transformers-table", "active_cell"),
        State("page-context", "data"),
        prevent_initial_call=True,
    )
    def navigate_from_transformers_table(active_cell, context):
        return transformer_row_target(active_cell, context)

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("devices-table", "active_cell"),
        prevent_initial_call=True,
    )
    def navigate_from_devices_table(active_cell):
        return device_row_target(active_cell)

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("my-rtls-table", "active_cell"),
        prevent_initial_call=True,
    )
    def navigate_from_my_rtls_table(active_cell):
        # Same link column id ("device") and the same device dashboard
        # target as devices-table — device_row_target is reused verbatim
        # rather than duplicated, so the two tables cannot drift on what
        # counts as the identity column or how a device_id becomes a URL.
        return device_row_target(active_cell)
