"""Migration 017 — application-local authentication (ADR-033).

Proves the documented UPGRADE BEHAVIOUR against rows that look like the real
development database: a legacy `inactive` user, five login-less linked
Technicians, ordinary active accounts and a mixed-case username. Alembic runs
in a SUBPROCESS against a temporary schema; the real schema is never touched.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text

from db.engine import session_scope

pytestmark = pytest.mark.db


def _alembic(schema: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PLANT_MONITORING_SCHEMA"] = schema
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=os.getcwd(), env=env,
        capture_output=True, text=True,
    )


def _sql(schema: str, sql: str, **params):
    with session_scope() as session:
        result = session.execute(text(sql.replace("SCHEMA.", f"{schema}.")), params)
        return result.all() if result.returns_rows else None


@pytest.fixture
def schema():
    name = f"pm_mig017_{uuid.uuid4().hex[:8]}"
    yield name
    with session_scope() as session:
        session.execute(text(f"DROP SCHEMA IF EXISTS {name} CASCADE"))


def _legacy_rows(schema: str, *, mixed_case_collision: bool = False) -> None:
    rows = [
        ("admin", "administrator", "active", None),
        ("demo.tech01", "technician", "active", None),
        ("retired.user", "general", "inactive", None),
        ("Mixed.Case", "general", "active", None),
    ] + [(f"client-person-{n}", "technician", "active", n) for n in range(2, 7)]
    if mixed_case_collision:
        rows.append(("MIXED.case", "general", "active", None))
    for username, role, status, person in rows:
        _sql(schema, "INSERT INTO SCHEMA.users (username, full_name, role, status, client_person_id) "
             "VALUES (:u, :u, :r, :s, :p)", u=username, r=role, s=status, p=person)


def test_upgrade_transitions_existing_rows_as_documented(schema):
    assert _alembic(schema, "upgrade", "016_rtl_technician_assignments").returncode == 0
    _legacy_rows(schema)
    ids = {r[0]: r[1] for r in _sql(schema, "SELECT username, user_id FROM SCHEMA.users")}

    result = _alembic(schema, "upgrade", "head")
    assert result.returncode == 0, result.stderr

    state = {r[0]: r[1:] for r in _sql(
        schema, "SELECT username, status, client_person_id, password_hash, session_version, user_id "
                "FROM SCHEMA.users")}

    # no row deleted, no id changed
    assert len(state) == 9
    assert {u: state[u.lower()][4] for u in ids} == ids

    # `inactive` -> `disabled`
    assert state["retired.user"][0] == "disabled"
    # the five linked login-less Technicians -> pending, links untouched
    for n in range(2, 7):
        status, person, pw, version, _ = state[f"client-person-{n}"]
        assert (status, person, pw, version) == ("pending_activation", n, None, 1)
    # ordinary active development accounts stay active (no lock-out), no hash
    assert state["admin"][0] == "active" and state["admin"][2] is None
    assert state["demo.tech01"][0] == "active"
    # usernames are lower-cased
    assert "mixed.case" in state and "Mixed.Case" not in state


def test_upgrade_does_not_alter_assignments(schema):
    assert _alembic(schema, "upgrade", "016_rtl_technician_assignments").returncode == 0
    _legacy_rows(schema)
    uid = _sql(schema, "SELECT user_id FROM SCHEMA.users WHERE username = 'client-person-2'")[0][0]
    _sql(schema, "INSERT INTO SCHEMA.rtl_technician_assignments "
                 "(device_uid, technician_user_id, provenance, imported_at) "
                 "VALUES (29001, :u, 'LEGACY_IMPORT', now())", u=uid)
    before = _sql(schema, "SELECT * FROM SCHEMA.rtl_technician_assignments")
    assert _alembic(schema, "upgrade", "head").returncode == 0
    assert _sql(schema, "SELECT * FROM SCHEMA.rtl_technician_assignments") == before


def test_upgrade_aborts_without_changes_on_a_case_collision(schema):
    assert _alembic(schema, "upgrade", "016_rtl_technician_assignments").returncode == 0
    _legacy_rows(schema, mixed_case_collision=True)
    result = _alembic(schema, "upgrade", "head")
    assert result.returncode != 0 and "collision" in result.stderr
    # still at 016, nothing normalised
    assert {r[0] for r in _sql(schema, "SELECT username FROM SCHEMA.users")} >= {"Mixed.Case", "MIXED.case"}
    cols = {r[0] for r in _sql(
        schema, "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = 'users'", s=schema)}
    assert "password_hash" not in cols


def test_downgrade_restores_the_legacy_vocabulary_and_drops_the_objects(schema):
    assert _alembic(schema, "upgrade", "head").returncode == 0
    _sql(schema, "INSERT INTO SCHEMA.users (username, full_name, role, status) "
                 "VALUES ('a.b.c', 'A', 'general', 'disabled'), ('d.e.f', 'D', 'general', 'pending_activation')")
    assert _alembic(schema, "downgrade", "016_rtl_technician_assignments").returncode == 0
    statuses = {r[0]: r[1] for r in _sql(schema, "SELECT username, status FROM SCHEMA.users")}
    assert statuses == {"a.b.c": "inactive", "d.e.f": "active"}
    tables = {r[0] for r in _sql(
        schema, "SELECT table_name FROM information_schema.tables WHERE table_schema = :s", s=schema)}
    assert "auth_tokens" not in tables and "auth_login_throttle" not in tables
