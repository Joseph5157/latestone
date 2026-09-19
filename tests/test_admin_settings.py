"""SETTINGS-PAGE-1 — configuration panels live on the Administrator Settings
page, not Fleet Overview. No database: panel services are spies."""
from __future__ import annotations

import contextlib

import pytest
from dash import no_update
from dash._callback_context import context_value
from dash._utils import AttributeDict

from callbacks import freshness_threshold, temperature_threshold, vibration_contract
from components import freshness_threshold_panel, temperature_threshold_panel, vibration_contract_panel
from pages import admin_settings, plants_overview
from routes import NAV_KEY_BY_ROUTE, parse_pathname
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN, may_access_route
from tests.auth_test_support import trusted_session
from tests.dash_tree import find_by_id, text_of

PANEL_SLOTS = (
    freshness_threshold_panel.PANEL_ID,
    temperature_threshold_panel.PANEL_ID,
    vibration_contract_panel.PANEL_ID,
)

# (callback module, services to stub, set/clear button ids, extra State args)
PANELS = (
    (freshness_threshold, ("get_current_config", "set_config", "clear_config"),
     freshness_threshold_panel, ("",)),
    (temperature_threshold, ("get_current_threshold_config", "set_threshold_config", "clear_threshold_config"),
     temperature_threshold_panel, ("", "")),
    (vibration_contract, ("get_all_answers", "set_answer", "clear_answer"),
     vibration_contract_panel, ("", "")),
)


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


@contextlib.contextmanager
def _triggered_by(prop_id: str, value):
    token = context_value.set(
        AttributeDict({"triggered_inputs": [{"prop_id": prop_id, "value": value}]})
    )
    try:
        yield
    finally:
        context_value.reset(token)


def _register(module, service_names, monkeypatch):
    calls = []

    def _spy(name):
        def _fn(*args, **kwargs):
            calls.append(name)
            return {} if name == "get_all_answers" else None
        return _fn

    for name in service_names:
        monkeypatch.setattr(module.service, name, _spy(name))
    app = _CapturingApp()
    module.register(app)
    return app.functions, calls


class TestRoute:
    def test_path_parses_to_the_settings_route(self):
        assert parse_pathname("/admin/settings").name == "admin_settings"
        assert NAV_KEY_BY_ROUTE["admin_settings"] == "settings"

    def test_administrator_only(self):
        assert may_access_route(ADMINISTRATOR, "admin_settings") is True
        assert may_access_route(TECHNICIAN, "admin_settings") is False
        assert may_access_route(GENERAL, "admin_settings") is False


class TestLayouts:
    def test_settings_page_holds_every_configuration_slot(self):
        page = admin_settings.layout()
        for slot in PANEL_SLOTS:
            assert find_by_id(page, slot) is not None, slot
        assert "Settings" in text_of(page)

    def test_fleet_overview_no_longer_holds_configuration_slots(self):
        page = plants_overview.layout()
        for slot in PANEL_SLOTS + ("auto-disable-override-panel",):
            assert find_by_id(page, slot) is None, slot



@pytest.mark.parametrize("module, service_names, panel, extra_state", PANELS)
class TestPanelCallbacks:
    def test_panel_stays_silent_on_fleet_overview(self, module, service_names, panel, extra_state, monkeypatch):
        functions, calls = _register(module, service_names, monkeypatch)
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            assert functions["_render_panel"]({"route": "overview"}) is no_update
        assert calls == []

    def test_panel_renders_on_the_settings_page(self, module, service_names, panel, extra_state, monkeypatch):
        functions, calls = _register(module, service_names, monkeypatch)
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            assert functions["_render_panel"]({"route": "admin_settings"}) is not None
        assert calls, "an authorized render must query its service"

    @pytest.mark.parametrize("button_attr", ["SET_BTN_ID", "CLEAR_BTN_ID"])
    def test_panel_insertion_with_zero_clicks_is_not_a_click(
        self, module, service_names, panel, extra_state, button_attr, monkeypatch,
    ):
        """ADMIN-PANEL-LOAD-ERROR-1: Dash fires the action callback when a
        panel is inserted, with n_clicks=0; that must not validate or write."""
        functions, calls = _register(module, service_names, monkeypatch)
        button = getattr(panel, button_attr)
        with trusted_session(monkeypatch, user_id=1, role=ADMINISTRATOR):
            with _triggered_by(f"{button}.n_clicks", value=0):
                result = functions["_handle_action"](0, 0, *extra_state)
        assert result is no_update
        assert calls == []
