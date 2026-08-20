"""
004_user_device_assignments — technician/device assignment history (DB-1).

Persists technician-to-RTL assignment history. Business rule: one device may
have at most one ACTIVE (``ended_at IS NULL``) assignment at a time; one
technician may hold many active assignments. History is preserved by closing
a row (``ended_at`` set) rather than overwriting it.

The one-active-assignment-per-device rule is enforced by PostgreSQL itself
via a partial unique index on ``device_id`` scoped to ``ended_at IS NULL`` —
not by application code, and not expressible as a plain UNIQUE constraint.

Additive only: no repository/service/callback wiring. The existing in-memory
stores (callbacks/device_assign.py) are untouched.

Revision ID: 004_user_device_assignments
Revises: 003_users
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "004_user_device_assignments"
down_revision = "003_users"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "user_device_assignments",
        sa.Column("assignment_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("device_id", sa.String(length=30), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("assigned_by", sa.BigInteger(), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= assigned_at",
            name="ck_user_device_assignments_ended_after_assigned",
        ),
        sa.ForeignKeyConstraint(["device_id"], [f"{SCHEMA}.devices.device_id"]),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.user_id"]),
        sa.ForeignKeyConstraint(["assigned_by"], [f"{SCHEMA}.users.user_id"]),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_user_device_assignments_device_id",
        "user_device_assignments",
        ["device_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_user_device_assignments_user_id",
        "user_device_assignments",
        ["user_id"],
        schema=SCHEMA,
    )
    # Partial unique index: the enforcement mechanism for "one active
    # assignment per device". A second INSERT with ended_at IS NULL for the
    # same device_id raises IntegrityError.
    op.create_index(
        "ux_user_device_assignments_active_device",
        "user_device_assignments",
        ["device_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_user_device_assignments_active_device", table_name="user_device_assignments", schema=SCHEMA)
    op.drop_index("ix_user_device_assignments_user_id", table_name="user_device_assignments", schema=SCHEMA)
    op.drop_index("ix_user_device_assignments_device_id", table_name="user_device_assignments", schema=SCHEMA)
    op.drop_table("user_device_assignments", schema=SCHEMA)
