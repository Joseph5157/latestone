"""A database failure on a listing page must explain itself.

Regression tests for audit finding NEW-08.

Routing and the device dashboard had error boundaries; the three listing
callbacks called services directly. The overview route performs no database
access of its own, so an outage *after* login first surfaced inside
`populate_overview()` and raised through the Dash callback — leaving the
operator on a page that simply never filled in.

An empty table is not an adequate answer either: "no plants exist" and "we could
not reach the database" look identical. Each listing page now carries an error
slot the callback fills.
"""
from __future__ import annotations

import logging

import pytest

from callbacks.listings import PLANT_COLUMNS, listing_outputs
from pages import plant_detail, plants_overview, transformer_detail

from tests.dash_tree import find_by_class, find_by_id, text_of


def _boom():
    raise RuntimeError("connection refused")


class TestListingOutputs:
    def test_success_returns_rows_and_no_error(self):
        rows, columns, error = listing_outputs(
            lambda: [{"id": "plant-01", "plant": "Alpha"}], PLANT_COLUMNS, "ctx"
        )
        assert rows == [{"id": "plant-01", "plant": "Alpha"}]
        assert columns is PLANT_COLUMNS
        assert error is None

    def test_failure_returns_an_error_panel_and_empty_rows(self):
        rows, columns, error = listing_outputs(_boom, PLANT_COLUMNS, "ctx")
        assert rows == []
        assert columns is PLANT_COLUMNS
        assert find_by_class(error, "status-panel--error"), "no error panel rendered"

    def test_failure_does_not_leak_internals_to_the_ui(self):
        """AGENTS.md: never expose stack traces, SQL or connection strings."""
        _, _, error = listing_outputs(_boom, PLANT_COLUMNS, "ctx")
        shown = text_of(error)
        assert "connection refused" not in shown
        assert "RuntimeError" not in shown
        assert "Traceback" not in shown

    def test_failure_is_logged_in_full(self, caplog):
        with caplog.at_level(logging.ERROR):
            listing_outputs(_boom, PLANT_COLUMNS, "loading plants")
        assert "loading plants" in caplog.text
        assert "connection refused" in caplog.text, "the real cause must reach the log"

    def test_an_empty_result_is_not_an_error(self):
        """No plants and unreachable database must not look the same."""
        rows, _, error = listing_outputs(lambda: [], PLANT_COLUMNS, "ctx")
        assert rows == []
        assert error is None


class TestEveryListingPageHasAnErrorSlot:
    @pytest.mark.parametrize(
        "layout,slot_id",
        [
            (plants_overview.layout(), "plants-error"),
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
