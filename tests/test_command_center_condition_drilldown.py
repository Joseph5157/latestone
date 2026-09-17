"""CLIENT-FEEDBACK-DRILLDOWN-1 interaction and scope regression tests."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from dash import dcc, html

import callbacks.command_center as callbacks
import services.command_center_service as service
from components.command_center.condition_investigation import (
    condition_investigation_card,
)
from components.command_center.electrical import (
    BATTERY_LOW_BUTTON_ID,
    POWER_DOWN_BUTTON_ID,
    electrical_conditions_card,
)
from services.device_scope import DeviceScope

NOW = datetime(2026, 9, 17, 8, 0, tzinfo=timezone.utc)


def _walk(node):
    if node is None:
        return
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


def _text(node) -> str:
    return " ".join(
        str(item)
        for item in _walk(node)
        if isinstance(item, (str, int, float))
    )


def _event(event_id, device_id, event_type, minute, voltage=None):
    return SimpleNamespace(
        event_id=event_id,
        device_id=device_id,
        transformer_id="t1",
        reported_uid=None,
        event_type=event_type,
        event_ts=NOW.replace(minute=minute),
        battery_voltage=voltage,
    )


def _path(device_id, code, transformer="AA12"):
    return SimpleNamespace(
        device_id=device_id,
        device_code=code,
        plant_name="North Plant",
        transformer_code=transformer,
    )


class TestConditionServiceFiltering:
    def test_power_down_selection_filters_and_deduplicates_latest_per_rtl(self, monkeypatch):
        captured = {}

        def events(**kwargs):
            captured.update(kwargs)
            return [
                _event(3, "d1", "power_down", 55, 3.5),
                _event(2, "d1", "power_down", 40, 3.4),
                _event(1, "d2", "power_down", 30, 3.3),
            ]

        monkeypatch.setattr(service, "list_recent_device_events", events)
        monkeypatch.setattr(
            service,
            "list_device_paths",
            lambda ids, *, scope: [_path("d1", "29001"), _path("d2", "29002")],
        )

        rows = service.get_condition_affected_rtls(
            "power_down", scope=DeviceScope(None), now=NOW
        )

        assert captured["event_types"] == ("power_down",)
        assert [row.asset_label for row in rows] == ["29001", "29002"]
        assert rows[0].event_id == 3
        assert all(row.event_type == "power_down" for row in rows)

    def test_battery_low_selection_uses_only_battery_low(self, monkeypatch):
        monkeypatch.setattr(
            service,
            "list_recent_device_events",
            lambda **kwargs: (
                [_event(4, "d1", "battery_low", 50, 3.7)]
                if kwargs["event_types"] == ("battery_low",)
                else []
            ),
        )
        monkeypatch.setattr(
            service, "list_device_paths", lambda ids, *, scope: [_path("d1", "29001")]
        )
        rows = service.get_condition_affected_rtls(
            "battery_low", scope=DeviceScope(None), now=NOW
        )
        assert len(rows) == 1
        assert rows[0].display_label == "Battery Low"

    def test_technician_scope_is_applied_to_event_and_path_reads(self, monkeypatch):
        scope = DeviceScope(frozenset({"assigned"}))
        calls = []
        monkeypatch.setattr(
            service,
            "list_recent_device_events",
            lambda **kwargs: calls.append(("events", kwargs)) or [],
        )
        monkeypatch.setattr(
            service,
            "list_device_paths",
            lambda ids, *, scope: calls.append(("paths", scope)) or [],
        )
        service.get_condition_affected_rtls("power_down", scope=scope, now=NOW)
        assert calls[0][1]["allowed_device_ids"] == frozenset({"assigned"})
        assert not [call for call in calls if call[0] == "paths"]

    def test_administrator_scope_is_unrestricted(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(
            service,
            "list_recent_device_events",
            lambda **kwargs: captured.update(kwargs) or [],
        )
        service.get_condition_affected_rtls(
            "battery_low", scope=DeviceScope(None), now=NOW
        )
        assert captured["allowed_device_ids"] is None
        assert captured["include_unattributed"] is False


class TestConditionInteraction:
    def test_cards_are_keyboard_native_buttons_with_controls_relationship(self):
        card = electrical_conditions_card(
            SimpleNamespace(electrical_conditions=service.ELECTRICAL_CONDITIONS)
        )
        buttons = [node for node in _walk(card) if isinstance(node, html.Button)]
        assert [button.id for button in buttons] == [
            POWER_DOWN_BUTTON_ID,
            BATTERY_LOW_BUTTON_ID,
        ]
        assert all(button.type == "button" for button in buttons)
        assert all(
            getattr(button, "aria-controls") == "command-center-condition-investigation"
            for button in buttons
        )
        assert all(getattr(button, "aria-pressed") == "false" for button in buttons)
        assert all(
            "View affected RTLs" in getattr(button, "aria-label")
            for button in buttons
        )

    def test_power_down_then_battery_low_switches_active_state(self, monkeypatch):
        monkeypatch.setattr(callbacks, "get_condition_affected_rtls", lambda *a, **k: ())
        power = callbacks.condition_selection_outputs(
            POWER_DOWN_BUTTON_ID, DeviceScope(None)
        )
        battery = callbacks.condition_selection_outputs(
            BATTERY_LOW_BUTTON_ID, DeviceScope(None)
        )
        assert power[0] == {"event_type": "power_down"}
        assert power[4:] == ("true", "false")
        assert "--active" in power[2] and "--active" not in power[3]
        assert battery[0] == {"event_type": "battery_low"}
        assert battery[4:] == ("false", "true")
        assert "--active" not in battery[2] and "--active" in battery[3]

    def test_zero_result_is_explicit_and_scope_aware(self):
        card = condition_investigation_card("Power Down", ())
        text = _text(card)
        assert "No Power Down occurrences" in text
        assert "current access scope" in text

    def test_selected_rtl_drills_into_existing_device_route(self):
        row = service.RecentEvent(
            event_id=1,
            occurred_at=NOW,
            event_type="power_down",
            display_label="Power Down",
            tone="critical",
            tone_label="Critical",
            asset_label="29017",
            context_label="North Plant / AA12",
            detail="Battery voltage · 3.50 V",
            asset_href="/devices/plant-01-t1-d1",
            time_label="08:00",
            time_title="2026-09-17 08:00 UTC",
        )
        card = condition_investigation_card("Power Down", (row,))
        links = [node for node in _walk(card) if isinstance(node, dcc.Link)]
        assert [(link.children, link.href) for link in links] == [
            ("Open RTL →", "/devices/plant-01-t1-d1")
        ]
        text = _text(card)
        assert "29017" in text
        assert "North Plant / AA12" in text
        assert "Power Down" in text
        assert "Latest recorded occurrence" in text

    def test_focus_and_pointer_affordances_are_declared(self):
        css = open("assets/app.css", encoding="utf-8").read()
        assert ".command-center__condition-button:focus-visible" in css
        assert ".command-center__condition-button:hover" in css
        assert "cursor: pointer" in css
