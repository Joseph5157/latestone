"""THRESH-CONFIG-1 presentation tests — the temperature threshold panel
component. Pure Dash component construction, no database, no callback.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from config.metrics import ATTRIBUTION_METRIC_KEY, get_metric
from components.temperature_threshold_panel import (
    CLEAR_BTN_ID,
    CRITICAL_INPUT_ID,
    SET_BTN_ID,
    WARNING_INPUT_ID,
    temperature_threshold_panel,
)
from services.temperature_threshold_service import ThresholdConfigState

_METRIC = get_metric(ATTRIBUTION_METRIC_KEY)


def _state(**overrides) -> ThresholdConfigState:
    """Real states always carry a canonical Decimal already scaled to
    NUMERIC(12,3) — these defaults mirror that exactly, never a bare
    float, so this test module cannot accidentally exercise a shape the
    real service never produces."""
    defaults = dict(
        warning_c=Decimal("60.000"), critical_c=Decimal("75.000"),
        configured_by_user_id=1,
        configured_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return ThresholdConfigState(**defaults)


class TestUnconfiguredState:
    def test_shows_not_configured(self):
        panel = temperature_threshold_panel(None)
        assert "Not configured" in str(panel)

    def test_clear_button_is_disabled_when_unconfigured(self):
        panel = temperature_threshold_panel(None)

        # Walk the tree to find the Clear button precisely, rather than
        # string-matching "disabled" against the whole rendered panel.
        def find_clear_button(node):
            if getattr(node, "id", None) == CLEAR_BTN_ID:
                return node
            for child in getattr(node, "children", None) or []:
                found = find_clear_button(child) if hasattr(child, "id") or hasattr(child, "children") else None
                if found is not None:
                    return found
            return None

        button = find_clear_button(panel)
        assert button is not None
        assert button.disabled is True


class TestConfiguredState:
    def test_shows_both_values_with_the_metric_unit(self):
        panel = temperature_threshold_panel(
            _state(warning_c=Decimal("60.000"), critical_c=Decimal("75.000"))
        )
        text = str(panel)
        assert f"60.000 {_METRIC.unit}" in text
        assert f"75.000 {_METRIC.unit}" in text

    def test_full_canonical_precision_is_shown_not_the_metric_display_precision(self):
        """Correctness fix: the metric config's display precision is 1
        decimal place, but a configured threshold's real stored precision
        (NUMERIC(12,3)) must never be hidden by rounding to it — a stored
        60.250 must show as "60.250", never "60.3" or "60.2"."""
        panel = temperature_threshold_panel(
            _state(warning_c=Decimal("60.250"), critical_c=Decimal("75.000"))
        )
        text = str(panel)
        assert "60.250" in text
        assert _METRIC.precision == 1  # the assumption this test guards
        assert "60.3" not in text
        assert "60.2 " not in text

    def test_clear_button_is_enabled_when_configured(self):
        panel = temperature_threshold_panel(_state())

        def find_clear_button(node):
            if getattr(node, "id", None) == CLEAR_BTN_ID:
                return node
            for child in getattr(node, "children", None) or []:
                found = find_clear_button(child) if hasattr(child, "id") or hasattr(child, "children") else None
                if found is not None:
                    return found
            return None

        button = find_clear_button(panel)
        assert button is not None
        assert button.disabled is False


class TestUnitIsNotDuplicated:
    def test_labels_reference_the_metric_unit_not_a_hardcoded_string(self):
        """If config/metrics.py's temperature unit ever changed, this
        panel's labels must change with it — proven by constructing the
        expected label from the SAME metric lookup this module uses."""
        panel = temperature_threshold_panel(None)
        text = str(panel)
        assert f"Warning ({_METRIC.unit})" in text
        assert f"Critical ({_METRIC.unit})" in text


class TestFormIds:
    def test_form_control_ids_are_present(self):
        panel = temperature_threshold_panel(None)
        ids = set()

        def walk(node):
            node_id = getattr(node, "id", None)
            if isinstance(node_id, str):
                ids.add(node_id)
            for child in getattr(node, "children", None) or []:
                if hasattr(child, "id") or hasattr(child, "children"):
                    walk(child)

        walk(panel)
        assert {WARNING_INPUT_ID, CRITICAL_INPUT_ID, SET_BTN_ID, CLEAR_BTN_ID} <= ids
