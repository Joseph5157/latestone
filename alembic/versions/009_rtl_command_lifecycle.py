"""
009_rtl_command_lifecycle — command execution lifecycle metadata (RTL-IF-2).

Adds the lifecycle timestamps and failure fields `rtl_commands` needs for
the deterministic SimulatorTransport dispatcher, without introducing any
transport-specific state:

    QUEUED -> SENT -> ACKNOWLEDGED -> SUCCEEDED
                  \-> FAILED
                  \-> TIMED_OUT

``rtl_commands.state``/``command_type`` still carry NO CHECK constraint
(migration 008's deliberate choice, ADR-017) — the six lifecycle values
above live in `config/commands.py` and are enforced by
`services/rtl_command_service.py`'s transition map, not by the database.
This migration only adds ordering/consistency CHECKs that hold regardless
of which specific state strings are in use:

- a timestamp can only exist once its predecessor does (``sent_at`` before
  ``acknowledged_at``/``completed_at``, both no earlier than ``sent_at``)
- ``failure_code`` implies the command reached a completed timestamp

No MQTT topic, broker message id, payload JSON, retry_count,
next_attempt_at, rtl_command_attempts, worker ownership, or provider
credentials — those remain out of scope for every RTL-IF tranche until a
real transport exists.

``failure_detail`` is bounded (``VARCHAR(255)``), not `TEXT`: it must carry
a normalized internal message (e.g. "Simulated transport failure."), never
a raw exception string or stack trace — see
`services/simulator_transport.py` and `services/rtl_command_dispatch_service.py`.

Revision ID: 009_rtl_command_lifecycle
Revises: 008_rtl_commands
Create Date: 2026-09-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "009_rtl_command_lifecycle"
down_revision = "008_rtl_commands"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema
TABLE = "rtl_commands"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("failure_code", sa.String(length=30), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("failure_detail", sa.String(length=255), nullable=True), schema=SCHEMA)

    op.create_check_constraint(
        "ck_rtl_commands_sent_after_created",
        TABLE,
        "sent_at IS NULL OR sent_at >= created_at",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_rtl_commands_acknowledged_after_sent",
        TABLE,
        "acknowledged_at IS NULL OR (sent_at IS NOT NULL AND acknowledged_at >= sent_at)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_rtl_commands_completed_after_sent",
        TABLE,
        "completed_at IS NULL OR (sent_at IS NOT NULL AND completed_at >= sent_at)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_rtl_commands_failure_requires_completion",
        TABLE,
        "failure_code IS NULL OR completed_at IS NOT NULL",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("ck_rtl_commands_failure_requires_completion", TABLE, schema=SCHEMA, type_="check")
    op.drop_constraint("ck_rtl_commands_completed_after_sent", TABLE, schema=SCHEMA, type_="check")
    op.drop_constraint("ck_rtl_commands_acknowledged_after_sent", TABLE, schema=SCHEMA, type_="check")
    op.drop_constraint("ck_rtl_commands_sent_after_created", TABLE, schema=SCHEMA, type_="check")

    op.drop_column(TABLE, "failure_detail", schema=SCHEMA)
    op.drop_column(TABLE, "failure_code", schema=SCHEMA)
    op.drop_column(TABLE, "completed_at", schema=SCHEMA)
    op.drop_column(TABLE, "acknowledged_at", schema=SCHEMA)
    op.drop_column(TABLE, "sent_at", schema=SCHEMA)
