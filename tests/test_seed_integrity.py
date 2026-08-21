"""Integrity checks on the seeded development dataset."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from config.metrics import METRIC_KEYS
from db.engine import session_scope

pytestmark = pytest.mark.db

SCHEMA = "plant_monitoring"


def _scalar(sql: str):
    with session_scope() as session:
        return session.execute(text(sql)).scalar_one()


class TestRowCounts:
    def test_thirty_plants(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.plants") == 30

    def test_seventy_one_transformers(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.transformers") == 71

    def test_one_hundred_twenty_devices(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.devices") == 120

    def test_total_readings(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.readings") == 1_383_360


class TestPerMetricCoverage:
    def test_every_metric_has_equal_coverage(self):
        with session_scope() as session:
            rows = session.execute(
                text(f"SELECT metric, COUNT(*) FROM {SCHEMA}.readings GROUP BY metric")
            ).all()
        counts = dict(rows)
        assert set(counts) == set(METRIC_KEYS)
        assert set(counts.values()) == {172_920}  # 120 devices x 1441 timestamps

    def test_every_device_has_every_metric(self):
        missing = _scalar(
            f"""
            SELECT COUNT(*) FROM {SCHEMA}.devices d
            CROSS JOIN (SELECT DISTINCT metric FROM {SCHEMA}.readings) m
            WHERE NOT EXISTS (
                SELECT 1 FROM {SCHEMA}.readings r
                WHERE r.device_id = d.device_id AND r.metric = m.metric
            )
            """
        )
        assert missing == 0


class TestSamplingCadence:
    def test_thirty_minute_spacing(self):
        irregular = _scalar(
            f"""
            SELECT COUNT(*) FROM (
              SELECT reading_ts - LAG(reading_ts) OVER (ORDER BY reading_ts) AS gap
              FROM {SCHEMA}.readings
              WHERE device_id = 'plant-01-t1-d1' AND metric = 'temperature'
            ) s WHERE gap IS NOT NULL AND gap <> INTERVAL '30 minutes'
            """
        )
        assert irregular == 0

    def test_thirty_days_of_history(self):
        with session_scope() as session:
            span = session.execute(
                text(
                    f"SELECT MAX(reading_ts) - MIN(reading_ts) FROM {SCHEMA}.readings "
                    "WHERE device_id = 'plant-01-t1-d1' AND metric = 'temperature'"
                )
            ).scalar_one()
        assert span == timedelta(days=30)


class TestEnergyIsCumulative:
    def test_no_metric_decreases_for_any_device(self):
        decreases = _scalar(
            f"""
            SELECT COUNT(*) FROM (
              SELECT value - LAG(value) OVER (
                       PARTITION BY device_id ORDER BY reading_ts
                     ) AS d
              FROM {SCHEMA}.readings WHERE metric = 'energy'
            ) s WHERE d < 0
            """
        )
        assert decreases == 0


class TestReferentialIntegrity:
    def test_reserved_client_naming_example_present(self):
        with session_scope() as session:
            row = session.execute(
                text(
                    f"""
                    SELECT t.transformer_code, d.device_code
                    FROM {SCHEMA}.devices d
                    JOIN {SCHEMA}.transformers t ON t.transformer_id = d.transformer_id
                    WHERE d.device_id = 'plant-01-t1-d1'
                    """
                )
            ).first()
        assert row == ("aa12", "29017")

    def test_device_codes_are_globally_unique(self):
        assert _scalar(f"SELECT COUNT(DISTINCT device_code) FROM {SCHEMA}.devices") == 120


class TestDeviceRegistrationHistory:
    """`devices.created_at` must carry real spread, not one backfilled instant.

    Before the seed set `created_at` explicitly, every device took migration
    002's `now()` server default and the whole fleet shared one registration
    timestamp — which made "registered in the last 7 days" report 120 of 120.
    These assertions fail on any database seeded before that fix; the remedy is
    a `--reset` reseed, since the insert deliberately does not overwrite
    existing rows.

    The dates are synthetic development seed history, not client registration
    records (see db.generators.registration_timestamp).
    """

    def test_registrations_are_not_all_identical(self):
        assert _scalar(f"SELECT COUNT(DISTINCT created_at) FROM {SCHEMA}.devices") > 1

    def test_every_device_has_a_distinct_registration(self):
        assert _scalar(f"SELECT COUNT(DISTINCT created_at) FROM {SCHEMA}.devices") == 120

    def test_history_spans_more_than_a_year(self):
        span = _scalar(
            f"SELECT MAX(created_at) - MIN(created_at) FROM {SCHEMA}.devices"
        )
        assert span > timedelta(days=365)

    def test_no_device_is_registered_in_the_future(self):
        assert _scalar(f"SELECT COUNT(*) FROM {SCHEMA}.devices WHERE created_at > now()") == 0

    def test_seeded_devices_are_unmodified_since_registration(self):
        """A freshly seeded device has never been edited."""
        assert _scalar(
            f"SELECT COUNT(*) FROM {SCHEMA}.devices WHERE updated_at <> created_at"
        ) == 0
