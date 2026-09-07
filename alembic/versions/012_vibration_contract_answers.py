"""
012_vibration_contract_answers — administrator-editable capture of the
vibration sensor contract, framework only (VIB-CONFIG-1 / C-02).

Development baseline (docs/context/ACTIVE_GATE.md, C08-BASELINE-1, pending
client confirmation): C-02 requires vibration to be a configurable
framework, never hardcoded. `docs/VIBRATION_METRIC_CONTRACT_TBD.md` lists
15 unanswered questions about the real sensor contract (unit, axes,
thresholds, storage, API shape, ...) — this migration adds storage for
whatever an Administrator later records against EACH question
individually, never a default or guessed answer for any of them.

GENUINE KEY-VALUE, deliberately NOT one column per question and NOT a
singleton like `forwarding_auto_disable_override`/`temperature_threshold_config`
(migrations 010/011). Those two model exactly one global fact each; this
one models up to fifteen INDEPENDENT facts, any subset of which may be
unknown at a time, so a multi-row `(question_key, answer_text)` table is
the natural shape — "unanswered" is the ABSENCE of a row for that key,
matching this repository's now-established convention (010, 011) that
unconfigured means no row, never a row with a NULL/placeholder value.
Answering question A can never require inventing an answer for question B.

`question_key` carries NO CHECK constraint against the 15 known keys.
This is deliberate, mirroring `config/audit.py`'s own precedent (the
`audit_log.operation` column has no CHECK either — "this module is the
application-side source of truth"): the valid key set lives in
`config/vibration_contract.py`, in Python, not baked into this migration.
If a 16th question is ever confirmed by the client, it needs no schema
change at all — only a new entry in that registry. A CHECK enumerating
today's 15 keys would silently defeat the entire reason this is a
key-value table rather than 15 dedicated columns.

`answer_text` is free-form `TEXT`, NOT NULL: exactly like `reason` on
`forwarding_auto_disable_override`, a row only exists once there IS an
answer, so there is no NULL-vs-empty nuance to encode. No unit, range, or
type constraint is placed on the text — this migration does not know what
shape any answer will take (a number, a column name, "TBD", a full
sentence), and inventing one would be exactly the premature semantic
encoding this gate exists to avoid.

Additive only: no changes to `readings`, `devices`, `config/metrics.py`,
or any existing table. No repository/service wiring here — see
services/vibration_contract_service.py. Vibration remains fully inactive
everywhere else in the application (event semantics, metric registry,
repository metric queries, freshness) — this migration only creates a
place to WRITE DOWN answers, not a place any runtime code reads FROM yet.

Revision ID: 012_vibration_contract_answers
Revises: 011_temperature_threshold_config
Create Date: 2026-09-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "012_vibration_contract_answers"
down_revision = "011_temperature_threshold_config"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    op.create_table(
        "vibration_contract_answers",
        sa.Column("question_key", sa.String(length=100), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("question_key"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], [f"{SCHEMA}.users.user_id"]),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("vibration_contract_answers", schema=SCHEMA)
