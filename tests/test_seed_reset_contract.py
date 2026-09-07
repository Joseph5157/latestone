"""SEED-RESET-1 — the monitoring reset contract (ADR-010).

`seed_plant_monitoring --reset` could not complete: it deleted `devices`
while four later tables referenced them, every constraint `NO ACTION`. That
made it the broken way back from every other seed.

The fix is subtractive, and these tests exist to keep it that way. Deleting
the hierarchy was never necessary — the inserts are already
`ON CONFLICT DO NOTHING` and `build_hierarchy` is stable — so a reset now
replaces measurements and preserves everything else.

The load-bearing test here is `test_the_purge_order_covers_every_dependent`:
it walks the LIVE schema rather than a hand-written list, because the
original defect was precisely a hand-written list that stopped being true
when someone added a table.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from db import seed_freshness_demo as fresh
from db import seed_plant_monitoring as seed

SEED_SOURCE = pathlib.Path(seed.__file__).read_text(encoding="utf-8")
FRESH_SOURCE = pathlib.Path(fresh.__file__).read_text(encoding="utf-8")

#: Every table the schema actually has, READ FROM the migration-owned DDL
#: rather than restated here.
#:
#: This used to be a hand-written set, and it rotted exactly the way
#: PURGE_ORDER once did: migrations 010, 011 and 012 each added a table and
#: none was added here, so `test_the_classification_covers_every_table`
#: kept passing while three tables sat unclassified. Both sides of that
#: assertion were stale in the same direction, which is the one way a
#: hand-written expectation can fail silently. Deriving the universe from
#: `op.create_table(...)` closes that: a migration that adds a table now
#: fails this file until the table is classified in
#: `seed_plant_monitoring`, which is what the check was always meant to do.
#:
#: Static parsing, not a database read, so this stays a pure ("not db")
#: test — the live-schema walk it complements is
#: `TestPurgeOrderAgainstTheLiveSchema` below.
#: Repository root, derived from a module this package always imports —
#: never the working directory, which varies with how pytest was invoked.
_REPO_ROOT = pathlib.Path(seed.__file__).resolve().parents[1]

_MIGRATIONS_DIR = _REPO_ROOT / "alembic" / "versions"
_CREATE_TABLE_RE = re.compile(r"""op\.create_table\(\s*["'](\w+)["']""")


def _tables_created_by_migrations() -> set[str]:
    found: set[str] = set()
    for migration in sorted(_MIGRATIONS_DIR.glob("[0-9]*.py")):
        found |= set(
            _CREATE_TABLE_RE.findall(migration.read_text(encoding="utf-8"))
        )
    return found


KNOWN_TABLES = _tables_created_by_migrations()


class TestResetReplacesMeasurementsOnly:
    def test_reset_replaces_readings_and_nothing_else(self):
        assert seed.RESET_REPLACES == ("readings",)

    def test_the_hierarchy_is_preserved(self):
        """The delete that caused the defect. Its absence is the fix."""
        for table in ("plants", "transformers", "devices"):
            assert table in seed.RESET_PRESERVES
            assert table not in seed.RESET_REPLACES

    @pytest.mark.parametrize(
        "table",
        ["device_events", "user_device_assignments", "rtl_active_state",
         "rtl_programming_requests", "rtl_commands", "audit_log", "users"],
    )
    def test_operational_history_is_preserved(self, table):
        """A reseed of synthetic telemetry is not a reason to forget that an
        RTL powered down or that a technician was assigned to it."""
        assert table in seed.RESET_PRESERVES

    def test_every_table_is_classified(self):
        """"Everything else" is not a contract. Each table is named as either
        replaced or preserved, so a new one cannot slip through unclassified."""
        classified = set(seed.RESET_REPLACES) | set(seed.RESET_PRESERVES)
        assert KNOWN_TABLES == classified

    def test_no_table_is_both(self):
        assert not set(seed.RESET_REPLACES) & set(seed.RESET_PRESERVES)

    def test_the_reset_function_touches_one_table(self):
        body = SEED_SOURCE[
            SEED_SOURCE.index("def _reset_measurements"):
            SEED_SOURCE.index("def _table_counts")
        ]
        deletes = re.findall(r"DELETE FROM \{schema\}\.(\w+)", body)
        assert deletes == ["readings"]


class TestNoCascade:
    @pytest.mark.parametrize("source", [SEED_SOURCE, FRESH_SOURCE])
    def test_no_cascade_in_any_sql(self, source):
        """ADR-010 D4. CASCADE would make the delete succeed while silently
        destroying history nothing can rebuild.

        Checked against CODE only. The first version of this test banned the
        word outright and failed on the comment explaining why the word is
        not used -- a test that forbids documenting a decision is worse than
        no test, because the first fix anyone reaches for is deleting the
        explanation.
        """
        code = re.sub(r'"""[\s\S]*?"""', "", source)
        code = re.sub(r"#.*", "", code)
        assert not re.search(r"CASCADE", code, re.IGNORECASE)

    def test_the_adr_says_why(self):
        """The decision record must explain why CASCADE is not used.

        Skipped ONLY where `docs/decisions/` is absent altogether — a
        curated client delivery, which deliberately carries no ADRs
        (docs/CLIENT_DELIVERY.md). That is the one legitimate reason for
        this file to be missing.

        Where the directory exists, a missing or silent ADR is a real
        failure and is reported as one: the skip must never become a way
        for the record to quietly disappear from the development
        repository. Anchored to the repository root rather than the
        working directory, so it does not depend on where pytest was
        invoked from.
        """
        decisions = _REPO_ROOT / "docs" / "decisions"
        if not decisions.is_dir():
            pytest.skip(
                "no docs/decisions/ — curated delivery without ADRs"
            )

        adr = decisions / (
            "ADR-010-monitoring-reset-preserves-operational-history.md"
        )
        assert adr.is_file(), (
            f"{adr.name} is missing while docs/decisions/ exists — the "
            "reset contract has lost its decision record"
        )
        assert "CASCADE" in adr.read_text(encoding="utf-8")


class TestPurgeIsSeparateAndExplicit:
    def test_purge_is_not_reachable_from_reset(self):
        """Hiding the demolition inside a command named "reset" is what
        produced this defect."""
        body = SEED_SOURCE[SEED_SOURCE.index("def seed("):SEED_SOURCE.index("def main(")]
        assert "purge(" not in body

    def test_purge_refuses_without_a_second_acknowledgement(self):
        assert "acknowledged" in SEED_SOURCE
        assert "yes-destroy-operational-history" in SEED_SOURCE

    def test_purge_names_what_cannot_be_rebuilt(self):
        for table in ("device_events", "user_device_assignments",
                      "rtl_active_state", "rtl_programming_requests",
                      "rtl_commands"):
            assert table in seed.PURGE_DESTROYS_IRRECOVERABLY

    def test_children_are_deleted_before_their_parents(self):
        order = list(seed.PURGE_ORDER)
        for child, parent in [
            ("readings", "devices"),
            ("device_events", "devices"),
            ("rtl_active_state", "devices"),
            ("user_device_assignments", "devices"),
            ("rtl_programming_requests", "devices"),
            ("rtl_commands", "devices"),
            ("rtl_commands", "rtl_programming_requests"),
            ("device_events", "transformers"),
            ("rtl_programming_requests", "transformers"),
            ("devices", "transformers"),
            ("transformers", "plants"),
        ]:
            assert order.index(child) < order.index(parent), f"{child} after {parent}"


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestPurgeOrderAgainstTheLiveSchema:
    """The one test that would have caught the original defect.

    A hand-written ordering is exactly what rotted. This walks the real
    foreign keys, so a table added tomorrow fails here instead of failing an
    operator's reset months later.
    """

    def test_the_purge_order_covers_every_dependent(self):
        from sqlalchemy import text

        from config.settings import monitoring
        from db.engine import session_scope

        with session_scope() as session:
            rows = session.execute(
                text(
                    """
                    SELECT DISTINCT tc.table_name AS child,
                                    ccu.table_name AS parent
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.constraint_column_usage ccu
                      ON tc.constraint_name = ccu.constraint_name
                     AND tc.table_schema = ccu.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema = :s
                    """
                ),
                {"s": monitoring.schema},
            ).fetchall()

        order = list(seed.PURGE_ORDER)
        for child, parent in rows:
            if parent not in order:
                # `users` is deliberately outside the purge (ADR-010 D2).
                continue
            assert child in order, (
                f"{child} references {parent} but is not in PURGE_ORDER — "
                "this is the shape of the original SEED-RESET-1 defect"
            )
            assert order.index(child) < order.index(parent)

    def test_no_foreign_key_relies_on_cascade(self):
        """The safety of the order above depends on nothing being removed
        implicitly."""
        from sqlalchemy import text

        from config.settings import monitoring
        from db.engine import session_scope

        with session_scope() as session:
            rules = session.execute(
                text(
                    """
                    SELECT DISTINCT rc.delete_rule
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.referential_constraints rc
                      ON tc.constraint_name = rc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema = :s
                    """
                ),
                {"s": monitoring.schema},
            ).scalars().all()

        assert set(rules) == {"NO ACTION"}
