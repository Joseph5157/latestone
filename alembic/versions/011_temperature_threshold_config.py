"""
011_temperature_threshold_config — administrator-configurable global
temperature warning/critical thresholds, framework only (THRESH-CONFIG-1).

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1, pending
client confirmation): C-01 requires warning/critical temperature thresholds
to be administrator-configurable and never permanently hardcoded, with every
change audited. Actual Eskom threshold values remain unconfirmed — this
migration adds storage for whatever an Administrator later configures, never
a default or seeded value.

Singleton via a fixed `id = 1` primary key plus a CHECK enforcing it — the
same shape `forwarding_auto_disable_override` (migration 010) already uses
for a single global settings row. UNCONFIGURED IS ABSENCE, not a row with
NULL columns: exactly like that override table, no row exists until an
Administrator actually sets one, and clearing deletes it rather than
nulling it out. There is therefore no NULL-related nuance to this schema at
all — `warning_temperature_c`/`critical_temperature_c` are NOT NULL, because
a row only ever exists once both are known.

`warning_temperature_c < critical_temperature_c` IS a database CHECK
constraint (`ck_temperature_threshold_config_warning_lt_critical`) — the
service (`services/temperature_threshold_service.py`) remains the
user-friendly validation boundary and rejects the same condition first, with
an actionable message, but the schema also protects the relational
invariant itself for any future caller or direct write that bypasses the
service. This is a genuine correction: an earlier version of this migration
reasoned the relationship should be service-only, but a service-side check
on ordinary Python floats cannot be trusted to still hold once both values
round to this column's fixed NUMERIC(12,3) scale — two distinct floats that
compare `warning < critical` in binary64 can collapse to the SAME
three-decimal value (or invert their order) once stored. The CHECK is
therefore not optional defense-in-depth; it is the only thing that
verifies the invariant against the actual persisted representation.
Note what the CHECK still does NOT do: no min/max range exists, and none
should — C-01 gives no numeric bounds to encode, and inventing one would be
exactly the kind of hardcoded threshold this gate exists to avoid. Whether
a given value even FITS in three decimal places without rounding is a
technical representability question, not a business threshold, and is the
service's job (reject excess precision outright, never silently round it).

`NUMERIC(12, 3)` matches `readings.value`'s precision (migration 001) — the
same physical quantity, stored the same way. The service canonicalizes
every value to this exact scale via `decimal.Decimal` BEFORE comparing or
persisting it, specifically so its own `warning < critical` check is
evaluated against the same representation this column will actually store
— never a raw `float` comparison that could disagree with what lands in
the database.

Additive only: no changes to `readings`, `devices`, or any existing table.
No repository/service wiring here — see
services/temperature_threshold_service.py.

Revision ID: 011_temperature_threshold_config
Revises: 010_forwarding_auto_disable
Create Date: 2026-09-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "011_temperature_threshold_config"
down_revision = "010_forwarding_auto_disable"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "temperature_threshold_config",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("warning_temperature_c", sa.Numeric(12, 3), nullable=False),
        sa.Column("critical_temperature_c", sa.Numeric(12, 3), nullable=False),
        sa.Column("configured_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("configured_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_temperature_threshold_config_singleton"),
        sa.CheckConstraint(
            "warning_temperature_c < critical_temperature_c",
            name="ck_temperature_threshold_config_warning_lt_critical",
        ),
        sa.ForeignKeyConstraint(["configured_by_user_id"], [f"{SCHEMA}.users.user_id"]),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("temperature_threshold_config", schema=SCHEMA)
