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
    _option_label,
    _plant_options,
    _success_actions,
    _transformer_options,
    _validate_code,
    _validate_form,
    _review_summary,
)
from pages.device_register import layout, summary_body as _summary_body
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.device_registration import (
    RegistrationError,
    device_code_problem,
    register_device,
    update_device_metadata,
)
from services.rtl_uid import UID_FORMAT_MESSAGE, UID_REQUIRED_MESSAGE, uid_format_error
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
        errors = _validate_form("290171", "plant-1", "tx-1")
        assert "code" in errors

    def test_code_too_short_fails(self):
        errors = _validate_form("2901", "plant-1", "tx-1")
        assert "code" in errors

    def test_non_numeric_code_fails(self):
        errors = _validate_form("AB-12", "plant-1", "tx-1")
        assert "code" in errors

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
        """Nothing typed yet: neutral guidance, not an error."""
        assert _code_field_guidance("") == "Required · 5 digits, e.g. 29017."
        assert _code_field_guidance(None) == "Required · 5 digits, e.g. 29017."

    def test_whitespace_only_is_invalid_guidance_matching_review(self):
        guidance = _code_field_guidance("   ")
        assert guidance == _validate_code("   ") == UID_REQUIRED_MESSAGE

    def test_valid_value_is_positive_guidance(self):
        """Claims only "passes the format", never that the device is
        confirmed or registered: no database is consulted while typing."""
        guidance = _code_field_guidance("29017")
        assert guidance == "Meets the device code format (5 digits)."
        assert "confirmed" not in guidance.lower()
        assert "registered" not in guidance.lower()

    @pytest.mark.parametrize("value", ["2901", "290171", "AB-12", "A" * 10])
    def test_invalid_value_matches_review(self, value):
        """The live hint and Review say the identical thing for the same input."""
        assert _code_field_guidance(value) == _validate_code(value) == UID_FORMAT_MESSAGE


class TestReviewEnforcesTheSharedUidRule:
    """ADR-022 reverses the old "no 5-digit rule at registration" contract:
    registration now uses the same rule as RTL programming."""

    def test_validate_code_is_the_shared_rule(self):
        for value in (None, "", "  ", "29017", "2901", "AB-12", "290171"):
            assert _validate_code(value) == uid_format_error(value)

    def test_blank_still_rejected(self):
        errors = _validate_form("", "plant-1", "tx-1")
        assert errors["code"] == UID_REQUIRED_MESSAGE


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
        assert node.children == _code_field_guidance(None)

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
# REGISTER-UX-1 — layout, live summary, duplicate refusal, success actions
# ---------------------------------------------------------------------------

def _parent_of(root, target_id):
    """The component whose direct children include the node with target_id."""
    children = getattr(root, "children", None)
    if children is None or isinstance(children, str):
        return None
    kids = children if isinstance(children, list) else [children]
    for kid in kids:
        if getattr(kid, "id", None) == target_id:
            return root
        found = _parent_of(kid, target_id)
        if found is not None:
            return found
    return None


class TestCodeInputLayout:
    def test_input_is_not_browser_required(self):
        """Dash styles `input.dash-input:invalid` with a red outline, so an
        empty browser-`required` input is drawn as an error on first load.
        The page validates the field itself; the asterisk stays."""
        node = find_by_id(layout(), "device-register-code")
        assert not getattr(node, "required", None)

    def test_input_is_five_digit_numeric(self):
        node = find_by_id(layout(), "device-register-code")
        assert node.maxLength == 5
        assert node.inputMode == "numeric"
        assert node.placeholder == "e.g. 29017"

    def test_hint_sits_directly_under_the_input_inside_its_field(self):
        """The hint used to follow the whole field, so it sat against the
        next field's label and read as that field's help."""
        lay = layout()
        field_node = _parent_of(lay, "device-register-code-hint")
        kids = field_node.children
        ids = [getattr(k, "id", None) for k in kids]
        assert ids.index("device-register-code-hint") == ids.index("device-register-code") + 1
        assert "device-register-code-error" in ids


class TestSummaryCard:
    def test_layout_has_summary_card_beside_the_form(self):
        lay = layout()
        ids = _collect_ids(lay)
        assert "device-register-summary" in ids
        assert "device-register-summary-body" in ids
        columns = _parent_of(lay, "device-register-summary")
        assert "device-register-layout" in columns.className

    def test_summary_names_what_happens_next(self):
        text = str(find_by_id(layout(), "device-register-summary"))
        assert "What happens next" in text
        assert "unassigned" in text

    def test_empty_summary_uses_placeholders(self):
        text = str(_summary_body(None, None, None, "active"))
        assert "Not entered" in text
        assert "Not selected" in text
        assert "Active" in text

    def test_filled_summary_shows_values(self):
        text = str(_summary_body("29017", "Plant A", "T1", "inactive"))
        for expected in ("29017", "Plant A", "T1", "Inactive"):
            assert expected in text

    def test_option_label_resolves_from_options_on_screen(self):
        options = [{"label": "Plant A", "value": "p-a"}, {"label": "Plant B", "value": "p-b"}]
        assert _option_label(options, "p-b") == "Plant B"
        assert _option_label(options, "missing") is None
        assert _option_label(None, "p-a") is None
        assert _option_label(options, None) is None

    def test_live_summary_callback_makes_no_privileged_read(self):
        """It only echoes what the operator already has on screen."""
        import inspect

        app = _CapturingApp()
        device_register.register(app)
        source = inspect.getsource(app.functions["_live_summary"])
        assert "hierarchy_service" not in source
        assert "device_code_problem" not in source


class TestSuccessActions:
    def test_success_actions_link_to_assign_and_device(self):
        from routes import device_assign_href, device_href

        actions = _success_actions("p1-t1-d9")
        hrefs = [getattr(a, "href", None) for a in actions.children]
        assert device_assign_href("p1-t1-d9") in hrefs
        assert device_href("p1-t1-d9") in hrefs
        text = str(actions)
        assert "Assign a technician" in text
        assert "Open the device" in text

    def test_layout_has_register_another_and_back(self):
        lay = layout()
        another = find_by_id(lay, "device-register-another-btn")
        assert another is not None
        assert "Register another" in str(another.children)
        success_text = str(find_by_id(lay, "device-register-success"))
        assert "Back to Device Management" in success_text
        assert find_by_id(lay, "device-register-success-actions") is not None

    def test_register_another_clears_code_and_keeps_placement(self):
        app = _CapturingApp()
        device_register.register(app)
        out = app.functions["_register_another"](1)
        (code, code_error, form_style, review_style, success_style,
         success_detail, success_actions, error_style) = out
        assert code == ""
        assert code_error == ""
        assert form_style == {"display": "block"}
        assert review_style == {"display": "none"}
        assert success_style == {"display": "none"}
        assert success_detail == [] and success_actions == []
        assert error_style == {"display": "none"}

    def test_register_another_ignores_zero_clicks(self):
        from dash import no_update

        app = _CapturingApp()
        device_register.register(app)
        out = app.functions["_register_another"](0)
        assert all(v is no_update for v in out)


class TestReviewRefusesTakenCode:
    """Review consults the service for fleet-wide duplicates (ADR-022)."""

    def _review(self, monkeypatch, problem):
        from types import SimpleNamespace

        monkeypatch.setattr(device_register, "current_identity", lambda: SimpleNamespace(user_id=1))
        monkeypatch.setattr(device_register, "require_capability", lambda *a, **k: None)
        monkeypatch.setattr(device_register, "device_code_problem", lambda code: problem)
        monkeypatch.setattr(
            device_register.hierarchy_service, "list_plants",
            lambda scope: [SimpleNamespace(plant_id="p1", name="Plant A")],
        )
        monkeypatch.setattr(
            device_register.hierarchy_service, "list_transformers",
            lambda plant_id, scope: [SimpleNamespace(transformer_id="t1", transformer_code="T1")],
        )
        app = _CapturingApp()
        device_register.register(app)
        return app.functions["_show_review"](1, "29017", "p1", "t1", "active")

    def test_taken_code_stays_on_the_form_with_the_message(self, monkeypatch):
        from dash import no_update

        message = "Device code 29017 is already registered at Plant B, transformer T2."
        out = self._review(monkeypatch, message)
        assert out[0] == message
        assert out[3] is no_update   # form stays visible
        assert out[4] is no_update   # review stays hidden

    def test_free_code_moves_to_review(self, monkeypatch):
        out = self._review(monkeypatch, None)
        assert out[0] == ""
        assert out[3] == {"display": "none"}
        assert out[4] == {"display": "block"}

    def test_lookup_failure_is_a_safe_message(self, monkeypatch):
        def boom(code):
            raise RuntimeError("connection refused on 10.0.0.5")

        from types import SimpleNamespace
        monkeypatch.setattr(device_register, "current_identity", lambda: SimpleNamespace(user_id=1))
        monkeypatch.setattr(device_register, "require_capability", lambda *a, **k: None)
        monkeypatch.setattr(device_register, "device_code_problem", boom)
        app = _CapturingApp()
        device_register.register(app)
        out = app.functions["_show_review"](1, "29017", "p1", "t1", "active")
        assert "could not be checked" in out[0]
        assert "10.0.0.5" not in out[0]


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

    def test_same_device_code_in_different_transformers_is_refused(self):
        """ADR-022: a UID is unique across the fleet, enforced in the
        application (the schema still only guarantees per-transformer)."""
        register_device("test-p1-t1", "29106", actor_user_id=self.admin_id)
        with pytest.raises(RegistrationError) as exc:
            register_device("test-p1-t2", "29106", actor_user_id=self.admin_id)
        assert str(exc.value) == (
            "Device code 29106 is already registered at Test Plant, "
            "transformer test-p1-t1."
        )
        assert repo.find_device_ids_by_code("29106") == ["test-p1-t1-d1"]

    @pytest.mark.parametrize("code", ["AB-12", "2901", "290171"])
    def test_service_refuses_a_non_five_digit_code(self, code):
        """The callback's check is not the only one: a direct call is refused too."""
        with pytest.raises(RegistrationError) as exc:
            register_device("test-p1-t1", code, actor_user_id=self.admin_id)
        assert str(exc.value) == UID_FORMAT_MESSAGE
        assert repo.find_device_ids_by_code(code) == []

    def test_service_trims_the_code_before_storing(self):
        device = register_device("test-p1-t1", " 29117 ", actor_user_id=self.admin_id)
        assert device.device_code == "29117"

    def test_refused_registration_writes_no_audit_row(self):
        register_device("test-p1-t1", "29118", actor_user_id=self.admin_id)
        with session_scope() as session:
            before = session.execute(
                text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.audit_log")
            ).scalar_one()
        with pytest.raises(RegistrationError):
            register_device("test-p1-t2", "29118", actor_user_id=self.admin_id)
        with session_scope() as session:
            after = session.execute(
                text(f"SELECT COUNT(*) FROM {repo._SCHEMA}.audit_log")
            ).scalar_one()
        assert after == before

    def test_device_code_problem_is_none_for_a_free_code(self):
        assert device_code_problem("29119") is None

    def test_device_code_problem_names_where_a_taken_code_lives(self):
        register_device("test-p1-t2", "29120", actor_user_id=self.admin_id)
        assert device_code_problem(" 29120 ") == (
            "Device code 29120 is already registered at Test Plant, "
            "transformer test-p1-t2."
        )

    def test_device_code_problem_reports_format_before_querying(self):
        assert device_code_problem("AB-12") == UID_FORMAT_MESSAGE

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
