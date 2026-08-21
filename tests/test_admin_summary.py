"""Administration summary cards — the presentation half of ADMIN-1's service.

These tests are mostly about the two device populations staying apart. The
Fleet Overview already shows a device count over **Monitoring Devices**; this
block counts **Managed RTLs**. On development data both are 120, which is
exactly when a swap goes unnoticed, so the guards here are about wording and
provenance rather than arithmetic.
"""
from __future__ import annotations

from components.admin_summary import admin_summary_cards
from services.admin_overview_service import (
    RECENT_REGISTRATION_WINDOW,
    AdminOverviewSummary,
)
from tests.dash_tree import find_by_exact_class, text_of


def summary(
    total=120,
    assigned=115,
    unassigned=5,
    technicians=4,
    recent=2,
) -> AdminOverviewSummary:
    return AdminOverviewSummary(
        total_devices=total,
        assigned_devices=assigned,
        unassigned_devices=unassigned,
        active_technicians=technicians,
        recently_registered_devices=recent,
        unassigned_rows=(),
    )


def card(block, label: str):
    """The kpi-card carrying `label`, or None."""
    for c in find_by_exact_class(block, "kpi-card"):
        if text_of(c.children[0]) == label:
            return c
    return None


def value_of(block, label: str) -> str:
    return text_of(card(block, label).children[1])


def secondary_of(block, label: str) -> str:
    return text_of(card(block, label).children[2])


def summary_block(**kwargs):
    return admin_summary_cards(summary(**kwargs))


class TestBlockStructure:
    def test_renders_exactly_three_cards(self):
        assert len(find_by_exact_class(summary_block(), "kpi-card")) == 3

    def test_cards_sit_in_their_own_kpi_row(self):
        assert len(find_by_exact_class(summary_block(), "kpi-row--admin")) == 1

    def test_carries_its_own_heading(self):
        """The heading lives in the component, not the page layout, so a failed
        render drops the heading with the cards instead of leaving a bare
        'Administration' title over nothing."""
        assert "Administration" in text_of(summary_block())

    def test_expected_card_labels(self):
        block = summary_block()
        labels = [text_of(c.children[0]) for c in find_by_exact_class(block, "kpi-card")]
        assert labels == ["RTL Assignment", "Active Technicians", "Recently Registered"]


class TestAssignmentCard:
    LABEL = "RTL Assignment"

    def test_headline_leads_with_the_number_needing_action(self):
        assert value_of(summary_block(), self.LABEL) == "5 unassigned"

    def test_secondary_carries_the_managed_total_as_a_denominator(self):
        """The Managed RTL total appears ONLY here, attached to its population
        name, so it cannot be read as a rival to the Fleet device count."""
        assert secondary_of(summary_block(), self.LABEL) == "115 of 120 RTLs assigned"

    def test_fully_assigned_fleet_leads_with_the_reassuring_state(self):
        block = summary_block(assigned=120, unassigned=0)
        assert value_of(block, self.LABEL) == "All assigned"
        assert secondary_of(block, self.LABEL) == "120 of 120 RTLs assigned"

    def test_empty_population_does_not_claim_success(self):
        """Zero managed RTLs is not zero unassigned RTLs. 'All assigned' over an
        empty fleet would be true and misleading at once."""
        block = summary_block(total=0, assigned=0, unassigned=0)
        assert value_of(block, self.LABEL) == "No managed RTLs"
        assert "0 of 0" not in secondary_of(block, self.LABEL)

    def test_single_unassigned_rtl_is_not_pluralised(self):
        assert value_of(summary_block(assigned=119, unassigned=1), self.LABEL) == (
            "1 unassigned"
        )


class TestTechnicianCard:
    LABEL = "Active Technicians"

    def test_shows_the_count(self):
        assert value_of(summary_block(), self.LABEL) == "4"

    def test_zero_technicians_says_what_that_means(self):
        block = summary_block(technicians=0)
        assert value_of(block, self.LABEL) == "0"
        assert secondary_of(block, self.LABEL) == "No technician can take an assignment"

    def test_secondary_explains_what_active_means(self):
        assert secondary_of(summary_block(), self.LABEL) == "Available for RTL assignment"


class TestRecentlyRegisteredCard:
    LABEL = "Recently Registered"

    def test_shows_the_count(self):
        assert value_of(summary_block(), self.LABEL) == "2"

    def test_window_wording_follows_the_service_constant(self):
        """The label must not hardcode 7. The window is a documented
        development value; if the service changes it, the card follows or it
        starts lying about what it counted."""
        days = RECENT_REGISTRATION_WINDOW.days
        assert f"last {days} days" in secondary_of(summary_block(), self.LABEL)

    def test_secondary_names_the_population(self):
        assert secondary_of(summary_block(), self.LABEL).startswith("RTLs added")

    def test_zero_recent_registrations_still_renders_the_window(self):
        block = summary_block(recent=0)
        assert value_of(block, self.LABEL) == "0"
        assert "days" in secondary_of(block, self.LABEL)


class TestPopulationsStayApart:
    """The guard for the defect this page shape invites."""

    def test_block_never_says_devices(self):
        """`Devices` is the Fleet Overview's Monitoring-Devices card. This
        block counts Managed RTLs and must say so everywhere, including when
        both populations happen to be 120."""
        assert "device" not in text_of(summary_block()).lower()

    def test_managed_total_appears_once_and_only_as_context(self):
        """120 must never render as a bare headline figure here — a second
        standalone 120 beside the Fleet card is the misreading to prevent."""
        block = summary_block()
        values = [text_of(c.children[1]) for c in find_by_exact_class(block, "kpi-card")]
        assert "120" not in values
