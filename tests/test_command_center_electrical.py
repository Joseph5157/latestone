"""Phase 6 - Electrical Conditions card.

The card must show that the system knows the CATEGORY DEFINITIONS while
being explicit that it does not know the current fleet count (ADR-001).
"""
from __future__ import annotations

from dataclasses import dataclass

from components.command_center.electrical import (
    UNAVAILABLE_TEXT,
    electrical_conditions_card,
)
from tests.dash_tree import find_by_class, text_of


@dataclass(frozen=True)
class _Condition:
    severity_key: str
    severity_label: str
    event_type: str
    condition_label: str
    current_count: int | None
    definition: str


CRITICAL = _Condition("critical", "Critical", "power_down", "Power Down", None, "< 3.61 V")
WARNING = _Condition("warning", "Warning", "battery_low", "Battery Low", None, "< 3.75 V")


@dataclass(frozen=True)
class _Snap:
    electrical_conditions: tuple = (CRITICAL, WARNING)


class TestCategoryPresentation:
    def test_shows_both_severity_labels(self):
        text = text_of(electrical_conditions_card(_Snap()))
        assert "Critical" in text
        assert "Warning" in text

    def test_shows_both_condition_labels(self):
        text = text_of(electrical_conditions_card(_Snap()))
        assert "Power Down" in text
        assert "Battery Low" in text

    def test_definitions_are_labelled_as_device_definitions(self):
        """The figures must read as what the DEVICE decided, not as
        something this application evaluates (ADR-001)."""
        text = text_of(electrical_conditions_card(_Snap()))
        assert "Device definition" in text
        assert "< 3.61 V" in text
        assert "< 3.75 V" in text


class TestUnavailableIsNotZero:
    def test_renders_the_unavailable_word(self):
        assert UNAVAILABLE_TEXT in text_of(electrical_conditions_card(_Snap()))

    def test_never_renders_a_zero_count(self):
        """A rendered 0 would assert 'no RTLs are currently in Power Down',
        which is precisely the claim the event model cannot support."""
        text = text_of(electrical_conditions_card(_Snap()))
        assert "0" not in text

    def test_unavailable_is_structurally_distinct_not_just_styled(self):
        """Its own element, so 'unavailable' and 'a number' are different
        kinds of thing in the DOM - not one value with a colour swapped."""
        card = electrical_conditions_card(_Snap())
        assert find_by_class(card, "command-center__unavailable")

    def test_current_state_row_is_present_and_named(self):
        assert "Current state" in text_of(electrical_conditions_card(_Snap()))


class TestColourNeverCarriesMeaningAlone:
    def test_each_condition_carries_its_severity_tone_class(self):
        card = electrical_conditions_card(_Snap())
        assert find_by_class(card, "command-center__tone--critical")
        assert find_by_class(card, "command-center__tone--warning")

    def test_the_severity_label_is_always_rendered_beside_its_marker(self):
        """If colour were removed entirely the card must still read
        correctly - the label is the meaning, the colour is reinforcement."""
        text = text_of(electrical_conditions_card(_Snap()))
        for condition in (CRITICAL, WARNING):
            assert condition.severity_label in text
            assert condition.condition_label in text


class TestNoInventedMembership:
    def test_renders_only_the_conditions_it_is_given(self):
        """The card is a renderer. It must not add a category because it
        has styling for one - high temperature has no approved domain rule
        (services/event_semantics.py keeps it structurally absent)."""
        text = text_of(electrical_conditions_card(_Snap(electrical_conditions=(CRITICAL,))))
        assert "Power Down" in text
        assert "Battery Low" not in text
        assert "temperature" not in text.lower()
