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
from services.admin_overview_service import AdminOverviewSummary
from tests.dash_tree import find_by_exact_class, find_by_id, text_of

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _summary() -> AdminOverviewSummary:
    return AdminOverviewSummary(
        total_devices=120,
        assigned_devices=115,
        unassigned_devices=5,
        active_technicians=4,
        recently_registered_devices=2,
        unassigned_rows=(),
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
