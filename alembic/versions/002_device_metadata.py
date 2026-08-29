"""
002_device_metadata — additive device metadata columns (DB-1).

Adds nullable identity/lifecycle metadata to the existing ``devices`` table:
    msisdn, hardware_version, firmware_version, installed_at,
    created_at, updated_at

No existing column is renamed, dropped, or retyped. ``devices.status``
remains administrative status only (see AGENTS.md) and is untouched here.

``created_at``/``updated_at`` are NOT NULL with a constant ``now()`` default,
which PostgreSQL applies as a fast metadata-only backfill (no table rewrite)
for already-seeded rows.

Revision ID: 002_device_metadata
Revises: 001_baseline
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "002_device_metadata"
down_revision = "001_baseline"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.add_column("devices", sa.Column("msisdn", sa.String(length=20), nullable=True), schema=SCHEMA)
    op.add_column("devices", sa.Column("hardware_version", sa.String(length=50), nullable=True), schema=SCHEMA)
    op.add_column("devices", sa.Column("firmware_version", sa.String(length=50), nullable=True), schema=SCHEMA)
    op.add_column("devices", sa.Column("installed_at", sa.TIMESTAMP(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column(
        "devices",
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )
    op.add_column(
        "devices",
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("devices", "updated_at", schema=SCHEMA)
    op.drop_column("devices", "created_at", schema=SCHEMA)
    op.drop_column("devices", "installed_at", schema=SCHEMA)
    op.drop_column("devices", "firmware_version", schema=SCHEMA)
    op.drop_column("devices", "hardware_version", schema=SCHEMA)
    op.drop_column("devices", "msisdn", schema=SCHEMA)
