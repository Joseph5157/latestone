"""The operational-event demo seed (CC-1 Phase 9, §13 of the gate).

Two things are under test and only two: that the seed crosses the CANONICAL
boundary rather than reaching around it, and that its batch actually
exercises every presentation path the panel has. Whether the numbers look
plausible is a judgement, not an assertion.
"""
from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timezone

import pytest

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_STARTUP,
)
from db import seed_events_demo as seed
from services import command_center_service as svc
from services import event_semantics

NOW = datetime(2026, 8, 29, 14, 30, tzinfo=timezone.utc)


class TestIngestionBoundary:
    def test_the_seed_writes_only_through_ingest_event(self):
        """ADR-007: `ingest_event()`, never `insert_device_event()`.

        Structural, because this is exactly the rule a hurried edit breaks:
        calling the repository directly would be shorter, would work, and
        would silently skip validation, identity resolution and the startup
        projection — producing demo rows that are not the same shape as real
        ones, which makes the whole seed worthless as verification.
        """
        tree = ast.parse(
            pathlib.Path(seed.__file__).read_text(encoding="utf-8")
        )
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        } | {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "ingest_event" in called
        for forbidden in (
            "insert_device_event",
            "activate_device_active_state",
            "execute",
        ):
            assert forbidden not in called

    def test_events_are_seeded_as_normalized_events(self, monkeypatch):
        captured = []
        monkeypatch.setattr(
            seed, "list_all_devices", lambda: _fake_devices(20)
        )
        monkeypatch.setattr(seed, "_already_seeded", lambda: False)
        monkeypatch.setattr(
            seed, "ingest_event", lambda e: captured.append(e) or _ok()
        )

        seed.seed(now=NOW)

        assert len(captured) == len(seed.DEMO_EVENTS)
        assert all(
            isinstance(e, seed.NormalizedEvent) for e in captured
        )

    def test_every_seeded_timestamp_is_timezone_aware(self, monkeypatch):
        """INGEST-D4 rejects naive timestamps at the boundary. A seed that
        produced them would fail loudly — this fails sooner."""
        captured = []
        monkeypatch.setattr(seed, "list_all_devices", lambda: _fake_devices(20))
        monkeypatch.setattr(seed, "_already_seeded", lambda: False)
        monkeypatch.setattr(
            seed, "ingest_event", lambda e: captured.append(e) or _ok()
        )

        seed.seed(now=NOW)

        assert all(e.event_ts.tzinfo is not None for e in captured)

    def test_every_seeded_event_is_stamped_as_demo_data(self, monkeypatch):
        captured = []
        monkeypatch.setattr(seed, "list_all_devices", lambda: _fake_devices(20))
        monkeypatch.setattr(seed, "_already_seeded", lambda: False)
        monkeypatch.setattr(
            seed, "ingest_event", lambda e: captured.append(e) or _ok()
        )

        seed.seed(now=NOW)

        assert {e.source for e in captured} == {seed.DEMO_SOURCE}


class TestQuarantineRowIsGenuine:
    def test_the_unregistered_row_is_not_declared_invalid_uid(self, monkeypatch):
        """It is sent as an ordinary event carrying a UID that matches
        nothing, and the EXISTING resolution retypes it (INGEST-D2). Hand-
        declaring `invalid_uid` would seed a row that never went through the
        code path it is meant to demonstrate."""
        captured = []
        monkeypatch.setattr(seed, "list_all_devices", lambda: _fake_devices(20))
        monkeypatch.setattr(seed, "_already_seeded", lambda: False)
        monkeypatch.setattr(
            seed, "ingest_event", lambda e: captured.append(e) or _ok()
        )

        seed.seed(now=NOW)

        unattributed = [e for e in captured if e.device_id is None]
        assert unattributed, "the batch must include an unregistered UID"
        for event in unattributed:
            assert event.event_type != "invalid_uid"
            assert event.reported_uid == seed.UNREGISTERED_UID
            assert event.transformer_id is None


class TestBatchCoverage:
    def test_the_batch_exercises_every_presentation_path(self):
        types = {e.event_type for e in seed.DEMO_EVENTS}
        # Critical, Warning, and two neutral informational types.
        assert EVENT_TYPE_POWER_DOWN in types
        assert EVENT_TYPE_BATTERY_LOW in types
        assert EVENT_TYPE_STARTUP in types
        assert EVENT_TYPE_CHECK_IN in types
        # And the quarantine row, which arrives by resolution rather than
        # by declaration — hence a slot with no device rather than a type.
        assert any(e.device_slot is None for e in seed.DEMO_EVENTS)

    def test_every_seeded_type_is_one_the_panel_can_read(self):
        """A type outside `mapped_event_types()` is never queried, so
        seeding one would produce a row nobody can see."""
        mapped = set(event_semantics.mapped_event_types())
        for demo in seed.DEMO_EVENTS:
            assert demo.event_type in mapped

    def test_every_presentation_path_lands_inside_the_VISIBLE_window(self):
        """Not merely somewhere in the batch.

        The first version of this seed put the unregistered UID oldest, so
        the one row whose entire point is that it carries no link was the
        one row that never reached the panel — and the batch-level
        assertion above passed anyway. What the seed exists for is being
        LOOKED at, so the window is what has to be covered.
        """
        visible = sorted(seed.DEMO_EVENTS, key=lambda e: e.minutes_ago)[
            : svc.RECENT_EVENT_ROWS
        ]
        types = {e.event_type for e in visible}
        assert EVENT_TYPE_POWER_DOWN in types     # Critical
        assert EVENT_TYPE_BATTERY_LOW in types    # Warning
        assert EVENT_TYPE_STARTUP in types        # neutral
        assert any(e.device_slot is None for e in visible)   # no-link row
        assert any(e.battery_voltage for e in visible)       # detail payload

    def test_the_batch_overflows_the_panel_so_the_bound_is_visible(self):
        """More events than the panel shows, so newest-first truncation and
        the scroll region are looked at rather than only unit-tested."""
        assert len(seed.DEMO_EVENTS) > svc.RECENT_EVENT_ROWS

    def test_timestamps_are_distinct_so_ordering_is_observable(self):
        offsets = [e.minutes_ago for e in seed.DEMO_EVENTS]
        assert len(set(offsets)) == len(offsets)

    def test_voltages_are_only_ever_carried_never_classified(self):
        """The seed picks voltages for realism. Some sit above the device
        thresholds and some below, and NONE of them may change how a row is
        presented — the event type alone decides that."""
        with_voltage = [e for e in seed.DEMO_EVENTS if e.battery_voltage]
        assert with_voltage
        assert any(e.battery_voltage > 3.61 for e in with_voltage)
        assert any(e.battery_voltage < 3.61 for e in with_voltage)


class TestContainment:
    def test_a_second_run_is_refused_rather_than_silently_doubling(
        self, monkeypatch
    ):
        monkeypatch.setattr(seed, "list_all_devices", lambda: _fake_devices(20))
        monkeypatch.setattr(seed, "_already_seeded", lambda: True)
        monkeypatch.setattr(seed, "ingest_event", lambda e: _ok())

        with pytest.raises(seed.DemoSeedRefused):
            seed.seed(now=NOW)

    def test_a_second_run_is_allowed_when_asked_for_explicitly(
        self, monkeypatch
    ):
        monkeypatch.setattr(seed, "list_all_devices", lambda: _fake_devices(20))
        monkeypatch.setattr(seed, "_already_seeded", lambda: True)
        monkeypatch.setattr(seed, "ingest_event", lambda e: _ok())

        assert seed.seed(now=NOW, again=True)

    def test_it_refuses_rather_than_seeding_a_fleet_it_does_not_have(
        self, monkeypatch
    ):
        monkeypatch.setattr(seed, "list_all_devices", lambda: _fake_devices(2))
        monkeypatch.setattr(seed, "_already_seeded", lambda: False)
        monkeypatch.setattr(seed, "ingest_event", lambda e: _ok())

        with pytest.raises(seed.DemoSeedRefused):
            seed.seed(now=NOW)

    def test_it_offers_no_way_to_delete_events(self):
        """Event persistence is append-only (INGEST-D3). A `--reset` here
        would model something the ingestion path cannot do.

        Asserted against the argparse DECLARATIONS, not the file text: the
        module docstring names the other seeds' `--reset` flags to explain
        why this one has none, and prose about a rule must not be
        indistinguishable from breaking it — the same lesson the Command
        Center's threshold guard already learned.
        """
        tree = ast.parse(
            pathlib.Path(seed.__file__).read_text(encoding="utf-8")
        )
        declared_flags = {
            arg.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            for arg in node.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        }
        assert "--reset" not in declared_flags
        assert declared_flags == {"--again"}


def _fake_devices(count: int) -> list:
    from types import SimpleNamespace

    return [
        SimpleNamespace(
            device_id=f"plant-01-t1-d{i}",
            device_code=f"29{i:03d}",
            transformer_id="plant-01-t1",
        )
        for i in range(count)
    ]


def _ok():
    from types import SimpleNamespace

    return SimpleNamespace(
        outcome="recorded", event_id=1, resolved_device_id=None, activated_at=None
    )
