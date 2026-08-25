"""OPS-FWD-1 message forwarding persistence tests — FWD-D1..D9 frozen.

Pure classes cover vocabulary and strict-actor validation. Database-backed
suites run against the module-scoped isolated_schema (tests/conftest.py),
never the real plant_monitoring tables.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services import audit_service, message_forwarding_service as fwd


# ---------------------------------------------------------------------------
# Pure — vocabulary and validation
# ---------------------------------------------------------------------------


class TestForwardingVocabulary:
    def test_operations_fit_column_limit(self):
        assert len(audit_cfg.MESSAGE_FORWARDING_ENABLED) <= 50
        assert len(audit_cfg.MESSAGE_FORWARDING_DISABLED) <= 50

    def test_entity_type_is_stable(self):
        assert audit_cfg.ENTITY_MESSAGE_FORWARDING == "message_forwarding"

    def test_missing_actor_fails_before_any_database_access(self):
        with pytest.raises(fwd.ForwardingError):
            fwd.set_forwarding(enabled=True, actor_user_id=None)

    def test_malformed_actor_fails_before_any_database_access(self):
        for bad in ("1", True, 4.0):
            with pytest.raises(fwd.ForwardingError):
                fwd.set_forwarding(enabled=True, actor_user_id=bad)


# ---------------------------------------------------------------------------
# Database-backed — persisted behaviour on isolated schema
# ---------------------------------------------------------------------------


def _wipe() -> None:
    """Reset everything this module touches, FK-safe order."""
    with session_scope() as session:
        for table in (
            "audit_log", "message_forwarding", "user_device_assignments",
            "readings", "devices", "transformers", "plants", "users",
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
class TestForwardingPersistence:
    def setup_method(self):
        _wipe()
        self.alice = repo.create_or_update_user(
            username="fwd-alice", full_name="Alice",
            role="technician", status="active",
        ).user_id

    def test_first_enable_creates_row_and_audits_with_null_old_values(self):
        state = fwd.set_forwarding(enabled=True, actor_user_id=self.alice)

        assert state.enabled is True
        assert state.enabled_at is not None
        assert state.disabled_at is None

        rows = _audit_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["operation"] == audit_cfg.MESSAGE_FORWARDING_ENABLED
        assert row["entity_type"] == audit_cfg.ENTITY_MESSAGE_FORWARDING
        assert row["entity_id"] == str(self.alice)          # FWD-D6
        assert row["user_id"] == self.alice                 # strict D2
        assert row["old_values"] is None
        assert row["new_values"]["username"] == "fwd-alice"
        assert row["new_values"]["enabled"] is True

    def test_disable_then_re_enable_preserves_opposite_timestamps_fwd_d4(self):
        first = fwd.set_forwarding(enabled=True, actor_user_id=self.alice)
        disabled = fwd.set_forwarding(enabled=False, actor_user_id=self.alice)
        re_enabled = fwd.set_forwarding(enabled=True, actor_user_id=self.alice)

        # Disable kept the enable timestamp; re-enable kept the disable one.
        assert disabled.enabled_at == first.enabled_at
        assert disabled.disabled_at is not None
        assert re_enabled.disabled_at == disabled.disabled_at
        assert re_enabled.enabled_at > first.enabled_at

        ops = [r["operation"] for r in _audit_rows()]
        assert ops == [
            audit_cfg.MESSAGE_FORWARDING_ENABLED,
            audit_cfg.MESSAGE_FORWARDING_DISABLED,
            audit_cfg.MESSAGE_FORWARDING_ENABLED,
        ]

    def test_re_enable_audits_a_real_old_new_pair(self):
        fwd.set_forwarding(enabled=True, actor_user_id=self.alice)
        fwd.set_forwarding(enabled=False, actor_user_id=self.alice)
        rows = _audit_rows()
        assert rows[1]["old_values"]["enabled"] is True
        assert rows[1]["new_values"]["enabled"] is False
        assert rows[1]["operation"] == audit_cfg.MESSAGE_FORWARDING_DISABLED

    def test_same_state_reapply_is_silent_noop_fwd_d3(self):
        first = fwd.set_forwarding(enabled=True, actor_user_id=self.alice)
        again = fwd.set_forwarding(enabled=True, actor_user_id=self.alice)

        assert again.enabled_at == first.enabled_at      # no timestamp churn
        assert len(_audit_rows()) == 1                   # only the transition

    def test_disable_without_row_inserts_nothing_and_audits_nothing_fwd_d2(self):
        state = fwd.set_forwarding(enabled=False, actor_user_id=self.alice)

        assert state.enabled is False
        assert state.enabled_at is None and state.disabled_at is None
        assert repo.get_message_forwarding(self.alice) is None   # no row made
        assert _audit_rows() == []

    def test_get_state_maps_absent_row_to_disabled_fwd_d7(self):
        state = fwd.get_state(self.alice)
        assert state.enabled is False
        assert state.enabled_at is None and state.disabled_at is None

    def test_states_are_per_user_fwd_d1(self):
        bob = repo.create_or_update_user(
            username="fwd-bob", full_name="Bob",
            role="administrator", status="active",
        ).user_id

        fwd.set_forwarding(enabled=True, actor_user_id=self.alice)

        assert fwd.get_state(self.alice).enabled is True
        assert fwd.get_state(bob).enabled is False       # untouched

        ids = {r["entity_id"] for r in _audit_rows()}
        assert ids == {str(self.alice)}                  # keyed by actor only

    def test_failed_audit_rolls_back_the_state_change(self, monkeypatch):
        """FWD-D5: mutation + audit share one transaction. The same failure
        injection AUD-1 uses must leave NO forwarding row behind."""

        def explode(**kwargs):
            raise RuntimeError("simulated audit-store outage")

        monkeypatch.setattr(repo, "insert_audit_log", explode)
        with pytest.raises(fwd.ForwardingError):
            fwd.set_forwarding(enabled=True, actor_user_id=self.alice)

        assert repo.get_message_forwarding(self.alice) is None
        assert _audit_rows() == []

    def test_unknown_actor_fails_and_persists_nothing(self):
        with pytest.raises(fwd.ForwardingError):
            fwd.set_forwarding(enabled=True, actor_user_id=999_999_999)

        assert repo.get_message_forwarding(999_999_999) is None
        assert _audit_rows() == []
