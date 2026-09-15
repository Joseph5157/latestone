"""013_alarm_acknowledgement — durable internal acknowledgement state.

Acknowledgement is a human response to one persisted device event.  It is
deliberately independent from event occurrence and any future alarm
clearance/resolution lifecycle: acknowledged events remain in history and in
the Notification Center projection.

Revision ID: 013_alarm_acknowledgement
Revises: 012_vibration_contract_answers
Create Date: 2026-09-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring


revision: str = "013_alarm_acknowledgement"
down_revision = "012_vibration_contract_answers"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.add_column(
        "device_events",
        sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "device_events",
        sa.Column("acknowledged_by_user_id", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_device_events_acknowledged_by_user",
        "device_events",
        "users",
        ["acknowledged_by_user_id"],
        ["user_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_device_events_acknowledgement_pair",
        "(acknowledged_at IS NULL) = (acknowledged_by_user_id IS NULL)",
        "device_events",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_device_events_acknowledgement_pair", "device_events", schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_device_events_acknowledged_by_user", "device_events", schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_column("device_events", "acknowledged_by_user_id", schema=SCHEMA)
    op.drop_column("device_events", "acknowledged_at", schema=SCHEMA)
