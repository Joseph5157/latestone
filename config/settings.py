"""
Central configuration module.

All environment-dependent values are read here, once, so the rest of the
application never touches os.environ directly. This keeps secrets and
connection details out of UI/service/repository code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class DatabaseSettings:
    db: str = os.getenv("POSTGRES_DB", "powerplant_demo")
    user: str = os.getenv("POSTGRES_USER", "powerplant")
    password: str = os.getenv("POSTGRES_PASSWORD", "")
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = _get_int("POSTGRES_PORT", 5432)
    schema: str = os.getenv("DB_SCHEMA", "trfr_temperature")

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )


@dataclass(frozen=True)
class DemoAuthSettings:
    username: str = os.getenv("DEMO_USERNAME", "admin")
    password: str = os.getenv("DEMO_PASSWORD", "demo1234")


@dataclass(frozen=True)
class DashSettings:
    debug: bool = _get_bool("DASH_DEBUG", True)
    host: str = os.getenv("DASH_HOST", "0.0.0.0")
    port: int = _get_int("DASH_PORT", 8050)


@dataclass(frozen=True)
class DemoDeviceSettings:
    """Fixed demo scope: exactly one transformer/device pair."""
    transformer: str = "aa12"
    device: str = "29017"
    metric_label: str = "Temperature"
    unit: str = "°C"


@dataclass(frozen=True)
class MonitoringSettings:
    """Freshness policy and refresh cadence.

    expected_interval_minutes: current project/client-known requirement
        (readings arrive roughly every 30 minutes).
    stale_after_intervals: DEVELOPMENT APPLICATION POLICY. Requires client
        confirmation before production use.
    refresh_interval_seconds: UI polling cadence. Short by default for local
        development convenience; production polling should be aligned to
        actual ingestion behaviour.
    """
    schema: str = os.getenv("PLANT_MONITORING_SCHEMA", "plant_monitoring")
    expected_interval_minutes: int = _get_int("EXPECTED_INTERVAL_MINUTES", 30)
    stale_after_intervals: int = _get_int("STALE_AFTER_INTERVALS", 3)
    refresh_interval_seconds: int = _get_int("UI_REFRESH_INTERVAL_SECONDS", 60)

    @property
    def stale_after_minutes(self) -> int:
        return self.expected_interval_minutes * self.stale_after_intervals


@dataclass(frozen=True)
class WarningSettings:
    # Explicitly a demo configuration value, not a client-provided threshold.
    threshold_celsius: float = float(os.getenv("DEMO_WARNING_THRESHOLD_C", "45"))


database = DatabaseSettings()
monitoring = MonitoringSettings()
demo_auth = DemoAuthSettings()
dash_settings = DashSettings()
demo_device = DemoDeviceSettings()
warning_settings = WarningSettings()
