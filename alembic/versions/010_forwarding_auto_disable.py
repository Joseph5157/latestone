"""
010_forwarding_auto_disable — BR016 daily auto-disable override (C08-AUTO-DISABLE-1).

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1, pending
client confirmation): this application owns BR016's cutoff, default 18:30
Africa/Johannesburg (config/forwarding_schedule.py — not stored here, since
it never varies from that one deployment-wide constant). This migration adds
only the temporary override: exactly ONE global same-day cutoff override may
exist at a time, never per-user or per-RTL (explicit baseline decision).

Singleton via a fixed `id = 1` primary key plus a CHECK enforcing it — the
same "there can only ever be one row" shape a dedicated settings table needs
when the value has no natural per-entity key. `override_date` scopes the
override to the single day it was set for; the service layer (not this
schema) is what makes it stop applying once that date has passed — no
"expiry" job or column exists because comparing today's date against
`override_date` is sufficient and requires no cleanup.

`reason` is NOT NULL: the development baseline requires a reason for every
override, so the constraint carries that rule at the schema level rather
than leaving it to be silently forgotten in a service layer.

Additive only: no changes to `message_forwarding`, no repository/service
wiring here — see services/forwarding_auto_disable_service.py.

Revision ID: 010_forwarding_auto_disable
Revises: 009_rtl_command_lifecycle
Create Date: 2026-09-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "010_forwarding_auto_disable"
down_revision = "009_rtl_command_lifecycle"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "forwarding_auto_disable_override",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("override_date", sa.Date(), nullable=False),
        sa.Column("cutoff_time", sa.Time(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("set_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("set_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_forwarding_auto_disable_override_singleton"),
        sa.ForeignKeyConstraint(["set_by_user_id"], [f"{SCHEMA}.users.user_id"]),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("forwarding_auto_disable_override", schema=SCHEMA)
