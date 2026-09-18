"""One filter surface on Device Management, and it is the toolbar.

The page shipped with two: the toolbar above the table, and the DataTable's
own native filter row directly beneath the header. The toolbar was inert, so
the working one was the row nobody designed. These cover the toolbar becoming
the real filter and the native row standing down — for this table only, since
every other table still relies on it.
"""
from dash import dash_table

import app as app_module
from callbacks import device_admin
from components.entity_table import entity_table
from tests.dash_tree import walk


def table_of(component):
    return next(n for n in walk(component) if isinstance(n, dash_table.DataTable))


class TestEntityTableFilterAction:
    def test_native_filtering_stays_the_default_for_every_other_table(self):
        """Fleet/Plants and the rest have no toolbar to fall back on."""
        assert table_of(entity_table("t", [{"name": "A", "id": "a"}], [])).filter_action == "native"

    def test_a_table_with_its_own_toolbar_can_stand_the_native_row_down(self):
        table = table_of(
            entity_table("t", [{"name": "A", "id": "a"}], [], filter_action="none")
        )
        assert table.filter_action == "none"

    def test_standing_down_the_filter_row_keeps_sorting(self):
        """Sorting is not a filter; losing it was never the intent."""
        table = table_of(
            entity_table("t", [{"name": "A", "id": "a"}], [], filter_action="none")
        )
        assert table.sort_action == "native"


class TestPageWiring:
    def test_device_management_renders_no_native_filter_row(self):
        from pages import device_admin as page

        assert table_of(page.layout()).filter_action == "none"

    def test_populate_reads_the_toolbar_it_renders(self):
        callbacks = app_module.app._callback_list
        populate = next(
            c for c in callbacks if "device-admin-table.data" in c["output"]
        )
        # DEVICE-FILTERS-1 added the column filters; the full set is pinned
        # in tests/test_device_admin_column_filters.py.
        assert {(i["id"], i["property"]) for i in populate["inputs"]} >= {
            ("page-context", "data"),
            ("device-admin-search", "value"),
            ("device-admin-status-filter", "value"),
        }


class TestSummaryLine:
    def test_unfiltered_summary_states_the_population(self):
        assert device_admin.device_admin_summary(120, 120, 118, 2) == (
            "120 devices — 118 active, 2 inactive"
        )

    def test_filtered_summary_leads_with_what_is_on_screen(self):
        """The totals stay visible: a filtered table must not look like a
        fleet that shrank."""
        assert device_admin.device_admin_summary(7, 120, 118, 2) == (
            "Showing 7 of 120 devices — 118 active, 2 inactive"
        )

    def test_a_filter_that_matches_nothing_says_so(self):
        assert device_admin.device_admin_summary(0, 120, 118, 2) == (
            "No devices match this filter — 120 devices, 118 active, 2 inactive"
        )
