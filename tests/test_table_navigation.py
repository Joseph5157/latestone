"""Row-click navigation must follow the clicked row's identity, not its index.

Regression tests for audit finding NEW-02.

`entity_table` enables `sort_action="native"` and `filter_action="native"`.
Under those, `active_cell["row"]` indexes the *derived viewport* — the sorted,
filtered, paged view — while `State(table, "data")` stays in the original load
order. Looking the row up as `rows[active_cell["row"]]` therefore sent the user
to whichever entity happened to occupy that index before sorting.

Same failure shape as the custom end-date bug: no error, no empty page, just a
different plant's dashboard than the row that was clicked.

The fix is `active_cell["row_id"]`, which dash_table populates from each row's
`id` key and which is immune to viewport transforms.
"""
from __future__ import annotations

from dash import no_update

from callbacks.listings import (
    DEVICE_LINK_COLUMN,
    PLANT_LINK_COLUMN,
    TRANSFORMER_LINK_COLUMN,
    device_row_target,
    plant_row_target,
    transformer_row_target,
)

PLANT_CONTEXT = {"route": "plant", "plant_id": "plant-07"}


def cell(column_id: str, row: int = 0, row_id: str | None = None) -> dict:
    """An `active_cell` as dash_table emits it."""
    return {"row": row, "column_id": column_id, "row_id": row_id}


class TestPlantRowNavigation:
    def test_navigates_to_the_clicked_plant(self):
        target = plant_row_target(cell(PLANT_LINK_COLUMN, row=0, row_id="plant-07"))
        assert target == "/plants/plant-07"

    def test_sorted_viewport_still_navigates_to_the_visible_row(self):
        """The regression: viewport row 0 is not base-order row 0.

        Sorting Plant descending puts `plant-30` at the top; its index in the
        unsorted `data` is 29. Navigation must follow the id, not the index.
        """
        target = plant_row_target(cell(PLANT_LINK_COLUMN, row=0, row_id="plant-30"))
        assert target == "/plants/plant-30"

    def test_filtered_viewport_still_navigates_to_the_visible_row(self):
        target = plant_row_target(cell(PLANT_LINK_COLUMN, row=0, row_id="plant-12"))
        assert target == "/plants/plant-12"

    def test_click_outside_the_link_column_does_not_navigate(self):
        assert plant_row_target(cell("country", row_id="plant-07")) is no_update

    def test_no_active_cell_does_not_navigate(self):
        assert plant_row_target(None) is no_update

    def test_missing_row_id_does_not_navigate(self):
        """Defensive: navigating on a guess is worse than not navigating."""
        assert plant_row_target(cell(PLANT_LINK_COLUMN, row=3, row_id=None)) is no_update


class TestTransformerRowNavigation:
    def test_navigates_within_the_current_plant(self):
        target = transformer_row_target(
            cell(TRANSFORMER_LINK_COLUMN, row_id="plant-07-t1"), PLANT_CONTEXT
        )
        assert target == "/plants/plant-07/plant-07-t1"

    def test_sorted_viewport_still_navigates_to_the_visible_row(self):
        target = transformer_row_target(
            cell(TRANSFORMER_LINK_COLUMN, row=0, row_id="plant-07-t4"), PLANT_CONTEXT
        )
        assert target == "/plants/plant-07/plant-07-t4"

    def test_without_a_plant_in_context_it_does_not_navigate(self):
        target = transformer_row_target(
            cell(TRANSFORMER_LINK_COLUMN, row_id="plant-07-t1"), {}
        )
        assert target is no_update

    def test_click_outside_the_link_column_does_not_navigate(self):
        assert transformer_row_target(cell("status", row_id="plant-07-t1"), PLANT_CONTEXT) is no_update


class TestDeviceRowNavigation:
    def test_navigates_to_the_device_dashboard(self):
        target = device_row_target(cell(DEVICE_LINK_COLUMN, row_id="plant-07-t1-d1"))
        assert target == "/devices/plant-07-t1-d1"

    def test_sorted_viewport_still_navigates_to_the_visible_row(self):
        target = device_row_target(cell(DEVICE_LINK_COLUMN, row=0, row_id="plant-07-t1-d3"))
        assert target == "/devices/plant-07-t1-d3"

    def test_click_outside_the_link_column_does_not_navigate(self):
        assert device_row_target(cell("status", row_id="plant-07-t1-d1")) is no_update


class TestRowsCarryTheirIdentity:
    """`row_id` only exists if each row dict carries an `id` key."""

    def test_plant_rows_expose_an_id(self):
        from callbacks.listings import build_plant_rows

        class _P:
            def __init__(self, pid):
                self.plant_id = pid
                self.name = "Grand Coulee"
                self.country = "USA"
                self.primary_fuel = "Hydro"
                self.capacity_mw = 6809.0

        from services.monitoring_service import fleet_health_from_rows

        rows = build_plant_rows(
            [_P("plant-07")], {"plant-07": (1, 3)}, fleet_health_from_rows([])
        )
        assert rows[0]["id"] == "plant-07"

    def test_transformer_rows_expose_an_id(self):
        from callbacks.listings import build_transformer_rows

        class _T:
            transformer_id = "plant-07-t1"
            transformer_code = "un01"
            status = "active"

        from services.monitoring_service import fleet_health_from_rows

        rows = build_transformer_rows(
            [_T()], {"plant-07-t1": 3}, fleet_health_from_rows([])
        )
        assert rows[0]["id"] == "plant-07-t1"

    def test_device_rows_expose_an_id(self):
        from callbacks.listings import build_device_rows

        class _D:
            device_id = "plant-07-t1-d1"
            device_code = "29017"
            status = "active"

        rows = build_device_rows([_D()])
        assert rows[0]["id"] == "plant-07-t1-d1"
