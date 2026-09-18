"""
015_freshness_threshold_config — administrator-configurable global freshness
(Stale-after) threshold, read live by freshness evaluation (FRESHNESS-CONFIG-1).

Same singleton shape as ``temperature_threshold_config`` (migration 011): a
fixed ``id = 1`` primary key plus a CHECK enforcing it. UNCONFIGURED IS
ABSENCE — no row exists until an Administrator sets a value, and clearing
deletes the row. With no row, the application keeps using the
environment-derived default (``FRESHNESS_STALE_AFTER_MINUTES``, 24 hours).

The range CHECK mirrors the service's input guards (5 minutes to 365 days).
Those bounds are typo guards, not client-confirmed business thresholds; the
database repeats them so a direct write can never store a value that would
mark the whole fleet Stale (e.g. 0) or effectively disable freshness.

Additive only: no change to ``readings``, ``devices`` or any existing table.

Revision ID: 015_freshness_threshold_config
Revises: 014_alarm_ack_fk_no_action
Create Date: 2026-09-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "015_freshness_threshold_config"
down_revision = "014_alarm_ack_fk_no_action"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "freshness_threshold_config",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("stale_after_minutes", sa.Integer(), nullable=False),
        sa.Column("configured_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "configured_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_freshness_threshold_config_singleton"),
        sa.CheckConstraint(
            "stale_after_minutes BETWEEN 5 AND 525600",
            name="ck_freshness_threshold_config_minutes_range",
        ),
        sa.ForeignKeyConstraint(["configured_by_user_id"], [f"{SCHEMA}.users.user_id"]),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("freshness_threshold_config", schema=SCHEMA)
