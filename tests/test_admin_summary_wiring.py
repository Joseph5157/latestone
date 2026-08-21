"""The administration card row on the Fleet Overview: slot, clock, isolation.

The component tests cover what the cards say. These cover how they reach the
page — in particular the guarantee that administration is a *secondary* axis
here: if its queries fail, the operator still gets the plant table and the
freshness figures they opened the page for.
"""
from __future__ import annotations

from datetime import datetime, timezone

from callbacks import listings
from pages import plants_overview
from repositories.plant_monitoring_repository import AdminDeviceRow
from services.admin_overview_service import AdminOverviewSummary
from tests.dash_tree import (
    find_by_class,
    find_by_exact_class,
    find_by_id,
    links,
    text_of,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _row(n: int = 1) -> AdminDeviceRow:
    return AdminDeviceRow(
        device_id=f"plant-0{n}-t1-d1",
        device_code=f"2901{n}",
        status="active",
        transformer_id=f"plant-0{n}-t1",
        transformer_code="t1",
        plant_id=f"plant-0{n}",
        plant_name=f"Plant {n}",
    )


def _summary(rows: tuple[AdminDeviceRow, ...] = ()) -> AdminOverviewSummary:
    return AdminOverviewSummary(
        total_devices=120,
        assigned_devices=115,
        unassigned_devices=5,
        active_technicians=4,
        recently_registered_devices=2,
        unassigned_rows=rows,
    )


class TestPageSlot:
    def test_layout_carries_the_admin_summary_slot(self):
        assert find_by_id(plants_overview.layout(), "admin-summary") is not None

    def test_slot_starts_empty(self):
        """Layout performs no queries, so the cards can only exist after the
        listing callback has run — the same contract as fleet-kpis."""
        slot = find_by_id(plants_overview.layout(), "admin-summary")
        assert not slot.children

    def test_slot_sits_between_fleet_health_and_needs_attention(self):
        """Administration reads after the monitoring figures it is not part
        of, and before the exception list."""
        ids = [
            n.id
            for n in plants_overview.layout().children
            if getattr(n, "id", None)
            in {"fleet-health-distribution", "admin-summary", "needs-attention"}
        ]
        assert ids == ["fleet-health-distribution", "admin-summary", "needs-attention"]


class TestAdminSummaryOutput:
    def test_renders_the_cards_from_the_service_summary(self, monkeypatch):
        monkeypatch.setattr(
            listings.admin_overview_service,
            "get_admin_overview",
            lambda now=None: _summary(),
        )
        block = listings.admin_summary_output(NOW)
        assert len(find_by_exact_class(block, "kpi-card")) == 3
        assert "5 unassigned" in text_of(block)

    def test_threads_the_render_instant_into_the_service(self, monkeypatch):
        """One instant per render: the registration window must be evaluated
        against the same moment as the freshness figures beside it, not a
        second clock read."""
        seen = {}

        def capture(now=None):
            seen["now"] = now
            return _summary()

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", capture
        )
        listings.admin_summary_output(NOW)
        assert seen["now"] == NOW

    def test_failure_returns_nothing_rather_than_raising(self, monkeypatch):
        def boom(now=None):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", boom
        )
        assert listings.admin_summary_output(NOW) is None

    def test_failure_does_not_leak_internals(self, monkeypatch, caplog):
        """CLAUDE.md: never expose stack traces, SQL or connection strings.
        The cause is logged in full; nothing reaches the page."""

        def boom(now=None):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", boom
        )
        with caplog.at_level("ERROR"):
            result = listings.admin_summary_output(NOW)
        assert result is None
        assert "connection refused" in caplog.text

    def test_failure_renders_no_competing_error_panel(self, monkeypatch):
        """The listing owns the one error panel on this page. A supporting card
        row failing must not imply the whole page is broken."""

        def boom(now=None):
            raise RuntimeError("down")

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", boom
        )
        assert listings.admin_summary_output(NOW) is None


class TestAdministrationDoesNotDisruptMonitoring:
    """Boundary: administration is secondary on this page."""

    def test_admin_failure_leaves_the_listing_boundary_untouched(self, monkeypatch):
        """`admin_summary_output` swallows its own failure, so a build() that
        calls it still returns rows — the plant table survives."""

        def boom(now=None):
            raise RuntimeError("admin down")

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", boom
        )

        def build():
            listings.admin_summary_output(NOW)
            return [{"id": "plant-01", "plant": "Alpha"}]

        rows, _columns, error = listings.listing_outputs(
            build, listings.PLANT_COLUMNS, "ctx"
        )
        assert rows == [{"id": "plant-01", "plant": "Alpha"}]
        assert error is None

    def test_admin_query_is_not_a_second_clock_read(self, monkeypatch):
        """Regression guard: calling get_admin_overview() with no `now` would
        let the registration window drift from the page's render instant."""
        seen = []
        monkeypatch.setattr(
            listings.admin_overview_service,
            "get_admin_overview",
            lambda now=None: seen.append(now) or _summary(),
        )
        listings.admin_summary_output(NOW)
        assert seen == [NOW]
        assert seen[0] is not None


class TestPopulationsStayApartOnThePage:
    def test_admin_block_does_not_restate_the_monitoring_device_count(
        self, monkeypatch
    ):
        """Both populations are 120 on development data. The admin row must
        still never render a bare 120 that could be read as the Devices card's
        figure restated."""
        monkeypatch.setattr(
            listings.admin_overview_service,
            "get_admin_overview",
            lambda now=None: _summary(),
        )
        block = listings.admin_summary_output(NOW)
        values = [
            text_of(c.children[1]) for c in find_by_exact_class(block, "kpi-card")
        ]
        assert "120" not in values
        assert "115 of 120 RTLs assigned" in text_of(block)


class TestUnassignedPanelInTheSlot:
    """ADMIN-3: the exception list ships in the same slot as the cards."""

    def _rendered(self, monkeypatch, rows=()):
        monkeypatch.setattr(
            listings.admin_overview_service,
            "get_admin_overview",
            lambda now=None: _summary(rows),
        )
        return listings.admin_summary_output(NOW)

    def test_panel_renders_below_the_cards(self, monkeypatch):
        block = self._rendered(monkeypatch, (_row(1),))
        assert "Unassigned RTLs" in text_of(block)

    def test_cards_come_first(self, monkeypatch):
        """Counts, then the list they summarise — the same order the page
        already reads in."""
        block = self._rendered(monkeypatch, (_row(1),))
        rendered = text_of(block)
        assert rendered.index("Administration") < rendered.index("Unassigned RTLs")

    def test_panel_shows_the_rows_the_service_supplied(self, monkeypatch):
        block = self._rendered(monkeypatch, (_row(1), _row(2)))
        assert len(find_by_exact_class(block, "unassigned-rtls__row")) == 2

    def test_panel_and_cards_read_one_summary(self, monkeypatch):
        """One `AdminOverviewSummary` per render feeds both. A second call
        would be a second set of queries, and the card's count could disagree
        with the list beneath it."""
        calls = []

        def once(now=None):
            calls.append(now)
            return _summary((_row(1),))

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", once
        )
        listings.admin_summary_output(NOW)
        assert calls == [NOW]

    def test_assign_action_targets_the_existing_workflow(self, monkeypatch):
        block = self._rendered(monkeypatch, (_row(1),))
        hrefs = dict(links(block))
        assert hrefs["Assign"] == "/admin/devices?assign=plant-01-t1-d1"

    def test_view_all_devices_targets_the_existing_route(self, monkeypatch):
        block = self._rendered(monkeypatch, (_row(1),))
        hrefs = dict(links(block))
        assert hrefs["View all devices"] == "/admin/devices"

    def test_panel_disappears_with_the_cards_on_failure(self, monkeypatch):
        """One boundary, one outcome. A panel surviving a failed read would
        stand alone under no heading and no counts."""

        def boom(now=None):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", boom
        )
        assert listings.admin_summary_output(NOW) is None

    def test_panel_failure_does_not_blank_the_plant_table(self, monkeypatch):
        def boom(now=None):
            raise RuntimeError("admin down")

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", boom
        )

        def build():
            listings.admin_summary_output(NOW)
            return [{"id": "plant-01", "plant": "Alpha"}]

        rows, _columns, error = listings.listing_outputs(
            build, listings.PLANT_COLUMNS, "ctx"
        )
        assert rows == [{"id": "plant-01", "plant": "Alpha"}]
        assert error is None

    def test_panel_failure_renders_no_competing_error_panel(self, monkeypatch):
        def boom(now=None):
            raise RuntimeError("down")

        monkeypatch.setattr(
            listings.admin_overview_service, "get_admin_overview", boom
        )
        block = listings.admin_summary_output(NOW)
        assert find_by_class(block or [], "listing-error") == []

    def test_empty_exception_list_still_renders_the_neutral_state(self, monkeypatch):
        monkeypatch.setattr(
            listings.admin_overview_service,
            "get_admin_overview",
            lambda now=None: AdminOverviewSummary(
                total_devices=120,
                assigned_devices=120,
                unassigned_devices=0,
                active_technicians=4,
                recently_registered_devices=2,
                unassigned_rows=(),
            ),
        )
        block = listings.admin_summary_output(NOW)
        assert "All managed RTLs are currently assigned." in text_of(block)
