"""
Bootstrap contract tests — BOOTSTRAP-1.

Pins the two properties that make a fresh-clone setup reproducible on a
machine that has never run this project.

SINGLE SCHEMA AUTHORITY:
    Alembic owns the database schema outright. Postgres' image-level
    `/docker-entrypoint-initdb.d` hook must not also create it. When both ran,
    Docker init produced the four baseline tables and then
    `alembic upgrade head` tried to create the same tables again
    (001_baseline uses `op.create_table`, which has no IF NOT EXISTS), so a
    fresh clone could not migrate. Working around that with
    `alembic stamp 001_baseline` only hid which component owned the schema.

IMPORTING THE APP MUST NOT NEED A DATABASE:
    `python -m pytest -m "not db"` is documented as the pure-logic suite that
    runs without Docker, and `gunicorn app:server` should not depend on the
    database being reachable at the instant the module is imported. Callback
    registration therefore has to stay free of queries — importing a module is
    not the moment to read or write rows.

Neither test needs PostgreSQL, which is the point of both of them.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Postgres runs anything mounted here on first init of an empty data
#: directory. Mounting schema DDL here is what created the second authority.
INITDB_HOOK_DIR = "docker-entrypoint-initdb.d"

#: A port nothing listens on, so the child process below cannot reach a
#: database even when the developer's normal stack happens to be running.
UNREACHABLE_PORT = "59999"


class TestAlembicIsTheOnlySchemaAuthority:
    def test_compose_mounts_nothing_into_the_postgres_init_hook(self):
        """docker-compose.yml must not seed schema behind Alembic's back.

        Comments are stripped before the check: the file deliberately explains
        why nothing is mounted there, and prose saying "don't do this" must not
        read as doing it.
        """
        raw = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        directives = [
            line
            for line in raw.splitlines()
            if not line.lstrip().startswith("#")
        ]

        assert all(INITDB_HOOK_DIR not in line for line in directives), (
            "docker-compose.yml mounts something into "
            f"/{INITDB_HOOK_DIR}. Postgres would create schema on first init, "
            "and `alembic upgrade head` would then fail creating tables that "
            "already exist. Alembic is the single bootstrap authority."
        )


class TestImportingTheAppNeedsNoDatabase:
    def test_import_app_succeeds_with_no_database_reachable(self):
        """`import app` must not open a connection.

        Runs in a subprocess pointed at a dead port: an in-process import
        would be satisfied by module caching and by whatever database the
        developer already has running, so it could never observe the defect.
        """
        env = dict(os.environ)
        env["POSTGRES_PORT"] = UNREACHABLE_PORT

        result = subprocess.run(
            [sys.executable, "-c", "import app"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            "Importing app opened a database connection. Callback "
            "registration must not query or write; move the call to the "
            "request path that actually needs the data.\n\n"
            f"{result.stderr[-2000:]}"
        )
