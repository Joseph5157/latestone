"""BR016 ownership boundary: RTL Master, never the dashboard scheduler."""
from __future__ import annotations

from pathlib import Path

from services.authorization import (
    ADMINISTRATOR,
    GENERAL,
    TECHNICIAN,
    TOGGLE_MESSAGE_FORWARDING,
    may_perform_action,
)


ROOT = Path(__file__).resolve().parents[1]


def test_manual_forwarding_authorization_is_unchanged():
    assert may_perform_action(ADMINISTRATOR, TOGGLE_MESSAGE_FORWARDING, is_assigned=False)
    assert may_perform_action(TECHNICIAN, TOGGLE_MESSAGE_FORWARDING, is_assigned=True)
    assert not may_perform_action(TECHNICIAN, TOGGLE_MESSAGE_FORWARDING, is_assigned=False)
    assert not may_perform_action(GENERAL, TOGGLE_MESSAGE_FORWARDING, is_assigned=True)


def test_no_active_dashboard_br016_scheduler_or_override_exists():
    assert not (ROOT / "services" / "forwarding_auto_disable_service.py").exists()
    assert not (ROOT / "scripts" / "run_forwarding_auto_disable.py").exists()
    assert not (ROOT / "callbacks" / "forwarding_schedule.py").exists()
    assert not (ROOT / "components" / "auto_disable_override_panel.py").exists()
    assert "forwarding_schedule" not in (ROOT / "app.py").read_text(encoding="utf-8")


def test_legacy_schema_is_not_exposed_as_an_administrator_capability():
    authorization_source = (ROOT / "services" / "authorization.py").read_text(encoding="utf-8")
    assert "MANAGE_AUTO_DISABLE_OVERRIDE" not in authorization_source
    assert "manage_auto_disable_override" not in authorization_source


def test_manual_forwarding_copy_names_rtl_master_br016_ownership():
    drawer_source = (ROOT / "components" / "device_manage_drawer.py").read_text(encoding="utf-8")
    assert "BR016's daily cutoff is" in drawer_source
    assert "RTL Master, not this dashboard" in drawer_source
    assert "documented 18:30 automatic disable are not yet connected" not in drawer_source
