"""Unassigned RTLs panel — the actionable half of the Administration block.

The cards above it say *how many* RTLs have nobody responsible for them; this
panel says *which*, and hands each one to the assignment workflow that already
exists on Device Management. Two things are therefore load-bearing here and
have their own guards: the panel derives every figure from the one
`AdminOverviewSummary` the callback already built (it must never issue a query
of its own), and the Assign action must carry a device context the existing
drawer can resolve.
"""
from __future__ import annotations

import inspect

from components import unassigned_rtls
from components.unassigned_rtls import (
    EMPTY_MESSAGE,
    UNASSIGNED_COLUMNS,
    unassigned_rtl_panel,
    unassigned_summary_text,
)
from repositories.plant_monitoring_repository import AdminDeviceRow
from routes import device_assign_href
from services.admin_overview_service import AdminOverviewSummary
from tests.dash_tree import find_by_class, find_by_exact_class, links, text_of, walk


def row(n: int = 1, status: str = "active") -> AdminDeviceRow:
    return AdminDeviceRow(
        device_id=f"plant-0{n}-t1-d1",
        device_code=f"2901{n}",
        status=status,
        transformer_id=f"plant-0{n}-t1",
        transformer_code="t1",
        plant_id=f"plant-0{n}",
        plant_name=f"Plant {n}",
    )


def summary(
    total=120,
    assigned=96,
    unassigned=24,
    technicians=5,
    recent=2,
    rows=None,
) -> AdminOverviewSummary:
    return AdminOverviewSummary(
        total_devices=total,
        assigned_devices=assigned,
        unassigned_devices=unassigned,
        active_technicians=technicians,
        recently_registered_devices=recent,
        unassigned_rows=tuple(row(n) for n in range(1, 6)) if rows is None else rows,
    )


def panel(**kwargs):
    return unassigned_rtl_panel(summary(**kwargs))


def header_labels(block) -> list[str]:
    return [th.children for th in walk(block) if type(th).__name__ == "Th"]


def body_rows(block) -> list:
    return find_by_exact_class(block, "unassigned-rtls__row")


class TestPanelStructure:
    def test_carries_its_own_heading(self):
        assert "Unassigned RTLs" in text_of(panel())

    def test_summary_line_states_the_real_count(self):
        assert "24 RTLs require assignment" in text_of(panel())

    def test_expected_column_labels(self):
        assert header_labels(panel()) == list(UNASSIGNED_COLUMNS)

    def test_columns_are_the_five_the_spec_names(self):
        assert UNASSIGNED_COLUMNS == (
            "RTL UID",
            "Plant",
            "Transformer",
            "Status",
            "Action",
        )

    def test_one_row_per_supplied_row(self):
        assert len(body_rows(panel())) == 5

    def test_rtl_uid_column_shows_the_device_code(self):
        first = body_rows(panel())[0]
        assert text_of(first.children[0]) == "29011"

    def test_internal_device_id_is_never_the_visible_identifier(self):
        """`device_id` is a hierarchy path, not a business identifier. It may
        appear in an href, never as text the operator is asked to read."""
        cells = body_rows(panel())[0].children
        visible = " ".join(text_of(c) for c in cells)
        assert "plant-01-t1-d1" not in visible

    def test_plant_and_transformer_render(self):
        cells = body_rows(panel())[0].children
        assert text_of(cells[1]) == "Plant 1"
        assert text_of(cells[2]) == "t1"

    def test_status_renders_the_administrative_status(self):
        assert text_of(body_rows(panel())[0].children[3]) == "Active"

    def test_missing_status_does_not_render_an_empty_cell(self):
        block = unassigned_rtl_panel(summary(rows=(row(1, status=""),)))
        assert text_of(body_rows(block)[0].children[3]).strip() != ""


class TestAssignAction:
    def test_every_row_exposes_an_assign_action(self):
        assert len(find_by_class(panel(), "unassigned-rtls__assign")) == 5

    def test_assign_targets_the_existing_device_management_workflow(self):
        hrefs = dict(links(panel()))
        assert hrefs["Assign"].startswith("/admin/devices?")

    def test_assign_carries_this_row_device_context(self):
        """The drawer resolves the device from this link. A row whose action
        names a different device (or none) would open the wrong assignment."""
        assign_links = find_by_class(panel(), "unassigned-rtls__assign")
        assert [link.href for link in assign_links] == [
            device_assign_href(row(n).device_id) for n in range(1, 6)
        ]

    def test_no_row_action_invents_a_second_assignment_route(self):
        for _label, href in links(panel()):
            assert "/admin/assignments" not in href


class TestViewAllDevices:
    def test_panel_links_to_device_management(self):
        hrefs = dict(links(panel()))
        assert hrefs["View all devices"] == "/admin/devices"

    def test_link_is_present_even_when_nothing_is_unassigned(self):
        """The way out of the panel does not depend on the panel having work
        in it."""
        hrefs = dict(links(panel(assigned=120, unassigned=0, rows=())))
        assert hrefs["View all devices"] == "/admin/devices"


class TestEmptyState:
    def test_zero_unassigned_states_the_neutral_outcome(self):
        block = panel(assigned=120, unassigned=0, rows=())
        assert EMPTY_MESSAGE in text_of(block)

    def test_zero_unassigned_renders_no_table_shell(self):
        block = panel(assigned=120, unassigned=0, rows=())
        assert header_labels(block) == []
        assert body_rows(block) == []

    def test_zero_unassigned_is_not_an_error(self):
        """No error panel, no warning wording — a fully assigned fleet is a
        good outcome, not a failure to load."""
        block = panel(assigned=120, unassigned=0, rows=())
        assert find_by_class(block, "listing-error") == []
        assert "unavailable" not in text_of(block).lower()

    def test_a_count_with_no_sample_rows_still_avoids_a_table_shell(self):
        """Defensive: a caller asking the service for zero sample rows must
        not produce headers over nothing."""
        block = panel(rows=())
        assert header_labels(block) == []
        assert "24 RTLs require assignment" in text_of(block)


class TestSummaryWording:
    def test_singular_unassigned_rtl(self):
        assert unassigned_summary_text(
            summary(assigned=119, unassigned=1, rows=(row(1),))
        ).startswith("1 RTL requires assignment")

    def test_plural_unassigned_rtls(self):
        assert unassigned_summary_text(summary()).startswith(
            "24 RTLs require assignment"
        )

    def test_says_so_when_the_list_is_a_sample_of_a_longer_one(self):
        """24 unassigned but 5 rows shown. Silently listing five would read as
        the whole problem."""
        assert "5" in unassigned_summary_text(summary())

    def test_no_sample_note_when_the_list_is_complete(self):
        text = unassigned_summary_text(
            summary(assigned=117, unassigned=3, rows=tuple(row(n) for n in (1, 2, 3)))
        )
        assert text == "3 RTLs require assignment"

    def test_zero_unassigned_uses_the_empty_message(self):
        assert (
            unassigned_summary_text(summary(assigned=120, unassigned=0, rows=()))
            == EMPTY_MESSAGE
        )

    def test_no_invented_risk_or_severity_wording(self):
        text = text_of(panel()).lower()
        for word in ("critical", "warning", "risk", "severe", "urgent", "alert"):
            assert word not in text


class TestServiceConsumption:
    def test_panel_never_reaches_for_a_repository(self):
        """Presentation only. A query here would be a second, independently
        limited opinion about the same exception list."""
        source = inspect.getsource(unassigned_rtls)
        assert "repositories" not in source
        assert "repo." not in source

    def test_count_comes_from_the_summary_not_from_len_of_the_rows(self):
        """The service caps the sample. Counting the rows would report 5
        unassigned RTLs on a fleet that has 24."""
        assert "24 RTLs" in unassigned_summary_text(summary())

    def test_panel_does_not_recompute_assignment_coverage(self):
        """assigned/total belong to the RTL Assignment card. Restating them
        here would be a second place for the same figures to drift."""
        text = text_of(panel())
        assert "96" not in text
        assert "120" not in text

    def test_rows_render_in_the_order_the_service_supplied(self):
        given = (row(3), row(1), row(2))
        block = unassigned_rtl_panel(summary(rows=given))
        codes = [text_of(r.children[0]) for r in body_rows(block)]
        assert codes == ["29013", "29011", "29012"]

    def test_respects_the_limited_row_set(self):
        """Whatever the service handed over is what renders — the panel never
        goes looking for the rest."""
        given = tuple(row(n) for n in (1, 2))
        block = unassigned_rtl_panel(summary(rows=given))
        assert len(body_rows(block)) == 2


class TestPopulationStaysManagedRtls:
    def test_panel_never_calls_them_devices(self):
        """Except in the link to the Device Management page, which names a
        destination rather than a population."""
        rendered = text_of(panel()).lower().replace("view all devices", "")
        assert "device" not in rendered
