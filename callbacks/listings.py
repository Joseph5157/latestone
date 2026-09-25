"""Listing callbacks — populate drill-down tables and handle row navigation.

Row builders and navigation targets are module-level functions so they can be
tested without a Dash runtime; `register()` only wires them up.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import Input, Output, State, no_update

from components.entity_context import entity_context
from components.entity_table import sort_table_rows
from components.fleet_summary import (
    plant_kpi_cards,
    transformer_kpi_cards,
)
from components.metric_health import metric_health_overview
from components.status_panels import empty_data_panel, error_panel
from components.temperature_attribution import temperature_attribution
from config.metrics import ATTRIBUTION_METRIC_KEY
from routes import device_href
from services import hierarchy_service, monitoring_service
from services.hierarchy_service import entity_in_scope
from services.device_scope import DeviceScope, current_device_scope
from services.monitoring_service import aggregate_freshness, severity_rank

logger = logging.getLogger(__name__)

# The column whose cells are styled as links and whose clicks navigate.
PLANT_LINK_COLUMN = "plant"
TRANSFORMER_LINK_COLUMN = "transformer"
DEVICE_LINK_COLUMN = "device"


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

#: TABLE-SORT-TEXT-1: Data renders a freshness label, which sorts A-Z under
#: native sort rather than by severity. Both tables above share this one
#: override — `_severity` is the same hidden key `sort_transformer_rows_
#: exception_first`/`sort_device_rows_exception_first` already rank on.
FRESHNESS_SORT_OVERRIDES = {"freshness": "_severity"}

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

    Used by a Technician's Devices page. Labels come from ONE scoped `hierarchy_service.list_device_paths` call —
    never `list_all_devices`/`hierarchy_code_index`, both unscoped fleet-wide
    reads ADR-004 forbids a restricted caller's render from reaching. Skipped
    entirely when there are no ids to resolve, so an EMPTY scope costs zero
    label queries, matching the zero this function costs an UNRESTRICTED
    caller by never being called for one.
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
        Input("transformers-table", "sort_by"),
        prevent_initial_call=True,
    )
    def populate_plant_detail(context, auth_data, sort_by=None):
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
        # TABLE-SORT-TEXT-1: a no-op until the operator clicks a header;
        # `build_plant_detail_view` already ran the exception-first default.
        rows = sort_table_rows(rows, sort_by, FRESHNESS_SORT_OVERRIDES)
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
        Input("devices-table", "sort_by"),
        prevent_initial_call=True,
    )
    def populate_transformer_detail(context, auth_data, sort_by=None):
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
        # TABLE-SORT-TEXT-1: a no-op until the operator clicks a header;
        # `build_transformer_detail_view` already ran the exception-first
        # default.
        rows = sort_table_rows(rows, sort_by, FRESHNESS_SORT_OVERRIDES)
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


