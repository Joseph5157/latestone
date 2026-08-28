"""
Central configuration module.

All environment-dependent values are read here, once, so the rest of the
application never touches os.environ directly. This keeps secrets and
connection details out of UI/service/repository code.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(value: str, name: str) -> str:
    """Guard a value that will be interpolated into SQL as an identifier.

    Schema names cannot be passed as bound parameters, so the repository
    interpolates this one. It comes from application configuration and is not
    reachable from browser input, but validating here means that stays true
    even if the value is later sourced from somewhere less trusted.
    """
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"{name} must be a plain SQL identifier, got {value!r}")
    return value


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


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _parse_csv_list(name: str) -> tuple[str, ...]:
    val = os.getenv(name, "")
    return tuple(item.strip() for item in val.split(",") if item.strip())


@dataclass(frozen=True)
class DatabaseSettings:
    db: str = os.getenv("POSTGRES_DB", "powerplant_demo")
    user: str = os.getenv("POSTGRES_USER", "powerplant")
    password: str = os.getenv("POSTGRES_PASSWORD", "")
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = _get_int("POSTGRES_PORT", 5432)

    @property
    def sqlalchemy_url(self) -> str:
        # Credentials must be percent-encoded: an unescaped '@', ':' or '/' in a
        # password otherwise corrupts the URL and surfaces as a baffling
        # "invalid literal for int()" from the port parser.
        return (
            f"postgresql+psycopg2://{quote_plus(self.user)}:{quote_plus(self.password)}"
            f"@{self.host}:{self.port}/{self.db}"
        )


# Defaults are chosen so that an unconfigured environment is the *safe* one and
# anything riskier has to be asked for explicitly. This is the primary
# development application, not a throwaway, and it is destined for a government
# client's environment.
DEFAULT_DASH_DEBUG = False      # was True: never the default for a served app
DEFAULT_DASH_HOST = "127.0.0.1"  # was 0.0.0.0: exposing interfaces is opt-in


@dataclass(frozen=True)
class DemoAuthSettings:
    """Placeholder credentials, replaced wholesale by the client's auth.

    There is deliberately **no** fallback credential. A hard-coded default
    password meant an operator who never configured anything still got a working
    login with a value published in `.env.example`. Unset now means unset, and
    `auth_service.verify_credentials()` fails closed.
    """
    username: str = os.getenv("DEMO_USERNAME", "")
    password: str = os.getenv("DEMO_PASSWORD", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.username) and bool(self.password)


@dataclass(frozen=True)
class DashSettings:
    debug: bool = _get_bool("DASH_DEBUG", DEFAULT_DASH_DEBUG)
    host: str = os.getenv("DASH_HOST", DEFAULT_DASH_HOST)
    port: int = _get_int("DASH_PORT", 8050)


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
    schema: str = _validate_identifier(
        os.getenv("PLANT_MONITORING_SCHEMA", "plant_monitoring"),
        "PLANT_MONITORING_SCHEMA",
    )
    expected_interval_minutes: int = _get_int("EXPECTED_INTERVAL_MINUTES", 30)
    stale_after_intervals: int = _get_int("STALE_AFTER_INTERVALS", 3)
    refresh_interval_seconds: int = _get_int("UI_REFRESH_INTERVAL_SECONDS", 60)

    @property
    def stale_after_minutes(self) -> int:
        return self.expected_interval_minutes * self.stale_after_intervals


@dataclass(frozen=True)
class LiveSimSettings:
    """db/live_simulator.py — the demo/dev live-append feed, distinct from
    the one-time historical batch in db/seed_plant_monitoring.py.

    device_ids/metrics empty (the default) means "every device"/"every
    metric" — db.live_simulator validates any non-empty list against the
    real hierarchy/metric registry at startup rather than silently ignoring
    a typo.
    """
    interval_seconds: float = _get_float("LIVE_SIM_INTERVAL_SECONDS", 10.0)
    device_ids: tuple[str, ...] = _parse_csv_list("LIVE_SIM_DEVICE_IDS")
    metrics: tuple[str, ...] = _parse_csv_list("LIVE_SIM_METRICS")
    noise_scale: float = _get_float("LIVE_SIM_NOISE_SCALE", 1.0)


database = DatabaseSettings()
monitoring = MonitoringSettings()
demo_auth = DemoAuthSettings()
dash_settings = DashSettings()
live_sim = LiveSimSettings()
