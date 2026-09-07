"""C08-AUTO-DISABLE-1 tests — BR016 daily auto-disable + same-day override.

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1), pending
client confirmation. Pure classes cover parsing, cutoff-date arithmetic, and
the before/after-cutoff gate without a database. Database-backed suites run
against the module-scoped isolated_schema (tests/conftest.py), never the
real plant_monitoring tables — mirrors tests/test_message_forwarding.py.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from config.forwarding_schedule import DEFAULT_CUTOFF_TIME, TIMEZONE
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service, forwarding_auto_disable_service as service


# ---------------------------------------------------------------------------
# Pure — parsing, vocabulary, cutoff-date arithmetic
# ---------------------------------------------------------------------------


class TestParseCutoffTime:
    def test_valid_time_parses(self):
        assert service.parse_cutoff_time("18:30") == time(18, 30)
        assert service.parse_cutoff_time(" 09:05 ") == time(9, 5)
        assert service.parse_cutoff_time("00:00") == time(0, 0)
        assert service.parse_cutoff_time("23:59") == time(23, 59)

    @pytest.mark.parametrize(
        "bad",
        ["", None, "9:5", "18:3", "24:00", "23:60", "18:30:00", "abc", "1830"],
    )
    def test_invalid_time_rejected(self, bad):
        with pytest.raises(service.AutoDisableError):
            service.parse_cutoff_time(bad)


class TestVocabulary:
    def test_operations_fit_column_limit(self):
        assert len(audit_cfg.AUTO_DISABLE_OVERRIDE_SET) <= 50
        assert len(audit_cfg.AUTO_DISABLE_OVERRIDE_CLEARED) <= 50

    def test_message_forwarding_disabled_is_a_system_operation(self):
        # C08-AUTO-DISABLE-1 reuses the existing operation constant for the
        # system-originated path — no second constant, per config/audit.py's
        # own long-standing comment anticipating exactly this.
        assert audit_cfg.MESSAGE_FORWARDING_DISABLED in audit_cfg.SYSTEM_OPERATIONS

    def test_entity_is_stable_and_global(self):
        assert audit_cfg.ENTITY_AUTO_DISABLE_SCHEDULE == "forwarding_auto_disable"
        assert audit_cfg.AUTO_DISABLE_SCHEDULE_ENTITY_ID == "global"


class TestEffectiveCutoffFor:
    def test_no_override_returns_default(self, monkeypatch):
        monkeypatch.setattr(repo, "get_auto_disable_override", lambda **_k: None)
        assert service.effective_cutoff_for(date(2026, 9, 6)) == DEFAULT_CUTOFF_TIME

    def test_override_applies_only_on_its_own_date(self, monkeypatch):
        record = repo.AutoDisableOverrideRecord(
            override_date=date(2026, 9, 6),
            cutoff_time=time(20, 0),
            reason="late maintenance window",
            set_by_user_id=1,
            set_at=datetime.now(timezone.utc),
        )
        monkeypatch.setattr(repo, "get_auto_disable_override", lambda **_k: record)

        assert service.effective_cutoff_for(date(2026, 9, 6)) == time(20, 0)
        # "Expires automatically... normal 18:30 resumes next day" (C-08):
        # no expiry step exists — the date simply no longer matches.
        assert service.effective_cutoff_for(date(2026, 9, 7)) == DEFAULT_CUTOFF_TIME
        assert service.effective_cutoff_for(date(2026, 9, 5)) == DEFAULT_CUTOFF_TIME


class TestApplyAutoDisableGating:
    """Africa/Johannesburg is UTC+2 year-round (no DST) — 18:30 local is
    16:30 UTC, used throughout to construct times either side of the cutoff
    without depending on the machine running the tests being in that zone.
    """

    def test_naive_now_rejected(self):
        with pytest.raises(service.AutoDisableError):
            service.apply_auto_disable(now=datetime(2026, 9, 6, 19, 0))

    def test_before_cutoff_touches_nothing(self, monkeypatch):
        monkeypatch.setattr(repo, "get_auto_disable_override", lambda **_k: None)

        def _must_not_be_called(*_a, **_k):
            raise AssertionError(
                "apply_auto_disable must not read/write forwarding state "
                "before the cutoff has passed"
            )

        monkeypatch.setattr(repo, "list_enabled_forwarding_user_ids", _must_not_be_called)

        before_cutoff_utc = datetime(2026, 9, 6, 16, 0, tzinfo=timezone.utc)  # 18:00 SAST
        result = service.apply_auto_disable(now=before_cutoff_utc)

        assert result.ran is False
        assert result.disabled_user_ids == ()
        assert result.effective_cutoff == DEFAULT_CUTOFF_TIME
        assert result.local_now == before_cutoff_utc.astimezone(TIMEZONE)

    def test_at_or_after_cutoff_proceeds_to_the_bulk_path(self, monkeypatch):
        monkeypatch.setattr(repo, "get_auto_disable_override", lambda **_k: None)
        monkeypatch.setattr(repo, "list_enabled_forwarding_user_ids", lambda **_k: [])

        at_cutoff_utc = datetime(2026, 9, 6, 16, 30, tzinfo=timezone.utc)  # exactly 18:30 SAST
        result = service.apply_auto_disable(now=at_cutoff_utc)

        assert result.ran is True
        assert result.disabled_user_ids == ()  # nobody enabled


# ---------------------------------------------------------------------------
# Database-backed — persisted behaviour on isolated schema
# ---------------------------------------------------------------------------


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "forwarding_auto_disable_override", "message_forwarding",
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


AFTER_CUTOFF_UTC = datetime(2026, 9, 6, 17, 0, tzinfo=timezone.utc)  # 19:00 SAST


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestAutoDisablePersistence:
    def setup_method(self):
        _wipe()
        self.admin = repo.create_or_update_user(
            username="autodis-admin", full_name="Admin",
            role="administrator", status="active",
        ).user_id
        self.alice = repo.create_or_update_user(
            username="autodis-alice", full_name="Alice",
            role="technician", status="active",
        ).user_id
        self.bob = repo.create_or_update_user(
            username="autodis-bob", full_name="Bob",
            role="technician", status="active",
        ).user_id

    def test_disables_every_enabled_user_and_audits_system_originated(self):
        repo.set_message_forwarding(self.alice, True)
        repo.set_message_forwarding(self.bob, True)

        result = service.apply_auto_disable(now=AFTER_CUTOFF_UTC)

        assert result.ran is True
        assert set(result.disabled_user_ids) == {self.alice, self.bob}
        assert repo.get_message_forwarding(self.alice).enabled is False
        assert repo.get_message_forwarding(self.bob).enabled is False

        rows = _audit_rows()
        assert len(rows) == 2
        for row in rows:
            assert row["operation"] == audit_cfg.MESSAGE_FORWARDING_DISABLED
            assert row["entity_type"] == audit_cfg.ENTITY_MESSAGE_FORWARDING
            assert row["user_id"] is None  # system-originated (ACT-D5 style)
            assert row["old_values"]["enabled"] is True
            assert row["new_values"]["enabled"] is False

    def test_leaves_already_disabled_and_never_enabled_users_untouched(self):
        repo.set_message_forwarding(self.alice, True)
        repo.set_message_forwarding(self.alice, False)  # already disabled
        # bob never toggled forwarding at all (no row, FWD-D2)

        result = service.apply_auto_disable(now=AFTER_CUTOFF_UTC)

        assert result.disabled_user_ids == ()
        # No audit at all: the setup calls repo.set_message_forwarding()
        # directly (unaudited, by design — auditing is the service layer's
        # job), and apply_auto_disable found nothing left to change.
        assert _audit_rows() == []

    def test_second_call_same_day_is_idempotent(self):
        repo.set_message_forwarding(self.alice, True)

        first = service.apply_auto_disable(now=AFTER_CUTOFF_UTC)
        second = service.apply_auto_disable(now=AFTER_CUTOFF_UTC)

        assert first.disabled_user_ids == (self.alice,)
        assert second.disabled_user_ids == ()  # already disabled — no-op
        assert len(_audit_rows()) == 1  # not re-audited

    def test_re_enabling_after_auto_disable_survives_until_next_cutoff(self):
        repo.set_message_forwarding(self.alice, True)
        service.apply_auto_disable(now=AFTER_CUTOFF_UTC)
        repo.set_message_forwarding(self.alice, True)  # re-enabled during the day

        before_next_cutoff = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)  # 12:00 SAST next day
        result = service.apply_auto_disable(now=before_next_cutoff)

        assert result.ran is False
        assert repo.get_message_forwarding(self.alice).enabled is True

    def test_set_override_requires_a_reason(self):
        with pytest.raises(service.AutoDisableError):
            service.set_override(
                cutoff_time=time(20, 0), reason="   ", actor_user_id=self.admin
            )
        with pytest.raises(service.AutoDisableError):
            service.set_override(
                cutoff_time=time(20, 0), reason=None, actor_user_id=self.admin
            )
        assert repo.get_auto_disable_override() is None

    def test_set_override_persists_and_audits_human_actor(self):
        state = service.set_override(
            cutoff_time=time(20, 0),
            reason="late installation window",
            actor_user_id=self.admin,
            today=date(2026, 9, 6),
        )
        assert state.cutoff_time == time(20, 0)
        assert state.override_date == date(2026, 9, 6)
        assert state.set_by_user_id == self.admin

        rows = _audit_rows()
        assert len(rows) == 1
        assert rows[0]["operation"] == audit_cfg.AUTO_DISABLE_OVERRIDE_SET
        assert rows[0]["entity_type"] == audit_cfg.ENTITY_AUTO_DISABLE_SCHEDULE
        assert rows[0]["entity_id"] == audit_cfg.AUTO_DISABLE_SCHEDULE_ENTITY_ID
        assert rows[0]["user_id"] == self.admin
        assert rows[0]["old_values"] is None
        assert rows[0]["new_values"]["cutoff_time"] == "20:00:00"

    def test_re_setting_identical_override_is_a_silent_noop(self):
        # Mirrors message_forwarding's FWD-D3: same date/cutoff/reason as
        # what is already set changes nothing and audits nothing.
        first = service.set_override(
            cutoff_time=time(20, 0), reason="same reason",
            actor_user_id=self.admin, today=date(2026, 9, 6),
        )
        again = service.set_override(
            cutoff_time=time(20, 0), reason="same reason",
            actor_user_id=self.admin, today=date(2026, 9, 6),
        )
        assert again.set_at == first.set_at  # no churn
        assert [r["operation"] for r in _audit_rows()] == [
            audit_cfg.AUTO_DISABLE_OVERRIDE_SET,
        ]

    def test_changing_cutoff_time_is_a_real_change_and_is_audited(self):
        service.set_override(
            cutoff_time=time(20, 0), reason="same reason",
            actor_user_id=self.admin, today=date(2026, 9, 6),
        )
        service.set_override(
            cutoff_time=time(21, 0), reason="same reason",
            actor_user_id=self.admin, today=date(2026, 9, 6),
        )
        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.AUTO_DISABLE_OVERRIDE_SET,
            audit_cfg.AUTO_DISABLE_OVERRIDE_SET,
        ]
        assert repo.get_auto_disable_override().cutoff_time == time(21, 0)

    def test_changing_reason_only_is_a_real_change_and_is_audited(self):
        service.set_override(
            cutoff_time=time(20, 0), reason="first reason",
            actor_user_id=self.admin, today=date(2026, 9, 6),
        )
        service.set_override(
            cutoff_time=time(20, 0), reason="second reason",
            actor_user_id=self.admin, today=date(2026, 9, 6),
        )
        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.AUTO_DISABLE_OVERRIDE_SET,
            audit_cfg.AUTO_DISABLE_OVERRIDE_SET,
        ]
        assert repo.get_auto_disable_override().reason == "second reason"

    def test_override_applies_only_to_its_own_day_end_to_end(self):
        service.set_override(
            cutoff_time=time(20, 0), reason="late window",
            actor_user_id=self.admin, today=date(2026, 9, 6),
        )
        repo.set_message_forwarding(self.alice, True)

        # 19:00 SAST on the override day: before the 20:00 override cutoff,
        # even though it is after the normal 18:30 default.
        still_before_override = datetime(2026, 9, 6, 17, 0, tzinfo=timezone.utc)
        result = service.apply_auto_disable(now=still_before_override)
        assert result.ran is False
        assert repo.get_message_forwarding(self.alice).enabled is True

        # Next day: override no longer applies, normal 18:30 resumes with no
        # action required.
        next_day_after_default = datetime(2026, 9, 7, 16, 45, tzinfo=timezone.utc)  # 18:45 SAST
        result = service.apply_auto_disable(now=next_day_after_default)
        assert result.ran is True
        assert result.effective_cutoff == DEFAULT_CUTOFF_TIME
        assert repo.get_message_forwarding(self.alice).enabled is False

    def test_clear_override_is_a_noop_when_nothing_is_set(self):
        result = service.clear_override(actor_user_id=self.admin)
        assert result is None
        assert _audit_rows() == []

    def test_clear_override_removes_row_and_audits(self):
        service.set_override(
            cutoff_time=time(20, 0), reason="late window",
            actor_user_id=self.admin, today=date(2026, 9, 6),
        )
        cleared = service.clear_override(actor_user_id=self.admin)

        assert cleared.cutoff_time == time(20, 0)
        assert repo.get_auto_disable_override() is None

        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.AUTO_DISABLE_OVERRIDE_SET,
            audit_cfg.AUTO_DISABLE_OVERRIDE_CLEARED,
        ]
        cleared_row = _audit_rows()[1]
        assert cleared_row["new_values"] is None
        assert cleared_row["old_values"]["cutoff_time"] == "20:00:00"

    def test_failed_audit_rolls_back_the_override_write(self, monkeypatch):
        def explode(**_kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        with pytest.raises(service.AutoDisableError):
            service.set_override(
                cutoff_time=time(20, 0), reason="late window",
                actor_user_id=self.admin, today=date(2026, 9, 6),
            )
        assert repo.get_auto_disable_override() is None

    def test_failed_audit_rolls_back_the_bulk_disable(self, monkeypatch):
        repo.set_message_forwarding(self.alice, True)

        def explode(**_kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        with pytest.raises(audit_service.AuditError):
            service.apply_auto_disable(now=AFTER_CUTOFF_UTC)

        # The whole batch is one transaction: a failure partway through must
        # not leave alice half-disabled.
        assert repo.get_message_forwarding(self.alice).enabled is True
