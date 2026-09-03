"""The administration card row on the Fleet Overview: slot, clock, isolation.

The component tests cover what the cards say. These cover how they reach the
page — in particular the guarantee that administration is a *secondary* axis
here: if its queries fail, the operator still gets the plant table and the
freshness figures they opened the page for.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone

import pytest

from callbacks import listings
from pages import plants_overview
from repositories.plant_monitoring_repository import AdminDeviceRow
from services.admin_overview_service import AdminOverviewSummary
from tests.auth_test_support import no_trusted_session, trusted_session
from tests.dash_tree import (
    find_by_class,
    find_by_exact_class,
    find_by_id,
    links,
    text_of,
    walk,
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

    def test_slot_sits_after_monitoring_needs_attention_and_inventory(self):
        """ENT-2 reading order: state -> exceptions -> hierarchy -> inventory
        -> administration. Administration is last and secondary."""
        ids = [
            n.id
            for n in walk(plants_overview.layout())
            if getattr(n, "id", None)
            in {"fleet-systemic-state", "needs-attention", "admin-summary", "fleet-plants"}
        ]
        assert ids == [
            "fleet-systemic-state", "needs-attention", "fleet-plants", "admin-summary"
        ]


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
        """AGENTS.md: never expose stack traces, SQL or connection strings.
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


# ==========================================================================
# ROLE-3 Task 12 / AUTH-HARDEN-1 — the Administration block is
# Administrator-only content
#
# `admin_summary_output` swallows its own failures and returns None, so a
# test that only asserted "absent for a technician" would pass even if the
# block were still being built and merely erroring. The load-bearing
# assertion in this section is therefore always the NO-QUERY one: a denied
# role must not reach get_admin_overview at all.
#
# AUTH-HARDEN-1 removed `administration_section`'s identity PARAMETER
# entirely — it now asks `current_identity()` directly, so there is no dict
# left to tamper with. "denied" is expressed below as a real (fake-backed)
# trusted session for a non-admin role, or no trusted session at all; the
# structural questions the old dict-shaped cases asked (a role with no
# identity, a non-integer user_id, a case-tampered role) are
# `current_identity()`'s own concern and are covered by
# tests/test_auth_identity.py, not here.
# ==========================================================================

ADMIN_USER_ID = 1
TECHNICIAN_USER_ID = 42
GENERAL_USER_ID = 7

DENIED_IDENTITIES = ["technician", "general", "no session"]


@contextlib.contextmanager
def _as(monkeypatch, label: str):
    """A trusted session for `label`, or `no_trusted_session()` for "no session"."""
    if label == "no session":
        with no_trusted_session():
            yield
        return
    user_id = {"technician": TECHNICIAN_USER_ID, "general": GENERAL_USER_ID}[label]
    with trusted_session(monkeypatch, user_id=user_id, role=label):
        yield


def _watch_admin_query(monkeypatch, calls, summary=None):
    """Replace the ONE administration read behind both cards and panel."""

    def _get(**kwargs):
        calls.append(kwargs)
        if summary is None:
            raise AssertionError("a denied role reached the administration query")
        return summary

    monkeypatch.setattr(
        listings.admin_overview_service, "get_admin_overview", _get
    )


class TestAdministrationSectionVisibility:
    def test_renders_for_the_administrator(self, monkeypatch):
        calls = []
        _watch_admin_query(monkeypatch, calls, _summary(rows=(_row(1),)))

        with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
            block = listings.administration_section(NOW)

        assert block is not None
        assert calls, "the administrator's section issued no query"

    def test_the_administrator_gets_cards_and_the_unassigned_panel(self, monkeypatch):
        """ADMIN-2 and ADMIN-3 both live in this block; gating must not drop
        one of them."""
        _watch_admin_query(monkeypatch, [], _summary(rows=(_row(1),)))

        with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
            block = listings.administration_section(NOW)

        assert len(find_by_exact_class(block, "kpi-card")) == 3
        assert find_by_exact_class(block, "unassigned-rtls") != []

    @pytest.mark.parametrize("label", DENIED_IDENTITIES)
    def test_absent_for_every_denied_identity(self, monkeypatch, label):
        calls = []
        _watch_admin_query(monkeypatch, calls)

        with _as(monkeypatch, label):
            assert listings.administration_section(NOW) is None

    @pytest.mark.parametrize("label", DENIED_IDENTITIES)
    def test_a_denied_identity_issues_no_administration_query(self, monkeypatch, label):
        """Invariant 6, and the load-bearing assertion of this section.

        The section is SKIPPED, not built and discarded. `_watch_admin_query`
        raises if it is reached, so this cannot pass by the block quietly
        erroring into None the way a real query failure would.
        """
        calls = []
        _watch_admin_query(monkeypatch, calls)

        with _as(monkeypatch, label):
            listings.administration_section(NOW)

        assert calls == []


class TestTheCapabilityIsNotTheRoute:
    def test_visibility_does_not_consult_the_admin_devices_route(self, monkeypatch):
        """Do not derive this from may_access_route(role, "admin_devices").

        They agree today. If the section were wired to the route instead of
        the capability, breaking the route policy would silently move page
        content too — so this asserts the section keeps rendering for an
        administrator even when the route answer is forced to False.
        """
        _watch_admin_query(monkeypatch, [], _summary())
        monkeypatch.setattr(
            listings, "may_access_route", lambda *a, **k: False, raising=False
        )

        with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
            assert listings.administration_section(NOW) is not None


class TestErrorIsolationSurvivesGating:
    def test_the_administrator_still_gets_none_when_the_query_fails(self, monkeypatch):
        """ADMIN-2/ADMIN-3 isolation: administration failing must cost the
        operator nothing else on the page, so it still fails to None rather
        than raising through the listing boundary."""
        monkeypatch.setattr(
            listings.admin_overview_service,
            "get_admin_overview",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
        )

        with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
            assert listings.administration_section(NOW) is None

    def test_gating_adds_no_second_query(self, monkeypatch):
        """No new queries: the whole section is still ONE administration
        read, and the capability check itself reads nothing."""
        calls = []
        _watch_admin_query(monkeypatch, calls, _summary(rows=(_row(1),)))

        with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
            listings.administration_section(NOW)

        assert len(calls) == 1


class TestDeviceScopeDoesNotLeakIntoAdministration:
    def test_the_administration_read_takes_no_scope_argument(self, monkeypatch):
        """The Administration summary counts Managed RTLs across the fleet.

        It is deliberately NOT narrowed by ROLE-3 device scope: it is
        administrator-only content about the whole estate, and passing a
        scope here would silently change what the counts mean.
        """
        calls = []
        _watch_admin_query(monkeypatch, calls, _summary())

        with trusted_session(monkeypatch, user_id=ADMIN_USER_ID, role="administrator"):
            listings.administration_section(NOW)

        assert calls == [{"now": NOW}]


class TestTheCallbackUsesTheGate:
    def test_populate_overview_appends_nothing_for_a_denied_role(self, monkeypatch):
        """The gate is wired into the render path, not merely available.

        Without this, `administration_section` could be perfectly gated and
        the callback could still call `admin_summary_output` directly.
        """
        calls = []
        _watch_admin_query(monkeypatch, calls)

        source = _populate_overview_source()
        assert "administration_section(" in source
        assert "admin_summary_output(" not in source


def _populate_overview_source() -> str:
    import inspect

    return inspect.getsource(listings.register)
