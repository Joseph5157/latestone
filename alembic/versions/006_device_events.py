"""
006_device_events — normalized device/transformer event history (DB-1).

Replaces (conceptually — no data migration performed) several legacy
per-alarm-type tables (alarm_log, comms_alarm, powerdown_log,
sensor_error_log, startup_msg_log, invalid_uid_log) with one normalized
event model.

``event_type`` is intentionally VARCHAR with NO CHECK constraint. The nine
values below are the currently-known vocabulary from the legacy system, not
a confirmed closed/permanent list the way ``users.role`` is confirmed by the
Functional Specification — a legitimate new event type should not require a
migration:

    startup, check_in, sensor_error, battery_low, power_down,
    comms_alarm, high_temperature, vibration_event, invalid_uid

``severity`` similarly has no CHECK / enum: no source document defines a
severity vocabulary, and AGENTS.md fixes MonitoringCondition as always
UNKNOWN with no thresholds — inventing a severity scale here would
contradict that policy.

``reported_uid`` exists specifically for ``invalid_uid`` events: an invalid
UID may not correspond to any registered device, so it cannot always carry a
``device_id``. The attribution CHECK requires at least one of device_id,
transformer_id, or reported_uid — never all three NULL.

Revision ID: 006_device_events
Revises: 005_rtl_operational_state
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "006_device_events"
down_revision = "005_rtl_operational_state"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "device_events",
        sa.Column("event_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("device_id", sa.String(length=30), nullable=True),
        sa.Column("transformer_id", sa.String(length=30), nullable=True),
        sa.Column("reported_uid", sa.String(length=30), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("event_ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("temperature", sa.Numeric(6, 2), nullable=True),
        sa.Column("battery_voltage", sa.Numeric(5, 2), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("event_id"),
        sa.CheckConstraint(
            "device_id IS NOT NULL OR transformer_id IS NOT NULL OR reported_uid IS NOT NULL",
            name="ck_device_events_attribution",
        ),
        sa.ForeignKeyConstraint(["device_id"], [f"{SCHEMA}.devices.device_id"]),
        sa.ForeignKeyConstraint(["transformer_id"], [f"{SCHEMA}.transformers.transformer_id"]),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_device_events_device_ts",
        "device_events",
        ["device_id", sa.text("event_ts DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_device_events_transformer_ts",
        "device_events",
        ["transformer_id", sa.text("event_ts DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_device_events_type",
        "device_events",
        ["event_type"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_device_events_type", table_name="device_events", schema=SCHEMA)
    op.drop_index("ix_device_events_transformer_ts", table_name="device_events", schema=SCHEMA)
    op.drop_index("ix_device_events_device_ts", table_name="device_events", schema=SCHEMA)
    op.drop_table("device_events", schema=SCHEMA)
