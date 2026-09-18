"""THRESH-CONFIG-1 callback authorization — the temperature threshold panel
must authorize before any query or write, exactly like
callbacks/forwarding_schedule.py's override panel (C08-AUTO-DISABLE-1),
which this gate's capability (MANAGE_TEMPERATURE_THRESHOLD) mirrors.

No database: the service functions are replaced with spies so these tests
prove the CALLBACK's authorization boundary, not the service/repository
layer (covered separately in tests/test_temperature_threshold.py).
"""
from __future__ import annotations

import contextlib

import pytest
from dash import no_update
from dash._callback_context import context_value
from dash._utils import AttributeDict

from callbacks import temperature_threshold
from components.temperature_threshold_panel import CLEAR_BTN_ID, SET_BTN_ID
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN
from tests.auth_test_support import no_trusted_session, trusted_session

EVERY_ROLE = (ADMINISTRATOR, TECHNICIAN, GENERAL)
DENIED_ROLES = (TECHNICIAN, GENERAL)


@contextlib.contextmanager
def _triggered_by(prop_id: str):
    """Simulate `dash.callback_context.triggered` outside a real Dash
    request — `_handle_action` reads it to tell SET_BTN_ID apart from
    CLEAR_BTN_ID, the same two-Input-one-Output shape
    callbacks/forwarding_schedule.py uses."""
    token = context_value.set(
        AttributeDict({"triggered_inputs": [{"prop_id": prop_id, "value": 1}]})
    )
    try:
        yield
    finally:
        context_value.reset(token)


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


class _Spy:
    def __init__(self, return_value=None):
        self.calls = []
        self.return_value = return_value

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.return_value


@pytest.fixture
def handlers(monkeypatch):
    get_config = _Spy(return_value=None)
    set_config = _Spy(return_value=None)
    clear_config = _Spy(return_value=None)
    monkeypatch.setattr(temperature_threshold.service, "get_current_threshold_config", get_config)
    monkeypatch.setattr(temperature_threshold.service, "set_threshold_config", set_config)
    monkeypatch.setattr(temperature_threshold.service, "clear_threshold_config", clear_config)
    monkeypatch.setattr(
        temperature_threshold.service, "parse_temperature",
        lambda raw, *, field_label: float(raw),
    )

    app = _CapturingApp()
    temperature_threshold.register(app)
    return app.functions, get_config, set_config, clear_config


# ---------------------------------------------------------------------------
# Panel render — authorize before any query
# ---------------------------------------------------------------------------


class TestPanelRenderAuthorization:
    def test_wrong_route_never_queries(self, handlers):
        render, get_config, _set, _clear = handlers
        result = render["_render_panel"]({"route": "device"})
        assert get_config.calls == []
        assert result is no_update

    def test_administrator_renders_the_panel(self, handlers, monkeypatch):
        render, get_config, _set, _clear = handlers
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = render["_render_panel"]({"route": "admin_settings"})
        assert get_config.calls, "an authorized render must query the config"
        assert result is not None

    @pytest.mark.parametrize("role", DENIED_ROLES)
    def test_denied_roles_never_query_and_render_nothing(self, handlers, monkeypatch, role):
        render, get_config, _set, _clear = handlers
        with trusted_session(monkeypatch, user_id=1, role=role):
            result = render["_render_panel"]({"route": "admin_settings"})
        assert get_config.calls == [], f"{role} must not reach the config query"
        assert result is None

    def test_no_trusted_session_never_queries(self, handlers):
        render, get_config, _set, _clear = handlers
        with no_trusted_session():
            result = render["_render_panel"]({"route": "admin_settings"})
        assert get_config.calls == []
        assert result is None


# ---------------------------------------------------------------------------
# Set/clear actions — authorize before any write
# ---------------------------------------------------------------------------


def _click_set(handler, warning="60", critical="75"):
    with _triggered_by(f"{SET_BTN_ID}.n_clicks"):
        return handler(1, 0, warning, critical)


def _click_clear(handler, warning="", critical=""):
    with _triggered_by(f"{CLEAR_BTN_ID}.n_clicks"):
        return handler(0, 1, warning, critical)


class TestActionAuthorization:
    def test_administrator_set_reaches_the_service(self, handlers, monkeypatch):
        functions, _get_config, set_config, _clear_config = handlers
        with trusted_session(monkeypatch, user_id=7, role=ADMINISTRATOR):
            _click_set(functions["_handle_action"])
        assert set_config.calls, "administrator must reach set_threshold_config"
        assert set_config.calls[0]["actor_user_id"] == 7
        assert set_config.calls[0]["warning_c"] == 60.0
        assert set_config.calls[0]["critical_c"] == 75.0

    def test_administrator_clear_reaches_the_service(self, handlers, monkeypatch):
        functions, _get_config, _set_config, clear_config = handlers
        with trusted_session(monkeypatch, user_id=7, role=ADMINISTRATOR):
            _click_clear(functions["_handle_action"])
        assert clear_config.calls
        assert clear_config.calls[0]["actor_user_id"] == 7

    @pytest.mark.parametrize("role", DENIED_ROLES)
    def test_denied_roles_never_reach_set(self, handlers, monkeypatch, role):
        functions, _get_config, set_config, _clear_config = handlers
        with trusted_session(monkeypatch, user_id=1, role=role):
            result = _click_set(functions["_handle_action"])
        assert set_config.calls == [], f"{role} must not reach set_threshold_config"
        assert result is not None  # a refusal notice, not a silent no-op

    @pytest.mark.parametrize("role", DENIED_ROLES)
    def test_denied_roles_never_reach_clear(self, handlers, monkeypatch, role):
        functions, _get_config, _set_config, clear_config = handlers
        with trusted_session(monkeypatch, user_id=1, role=role):
            _click_clear(functions["_handle_action"])
        assert clear_config.calls == [], f"{role} must not reach clear_threshold_config"

    def test_no_trusted_session_refuses_before_any_write(self, handlers):
        functions, _get_config, set_config, _clear_config = handlers
        with no_trusted_session():
            result = _click_set(functions["_handle_action"])
        assert set_config.calls == []
        assert result is not None
