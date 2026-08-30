"""The freshness demo is REVERSIBLE (SEED-RESET-1, ADR-010 D5).

This is the test that unblocks CC-1's mixed-freshness acceptance. The demo
has to DELETE readings — staleness and absence cannot be inserted (ADR-009
D3) — so the only way it can be safe is if the exact rows come back.

"Exact" is the whole point, and it is asserted on values as well as keys: a
restore that returned the right (device, metric, timestamp) triples with
drifted numbers would pass a count check and still have corrupted the
fixture. `NUMERIC` round-trips through `Decimal`, so the capture stores
strings and this compares them.

Runs against a disposable schema. It writes and deletes readings, and must
never do that to the developer's real `plant_monitoring` tables.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from db import seed_freshness_demo as fresh
from db.engine import session_scope

pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)

#: Mirrors the demo's own targets so the fixture exercises the real ones.
STALE_TARGET = "plant-03-t1-d1"
LAGGING_TARGET = "plant-04-t1-d1"
BLIND_TARGET = "plant-05-t1-d1"
CONTROL = "plant-02-t1-d1"

METRICS = ("temperature", "voltage", "current", "frequency")


@pytest.fixture
def seeded(isolated_schema, tmp_path, monkeypatch):
    """A minimal hierarchy plus 48 hours of readings for the demo's targets.

    Deliberately small: this test is about the capture/restore contract, not
    about the generator, and 1.38M rows would say nothing extra.
    """
    monkeypatch.setattr(
        fresh, "CAPTURE_PATH", tmp_path / "capture.json", raising=True
    )
    schema = isolated_schema
    devices = [CONTROL, STALE_TARGET, LAGGING_TARGET, BLIND_TARGET]

    with session_scope() as s:
        # `isolated_schema` is MODULE-scoped, so the schema survives between
        # tests in this file. Each test starts from a known state instead of
        # inheriting whatever the previous one left — in FK-safe order, the
        # same discipline ADR-010 requires of the seeds themselves.
        for table in ("readings", "devices", "transformers", "plants"):
            s.execute(text(f"DELETE FROM {schema}.{table}"))
        s.execute(
            text(
                f"INSERT INTO {schema}.plants "
                "(plant_id, name, country, latitude, longitude) "
                "VALUES ('p', 'P', 'ZA', 0, 0) ON CONFLICT DO NOTHING"
            )
        )
        s.execute(
            text(
                f"INSERT INTO {schema}.transformers "
                "(transformer_id, plant_id, transformer_code) "
                "VALUES ('t', 'p', 'tx') ON CONFLICT DO NOTHING"
            )
        )
        for index, device_id in enumerate(devices):
            # Codes must be DISTINCT. An earlier version derived them from
            # `device_id[-4:]`, which is "1-d1" for all four — and because the
            # insert is ON CONFLICT DO NOTHING, three devices silently failed
            # to exist and the readings insert then failed on the foreign key.
            s.execute(
                text(
                    f"INSERT INTO {schema}.devices "
                    "(device_id, transformer_id, device_code) "
                    "VALUES (:d, 't', :c)"
                ),
                {"d": device_id, "c": f"dev{index}"},
            )
        rows = []
        for device_id in devices:
            for metric in METRICS:
                for hour in range(48):
                    rows.append(
                        {
                            "d": device_id,
                            "m": metric,
                            "ts": NOW - timedelta(hours=hour),
                            "v": Decimal(f"{hour}.{len(metric)}25"),
                        }
                    )
        for row in rows:
            s.execute(
                text(
                    f"INSERT INTO {schema}.readings "
                    "(device_id, metric, reading_ts, value) "
                    "VALUES (:d, :m, :ts, :v)"
                ),
                row,
            )
    return schema


def _all_readings(schema: str) -> set[tuple]:
    """Every reading as a comparable tuple, values as strings."""
    with session_scope() as s:
        rows = s.execute(
            text(
                f"SELECT device_id, metric, reading_ts, value "
                f"FROM {schema}.readings"
            )
        ).fetchall()
    return {(r.device_id, r.metric, r.reading_ts.isoformat(), str(r.value)) for r in rows}


def _apply_demo(schema: str):
    with session_scope() as s:
        captured = fresh._capture(s, schema, NOW)
    fresh._write_capture(captured)
    with session_scope() as s:
        removed = fresh._apply(s, schema, NOW)
    return captured, removed


class TestRoundTrip:
    def test_restore_returns_the_database_exactly(self, seeded):
        """The acceptance sequence: capture -> apply -> restore -> prove."""
        before = _all_readings(seeded)

        captured, removed = _apply_demo(seeded)
        during = _all_readings(seeded)

        assert removed > 0
        assert during != before
        assert len(before) - len(during) == removed

        with session_scope() as s:
            restored = fresh._restore(s, seeded, captured)

        assert restored == removed
        assert _all_readings(seeded) == before

    def test_values_survive_the_round_trip_unchanged(self, seeded):
        """A float would re-insert a subtly different number and still pass a
        count check. The capture stores strings for exactly this reason."""
        before = {
            (d, m, ts): v for (d, m, ts, v) in _all_readings(seeded)
        }
        captured, _ = _apply_demo(seeded)
        with session_scope() as s:
            fresh._restore(s, seeded, captured)
        after = {(d, m, ts): v for (d, m, ts, v) in _all_readings(seeded)}
        assert after == before

    def test_unrelated_rtl_readings_are_untouched(self, seeded):
        control_before = {r for r in _all_readings(seeded) if r[0] == CONTROL}
        _apply_demo(seeded)
        assert {r for r in _all_readings(seeded) if r[0] == CONTROL} == control_before

    def test_the_lagging_target_goes_STALE_not_absent(self, seeded):
        """The delicate case, and the one an over-eager assertion gets wrong.

        The lagging metric must keep its OLD readings and lose only the recent
        ones — that is what makes the RTL Stale. Deleting the metric entirely
        would make it NO_DATA, a different state with different copy and a
        different rank (ADR-009 D3). Its other feeds stay fresh, which is
        exactly the case where `device_last_updated` misreports the device.
        """
        _apply_demo(seeded)
        with session_scope() as s:
            newest = {
                row.metric: row.newest
                for row in s.execute(
                    text(
                        f"SELECT metric, MAX(reading_ts) AS newest "
                        f"FROM {seeded}.readings WHERE device_id = :d "
                        "GROUP BY metric"
                    ),
                    {"d": LAGGING_TARGET},
                ).fetchall()
            }

        # Every metric still reports — nothing became NO_DATA.
        assert set(newest) == set(METRICS)
        # The lagging one is old; the others are current.
        lag = NOW - newest["voltage"]
        assert lag >= fresh.LAGGING_AGE
        for metric in ("temperature", "current", "frequency"):
            assert NOW - newest[metric] < timedelta(hours=1)

    def test_the_blind_target_loses_a_metric_entirely(self, seeded):
        """NO_DATA is the ABSENCE of any row for a metric, not an old row."""
        _apply_demo(seeded)
        with session_scope() as s:
            count = s.execute(
                text(
                    f"SELECT COUNT(*) FROM {seeded}.readings "
                    "WHERE device_id = :d AND metric = 'frequency'"
                ),
                {"d": BLIND_TARGET},
            ).scalar_one()
        assert count == 0


class TestIdempotence:
    def test_restoring_twice_does_not_duplicate(self, seeded):
        """`ON CONFLICT DO NOTHING` against the UNIQUE constraint. A second
        restore converges instead of erroring or doubling."""
        before = _all_readings(seeded)
        captured, _ = _apply_demo(seeded)
        with session_scope() as s:
            first = fresh._restore(s, seeded, captured)
            second = fresh._restore(s, seeded, captured)
        assert first > 0
        assert second == 0
        assert _all_readings(seeded) == before

    def test_a_half_finished_apply_still_restores_cleanly(self, seeded):
        """The partial-failure case: capture written, delete never ran. The
        restore must be a no-op rather than a duplication."""
        before = _all_readings(seeded)
        with session_scope() as s:
            captured = fresh._capture(s, seeded, NOW)
        fresh._write_capture(captured)
        # crash here — nothing deleted
        with session_scope() as s:
            restored = fresh._restore(s, seeded, captured)
        assert restored == 0
        assert _all_readings(seeded) == before


class TestDeterminism:
    def test_the_same_now_selects_the_same_rows(self, seeded):
        with session_scope() as s:
            first = fresh._capture(s, seeded, NOW)
            second = fresh._capture(s, seeded, NOW)
        assert first == second

    def test_the_capture_is_the_set_the_delete_removes(self, seeded):
        """One predicate builds counting, capture and delete, so a capture can
        never cover a different set than the deletion it protects."""
        captured, removed = _apply_demo(seeded)
        assert len(captured) == removed


class TestCaptureSafety:
    def test_the_capture_is_verified_before_anything_is_deleted(self, seeded):
        before = _all_readings(seeded)
        with session_scope() as s:
            captured = fresh._capture(s, seeded, NOW)
        written = fresh._write_capture(captured)
        assert written == len(captured)
        # Reading and writing the capture changed nothing.
        assert _all_readings(seeded) == before

    def test_the_capture_file_is_plain_readable_data(self, seeded):
        captured, _ = _apply_demo(seeded)
        payload = json.loads(fresh.CAPTURE_PATH.read_text(encoding="utf-8"))
        assert len(payload) == len(captured)
        assert set(payload[0]) == {"device_id", "metric", "reading_ts", "value"}
