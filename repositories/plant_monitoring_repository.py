"""
Plant monitoring repository — the only module containing raw SQL.

No generic raw-query helpers exist here. Identifiers (schema name) come from
application configuration, never from browser or user input. Metric lists are
bound with SQLAlchemy expanding parameters — never interpolated into SQL strings.

There is no unbounded reading query by design: PostgreSQL must always perform
device/metric/time-range filtering.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import String, bindparam, text

from config.settings import monitoring
from db.engine import session_scope

_SCHEMA = monitoring.schema

# Administrative status only. Never a monitoring condition — see AGENTS.md.
ACTIVE_STATUS = "active"


@dataclass(frozen=True)
class PlantRecord:
    plant_id: str
    name: str
    country: str
    latitude: float
    longitude: float
    capacity_mw: float | None
    primary_fuel: str | None
    status: str


@dataclass(frozen=True)
class TransformerRecord:
    transformer_id: str
    plant_id: str
    transformer_code: str
    status: str


@dataclass(frozen=True)
class DeviceRecord:
    """device_id/transformer_id/device_code/status are the DB-M0 baseline.

    The six trailing fields are DB-1's additive metadata columns (all
    nullable in the schema). They default to None so DeviceRecord(*row)
    keeps working unchanged wherever a query only ever selected the
    original four columns (list_devices/get_device now select all ten;
    this default only matters if a future caller selects fewer).
    """
    device_id: str
    transformer_id: str
    device_code: str
    status: str
    msisdn: str | None = None
    hardware_version: str | None = None
    firmware_version: str | None = None
    installed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class DevicePath:
    plant_id: str
    plant_name: str
    transformer_id: str
    transformer_code: str
    device_id: str
    device_code: str
    device_status: str


@dataclass(frozen=True)
class RawReading:
    device_id: str
    metric: str
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class UserRecord:
    user_id: int
    username: str
    full_name: str
    email_address: str | None
    mobile_number: str | None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AssignmentRecord:
    assignment_id: int
    device_id: str
    user_id: int
    username: str
    assigned_at: datetime
    assigned_by: int | None
    ended_at: datetime | None


@dataclass(frozen=True)
class AssignmentChange:
    """Result of an assignment attempt when callers need before/after state
    (AUD-1 audit composition). ``changed`` is False only for the genuine
    no-op — re-assigning the technician who already holds the device — in
    which case no rows were written and ``previous``/``current`` are the
    same pre-existing active row.
    """

    previous: AssignmentRecord | None
    current: AssignmentRecord
    changed: bool


def _to_plant(row) -> PlantRecord:
    """latitude/longitude/capacity_mw are NUMERIC columns — psycopg2/SQLAlchemy
    return those as decimal.Decimal, not the float PlantRecord declares. Cast
    here so every caller gets the real type, not just one that prints the same.
    """
    return PlantRecord(
        row[0], row[1], row[2],
        float(row[3]), float(row[4]),
        float(row[5]) if row[5] is not None else None,
        row[6], row[7],
    )


def _to_transformer(row) -> TransformerRecord:
    return TransformerRecord(*row)


def _to_device(row) -> DeviceRecord:
    return DeviceRecord(*row)


def _to_reading(row) -> RawReading:
    return RawReading(row[0], row[1], row[2], float(row[3]))


def _to_user(row) -> UserRecord:
    return UserRecord(*row)


def _to_assignment(row) -> AssignmentRecord:
    return AssignmentRecord(*row)


_ASSIGNMENT_COLUMNS = (
    "a.assignment_id, a.device_id, a.user_id, u.username, "
    "a.assigned_at, a.assigned_by, a.ended_at"
)


_USER_COLUMNS = (
    "user_id, username, full_name, email_address, mobile_number, "
    "role, status, created_at, updated_at"
)

_DEVICE_COLUMNS = (
    "device_id, transformer_id, device_code, status, "
    "msisdn, hardware_version, firmware_version, installed_at, "
    "created_at, updated_at"
)


# ---------------------------------------------------------------------------
# Hierarchy queries
# ---------------------------------------------------------------------------

#: The bound parameter name every scoped query uses. One name, so the
#: expanding bindparam is declared identically everywhere.
_SCOPE_PARAM = "allowed_device_ids"


def _scope_clause(alias: str, allowed_device_ids) -> tuple[str, dict]:
    """SQL fragment and params constraining `<alias>.device_id` to a set.

    ROLE-BLIND BY CONSTRUCTION. This understands "restrict to these device
    ids" and nothing else — not what a technician is, not why a device is in
    scope, not that assignments exist. Scope semantics live in
    services/device_scope.py.

    `None` means unrestricted and produces no SQL. An EMPTY frozenset is a
    real constraint that matches nothing, and the difference between the two
    is load-bearing: collapsing them would hand an unassigned technician the
    whole fleet.
    """
    if allowed_device_ids is None:
        return "", {}
    return (
        f" AND {alias}.device_id IN :{_SCOPE_PARAM}",
        {_SCOPE_PARAM: list(allowed_device_ids)},
    )


def _scoped(statement, allowed_device_ids):
    """Declare the expanding bindparam when the statement is constrained.

    `type_=String` is required, not decorative: device ids are varchar, and
    when `allowed_device_ids` is empty SQLAlchemy has no values to infer a
    type from, so an untyped expanding bindparam defaults to Integer and
    renders `IN (SELECT CAST(NULL AS INTEGER) WHERE 1!=1)` — a type mismatch
    against a varchar column on Postgres. That failure mode only surfaces
    when the empty-set case actually executes against real SQL.
    """
    if allowed_device_ids is None:
        return statement
    return statement.bindparams(
        bindparam(_SCOPE_PARAM, expanding=True, type_=String)
    )


def list_plants(*, allowed_device_ids: frozenset[str] | None) -> list[PlantRecord]:
    """Plants, constrained to those holding at least one visible device.

    The constraint is an EXISTS rather than a join so a plant is never
    duplicated by the number of matching devices beneath it.
    """
    scope_sql, scope_params = _scope_clause("d", allowed_device_ids)
    where = ""
    if scope_sql:
        where = (
            f" WHERE EXISTS (SELECT 1 FROM {_SCHEMA}.transformers t "
            f"JOIN {_SCHEMA}.devices d ON d.transformer_id = t.transformer_id "
            f"WHERE t.plant_id = p.plant_id{scope_sql})"
        )
    statement = _scoped(
        text(f"SELECT p.plant_id, p.name, p.country, p.latitude, p.longitude, "
             f"p.capacity_mw, p.primary_fuel, p.status "
             f"FROM {_SCHEMA}.plants p{where} ORDER BY p.name"),
        allowed_device_ids,
    )
    with session_scope() as session:
        rows = session.execute(statement, scope_params).all()
    return [_to_plant(r) for r in rows]


def get_plant(plant_id: str) -> PlantRecord | None:
    with session_scope() as session:
        row = session.execute(
            text(f"SELECT plant_id, name, country, latitude, longitude, "
                 f"capacity_mw, primary_fuel, status FROM {_SCHEMA}.plants "
                 f"WHERE plant_id = :plant_id"),
            {"plant_id": plant_id},
        ).first()
    return _to_plant(row) if row else None


def list_transformers(
    plant_id: str, *, allowed_device_ids: frozenset[str] | None
) -> list[TransformerRecord]:
    """Transformers under one plant, constrained to those holding at least
    one visible device."""
    scope_sql, scope_params = _scope_clause("d", allowed_device_ids)
    extra = ""
    if scope_sql:
        extra = (
            f" AND EXISTS (SELECT 1 FROM {_SCHEMA}.devices d "
            f"WHERE d.transformer_id = t.transformer_id{scope_sql})"
        )
    statement = _scoped(
        text(f"SELECT t.transformer_id, t.plant_id, t.transformer_code, t.status "
             f"FROM {_SCHEMA}.transformers t "
             f"WHERE t.plant_id = :plant_id{extra} "
             f"ORDER BY t.transformer_code"),
        allowed_device_ids,
    )
    with session_scope() as session:
        rows = session.execute(
            statement, {"plant_id": plant_id, **scope_params}
        ).all()
    return [_to_transformer(r) for r in rows]


def get_transformer(transformer_id: str) -> TransformerRecord | None:
    with session_scope() as session:
        row = session.execute(
            text(f"SELECT transformer_id, plant_id, transformer_code, status "
                 f"FROM {_SCHEMA}.transformers WHERE transformer_id = :transformer_id"),
            {"transformer_id": transformer_id},
        ).first()
    return _to_transformer(row) if row else None


def list_devices(
    transformer_id: str, *, allowed_device_ids: frozenset[str] | None
) -> list[DeviceRecord]:
    """Devices under one transformer, constrained to a visible set.

    `allowed_device_ids` is keyword-only and undefaulted on purpose: a default
    of None would let an omitted argument silently return the whole
    transformer, which is a fail-open seam wearing the costume of a safe
    default (ROLE-3 invariant 8).
    """
    scope_sql, scope_params = _scope_clause("devices", allowed_device_ids)
    statement = _scoped(
        text(f"SELECT {_DEVICE_COLUMNS} "
             f"FROM {_SCHEMA}.devices AS devices "
             f"WHERE devices.transformer_id = :transformer_id{scope_sql} "
             f"ORDER BY devices.device_code"),
        allowed_device_ids,
    )
    with session_scope() as session:
        rows = session.execute(
            statement, {"transformer_id": transformer_id, **scope_params}
        ).all()
    return [_to_device(r) for r in rows]


def get_device(device_id: str) -> DeviceRecord | None:
    with session_scope() as session:
        row = session.execute(
            text(f"SELECT {_DEVICE_COLUMNS} "
                 f"FROM {_SCHEMA}.devices WHERE device_id = :device_id"),
            {"device_id": device_id},
        ).first()
    return _to_device(row) if row else None


def get_device_breadcrumb(device_id: str) -> DevicePath | None:
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT p.plant_id, p.name, t.transformer_id, t.transformer_code,
                       d.device_id, d.device_code, d.status
                FROM {_SCHEMA}.devices d
                JOIN {_SCHEMA}.transformers t ON t.transformer_id = d.transformer_id
                JOIN {_SCHEMA}.plants p       ON p.plant_id = t.plant_id
                WHERE d.device_id = :device_id
                """
            ),
            {"device_id": device_id},
        ).first()
    return DevicePath(*row) if row else None


def list_device_paths(
    device_ids, *, allowed_device_ids: frozenset[str] | None
) -> list[DevicePath]:
    """Label paths for a BOUNDED set of devices, in one query (ADR-008).

    The batched form of `get_device_breadcrumb`. Command Center names the
    assets on its event rows through this: resolving them through
    `list_transformers`/`list_devices` would be one query per distinct plant
    AND per distinct transformer on screen, which is the N+1 shape ADR-008
    exists to prevent on a page intended to auto-refresh.

    `allowed_device_ids` is keyword-only and undefaulted for the same reason
    it is everywhere else here: an omitted argument must not silently return
    the fleet (ROLE-3 invariant 8). Scope is applied in SQL, never by the
    caller filtering afterwards.

    STATUS IS NOT FILTERED, unlike `list_devices`. That filter answers "what
    is selectable for live monitoring"; this answers "what is this device
    called", and an event that already happened does not stop needing a name
    because its RTL was later deactivated.

    Ids that match nothing are simply absent from the result — a caller
    labels what it can and keeps the rest.
    """
    ids = list(dict.fromkeys(device_ids))
    if not ids:
        return []          # no ids, no query — mirrors list_recent_device_events

    scope_sql, scope_params = _scope_clause("d", allowed_device_ids)
    statement = _scoped(
        text(
            f"""
            SELECT p.plant_id, p.name, t.transformer_id, t.transformer_code,
                   d.device_id, d.device_code, d.status
            FROM {_SCHEMA}.devices d
            JOIN {_SCHEMA}.transformers t ON t.transformer_id = d.transformer_id
            JOIN {_SCHEMA}.plants p       ON p.plant_id = t.plant_id
            WHERE d.device_id IN :device_ids{scope_sql}
            ORDER BY d.device_id
            """
        ).bindparams(bindparam("device_ids", expanding=True, type_=String)),
        allowed_device_ids,
    )
    with session_scope() as session:
        rows = session.execute(
            statement, {"device_ids": ids, **scope_params}
        ).all()
    return [DevicePath(*row) for row in rows]


def count_hierarchy_by_plant(
    *, allowed_device_ids: frozenset[str] | None, include_inactive: bool = False
) -> dict[str, tuple[int, int]]:
    """Returns {plant_id: (transformer_count, device_count)}.

    Counts **Monitoring Devices** — active devices under active transformers.
    Administration figures count Managed RTLs instead (see the ADMIN-1 section
    header), so this device total and the administration total may legitimately
    differ; neither is wrong and they must not be swapped.

    Counts the same population the drill-down pages list. Without the status
    filters an overview row could claim 4 transformers and then show 3 once
    opened, because `list_transformers`/`list_devices` exclude inactive
    equipment by default.

    The filters sit in the JOIN, not a WHERE clause: moving them to WHERE would
    turn the LEFT JOINs inner and drop plants that have no active equipment
    from the overview entirely.

    SCOPE IS APPLIED BEFORE AGGREGATION (ROLE-3 invariant 4). The constraint
    sits in the transformer JOIN, the device JOIN, and a plant-level EXISTS,
    so a scoped caller receives counts of what they may see rather than fleet
    counts trimmed afterwards. The transformer JOIN needs its own EXISTS
    (against a distinct `d2` alias) because a transformer whose only devices
    are out of scope must not be counted either — without it, that
    transformer survives via its own status-filtered row (device columns
    NULL from the LEFT JOIN) and inflates COUNT(DISTINCT t.transformer_id)
    past what list_transformers would actually list for the same scope. A
    plant with no visible device drops out entirely — unlike the status
    filters, which deliberately keep such plants at zero, because a plant
    outside your scope is not a plant of yours that happens to be empty.
    """
    status_filter = "" if include_inactive else " AND t.status = :active"
    device_filter = "" if include_inactive else " AND d.status = :active"
    scope_sql, scope_params = _scope_clause("d", allowed_device_ids)

    tx_scope_sql, _ = _scope_clause("d2", allowed_device_ids)
    transformer_filter = ""
    if tx_scope_sql:
        transformer_filter = (
            f" AND EXISTS (SELECT 1 FROM {_SCHEMA}.devices d2 "
            f"WHERE d2.transformer_id = t.transformer_id{tx_scope_sql})"
        )

    plant_filter = ""
    if scope_sql:
        plant_filter = (
            f" WHERE EXISTS (SELECT 1 FROM {_SCHEMA}.transformers t2 "
            f"JOIN {_SCHEMA}.devices d ON d.transformer_id = t2.transformer_id "
            f"WHERE t2.plant_id = p.plant_id{scope_sql})"
        )

    params = {"active": ACTIVE_STATUS, **scope_params}
    statement = _scoped(
        text(
            f"""
            SELECT p.plant_id,
                   COUNT(DISTINCT t.transformer_id) AS transformers,
                   COUNT(d.device_id)               AS devices
            FROM {_SCHEMA}.plants p
            LEFT JOIN {_SCHEMA}.transformers t
                   ON t.plant_id = p.plant_id{status_filter}{transformer_filter}
            LEFT JOIN {_SCHEMA}.devices d
                   ON d.transformer_id = t.transformer_id{device_filter}{scope_sql}
            {plant_filter}
            GROUP BY p.plant_id
            """
        ),
        allowed_device_ids,
    )
    with session_scope() as session:
        rows = session.execute(statement, params).all()
    return {r[0]: (r[1], r[2]) for r in rows}


@dataclass(frozen=True)
class AdminDeviceRow:
    """Fleet-wide device row for the admin table.

    Carries the full path context so the admin page never issues N+1 queries
    to resolve which plant/transformer a device belongs to. All fields come
    from existing tables — no new columns are required.
    """

    device_id: str
    device_code: str
    status: str
    transformer_id: str
    transformer_code: str
    plant_id: str
    plant_name: str


def list_all_devices(include_inactive: bool = False) -> list[AdminDeviceRow]:
    """Every **Managed RTL** in the fleet with its plant/transformer context.

    Administratively active devices, whatever their transformer's status —
    the administration population, not the Monitoring Devices one the Fleet
    Overview counts. See the ADMIN-1 section header for why they differ.

    One query, one result set. The admin page needs the full hierarchy path
    for every device; issuing per-transformer queries would be N+1 against
    the 71-transformer fleet.

    `include_inactive` follows the same convention as `list_devices`:
    active-only by default.
    """
    status_filter = "" if include_inactive else " AND d.status = :active"
    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT d.device_id, d.device_code, d.status,
                       t.transformer_id, t.transformer_code,
                       p.plant_id, p.name
                FROM {_SCHEMA}.devices d
                JOIN {_SCHEMA}.transformers t ON t.transformer_id = d.transformer_id
                JOIN {_SCHEMA}.plants p       ON p.plant_id = t.plant_id
                WHERE 1=1{status_filter}
                ORDER BY p.name, t.transformer_code, d.device_code
                """
            ),
            {"active": ACTIVE_STATUS},
        ).all()
    return [AdminDeviceRow(*r) for r in rows]


@dataclass(frozen=True)
class LatestReadingRow:
    """Newest reading time for one (device, metric), with its place in the tree.

    Carries both ancestor ids because the transformer join is already in the
    query: one result set then serves the fleet card, the plant table's
    freshness column and the plant screen's per-transformer rollups.
    """
    plant_id: str
    transformer_id: str
    device_id: str
    metric: str
    reading_ts: datetime | None


def latest_reading_times(
    metrics: list[str],
    *,
    allowed_device_ids: frozenset[str] | None,
    include_inactive: bool = False,
) -> list[LatestReadingRow]:
    """Newest reading per (device, metric) across the whole fleet, in one query.

    Covers **Monitoring Devices** — active devices under active transformers.
    A device under a decommissioned transformer delivers nothing to monitor,
    so it is absent here even though administration still manages it.

    Feeds both the fleet Data Health card and the per-plant freshness column —
    counting the rows gives one, grouping by plant_id gives the other. Issuing
    two near-identical queries per page load would be the obvious mistake.

    **Query shape is a contract, not an implementation detail.** The seeks are
    driven from the small `devices` relation through
    `LEFT JOIN LATERAL (... ORDER BY reading_ts DESC LIMIT 1)`, which uses
    `ix_readings_device_metric_ts` and costs one bounded seek per pair.

    The obvious alternative, `DISTINCT ON (device_id, metric)` over `readings`,
    plans as a full index scan — measured at 3332 ms against 1.38M rows versus
    ~14 ms warm here, and it degrades with history rather than with device
    count. The client's dataset is larger than ours, so a shape that scales with
    history is the wrong one regardless of how it benchmarks today.

    `metrics` is passed in rather than read from config so this layer stays
    free of presentation concerns.

    SCOPE IS APPLIED PER-ROW, NOT AGGREGATED (ROLE-3 invariant 4). This query
    is device-grained — one row per (device, metric), no GROUP BY, no COUNT —
    so constraining `d.device_id` here is already the correct grain; unlike
    `count_hierarchy_by_plant`, no separate EXISTS is needed at a coarser
    level. Every rollup (fleet health, the health distribution bar, Needs
    Attention, the Notification Center) is built from these rows in Python,
    so a caller that gets this constraint wrong shows freshness figures for a
    different population than the counts on the same screen.
    """
    if not metrics:
        return []

    # Metric keys come from application config, never from browser input, but
    # they are still bound rather than interpolated.
    values = ", ".join(f"(:m{i})" for i in range(len(metrics)))
    params = {f"m{i}": key for i, key in enumerate(metrics)}

    # Both levels, matching count_hierarchy_by_plant exactly. Filtering only on
    # the device would let a device under an inactive transformer into the
    # fleet health figures while the listing pages omit it — the two numbers
    # sit on the same screen and must describe the same population.
    status_filter = (
        "" if include_inactive
        else " AND d.status = :active AND t.status = :active"
    )
    if not include_inactive:
        params["active"] = ACTIVE_STATUS

    scope_sql, scope_params = _scope_clause("d", allowed_device_ids)
    params.update(scope_params)

    statement = _scoped(
        text(
            f"""
            SELECT t.plant_id, t.transformer_id, d.device_id,
                   m.metric, latest.reading_ts
            FROM {_SCHEMA}.devices d
            JOIN {_SCHEMA}.transformers t
              ON t.transformer_id = d.transformer_id
            CROSS JOIN (VALUES {values}) AS m(metric)
            LEFT JOIN LATERAL (
                SELECT rr.reading_ts
                FROM {_SCHEMA}.readings rr
                WHERE rr.device_id = d.device_id AND rr.metric = m.metric
                ORDER BY rr.reading_ts DESC
                LIMIT 1
            ) latest ON TRUE
            WHERE TRUE{status_filter}{scope_sql}
            """
        ),
        allowed_device_ids,
    )

    with session_scope() as session:
        rows = session.execute(statement, params).all()

    return [LatestReadingRow(r[0], r[1], r[2], r[3], r[4]) for r in rows]


@dataclass(frozen=True)
class DeviceMetricReading:
    """One device's newest reading of one metric, with its place in the tree.

    `reading_ts`/`value` are nullable: the query keeps a device that has never
    reported, so a caller can say "3 of 7 devices reporting" rather than
    silently narrowing the population it claims to describe.
    """

    plant_id: str
    transformer_id: str
    transformer_code: str
    device_id: str
    device_code: str
    metric: str
    reading_ts: datetime | None
    value: float | None


def _to_device_metric_reading(row) -> DeviceMetricReading:
    """Deliberately not `_to_reading`, which does an unguarded `float(row[3])`.

    A device with no reading of this metric arrives from the LEFT JOIN with
    NULLs, and coercing those would raise rather than report the gap.
    """
    return DeviceMetricReading(
        plant_id=row[0],
        transformer_id=row[1],
        transformer_code=row[2],
        device_id=row[3],
        device_code=row[4],
        metric=row[5],
        reading_ts=row[6],
        value=float(row[7]) if row[7] is not None else None,
    )


def latest_metric_readings(
    metric: str,
    *,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    allowed_device_ids: frozenset[str] | None,
    include_inactive: bool = False,
) -> list[DeviceMetricReading]:
    """Newest reading of ONE metric for every device beneath one entity.

    Covers **Monitoring Devices** — active devices under active transformers,
    the same population as `latest_reading_times`, so attribution and
    freshness always describe the same set.

    Deliberately single-metric and entity-scoped. Widening it to all eight
    metrics fleet-wide would make every caller pay for 960 values to read one,
    and `latest_reading_times` already covers the fleet-wide case by returning
    timestamps alone.

    Same `LEFT JOIN LATERAL (... ORDER BY reading_ts DESC LIMIT 1)` shape as
    `latest_reading_times`, for the same reason: the predicate plus ordering is
    an exact prefix of `ix_readings_device_metric_ts`, so each device costs one
    bounded index seek. It is one round trip with N seeks, not N queries — and
    emphatically not a range scan, which would read ~1,400 rows per device to
    compute a single maximum.

    The status filter is byte-identical to `latest_reading_times` so the
    population here matches the freshness figures rendered beside it. Two
    filters that drift would put two different device counts on one screen.

    DEVELOPMENT ADAPTER. The client's final schema is unknown; when it lands,
    this is reimplemented behind the same typed return contract, and nothing
    above the repository changes.
    """
    if plant_id is None and transformer_id is None:
        # Matches the module's no-unbounded-reading-query rule: without a scope
        # this would seek every device in the fleet.
        raise ValueError(
            "latest_metric_readings requires either plant_id or transformer_id"
        )

    params: dict = {"metric": metric}

    # Literal fragments, bound values — the same idiom as `latest_reading_times`
    # and `count_hierarchy_by_plant`, so this file has one way of doing it.
    if transformer_id is not None:
        scope_sql = " AND d.transformer_id = :transformer_id"
        params["transformer_id"] = transformer_id
    else:
        scope_sql = " AND t.plant_id = :plant_id"
        params["plant_id"] = plant_id

    status_filter = (
        "" if include_inactive
        else " AND d.status = :active AND t.status = :active"
    )
    if not include_inactive:
        params["active"] = ACTIVE_STATUS

    scope_clause, scope_params = _scope_clause("d", allowed_device_ids)
    params.update(scope_params)

    statement = _scoped(
        text(
            f"""
            SELECT t.plant_id, t.transformer_id, t.transformer_code,
                   d.device_id, d.device_code,
                   :metric AS metric,
                   latest.reading_ts, latest.value
            FROM {_SCHEMA}.devices d
            JOIN {_SCHEMA}.transformers t
              ON t.transformer_id = d.transformer_id
            LEFT JOIN LATERAL (
                SELECT rr.reading_ts, rr.value
                FROM {_SCHEMA}.readings rr
                WHERE rr.device_id = d.device_id AND rr.metric = :metric
                ORDER BY rr.reading_ts DESC
                LIMIT 1
            ) latest ON TRUE
            WHERE TRUE{status_filter}{scope_sql}{scope_clause}
            ORDER BY t.transformer_code, d.device_code
            """
        ),
        allowed_device_ids,
    )

    with session_scope() as session:
        rows = session.execute(statement, params).all()

    return [_to_device_metric_reading(r) for r in rows]


@dataclass(frozen=True)
class InstalledRtlsRecord:
    """One registered RTL's row for the Installed RTLs report (REPORT-2).

    `last_recorded_at`/`last_temperature` are nullable: a device that has
    never reported stays in the report with NULLs rather than silently
    disappearing — a never-reporting RTL is arguably the most operationally
    interesting row an inventory report can show.
    """

    plant_id: str
    transformer_id: str
    transformer_code: str
    device_id: str
    device_code: str
    status: str
    last_recorded_at: datetime | None
    last_temperature: float | None


def _to_installed_rtls_record(row) -> InstalledRtlsRecord:
    return InstalledRtlsRecord(
        plant_id=row[0],
        transformer_id=row[1],
        transformer_code=row[2],
        device_id=row[3],
        device_code=row[4],
        status=row[5],
        last_recorded_at=row[6],
        last_temperature=float(row[7]) if row[7] is not None else None,
    )


def installed_rtls_report_rows(
    *,
    temperature_metric: str,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    device_id: str | None = None,
    allowed_device_ids: frozenset[str] | None,
) -> list[InstalledRtlsRecord]:
    """Every registered device in scope, for the Installed RTLs report.

    DELIBERATELY NO STATUS FILTER (R2-D3). The client's report carries an
    "RTL Status" column, so filtering administrative inactive devices out at
    query time would redefine "Installed RTLs" as "Active RTLs" and hollow
    out that column. This is also the one place the codebase treats
    administrative `devices.status` as report *output* rather than a
    population filter; if the client later confirms installed means active,
    that business rule gets applied here, explicitly.

    Two independent LATERAL seeks against `ix_readings_device_metric_ts`,
    the same bounded-seek shape as `latest_reading_times`:

    - latest_any   — newest reading of ANY metric. R2-D1 development
      semantic: "Timestamp of Last Recorded Data" means general device
      communication freshness, pending client confirmation.
    - latest_temp  — newest temperature value only.

    They are not required to agree; an RTL whose temperature channel lags
    its other metrics shows two different timestamps by design.

    `temperature_metric` is passed in rather than read from config so this
    layer stays free of presentation concerns, exactly as in
    `latest_reading_times`.

    Scope is the intersection of the caller's ROLE-3 device set and the
    report's asset-scope selection, both ANDed here — never resolved in two
    different places. Zero readings keep the row (LEFT JOIN, not INNER).
    """
    params: dict = {"temp_metric": temperature_metric}

    asset_sql = ""
    if device_id is not None:
        asset_sql += " AND d.device_id = :device_id"
        params["device_id"] = device_id
    if transformer_id is not None:
        asset_sql += " AND d.transformer_id = :transformer_id"
        params["transformer_id"] = transformer_id
    if plant_id is not None:
        asset_sql += " AND t.plant_id = :plant_id"
        params["plant_id"] = plant_id

    scope_sql, scope_params = _scope_clause("d", allowed_device_ids)
    params.update(scope_params)

    statement = _scoped(
        text(
            f"""
            SELECT t.plant_id, d.transformer_id, t.transformer_code,
                   d.device_id, d.device_code, d.status,
                   latest_any.reading_ts, latest_temp.value
            FROM {_SCHEMA}.devices d
            JOIN {_SCHEMA}.transformers t
              ON t.transformer_id = d.transformer_id
            LEFT JOIN LATERAL (
                SELECT rr.reading_ts
                FROM {_SCHEMA}.readings rr
                WHERE rr.device_id = d.device_id
                ORDER BY rr.reading_ts DESC
                LIMIT 1
            ) latest_any ON TRUE
            LEFT JOIN LATERAL (
                SELECT rr.value
                FROM {_SCHEMA}.readings rr
                WHERE rr.device_id = d.device_id AND rr.metric = :temp_metric
                ORDER BY rr.reading_ts DESC
                LIMIT 1
            ) latest_temp ON TRUE
            WHERE TRUE{asset_sql}{scope_sql}
            ORDER BY t.transformer_code, d.device_code
            """
        ),
        allowed_device_ids,
    )

    with session_scope() as session:
        rows = session.execute(statement, params).all()

    return [_to_installed_rtls_record(r) for r in rows]


@dataclass(frozen=True)
class RtlAlarms30dRecord:
    """One qualifying alarm event's row for the RTL Alarms (30 Days)
    report (REPORT-3).

    ``event_transformer_id``/``event_transformer_code`` carry the
    event-time snapshot written at ingestion; ``current_transformer_code``
    is the device's present transformer. Which one populates the report
    cell is the R3-D6 rule and lives in the SERVICE, not here.
    ``alarm_at`` is the source occurrence time (EVT-D9); battery/temperature
    are display payload (EVT-D4).
    """

    event_id: int
    event_type: str
    alarm_at: datetime
    event_transformer_id: str | None
    event_transformer_code: str | None
    current_transformer_code: str | None
    device_code: str | None
    firmware_version: str | None
    temperature: float | None
    battery_voltage: float | None


def rtl_alarms_30d_report_rows(
    *,
    event_types: Sequence[str],
    since: datetime,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    device_id: str | None = None,
    allowed_device_ids: frozenset[str] | None,
) -> list[RtlAlarms30dRecord]:
    """Qualifying alarm events for the RTL Alarms (30 Days) report.

    REPORT-3 (R3-D2): one dedicated joined query — events plus the device/
    transformer metadata every row needs, in a single pass.

    - ``event_types`` is supplied by the caller; the SERVICE derives it
      from EventSemantics.is_reportable_alarm (R3-D1), so this layer never
      re-states which types are alarms.
    - INNER JOIN devices: only resolved events can be alarms (EVT-D6);
      quarantined unattributed rows cannot appear.
    - Scope is ROLE-3 device set ∩ asset-scope selection, both ANDed here
      (R3-D7) — identical mechanics to installed_rtls_report_rows.
    - Ordered ``event_ts DESC, event_id DESC`` (R3-D4 / INGEST-D4
      tiebreak). One row per persisted qualifying event (R3-D3); no
      collapsing, no dedup.
    """
    if not event_types:
        return []

    params: dict = {"event_types": list(event_types), "since": since}

    asset_sql = ""
    if device_id is not None:
        asset_sql += " AND d.device_id = :device_id"
        params["device_id"] = device_id
    if transformer_id is not None:
        asset_sql += " AND d.transformer_id = :transformer_id"
        params["transformer_id"] = transformer_id
    if plant_id is not None:
        asset_sql += " AND t.plant_id = :plant_id"
        params["plant_id"] = plant_id

    scope_sql, scope_params = _scope_clause("d", allowed_device_ids)
    params.update(scope_params)

    statement = _scoped(
        text(
            f"""
            SELECT e.event_id, e.event_type, e.event_ts,
                   e.transformer_id, t_evt.transformer_code,
                   t_cur.transformer_code,
                   d.device_code, d.firmware_version,
                   e.temperature, e.battery_voltage
            FROM {_SCHEMA}.device_events e
            JOIN {_SCHEMA}.devices d
              ON d.device_id = e.device_id
            JOIN {_SCHEMA}.transformers t_cur
              ON t_cur.transformer_id = d.transformer_id
            LEFT JOIN {_SCHEMA}.transformers t_evt
              ON t_evt.transformer_id = e.transformer_id
            WHERE e.event_type IN :event_types
              AND e.event_ts >= :since{asset_sql}{scope_sql}
            ORDER BY e.event_ts DESC, e.event_id DESC
            """
        ).bindparams(bindparam("event_types", expanding=True, type_=String)),
        allowed_device_ids,
    )

    with session_scope() as session:
        rows = session.execute(statement, params).all()

    return [
        RtlAlarms30dRecord(
            event_id=r[0],
            event_type=r[1],
            alarm_at=r[2],
            event_transformer_id=r[3],
            event_transformer_code=r[4],
            current_transformer_code=r[5],
            device_code=r[6],
            firmware_version=r[7],
            temperature=float(r[8]) if r[8] is not None else None,
            battery_voltage=float(r[9]) if r[9] is not None else None,
        )
        for r in rows
    ]


@dataclass(frozen=True)
class MaxTemperatureRecord:
    """One transformer's peak-temperature row for the Maximum Temperature
    report (REPORT-MAXTEMP-1).

    ``device_id``/``installed_at`` describe the SPECIFIC device whose
    reading produced ``max_temperature`` — see
    ``max_temperature_report_rows`` for why that is the only defensible
    "Date Installed" source. All three of ``device_id``,
    ``max_temperature``, ``max_reading_at`` and ``installed_at`` are None
    together whenever the transformer has no in-window, in-scope
    temperature reading (a legitimate empty row, not an error).
    """

    plant_id: str
    transformer_id: str
    transformer_code: str
    device_id: str | None
    max_temperature: float | None
    max_reading_at: datetime | None
    installed_at: datetime | None


def _to_max_temperature(row) -> MaxTemperatureRecord:
    return MaxTemperatureRecord(
        plant_id=row[0],
        transformer_id=row[1],
        transformer_code=row[2],
        device_id=row[3],
        max_temperature=float(row[4]) if row[4] is not None else None,
        max_reading_at=row[5],
        installed_at=row[6],
    )


def max_temperature_report_rows(
    *,
    temperature_metric: str,
    since: datetime,
    until: datetime,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    device_id: str | None = None,
    allowed_device_ids: frozenset[str] | None,
) -> list[MaxTemperatureRecord]:
    """One row per transformer: its single highest temperature reading in
    the closed window ``[since, until]`` (REPORT-MAXTEMP-1 / C-15).

    RMT-D1 (tie-break): when more than one reading shares the maximum
    value, the winner is deterministic — earliest ``reading_ts`` first (the
    first time the peak was reached), then ``device_id``, then the
    ``readings.id`` identity column as a final, unconditional tiebreak.
    Same inputs always name the same winning reading; nothing is left to
    whatever order the planner happens to visit rows in.

    RMT-D2 (Date Installed): there is no transformer-level installation
    date anywhere in this schema — only ``devices.installed_at``, itself
    optional metadata set at device registration (DB-1, migration 002).
    Synthesizing a transformer-level date (earliest of its devices', say)
    would report a date about a device that is not the one this row's
    reading came from. Instead this reports ``installed_at`` of the exact
    device that produced ``max_temperature`` — the one device the row is
    actually about — and leaves it None when that device has none, rather
    than inventing one.

    Two independent scope gates, both matching the convention already used
    by ``count_hierarchy_by_plant``: an outer EXISTS keeps a transformer out
    entirely when the caller has zero visible devices anywhere on it (no
    Technician sees a transformer they hold no assignment on, even as a
    bare code with null data — same as ``list_transformers``); the LATERAL
    itself additionally restricts which of that transformer's OWN devices
    may supply the winning reading, so a transformer with a mix of in- and
    out-of-scope devices never lets an out-of-scope device's reading win.

    Transformers with no in-scope device, or no temperature reading in the
    window, are never dropped by the window/metric filter itself — they
    surface as a real row with every reading field None (R2-D4/R3-D8's
    "legitimate empty" convention), never an exception. Only the scope
    EXISTS gate above removes a row outright, and only for reasons of
    visibility, never data absence.
    """
    params: dict = {
        "temp_metric": temperature_metric,
        "since": since,
        "until": until,
    }

    asset_sql = ""
    if transformer_id is not None:
        asset_sql += " AND t.transformer_id = :transformer_id"
        params["transformer_id"] = transformer_id
    if plant_id is not None:
        asset_sql += " AND t.plant_id = :plant_id"
        params["plant_id"] = plant_id

    device_sql = ""
    if device_id is not None:
        device_sql = " AND r.device_id = :device_id"
        params["device_id"] = device_id

    lateral_scope_sql, scope_params = _scope_clause("r", allowed_device_ids)
    params.update(scope_params)

    exists_scope_sql, _ = _scope_clause("d2", allowed_device_ids)
    transformer_visibility_sql = ""
    if exists_scope_sql:
        transformer_visibility_sql = (
            f" AND EXISTS (SELECT 1 FROM {_SCHEMA}.devices d2 "
            f"WHERE d2.transformer_id = t.transformer_id{exists_scope_sql})"
        )

    statement = _scoped(
        text(
            f"""
            SELECT t.plant_id, t.transformer_id, t.transformer_code,
                   top.device_id, top.value, top.reading_ts, d.installed_at
            FROM {_SCHEMA}.transformers t
            LEFT JOIN LATERAL (
                SELECT r.device_id, r.value, r.reading_ts
                FROM {_SCHEMA}.readings r
                JOIN {_SCHEMA}.devices dd ON dd.device_id = r.device_id
                WHERE dd.transformer_id = t.transformer_id
                  AND r.metric = :temp_metric
                  AND r.reading_ts >= :since AND r.reading_ts <= :until
                  {device_sql}{lateral_scope_sql}
                ORDER BY r.value DESC, r.reading_ts ASC, r.device_id ASC, r.id ASC
                LIMIT 1
            ) top ON TRUE
            LEFT JOIN {_SCHEMA}.devices d ON d.device_id = top.device_id
            WHERE TRUE{asset_sql}{transformer_visibility_sql}
            ORDER BY t.transformer_code
            """
        ),
        allowed_device_ids,
    )

    with session_scope() as session:
        rows = session.execute(statement, params).all()

    return [_to_max_temperature(r) for r in rows]


# ---------------------------------------------------------------------------
# Reading queries
# ---------------------------------------------------------------------------

def insert_readings(readings: Sequence[RawReading]) -> None:
    """Append-only write for db/live_simulator.py's per-tick readings.

    One parameterized multi-row INSERT — distinct from
    db/seed_plant_monitoring.py's psycopg2 COPY, which exists for that
    script's much larger one-time historical volume and isn't a fit for a
    handful of rows per tick.
    """
    if not readings:
        return
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {_SCHEMA}.readings (device_id, metric, reading_ts, value) "
                f"VALUES (:device_id, :metric, :reading_ts, :value)"
            ),
            [
                {
                    "device_id": r.device_id,
                    "metric": r.metric,
                    "reading_ts": r.timestamp,
                    "value": r.value,
                }
                for r in readings
            ],
        )


def get_latest_reading(device_id: str, metric: str) -> RawReading | None:
    with session_scope() as session:
        row = session.execute(
            text(
                f"SELECT device_id, metric, reading_ts, value "
                f"FROM {_SCHEMA}.readings "
                f"WHERE device_id = :device_id AND metric = :metric "
                f"ORDER BY reading_ts DESC LIMIT 1"
            ),
            {"device_id": device_id, "metric": metric},
        ).first()
    return _to_reading(row) if row else None


def get_last_reading_before(
    device_id: str, metric: str, ts: datetime
) -> RawReading | None:
    """Newest reading strictly before `ts`, or None if there is none.

    Opens the first energy bin. A bar is consumption *across* its bin, so the
    first one needs the meter value at the window start — a reading that lies
    outside the window. Without it the first bar is short by one sampling
    interval, and nothing on screen says so.

    Strictly before, not at-or-before: including the instant itself would make
    the first bar cover zero elapsed time.

    One bounded seek against `ix_readings_device_metric_ts`, the same shape as
    `latest_reading_times`.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"SELECT device_id, metric, reading_ts, value "
                f"FROM {_SCHEMA}.readings "
                f"WHERE device_id = :device_id AND metric = :metric "
                f"AND reading_ts < :ts "
                f"ORDER BY reading_ts DESC LIMIT 1"
            ),
            {"device_id": device_id, "metric": metric, "ts": ts},
        ).first()
    return _to_reading(row) if row else None


def get_latest_readings_for_device(
    device_id: str, metrics: list[str] | None = None
) -> dict[str, RawReading]:
    """One query for all requested metrics — never one query per metric.

    **Bounded index seeks, not a range scan** — the same contract
    `latest_reading_times` states, applied at device grain. The obvious shape,
    `DISTINCT ON (metric) ... ORDER BY metric, reading_ts DESC`, plans as an
    index scan across the device's entire history: measured at 11,528 rows and
    463 buffers to return 8 values on the seeded database. Its cost grows with
    every reading the client ever logs, and the client's history is longer than
    ours.

    Two bounded stages replace it, 17 rows and 86 buffers for the same answer:

    - `metric_domain` is a loose index scan — the device's distinct metrics,
      each located by one `LIMIT 1` descent of `ix_readings_device_metric_ts`.
      PostgreSQL 16 has no skip scan, so the recursion is what keeps finding
      "the next metric" off a full range scan.
    - each metric's newest row is then one more bounded descent of the same
      index, via `CROSS JOIN LATERAL (... ORDER BY reading_ts DESC LIMIT 1)`.

    Deriving the domain from `readings` rather than from configuration is what
    keeps this layer free of presentation concerns, exactly as the `metrics`
    argument does for `latest_reading_times`. `CROSS JOIN` (not `LEFT JOIN`)
    preserves the documented result: a metric with no reading is absent from
    the mapping rather than present with a null.
    """
    if metrics is not None and not metrics:
        return {}

    filter_sql = "AND metric IN :metrics" if metrics is not None else ""
    stmt = text(
        f"""
        WITH RECURSIVE metric_domain AS (
            (SELECT metric
               FROM {_SCHEMA}.readings
              WHERE device_id = :device_id
              ORDER BY metric
              LIMIT 1)
            UNION ALL
            SELECT (SELECT r.metric
                      FROM {_SCHEMA}.readings r
                     WHERE r.device_id = :device_id
                       AND r.metric > d.metric
                     ORDER BY r.metric
                     LIMIT 1)
              FROM metric_domain d
             WHERE d.metric IS NOT NULL
        )
        SELECT l.device_id, m.metric, l.reading_ts, l.value
        FROM (
            SELECT metric FROM metric_domain
             WHERE metric IS NOT NULL {filter_sql}
        ) m
        CROSS JOIN LATERAL (
            SELECT r.device_id, r.reading_ts, r.value
              FROM {_SCHEMA}.readings r
             WHERE r.device_id = :device_id
               AND r.metric = m.metric
             ORDER BY r.reading_ts DESC
             LIMIT 1
        ) l
        ORDER BY m.metric
        """
    )
    params: dict = {"device_id": device_id}
    if metrics is not None:
        stmt = stmt.bindparams(bindparam("metrics", expanding=True))
        params["metrics"] = metrics

    with session_scope() as session:
        rows = session.execute(stmt, params).all()
    return {r[1]: _to_reading(r) for r in rows}


def get_readings_in_range(
    device_id: str, metric: str, start: datetime, end: datetime
) -> list[RawReading]:
    with session_scope() as session:
        rows = session.execute(
            text(
                f"SELECT device_id, metric, reading_ts, value "
                f"FROM {_SCHEMA}.readings "
                f"WHERE device_id = :device_id AND metric = :metric "
                f"AND reading_ts >= :start AND reading_ts <= :end "
                f"ORDER BY reading_ts ASC"
            ),
            {"device_id": device_id, "metric": metric, "start": start, "end": end},
        ).all()
    return [_to_reading(r) for r in rows]


def get_readings_for_device_in_range(
    device_id: str, metrics: list[str], start: datetime, end: datetime
) -> dict[str, list[RawReading]]:
    """One query for all requested metrics over one common time window."""
    if not metrics:
        return {}

    stmt = text(
        f"""
        SELECT device_id, metric, reading_ts, value
        FROM {_SCHEMA}.readings
        WHERE device_id = :device_id
          AND metric IN :metrics
          AND reading_ts >= :start
          AND reading_ts <= :end
        ORDER BY metric, reading_ts ASC
        """
    ).bindparams(bindparam("metrics", expanding=True))

    with session_scope() as session:
        rows = session.execute(
            stmt,
            {"device_id": device_id, "metrics": metrics, "start": start, "end": end},
        ).all()

    result: dict[str, list[RawReading]] = {m: [] for m in metrics}
    for row in rows:
        result[row[1]].append(_to_reading(row))
    return result


# ---------------------------------------------------------------------------
# User queries (DB-2: backs services/prototype_users.py)
# ---------------------------------------------------------------------------

def list_users() -> list[UserRecord]:
    """All users, ordered by creation (user_id) — the DB analogue of the
    insertion-order iteration the prototype's in-memory dict gave for free.
    """
    with session_scope() as session:
        rows = session.execute(
            text(f"SELECT {_USER_COLUMNS} FROM {_SCHEMA}.users ORDER BY user_id")
        ).all()
    return [_to_user(r) for r in rows]


def get_user_by_username(username: str) -> UserRecord | None:
    with session_scope() as session:
        row = session.execute(
            text(f"SELECT {_USER_COLUMNS} FROM {_SCHEMA}.users WHERE username = :username"),
            {"username": username},
        ).first()
    return _to_user(row) if row else None


def get_user_by_id(user_id: int) -> UserRecord | None:
    """Lookup by persistent identity — used by audit payload builders that
    start from an actor's ``user_id`` (strict D2) and never a username."""
    with session_scope() as session:
        row = session.execute(
            text(f"SELECT {_USER_COLUMNS} FROM {_SCHEMA}.users WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).first()
    return _to_user(row) if row else None


def create_or_update_user(
    username: str,
    full_name: str,
    role: str,
    status: str,
    email_address: str | None = None,
    mobile_number: str | None = None,
    *,
    session=None,
    with_change_info: bool = False,
):
    """Insert a new user, or update the existing row for that username.

    AUD-1 shape: the caller's transaction may be supplied via ``session``
    (service-level mutation+audit composition). Without one, the function
    opens and commits its own transaction exactly as before.

    Create/update classification is decided by an explicit
    ``SELECT ... FOR UPDATE`` of any existing row inside the same
    transaction (approved review decision: no reliance on PostgreSQL MVCC
    system columns). The pre-read row doubles as the exact before image for
    auditing; absent means INSERT (USER_CREATED), present means UPDATE
    (USER_UPDATED) with a real old/new pair.

    Trade-off accepted by review: two transactions racing to create the
    same username no longer merge via ON CONFLICT — the loser surfaces an
    IntegrityError instead, i.e. an explicit retry rather than a silent
    overwrite. Admin-UI concurrency makes this negligible.

    With ``with_change_info=True`` returns ``(UserRecord, created, before)``
    where ``before`` is None for creates; otherwise returns just UserRecord.
    """

    def _run(s):
        before_row = s.execute(
            text(
                f"SELECT {_USER_COLUMNS} FROM {_SCHEMA}.users "
                f"WHERE username = :username FOR UPDATE"
            ),
            {"username": username},
        ).first()
        created = before_row is None

        if created:
            row = s.execute(
                text(
                    f"""
                    INSERT INTO {_SCHEMA}.users
                        (username, full_name, email_address, mobile_number, role, status)
                    VALUES
                        (:username, :full_name, :email_address, :mobile_number, :role, :status)
                    RETURNING {_USER_COLUMNS}
                    """
                ),
                {
                    "username": username,
                    "full_name": full_name,
                    "email_address": email_address,
                    "mobile_number": mobile_number,
                    "role": role,
                    "status": status,
                },
            ).first()
        else:
            row = s.execute(
                text(
                    f"""
                    UPDATE {_SCHEMA}.users SET
                        full_name = :full_name,
                        email_address = :email_address,
                        mobile_number = :mobile_number,
                        role = :role,
                        status = :status,
                        updated_at = now()
                    WHERE username = :username
                    RETURNING {_USER_COLUMNS}
                    """
                ),
                {
                    "username": username,
                    "full_name": full_name,
                    "email_address": email_address,
                    "mobile_number": mobile_number,
                    "role": role,
                    "status": status,
                },
            ).first()

        record = _to_user(row)
        if not with_change_info:
            return record
        return record, created, _to_user(before_row) if before_row else None

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def delete_user_by_username(username: str) -> None:
    """No-op if the username does not exist — matches the current service
    contract's remove_user(), which is a silent no-op for a missing user.
    """
    with session_scope() as session:
        session.execute(
            text(f"DELETE FROM {_SCHEMA}.users WHERE username = :username"),
            {"username": username},
        )


def delete_all_users() -> None:
    """Test/prototype support only. No ON DELETE CASCADE exists from the
    DB-1 workflow tables (user_device_assignments, rtl_programming_requests,
    message_forwarding, audit_log) that FK to users.user_id.

    AUD-1 update: audit_log is now populated by audited service flows, so
    this reset removes those rows first — deleting a user must not leave
    audit entries dangling. Callers that also created assignment rows still
    need delete_all_assignments() first, as before.
    """
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {_SCHEMA}.audit_log"))
        session.execute(text(f"DELETE FROM {_SCHEMA}.users"))


# ---------------------------------------------------------------------------
# Message forwarding state (OPS-FWD-1: backs services/message_forwarding_service.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MessageForwardingRecord:
    """One user's forwarding membership row. ``None`` timestamps mean that
    transition has never happened for this account."""

    user_id: int
    enabled: bool
    enabled_at: datetime | None
    disabled_at: datetime | None


@dataclass(frozen=True)
class ForwardingChange:
    """Result of a forwarding write (FWD-D2/D3 no-op semantics).

    ``changed`` is False — and ``current`` None — only for the two genuine
    no-ops: disabling an account with no row (FWD-D2: nothing is inserted,
    nothing is audited), or re-applying the state already stored (FWD-D3).
    A real transition returns before/after images for the audit payload.
    """

    previous: MessageForwardingRecord | None
    current: MessageForwardingRecord | None
    changed: bool


def _to_forwarding_record(row) -> MessageForwardingRecord:
    return MessageForwardingRecord(
        user_id=row[0],
        enabled=bool(row[1]),
        enabled_at=row[2],
        disabled_at=row[3],
    )


def get_message_forwarding(user_id: int) -> MessageForwardingRecord | None:
    """A user's forwarding row, or None when they have never toggled.

    Callers decide what absence means; the service layer owns the FWD-D2
    rule that no row presents as disabled.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"SELECT user_id, enabled, enabled_at, disabled_at "
                f"FROM {_SCHEMA}.message_forwarding WHERE user_id = :user_id"
            ),
            {"user_id": user_id},
        ).first()
    return _to_forwarding_record(row) if row else None


def set_message_forwarding(
    user_id: int, enabled: bool, *, session=None
) -> ForwardingChange:
    """Set one user's forwarding state and classify the outcome.

    OPS-FWD-1 shape: the caller's transaction may be supplied via
    ``session`` (service-level mutation+audit composition). Without one,
    the function opens and commits its own transaction exactly like the
    AUD-1 refactored mutations do.

    Semantics frozen at review (FWD-D2/D3/D4):

    - No row + disable  -> genuine no-op. Nothing is inserted; the table's
      default-off means absence already IS the disabled state.
    - Same-state write  -> genuine no-op. Timestamps are last-TRANSITION
      markers, so re-applying must not churn them.
    - Real transition   -> the changed flag flips and only the matching
      timestamp moves; its opposite is preserved. All times come from the
      database clock via now(), consistent with AUD-1.

    The pre-read uses ``SELECT ... FOR UPDATE`` inside the transaction —
    the same approved before-image idiom as ``create_or_update_user``, not
    MVCC system columns.
    """

    def _run(s):
        before_row = s.execute(
            text(
                f"SELECT user_id, enabled, enabled_at, disabled_at "
                f"FROM {_SCHEMA}.message_forwarding "
                f"WHERE user_id = :user_id FOR UPDATE"
            ),
            {"user_id": user_id},
        ).first()

        if before_row is None:
            if not enabled:
                # FWD-D2: absent means disabled already; writing a row here
                # would manufacture state (and an audit event) from nothing.
                return ForwardingChange(previous=None, current=None, changed=False)
            row = s.execute(
                text(
                    f"""
                    INSERT INTO {_SCHEMA}.message_forwarding
                        (user_id, enabled, enabled_at, updated_at)
                    VALUES (:user_id, TRUE, now(), now())
                    RETURNING user_id, enabled, enabled_at, disabled_at
                    """
                ),
                {"user_id": user_id},
            ).first()
        else:
            if bool(before_row[1]) == enabled:
                # FWD-D3: re-applying the stored state changes nothing.
                record = _to_forwarding_record(before_row)
                return ForwardingChange(
                    previous=record, current=record, changed=False
                )
            if enabled:
                row = s.execute(
                    text(
                        f"""
                        UPDATE {_SCHEMA}.message_forwarding
                        SET enabled = TRUE, enabled_at = now(), updated_at = now()
                        WHERE user_id = :user_id
                        RETURNING user_id, enabled, enabled_at, disabled_at
                        """
                    ),
                    {"user_id": user_id},
                ).first()
            else:
                row = s.execute(
                    text(
                        f"""
                        UPDATE {_SCHEMA}.message_forwarding
                        SET enabled = FALSE, disabled_at = now(), updated_at = now()
                        WHERE user_id = :user_id
                        RETURNING user_id, enabled, enabled_at, disabled_at
                        """
                    ),
                    {"user_id": user_id},
                ).first()

        return ForwardingChange(
            previous=(
                _to_forwarding_record(before_row) if before_row is not None else None
            ),
            current=_to_forwarding_record(row),
            changed=True,
        )

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


def list_enabled_forwarding_user_ids(*, session=None) -> list[int]:
    """Every user_id currently forwarding-enabled (C08-AUTO-DISABLE-1).

    Plain read, no locking: the caller (``forwarding_auto_disable_service.
    apply_auto_disable``) re-locks each row individually via
    ``set_message_forwarding``'s own ``FOR UPDATE`` when it actually disables
    one, so a race with a user re-enabling between this read and that write
    is resolved there, not here.
    """

    def _run(s):
        rows = s.execute(
            text(
                f"SELECT user_id FROM {_SCHEMA}.message_forwarding "
                f"WHERE enabled = TRUE"
            )
        ).all()
        return [row[0] for row in rows]

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


# ---------------------------------------------------------------------------
# Forwarding auto-disable override (C08-AUTO-DISABLE-1: backs
# services/forwarding_auto_disable_service.py). Singleton row, id=1 always —
# ONE global override, never per-user or per-RTL (development baseline).
# ---------------------------------------------------------------------------

_AUTO_DISABLE_OVERRIDE_ID = 1


@dataclass(frozen=True)
class AutoDisableOverrideRecord:
    """The one active (or most recently set) override row, if any."""

    override_date: date
    cutoff_time: time
    reason: str
    set_by_user_id: int
    set_at: datetime


def _to_override_record(row) -> AutoDisableOverrideRecord:
    return AutoDisableOverrideRecord(
        override_date=row[0],
        cutoff_time=row[1],
        reason=row[2],
        set_by_user_id=row[3],
        set_at=row[4],
    )


def get_auto_disable_override(*, session=None) -> AutoDisableOverrideRecord | None:
    """The current override row, or None when no override has ever been set
    (or the last one was explicitly cleared). Does NOT filter by date — the
    caller decides whether ``override_date`` still applies to "today"."""

    def _run(s):
        row = s.execute(
            text(
                f"SELECT override_date, cutoff_time, reason, set_by_user_id, set_at "
                f"FROM {_SCHEMA}.forwarding_auto_disable_override "
                f"WHERE id = :id"
            ),
            {"id": _AUTO_DISABLE_OVERRIDE_ID},
        ).first()
        return _to_override_record(row) if row else None

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


@dataclass(frozen=True)
class OverrideChange:
    """Result of an override write, mirroring ``ForwardingChange``'s
    changed-flag shape (FWD-D3) for the same reason: a caller composing
    mutation + audit needs to know whether anything actually happened
    without re-deriving it from before/after equality itself.

    ``current`` is never None here (unlike ``ForwardingChange``): setting an
    override always results in a row, even when the write is a same-state
    no-op — there is no "absence means the target state" case the way an
    absent forwarding row means disabled.
    """

    previous: AutoDisableOverrideRecord | None
    current: AutoDisableOverrideRecord
    changed: bool


def set_auto_disable_override(
    *,
    override_date: date,
    cutoff_time: time,
    reason: str,
    set_by_user_id: int,
    session=None,
) -> OverrideChange:
    """Upsert the single override row and classify the outcome.

    Same-state re-application (identical ``override_date``, ``cutoff_time``
    and ``reason`` as the current row) is a genuine no-op — mirrors
    ``set_message_forwarding``'s FWD-D3 rule: neither ``set_by_user_id`` nor
    ``set_at`` are touched, and the caller must not audit it. Changing the
    date, cutoff, or reason is always a real transition, regardless of who
    made it.
    """

    def _run(s):
        before_row = s.execute(
            text(
                f"SELECT override_date, cutoff_time, reason, set_by_user_id, set_at "
                f"FROM {_SCHEMA}.forwarding_auto_disable_override "
                f"WHERE id = :id FOR UPDATE"
            ),
            {"id": _AUTO_DISABLE_OVERRIDE_ID},
        ).first()
        previous = _to_override_record(before_row) if before_row is not None else None

        if previous is not None and (
            previous.override_date == override_date
            and previous.cutoff_time == cutoff_time
            and previous.reason == reason
        ):
            return OverrideChange(previous=previous, current=previous, changed=False)

        if before_row is None:
            row = s.execute(
                text(
                    f"""
                    INSERT INTO {_SCHEMA}.forwarding_auto_disable_override
                        (id, override_date, cutoff_time, reason, set_by_user_id, set_at)
                    VALUES (:id, :override_date, :cutoff_time, :reason, :set_by_user_id, now())
                    RETURNING override_date, cutoff_time, reason, set_by_user_id, set_at
                    """
                ),
                {
                    "id": _AUTO_DISABLE_OVERRIDE_ID,
                    "override_date": override_date,
                    "cutoff_time": cutoff_time,
                    "reason": reason,
                    "set_by_user_id": set_by_user_id,
                },
            ).first()
        else:
            row = s.execute(
                text(
                    f"""
                    UPDATE {_SCHEMA}.forwarding_auto_disable_override
                    SET override_date = :override_date, cutoff_time = :cutoff_time,
                        reason = :reason, set_by_user_id = :set_by_user_id, set_at = now()
                    WHERE id = :id
                    RETURNING override_date, cutoff_time, reason, set_by_user_id, set_at
                    """
                ),
                {
                    "id": _AUTO_DISABLE_OVERRIDE_ID,
                    "override_date": override_date,
                    "cutoff_time": cutoff_time,
                    "reason": reason,
                    "set_by_user_id": set_by_user_id,
                },
            ).first()

        return OverrideChange(
            previous=previous, current=_to_override_record(row), changed=True
        )

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


def clear_auto_disable_override(
    *, session=None
) -> AutoDisableOverrideRecord | None:
    """Delete the override row, returning what was deleted (None if nothing
    was set — a genuine no-op, matching FWD-D2's absence-based idiom)."""

    def _run(s):
        row = s.execute(
            text(
                f"SELECT override_date, cutoff_time, reason, set_by_user_id, set_at "
                f"FROM {_SCHEMA}.forwarding_auto_disable_override "
                f"WHERE id = :id FOR UPDATE"
            ),
            {"id": _AUTO_DISABLE_OVERRIDE_ID},
        ).first()
        if row is None:
            return None
        s.execute(
            text(
                f"DELETE FROM {_SCHEMA}.forwarding_auto_disable_override WHERE id = :id"
            ),
            {"id": _AUTO_DISABLE_OVERRIDE_ID},
        )
        return _to_override_record(row)

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


_TEMPERATURE_THRESHOLD_CONFIG_ID = 1


@dataclass(frozen=True)
class TemperatureThresholdConfigRecord:
    """The one global temperature threshold configuration row, if any
    (THRESH-CONFIG-1 / C-01, framework only).

    ``warning_c``/``critical_c`` are ``Decimal`` — the driver's own exact
    representation of the NUMERIC(12,3) column, never cast to ``float``.
    A binary64 float cannot reliably preserve or compare a 3-decimal-place
    value; casting here would let this layer's own same-state no-op check
    (below) disagree with what is actually stored.
    """

    warning_c: Decimal
    critical_c: Decimal
    configured_by_user_id: int
    configured_at: datetime


def _to_threshold_config(row) -> TemperatureThresholdConfigRecord:
    return TemperatureThresholdConfigRecord(
        warning_c=row[0],
        critical_c=row[1],
        configured_by_user_id=row[2],
        configured_at=row[3],
    )


def get_temperature_threshold_config(
    *, session=None
) -> TemperatureThresholdConfigRecord | None:
    """The current threshold configuration, or None when never configured
    (or the last one was explicitly cleared) — absence IS "unconfigured",
    the same idiom `get_auto_disable_override` uses."""

    def _run(s):
        row = s.execute(
            text(
                f"SELECT warning_temperature_c, critical_temperature_c, "
                f"configured_by_user_id, configured_at "
                f"FROM {_SCHEMA}.temperature_threshold_config "
                f"WHERE id = :id"
            ),
            {"id": _TEMPERATURE_THRESHOLD_CONFIG_ID},
        ).first()
        return _to_threshold_config(row) if row else None

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


@dataclass(frozen=True)
class ThresholdConfigChange:
    """Result of a threshold-config write, mirroring ``OverrideChange``'s
    changed-flag shape for the same reason: the caller composing
    mutation + audit needs to know whether anything actually happened
    without re-deriving it from before/after equality itself.

    ``current`` is never None here (unlike ``ForwardingChange``): setting a
    configuration always results in a row, even when the write is a
    same-state no-op.
    """

    previous: TemperatureThresholdConfigRecord | None
    current: TemperatureThresholdConfigRecord
    changed: bool


def set_temperature_threshold_config(
    *,
    warning_c: Decimal,
    critical_c: Decimal,
    configured_by_user_id: int,
    session=None,
) -> ThresholdConfigChange:
    """Upsert the single threshold-config row and classify the outcome.

    ``warning_c``/``critical_c`` MUST already be the exact ``Decimal``
    that will be stored (the service layer canonicalizes to NUMERIC(12,3)'s
    scale before calling this) — this function compares and persists
    whatever it is given, in that representation, and performs no
    validation of its own beyond the database's own CHECK constraints
    (singleton, ``warning_temperature_c < critical_temperature_c``).

    Same-state re-application (identical ``warning_c``/``critical_c`` as the
    current row) is a genuine no-op — mirrors
    ``set_auto_disable_override``'s rule: neither
    ``configured_by_user_id`` nor ``configured_at`` are touched, and the
    caller must not audit it. Changing either value is always a real
    transition, regardless of who made it. Because both sides of this
    comparison are ``Decimal`` at the same fixed scale (never a ``float``),
    it can never disagree with what the database itself would consider
    equal.
    """

    def _run(s):
        before_row = s.execute(
            text(
                f"SELECT warning_temperature_c, critical_temperature_c, "
                f"configured_by_user_id, configured_at "
                f"FROM {_SCHEMA}.temperature_threshold_config "
                f"WHERE id = :id FOR UPDATE"
            ),
            {"id": _TEMPERATURE_THRESHOLD_CONFIG_ID},
        ).first()
        previous = _to_threshold_config(before_row) if before_row is not None else None

        if previous is not None and (
            previous.warning_c == warning_c and previous.critical_c == critical_c
        ):
            return ThresholdConfigChange(previous=previous, current=previous, changed=False)

        if before_row is None:
            row = s.execute(
                text(
                    f"""
                    INSERT INTO {_SCHEMA}.temperature_threshold_config
                        (id, warning_temperature_c, critical_temperature_c,
                         configured_by_user_id, configured_at)
                    VALUES (:id, :warning_c, :critical_c, :configured_by_user_id, now())
                    RETURNING warning_temperature_c, critical_temperature_c,
                              configured_by_user_id, configured_at
                    """
                ),
                {
                    "id": _TEMPERATURE_THRESHOLD_CONFIG_ID,
                    "warning_c": warning_c,
                    "critical_c": critical_c,
                    "configured_by_user_id": configured_by_user_id,
                },
            ).first()
        else:
            row = s.execute(
                text(
                    f"""
                    UPDATE {_SCHEMA}.temperature_threshold_config
                    SET warning_temperature_c = :warning_c,
                        critical_temperature_c = :critical_c,
                        configured_by_user_id = :configured_by_user_id,
                        configured_at = now()
                    WHERE id = :id
                    RETURNING warning_temperature_c, critical_temperature_c,
                              configured_by_user_id, configured_at
                    """
                ),
                {
                    "id": _TEMPERATURE_THRESHOLD_CONFIG_ID,
                    "warning_c": warning_c,
                    "critical_c": critical_c,
                    "configured_by_user_id": configured_by_user_id,
                },
            ).first()

        return ThresholdConfigChange(
            previous=previous, current=_to_threshold_config(row), changed=True
        )

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


def clear_temperature_threshold_config(
    *, session=None
) -> TemperatureThresholdConfigRecord | None:
    """Delete the threshold-config row, returning what was deleted (None if
    nothing was set — a genuine no-op, matching
    ``clear_auto_disable_override``'s absence-based idiom)."""

    def _run(s):
        row = s.execute(
            text(
                f"SELECT warning_temperature_c, critical_temperature_c, "
                f"configured_by_user_id, configured_at "
                f"FROM {_SCHEMA}.temperature_threshold_config "
                f"WHERE id = :id FOR UPDATE"
            ),
            {"id": _TEMPERATURE_THRESHOLD_CONFIG_ID},
        ).first()
        if row is None:
            return None
        s.execute(
            text(
                f"DELETE FROM {_SCHEMA}.temperature_threshold_config WHERE id = :id"
            ),
            {"id": _TEMPERATURE_THRESHOLD_CONFIG_ID},
        )
        return _to_threshold_config(row)

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


@dataclass(frozen=True)
class VibrationContractAnswerRecord:
    """One answered vibration contract question (VIB-CONFIG-1 / C-02,
    framework only). Absence of a row for a given ``question_key`` means
    that question is unanswered — never a row with placeholder text."""

    question_key: str
    answer_text: str
    updated_by_user_id: int
    updated_at: datetime


def _to_vibration_answer(row) -> VibrationContractAnswerRecord:
    return VibrationContractAnswerRecord(
        question_key=row[0],
        answer_text=row[1],
        updated_by_user_id=row[2],
        updated_at=row[3],
    )


def get_vibration_contract_answer(
    question_key: str, *, session=None
) -> VibrationContractAnswerRecord | None:
    """One question's current answer, or None when unanswered."""

    def _run(s):
        row = s.execute(
            text(
                f"SELECT question_key, answer_text, updated_by_user_id, updated_at "
                f"FROM {_SCHEMA}.vibration_contract_answers "
                f"WHERE question_key = :question_key"
            ),
            {"question_key": question_key},
        ).first()
        return _to_vibration_answer(row) if row else None

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


def list_vibration_contract_answers(
    *, session=None
) -> list[VibrationContractAnswerRecord]:
    """Every ANSWERED question, ordered by key. Unanswered questions have
    no row at all and so are simply absent from this list — the caller
    (services.vibration_contract_service) is what knows the full set of
    15 keys to reconcile this against."""

    def _run(s):
        rows = s.execute(
            text(
                f"SELECT question_key, answer_text, updated_by_user_id, updated_at "
                f"FROM {_SCHEMA}.vibration_contract_answers "
                f"ORDER BY question_key"
            )
        ).all()
        return [_to_vibration_answer(r) for r in rows]

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


@dataclass(frozen=True)
class VibrationAnswerChange:
    """Result of an answer write, mirroring ``OverrideChange``'s/
    ``ThresholdConfigChange``'s changed-flag shape for the same reason."""

    previous: VibrationContractAnswerRecord | None
    current: VibrationContractAnswerRecord
    changed: bool


def set_vibration_contract_answer(
    *,
    question_key: str,
    answer_text: str,
    updated_by_user_id: int,
    session=None,
) -> VibrationAnswerChange:
    """Upsert one question's answer and classify the outcome.

    Same-state re-application (identical ``answer_text`` as the current
    row for this key) is a genuine no-op — mirrors
    ``set_temperature_threshold_config``'s rule: neither
    ``updated_by_user_id`` nor ``updated_at`` are touched, and the caller
    must not audit it. Whether ``question_key`` is one of the 15 known
    questions is the SERVICE layer's job, not this one's (see migration
    012's docstring) — this function persists whatever key it is given.
    """

    def _run(s):
        before_row = s.execute(
            text(
                f"SELECT question_key, answer_text, updated_by_user_id, updated_at "
                f"FROM {_SCHEMA}.vibration_contract_answers "
                f"WHERE question_key = :question_key FOR UPDATE"
            ),
            {"question_key": question_key},
        ).first()
        previous = _to_vibration_answer(before_row) if before_row is not None else None

        if previous is not None and previous.answer_text == answer_text:
            return VibrationAnswerChange(previous=previous, current=previous, changed=False)

        if before_row is None:
            row = s.execute(
                text(
                    f"""
                    INSERT INTO {_SCHEMA}.vibration_contract_answers
                        (question_key, answer_text, updated_by_user_id, updated_at)
                    VALUES (:question_key, :answer_text, :updated_by_user_id, now())
                    RETURNING question_key, answer_text, updated_by_user_id, updated_at
                    """
                ),
                {
                    "question_key": question_key,
                    "answer_text": answer_text,
                    "updated_by_user_id": updated_by_user_id,
                },
            ).first()
        else:
            row = s.execute(
                text(
                    f"""
                    UPDATE {_SCHEMA}.vibration_contract_answers
                    SET answer_text = :answer_text,
                        updated_by_user_id = :updated_by_user_id,
                        updated_at = now()
                    WHERE question_key = :question_key
                    RETURNING question_key, answer_text, updated_by_user_id, updated_at
                    """
                ),
                {
                    "question_key": question_key,
                    "answer_text": answer_text,
                    "updated_by_user_id": updated_by_user_id,
                },
            ).first()

        return VibrationAnswerChange(
            previous=previous, current=_to_vibration_answer(row), changed=True
        )

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


def clear_vibration_contract_answer(
    question_key: str, *, session=None
) -> VibrationContractAnswerRecord | None:
    """Delete one question's answer row, returning what was deleted (None
    if it was already unanswered — a genuine no-op)."""

    def _run(s):
        row = s.execute(
            text(
                f"SELECT question_key, answer_text, updated_by_user_id, updated_at "
                f"FROM {_SCHEMA}.vibration_contract_answers "
                f"WHERE question_key = :question_key FOR UPDATE"
            ),
            {"question_key": question_key},
        ).first()
        if row is None:
            return None
        s.execute(
            text(
                f"DELETE FROM {_SCHEMA}.vibration_contract_answers "
                f"WHERE question_key = :question_key"
            ),
            {"question_key": question_key},
        )
        return _to_vibration_answer(row)

    if session is not None:
        return _run(session)
    with session_scope() as s:
        return _run(s)


# ---------------------------------------------------------------------------
# Technician/device assignment queries (DB-3: backs
# services/prototype_assignments.py)
# ---------------------------------------------------------------------------

def get_active_device_assignment(device_id: str) -> AssignmentRecord | None:
    """The current (``ended_at IS NULL``) assignment for a device, if any.

    At most one row can match — enforced by
    ``ux_user_device_assignments_active_device``.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT {_ASSIGNMENT_COLUMNS}
                FROM {_SCHEMA}.user_device_assignments a
                JOIN {_SCHEMA}.users u ON u.user_id = a.user_id
                WHERE a.device_id = :device_id AND a.ended_at IS NULL
                """
            ),
            {"device_id": device_id},
        ).first()
    return _to_assignment(row) if row else None


def list_active_assignments() -> dict[str, str]:
    """Every current assignment as device_id -> technician username.

    The fleet-wide counterpart of `get_active_device_assignment`, for screens
    that render one row per device: Device Management would otherwise issue
    120 single-device queries to fill one column.

    Unassigned devices are absent rather than present with a None value, so a
    caller has one empty case to handle instead of two. Same
    ``ended_at IS NULL`` definition of "current" as the single-device query —
    two definitions would eventually disagree.
    """
    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT a.device_id, u.username
                FROM {_SCHEMA}.user_device_assignments a
                JOIN {_SCHEMA}.users u ON u.user_id = a.user_id
                WHERE a.ended_at IS NULL
                """
            )
        ).all()
    return {row[0]: row[1] for row in rows}


def list_assignment_history(device_id: str) -> list[AssignmentRecord]:
    """Every assignment ever made for a device, oldest first — including the
    currently active one (``ended_at IS NULL``), if any.
    """
    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT {_ASSIGNMENT_COLUMNS}
                FROM {_SCHEMA}.user_device_assignments a
                JOIN {_SCHEMA}.users u ON u.user_id = a.user_id
                WHERE a.device_id = :device_id
                ORDER BY a.assigned_at ASC, a.assignment_id ASC
                """
            ),
            {"device_id": device_id},
        ).all()
    return [_to_assignment(r) for r in rows]


def list_devices_for_technician(username: str) -> list[str]:
    """Device ids currently (actively) assigned to a technician."""
    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT a.device_id
                FROM {_SCHEMA}.user_device_assignments a
                JOIN {_SCHEMA}.users u ON u.user_id = a.user_id
                WHERE u.username = :username AND a.ended_at IS NULL
                ORDER BY a.device_id
                """
            ),
            {"username": username},
        ).all()
    return [r[0] for r in rows]


def list_active_device_ids_for_user(user_id: int) -> list[str]:
    """Device ids with a current active assignment to `user_id`.

    Keyed on user_id — the persistent identity key — not username. See
    services/device_scope.py for why authorization never resolves through a
    display identity.
    """
    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT a.device_id
                FROM {_SCHEMA}.user_device_assignments a
                WHERE a.user_id = :user_id AND a.ended_at IS NULL
                ORDER BY a.device_id
                """
            ),
            {"user_id": user_id},
        ).all()
    return [r[0] for r in rows]


def assign_device_to_user(
    device_id: str,
    technician_username: str,
    assigned_by_user_id: int | None = None,
    *,
    session=None,
    with_change_info: bool = False,
):
    """Atomically (re)assign a device to a technician, preserving history.

    One transaction: resolve the technician username to a user_id, validate
    the technician's role, lock the device's current active row
    (``SELECT ... FOR UPDATE``), then either leave it alone (same technician
    — no duplicate history row), or close it and insert a new active row.

    AUD-1 shape: the caller's transaction may be supplied via ``session``.
    The acting administrator is recorded directly as ``assigned_by_user_id``
    (the previous ``assigned_by_username`` parameter was never called with a
    non-null value, so it was replaced rather than duplicated). The FOR
    UPDATE select now fetches the full active row so a genuine reassignment
    can report the closed row's before image.

    With ``with_change_info=True`` returns an :class:`AssignmentChange`
    whose ``changed`` flag is False only for the genuine no-op (same
    technician — nothing was written); otherwise returns just the resulting
    AssignmentRecord.

    Raises ValueError if the username does not exist or is not an active
    technician.
    """

    def _run(s):
        tech_row = s.execute(
            text(
                f"SELECT user_id, role FROM {_SCHEMA}.users "
                f"WHERE username = :username"
            ),
            {"username": technician_username},
        ).first()
        if tech_row is None:
            raise ValueError(f"Unknown technician username: {technician_username!r}")
        tech_user_id, role = tech_row
        if role != "technician":
            raise ValueError(
                f"User {technician_username!r} has role {role!r}, not 'technician'"
            )

        current = s.execute(
            text(
                f"""
                SELECT {_ASSIGNMENT_COLUMNS}
                FROM {_SCHEMA}.user_device_assignments a
                JOIN {_SCHEMA}.users u ON u.user_id = a.user_id
                WHERE a.device_id = :device_id AND a.ended_at IS NULL
                FOR UPDATE OF a
                """
            ),
            {"device_id": device_id},
        ).first()

        if current is not None and current[2] == tech_user_id:
            # Already assigned to this technician — externally-visible state
            # is unchanged, and closing+reinserting would create a
            # duplicate history row for no behavioral difference. Report it
            # as changed=False so audit composition can suppress the row (D1).
            record = _to_assignment(current)
            if with_change_info:
                return AssignmentChange(previous=record, current=record, changed=False)
            return record

        previous_record = _to_assignment(current) if current is not None else None

        if current is not None:
            s.execute(
                text(
                    f"UPDATE {_SCHEMA}.user_device_assignments "
                    f"SET ended_at = now() WHERE assignment_id = :assignment_id"
                ),
                {"assignment_id": current[0]},
            )

        new_row = s.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.user_device_assignments
                    (device_id, user_id, assigned_by)
                VALUES
                    (:device_id, :user_id, :assigned_by)
                RETURNING assignment_id, device_id, user_id, assigned_at, assigned_by, ended_at
                """
            ),
            {
                "device_id": device_id,
                "user_id": tech_user_id,
                "assigned_by": assigned_by_user_id,
            },
        ).first()

        record = AssignmentRecord(
            assignment_id=new_row[0],
            device_id=new_row[1],
            user_id=new_row[2],
            username=technician_username,
            assigned_at=new_row[3],
            assigned_by=new_row[4],
            ended_at=new_row[5],
        )
        if with_change_info:
            return AssignmentChange(previous=previous_record, current=record, changed=True)
        return record

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def end_active_device_assignment(
    device_id: str, ended_at: datetime | None = None, *, session=None
) -> list[AssignmentRecord]:
    """Close the active assignment(s) for a device, if any.

    AUD-1 shape: closes via UPDATE ... RETURNING and reports exactly which
    rows were closed (with technician username resolved in the same
    transaction), so callers can audit a genuine unassignment and stay
    silent when there was nothing to close. The partial unique index means
    at most one active row exists per device; the return is a list for
    statement-level honesty rather than an assumed singleton.

    Existing callers that ignore the return value are unaffected.
    """

    def _run(s):
        closed_rows = s.execute(
            text(
                f"""
                UPDATE {_SCHEMA}.user_device_assignments
                SET ended_at = COALESCE(:ended_at, now())
                WHERE device_id = :device_id AND ended_at IS NULL
                RETURNING assignment_id, device_id, user_id,
                          assigned_at, assigned_by, ended_at
                """
            ),
            {"device_id": device_id, "ended_at": ended_at},
        ).fetchall()

        closed: list[AssignmentRecord] = []
        for row in closed_rows:
            (
                assignment_id,
                closed_device_id,
                user_id_,
                assigned_at,
                assigned_by,
                closed_ended_at,
            ) = row
            username_row = s.execute(
                text(f"SELECT username FROM {_SCHEMA}.users WHERE user_id = :uid"),
                {"uid": user_id_},
            ).first()
            closed.append(
                AssignmentRecord(
                    assignment_id=assignment_id,
                    device_id=closed_device_id,
                    user_id=user_id_,
                    username=username_row[0] if username_row else "",
                    assigned_at=assigned_at,
                    assigned_by=assigned_by,
                    ended_at=closed_ended_at,
                )
            )
        return closed

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def delete_all_assignments() -> None:
    """Test/prototype support only — mirrors delete_all_users()."""
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {_SCHEMA}.user_device_assignments"))


def delete_assignments_for_usernames(usernames: Sequence[str]) -> int:
    """Delete every assignment row (open or closed) held by these users.

    Scoped deliberately narrowly. `delete_all_assignments()` is the blunt
    test-support version; this exists so the administration demo seed
    (`db/seed_admin_demo.py`) can undo exactly its own rows and leave every
    other assignment — including history belonging to real users — intact.

    Matches on `user_id`, not on `assigned_by`: an assignment made BY a demo
    account but held by someone else is that other person's row, and deleting
    it would remove data this function does not own.

    Returns the number of rows removed. An empty `usernames` deletes nothing
    rather than everything — the difference matters, because a bug that let an
    empty list through would otherwise wipe the table.
    """
    if not usernames:
        return 0
    with session_scope() as session:
        result = session.execute(
            text(
                f"DELETE FROM {_SCHEMA}.user_device_assignments "
                f"WHERE user_id IN ("
                f"    SELECT user_id FROM {_SCHEMA}.users "
                f"    WHERE username = ANY(:usernames)"
                f")"
            ),
            {"usernames": list(usernames)},
        )
        return result.rowcount or 0


# ---------------------------------------------------------------------------
# Administration summary queries (ADMIN-1: backs
# services/admin_overview_service.py)
#
# Reporting only — these never write, and they never compute freshness or any
# monitoring condition. The Fleet Overview already owns that axis via
# `latest_reading_times` / `FleetHealth`; duplicating it here would create a
# second opinion about which devices are healthy.
#
# DEVICE POPULATIONS. Two exist, and they are not interchangeable:
#
#   Monitoring Devices — active devices under active transformers
#       (`d.status = active AND t.status = active`). What is being monitored:
#       a device hanging off a decommissioned transformer delivers nothing to
#       monitor. Used by `count_hierarchy_by_plant`, `latest_reading_times`
#       and `latest_metric_readings`.
#
#   Managed RTLs — administratively active devices, regardless of transformer
#       status (`d.status = active`). What is being administered: an RTL under
#       a decommissioned transformer is still a real unit somebody owns,
#       assigns and eventually recovers. Used by `list_all_devices` and by
#       every query in this section.
#
# Administration answers "what do we manage", monitoring answers "what
# reports", so the two counts may legitimately differ and must never be
# swapped to make a screen add up. On the current development data both
# populations are the same 120 devices — nothing is deactivated — so the
# difference is invisible until it is not. tests/test_admin_overview.py
# ::TestDevicePopulations pins it.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeviceAssignmentCounts:
    """Device totals split by whether a technician currently holds them.

    One dataclass rather than three separate count functions because the
    three numbers are only meaningful together: `unassigned` is defined as
    the complement of `assigned` within `total`, so computing them in
    separate queries would let a concurrent assignment land between two
    round trips and produce a summary whose parts do not add up.
    """

    total_devices: int
    assigned_devices: int
    unassigned_devices: int


def count_device_assignments(include_inactive: bool = False) -> DeviceAssignmentCounts:
    """Total / assigned / unassigned device counts, from one aggregate query.

    Counts **Managed RTLs** (see the section header): administratively active
    devices, whatever their transformer's status. Matches `list_all_devices`
    exactly, so the administration summary and the Device Management table
    can never describe different fleets. This is deliberately NOT the
    Monitoring Devices population the Fleet Overview counts — an RTL under a
    decommissioned transformer still needs a technician.

    The transformer/plant joins `list_all_devices` performs are omitted here:
    they exist there to carry hierarchy context, and being inner joins over
    NOT NULL foreign keys they can neither add nor drop a device.

    "Assigned" means an active row (`ended_at IS NULL`) in
    `user_device_assignments`. Ended history rows are ignored, so a device
    whose technician was removed counts as unassigned again.

    COUNT(DISTINCT ...) rather than COUNT(*): the LEFT JOIN cannot currently
    fan out, because `ux_user_device_assignments_active_device` permits at
    most one active row per device — but stating the intent in the query
    keeps it correct on its own terms rather than only by virtue of an index
    defined in another file.
    """
    status_filter = "" if include_inactive else " AND d.status = :active"
    params: dict = {}
    if not include_inactive:
        params["active"] = ACTIVE_STATUS

    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT COUNT(DISTINCT d.device_id) AS total,
                       COUNT(DISTINCT a.device_id) AS assigned
                FROM {_SCHEMA}.devices d
                LEFT JOIN {_SCHEMA}.user_device_assignments a
                       ON a.device_id = d.device_id AND a.ended_at IS NULL
                WHERE TRUE{status_filter}
                """
            ),
            params,
        ).first()

    total, assigned = int(row[0]), int(row[1])
    return DeviceAssignmentCounts(
        total_devices=total,
        assigned_devices=assigned,
        unassigned_devices=total - assigned,
    )


def count_active_technicians() -> int:
    """How many users are active technicians (`role='technician'` and
    `status='active'`) — the same population
    `services.prototype_users.get_technician_options()` offers for assignment.

    Counted in SQL rather than by reusing that service for two reasons:
    it materialises every user row only to filter and discard most of them,
    and `get_technicians()` calls `seed_demo_user()` first — a write. A
    read-only dashboard figure must not insert a row as a side effect of
    being displayed.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"SELECT COUNT(*) FROM {_SCHEMA}.users "
                f"WHERE role = :role AND status = :active"
            ),
            {"role": "technician", "active": ACTIVE_STATUS},
        ).first()
    return int(row[0])


def count_devices_registered_between(
    start: datetime, end: datetime, include_inactive: bool = False
) -> int:
    """How many **Managed RTLs** were registered within a closed `[start, end]`
    window, read from `devices.created_at`.

    Takes explicit bounds rather than a "recent" duration: how long "recently"
    lasts is a dashboard policy and lives in
    `services.admin_overview_service`, while this layer only answers the
    question it is given. Both ends are inclusive, matching the `>= start AND
    <= end` convention `get_readings_in_range` already established for time
    windows.

    The upper bound is real, not decorative: `created_at` is defaulted by the
    database, but clock skew or hand-edited data can still produce a
    future-dated row, and "the last seven days" must not silently become
    "anything newer than seven days ago".
    """
    status_filter = "" if include_inactive else " AND d.status = :active"
    params: dict = {"start": start, "end": end}
    if not include_inactive:
        params["active"] = ACTIVE_STATUS

    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM {_SCHEMA}.devices d
                WHERE d.created_at >= :start
                  AND d.created_at <= :end{status_filter}
                """
            ),
            params,
        ).first()
    return int(row[0])


def list_unassigned_devices(
    limit: int | None = None, include_inactive: bool = False
) -> list[AdminDeviceRow]:
    """**Managed RTLs** with no active technician assignment, with hierarchy
    context.

    An RTL under an inactive transformer is included: it is still a unit
    nobody is responsible for, and dropping it from the exception list is
    how it would be forgotten.

    Returns `AdminDeviceRow` — the shape the Device Management table already
    consumes — rather than a near-identical administration-only row type. Every
    field the exception list needs is already on it, and a second contract
    carrying the same seven columns would be one more place for the two
    screens to drift apart. The assigned technician is deliberately not a
    field: on this list it is None by construction, and a column that is
    always None carries no information.

    A LEFT JOIN ... IS NULL anti-join, not a NOT IN subquery: one pass over
    the same index the assignment lookups already use, and no N+1.

    Ordering is plant name, transformer code, device code — matching
    `list_all_devices` so an operator sees the same sequence on both screens —
    with `device_id` as a final tiebreaker, because plant names carry no
    uniqueness constraint and `limit` makes ties observable as missing rows.

    Deliberately carries no freshness/monitoring column. The Fleet Overview
    already builds `FleetHealth` for the whole fleet in one query; a callback
    that wants freshness beside these rows should join against that, not pay
    for a second, independently-computed opinion.
    """
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be zero or greater, got {limit!r}")

    status_filter = "" if include_inactive else " AND d.status = :active"
    limit_clause = "" if limit is None else " LIMIT :limit"
    params: dict = {}
    if not include_inactive:
        params["active"] = ACTIVE_STATUS
    if limit is not None:
        params["limit"] = limit

    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT d.device_id, d.device_code, d.status,
                       t.transformer_id, t.transformer_code,
                       p.plant_id, p.name
                FROM {_SCHEMA}.devices d
                JOIN {_SCHEMA}.transformers t ON t.transformer_id = d.transformer_id
                JOIN {_SCHEMA}.plants p       ON p.plant_id = t.plant_id
                LEFT JOIN {_SCHEMA}.user_device_assignments a
                       ON a.device_id = d.device_id AND a.ended_at IS NULL
                WHERE a.device_id IS NULL{status_filter}
                ORDER BY p.name, t.transformer_code, d.device_code, d.device_id
                {limit_clause}
                """
            ),
            params,
        ).all()
    return [AdminDeviceRow(*r) for r in rows]


# ---------------------------------------------------------------------------
# Device registration (DB-4: backs services/device_registration.py)
# ---------------------------------------------------------------------------

def create_device(
    transformer_id: str,
    device_code: str,
    status: str = "active",
    *,
    session=None,
) -> DeviceRecord:
    """Register a new device under a transformer. Create-only — there is no
    ON CONFLICT/upsert path; a duplicate is always an error, never a merge.

    One transaction: validate the transformer exists, pre-check the
    (transformer_id, device_code) pair for a friendlier error than a raw
    constraint violation, generate device_id, then insert.

    AUD-1 shape: the caller's transaction may be supplied via ``session``
    (service-level mutation+audit composition); without one the function
    opens and commits its own transaction exactly as before.

    device_id follows the existing seed-time convention from
    db/hierarchy.py: ``{transformer_id}-d{n}``. ``n`` is one more than the
    highest existing numeric ``-dN`` suffix among this transformer's
    devices — MAX, not COUNT, so a gap left by a deleted device (e.g.
    -d1, -d2, -d4) is never reused and never collides with -d4 (a COUNT+1
    scheme would compute -d4 again here and collide).

    Concurrency is not trusted to this MAX-based computation alone: the
    devices PK (device_id) and the baseline (transformer_id, device_code)
    unique constraint are the final guards. A race between two concurrent
    registrations under the same transformer surfaces as IntegrityError
    from the INSERT itself, not as a silently wrong device_id.

    Raises ValueError if transformer_id does not exist, or if
    (transformer_id, device_code) is already registered (the common,
    non-racing case — a friendly pre-check, not the only enforcement).
    Raises sqlalchemy.exc.IntegrityError for the rare concurrent-write race
    that the pre-check could not see.
    """

    def _run(s):
        transformer_row = s.execute(
            text(f"SELECT 1 FROM {_SCHEMA}.transformers WHERE transformer_id = :transformer_id"),
            {"transformer_id": transformer_id},
        ).first()
        if transformer_row is None:
            raise ValueError(f"Unknown transformer_id: {transformer_id!r}")

        duplicate_row = s.execute(
            text(
                f"SELECT 1 FROM {_SCHEMA}.devices "
                f"WHERE transformer_id = :transformer_id AND device_code = :device_code"
            ),
            {"transformer_id": transformer_id, "device_code": device_code},
        ).first()
        if duplicate_row is not None:
            raise ValueError(
                f"Device code {device_code!r} is already registered under "
                f"transformer {transformer_id!r}"
            )

        next_index = s.execute(
            text(
                f"""
                SELECT COALESCE(
                    MAX(substring(device_id from '-d(\\d+)$')::int),
                    0
                ) + 1
                FROM {_SCHEMA}.devices
                WHERE transformer_id = :transformer_id
                """
            ),
            {"transformer_id": transformer_id},
        ).scalar_one()
        new_device_id = f"{transformer_id}-d{next_index}"

        row = s.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.devices (device_id, transformer_id, device_code, status)
                VALUES (:device_id, :transformer_id, :device_code, :status)
                RETURNING {_DEVICE_COLUMNS}
                """
            ),
            {
                "device_id": new_device_id,
                "transformer_id": transformer_id,
                "device_code": device_code,
                "status": status,
            },
        ).first()
        return _to_device(row)

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def insert_audit_log(
    *,
    operation: str,
    entity_type: str,
    entity_id: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
    actor_user_id: int | None = None,
    session=None,
) -> int:
    """Append one audit_log row and return its audit_id.

    AUD-1 write path. ``actor_user_id`` is deliberately NOT resolved from a
    username here: UI mutations must pass the authenticated session's
    user_id directly (strict-actor review decision), and NULL remains
    reserved for future system-originated operations. The users FK is the
    validity check — an unknown actor id fails the surrounding transaction.

    JSONB payloads arrive as plain dicts of JSON-safe primitives and are
    serialized here; occurred_at comes from the column's server default
    (DB clock). When ``session`` is omitted the insert commits on its own —
    which no service-level flow should rely on, because mutation+audit must
    share one transaction.
    """

    def _run(s) -> int:
        row = s.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.audit_log
                    (user_id, operation, entity_type, entity_id,
                     old_values, new_values)
                VALUES
                    (:user_id, :operation, :entity_type, :entity_id,
                     CAST(:old_values AS jsonb), CAST(:new_values AS jsonb))
                RETURNING audit_id
                """
            ),
            {
                "user_id": actor_user_id,
                "operation": operation,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "old_values": json.dumps(old_values) if old_values is not None else None,
                "new_values": json.dumps(new_values) if new_values is not None else None,
            },
        ).first()
        return int(row[0])

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


class _Unset:
    """Sentinel for update_device_metadata()'s defaults.

    Distinguishes "argument omitted, leave this column unchanged" from
    "argument explicitly passed as None, clear this column to NULL" — a
    plain `= None` default cannot make that distinction, and silently
    treating omitted as NULL would erase existing metadata on any partial
    update (e.g. updating only firmware_version would NULL out msisdn,
    hardware_version and installed_at).
    """

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _Unset()


def update_device_metadata(
    device_id: str,
    *,
    msisdn: str | None | _Unset = UNSET,
    hardware_version: str | None | _Unset = UNSET,
    firmware_version: str | None | _Unset = UNSET,
    installed_at: datetime | None | _Unset = UNSET,
) -> DeviceRecord | None:
    """Update a device's operational metadata columns, updating updated_at.

    Partial update: a parameter left at its default (UNSET) is left
    unchanged in the database. To deliberately clear a field to NULL, pass
    it explicitly as None — that is a distinct, deliberate call, not the
    default behavior of omitting it.

    No callback wires this yet — it is DB-4's persistence contract for a
    later commissioning/programming phase (services/device_registration.py
    does not call this from the registration flow; newly registered
    devices keep all four fields NULL).

    Returns None if device_id does not exist. If no field is supplied at
    all, this is a no-op read (updated_at is not touched — there is
    nothing to update).
    """
    fields = {
        "msisdn": msisdn,
        "hardware_version": hardware_version,
        "firmware_version": firmware_version,
        "installed_at": installed_at,
    }
    provided = {name: value for name, value in fields.items() if value is not UNSET}

    if not provided:
        with session_scope() as session:
            row = session.execute(
                text(f"SELECT {_DEVICE_COLUMNS} FROM {_SCHEMA}.devices WHERE device_id = :device_id"),
                {"device_id": device_id},
            ).first()
        return _to_device(row) if row else None

    # Column names come from the fixed dict above, never from caller input,
    # so this f-string is not an injection surface.
    set_clause = ", ".join(f"{column} = :{column}" for column in provided)
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                UPDATE {_SCHEMA}.devices
                SET {set_clause}, updated_at = now()
                WHERE device_id = :device_id
                RETURNING {_DEVICE_COLUMNS}
                """
            ),
            {"device_id": device_id, **provided},
        ).first()
    return _to_device(row) if row else None


# ---------------------------------------------------------------------------
# RTL programming requests (DB-1: OPS-PROG-1). Append-only request history —
# every deliberate submission inserts a new row (PROG-D3); no dedupe, no
# status progression, no completion writes (PROG-D6). The schema's defaults
# supply status='pending', requested_at=now() and NULL completion columns.
# ---------------------------------------------------------------------------

_PROGRAMMING_REQUEST_COLUMNS = (
    "request_id, device_id, transformer_id, requested_by, master_msisdn, "
    "requested_at, request_method, status, completed_at, error_message"
)


@dataclass(frozen=True)
class ProgrammingRequestRecord:
    """One persisted programming-request row.

    ``transformer_id`` is a point-in-time snapshot taken from the device's
    current transformer at insert time (migration 005), not a live join.
    ``status``/``completed_at``/``error_message`` start at their insert-time
    defaults (``'pending'``, NULL, NULL) and, as of RTL-PROG-EXEC-1, are
    projected forward by ``update_programming_request_status`` as the
    request's corresponding ``rtl_commands`` row moves through its own
    lifecycle (``config.commands.REQUEST_STATUS_FOR_COMMAND_STATE``) — this
    module never decides that mapping, only persists what it is told.
    """

    request_id: int
    device_id: str
    transformer_id: str
    requested_by: int
    master_msisdn: str
    requested_at: datetime
    request_method: str
    status: str
    completed_at: datetime | None
    error_message: str | None


def _to_programming_request(row) -> ProgrammingRequestRecord:
    return ProgrammingRequestRecord(*row)


def create_programming_request(
    device_id: str,
    *,
    master_msisdn: str,
    requested_by: int,
    request_method: str,
    session=None,
) -> ProgrammingRequestRecord:
    """Insert one pending programming-request row and return it.

    OPS-FWD-1/AUD-1 shape: the caller's transaction may be supplied via
    ``session`` (service-level mutation+audit composition); without one,
    the function opens and commits its own transaction exactly like the
    other refactored mutations do. ``requested_at`` comes from the column's
    server default (DB clock) — never host Python time.

    ``transformer_id`` is resolved from the device row in the same INSERT,
    so the snapshot cannot drift from the device the request names even
    under a concurrent move. An unknown device_id inserts nothing; that
    surfaces as ValueError rather than a bare FK IntegrityError.
    """
    if not isinstance(device_id, str) or not device_id:
        raise ValueError("A programming request requires a device_id.")

    def _run(s):
        row = s.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.rtl_programming_requests
                    (device_id, transformer_id, requested_by, master_msisdn,
                     request_method)
                SELECT d.device_id, d.transformer_id, :requested_by,
                       :master_msisdn, :request_method
                FROM {_SCHEMA}.devices d
                WHERE d.device_id = :device_id
                RETURNING {_PROGRAMMING_REQUEST_COLUMNS}
                """
            ),
            {
                "device_id": device_id,
                "requested_by": requested_by,
                "master_msisdn": master_msisdn,
                "request_method": request_method,
            },
        ).first()
        if row is None:
            raise ValueError(f"Unknown device_id: {device_id!r}")
        return _to_programming_request(row)

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def list_recent_programming_requests(
    device_id: str, *, limit: int = 5
) -> list[ProgrammingRequestRecord]:
    """A device's most recent programming requests, newest first.

    Read-back path for the drawer: confirmation state comes from
    PostgreSQL, never callback memory. Uses
    ix_rtl_programming_requests_device_ts (device_id, requested_at DESC).
    """
    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT {_PROGRAMMING_REQUEST_COLUMNS}
                FROM {_SCHEMA}.rtl_programming_requests
                WHERE device_id = :device_id
                ORDER BY requested_at DESC, request_id DESC
                LIMIT :limit
                """
            ),
            {"device_id": device_id, "limit": limit},
        ).all()
    return [_to_programming_request(row) for row in rows]


@dataclass(frozen=True)
class DeviceAuditHistoryRecord:
    """One device-scoped audit row, reduced to safe operational fields.

    Audit payload JSON is intentionally not returned here.  It can contain
    implementation-specific before/after values and is not required for an
    operator to understand who performed which recorded action.  The device
    join lets this generic audit table use the same neutral DeviceScope SQL
    constraint as every other device reader.
    """

    audit_id: int
    device_id: str
    occurred_at: datetime
    operation: str
    requester_name: str


def _to_device_audit_history(row) -> DeviceAuditHistoryRecord:
    return DeviceAuditHistoryRecord(*row)


def list_device_audit_history(
    device_ids,
    *,
    allowed_device_ids: frozenset[str] | None,
    limit_per_device: int = 10,
) -> list[DeviceAuditHistoryRecord]:
    """Return newest-first, scope-constrained device audit entries.

    ``audit_log`` is polymorphic, so its ``entity_id`` alone cannot receive
    the usual device scope clause.  Joining the audited device is deliberate:
    it proves the entity still names a device and applies scope in SQL before
    any audit entry becomes a presentation record.
    """
    ids = list(dict.fromkeys(device_ids))
    if not ids or allowed_device_ids == frozenset():
        return []
    if not isinstance(limit_per_device, int) or isinstance(limit_per_device, bool):
        raise ValueError("limit_per_device must be a positive integer")
    if limit_per_device < 1:
        raise ValueError("limit_per_device must be a positive integer")

    scope_sql, scope_params = _scope_clause("d", allowed_device_ids)
    statement = _scoped(
        text(
            f"""
            WITH ranked_audit AS (
                SELECT a.audit_id,
                       d.device_id,
                       a.occurred_at,
                       a.operation,
                       COALESCE(NULLIF(u.full_name, ''), u.username,
                                'System') AS requester_name,
                       ROW_NUMBER() OVER (
                           PARTITION BY d.device_id
                           ORDER BY a.occurred_at DESC, a.audit_id DESC
                       ) AS audit_rank
                FROM {_SCHEMA}.audit_log a
                JOIN {_SCHEMA}.devices d ON d.device_id = a.entity_id
                LEFT JOIN {_SCHEMA}.users u ON u.user_id = a.user_id
                WHERE a.entity_type = 'device'
                  AND a.entity_id IN :device_ids{scope_sql}
            )
            SELECT audit_id, device_id, occurred_at, operation, requester_name
            FROM ranked_audit
            WHERE audit_rank <= :limit_per_device
            ORDER BY occurred_at DESC, audit_id DESC
            """
        ).bindparams(bindparam("device_ids", expanding=True, type_=String)),
        allowed_device_ids,
    )
    with session_scope() as session:
        rows = session.execute(
            statement,
            {
                "device_ids": ids,
                "limit_per_device": limit_per_device,
                **scope_params,
            },
        ).all()
    return [_to_device_audit_history(row) for row in rows]


@dataclass(frozen=True)
class ProgrammingActivityRecord:
    """One request with its optional command lifecycle for activity views.

    This is a read model, not a new lifecycle.  The request remains the
    append-only operator-intent record and the command remains its separate
    protocol-neutral seam.  ``command_*`` fields are therefore nullable for
    historic or incomplete records; callers must not infer physical delivery
    from their presence.
    """

    request_id: int
    device_id: str
    requested_by_name: str
    master_msisdn: str
    requested_at: datetime
    request_status: str
    request_completed_at: datetime | None
    error_message: str | None
    command_id: int | None
    command_type: str | None
    command_state: str | None
    command_sent_at: datetime | None
    command_acknowledged_at: datetime | None
    command_completed_at: datetime | None
    failure_code: str | None


def _to_programming_activity(row) -> ProgrammingActivityRecord:
    return ProgrammingActivityRecord(*row)


def list_programming_activity(
    device_ids,
    *,
    allowed_device_ids: frozenset[str] | None,
    limit_per_device: int = 10,
) -> list[ProgrammingActivityRecord]:
    """Recent request/command activity for a bounded, scoped RTL set.

    One windowed query serves one device page today and a future assigned-RTL
    work list without an N+1 pattern.  Scope is applied in SQL, not filtered
    after the read: an empty Technician scope consequently returns no rows
    without querying, while ``None`` remains the explicit unrestricted scope.
    """
    ids = list(dict.fromkeys(device_ids))
    if not ids or allowed_device_ids == frozenset():
        return []
    if not isinstance(limit_per_device, int) or isinstance(limit_per_device, bool):
        raise ValueError("limit_per_device must be a positive integer")
    if limit_per_device < 1:
        raise ValueError("limit_per_device must be a positive integer")

    scope_sql, scope_params = _scope_clause("r", allowed_device_ids)
    statement = _scoped(
        text(
            f"""
            WITH ranked_activity AS (
                SELECT r.request_id,
                       r.device_id,
                       COALESCE(NULLIF(u.full_name, ''), u.username,
                                'Unknown account') AS requested_by_name,
                       r.master_msisdn,
                       r.requested_at,
                       r.status AS request_status,
                       r.completed_at AS request_completed_at,
                       r.error_message,
                       c.command_id,
                       c.command_type,
                       c.state AS command_state,
                       c.sent_at AS command_sent_at,
                       c.acknowledged_at AS command_acknowledged_at,
                       c.completed_at AS command_completed_at,
                       c.failure_code,
                       ROW_NUMBER() OVER (
                           PARTITION BY r.device_id
                           ORDER BY r.requested_at DESC, r.request_id DESC
                       ) AS activity_rank
                FROM {_SCHEMA}.rtl_programming_requests r
                LEFT JOIN {_SCHEMA}.users u ON u.user_id = r.requested_by
                LEFT JOIN {_SCHEMA}.rtl_commands c ON c.request_id = r.request_id
                WHERE r.device_id IN :device_ids{scope_sql}
            )
            SELECT request_id, device_id, requested_by_name, master_msisdn,
                   requested_at, request_status, request_completed_at,
                   error_message, command_id, command_type, command_state, command_sent_at,
                   command_acknowledged_at, command_completed_at, failure_code
            FROM ranked_activity
            WHERE activity_rank <= :limit_per_device
            ORDER BY requested_at DESC, request_id DESC
            """
        ).bindparams(bindparam("device_ids", expanding=True, type_=String)),
        allowed_device_ids,
    )
    with session_scope() as session:
        rows = session.execute(
            statement,
            {
                "device_ids": ids,
                "limit_per_device": limit_per_device,
                **scope_params,
            },
        ).all()
    return [_to_programming_activity(row) for row in rows]


def get_programming_request(request_id: int) -> ProgrammingRequestRecord | None:
    """One programming request by primary key, or None.

    RTL-IF-2's dispatcher resolves a command's referenced request through
    this — the request stays the operator-intent record a transport reads,
    never something the dispatcher re-derives or duplicates.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT {_PROGRAMMING_REQUEST_COLUMNS}
                FROM {_SCHEMA}.rtl_programming_requests
                WHERE request_id = :request_id
                """
            ),
            {"request_id": request_id},
        ).first()
    return _to_programming_request(row) if row else None


def update_programming_request_status(
    request_id: int,
    *,
    status: str,
    set_completed_at: bool = False,
    error_message: str | None = None,
    session=None,
) -> ProgrammingRequestRecord:
    """Project a command-lifecycle transition onto its programming request
    (RTL-PROG-EXEC-1).

    Pure persistence: the caller (``services/rtl_command_service.py``,
    ``services/rtl_programming_service.py``) owns which status/error
    message a given command state maps to
    (``config.commands.REQUEST_STATUS_FOR_COMMAND_STATE``) — this function
    only writes what it is told. ``completed_at`` is written from the DB
    clock, never host Python time, matching every other timestamp in this
    module, and only when ``set_completed_at`` is True (a terminal
    projection); otherwise the column is left exactly as it was. A terminal
    projection always happens strictly after the row's own insert, so this
    can never violate migration 005's
    ``completed_at >= requested_at`` CHECK.

    An unknown ``request_id`` updates nothing and raises ValueError, the
    same convention ``create_command``/``update_command_state`` use, rather
    than surfacing as a silent no-op.
    """

    def _run(s):
        row = s.execute(
            text(
                f"""
                UPDATE {_SCHEMA}.rtl_programming_requests
                SET status = :status,
                    completed_at = CASE WHEN :set_completed_at THEN now()
                                         ELSE completed_at END,
                    error_message = :error_message
                WHERE request_id = :request_id
                RETURNING {_PROGRAMMING_REQUEST_COLUMNS}
                """
            ),
            {
                "request_id": request_id,
                "status": status,
                "set_completed_at": set_completed_at,
                "error_message": error_message,
            },
        ).first()
        if row is None:
            raise ValueError(f"Unknown request_id: {request_id!r}")
        return _to_programming_request(row)

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


# ---------------------------------------------------------------------------
# RTL commands (RTL-IF-1): the protocol-neutral persistence boundary between
# an authorized programming request and a future device transport. One
# command per programming request, enforced by uq_rtl_commands_request_id;
# command_type/state carry no CHECK constraint so a future transport slice
# can introduce new values without a schema migration (migration 008).
#
# RTL-IF-2 (migration 009) adds execution-lifecycle columns: sent_at,
# acknowledged_at, completed_at, failure_code, failure_detail. Legal state
# values and transitions live in config/commands.py and are enforced by
# services/rtl_command_service.py — never here. This module only knows how
# to read a command and how to perform one conditional state UPDATE.
# ---------------------------------------------------------------------------

_COMMAND_COLUMNS = (
    "command_id, request_id, device_id, command_type, state, "
    "created_at, updated_at, sent_at, acknowledged_at, completed_at, "
    "failure_code, failure_detail"
)

#: The only columns update_command_state() may set a DB-clock timestamp on.
#: Interpolated into an UPDATE's SET clause below — validated against this
#: fixed set first, so it is never derived from caller input and this is
#: not an injection surface (same pattern as update_device_metadata()'s
#: set_clause).
_TRANSITION_TIMESTAMP_COLUMNS = frozenset({"sent_at", "acknowledged_at", "completed_at"})


@dataclass(frozen=True)
class CommandRecord:
    """One persisted rtl_commands row.

    ``device_id`` is resolved from the referenced request at insert time
    (below), never taken as caller input — the command cannot name a
    device other than the one its request already named.

    ``sent_at``/``acknowledged_at``/``completed_at`` are None until
    ``update_command_state()`` sets the one matching column for that
    transition (RTL-IF-2); ``failure_code``/``failure_detail`` are None
    unless the command reached FAILED or TIMED_OUT.
    """

    command_id: int
    request_id: int
    device_id: str
    command_type: str
    state: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    acknowledged_at: datetime | None
    completed_at: datetime | None
    failure_code: str | None
    failure_detail: str | None


def _to_command(row) -> CommandRecord:
    return CommandRecord(*row)


def create_command(
    *,
    request_id: int,
    command_type: str,
    state: str,
    session=None,
) -> CommandRecord:
    """Insert one command row referencing an existing programming request.

    ``device_id`` is resolved from ``rtl_programming_requests`` in the same
    INSERT (the same pattern ``create_programming_request`` uses to resolve
    ``transformer_id`` from ``devices``), so the command cannot drift from
    the request it names. An unknown ``request_id`` inserts nothing and
    raises ValueError rather than a bare FK IntegrityError; a repeated call
    for a ``request_id`` that already has a command fails on
    ``uq_rtl_commands_request_id`` instead of silently creating a second one.
    """
    def _run(s):
        row = s.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.rtl_commands
                    (request_id, device_id, command_type, state)
                SELECT r.request_id, r.device_id, :command_type, :state
                FROM {_SCHEMA}.rtl_programming_requests r
                WHERE r.request_id = :request_id
                RETURNING {_COMMAND_COLUMNS}
                """
            ),
            {
                "request_id": request_id,
                "command_type": command_type,
                "state": state,
            },
        ).first()
        if row is None:
            raise ValueError(f"Unknown request_id: {request_id!r}")
        return _to_command(row)

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def get_command_for_request(request_id: int) -> CommandRecord | None:
    """The single command referencing ``request_id``, or None.

    Read-back path for tests and future transport work: resolves
    "programming request -> corresponding command" straight from
    PostgreSQL via uq_rtl_commands_request_id.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT {_COMMAND_COLUMNS}
                FROM {_SCHEMA}.rtl_commands
                WHERE request_id = :request_id
                """
            ),
            {"request_id": request_id},
        ).first()
    return _to_command(row) if row else None


def get_command(command_id: int) -> CommandRecord | None:
    """One command by primary key, or None.

    RTL-IF-2's dispatcher and rtl_command_service use this to load the
    current command before validating a transition against
    config.commands.ALLOWED_TRANSITIONS.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT {_COMMAND_COLUMNS}
                FROM {_SCHEMA}.rtl_commands
                WHERE command_id = :command_id
                """
            ),
            {"command_id": command_id},
        ).first()
    return _to_command(row) if row else None


def update_command_state(
    command_id: int,
    *,
    expected_state: str,
    to_state: str,
    timestamp_column: str,
    failure_code: str | None = None,
    failure_detail: str | None = None,
    session=None,
) -> CommandRecord:
    """Atomically move a command from ``expected_state`` to ``to_state``.

    RTL-IF-2. The ``WHERE ... AND state = :expected_state`` clause is the
    whole safety story: it makes this a single conditional UPDATE rather
    than a read-then-write with a race window, so a concurrent transition
    (or a caller trying to move an already-terminal or already-moved
    command) affects zero rows and raises, instead of silently clobbering
    another transition or corrupting the row into two states at once.
    Legality of ``expected_state -> to_state`` itself is
    services/rtl_command_service.py's job (config.commands.ALLOWED_TRANSITIONS)
    — this function only enforces that the row was actually in
    ``expected_state`` at UPDATE time.

    ``timestamp_column`` must be one of _TRANSITION_TIMESTAMP_COLUMNS —
    checked before use, never taken as raw caller input, so interpolating
    it into the SET clause is not an injection surface (same pattern as
    update_device_metadata()'s set_clause).
    """
    if timestamp_column not in _TRANSITION_TIMESTAMP_COLUMNS:
        raise ValueError(f"Unknown lifecycle timestamp column: {timestamp_column!r}")

    def _run(s):
        row = s.execute(
            text(
                f"""
                UPDATE {_SCHEMA}.rtl_commands
                SET state = :to_state,
                    {timestamp_column} = now(),
                    updated_at = now(),
                    failure_code = :failure_code,
                    failure_detail = :failure_detail
                WHERE command_id = :command_id AND state = :expected_state
                RETURNING {_COMMAND_COLUMNS}
                """
            ),
            {
                "command_id": command_id,
                "expected_state": expected_state,
                "to_state": to_state,
                "failure_code": failure_code,
                "failure_detail": failure_detail,
            },
        ).first()
        if row is None:
            raise ValueError(
                f"Command {command_id} is not currently in state "
                f"{expected_state!r} (unknown command, concurrent "
                f"transition, or an illegal move)."
            )
        return _to_command(row)

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


# ---------------------------------------------------------------------------
# Device events (DB-1: INGEST-1). Normalized append-only event history
# (INGEST-D3): every accepted call inserts a new row — there is no dedup,
# because the schema offers no legitimate idempotency key (INGEST-D10).
# ``event_ts`` is the caller-supplied source occurrence time (INGEST-D4);
# ``created_at`` is the DB ingestion clock. Attribution must satisfy
# ck_device_events_attribution; identity RESOLUTION policy lives in
# services/device_event_service.py, never here.
# ---------------------------------------------------------------------------

_DEVICE_EVENT_COLUMNS = (
    "event_id, device_id, transformer_id, reported_uid, event_type, "
    "severity, event_ts, temperature, battery_voltage, message, source, "
    "created_at, acknowledged_at, acknowledged_by_user_id"
)


def insert_device_event(
    *,
    event_type: str,
    event_ts: datetime,
    device_id: str | None = None,
    transformer_id: str | None = None,
    reported_uid: str | None = None,
    severity: str | None = None,
    temperature=None,
    battery_voltage=None,
    message: str | None = None,
    source: str | None = None,
    session=None,
) -> int:
    """Append one normalized device_events row and return its event_id.

    Pure persistence: no validation beyond what the database enforces (the
    attribution CHECK and FKs). The service layer owns shape validation and
    identity resolution. When ``session`` is omitted the insert commits on
    its own — which no ingestion flow should rely on, because INGEST-D5
    requires event + activation + audit to share one transaction.
    """

    def _run(s) -> int:
        row = s.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.device_events
                    (device_id, transformer_id, reported_uid, event_type,
                     severity, event_ts, temperature, battery_voltage,
                     message, source)
                VALUES
                    (:device_id, :transformer_id, :reported_uid, :event_type,
                     :severity, :event_ts, :temperature, :battery_voltage,
                     :message, :source)
                RETURNING event_id
                """
            ),
            {
                "device_id": device_id,
                "transformer_id": transformer_id,
                "reported_uid": reported_uid,
                "event_type": event_type,
                "severity": severity,
                "event_ts": event_ts,
                "temperature": temperature,
                "battery_voltage": battery_voltage,
                "message": message,
                "source": source,
            },
        ).first()
        return int(row[0])

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def get_device_event(
    event_id: int,
    *,
    session=None,
    allowed_device_ids: frozenset[str] | None = None,
) -> dict | None:
    """One device_events row as a plain dict, or None when absent.

    Test/read-back helper for the ingestion slice; not a UI query.
    """
    def _run(s):
        scope_sql, scope_params = _scope_clause("e", allowed_device_ids)
        row = s.execute(
            _scoped(
                text(
                    f"SELECT {_DEVICE_EVENT_COLUMNS} "
                    f"FROM {_SCHEMA}.device_events e "
                    f"WHERE e.event_id = :event_id{scope_sql}"
                ),
                allowed_device_ids,
            ),
            {"event_id": event_id, **scope_params},
        ).first()
        return row

    if session is not None:
        row = _run(session)
    else:
        with session_scope() as own:
            row = _run(own)
    if row is None:
        return None
    keys = (
        "event_id", "device_id", "transformer_id", "reported_uid",
        "event_type", "severity", "event_ts", "temperature",
        "battery_voltage", "message", "source", "created_at",
        "acknowledged_at", "acknowledged_by_user_id",
    )
    return dict(zip(keys, row))


@dataclass(frozen=True)
class DeviceEventRecord:
    """One persisted device event, typed for consumer read paths.

    ``event_ts`` is the source occurrence time and ``created_at`` the DB
    ingestion clock (INGEST-D4); consumers display/order by ``event_ts``
    only (EVT-D9). Numeric payloads are converted to float for display;
    they are presentation payload — never a classification input
    (EVT-D4).
    """

    event_id: int
    device_id: str | None
    transformer_id: str | None
    reported_uid: str | None
    event_type: str
    severity: str | None
    event_ts: datetime
    temperature: float | None
    battery_voltage: float | None
    message: str | None
    source: str | None
    created_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by_user_id: int | None


def _to_device_event(row) -> DeviceEventRecord:
    return DeviceEventRecord(
        event_id=row[0],
        device_id=row[1],
        transformer_id=row[2],
        reported_uid=row[3],
        event_type=row[4],
        severity=row[5],
        event_ts=row[6],
        temperature=float(row[7]) if row[7] is not None else None,
        battery_voltage=float(row[8]) if row[8] is not None else None,
        message=row[9],
        source=row[10],
        created_at=row[11],
        acknowledged_at=row[12],
        acknowledged_by_user_id=row[13],
    )


def acknowledge_device_event(
    event_id: int,
    *,
    actor_user_id: int,
    allowed_device_ids: frozenset[str] | None,
    session,
) -> DeviceEventRecord | None:
    """Atomically acknowledge one scoped event that is still active.

    ``None`` is intentionally ambiguous to the repository: the service
    distinguishes an absent/out-of-scope event from an already-acknowledged
    one through its scoped read.  The device-scope predicate is repeated in
    this write, so a caller cannot turn a previously-read event id into a
    cross-device mutation.
    """
    scope_sql, scope_params = _scope_clause("e", allowed_device_ids)
    row = session.execute(
        _scoped(
            text(
                f"""
                UPDATE {_SCHEMA}.device_events AS e
                SET acknowledged_at = now(),
                    acknowledged_by_user_id = :actor_user_id
                WHERE e.event_id = :event_id
                  AND e.acknowledged_at IS NULL{scope_sql}
                RETURNING {_DEVICE_EVENT_COLUMNS}
                """
            ),
            allowed_device_ids,
        ),
        {
            "event_id": event_id,
            "actor_user_id": actor_user_id,
            **scope_params,
        },
    ).first()
    return _to_device_event(row) if row is not None else None


def list_recent_device_events(
    *,
    event_types: Sequence[str],
    since: datetime | None = None,
    allowed_device_ids: frozenset[str] | None = None,
    include_unattributed: bool = False,
    limit: int = 500,
) -> list[DeviceEventRecord]:
    """Recent events of the given types, scoped at the SQL level.

    The single consumer read API (EVT-D2): Notification Center, report
    projections and future delivery code all read through this one
    function instead of each re-querying device_events.

    - ``event_types`` must be non-empty; the caller names what it consumes.
    - ``since`` is an OPTIONAL occurrence-time bound (``event_ts``); the
      Notification Center passes none — it has no retention/expiry rule
      (review correction to EVT-D8). Ordering is ``event_ts DESC,
      event_id DESC`` (INGEST-D4 tiebreak).
    - ``limit`` is a technical pilot-safety capacity bound, not product
      semantics.
    - Scope follows the ROLE-BLIND ``_scope_clause`` idiom: ``None`` means
      unrestricted, an EMPTY frozenset matches nothing. Unattributed rows
      (``invalid_uid`` quarantines with no device) are excluded unless
      ``include_unattributed=True`` — an admin-only surface (EVT-D5) that
      scope alone cannot express, because an unregistered UID belongs to
      no device set.
    - No index migration backs this yet; pilot volumes do not justify DDL
      (EVT-D2).
    """
    if not event_types:
        return []

    def _run(s) -> list[DeviceEventRecord]:
        unattributed_sql = (
            "" if include_unattributed else " AND e.device_id IS NOT NULL"
        )
        since_sql = "" if since is None else " AND e.event_ts >= :since"
        scope_sql, scope_params = _scope_clause("e", allowed_device_ids)
        statement = text(
            f"""
            SELECT {_DEVICE_EVENT_COLUMNS}
            FROM {_SCHEMA}.device_events e
            WHERE e.event_type IN :event_types{since_sql}{unattributed_sql}{scope_sql}
            ORDER BY e.event_ts DESC, e.event_id DESC
            LIMIT :limit
            """
        ).bindparams(bindparam("event_types", expanding=True, type_=String))
        params = {
            "event_types": list(event_types),
            "limit": limit,
            **scope_params,
        }
        if since is not None:
            params["since"] = since
        rows = s.execute(_scoped(statement, allowed_device_ids), params).all()
        return [_to_device_event(row) for row in rows]

    with session_scope() as own:
        return _run(own)


def find_device_ids_by_code(
    device_code: str, transformer_id: str | None = None, *, session=None
) -> list[str]:
    """Registered device_ids whose ``device_code`` matches a reported UID.

    Identity resolution primitive (INGEST-D2). The schema's ONLY uniqueness
    guarantee is UNIQUE (transformer_id, device_code) — ``device_code``
    alone is NOT globally unique even though today's seed generation makes
    it so in practice; this function never assumes otherwise.

    - With ``transformer_id``: resolves the composite identity, which the
      constraint caps at one row.
    - Without it: returns EVERY match, possibly several — the caller (not
      this function) decides that an ambiguous UID resolves to nothing.
    """

    def _run(s) -> list[str]:
        if transformer_id is not None:
            rows = s.execute(
                text(
                    f"SELECT device_id FROM {_SCHEMA}.devices "
                    f"WHERE device_code = :code AND transformer_id = :t "
                    f"ORDER BY device_id"
                ),
                {"code": device_code, "t": transformer_id},
            ).all()
        else:
            rows = s.execute(
                text(
                    f"SELECT device_id FROM {_SCHEMA}.devices "
                    f"WHERE device_code = :code ORDER BY device_id"
                ),
                {"code": device_code},
            ).all()
        return [r[0] for r in rows]

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def device_id_registered(device_id: str, *, session=None) -> bool:
    """Whether ``device_id`` names an existing devices row.

    Resolution primitive for the trusted-explicit-device_id path
    (INGEST-D2): an explicit id is honoured only when it is actually
    registered — never assumed valid.
    """

    def _run(s) -> bool:
        return (
            s.execute(
                text(
                    f"SELECT 1 FROM {_SCHEMA}.devices "
                    f"WHERE device_id = :device_id"
                ),
                {"device_id": device_id},
            ).first()
            is not None
        )

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


# ---------------------------------------------------------------------------
# RTL active-list state (DB-1: OPS-DEACT-1 / INGEST-1). Single row per
# device; absence IS the off-list state (DEACT-D1) and reads never
# manufacture rows. Mutations are exactly the two transitions: true→false
# (deactivation, DEACT-D3) and absent/false→true (activation, ACT-D4);
# active→active is a no-op on both sides (ACT-D3). Deliberately independent
# of devices.status (RTL-ACT-05).
# ---------------------------------------------------------------------------

_ACTIVE_STATE_COLUMNS = (
    "device_id, is_active, activated_at, deactivated_at, updated_at"
)


@dataclass(frozen=True)
class ActiveStateRecord:
    """One device's active-list membership row. ``None`` timestamps mean
    that transition has never happened for this device."""

    device_id: str
    is_active: bool
    activated_at: datetime | None
    deactivated_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True)
class ActiveStateChange:
    """Result of an active-state mutation attempt.

    Deactivation outcomes (DEACT-D1/D2/D3):

    - absent:          previous/current None, changed False (no insert)
    - already inactive: previous == current row, changed False (no write)
    - transitioned:     changed True, before/after images for the audit

    Activation outcomes (ACT-D3/D4) mirror this: absent→active and
    inactive→active return changed True (previous None or the inactive
    row); active→active returns changed False with both images set.
    """

    previous: ActiveStateRecord | None
    current: ActiveStateRecord | None
    changed: bool


def _to_active_state(row) -> ActiveStateRecord:
    return ActiveStateRecord(
        device_id=row[0],
        is_active=bool(row[1]),
        activated_at=row[2],
        deactivated_at=row[3],
        updated_at=row[4],
    )


def get_device_active_state(device_id: str) -> ActiveStateRecord | None:
    """A device's active-list row, or None when it has none.

    Callers decide what absence means; the service layer owns the DEACT-D1
    rule that no row presents as off-list.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"SELECT {_ACTIVE_STATE_COLUMNS} "
                f"FROM {_SCHEMA}.rtl_active_state WHERE device_id = :device_id"
            ),
            {"device_id": device_id},
        ).first()
    return _to_active_state(row) if row else None


def deactivate_device_active_state(
    device_id: str, *, session=None
) -> ActiveStateChange:
    """Deactivate one device's active-list membership, classifying the outcome.

    OPS-FWD-1 shape: the caller's transaction may be supplied via
    ``session`` (service-level mutation+audit composition); without one,
    the function opens and commits its own transaction exactly like the
    other refactored mutations do.

    Semantics frozen at review (DEACT-D1/D2/D3):

    - No row            -> genuine no-op. Absence already IS the off-list
      state; writing an inactive row here would manufacture state.
    - Already inactive  -> genuine no-op. Timestamps are last-TRANSITION
      markers, so re-applying must not churn them.
    - Active            -> the changed flag flips; deactivated_at/updated_at
      come from now() (DB clock) and activated_at is preserved untouched.
      The pre-read uses ``SELECT ... FOR UPDATE`` — the approved
      before-image idiom — so two concurrent deactivations cannot both
      classify as transitions.
    """

    def _run(s):
        before_row = s.execute(
            text(
                f"SELECT {_ACTIVE_STATE_COLUMNS} "
                f"FROM {_SCHEMA}.rtl_active_state "
                f"WHERE device_id = :device_id FOR UPDATE"
            ),
            {"device_id": device_id},
        ).first()

        if before_row is None:
            # DEACT-D1: absent means off-list already.
            return ActiveStateChange(previous=None, current=None, changed=False)

        if not before_row[1]:
            # DEACT-D2: re-applying the stored state changes nothing.
            record = _to_active_state(before_row)
            return ActiveStateChange(
                previous=record, current=record, changed=False
            )

        row = s.execute(
            text(
                f"""
                UPDATE {_SCHEMA}.rtl_active_state
                SET is_active = FALSE, deactivated_at = now(), updated_at = now()
                WHERE device_id = :device_id
                RETURNING {_ACTIVE_STATE_COLUMNS}
                """
            ),
            {"device_id": device_id},
        ).first()

        return ActiveStateChange(
            previous=_to_active_state(before_row),
            current=_to_active_state(row),
            changed=True,
        )

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)


def activate_device_active_state(
    device_id: str, *, session=None
) -> ActiveStateChange:
    """Activate one device's active-list membership, classifying the outcome.

    INGEST-1 counterpart to :func:`deactivate_device_active_state`, with the
    frozen ACT-D3/D4 semantics:

    - No row            -> first activation (absent → active): INSERT an
      active row; activated_at/updated_at come from now() (DB clock).
    - Already inactive  -> reactivation (inactive → active): is_active flips,
      activated_at/updated_at refresh from now(); deactivated_at is
      preserved untouched.
    - Already active    -> genuine no-op (ACT-D3). Timestamps are last-
      TRANSITION markers, so re-applying must not churn them and the caller
      must not audit (no duplicate activation audit).

    The pre-read uses ``SELECT ... FOR UPDATE`` — the approved before-image
    idiom — so two concurrent activations cannot both classify as
    transitions. The caller supplies ``session`` to share the ingestion
    transaction (INGEST-D5 atomicity); without one, the function opens and
    commits its own transaction like every other refactored mutation.
    """

    def _run(s):
        before_row = s.execute(
            text(
                f"SELECT {_ACTIVE_STATE_COLUMNS} "
                f"FROM {_SCHEMA}.rtl_active_state "
                f"WHERE device_id = :device_id FOR UPDATE"
            ),
            {"device_id": device_id},
        ).first()

        if before_row is None:
            # ACT-D4: absent → active = FIRST activation. Insert the row
            # with activated_at from the DB clock.
            row = s.execute(
                text(
                    f"""
                    INSERT INTO {_SCHEMA}.rtl_active_state
                        (device_id, is_active, activated_at, updated_at)
                    VALUES (:device_id, TRUE, now(), now())
                    RETURNING {_ACTIVE_STATE_COLUMNS}
                    """
                ),
                {"device_id": device_id},
            ).first()
            return ActiveStateChange(
                previous=None, current=_to_active_state(row), changed=True
            )

        if before_row[1]:
            # ACT-D3: already-active startup is a no-op — zero churn.
            record = _to_active_state(before_row)
            return ActiveStateChange(
                previous=record, current=record, changed=False
            )

        row = s.execute(
            text(
                f"""
                UPDATE {_SCHEMA}.rtl_active_state
                SET is_active = TRUE, activated_at = now(), updated_at = now()
                WHERE device_id = :device_id
                RETURNING {_ACTIVE_STATE_COLUMNS}
                """
            ),
            {"device_id": device_id},
        ).first()

        return ActiveStateChange(
            previous=_to_active_state(before_row),
            current=_to_active_state(row),
            changed=True,
        )

    if session is not None:
        return _run(session)
    with session_scope() as own:
        return _run(own)
