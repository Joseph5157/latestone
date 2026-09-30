"""016_rtl_technician_assignments — Technician to client RTL UID assignment.

TECHNICIAN-REAL-RTL-ACCESS-01 (ADR-032). Application-owned assignment store
keyed on the CLIENT RTL UID (``dbo.device_list.device_uid``, a SQL Server int),
because the older ``user_device_assignments`` table is keyed on the synthetic
``devices.device_id`` and there is no approved mapping between the two.

Rules enforced by the database itself, not only by application code:

* one OPEN (``ended_at IS NULL``) assignment per RTL UID — a partial unique
  index. An RTL may have many closed rows over time (retained history);
* a technician may hold many open assignments;
* provenance is ``APPLICATION`` (created by an Administrator through the
  application) or ``LEGACY_IMPORT`` (adopted from the client's legacy
  ``techmician_device_list`` snapshot). A legacy row carries NO assigned_at and
  NO assigned_by — the original date and actor are unknown and are not
  invented — and records its own ``imported_at`` instead. That is a CHECK, so
  a legacy row cannot be given a fabricated date later by accident.

``device_uid`` has no foreign key: the registered directory lives in the
read-only client SQL Server, which PostgreSQL cannot reference. Registration
is validated by the service against that source at write time.

``users.client_person_id`` is the verified identity bridge between an
application user and a client SQL Server ``persons.person_id``. It is NULL for
users with no client identity (all demo users) and unique where set. Identity
is never matched by display name at authorization time.

Additive only. Downgrade drops both.

Revision ID: 016_rtl_technician_assignments
Revises: 015_freshness_threshold_config
Create Date: 2026-09-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "016_rtl_technician_assignments"
down_revision = "015_freshness_threshold_config"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema
TABLE = "rtl_technician_assignments"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("client_person_id", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ux_users_client_person_id",
        "users",
        ["client_person_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("client_person_id IS NOT NULL"),
    )

    op.create_table(
        TABLE,
        sa.Column("assignment_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("device_uid", sa.Integer(), nullable=False),
        sa.Column("technician_user_id", sa.BigInteger(), nullable=False),
        sa.Column("provenance", sa.String(length=20), nullable=False),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.BigInteger(), nullable=True),
        sa.Column("imported_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.ForeignKeyConstraint(["technician_user_id"], [f"{SCHEMA}.users.user_id"]),
        sa.ForeignKeyConstraint(["assigned_by"], [f"{SCHEMA}.users.user_id"]),
        sa.ForeignKeyConstraint(["ended_by"], [f"{SCHEMA}.users.user_id"]),
        sa.CheckConstraint("device_uid > 0", name="ck_rtl_assign_uid_positive"),
        sa.CheckConstraint(
            "provenance IN ('APPLICATION', 'LEGACY_IMPORT')",
            name="ck_rtl_assign_provenance",
        ),
        # A legacy row has no known date or actor; an application row has both.
        sa.CheckConstraint(
            "(provenance = 'APPLICATION' AND assigned_at IS NOT NULL "
            "AND assigned_by IS NOT NULL AND imported_at IS NULL) OR "
            "(provenance = 'LEGACY_IMPORT' AND assigned_at IS NULL "
            "AND assigned_by IS NULL AND imported_at IS NOT NULL)",
            name="ck_rtl_assign_provenance_shape",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= COALESCE(assigned_at, imported_at)",
            name="ck_rtl_assign_ended_after_start",
        ),
        sa.CheckConstraint(
            "(ended_at IS NULL) = (ended_by IS NULL)",
            name="ck_rtl_assign_end_actor",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ux_rtl_assign_open_device_uid",
        TABLE,
        ["device_uid"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(f"ix_{TABLE}_technician", TABLE, ["technician_user_id"], schema=SCHEMA)
    op.create_index(f"ix_{TABLE}_device_uid", TABLE, ["device_uid"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_device_uid", table_name=TABLE, schema=SCHEMA)
    op.drop_index(f"ix_{TABLE}_technician", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ux_rtl_assign_open_device_uid", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
    op.drop_index("ux_users_client_person_id", table_name="users", schema=SCHEMA)
    op.drop_column("users", "client_person_id", schema=SCHEMA)
