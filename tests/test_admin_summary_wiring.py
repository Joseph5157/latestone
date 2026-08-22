"""The administration card row on the Fleet Overview: slot, clock, isolation.

The component tests cover what the cards say. These cover how they reach the
page — in particular the guarantee that administration is a *secondary* axis
here: if its queries fail, the operator still gets the plant table and the
freshness figures they opened the page for.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

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

    def test_slot_sits_after_monitoring_and_needs_attention(self):
        """Administration is secondary to monitoring and its exception queue."""
        ids = [
            n.id
            for n in plants_overview.layout().children
            if getattr(n, "id", None)
            in {"fleet-systemic-state", "needs-attention", "admin-summary", "fleet-plants"}
        ]
        assert ids == [
            "fleet-systemic-state", "needs-attention", "admin-summary", "fleet-plants"
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


# ==========================================================================
# ROLE-3 Task 12 — the Administration block is Administrator-only content
#
# `admin_summary_output` swallows its own failures and returns None, so a
# test that only asserted "absent for a technician" would pass even if the
# block were still being built and merely erroring. The load-bearing
# assertion in this section is therefore always the NO-QUERY one: a denied
# role must not reach get_admin_overview at all.
# ==========================================================================

ADMINISTRATOR_SESSION = {
    "authenticated": True,
    "user_id": 1,
    "username": "admin",
    "full_name": "Admin",
    "role": "administrator",
}

TECHNICIAN_SESSION = {
    "authenticated": True,
    "user_id": 42,
    "username": "tech",
    "full_name": "Tech",
    "role": "technician",
}

GENERAL_SESSION = {
    "authenticated": True,
    "user_id": 7,
    "username": "general",
    "full_name": "General",
    "role": "general",
}

#: The pre-ROLE-1 payload: a valid flag and no usable identity.
STALE_SESSION = {"authenticated": True}

#: A client-set store claiming a role the session never earned.
TAMPERED_SESSION = {
    "authenticated": True,
    "user_id": 42,
    "username": "tech",
    "full_name": "Tech",
    "role": "Administrator",  # exact-match policy: not the administrator
}

DENIED_SESSIONS = [
    (TECHNICIAN_SESSION, "technician"),
    (GENERAL_SESSION, "general"),
    (STALE_SESSION, "pre-ROLE-1 payload"),
    (TAMPERED_SESSION, "case-tampered role"),
    (None, "no session"),
    ({}, "empty store"),
    ({"authenticated": False}, "signed out"),
    ({"authenticated": True, "role": "administrator"}, "role without identity"),
]


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

        block = listings.administration_section(ADMINISTRATOR_SESSION, NOW)

        assert block is not None
        assert calls, "the administrator's section issued no query"

    def test_the_administrator_gets_cards_and_the_unassigned_panel(self, monkeypatch):
        """ADMIN-2 and ADMIN-3 both live in this block; gating must not drop
        one of them."""
        _watch_admin_query(monkeypatch, [], _summary(rows=(_row(1),)))

        block = listings.administration_section(ADMINISTRATOR_SESSION, NOW)

        assert len(find_by_exact_class(block, "kpi-card")) == 3
        assert find_by_exact_class(block, "unassigned-rtls") != []

    @pytest.mark.parametrize(
        "session,label", DENIED_SESSIONS, ids=[label for _s, label in DENIED_SESSIONS]
    )
    def test_absent_for_every_denied_session(self, monkeypatch, session, label):
        calls = []
        _watch_admin_query(monkeypatch, calls)

        assert listings.administration_section(session, NOW) is None

    @pytest.mark.parametrize(
        "session,label", DENIED_SESSIONS, ids=[label for _s, label in DENIED_SESSIONS]
    )
    def test_a_denied_session_issues_no_administration_query(
        self, monkeypatch, session, label
    ):
        """Invariant 6, and the load-bearing assertion of this section.

        The section is SKIPPED, not built and discarded. `_watch_admin_query`
        raises if it is reached, so this cannot pass by the block quietly
        erroring into None the way a real query failure would.
        """
        calls = []
        _watch_admin_query(monkeypatch, calls)

        listings.administration_section(session, NOW)

        assert calls == []


class TestIdentityComesFromTheSession:
    def test_a_raw_role_key_without_an_identity_is_not_enough(self, monkeypatch):
        """The store is client-settable. Reading `auth_data["role"]` directly
        would accept this payload; `from_session` rejects it because it
        carries no user_id, username or full_name.
        """
        calls = []
        _watch_admin_query(monkeypatch, calls)

        payload = {"authenticated": True, "role": "administrator"}
        assert listings.administration_section(payload, NOW) is None
        assert calls == []

    def test_the_role_is_compared_exactly(self, monkeypatch):
        calls = []
        _watch_admin_query(monkeypatch, calls)

        assert listings.administration_section(TAMPERED_SESSION, NOW) is None
        assert calls == []

    def test_a_non_integer_user_id_is_rejected(self, monkeypatch):
        """from_session rejects a bool user_id (bool is an int in Python)."""
        calls = []
        _watch_admin_query(monkeypatch, calls)

        payload = dict(ADMINISTRATOR_SESSION, user_id=True)
        assert listings.administration_section(payload, NOW) is None
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

        assert listings.administration_section(ADMINISTRATOR_SESSION, NOW) is not None


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

        assert listings.administration_section(ADMINISTRATOR_SESSION, NOW) is None

    def test_gating_adds_no_second_query(self, monkeypatch):
        """No new queries: the whole section is still ONE administration
        read, and the capability check itself reads nothing."""
        calls = []
        _watch_admin_query(monkeypatch, calls, _summary(rows=(_row(1),)))

        listings.administration_section(ADMINISTRATOR_SESSION, NOW)

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

        listings.administration_section(ADMINISTRATOR_SESSION, NOW)

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
