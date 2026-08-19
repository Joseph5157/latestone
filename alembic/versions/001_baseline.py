"""
001_baseline — current four-table monitoring schema.

Mirrors db/init_plant_monitoring.sql.template exactly:
    plant_monitoring.plants
    plant_monitoring.transformers
    plant_monitoring.devices
    plant_monitoring.readings

This migration is the schema authority for the baseline. On an EXISTING
seeded database it is applied by stamping (``alembic stamp 001_baseline``),
which records the revision WITHOUT executing this DDL, so the existing
tables and their data are never touched. On a FRESH database it is applied
by ``alembic upgrade head`` and creates the full baseline from nothing.

The configured schema name comes from config.settings.monitoring.schema
(the same validated value the repository interpolates). Alembic's
``version_table_schema`` in env.py places alembic_version inside that same
schema, so schema and migration metadata can never disagree.

Revision ID: 001_baseline
Revises:
Create Date: 2026-08-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "001_baseline"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    """Create the baseline monitoring schema (fresh databases only)."""
    op.create_table(
        "plants",
        sa.Column("plant_id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("latitude", sa.Numeric(8, 4), nullable=False),
        sa.Column("longitude", sa.Numeric(8, 4), nullable=False),
        sa.Column("capacity_mw", sa.Numeric(10, 1), nullable=True),
        sa.Column("primary_fuel", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.PrimaryKeyConstraint("plant_id"),
        schema=SCHEMA,
    )

    op.create_table(
        "transformers",
        sa.Column("transformer_id", sa.String(length=30), nullable=False),
        sa.Column("plant_id", sa.String(length=20), nullable=False),
        sa.Column("transformer_code", sa.String(length=10), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.PrimaryKeyConstraint("transformer_id"),
        sa.UniqueConstraint("plant_id", "transformer_code"),
        sa.ForeignKeyConstraint(
            ["plant_id"],
            [f"{SCHEMA}.plants.plant_id"],
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(length=30), nullable=False),
        sa.Column("transformer_id", sa.String(length=30), nullable=False),
        sa.Column("device_code", sa.String(length=10), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint("transformer_id", "device_code"),
        sa.ForeignKeyConstraint(
            ["transformer_id"],
            [f"{SCHEMA}.transformers.transformer_id"],
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "readings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("device_id", sa.String(length=30), nullable=False),
        sa.Column("metric", sa.String(length=30), nullable=False),
        sa.Column("reading_ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(12, 3), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "metric", "reading_ts"),
        sa.ForeignKeyConstraint(
            ["device_id"],
            [f"{SCHEMA}.devices.device_id"],
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_transformers_plant_id",
        "transformers",
        ["plant_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_devices_transformer_id",
        "devices",
        ["transformer_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_readings_device_metric_ts",
        "readings",
        ["device_id", "metric", sa.text("reading_ts DESC")],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop the baseline monitoring schema (reverse FK order)."""
    op.drop_index("ix_readings_device_metric_ts", table_name="readings", schema=SCHEMA)
    op.drop_index("ix_devices_transformer_id", table_name="devices", schema=SCHEMA)
    op.drop_index("ix_transformers_plant_id", table_name="transformers", schema=SCHEMA)

    op.drop_table("readings", schema=SCHEMA)
    op.drop_table("devices", schema=SCHEMA)
    op.drop_table("transformers", schema=SCHEMA)
    op.drop_table("plants", schema=SCHEMA)
