"""FRESHNESS-CONFIG-1 — Administrator-configurable global freshness threshold.

Pure classes cover parsing, validation and live resolution without a
database. Database-backed suites run against the module-scoped
isolated_schema (tests/conftest.py), never the real plant_monitoring tables.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import freshness_threshold_service as service
from services.monitoring_service import Freshness, evaluate_freshness

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Pure — parsing and validation
# ---------------------------------------------------------------------------


class TestParseMinutes:
    @pytest.mark.parametrize("raw, expected", [
        ("720", 720), (" 1440 ", 1440), ("5", 5), ("525600", 525600), (60, 60),
    ])
    def test_whole_minutes_parse(self, raw, expected):
        assert service.parse_minutes(raw) == expected

    @pytest.mark.parametrize("bad", ["", None, "   ", "abc", "12.5", "-60", "+60", "1e3", "٣٠"])
    def test_non_whole_or_malformed_input_rejected(self, bad):
        with pytest.raises(service.FreshnessThresholdError):
            service.parse_minutes(bad)

    @pytest.mark.parametrize("out_of_range", ["0", "1", "4", "525601", "99999999"])
    def test_typo_guards_reject_values_outside_the_range(self, out_of_range):
        with pytest.raises(service.FreshnessThresholdError, match="between 5 minutes"):
            service.parse_minutes(out_of_range)


class TestSetConfigValidation:
    """`set_config` validates independently of `parse_minutes`."""

    @pytest.mark.parametrize("actor", [None, True, "7"])
    def test_requires_authenticated_actor(self, actor):
        with pytest.raises(service.FreshnessThresholdError):
            service.set_config(stale_after_minutes=720, actor_user_id=actor)

    @pytest.mark.parametrize("bad", [0, 4, 525601, 12.5, "720", True, None])
    def test_rejects_invalid_values_before_any_write(self, bad, monkeypatch):
        def _must_not_write(**_kwargs):
            raise AssertionError("repository must not be reached")

        monkeypatch.setattr(repo, "set_freshness_threshold_config", _must_not_write)
        with pytest.raises(service.FreshnessThresholdError):
            service.set_config(stale_after_minutes=bad, actor_user_id=1)

    def test_clear_requires_authenticated_actor(self):
        with pytest.raises(service.FreshnessThresholdError):
            service.clear_config(actor_user_id=None)


# ---------------------------------------------------------------------------
# Pure — live resolution
# ---------------------------------------------------------------------------


class TestEffectiveThreshold:
    def test_unconfigured_uses_the_environment_default(self):
        assert service.effective_stale_after_minutes() == service.default_stale_after_minutes()
        assert service.default_stale_after_minutes() == 1440

    def test_configured_value_wins(self, monkeypatch):
        monkeypatch.setattr(service, "_read_override_minutes", lambda: 90)
        assert service.effective_stale_after_minutes() == 90

    def test_evaluate_freshness_follows_the_configured_value(self, monkeypatch):
        reading = NOW - timedelta(hours=3)
        assert evaluate_freshness(reading, NOW) is Freshness.FRESH  # 24h default
        monkeypatch.setattr(service, "_read_override_minutes", lambda: 120)
        assert evaluate_freshness(reading, NOW) is Freshness.STALE

    def test_boundary_stays_strictly_greater_than(self, monkeypatch):
        monkeypatch.setattr(service, "_read_override_minutes", lambda: 60)
        assert evaluate_freshness(NOW - timedelta(minutes=60), NOW) is Freshness.FRESH
        assert evaluate_freshness(
            NOW - timedelta(minutes=60, seconds=1), NOW
        ) is Freshness.STALE

    def test_resolved_once_per_request_not_once_per_reading(self, monkeypatch):
        """evaluate_freshness runs ~960 times per fleet render; the override
        must cost one read per request."""
        reads = []

        def _counting_read():
            reads.append(1)
            return 30

        monkeypatch.setattr(service, "_read_override_minutes", _counting_read)
        with Flask(__name__).test_request_context():
            for _ in range(50):
                evaluate_freshness(NOW - timedelta(minutes=10), NOW)
        assert len(reads) == 1

    def test_a_new_request_sees_a_changed_value(self, monkeypatch):
        app = Flask(__name__)
        value = {"minutes": 30}
        monkeypatch.setattr(service, "_read_override_minutes", lambda: value["minutes"])
        with app.test_request_context():
            assert service.effective_stale_after_minutes() == 30
        value["minutes"] = 45
        with app.test_request_context():
            assert service.effective_stale_after_minutes() == 45

    def test_saving_forgets_the_value_already_resolved_in_this_request(self, monkeypatch):
        value = {"minutes": 30}
        monkeypatch.setattr(service, "_read_override_minutes", lambda: value["minutes"])
        monkeypatch.setattr(service, "session_scope", _fake_session_scope)
        monkeypatch.setattr(
            repo, "set_freshness_threshold_config",
            lambda **kw: repo.FreshnessThresholdConfigChange(
                previous=None, current=_record(kw["stale_after_minutes"]), changed=True,
            ),
        )
        monkeypatch.setattr(service.audit_service, "record", lambda *a, **k: None)
        with Flask(__name__).test_request_context():
            assert service.effective_stale_after_minutes() == 30
            value["minutes"] = 45
            service.set_config(stale_after_minutes=45, actor_user_id=1)
            assert service.effective_stale_after_minutes() == 45


class _FakeSession:
    pass


class _fake_session_scope:
    def __enter__(self):
        return _FakeSession()

    def __exit__(self, *exc):
        return False


def _record(minutes: int) -> repo.FreshnessThresholdConfigRecord:
    return repo.FreshnessThresholdConfigRecord(
        stale_after_minutes=minutes, configured_by_user_id=1,
        configured_at=datetime.now(timezone.utc),
    )


class TestVocabulary:
    def test_operations_fit_column_limit(self):
        assert len(audit_cfg.FRESHNESS_THRESHOLD_SET) <= 50
        assert len(audit_cfg.FRESHNESS_THRESHOLD_CLEARED) <= 50

    def test_entity_is_stable_and_global(self):
        assert audit_cfg.ENTITY_FRESHNESS_THRESHOLD == "freshness_threshold"
        assert audit_cfg.FRESHNESS_THRESHOLD_ENTITY_ID == "global"

    def test_not_a_system_operation(self):
        assert audit_cfg.FRESHNESS_THRESHOLD_SET not in audit_cfg.SYSTEM_OPERATIONS
        assert audit_cfg.FRESHNESS_THRESHOLD_CLEARED not in audit_cfg.SYSTEM_OPERATIONS


class TestBr008StaysIndependent:
    def test_notification_rule_does_not_read_the_configurable_threshold(self):
        import inspect

        from services import notification_service

        source = inspect.getsource(notification_service)
        assert "freshness_threshold" not in source
        assert "effective_stale_after_minutes" not in source


# ---------------------------------------------------------------------------
# Database-backed — persistence, no-op semantics, audit, rollback
# ---------------------------------------------------------------------------


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "freshness_threshold_config",
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
class TestFreshnessThresholdPersistence:
    def setup_method(self):
        _wipe()
        self.admin = repo.create_or_update_user(
            username="fresh-admin", full_name="Admin",
            role="administrator", status="active",
        ).user_id

    def test_starts_unconfigured_and_uses_the_default(self):
        assert service.get_current_config() is None
        assert service.effective_stale_after_minutes() == service.default_stale_after_minutes()

    def test_set_persists_audits_and_takes_effect(self):
        state = service.set_config(stale_after_minutes=720, actor_user_id=self.admin)
        assert state.stale_after_minutes == 720
        assert state.configured_by_user_id == self.admin
        assert service.effective_stale_after_minutes() == 720

        rows = _audit_rows()
        assert len(rows) == 1
        assert rows[0]["operation"] == audit_cfg.FRESHNESS_THRESHOLD_SET
        assert rows[0]["entity_type"] == audit_cfg.ENTITY_FRESHNESS_THRESHOLD
        assert rows[0]["entity_id"] == audit_cfg.FRESHNESS_THRESHOLD_ENTITY_ID
        assert rows[0]["user_id"] == self.admin
        assert rows[0]["old_values"] is None
        assert rows[0]["new_values"]["stale_after_minutes"] == 720

    def test_identical_re_save_is_a_silent_noop(self):
        first = service.set_config(stale_after_minutes=720, actor_user_id=self.admin)
        again = service.set_config(stale_after_minutes=720, actor_user_id=self.admin)
        assert again.configured_at == first.configured_at
        assert [r["operation"] for r in _audit_rows()] == [audit_cfg.FRESHNESS_THRESHOLD_SET]

    def test_change_is_audited_with_old_and_new_values(self):
        service.set_config(stale_after_minutes=720, actor_user_id=self.admin)
        service.set_config(stale_after_minutes=360, actor_user_id=self.admin)
        rows = _audit_rows()
        assert [r["operation"] for r in rows] == [
            audit_cfg.FRESHNESS_THRESHOLD_SET, audit_cfg.FRESHNESS_THRESHOLD_SET,
        ]
        assert rows[1]["old_values"]["stale_after_minutes"] == 720
        assert rows[1]["new_values"]["stale_after_minutes"] == 360

    def test_clear_returns_to_default_and_is_audited(self):
        service.set_config(stale_after_minutes=720, actor_user_id=self.admin)
        cleared = service.clear_config(actor_user_id=self.admin)
        assert cleared.stale_after_minutes == 720
        assert service.get_current_config() is None
        assert service.effective_stale_after_minutes() == service.default_stale_after_minutes()
        rows = _audit_rows()
        assert rows[-1]["operation"] == audit_cfg.FRESHNESS_THRESHOLD_CLEARED
        assert rows[-1]["new_values"] is None

    def test_clearing_when_unconfigured_is_a_noop(self):
        assert service.clear_config(actor_user_id=self.admin) is None
        assert _audit_rows() == []

    def test_audit_failure_rolls_back_the_write(self, monkeypatch):
        def _boom(*_a, **_k):
            raise RuntimeError("audit down")

        monkeypatch.setattr(service.audit_service, "record", _boom)
        with pytest.raises(service.FreshnessThresholdError):
            service.set_config(stale_after_minutes=720, actor_user_id=self.admin)
        assert service.get_current_config() is None

    def test_database_rejects_out_of_range_even_bypassing_the_service(self):
        with pytest.raises(IntegrityError):
            repo.set_freshness_threshold_config(
                stale_after_minutes=0, configured_by_user_id=self.admin,
            )
