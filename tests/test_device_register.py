"""Tests for device registration — layout, validation, review, persistence.

Layout/validation/review tests exercise pure logic (no Dash runtime, no
database). Persistence tests (DB-4) are database-backed and use the
isolated_schema fixture from tests/conftest.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from callbacks.device_register import (
    _plant_options,
    _transformer_options,
    _validate_form,
    _review_summary,
)
from pages.device_register import layout
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.device_registration import (
    RegistrationError,
    register_device,
    update_device_metadata,
)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class TestDeviceRegisterLayout:
    def test_layout_returns_component(self):
        lay = layout()
        assert hasattr(lay, "children")

    def test_layout_has_breadcrumb(self):
        lay = layout()
        assert "breadcrumb" in str(lay).lower() or "Devices" in str(lay)

    def test_layout_has_form(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-form" in ids

    def test_layout_has_review_section(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-review" in ids

    def test_layout_has_success_section(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-success" in ids

    def test_layout_has_scope_notice(self):
        lay = layout()
        page_text = str(lay)
        assert "Registers device identity only" in page_text

    def test_layout_has_required_fields(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-code" in ids
        assert "device-register-plant" in ids
        assert "device-register-transformer" in ids
        assert "device-register-status" in ids

    def test_layout_has_error_section(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-error" in ids


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidateForm:
    def test_empty_code_fails(self):
        errors = _validate_form("", "plant-1", "tx-1")
        assert "code" in errors

    def test_whitespace_only_code_fails(self):
        errors = _validate_form("   ", "plant-1", "tx-1")
        assert "code" in errors

    def test_code_too_long_fails(self):
        errors = _validate_form("a" * 11, "plant-1", "tx-1")
        assert "code" in errors

    def test_code_exactly_10_chars_passes(self):
        errors = _validate_form("a" * 10, "plant-1", "tx-1")
        assert "code" not in errors

    def test_missing_plant_fails(self):
        errors = _validate_form("29017", "", "tx-1")
        assert "plant" in errors

    def test_missing_transformer_fails(self):
        errors = _validate_form("29017", "plant-1", "")
        assert "transformer" in errors

    def test_all_valid_returns_empty(self):
        errors = _validate_form("29017", "plant-1", "tx-1")
        assert errors == {}

    def test_valid_with_whitespace_code_passes(self):
        errors = _validate_form(" 29017 ", "plant-1", "tx-1")
        assert errors == {}


# ---------------------------------------------------------------------------
# Review summary
# ---------------------------------------------------------------------------

class TestReviewSummary:
    def test_returns_div(self):
        summary = _review_summary("29017", "Plant A", "T1", "active")
        assert hasattr(summary, "children")

    def test_shows_all_fields(self):
        summary = _review_summary("29017", "Plant A", "T1", "active")
        text = str(summary)
        assert "29017" in text
        assert "Plant A" in text
        assert "T1" in text
        assert "Active" in text


# ---------------------------------------------------------------------------
# Persistence (DB-4)
# ---------------------------------------------------------------------------

def _seed_transformer(transformer_id: str, plant_id: str = "test-p1") -> None:
    """Insert a minimal plant/transformer row (idempotent) so devices can be
    registered under transformer_id.
    """
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants (plant_id, name, country, latitude, longitude) "
                f"VALUES (:plant_id, 'Test Plant', 'Testland', 0, 0) "
                f"ON CONFLICT (plant_id) DO NOTHING"
            ),
            {"plant_id": plant_id},
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers (transformer_id, plant_id, transformer_code) "
                f"VALUES (:transformer_id, :plant_id, :code) "
                f"ON CONFLICT (transformer_id) DO NOTHING"
            ),
            {"transformer_id": transformer_id, "plant_id": plant_id, "code": transformer_id},
        )


def _insert_raw_device(device_id: str, transformer_id: str, device_code: str) -> None:
    """Insert a device row directly, bypassing register_device — used to set
    up a gap scenario (e.g. -d1, -d2, -d4) for the MAX-suffix generation test.
    """
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices (device_id, transformer_id, device_code) "
                f"VALUES (:device_id, :transformer_id, :device_code)"
            ),
            {"device_id": device_id, "transformer_id": transformer_id, "device_code": device_code},
        )


class TestDeviceRegistrationPersistence:
    # register_device()/update_device_metadata() are database-backed (DB-4);
    # run against the isolated test schema (tests/conftest.py), never the
    # real plant_monitoring.devices table.
    pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

    def setup_method(self):
        with session_scope() as session:
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.devices"))
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.transformers"))
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.plants"))
        _seed_transformer("test-p1-t1")
        _seed_transformer("test-p1-t2")

    def test_valid_registration_persists(self):
        device = register_device("test-p1-t1", "29101")
        assert device.device_code == "29101"
        fetched = repo.get_device(device.device_id)
        assert fetched is not None
        assert fetched.device_code == "29101"

    def test_registration_survives_a_separate_process(self, isolated_schema):
        device = register_device("test-p1-t1", "29102")
        env = dict(os.environ)
        env["PLANT_MONITORING_SCHEMA"] = isolated_schema
        result = subprocess.run(
            [sys.executable, "-c",
             "from repositories import plant_monitoring_repository as repo; "
             f"d = repo.get_device('{device.device_id}'); "
             "print(d.device_code if d else 'MISSING')"],
            cwd=os.getcwd(), env=env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "29102"

    def test_empty_transformer_id_fails_safely(self):
        with pytest.raises(RegistrationError):
            register_device("", "29103")

    def test_nonexistent_transformer_fails_safely(self):
        with pytest.raises(RegistrationError):
            register_device("does-not-exist", "29104")

    def test_duplicate_device_code_in_same_transformer_fails(self):
        register_device("test-p1-t1", "29105")
        with pytest.raises(RegistrationError):
            register_device("test-p1-t1", "29105")

    def test_same_device_code_in_different_transformers_succeeds(self):
        d1 = register_device("test-p1-t1", "29106")
        d2 = register_device("test-p1-t2", "29106")
        assert d1.device_id != d2.device_id
        assert d1.device_code == d2.device_code == "29106"

    def test_generated_device_id_follows_transformer_dn_pattern(self):
        device = register_device("test-p1-t1", "29107")
        assert device.device_id == "test-p1-t1-d1"

    def test_generation_uses_max_suffix_not_count(self):
        # Simulate a gap: -d1, -d2, -d4 exist (e.g. -d3 was deleted).
        _insert_raw_device("test-p1-t1-d1", "test-p1-t1", "10001")
        _insert_raw_device("test-p1-t1-d2", "test-p1-t1", "10002")
        _insert_raw_device("test-p1-t1-d4", "test-p1-t1", "10004")

        device = register_device("test-p1-t1", "10005")

        # COUNT+1 would compute 3+1=4, colliding with the existing -d4.
        assert device.device_id == "test-p1-t1-d5"

    def test_new_device_has_null_operational_metadata(self):
        device = register_device("test-p1-t1", "29108")
        assert device.msisdn is None
        assert device.hardware_version is None
        assert device.firmware_version is None
        assert device.installed_at is None

    def test_update_device_metadata_persists_all_four_fields(self):
        device = register_device("test-p1-t1", "29109")
        installed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        updated = update_device_metadata(
            device.device_id,
            msisdn="+15550000",
            hardware_version="hw-1",
            firmware_version="fw-1",
            installed_at=installed,
        )
        assert updated.msisdn == "+15550000"
        assert updated.hardware_version == "hw-1"
        assert updated.firmware_version == "fw-1"
        assert updated.installed_at == installed

    def test_partial_metadata_update_preserves_other_fields(self):
        device = register_device("test-p1-t1", "29116")
        installed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        update_device_metadata(
            device.device_id,
            msisdn="+27821234567",
            hardware_version="HW-2",
            firmware_version="1.4.3",
            installed_at=installed,
        )

        # Omit everything except firmware_version — an omitted argument
        # must leave that column unchanged, not NULL it out.
        updated = update_device_metadata(device.device_id, firmware_version="1.4.4")

        assert updated.firmware_version == "1.4.4"
        assert updated.msisdn == "+27821234567"
        assert updated.hardware_version == "HW-2"
        assert updated.installed_at == installed

    def test_update_device_metadata_missing_device_returns_none(self):
        assert update_device_metadata("does-not-exist", firmware_version="1.0.0") is None

    def test_created_at_is_database_generated(self):
        device = register_device("test-p1-t1", "29110")
        assert device.created_at is not None

    def test_updated_at_changes_on_metadata_update(self):
        device = register_device("test-p1-t1", "29111")
        assert device.updated_at is not None
        updated = update_device_metadata(device.device_id, msisdn="+15551111")
        assert updated.updated_at > device.updated_at

    def test_newly_registered_active_device_appears_in_admin_devices(self):
        from services import hierarchy_service
        device = register_device("test-p1-t1", "29112", "active")
        all_devices = hierarchy_service.list_all_devices()
        assert any(d.device_id == device.device_id for d in all_devices)

    def test_new_device_with_no_readings_has_no_fake_readings(self):
        device = register_device("test-p1-t1", "29113")
        readings = repo.get_latest_readings_for_device(device.device_id)
        assert readings == {}

    def test_inactive_registration_excluded_by_default_listing(self):
        from services import hierarchy_service
        device = register_device("test-p1-t1", "29114", "inactive")
        all_devices = hierarchy_service.list_all_devices()
        assert not any(d.device_id == device.device_id for d in all_devices)
        # Still reachable directly, matching existing inactive-equipment behavior.
        all_including_inactive = hierarchy_service.list_all_devices(include_inactive=True)
        assert any(d.device_id == device.device_id for d in all_including_inactive)

    def test_no_readings_rows_created_during_registration(self):
        with session_scope() as session:
            before = session.execute(
                text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.readings")
            ).scalar_one()
        register_device("test-p1-t1", "29115")
        with session_scope() as session:
            after = session.execute(
                text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.readings")
            ).scalar_one()
        assert after == before


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_ids(component) -> list[str]:
    """Recursively collect all component IDs from a Dash layout."""
    ids = []
    if hasattr(component, "id") and component.id:
        ids.append(component.id)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                ids.extend(_collect_ids(child))
        elif children is not None:
            ids.extend(_collect_ids(children))
    return ids
