"""
008_rtl_commands — protocol-neutral command persistence (RTL-IF-1).

The seam between an authorized programming request and a future device
transport:

    authorized Program RTL
            v
    rtl_programming_requests   (operator-intent record, immutable — OPS-PROG-1)
            v
    rtl_commands                (this migration)
            v
    future transport            (not this tranche)
            v
    future simulator / Eskom adapter (not this tranche)

``rtl_programming_requests`` stays the append-only intent/provenance record
(PROG-D3) and is not touched by this migration. ``rtl_commands`` references
it rather than duplicating its payload: no master_msisdn, no requested_by,
no request_method here — a future transport resolves everything it needs
from the command plus its referenced request.

One command per programming request: ``uq_rtl_commands_request_id`` enforces
this at the database level rather than relying on service-layer discipline.

``command_type`` and ``state`` deliberately carry NO CHECK constraint,
unlike ``rtl_programming_requests.status`` (migration 005, a fully-known
five-value lifecycle at the time it was written). This tranche's vocabulary
is a single value each (PROGRAM_RTL, QUEUED — see config/commands.py); a
future transport tranche will add SENT/ACK/FAILED states without needing a
migration merely to extend an enum. This follows ``device_events.event_type``
(migration 006, open VARCHAR) rather than migration 005's CHECK.

No MQTT topic, broker message id, wire payload, SMS fields, Eskom ACK
fields, retry fields, command_attempts, desired/reported state, or
notification delivery state — those belong to a future transport-specific
migration, not this protocol-neutral one.

Revision ID: 008_rtl_commands
Revises: 007_audit_log
Create Date: 2026-09-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "008_rtl_commands"
down_revision = "007_audit_log"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "rtl_commands",
        sa.Column("command_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.String(length=30), nullable=False),
        sa.Column("command_type", sa.String(length=30), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default=sa.text("'QUEUED'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("command_id"),
        sa.UniqueConstraint("request_id", name="uq_rtl_commands_request_id"),
        sa.ForeignKeyConstraint(
            ["request_id"], [f"{SCHEMA}.rtl_programming_requests.request_id"]
        ),
        sa.ForeignKeyConstraint(["device_id"], [f"{SCHEMA}.devices.device_id"]),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_rtl_commands_device_ts",
        "rtl_commands",
        ["device_id", sa.text("created_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_rtl_commands_state",
        "rtl_commands",
        ["state"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_rtl_commands_state", table_name="rtl_commands", schema=SCHEMA)
    op.drop_index("ix_rtl_commands_device_ts", table_name="rtl_commands", schema=SCHEMA)
    op.drop_table("rtl_commands", schema=SCHEMA)
