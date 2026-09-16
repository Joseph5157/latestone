"""Tests for device registration â€” layout, validation, review, persistence.

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

from callbacks import device_register
from callbacks.device_register import (
    _code_field_guidance,
    _plant_options,
    _transformer_options,
    _validate_code,
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
from tests.dash_tree import find_by_id


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
# MOBBIN-UX-6 — live inline device code guidance, before Review.
#
# One rule (_validate_code), two presentations: _validate_form (Review-time,
# authoritative) and _code_field_guidance (live, before Review). Every
# "invalid" guidance string below is asserted equal to what _validate_code
# itself returns, so the two literally cannot drift.
# ---------------------------------------------------------------------------

class TestCodeFieldGuidance:
    def test_empty_value_is_neutral_initial_guidance(self):
        """1. Initial (nothing typed) state is neutral, not an error."""
        assert _code_field_guidance("") == "Required · maximum 10 characters."
        assert _code_field_guidance(None) == "Required · maximum 10 characters."

    def test_whitespace_only_is_invalid_guidance_matching_review(self):
        """2. Whitespace-only entered -> invalid guidance, identical to
        what Review would show for the same input."""
        guidance = _code_field_guidance("   ")
        assert guidance == _validate_code("   ") == "Device code is required."

    def test_valid_current_rule_value_is_positive_guidance(self):
        """3. A nonblank value within the current length rule -> positive
        guidance that claims only "passes this field's rule right now",
        never that the device is confirmed or registered."""
        guidance = _code_field_guidance("29017")
        assert guidance == "Meets the device code format (10 characters or fewer)."
        assert "confirmed" not in guidance.lower()
        assert "registered" not in guidance.lower()

    def test_over_length_value_is_invalid_guidance_matching_review(self):
        """6. Max-length behaviour is unchanged; the live hint says the
        identical thing Review would for the same over-length input."""
        guidance = _code_field_guidance("a" * 11)
        assert guidance == _validate_code("a" * 11) == (
            "Device code must be 10 characters or fewer."
        )

    def test_exactly_ten_characters_is_positive_guidance(self):
        """6 (cont'd). The boundary itself is unchanged: 10 passes, 11 fails."""
        assert _validate_code("a" * 10) is None
        assert "10 characters or fewer" in _code_field_guidance("a" * 10)


class TestReviewAcceptsCurrentContractIdentifiers:
    """No 5-digit-only, numeric-only, or pattern rule exists. Proven
    directly so a future edit cannot silently tighten the field beyond
    what this tranche's brief authorizes."""

    @pytest.mark.parametrize("code", [
        "29017",   # the reserved numeric identifier form
        "AB-12c",  # non-numeric, non-5-digit
        "rtl_9",   # short, mixed case, underscore
        "A" * 10,  # exactly at the length limit, all letters
    ])
    def test_non_numeric_and_non_five_digit_codes_pass(self, code):
        """5. Review still accepts identifiers the current contract
        allows, beyond the reserved 5-digit numeric example."""
        errors = _validate_form(code, "plant-1", "tx-1")
        assert "code" not in errors

    def test_blank_still_rejected(self):
        """4. Review validation still rejects a blank code."""
        errors = _validate_form("", "plant-1", "tx-1")
        assert errors["code"] == "Device code is required."

    def test_whitespace_only_still_rejected(self):
        """4 (cont'd). ...and a whitespace-only code."""
        errors = _validate_form("   ", "plant-1", "tx-1")
        assert errors["code"] == "Device code is required."

    def test_eleven_characters_still_rejected(self):
        errors = _validate_form("a" * 11, "plant-1", "tx-1")
        assert errors["code"] == "Device code must be 10 characters or fewer."


class _CapturingApp:
    def __init__(self):
        self.functions = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            return fn

        return decorator


class TestCodeHintLayoutAndWiring:
    def test_layout_has_hint_slot_with_neutral_initial_text(self):
        lay = layout()
        node = find_by_id(lay, "device-register-code-hint")
        assert node is not None
        rendered = str(node.children)
        assert "Required" in rendered
        assert "10 characters" in rendered

    def test_hint_slot_is_a_separate_output_from_the_alert_error_slot(self):
        """Prefer a separate guidance slot rather than a second writer for
        device-register-code-error (MOBBIN-UX-6) — the existing
        role="alert" Review-time error is untouched."""
        lay = layout()
        hint = find_by_id(lay, "device-register-code-hint")
        error = find_by_id(lay, "device-register-code-error")
        assert hint is not error
        assert getattr(error, "role", None) == "alert"
        assert getattr(hint, "role", None) != "alert"

    def test_form_review_success_structure_is_unchanged(self):
        """7. Form -> Review -> Success structure unchanged."""
        lay = layout()
        ids = _collect_ids(lay)
        for expected in (
            "device-register-form", "device-register-review",
            "device-register-success", "device-register-review-btn",
            "device-register-submit-btn", "device-register-edit-btn",
            "device-register-code-hint",
        ):
            assert expected in ids

    def test_code_hint_callback_makes_no_privileged_read(self):
        """8. Authorization untouched: the new callback is a pure function
        of the value the caller already typed — no service call, no
        current_identity/require_capability, since it discloses nothing an
        unauthorized caller could not already see on their own screen."""
        import inspect

        app = _CapturingApp()
        device_register.register(app)
        source = inspect.getsource(app.functions["_code_hint"])
        assert "require_capability" not in source
        assert "current_identity" not in source
        assert "hierarchy_service" not in source

    def test_existing_registration_callbacks_still_require_capability(self):
        """8 (cont'd). The pre-existing REGISTER_DEVICE-gated callbacks
        (AUTH-HARDEN-1R) are registered exactly as before."""
        import inspect

        app = _CapturingApp()
        device_register.register(app)
        for name in (
            "_populate_plants", "_populate_transformers",
            "_show_review", "_submit_registration",
        ):
            source = inspect.getsource(app.functions[name])
            assert "require_capability" in source


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
    """Insert a device row directly, bypassing register_device â€” used to set
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
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.audit_log"))
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.devices"))
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.transformers"))
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.plants"))
        _seed_transformer("test-p1-t1")
        _seed_transformer("test-p1-t2")
        # AUD-1: register_device requires an authenticated actor; create one
        # at the repository level (no audit row) and attribute writes to it.
        self.admin_id = repo.create_or_update_user(
            username="register-admin",
            full_name="register-admin",
            role="administrator",
            status="active",
        ).user_id

    def test_valid_registration_persists(self):
        device = register_device("test-p1-t1", "29101", actor_user_id=self.admin_id)
        assert device.device_code == "29101"
        fetched = repo.get_device(device.device_id)
        assert fetched is not None
        assert fetched.device_code == "29101"

    def test_registration_survives_a_separate_process(self, isolated_schema):
        device = register_device("test-p1-t1", "29102", actor_user_id=self.admin_id)
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
            register_device("", "29103", actor_user_id=self.admin_id)

    def test_nonexistent_transformer_fails_safely(self):
        with pytest.raises(RegistrationError):
            register_device("does-not-exist", "29104", actor_user_id=self.admin_id)

    def test_duplicate_device_code_in_same_transformer_fails(self):
        register_device("test-p1-t1", "29105", actor_user_id=self.admin_id)
        with pytest.raises(RegistrationError):
            register_device("test-p1-t1", "29105", actor_user_id=self.admin_id)

    def test_same_device_code_in_different_transformers_succeeds(self):
        d1 = register_device("test-p1-t1", "29106", actor_user_id=self.admin_id)
        d2 = register_device("test-p1-t2", "29106", actor_user_id=self.admin_id)
        assert d1.device_id != d2.device_id
        assert d1.device_code == d2.device_code == "29106"

    def test_generated_device_id_follows_transformer_dn_pattern(self):
        device = register_device("test-p1-t1", "29107", actor_user_id=self.admin_id)
        assert device.device_id == "test-p1-t1-d1"

    def test_generation_uses_max_suffix_not_count(self):
        # Simulate a gap: -d1, -d2, -d4 exist (e.g. -d3 was deleted).
        _insert_raw_device("test-p1-t1-d1", "test-p1-t1", "10001")
        _insert_raw_device("test-p1-t1-d2", "test-p1-t1", "10002")
        _insert_raw_device("test-p1-t1-d4", "test-p1-t1", "10004")

        device = register_device("test-p1-t1", "10005", actor_user_id=self.admin_id)

        # COUNT+1 would compute 3+1=4, colliding with the existing -d4.
        assert device.device_id == "test-p1-t1-d5"

    def test_new_device_has_null_operational_metadata(self):
        device = register_device("test-p1-t1", "29108", actor_user_id=self.admin_id)
        assert device.msisdn is None
        assert device.hardware_version is None
        assert device.firmware_version is None
        assert device.installed_at is None

    def test_update_device_metadata_persists_all_four_fields(self):
        device = register_device("test-p1-t1", "29109", actor_user_id=self.admin_id)
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
        device = register_device("test-p1-t1", "29116", actor_user_id=self.admin_id)
        installed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        update_device_metadata(
            device.device_id,
            msisdn="+27821234567",
            hardware_version="HW-2",
            firmware_version="1.4.3",
            installed_at=installed,
        )

        # Omit everything except firmware_version â€” an omitted argument
        # must leave that column unchanged, not NULL it out.
        updated = update_device_metadata(device.device_id, firmware_version="1.4.4")

        assert updated.firmware_version == "1.4.4"
        assert updated.msisdn == "+27821234567"
        assert updated.hardware_version == "HW-2"
        assert updated.installed_at == installed

    def test_update_device_metadata_missing_device_returns_none(self):
        assert update_device_metadata("does-not-exist", firmware_version="1.0.0") is None

    def test_created_at_is_database_generated(self):
        device = register_device("test-p1-t1", "29110", actor_user_id=self.admin_id)
        assert device.created_at is not None

    def test_updated_at_changes_on_metadata_update(self):
        device = register_device("test-p1-t1", "29111", actor_user_id=self.admin_id)
        assert device.updated_at is not None
        updated = update_device_metadata(device.device_id, msisdn="+15551111")
        assert updated.updated_at > device.updated_at

    def test_newly_registered_active_device_appears_in_admin_devices(self):
        from services import hierarchy_service
        device = register_device("test-p1-t1", "29112", "active", actor_user_id=self.admin_id)
        all_devices = hierarchy_service.list_all_devices()
        assert any(d.device_id == device.device_id for d in all_devices)

    def test_new_device_with_no_readings_has_no_fake_readings(self):
        device = register_device("test-p1-t1", "29113", actor_user_id=self.admin_id)
        readings = repo.get_latest_readings_for_device(device.device_id)
        assert readings == {}

    def test_inactive_registration_excluded_by_default_listing(self):
        from services import hierarchy_service
        device = register_device("test-p1-t1", "29114", "inactive", actor_user_id=self.admin_id)
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
        register_device("test-p1-t1", "29115", actor_user_id=self.admin_id)
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
