"""
005_rtl_operational_state — RTL programming/forwarding/active-list state (DB-1).

Three tables, bundled because they are one workflow unit:

rtl_programming_requests
    Persists programming/configuration requests only. Does NOT send real
    commands and does NOT pretend a physical RTL was actually programmed.
    ``transformer_id`` is a deliberate point-in-time snapshot of the
    device's transformer at request time — not redundant once device-
    transformer history (deferred, DB-8) exists, since a device's
    transformer can change after the request was made.

message_forwarding
    Per-user forwarding state (mirrors the client's flat membership-list
    semantics). No 18:30 scheduler here — that is backend work, not schema.

rtl_active_state
    RTL Master active-list membership, kept deliberately separate from
    ``devices.status`` (administrative status). A device can be
    administratively active but off the RTL Master's active list, or vice
    versa.

Additive only: no repository/service/callback wiring, no real SMS/RTL
integration.

Revision ID: 005_rtl_operational_state
Revises: 004_user_device_assignments
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "005_rtl_operational_state"
down_revision = "004_user_device_assignments"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "rtl_programming_requests",
        sa.Column("request_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("device_id", sa.String(length=30), nullable=False),
        sa.Column("transformer_id", sa.String(length=30), nullable=False),
        sa.Column("requested_by", sa.BigInteger(), nullable=False),
        sa.Column("master_msisdn", sa.String(length=20), nullable=False),
        sa.Column("requested_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("request_method", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("request_id"),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'sent', 'successful', 'failed')",
            name="ck_rtl_programming_requests_status",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= requested_at",
            name="ck_rtl_programming_requests_completed_after_requested",
        ),
        sa.ForeignKeyConstraint(["device_id"], [f"{SCHEMA}.devices.device_id"]),
        sa.ForeignKeyConstraint(["transformer_id"], [f"{SCHEMA}.transformers.transformer_id"]),
        sa.ForeignKeyConstraint(["requested_by"], [f"{SCHEMA}.users.user_id"]),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_rtl_programming_requests_device_ts",
        "rtl_programming_requests",
        ["device_id", sa.text("requested_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_rtl_programming_requests_status",
        "rtl_programming_requests",
        ["status"],
        schema=SCHEMA,
    )

    op.create_table(
        "message_forwarding",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.user_id"]),
        schema=SCHEMA,
    )

    op.create_table(
        "rtl_active_state",
        sa.Column("device_id", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("activated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("device_id"),
        sa.ForeignKeyConstraint(["device_id"], [f"{SCHEMA}.devices.device_id"]),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("rtl_active_state", schema=SCHEMA)
    op.drop_table("message_forwarding", schema=SCHEMA)

    op.drop_index("ix_rtl_programming_requests_status", table_name="rtl_programming_requests", schema=SCHEMA)
    op.drop_index("ix_rtl_programming_requests_device_ts", table_name="rtl_programming_requests", schema=SCHEMA)
    op.drop_table("rtl_programming_requests", schema=SCHEMA)
