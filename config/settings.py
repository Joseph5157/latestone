"""
Central configuration module.

All environment-dependent values are read here, once, so the rest of the
application never touches os.environ directly. This keeps secrets and
connection details out of UI/service/repository code.
"""
from __future__ import annotations

import json
import os
import re
import secrets
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


#: The one truthy vocabulary this file recognises. Named once so a setting
#: that must ALSO reason about "was this explicitly asked for?" (see
#: resolve_programming_simulator_enabled) cannot disagree with `_get_bool`
#: about what "on" means.
_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def _is_truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in _TRUTHY_VALUES


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return _is_truthy(val)


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


class _JsonObject(list):
    """A JSON *object*, kept as ordered pairs.

    A distinct type rather than a bare list because `["a", "1"]` — a JSON
    array — would otherwise be indistinguishable from an object's pair list
    and get unpacked as if it were one.
    """


def _credential_pairs(raw: str) -> tuple[list[tuple[str, str]], str | None]:
    """The `DEMO_CREDENTIALS` JSON object as ordered pairs, or an error.

    `object_pairs_hook` is the point of this function. `json.loads` resolves a
    repeated key by silently keeping the last one, so
    `{"a": "x", "a": "y"}` would quietly configure ONE credential and give no
    hint which. Reading the pairs before they collapse into a dict is what lets
    a repeat be refused instead of guessed at.
    """
    try:
        parsed = json.loads(raw, object_pairs_hook=_JsonObject)
    except json.JSONDecodeError as exc:
        # Only the message and position — never `exc.doc`, which is the
        # configuration value itself and therefore contains the passwords.
        return [], (
            f"DEMO_CREDENTIALS is not valid JSON: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno}). Expected an object of "
            f'"username": "password" pairs.'
        )
    if not isinstance(parsed, _JsonObject):
        return [], (
            "DEMO_CREDENTIALS must be a JSON object of "
            '"username": "password" pairs.'
        )
    return list(parsed), None


def parse_demo_credentials(
    username: str, password: str, extra: str
) -> tuple[dict[str, str], str | None]:
    """Build the username -> password map, or refuse it entirely.

    ROLE-4A. Returns `(credentials, error)`; exactly one is meaningful. The
    map carries credentials and **nothing else** — no role, no identity, no
    capability. That is deliberate and load-bearing: a role read out of
    configuration would be a role an operator could grant themselves by
    editing their own credential entry. Roles live in `users`, and
    `auth_service.authenticate()` reads them from there.

    `DEMO_USERNAME`/`DEMO_PASSWORD` remain the single administrator pair they
    always were. `extra` (`DEMO_CREDENTIALS`) adds further personas as a JSON
    object:

        {"demo.tech01": "s3cret", "demo.general01": "pa,ss:word"}

    **JSON because a delimiter-separated grammar could not say what a password
    was.** The first form of this setting split on commas and then on the first
    colon, which made `a:pw,b:c` ambiguous: a password of `pw,b:c` for user `a`
    and the pair `a`/`pw` plus `b`/`c` are the same string, and the parser
    silently chose the second. The failure was quiet and it weakened a
    credential — the operator got a shorter password than they set, with no
    error. JSON quotes the values, so `,` and `:` are ordinary characters and
    the encoding has one reading.

    **Malformed configuration refuses the whole map**, rather than dropping the
    bad entry and keeping the rest. A partly-applied credential list is the
    shape that convinces an operator a persona is disabled when it is not, and
    ambiguity about who may sign in must never resolve to "some logins work".

    The returned error is safe to log: it names usernames and positions, never
    a secret and never the raw configuration.
    """
    credentials: dict[str, str] = {}
    if username and password:
        credentials[username] = password

    if not extra.strip():
        return credentials, None

    pairs, error = _credential_pairs(extra)
    if error is not None:
        return {}, error

    for position, pair in enumerate(pairs, start=1):
        name, secret = pair
        if not isinstance(name, str) or not name.strip():
            return {}, (
                f"DEMO_CREDENTIALS entry {position} has an empty username."
            )
        name = name.strip()
        if not isinstance(secret, str) or not secret:
            # A number, null, list or object here is a configuration mistake,
            # and coercing one to text would invent a password nobody chose.
            return {}, (
                f"DEMO_CREDENTIALS entry {position} ({name!r}) must have a "
                f"non-empty string password."
            )
        if name in credentials:
            return {}, (
                f"DEMO_CREDENTIALS entry {position} repeats username {name!r}; "
                f"refusing an ambiguous credential configuration."
            )
        credentials[name] = secret

    return credentials, None


@dataclass(frozen=True)
class DemoAuthSettings:
    """Placeholder credentials, replaced wholesale by the client's auth.

    There is deliberately **no** fallback credential. A hard-coded default
    password meant an operator who never configured anything still got a working
    login with a value published in `.env.example`. Unset now means unset, and
    `auth_service.verify_credentials()` fails closed.

    ROLE-4A widened this from one pair to a map so Technician and General
    personas can reach the same login path Administrator already used. What did
    NOT widen is what configuration may say: it names logins, never roles.
    """
    username: str = os.getenv("DEMO_USERNAME", "")
    password: str = os.getenv("DEMO_PASSWORD", "")
    extra_credentials: str = os.getenv("DEMO_CREDENTIALS", "")

    @property
    def credentials(self) -> dict[str, str]:
        """Configured logins. Empty when unset OR malformed — both fail closed."""
        return parse_demo_credentials(
            self.username, self.password, self.extra_credentials
        )[0]

    @property
    def config_error(self) -> str | None:
        """Why the map is empty despite something being configured, if so."""
        return parse_demo_credentials(
            self.username, self.password, self.extra_credentials
        )[1]

    @property
    def is_configured(self) -> bool:
        return bool(self.credentials)


#: The one environment/deployment-mode concept this app has (AUTH-PROD-HARDEN-1).
#: FLASK_SECRET_KEY's fail-closed requirement and the session cookie's
#: Secure flag both key off this single setting, rather than each growing its
#: own separate notion of "are we in production" that could disagree with the
#: other.
_VALID_APP_ENVIRONMENTS = ("development", "production")


def resolve_app_environment(raw: str) -> str:
    """`raw` (the `APP_ENV` env var) as a validated environment name.

    Blank or unset means `development` — an existing local `.env` that has
    never heard of `APP_ENV` keeps behaving exactly as it did before this
    setting existed. Anything other than the two recognised values raises
    immediately rather than silently treating a typo (`"prod"`, `"Production "`)
    as `development` and shipping an unhardened session.
    """
    value = (raw or "").strip().lower() or "development"
    if value not in _VALID_APP_ENVIRONMENTS:
        raise RuntimeError(
            f"APP_ENV must be one of {_VALID_APP_ENVIRONMENTS!r}, got {value!r}."
        )
    return value


APP_ENV: str = resolve_app_environment(os.getenv("APP_ENV", ""))
IS_PRODUCTION: bool = APP_ENV == "production"


def resolve_flask_secret_key(app_env: str, configured: str) -> str:
    """The Flask session-signing key for `app_env`, or a fail-closed error.

    Any non-production `app_env`: the configured key if one was set, else a
    fresh random key generated once per process start (evaluated exactly
    once, same as every other default in this file, so every request within
    one running process shares it). That is not a weaker default, it is a
    stronger one — no fixed value ships in `.env.example` for an attacker to
    read — the tradeoff is that a server restart invalidates every open
    session, which for local/demo Dash is the same "log in again" experience
    a browser tab close already produces (`auth-store` is session storage).
    Unchanged from AUTH-HARDEN-1's original behaviour.

    `production`: the configured key, or a `RuntimeError` naming exactly what
    is missing. A production deployment must NEVER fall back to a per-process
    random key — that would silently invalidate every signed-in session on
    every restart/redeploy (and would let two replicas of one deployment sign
    with two different keys). Failing closed at startup surfaces the missing
    configuration immediately, instead of as a wave of mysteriously
    logged-out operators after the next deploy.
    """
    configured = (configured or "").strip()
    if app_env == "production":
        if not configured:
            raise RuntimeError(
                "FLASK_SECRET_KEY must be set when APP_ENV=production. "
                "Production sessions must not sign with a per-process random "
                "key — set FLASK_SECRET_KEY explicitly (see .env.example)."
            )
        return configured
    return configured or secrets.token_hex(32)


@dataclass(frozen=True)
class FlaskSessionSettings:
    """Signs the trusted server-side session cookie (AUTH-HARDEN-1) and
    carries its transport-security policy (AUTH-PROD-HARDEN-1).

    This is NOT the `auth-store` `dcc.Store` — that is plain JSON the browser
    can edit freely and is never trusted for authorization after this gate.
    This is Flask's own signed session, which `services.auth_service` uses to
    remember which database user is logged in; the browser can see the cookie
    but cannot alter it without invalidating its signature.

    `secret_key` is resolved by `resolve_flask_secret_key()` — optional and
    auto-generated for local/demo use, required and fail-closed once
    `APP_ENV=production` (see that function's docstring).
    """
    secret_key: str = resolve_flask_secret_key(APP_ENV, os.getenv("FLASK_SECRET_KEY", ""))

    #: Sent only over HTTPS. `False` outside production so the cookie still
    #: reaches the browser when the app is served over plain local HTTP — a
    #: browser silently drops a `Secure` cookie set from an `http://` origin,
    #: which looks exactly like a broken login rather than an error. `True`
    #: in production, where this app is reached only through the deployment
    #: platform's HTTPS edge (see `app.py`'s comment beside where this is
    #: wired into `server.config`).
    cookie_secure: bool = IS_PRODUCTION

    #: Never readable from JavaScript, in every environment. There is no
    #: legitimate client-side reason to read the session cookie — `auth-store`
    #: is the presentation-only store scripts may touch — so this forecloses
    #: one whole class of session theft via XSS.
    cookie_httponly: bool = True

    #: `"Lax"` in every environment. This is a single-origin Dash app with no
    #: cross-site POST target the session cookie needs to accompany, so `Lax`
    #: costs nothing here and blocks the cookie from riding along on a
    #: cross-site request.
    cookie_samesite: str = "Lax"


def resolve_programming_simulator_enabled(app_env: str, raw: str) -> bool:
    """Whether the development-only RTL programming simulator is enabled.

    RTL-PROG-SIM-1. `SimulatorTransport` (ADR-018) is a deterministic test
    contract, NOT the Eskom protocol — a simulated `SUCCEEDED` says nothing
    about a physical RTL. So it must never be reachable from a real
    deployment, and reaching it must take a deliberate act:

    - **Default off.** Unset, blank, or any non-truthy value is `False`.
      An environment that has never heard of this setting cannot simulate.
    - **Explicitly on for local/demo use** (`app_env` other than
      `production`): a truthy value enables it.
    - **Fail closed in production.** A truthy value together with
      `APP_ENV=production` raises here, at configuration resolution — which
      is import time, so the process refuses to start. It deliberately does
      NOT silently downgrade to `False`: an operator who asked a production
      deployment to run a simulator has a mistaken belief about what that
      deployment is doing, and quietly ignoring the request would leave the
      belief intact. Same fail-closed shape as
      `resolve_flask_secret_key`, and for the same reason.

    Because the only truthy path returns from a branch that has already
    excluded production, no production process can hold `True` here — which
    is what makes `services/rtl_programming_simulation_service.py` the only
    module that ever constructs a `SimulatorTransport`, and makes that
    construction unreachable in production.
    """
    if not _is_truthy(raw):
        return False
    if app_env == "production":
        raise RuntimeError(
            "RTL_PROGRAMMING_SIMULATOR_ENABLED must not be enabled when "
            "APP_ENV=production. The RTL programming simulator is a "
            "development/demo-only path: it reports simulated command "
            "outcomes that are not evidence any physical RTL was "
            "programmed, and no real MQTT/SMS/Eskom communication occurs. "
            "Unset it, or set APP_ENV=development."
        )
    return True


@dataclass(frozen=True)
class ProgrammingSimulatorSettings:
    """RTL-PROG-SIM-1's single on/off boundary.

    Read through `services.rtl_programming_simulation_service.
    is_simulation_enabled()` rather than directly, so the "and not
    production" re-check travels with every consumer.
    """

    enabled: bool = resolve_programming_simulator_enabled(
        APP_ENV, os.getenv("RTL_PROGRAMMING_SIMULATOR_ENABLED", "")
    )


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
flask_session = FlaskSessionSettings()
dash_settings = DashSettings()
live_sim = LiveSimSettings()
programming_simulator = ProgrammingSimulatorSettings()
