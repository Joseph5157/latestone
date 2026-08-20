"""
003_users — persistent users table (DB-1).

Additive only: does not wire any repository/service/callback to this table.
The existing in-memory prototype store (services/prototype_users.py) is
untouched; replacing it is DB-2, not DB-1.

Roles are the three confirmed values from the Functional Specification
(services/prototype_access.py::CONFIRMED_ROLES). Full Role/Privilege/
Permission RBAC is deliberately deferred, so this is a CHECK constraint,
not a lookup table.

``email_address``/``mobile_number`` are nullable and NOT unique: uniqueness
for either is a plausible future rule but is not a confirmed business rule,
so it is not invented here.

Revision ID: 003_users
Revises: 002_device_metadata
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "003_users"
down_revision = "002_device_metadata"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email_address", sa.String(length=255), nullable=True),
        sa.Column("mobile_number", sa.String(length=20), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("username"),
        sa.CheckConstraint(
            "role IN ('administrator', 'technician', 'general')",
            name="ck_users_role",
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("users", schema=SCHEMA)
