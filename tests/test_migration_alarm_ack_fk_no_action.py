"""Schema contract for migration 014 — acknowledgement actor FK is NO ACTION."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import pytest

from db.engine import session_scope


pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]


@pytest.fixture(scope="module", autouse=True)
def _schema(isolated_schema: str):
    with session_scope() as session:
        session.execute(text(f"INSERT INTO {isolated_schema}.users (username, full_name, role) VALUES ('ack', 'Ack', 'administrator')"))
        session.execute(text(f"INSERT INTO {isolated_schema}.plants (plant_id, name, country, latitude, longitude) VALUES ('p1', 'Plant', 'Test', 0, 0)"))
        session.execute(text(f"INSERT INTO {isolated_schema}.transformers (transformer_id, plant_id, transformer_code) VALUES ('t1', 'p1', 't1')"))
        session.execute(text(f"INSERT INTO {isolated_schema}.devices (device_id, transformer_id, device_code) VALUES ('d1', 't1', 'd1')"))


def _acknowledger_user_id(isolated_schema: str) -> int:
    with session_scope() as session:
        return session.execute(
            text(f"SELECT user_id FROM {isolated_schema}.users WHERE username = 'ack'")
        ).scalar_one()


def test_acknowledgement_fk_delete_rule_is_no_action(isolated_schema: str):
    with session_scope() as session:
        rule = session.execute(
            text(
                """
                SELECT rc.delete_rule
                FROM information_schema.table_constraints tc
                JOIN information_schema.referential_constraints rc
                  ON tc.constraint_name = rc.constraint_name
                 AND tc.constraint_schema = rc.constraint_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = :schema
                  AND tc.constraint_name = 'fk_device_events_acknowledged_by_user'
                """
            ),
            {"schema": isolated_schema},
        ).scalar_one()
    assert rule == "NO ACTION"


def test_acknowledgement_pair_check_still_enforced(isolated_schema: str):
    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {isolated_schema}.device_events "
                    "(device_id, event_type, event_ts, acknowledged_at) "
                    "VALUES ('d1', 'battery_low', now(), now())"
                )
            )


def test_acknowledgement_pair_check_accepts_a_complete_pair(isolated_schema: str):
    user_id = _acknowledger_user_id(isolated_schema)
    with session_scope() as session:
        row = session.execute(
            text(
                f"INSERT INTO {isolated_schema}.device_events "
                "(device_id, event_type, event_ts, acknowledged_at, acknowledged_by_user_id) "
                "VALUES ('d1', 'battery_low', now(), now(), :user_id) "
                "RETURNING acknowledged_at, acknowledged_by_user_id"
            ),
            {"user_id": user_id},
        ).one()
    assert row.acknowledged_by_user_id == user_id


def test_deleting_a_referenced_acknowledger_is_refused(isolated_schema: str):
    user_id = _acknowledger_user_id(isolated_schema)
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {isolated_schema}.device_events "
                "(device_id, event_type, event_ts, acknowledged_at, acknowledged_by_user_id) "
                "VALUES ('d1', 'sensor_error', now(), now(), :user_id)"
            ),
            {"user_id": user_id},
        )

    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.execute(
                text(f"DELETE FROM {isolated_schema}.users WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
