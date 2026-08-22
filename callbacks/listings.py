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
from components.fleet_summary import (
    fleet_health_distribution,
    fleet_kpi_cards,
    fleet_subtitle_text,
    format_render_stamp,
    plant_kpi_cards,
    transformer_kpi_cards,
)
from components.metric_health import metric_health_overview
from components.needs_attention import needs_attention
from components.status_panels import error_panel
from components.temperature_attribution import temperature_attribution
from components.unassigned_rtls import unassigned_rtl_panel
from config.metrics import ATTRIBUTION_METRIC_KEY
from components.freshness_badge import format_last_reading
from routes import device_href
from services import admin_overview_service, hierarchy_service, monitoring_service
from services.device_scope import DeviceScope, scope_from_session
from services.monitoring_service import Freshness, aggregate_freshness, reading_age, severity_rank

logger = logging.getLogger(__name__)

# The column whose cells are styled as links and whose clicks navigate.
PLANT_LINK_COLUMN = "plant"
TRANSFORMER_LINK_COLUMN = "transformer"
DEVICE_LINK_COLUMN = "device"

PLANT_COLUMNS = [
    {"name": "Plant", "id": "plant"},
    {"name": "Country", "id": "country"},
    {"name": "Fuel", "id": "fuel"},
    # Numeric so native sorting orders 900 < 1,000 < 12,000 instead of sorting
    # the formatted strings lexically. The unit lives in the header.
    {"name": "Capacity (MW)", "id": "capacity_mw", "type": "numeric"},
    {"name": "Transformers", "id": "transformers", "type": "numeric"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
    # Data-delivery freshness only, never an electrical condition (§21).
    {"name": "Data", "id": "freshness"},
]

TRANSFORMER_COLUMNS = [
    {"name": "Transformer", "id": "transformer"},
    {"name": "Devices", "id": "devices", "type": "numeric"},
    # Administrative status (active/inactive) and data freshness are separate
    # concepts per CLAUDE.md and stay separate columns. Merging them would let
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
            "fuel": p.primary_fuel or "",
            "capacity_mw": p.capacity_mw,
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
# Needs Attention row builder
# --------------------------------------------------------------------------

#: Entity type label for the panel's "Type" column. Only plants are listed;
#: transformers and devices roll up through the same FleetHealth.plants tree.
_NEEDS_ATTENTION_TYPE = "Plant"


def build_needs_attention_rows(
    plants, health, rendered_at,
) -> list[dict]:
    """Plants whose rollup is NO_DATA or STALE, exception-first, formatted.

    FRESH plants are the *absence* of an exception and are excluded — this is
    an exceptions list, not a summary. The KPI cards and distribution bar
    already summarise the full fleet.

    A plant missing from the health tree is NO_DATA over zero devices, the
    same rule the fleet table applies (``build_plant_rows``).

    ``rendered_at`` is the same ``datetime.now(timezone.utc)`` taken once at
    the start of ``populate_overview`` — the age column and the freshness
    labels agree about which moment "now" was.
    """
    rows: list[dict] = []
    for p in plants:
        rollup = health.plants.get(p.plant_id) or aggregate_freshness([])
        if rollup.state is Freshness.FRESH:
            continue
        last_updated = health.plant_last_updated.get(p.plant_id)
        last_update_text = format_last_reading(
            last_updated, reading_age(last_updated, rendered_at)
        )
        rows.append({
            "id": p.plant_id,
            "entity": p.name,
            "type": _NEEDS_ATTENTION_TYPE,
            "issue": rollup.label("devices"),
            "last_update": last_update_text,
            "href": f"/plants/{p.plant_id}",
            "_state": rollup.state.value,
            "_severity": severity_rank(rollup.state),
        })
    return sort_needs_attention_rows(rows)


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
    cause is logged in full; the panel stays generic per CLAUDE.md.
    """
    try:
        return build_rows(), columns, None
    except Exception:
        logger.exception("Listing failed while %s", context_msg)
        return [], columns, error_panel()


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


# --------------------------------------------------------------------------
# Plant / Transformer detail data (Phase 5)
#
# Named module-level functions rather than closures, matching the row
# builders above: the query-count and one-render-timestamp behaviour these
# depend on becomes directly testable without the Dash callback machinery.
# --------------------------------------------------------------------------

def _format_capacity_mw(value) -> str | None:
    """Same raw figure the Fleet/Plant table's numeric "Capacity (MW)" column
    carries, with the unit restated — Entity Context has no column header to
    carry it.

    `value` arrives as `decimal.Decimal` (the column is NUMERIC), not
    `float`: `f"{Decimal('5805.0'):g}"` renders "5805.0", preserving the
    column's stored scale, while `f"{5805.0:g}"` renders "5805" — the exact
    trailing-zero-free form dash_table's own numeric renderer already shows
    for this same value one screen away. Coercing to float first is what
    "consistent with the existing Fleet table" actually requires.
    """
    if value is None:
        return None
    return f"{float(value):g} MW"


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
        ATTRIBUTION_METRIC_KEY, plant_id=plant_id
    )
    attribution = monitoring_service.hottest_temperature(temperature_readings, now=rendered_at)

    context_fields = [
        ("Country", plant.country if plant else None),
        ("Primary fuel", plant.primary_fuel if plant else None),
        ("Capacity", _format_capacity_mw(plant.capacity_mw) if plant else None),
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
        ATTRIBUTION_METRIC_KEY, transformer_id=transformer_id
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
        Output("admin-summary", "children"),
        Output("needs-attention", "children"),
        Output("fleet-subtitle", "children"),
        Output("fleet-refreshed", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_overview(context, auth_data):
        if not context or context.get("route") != "overview":
            return (no_update,) * 9

        # One instant for the whole render. Taken once here and passed to both
        # the freshness computation and the header, so the stamp cannot name a
        # moment different from the one the rows were evaluated at.
        rendered_at = datetime.now(timezone.utc)
        # Resolved once for the whole render — same reasoning as `rendered_at`.
        scope = scope_from_session(auth_data)
        subtitle = []

        # One fetch, one FleetHealth, every output derived from it. Building the
        # cards (or the distribution bar) in a second callback would issue a
        # second query and let two parts of the screen answer "which devices
        # are stale?" differently.
        cards = []
        distribution = []
        admin = []
        attention = []

        def build():
            plants = hierarchy_service.list_plants(scope=scope)
            counts = hierarchy_service.get_plant_hierarchy_counts(scope=scope)
            health = monitoring_service.get_fleet_health(rendered_at, scope=scope)
            cards.append(
                fleet_kpi_cards(
                    plants=len(plants),
                    transformers=sum(t for t, _d in counts.values()),
                    devices=sum(d for _t, d in counts.values()),
                    health=health,
                )
            )
            # Same health.counts the Data Health KPI card above already
            # reads — a restatement, not a second computation.
            distribution.append(fleet_health_distribution(health.counts))
            # Administration figures, on `rendered_at` like everything else on
            # this page. These count Managed RTLs — a different population from
            # the Devices card built above, which counts Monitoring Devices.
            # The two are labelled, never reconciled; see admin_overview_service.
            admin.append(admin_summary_output(rendered_at))
            attention.append(
                needs_attention(
                    build_needs_attention_rows(plants, health, rendered_at)
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
            (admin[0] if admin else None),
            (attention[0] if attention else None),
            (subtitle[0] if subtitle else ""),
            format_render_stamp(rendered_at),
        )

    @app.callback(
        Output("transformers-table", "data"),
        Output("transformers-table", "columns"),
        Output("transformers-error", "children"),
        Output("plant-kpis", "children"),
        Output("plant-context", "children"),
        Output("plant-metric-health", "children"),
        Output("plant-attribution", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_plant_detail(context, auth_data):
        if not context or context.get("route") != "plant":
            return (no_update,) * 7
        plant_id = context.get("plant_id")

        # One instant for the whole render (§2): Data Health, Metric Health
        # and the attribution card's freshness must not disagree about which
        # instant "now" was.
        rendered_at = datetime.now(timezone.utc)
        # Resolved once for the whole render, same reasoning as `rendered_at`:
        # re-resolving per section could let two parts of one screen disagree
        # about which devices are visible.
        scope = scope_from_session(auth_data)
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
        )

    @app.callback(
        Output("devices-table", "data"),
        Output("devices-table", "columns"),
        Output("devices-error", "children"),
        Output("transformer-kpis", "children"),
        Output("transformer-context", "children"),
        Output("transformer-metric-health", "children"),
        Output("transformer-attribution", "children"),
        Input("page-context", "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_transformer_detail(context, auth_data):
        if not context or context.get("route") != "transformer":
            return (no_update,) * 7
        transformer_id = context.get("transformer_id")
        plant_name = context.get("plant_name", "")
        transformer_code = context.get("transformer_code", "")

        rendered_at = datetime.now(timezone.utc)
        scope = scope_from_session(auth_data)
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
