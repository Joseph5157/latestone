"""Device Management earns its width with information, not spacing.

Six short columns cannot fill a 2,100px workspace: Plant held 1,320px for
143px of text. Rather than distributing that void as padding, the table
carries the two facts an administrator actually opens this page for — when
the RTL last reported, and who is responsible for it.

Neither costs a new fetch per row. `FleetHealth.device_last_updated` is
already in hand from the one fleet-wide query the callback makes, and
assignments arrive as one bulk lookup rather than 120 per-device ones.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from callbacks.device_admin import DEVICE_ADMIN_COLUMNS, build_device_admin_rows
from services.monitoring_service import Freshness

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def device(device_id="plant-01-t1-d1", code="29017", status="active"):
    return SimpleNamespace(
        device_id=device_id,
        device_code=code,
        plant_id="plant-01",
        plant_name="Az Zour South CCGT",
        transformer_id="plant-01-t1",
        transformer_code="ku01",
        status=status,
    )


def health(last_updated, state=Freshness.FRESH):
    rollup = SimpleNamespace(state=state, label=lambda _unit: state.value.title())
    return SimpleNamespace(
        devices={"plant-01-t1-d1": rollup},
        device_last_updated={"plant-01-t1-d1": last_updated},
    )


def row_for(last_updated, assignments=None, **kwargs):
    return build_device_admin_rows(
        [device(**kwargs)], health(last_updated), assignments or {}, now=NOW
    )[0]


class TestColumnSpec:
    def test_the_two_new_columns_are_declared(self):
        assert [c["id"] for c in DEVICE_ADMIN_COLUMNS] == [
            "device", "plant", "transformer", "status",
            "freshness", "last_reading", "technician", "assign", "manage",
        ]

    def test_actions_stay_last(self):
        """Controls belong at the end of the row, after everything they
        act on. Two of them since FIX-1C, still last."""
        assert [c["id"] for c in DEVICE_ADMIN_COLUMNS[-2:]] == ["assign", "manage"]

    def test_each_action_is_separately_addressable(self):
        """The FIX-1C contract at the column level: a DataTable click is
        identified by `column_id`, so two actions sharing one column cannot
        be told apart. One column per action, or the drawers collide."""
        ids = [c["id"] for c in DEVICE_ADMIN_COLUMNS]
        assert "actions" not in ids
        assert len({"assign", "manage"} & set(ids)) == 2


class TestLastReading:
    def test_renders_a_compact_age(self):
        assert row_for(NOW - timedelta(hours=2, minutes=17))["last_reading"] == "2h 17m"

    def test_a_device_that_never_reported_says_so_rather_than_showing_a_dash(self):
        """"—" reads as a rendering gap; this is a real administrative state."""
        assert row_for(None)["last_reading"] == "No readings"

    def test_age_is_measured_from_the_render_instant_not_wall_clock(self):
        """The callback already threads one instant through freshness; the
        age column must not answer a different "now" from the state beside
        it."""
        assert row_for(NOW - timedelta(minutes=8))["last_reading"] == "8 min"


class TestTechnician:
    def test_shows_the_assigned_technician(self):
        assert row_for(NOW, {"plant-01-t1-d1": "t.mokoena"})["technician"] == "t.mokoena"

    def test_unassigned_is_stated_not_left_blank(self):
        """An empty cell is indistinguishable from a failed lookup, and
        unassigned RTLs are the queue Administration exists to clear."""
        assert row_for(NOW, {})["technician"] == "Unassigned"

    def test_an_assignment_for_another_device_does_not_leak_across_rows(self):
        assert row_for(NOW, {"plant-02-t1-d1": "someone.else"})["technician"] == "Unassigned"


class TestExistingContract:
    def test_freshness_and_state_are_unchanged(self):
        row = row_for(NOW - timedelta(minutes=5))
        assert row["_state"] == "fresh"
        assert row["freshness"] == "Fresh"

    def test_identity_columns_are_unchanged(self):
        row = row_for(NOW)
        assert row["device"] == "29017"
        assert row["plant"] == "Az Zour South CCGT"
        assert row["transformer"] == "ku01"


class TestSearchReachesTheNewColumns:
    def test_technician_is_searchable(self):
        """An administrator's most common question on this page is "what is
        assigned to this person"."""
        from callbacks.device_admin import SEARCHABLE_COLUMNS, filter_device_rows

        assert "technician" in SEARCHABLE_COLUMNS
        rows = [row_for(NOW, {"plant-01-t1-d1": "t.mokoena"})]
        assert filter_device_rows(rows, "mokoena", "all") == rows

    def test_age_text_is_not_searchable(self):
        """"2h 17m" is a rendering of a timestamp, not an identifier; matching
        it would filter on how long the page had been open."""
        from callbacks.device_admin import SEARCHABLE_COLUMNS

        assert "last_reading" not in SEARCHABLE_COLUMNS
