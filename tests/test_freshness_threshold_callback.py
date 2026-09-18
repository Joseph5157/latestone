"""FRESHNESS-CONFIG-1 callback authorization — authorize before any query or
write. Service functions are spies; no database."""
from __future__ import annotations

import contextlib

import pytest
from dash import no_update
from dash._callback_context import context_value
from dash._utils import AttributeDict

from callbacks import freshness_threshold
from components.freshness_threshold_panel import CLEAR_BTN_ID, ERROR_ID, SET_BTN_ID
from services.authorization import (
    ADMINISTRATOR,
    GENERAL,
    MANAGE_FRESHNESS_THRESHOLD,
    TECHNICIAN,
    may_perform_capability,
)
from tests.auth_test_support import no_trusted_session, trusted_session
from tests.dash_tree import find_by_id, text_of

DENIED_ROLES = (TECHNICIAN, GENERAL)


@contextlib.contextmanager
def _triggered_by(prop_id: str, value=1):
    token = context_value.set(
        AttributeDict({"triggered_inputs": [{"prop_id": prop_id, "value": value}]})
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
    get_config = _Spy()
    set_config = _Spy()
    clear_config = _Spy()
    monkeypatch.setattr(freshness_threshold.service, "get_current_config", get_config)
    monkeypatch.setattr(freshness_threshold.service, "set_config", set_config)
    monkeypatch.setattr(freshness_threshold.service, "clear_config", clear_config)
    app = _CapturingApp()
    freshness_threshold.register(app)
    return app.functions, get_config, set_config, clear_config


def _click_set(handler, minutes="720"):
    with _triggered_by(f"{SET_BTN_ID}.n_clicks"):
        return handler(1, 0, minutes)


def _click_clear(handler):
    with _triggered_by(f"{CLEAR_BTN_ID}.n_clicks"):
        return handler(0, 1, "")


class TestCapability:
    def test_administrator_only(self):
        assert may_perform_capability(ADMINISTRATOR, MANAGE_FRESHNESS_THRESHOLD) is True
        assert may_perform_capability(TECHNICIAN, MANAGE_FRESHNESS_THRESHOLD) is False
        assert may_perform_capability(GENERAL, MANAGE_FRESHNESS_THRESHOLD) is False


class TestPanelRenderAuthorization:
    def test_wrong_route_never_queries(self, handlers):
        functions, get_config, _set, _clear = handlers
        assert functions["_render_panel"]({"route": "device"}) is no_update
        assert get_config.calls == []

    def test_administrator_renders_the_panel(self, handlers, monkeypatch):
        functions, get_config, _set, _clear = handlers
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            result = functions["_render_panel"]({"route": "overview"})
        assert get_config.calls
        assert "Freshness Threshold" in text_of(result)

    @pytest.mark.parametrize("role", DENIED_ROLES)
    def test_denied_roles_never_query_and_render_nothing(self, handlers, monkeypatch, role):
        functions, get_config, _set, _clear = handlers
        with trusted_session(monkeypatch, user_id=1, role=role):
            result = functions["_render_panel"]({"route": "overview"})
        assert get_config.calls == []
        assert result is None

    def test_no_trusted_session_never_queries(self, handlers):
        functions, get_config, _set, _clear = handlers
        with no_trusted_session():
            assert functions["_render_panel"]({"route": "overview"}) is None
        assert get_config.calls == []


class TestActions:
    def test_administrator_save_reaches_the_service_with_parsed_minutes(self, handlers, monkeypatch):
        functions, _get, set_config, _clear = handlers
        with trusted_session(monkeypatch, user_id=7, role=ADMINISTRATOR):
            _click_set(functions["_handle_action"], " 720 ")
        assert set_config.calls == [{"stale_after_minutes": 720, "actor_user_id": 7}]

    def test_administrator_reset_reaches_the_service(self, handlers, monkeypatch):
        functions, _get, _set, clear_config = handlers
        with trusted_session(monkeypatch, user_id=7, role=ADMINISTRATOR):
            _click_clear(functions["_handle_action"])
        assert clear_config.calls == [{"actor_user_id": 7}]

    @pytest.mark.parametrize("button", [SET_BTN_ID, CLEAR_BTN_ID])
    def test_panel_insertion_with_zero_clicks_is_not_a_click(self, handlers, monkeypatch, button):
        """Dash fires the action callback when the panel is inserted, with
        n_clicks=0. That must not validate the empty input or write."""
        functions, _get, set_config, clear_config = handlers
        with trusted_session(monkeypatch, user_id=7, role=ADMINISTRATOR):
            with _triggered_by(f"{button}.n_clicks", value=0):
                result = functions["_handle_action"](0, 0, "")
        assert result is no_update
        assert set_config.calls == [] and clear_config.calls == []

    def test_invalid_input_shows_an_error_and_writes_nothing(self, handlers, monkeypatch):
        functions, _get, set_config, _clear = handlers
        with trusted_session(monkeypatch, user_id=7, role=ADMINISTRATOR):
            result = _click_set(functions["_handle_action"], "0")
        assert set_config.calls == []
        assert "between 5 minutes" in text_of(find_by_id(result, ERROR_ID))

    @pytest.mark.parametrize("role", DENIED_ROLES)
    def test_denied_roles_never_reach_a_write(self, handlers, monkeypatch, role):
        functions, _get, set_config, clear_config = handlers
        with trusted_session(monkeypatch, user_id=1, role=role):
            assert _click_set(functions["_handle_action"]) is not None
            _click_clear(functions["_handle_action"])
        assert set_config.calls == []
        assert clear_config.calls == []

    def test_no_trusted_session_refuses_before_any_write(self, handlers):
        functions, _get, set_config, _clear = handlers
        with no_trusted_session():
            assert _click_set(functions["_handle_action"]) is not None
        assert set_config.calls == []
