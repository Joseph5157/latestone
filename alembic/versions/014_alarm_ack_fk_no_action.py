"""014_alarm_ack_fk_no_action — acknowledgement actor FK is NO ACTION.

Migration 013 created `fk_device_events_acknowledged_by_user` with
`ON DELETE SET NULL`. That conflicts with ADR-010: every foreign key in
this schema is `NO ACTION` (D4 — "No CASCADE, ever... Not on the
constraints, not on the deletes"), an invariant
`tests/test_seed_reset_contract.py::TestPurgeOrderAgainstTheLiveSchema::
test_no_foreign_key_relies_on_cascade` enforces directly. This migration
brings the constraint back into line without touching 013 or the
acknowledgement-pair CHECK it also created.

Revision ID: 014_alarm_ack_fk_no_action
Revises: 013_alarm_acknowledgement
Create Date: 2026-09-16
"""
from __future__ import annotations

from alembic import op

from config.settings import monitoring


revision: str = "014_alarm_ack_fk_no_action"
down_revision = "013_alarm_acknowledgement"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.drop_constraint(
        "fk_device_events_acknowledged_by_user",
        "device_events",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_device_events_acknowledged_by_user",
        "device_events",
        "users",
        ["acknowledged_by_user_id"],
        ["user_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="NO ACTION",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_device_events_acknowledged_by_user",
        "device_events",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_device_events_acknowledged_by_user",
        "device_events",
        "users",
        ["acknowledged_by_user_id"],
        ["user_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )
