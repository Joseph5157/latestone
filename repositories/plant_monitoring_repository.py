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


def count_hierarchy_by_plant() -> dict[str, tuple[int, int]]:
    """Returns {plant_id: (transformer_count, device_count)}."""
    with session_scope() as session:
        rows = session.execute(
            text(
                f"""
                SELECT p.plant_id,
                       COUNT(DISTINCT t.transformer_id) AS transformers,
                       COUNT(d.device_id)               AS devices
                FROM {_SCHEMA}.plants p
                LEFT JOIN {_SCHEMA}.transformers t ON t.plant_id = p.plant_id
                LEFT JOIN {_SCHEMA}.devices d      ON d.transformer_id = t.transformer_id
                GROUP BY p.plant_id
                """
            )
        ).all()
    return {r[0]: (r[1], r[2]) for r in rows}


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
