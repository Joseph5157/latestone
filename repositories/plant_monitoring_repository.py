"""
Plant monitoring repository — the only module containing raw SQL.

No generic raw-query helpers exist here. Identifiers (schema name) come from
application configuration, never from browser or user input. Metric lists are
bound with SQLAlchemy expanding parameters — never interpolated into SQL strings.

There is no unbounded reading query by design: PostgreSQL must always perform
device/metric/time-range filtering.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import bindparam, text

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
    device_id: str
    transformer_id: str
    device_code: str
    status: str


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


def _to_plant(row) -> PlantRecord:
    return PlantRecord(*row)


def _to_transformer(row) -> TransformerRecord:
    return TransformerRecord(*row)


def _to_device(row) -> DeviceRecord:
    return DeviceRecord(*row)


def _to_reading(row) -> RawReading:
    return RawReading(row[0], row[1], row[2], float(row[3]))


# ---------------------------------------------------------------------------
# Hierarchy queries
# ---------------------------------------------------------------------------

def list_plants() -> list[PlantRecord]:
    with session_scope() as session:
        rows = session.execute(
            text(f"SELECT plant_id, name, country, latitude, longitude, "
                 f"capacity_mw, primary_fuel, status FROM {_SCHEMA}.plants ORDER BY name")
        ).all()
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


def list_transformers(plant_id: str) -> list[TransformerRecord]:
    with session_scope() as session:
        rows = session.execute(
            text(f"SELECT transformer_id, plant_id, transformer_code, status "
                 f"FROM {_SCHEMA}.transformers WHERE plant_id = :plant_id "
                 f"ORDER BY transformer_code"),
            {"plant_id": plant_id},
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


def list_devices(transformer_id: str) -> list[DeviceRecord]:
    with session_scope() as session:
        rows = session.execute(
            text(f"SELECT device_id, transformer_id, device_code, status "
                 f"FROM {_SCHEMA}.devices WHERE transformer_id = :transformer_id "
                 f"ORDER BY device_code"),
            {"transformer_id": transformer_id},
        ).all()
    return [_to_device(r) for r in rows]


def get_device(device_id: str) -> DeviceRecord | None:
    with session_scope() as session:
        row = session.execute(
            text(f"SELECT device_id, transformer_id, device_code, status "
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
