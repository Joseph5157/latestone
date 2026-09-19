"""A database failure on a listing page must explain itself.

Regression tests for audit finding NEW-08.

Routing and the device dashboard had error boundaries; the three listing
callbacks called services directly. The overview route performs no database
access of its own, so an outage *after* login first surfaced inside
a page's populate callback and raised through the Dash callback — leaving the
operator on a page that simply never filled in.

An empty table is not an adequate answer either: "no plants exist" and "we could
not reach the database" look identical. Each listing page now carries an error
slot the callback fills.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from callbacks.listings import (
    DEVICE_COLUMNS,
    NO_DEVICES_MESSAGE,
    NO_TRANSFORMERS_MESSAGE,
    TRANSFORMER_COLUMNS,
    build_device_rows,
    inventory_empty_notice,
    listing_outputs,
)
from pages import plant_detail, plants_overview, transformer_detail
from services.monitoring_service import fleet_health_from_rows

from tests.dash_tree import find_by_class, find_by_id, text_of

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


def _boom():
    raise RuntimeError("connection refused")


class _Device:
    """Only the fields `build_device_rows` reads."""

    def __init__(self, device_id: str, device_code: str, status: str = "active"):
        self.device_id = device_id
        self.device_code = device_code
        self.status = status


class TestListingOutputs:
    def test_success_returns_rows_and_no_error(self):
        rows, columns, error = listing_outputs(
            lambda: [{"id": "plant-01", "plant": "Alpha"}], TRANSFORMER_COLUMNS, "ctx"
        )
        assert rows == [{"id": "plant-01", "plant": "Alpha"}]
        assert columns is TRANSFORMER_COLUMNS
        assert error is None

    def test_failure_returns_an_error_panel_and_empty_rows(self):
        rows, columns, error = listing_outputs(_boom, TRANSFORMER_COLUMNS, "ctx")
        assert rows == []
        assert columns is TRANSFORMER_COLUMNS
        assert find_by_class(error, "status-panel--error"), "no error panel rendered"

    def test_failure_does_not_leak_internals_to_the_ui(self):
        """AGENTS.md: never expose stack traces, SQL or connection strings."""
        _, _, error = listing_outputs(_boom, TRANSFORMER_COLUMNS, "ctx")
        shown = text_of(error)
        assert "connection refused" not in shown
        assert "RuntimeError" not in shown
        assert "Traceback" not in shown

    def test_failure_is_logged_in_full(self, caplog):
        with caplog.at_level(logging.ERROR):
            listing_outputs(_boom, TRANSFORMER_COLUMNS, "loading plants")
        assert "loading plants" in caplog.text
        assert "connection refused" in caplog.text, "the real cause must reach the log"

    def test_an_empty_result_is_not_an_error(self):
        """No plants and unreachable database must not look the same."""
        rows, _, error = listing_outputs(lambda: [], TRANSFORMER_COLUMNS, "ctx")
        assert rows == []
        assert error is None


class TestEveryListingPageHasAnErrorSlot:
    @pytest.mark.parametrize(
        "layout,slot_id",
        [
            (plants_overview.layout(), "fleet-overview-error"),
            (plant_detail.layout("Plant"), "transformers-error"),
            (transformer_detail.layout("Plant", "T1", "p1"), "devices-error"),
        ],
    )
    def test_slot_is_present(self, layout, slot_id):
        assert find_by_id(layout, slot_id) is not None

    @pytest.mark.parametrize(
        "layout",
        [
            plants_overview.layout(),
            plant_detail.layout("Plant"),
            transformer_detail.layout("Plant", "T1", "p1"),
        ],
    )
    def test_slot_starts_empty(self, layout):
        """No error is shown until one happens."""
        assert find_by_class(layout, "status-panel--error") == []


# ---------------------------------------------------------------------------
# MOBBIN-UX-2 — hierarchy inventory empty states.
#
# A zero-row result is a real, distinct fact from a query failure and from a
# NO_DATA/STALE rollup: the first gets a truthful "nothing registered here"
# notice, the second already has its own error slot above, and the third is
# not empty at all — a row exists, it simply has bad telemetry.
# ---------------------------------------------------------------------------


class TestInventoryEmptyNotice:
    def test_plant_zero_transformers_shows_the_required_message(self):
        """1. Plant with zero transformers -> correct empty message, and the
        bare (headers-only) table is paired with it rather than left silent."""
        rows, columns, error = listing_outputs(lambda: [], TRANSFORMER_COLUMNS, "ctx")
        notice = inventory_empty_notice(rows, error, NO_TRANSFORMERS_MESSAGE)

        assert rows == []
        assert error is None
        assert columns is TRANSFORMER_COLUMNS
        assert notice is not None
        assert find_by_class(notice, "status-panel--empty"), "reuses the shared empty panel"
        assert "No transformers are registered for this plant." in text_of(notice)

    def test_transformer_zero_devices_shows_the_required_message(self):
        """2. Transformer with zero RTLs -> correct empty message."""
        rows, columns, error = listing_outputs(lambda: [], DEVICE_COLUMNS, "ctx")
        notice = inventory_empty_notice(rows, error, NO_DEVICES_MESSAGE)

        assert rows == []
        assert error is None
        assert notice is not None
        assert "No RTL devices are registered for this transformer." in text_of(notice)

    def test_non_empty_inventory_shows_no_notice(self):
        """3. A real row present -> the table is normal, no notice at all."""
        rows = [{
            "id": "t1", "transformer": "aa12", "devices": 1,
            "status": "active", "freshness": "Fresh",
        }]
        assert inventory_empty_notice(rows, None, NO_TRANSFORMERS_MESSAGE) is None

    def test_no_data_device_still_counts_as_present_inventory(self):
        """4. A device with NO_DATA telemetry is not an empty transformer —
        the row exists; only its freshness is bad. `fleet_health_from_rows`
        with no readings rolls every device up to NO_DATA, and that row must
        still suppress the notice."""
        health = fleet_health_from_rows([], now=NOW)
        rows = build_device_rows([_Device("d1", "29017")], health)

        assert rows[0]["freshness"].lower().startswith("no data")
        assert inventory_empty_notice(rows, None, NO_DEVICES_MESSAGE) is None

    def test_query_failure_is_never_converted_into_an_empty_state(self):
        """5. A raised exception must keep its own error presentation — the
        empty notice must not also appear underneath it."""
        rows, _columns, error = listing_outputs(_boom, TRANSFORMER_COLUMNS, "ctx")

        assert rows == []
        assert error is not None
        assert inventory_empty_notice(rows, error, NO_TRANSFORMERS_MESSAGE) is None


class TestEveryInventoryPageHasAnEmptySlot:
    @pytest.mark.parametrize(
        "layout,slot_id",
        [
            (plant_detail.layout("Plant"), "transformers-empty"),
            (transformer_detail.layout("Plant", "T1", "p1"), "devices-empty"),
        ],
    )
    def test_slot_is_present(self, layout, slot_id):
        assert find_by_id(layout, slot_id) is not None

    @pytest.mark.parametrize(
        "layout",
        [
            plant_detail.layout("Plant"),
            transformer_detail.layout("Plant", "T1", "p1"),
        ],
    )
    def test_slot_starts_empty(self, layout):
        """No notice is shown until the callback decides inventory is
        actually empty."""
        assert find_by_class(layout, "status-panel--empty") == []
