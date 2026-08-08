"""
Monitoring repository (multi-plant demo).

Unlike repositories/temperature_repository.py, this module queries a
single consolidated table (monitoring.readings) with plant_id/metric as
ordinary parameterized values - there is no dynamic identifier/table-name
building here, because the schema itself no longer needs one table per
device. That's the whole point of the consolidated design: plant_id is
just data, so normal parameterized queries are sufficient and there is no
identifier-injection surface to defend against in the first place.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from db.engine import session_scope

DEFAULT_METRIC = "temperature"


@dataclass(frozen=True)
class Plant:
    plant_id: str
    name: str
    country: str
    latitude: float
    longitude: float
    capacity_mw: float | None
    primary_fuel: str | None
    transformer: str
    device: str


@dataclass(frozen=True)
class RawReading:
    timestamp: datetime
    value: float


def list_plants() -> list[Plant]:
    with session_scope() as session:
        rows = session.execute(
            text(
                """
                SELECT plant_id, name, country, latitude, longitude,
                       capacity_mw, primary_fuel, transformer, device
                FROM monitoring.plants
                ORDER BY name ASC
                """
            )
        ).all()
    return [
        Plant(
            plant_id=r[0],
            name=r[1],
            country=r[2],
            latitude=float(r[3]),
            longitude=float(r[4]),
            capacity_mw=float(r[5]) if r[5] is not None else None,
            primary_fuel=r[6],
            transformer=r[7],
            device=r[8],
        )
        for r in rows
    ]


def get_all_readings(plant_id: str, metric: str = DEFAULT_METRIC) -> list[RawReading]:
    with session_scope() as session:
        rows = session.execute(
            text(
                """
                SELECT reading_ts, value FROM monitoring.readings
                WHERE plant_id = :plant_id AND metric = :metric
                ORDER BY reading_ts ASC
                """
            ),
            {"plant_id": plant_id, "metric": metric},
        ).all()
    return [RawReading(timestamp=r[0], value=float(r[1])) for r in rows]


def get_recent_readings(
    plant_id: str, metric: str = DEFAULT_METRIC, limit: int = 50
) -> list[RawReading]:
    with session_scope() as session:
        rows = session.execute(
            text(
                """
                SELECT reading_ts, value FROM monitoring.readings
                WHERE plant_id = :plant_id AND metric = :metric
                ORDER BY reading_ts DESC
                LIMIT :limit
                """
            ),
            {"plant_id": plant_id, "metric": metric, "limit": limit},
        ).all()
    return [RawReading(timestamp=r[0], value=float(r[1])) for r in rows]


def get_latest_reading(plant_id: str, metric: str = DEFAULT_METRIC) -> RawReading | None:
    with session_scope() as session:
        row = session.execute(
            text(
                """
                SELECT reading_ts, value FROM monitoring.readings
                WHERE plant_id = :plant_id AND metric = :metric
                ORDER BY reading_ts DESC
                LIMIT 1
                """
            ),
            {"plant_id": plant_id, "metric": metric},
        ).first()
    return RawReading(timestamp=row[0], value=float(row[1])) if row else None
