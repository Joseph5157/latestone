"""
007_audit_log — system activity audit trail (DB-1).

``entity_id`` is untyped (VARCHAR, no FK): audited entities have
heterogeneous key types (string device/transformer ids, bigint user/
assignment ids), so a single polymorphic FK is not possible. This is the
standard shape for a generic audit table, not an accidental repeat of the
client's weak-FK legacy pattern (RTL_DATABASE_EVOLUTION_PLAN.md section 3) —
it is structurally required here, not a shortcut.

``operation`` has no CHECK constraint: the plan documents it as an
open-ended, growing list ("should later include..."), unlike the confirmed
closed vocabularies used elsewhere (e.g. users.role).

``user_id`` is nullable to allow future system/scheduled actions (e.g. the
documented 18:30 automatic forwarding disable) that have no human actor.

Revision ID: 007_audit_log
Revises: 006_device_events
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "007_audit_log"
down_revision = "006_device_events"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("audit_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("old_values", JSONB(), nullable=True),
        sa.Column("new_values", JSONB(), nullable=True),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("audit_id"),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.user_id"]),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_audit_log_entity",
        "audit_log",
        ["entity_type", "entity_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_audit_log_user_ts",
        "audit_log",
        ["user_id", sa.text("occurred_at DESC")],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_user_ts", table_name="audit_log", schema=SCHEMA)
    op.drop_index("ix_audit_log_entity", table_name="audit_log", schema=SCHEMA)
    op.drop_table("audit_log", schema=SCHEMA)
