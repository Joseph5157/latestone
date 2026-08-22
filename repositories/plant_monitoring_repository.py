"""
Plant monitoring repository — the only module containing raw SQL.

No generic raw-query helpers exist here. Identifiers (schema name) come from
application configuration, never from browser or user input. Metric lists are
bound with SQLAlchemy expanding parameters — never interpolated into SQL strings.

There is no unbounded reading query by design: PostgreSQL must always perform
device/metric/time-range filtering.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import String, bindparam, text

from config.settings import monitoring
from db.engine import session_scope

_SCHEMA = monitoring.schema

# Administrative status only. Never a monitoring condition — see CLAUDE.md.
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


def _to_plant(row) -> PlantRecord:
    return PlantRecord(*row)


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


def count_hierarchy_by_plant(include_inactive: bool = False) -> dict[str, tuple[int, int]]:
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
    """
    status_filter = "" if include_inactive else " AND t.status = :active"
    device_filter = "" if include_inactive else " AND d.status = :active"
    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT p.plant_id,
                       COUNT(DISTINCT t.transformer_id) AS transformers,
                       COUNT(d.device_id)               AS devices
                FROM {_SCHEMA}.plants p
                LEFT JOIN {_SCHEMA}.transformers t
                       ON t.plant_id = p.plant_id{status_filter}
                LEFT JOIN {_SCHEMA}.devices d
                       ON d.transformer_id = t.transformer_id{device_filter}
                GROUP BY p.plant_id
                """
            ),
            {"active": ACTIVE_STATUS},
        ).all()
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
    metrics: list[str], include_inactive: bool = False
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

    with session_scope() as session:
        rows = session.execute(
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
                WHERE TRUE{status_filter}
                """
            ),
            params,
        ).all()

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

    with session_scope() as session:
        rows = session.execute(
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
                WHERE TRUE{status_filter}{scope_sql}
                ORDER BY t.transformer_code, d.device_code
                """
            ),
            params,
        ).all()

    return [_to_device_metric_reading(r) for r in rows]


# ---------------------------------------------------------------------------
# Reading queries
# ---------------------------------------------------------------------------

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
    """One query for all requested metrics — never one query per metric."""
    if metrics is not None and not metrics:
        return {}

    filter_sql = "AND metric IN :metrics" if metrics is not None else ""
    stmt = text(
        f"""
        SELECT DISTINCT ON (metric) device_id, metric, reading_ts, value
        FROM {_SCHEMA}.readings
        WHERE device_id = :device_id {filter_sql}
        ORDER BY metric, reading_ts DESC
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


def create_or_update_user(
    username: str,
    full_name: str,
    role: str,
    status: str,
    email_address: str | None = None,
    mobile_number: str | None = None,
) -> UserRecord:
    """Insert a new user, or update the existing row for that username.

    A native ``INSERT ... ON CONFLICT (username) DO UPDATE`` rather than a
    check-then-write: atomic, and matches ``users.username``'s UNIQUE
    constraint as the single source of truth for "does this user exist".
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.users
                    (username, full_name, email_address, mobile_number, role, status)
                VALUES
                    (:username, :full_name, :email_address, :mobile_number, :role, :status)
                ON CONFLICT (username) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    email_address = EXCLUDED.email_address,
                    mobile_number = EXCLUDED.mobile_number,
                    role = EXCLUDED.role,
                    status = EXCLUDED.status,
                    updated_at = now()
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
    return _to_user(row)


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
    message_forwarding, audit_log) that FK to users.user_id — this will
    raise IntegrityError once those are populated by a later phase. At DB-2
    none of them are wired yet, so an unconditional DELETE is safe today.
    """
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {_SCHEMA}.users"))


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
    assigned_by_username: str | None = None,
) -> AssignmentRecord:
    """Atomically (re)assign a device to a technician, preserving history.

    One transaction: resolve the technician (and, if given, the actor)
    username to a user_id, validate the technician's role, lock the
    device's current active row (``SELECT ... FOR UPDATE``), then either
    leave it alone (same technician — no duplicate history row), or close
    it and insert a new active row.

    The partial unique index ``ux_user_device_assignments_active_device``
    remains the final concurrency guard; the row lock here narrows the
    race window but this function does not rely on application logic alone
    to enforce "one active assignment per device".

    Raises ValueError if the username does not exist or is not an active
    technician.
    """
    with session_scope() as session:
        tech_row = session.execute(
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

        assigned_by_id = None
        if assigned_by_username is not None:
            actor_row = session.execute(
                text(f"SELECT user_id FROM {_SCHEMA}.users WHERE username = :username"),
                {"username": assigned_by_username},
            ).first()
            assigned_by_id = actor_row[0] if actor_row else None

        current = session.execute(
            text(
                f"SELECT assignment_id, user_id FROM {_SCHEMA}.user_device_assignments "
                f"WHERE device_id = :device_id AND ended_at IS NULL FOR UPDATE"
            ),
            {"device_id": device_id},
        ).first()

        if current is not None and current[1] == tech_user_id:
            # Already assigned to this technician — externally-visible state
            # is unchanged, and closing+reinserting would create a
            # duplicate history row for no behavioral difference.
            row = session.execute(
                text(
                    f"""
                    SELECT {_ASSIGNMENT_COLUMNS}
                    FROM {_SCHEMA}.user_device_assignments a
                    JOIN {_SCHEMA}.users u ON u.user_id = a.user_id
                    WHERE a.assignment_id = :assignment_id
                    """
                ),
                {"assignment_id": current[0]},
            ).first()
            return _to_assignment(row)

        if current is not None:
            session.execute(
                text(
                    f"UPDATE {_SCHEMA}.user_device_assignments "
                    f"SET ended_at = now() WHERE assignment_id = :assignment_id"
                ),
                {"assignment_id": current[0]},
            )

        new_row = session.execute(
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
                "assigned_by": assigned_by_id,
            },
        ).first()

    return AssignmentRecord(
        assignment_id=new_row[0],
        device_id=new_row[1],
        user_id=new_row[2],
        username=technician_username,
        assigned_at=new_row[3],
        assigned_by=new_row[4],
        ended_at=new_row[5],
    )


def end_active_device_assignment(
    device_id: str, ended_at: datetime | None = None
) -> None:
    """Close the active assignment for a device, if any. No-op otherwise —
    matches the current UI's "clear technician" behavior for a device that
    has no assignment.
    """
    with session_scope() as session:
        session.execute(
            text(
                f"UPDATE {_SCHEMA}.user_device_assignments "
                f"SET ended_at = COALESCE(:ended_at, now()) "
                f"WHERE device_id = :device_id AND ended_at IS NULL"
            ),
            {"device_id": device_id, "ended_at": ended_at},
        )


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
    transformer_id: str, device_code: str, status: str = "active"
) -> DeviceRecord:
    """Register a new device under a transformer. Create-only — there is no
    ON CONFLICT/upsert path; a duplicate is always an error, never a merge.

    One transaction: validate the transformer exists, pre-check the
    (transformer_id, device_code) pair for a friendlier error than a raw
    constraint violation, generate device_id, then insert.

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
    with session_scope() as session:
        transformer_row = session.execute(
            text(f"SELECT 1 FROM {_SCHEMA}.transformers WHERE transformer_id = :transformer_id"),
            {"transformer_id": transformer_id},
        ).first()
        if transformer_row is None:
            raise ValueError(f"Unknown transformer_id: {transformer_id!r}")

        duplicate_row = session.execute(
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

        next_index = session.execute(
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
        device_id = f"{transformer_id}-d{next_index}"

        row = session.execute(
            text(
                f"""
                INSERT INTO {_SCHEMA}.devices (device_id, transformer_id, device_code, status)
                VALUES (:device_id, :transformer_id, :device_code, :status)
                RETURNING {_DEVICE_COLUMNS}
                """
            ),
            {
                "device_id": device_id,
                "transformer_id": transformer_id,
                "device_code": device_code,
                "status": status,
            },
        ).first()

    return _to_device(row)


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
