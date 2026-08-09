"""The header freshness target must be a container, not a badge.

Regression tests for audit finding NEW-05.

`app_header()` gave the id `header-freshness` to the badge `<span>` itself, and
the device callback wrote a whole new `freshness_badge(...)` into that span's
children. The result was a badge nested inside a badge, with the *outer* class
frozen at whatever the layout first rendered (`freshness-badge--no_data`). So
the visible pill kept the no-data styling no matter what the data said, and the
error path put a `<div>` panel inside a `<span>`.

The fix makes `header-freshness` a neutral container that holds exactly one
badge.
"""
from __future__ import annotations

import pytest

from callbacks.device import header_freshness_children, error_outputs
from components.app_header import app_header
from components.freshness_badge import freshness_badge, freshness_class
from services.monitoring_service import Freshness

from tests.dash_tree import find_by_class, find_by_id, text_of

ALL = [Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA]


class TestHeaderSlotIsNeutral:
    def test_slot_exists(self):
        header = app_header(freshness=Freshness.NO_DATA)
        assert find_by_id(header, "header-freshness") is not None

    def test_slot_is_not_itself_a_badge(self):
        """The regression: the callback target must not carry badge styling."""
        header = app_header(freshness=Freshness.NO_DATA)
        slot = find_by_id(header, "header-freshness")
        assert "freshness-badge" not in (slot.className or "")

    @pytest.mark.parametrize("freshness", ALL)
    def test_header_renders_exactly_one_badge(self, freshness):
        header = app_header(freshness=freshness)
        assert len(find_by_class(header, "freshness-badge")) == 1

    @pytest.mark.parametrize("freshness", ALL)
    def test_header_badge_carries_the_right_class(self, freshness):
        header = app_header(freshness=freshness)
        badge = find_by_class(header, "freshness-badge")[0]
        assert badge.className == freshness_class(freshness)


class TestCallbackOutputStaysOneBadge:
    @pytest.mark.parametrize("freshness", ALL)
    def test_output_is_a_single_badge_with_the_right_class(self, freshness):
        rendered = header_freshness_children(freshness)
        badges = find_by_class(rendered, "freshness-badge")
        assert len(badges) == 1
        assert badges[0].className == freshness_class(freshness)

    @pytest.mark.parametrize("freshness", ALL)
    def test_slot_holds_one_badge_after_the_callback_writes_into_it(self, freshness):
        """Simulate Dash replacing the slot's children."""
        header = app_header(freshness=Freshness.NO_DATA)
        slot = find_by_id(header, "header-freshness")
        slot.children = header_freshness_children(freshness)

        badges = find_by_class(header, "freshness-badge")
        assert len(badges) == 1, "a badge was nested inside another badge"
        assert badges[0].className == freshness_class(freshness)

    def test_transitions_do_not_accumulate_badges(self):
        header = app_header(freshness=Freshness.NO_DATA)
        slot = find_by_id(header, "header-freshness")
        for freshness in [Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA]:
            slot.children = header_freshness_children(freshness)
            assert len(find_by_class(header, "freshness-badge")) == 1


class TestErrorPathDoesNotPutAPanelInTheHeader:
    def test_error_output_for_the_slot_is_a_badge_not_an_error_panel(self):
        """A `<div>` status panel inside the header badge slot was invalid markup.

        A failed refresh means we do not know the freshness, which is what
        no-data already expresses.
        """
        outputs = error_outputs()
        slot_children = outputs[5]
        badges = find_by_class(slot_children, "freshness-badge")
        assert len(badges) == 1
        assert badges[0].className == freshness_class(Freshness.NO_DATA)
        assert find_by_class(slot_children, "status-panel") == []

    def test_error_output_still_covers_every_callback_output(self):
        assert len(error_outputs()) == 7
