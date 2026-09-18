"""FRESHNESS-CONFIG-1 — the freshness threshold panel's rendered content."""
from __future__ import annotations

from datetime import datetime, timezone

from components.freshness_threshold_panel import (
    CLEAR_BTN_ID,
    ERROR_ID,
    MINUTES_INPUT_ID,
    SET_BTN_ID,
    freshness_threshold_panel,
)
from services.freshness_threshold_service import FreshnessThresholdState
from tests.dash_tree import find_by_id, text_of


def _state(minutes: int) -> FreshnessThresholdState:
    return FreshnessThresholdState(
        stale_after_minutes=minutes, configured_by_user_id=1,
        configured_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
    )


class TestStatusLine:
    def test_unconfigured_names_the_default_in_plain_words(self):
        rendered = text_of(freshness_threshold_panel(None, default_minutes=1440))
        assert "Using the default: Stale after 24 hours (1,440 minutes)." in rendered

    def test_configured_value_is_shown_in_hours_and_minutes(self):
        rendered = text_of(freshness_threshold_panel(_state(720), default_minutes=1440))
        assert "Stale after 12 hours (720 minutes)." in rendered
        assert "Using the default" not in rendered

    def test_odd_minute_values_are_shown_exactly(self):
        rendered = text_of(freshness_threshold_panel(_state(90), default_minutes=1440))
        assert "Stale after 90 min (90 minutes)." in rendered


class TestControls:
    def test_form_controls_exist(self):
        panel = freshness_threshold_panel(None, default_minutes=1440)
        for control_id in (MINUTES_INPUT_ID, SET_BTN_ID, CLEAR_BTN_ID, ERROR_ID):
            assert find_by_id(panel, control_id) is not None

    def test_reset_is_disabled_when_nothing_is_configured(self):
        panel = freshness_threshold_panel(None, default_minutes=1440)
        assert find_by_id(panel, CLEAR_BTN_ID).disabled is True

    def test_reset_is_enabled_when_a_value_is_configured(self):
        panel = freshness_threshold_panel(_state(720), default_minutes=1440)
        assert find_by_id(panel, CLEAR_BTN_ID).disabled is False

    def test_error_is_rendered_in_the_error_slot(self):
        panel = freshness_threshold_panel(None, default_minutes=1440, error="Enter a threshold in minutes.")
        assert text_of(find_by_id(panel, ERROR_ID)) == "Enter a threshold in minutes."

    def test_copy_states_scope_and_that_br008_is_unaffected(self):
        rendered = text_of(freshness_threshold_panel(None, default_minutes=1440))
        assert "Applies to every RTL" in rendered
        assert ">24h no-data notification is not affected" in rendered
        assert "5 to 525,600" in rendered
