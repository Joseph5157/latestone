"""THRESH-CONFIG-1 tests — C-01 global temperature threshold configuration
(framework only).

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1), pending
client confirmation. Pure classes cover parsing/validation without a
database. Database-backed suites run against the module-scoped
isolated_schema (tests/conftest.py), never the real plant_monitoring
tables — mirrors tests/test_forwarding_auto_disable.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import temperature_threshold_service as service

NAN = float("nan")
INF = float("inf")


# ---------------------------------------------------------------------------
# Pure — parsing and validation, no database
# ---------------------------------------------------------------------------


class TestParseTemperature:
    def test_valid_numbers_parse(self):
        assert service.parse_temperature("60", field_label="Warning") == Decimal("60.000")
        assert service.parse_temperature(" 60.5 ", field_label="Warning") == Decimal("60.500")
        assert service.parse_temperature("-10", field_label="Warning") == Decimal("-10.000")
        assert service.parse_temperature("0", field_label="Warning") == Decimal("0.000")

    def test_returns_a_decimal_not_a_float(self):
        """The correctness fix: this must never be a binary float — see
        the module docstring's CANONICAL DECIMAL SEMANTICS section."""
        assert isinstance(service.parse_temperature("60", field_label="Warning"), Decimal)

    @pytest.mark.parametrize("bad", ["", None, "   ", "abc", "60C", "60,5"])
    def test_malformed_input_rejected(self, bad):
        with pytest.raises(service.ThresholdConfigError):
            service.parse_temperature(bad, field_label="Warning")

    @pytest.mark.parametrize("bad", ["inf", "-inf", "Infinity", "nan", "NaN"])
    def test_non_finite_strings_rejected(self, bad):
        """float() alone accepts these without raising — the exact
        malformed-input class a temperature threshold must never silently
        accept."""
        with pytest.raises(service.ThresholdConfigError):
            service.parse_temperature(bad, field_label="Warning")

    def test_error_names_the_field(self):
        with pytest.raises(service.ThresholdConfigError, match="Critical"):
            service.parse_temperature("", field_label="Critical")


class TestSetThresholdConfigValidation:
    """Validation happens in `set_threshold_config` itself, independent of
    `parse_temperature` — a caller passing floats directly must still be
    checked."""

    def test_requires_authenticated_actor(self):
        with pytest.raises(service.ThresholdConfigError):
            service.set_threshold_config(warning_c=60.0, critical_c=75.0, actor_user_id=None)
        with pytest.raises(service.ThresholdConfigError):
            service.set_threshold_config(warning_c=60.0, critical_c=75.0, actor_user_id=True)

    @pytest.mark.parametrize("bad", [NAN, INF, -INF])
    def test_non_finite_warning_rejected(self, bad):
        with pytest.raises(service.ThresholdConfigError):
            service.set_threshold_config(warning_c=bad, critical_c=75.0, actor_user_id=1)

    @pytest.mark.parametrize("bad", [NAN, INF, -INF])
    def test_non_finite_critical_rejected(self, bad):
        with pytest.raises(service.ThresholdConfigError):
            service.set_threshold_config(warning_c=60.0, critical_c=bad, actor_user_id=1)

    def test_warning_must_be_strictly_below_critical(self):
        with pytest.raises(service.ThresholdConfigError):
            service.set_threshold_config(warning_c=75.0, critical_c=60.0, actor_user_id=1)
        with pytest.raises(service.ThresholdConfigError):
            service.set_threshold_config(warning_c=60.0, critical_c=60.0, actor_user_id=1)

    def test_no_arbitrary_range_is_enforced(self, monkeypatch):
        """C-01 gives no numeric bounds — extreme-but-finite, correctly
        ordered values must not be rejected by this layer. (The repository
        call is monkeypatched out so this stays a pure validation test.)"""
        captured = {}

        def fake_set(**kwargs):
            captured.update(kwargs)
            return repo.ThresholdConfigChange(
                previous=None,
                current=repo.TemperatureThresholdConfigRecord(
                    warning_c=kwargs["warning_c"], critical_c=kwargs["critical_c"],
                    configured_by_user_id=kwargs["configured_by_user_id"],
                    configured_at=datetime.now(timezone.utc),
                ),
                changed=True,
            )

        monkeypatch.setattr(repo, "set_temperature_threshold_config", fake_set)
        monkeypatch.setattr(
            "services.temperature_threshold_service.audit_service.record",
            lambda *a, **k: None,
        )
        service.set_threshold_config(warning_c=-273.0, critical_c=10000.0, actor_user_id=1)
        assert captured["warning_c"] == -273.0
        assert captured["critical_c"] == 10000.0


class TestExcessPrecisionIsRejectedNotRounded:
    """Correctness fix: migration 011 stores NUMERIC(12,3). A value with
    more than 3 decimal places must be REFUSED, never silently rounded —
    and the two values from the reported example must never both be
    accepted only to collapse together once persisted."""

    def test_four_decimal_places_is_rejected(self):
        with pytest.raises(service.ThresholdConfigError, match="3 decimal places"):
            service.parse_temperature("20.0004", field_label="Warning")

    def test_the_reported_collapsing_pair_is_rejected_before_comparison(self):
        """20.0004 and 20.0005 both round to (or straddle) the same
        NUMERIC(12,3) value — `warning_c < critical_c` on the raw floats
        would pass, then silently stop meaning anything once stored. Both
        must be refused at the door, never reach that comparison."""
        with pytest.raises(service.ThresholdConfigError, match="3 decimal places"):
            service.parse_temperature("20.0004", field_label="Warning")
        with pytest.raises(service.ThresholdConfigError, match="3 decimal places"):
            service.parse_temperature("20.0005", field_label="Critical")
        # And set_threshold_config itself refuses the pair outright too,
        # independent of parse_temperature:
        with pytest.raises(service.ThresholdConfigError):
            service.set_threshold_config(
                warning_c="20.0004", critical_c="20.0005", actor_user_id=1,
            )

    def test_exactly_three_decimal_places_is_accepted(self):
        assert service.parse_temperature("60.123", field_label="Warning") == Decimal("60.123")

    def test_fewer_than_three_decimal_places_is_padded_not_rejected(self):
        assert service.parse_temperature("60", field_label="Warning") == Decimal("60.000")
        assert service.parse_temperature("60.1", field_label="Warning") == Decimal("60.100")

    def test_excess_precision_from_a_float_argument_is_also_rejected(self):
        """A caller skipping `parse_temperature` and passing a float
        directly gets the same protection — `set_threshold_config` is the
        single trusted entry point, not the string parser."""
        with pytest.raises(service.ThresholdConfigError, match="3 decimal places"):
            service.set_threshold_config(
                warning_c=20.0004, critical_c=30.0, actor_user_id=1,
            )


class TestVocabulary:
    def test_operations_fit_column_limit(self):
        assert len(audit_cfg.TEMPERATURE_THRESHOLD_SET) <= 50
        assert len(audit_cfg.TEMPERATURE_THRESHOLD_CLEARED) <= 50

    def test_entity_is_stable_and_global(self):
        assert audit_cfg.ENTITY_TEMPERATURE_THRESHOLD == "temperature_threshold"
        assert audit_cfg.TEMPERATURE_THRESHOLD_ENTITY_ID == "global"

    def test_not_a_system_operation(self):
        """No scheduler, no automatic evaluation exists for this feature —
        every change is human-originated."""
        assert audit_cfg.TEMPERATURE_THRESHOLD_SET not in audit_cfg.SYSTEM_OPERATIONS
        assert audit_cfg.TEMPERATURE_THRESHOLD_CLEARED not in audit_cfg.SYSTEM_OPERATIONS


# ---------------------------------------------------------------------------
# Database-backed — persistence, no-op semantics, audit, rollback
# ---------------------------------------------------------------------------


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "temperature_threshold_config",
            "user_device_assignments", "readings", "devices", "transformers",
            "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _audit_rows() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            text(
                f"SELECT operation, entity_type, entity_id, old_values, "
                f"new_values, user_id FROM {repo._SCHEMA}.audit_log "
                f"ORDER BY audit_id"
            )
        ).mappings().fetchall()
    return [dict(r) for r in rows]


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestThresholdConfigPersistence:
    def setup_method(self):
        _wipe()
        self.admin = repo.create_or_update_user(
            username="thresh-admin", full_name="Admin",
            role="administrator", status="active",
        ).user_id

    def test_starts_unconfigured(self):
        assert service.get_current_threshold_config() is None

    def test_set_persists_and_audits_human_actor(self):
        state = service.set_threshold_config(
            warning_c=60.0, critical_c=75.0, actor_user_id=self.admin,
        )
        assert state.warning_c == 60.0
        assert state.critical_c == 75.0
        assert state.configured_by_user_id == self.admin
        assert service.get_current_threshold_config().warning_c == 60.0

        rows = _audit_rows()
        assert len(rows) == 1
        assert rows[0]["operation"] == audit_cfg.TEMPERATURE_THRESHOLD_SET
        assert rows[0]["entity_type"] == audit_cfg.ENTITY_TEMPERATURE_THRESHOLD
        assert rows[0]["entity_id"] == audit_cfg.TEMPERATURE_THRESHOLD_ENTITY_ID
        assert rows[0]["user_id"] == self.admin
        assert rows[0]["old_values"] is None
        # The audit snapshot stores the canonical value as str(), not a
        # JSON number — see _snapshot()'s docstring (json.dumps has no
        # native Decimal support, and str() is what preserves exactness).
        assert rows[0]["new_values"]["warning_c"] == "60.000"
        assert rows[0]["new_values"]["critical_c"] == "75.000"

    def test_identical_re_save_is_a_silent_noop(self):
        first = service.set_threshold_config(
            warning_c=60.0, critical_c=75.0, actor_user_id=self.admin,
        )
        again = service.set_threshold_config(
            warning_c=60.0, critical_c=75.0, actor_user_id=self.admin,
        )
        assert again.configured_at == first.configured_at  # no churn
        assert [r["operation"] for r in _audit_rows()] == [
            audit_cfg.TEMPERATURE_THRESHOLD_SET,
        ]

    def test_differently_written_but_canonically_equal_resave_is_still_a_noop(self):
        """"60", "60.0" and "60.00" are different Python values on the way
        in but the SAME canonical Decimal (60.000) once normalized to this
        column's scale — the no-op check must compare that canonical form,
        not the caller's original spelling."""
        first = service.set_threshold_config(
            warning_c="60", critical_c="75", actor_user_id=self.admin,
        )
        again = service.set_threshold_config(
            warning_c="60.00", critical_c="75.0", actor_user_id=self.admin,
        )
        assert again.configured_at == first.configured_at
        assert [r["operation"] for r in _audit_rows()] == [
            audit_cfg.TEMPERATURE_THRESHOLD_SET,
        ]

    def test_exact_persisted_value_round_trips_through_the_database(self):
        """A value with real fractional precision must come back byte-for-
        byte identical after a genuine round trip through Postgres —
        proving the fix end-to-end, not just inside Python."""
        service.set_threshold_config(
            warning_c="60.125", critical_c="75.875", actor_user_id=self.admin,
        )
        read_back = service.get_current_threshold_config()
        assert read_back.warning_c == Decimal("60.125")
        assert read_back.critical_c == Decimal("75.875")
        # And directly at the repository/driver boundary, with no Python
        # rounding of any kind on either side of the round trip:
        record = repo.get_temperature_threshold_config()
        assert record.warning_c == Decimal("60.125")
        assert isinstance(record.warning_c, Decimal)

    def test_changing_warning_is_a_real_change_and_is_audited(self):
        service.set_threshold_config(warning_c=60.0, critical_c=75.0, actor_user_id=self.admin)
        service.set_threshold_config(warning_c=62.0, critical_c=75.0, actor_user_id=self.admin)

        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.TEMPERATURE_THRESHOLD_SET, audit_cfg.TEMPERATURE_THRESHOLD_SET,
        ]
        assert service.get_current_threshold_config().warning_c == 62.0
        last_row = _audit_rows()[1]
        assert last_row["old_values"]["warning_c"] == "60.000"
        assert last_row["new_values"]["warning_c"] == "62.000"

    def test_changing_critical_is_a_real_change_and_is_audited(self):
        service.set_threshold_config(warning_c=60.0, critical_c=75.0, actor_user_id=self.admin)
        service.set_threshold_config(warning_c=60.0, critical_c=80.0, actor_user_id=self.admin)

        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.TEMPERATURE_THRESHOLD_SET, audit_cfg.TEMPERATURE_THRESHOLD_SET,
        ]
        assert service.get_current_threshold_config().critical_c == 80.0

    def test_clear_is_a_noop_when_nothing_is_set(self):
        result = service.clear_threshold_config(actor_user_id=self.admin)
        assert result is None
        assert _audit_rows() == []

    def test_clear_removes_row_and_audits(self):
        service.set_threshold_config(warning_c=60.0, critical_c=75.0, actor_user_id=self.admin)
        cleared = service.clear_threshold_config(actor_user_id=self.admin)

        assert cleared.warning_c == 60.0
        assert service.get_current_threshold_config() is None

        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.TEMPERATURE_THRESHOLD_SET, audit_cfg.TEMPERATURE_THRESHOLD_CLEARED,
        ]
        cleared_row = _audit_rows()[1]
        assert cleared_row["new_values"] is None
        assert cleared_row["old_values"]["warning_c"] == "60.000"

    def test_clear_requires_authenticated_actor(self):
        service.set_threshold_config(warning_c=60.0, critical_c=75.0, actor_user_id=self.admin)
        with pytest.raises(service.ThresholdConfigError):
            service.clear_threshold_config(actor_user_id=None)
        # Refused before anything changed:
        assert service.get_current_threshold_config() is not None

    def test_failed_audit_rolls_back_the_set(self, monkeypatch):
        def explode(**_kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        with pytest.raises(service.ThresholdConfigError):
            service.set_threshold_config(
                warning_c=60.0, critical_c=75.0, actor_user_id=self.admin,
            )
        assert repo.get_temperature_threshold_config() is None

    def test_failed_audit_rolls_back_the_clear(self, monkeypatch):
        service.set_threshold_config(warning_c=60.0, critical_c=75.0, actor_user_id=self.admin)

        def explode(**_kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        with pytest.raises(service.ThresholdConfigError):
            service.clear_threshold_config(actor_user_id=self.admin)

        # The delete must not have survived without its audit row.
        assert repo.get_temperature_threshold_config() is not None

    def test_database_check_fires_even_bypassing_the_service_validation(self):
        """Defense-in-depth: the repository performs no relational
        validation of its own (its own docstring says so) — a caller that
        reaches the repository directly, skipping
        `set_threshold_config`'s canonicalization and ordering check
        entirely, must still be stopped by the database's own CHECK."""
        with pytest.raises(IntegrityError):
            repo.set_temperature_threshold_config(
                warning_c=Decimal("90.000"),
                critical_c=Decimal("10.000"),
                configured_by_user_id=self.admin,
            )
