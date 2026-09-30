"""017_local_auth_hardening — application-local authentication (ADR-033).

AUTHENTICATION-LOCAL-HARDENING-01. Application-owned credential, lifecycle and
session-security state on ``users``, plus two small tables:

* ``auth_tokens`` — single-use, time-limited password setup/reset tokens. Only
  the SHA-256 of the token is stored; the raw token exists once, in the
  Administrator's provisioning view.
* ``auth_login_throttle`` — failed-login counters keyed by a hash of the
  normalised login name, so an unknown name is throttled exactly like a real
  one (no username oracle) and no attempt counter sits on a user row.

``users`` gains ``password_hash`` (werkzeug scrypt; NULL = no credential),
``password_changed_at``, ``session_version`` (bumped on every security change;
a session whose stored version differs is dead) and ``last_login_at``. The
status vocabulary becomes ``pending_activation`` / ``active`` / ``disabled``.

UPGRADE BEHAVIOUR for existing rows (no row is deleted; user ids, roles,
``client_person_id`` and assignments are untouched):

1. ``inactive`` -> ``disabled`` (the old two-state vocabulary).
2. ``active`` rows linked to a client person (the login-less Technician
   anchors, users 117-121 in the development database) -> ``pending_activation``.
   They have no credential; an Administrator must issue a setup link.
3. Every other existing ``active`` row keeps ``active`` and has no hash. In a
   development process with demo login explicitly enabled it stays reachable
   through the demo fixture; in production it cannot authenticate (no hash, demo
   refused) until an Administrator issues a reset link.
4. Usernames are lower-cased so the login identifier has one canonical form;
   the migration aborts, changing nothing, if two rows would collide.

Additive except for those value normalisations. Downgrade drops the new
objects and maps ``disabled``/``pending_activation`` back to ``inactive``/
``active`` (a reversible legacy view; hashes and tokens are discarded).

Revision ID: 017_local_auth_hardening
Revises: 016_rtl_technician_assignments
Create Date: 2026-09-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from config.settings import monitoring

# revision identifiers, used by Alembic.
revision: str = "017_local_auth_hardening"
down_revision = "016_rtl_technician_assignments"
branch_labels = None
depends_on = None

SCHEMA = monitoring.schema


def upgrade() -> None:
    bind = op.get_bind()

    collisions = bind.execute(
        sa.text(
            f"SELECT lower(username) FROM {SCHEMA}.users "
            "GROUP BY lower(username) HAVING count(*) > 1"
        )
    ).all()
    if collisions:
        raise RuntimeError(
            "Cannot normalise usernames to lower case: "
            f"{len(collisions)} case-insensitive collision(s) exist. "
            "Resolve them explicitly before upgrading."
        )

    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        schema=SCHEMA,
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    op.execute(sa.text(f"UPDATE {SCHEMA}.users SET status = 'disabled' WHERE status = 'inactive'"))
    op.execute(
        sa.text(
            f"UPDATE {SCHEMA}.users SET status = 'pending_activation' "
            "WHERE status = 'active' AND client_person_id IS NOT NULL "
            "AND password_hash IS NULL"
        )
    )
    op.execute(sa.text(f"UPDATE {SCHEMA}.users SET username = lower(username) WHERE username <> lower(username)"))

    op.create_check_constraint(
        "ck_users_status",
        "users",
        "status IN ('pending_activation', 'active', 'disabled')",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_users_username_lower",
        "users",
        "username = lower(username)",
        schema=SCHEMA,
    )

    op.create_table(
        "auth_tokens",
        sa.Column("token_id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("purpose", sa.String(length=10), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("token_id"),
        sa.ForeignKeyConstraint(["user_id"], [f"{SCHEMA}.users.user_id"]),
        sa.ForeignKeyConstraint(["created_by"], [f"{SCHEMA}.users.user_id"]),
        sa.UniqueConstraint("token_hash", name="ux_auth_tokens_token_hash"),
        sa.CheckConstraint("purpose IN ('setup', 'reset')", name="ck_auth_tokens_purpose"),
        schema=SCHEMA,
    )
    op.create_index("ix_auth_tokens_user", "auth_tokens", ["user_id"], schema=SCHEMA)

    op.create_table(
        "auth_login_throttle",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_failure_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("locked_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key_hash"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("auth_login_throttle", schema=SCHEMA)
    op.drop_index("ix_auth_tokens_user", table_name="auth_tokens", schema=SCHEMA)
    op.drop_table("auth_tokens", schema=SCHEMA)
    op.drop_constraint("ck_users_username_lower", "users", schema=SCHEMA, type_="check")
    op.drop_constraint("ck_users_status", "users", schema=SCHEMA, type_="check")
    op.execute(sa.text(f"UPDATE {SCHEMA}.users SET status = 'inactive' WHERE status = 'disabled'"))
    op.execute(sa.text(f"UPDATE {SCHEMA}.users SET status = 'active' WHERE status = 'pending_activation'"))
    for column in ("last_login_at", "session_version", "password_changed_at", "password_hash"):
        op.drop_column("users", column, schema=SCHEMA)
