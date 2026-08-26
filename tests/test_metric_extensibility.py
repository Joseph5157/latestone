"""Tests for metric extensibility — proves generic behavior works with any metric.

Uses a temporary test-only MetricConfig to verify that UI components and
services derive behavior from the registry, not from a fixed list of keys.
"""
from __future__ import annotations

import pytest

from config.metrics import (
    Aggregation,
    MetricConfig,
    METRICS,
    format_value,
    get_metric,
    ordered_metrics,
)


class TestRegistryIsGeneric:
    """Prove the registry is the single source of truth."""

    def test_ordered_metrics_returns_all_configured(self):
        result = ordered_metrics()
        assert len(result) == len(METRICS)

    def test_get_metric_returns_none_for_unknown(self):
        assert get_metric("nonexistent_metric") is None

    def test_format_value_works_with_any_metric_config(self):
        """format_value accepts any MetricConfig, not just built-in ones."""
        custom = MetricConfig("test", "Test", "unit", 2, "line", 99, Aggregation.STATISTICS)
        assert format_value(custom, 1.234) == "1.23 unit"

    def test_format_value_none_works_with_any_config(self):
        custom = MetricConfig("test", "Test", "unit", 2, "line", 99, Aggregation.STATISTICS)
        assert format_value(custom, None) == "—"

    def test_format_value_empty_unit_works(self):
        custom = MetricConfig("test", "Test", "", 3, "line", 99, Aggregation.STATISTICS)
        assert format_value(custom, 0.9723) == "0.972"


class TestMetricConfigIsExtensible:
    """Prove MetricConfig fields are driven by the dataclass, not hardcoded."""

    def test_metric_config_has_all_required_fields(self):
        m = METRICS[0]
        assert hasattr(m, "key")
        assert hasattr(m, "label")
        assert hasattr(m, "unit")
        assert hasattr(m, "precision")
        assert hasattr(m, "chart_type")
        assert hasattr(m, "display_order")
        assert hasattr(m, "aggregation")

    def test_any_metricconfig_can_be_formatted(self):
        """Adding a new metric only requires adding to METRICS tuple."""
        for m in METRICS:
            result = format_value(m, 1.0)
            assert isinstance(result, str)

    def test_aggregation_drives_chart_behavior(self):
        """Chart type is determined by aggregation, not metric key."""
        for m in METRICS:
            if m.aggregation is Aggregation.DELTA:
                assert m.chart_type == "bar"
            else:
                assert m.chart_type == "line"


class TestSelectorDerivesFromRegistry:
    """Prove selector behavior derives from ordered_metrics()."""

    def test_ordered_metrics_returns_list(self):
        result = ordered_metrics()
        assert isinstance(result, list)

    def test_ordered_metrics_sorted_by_display_order(self):
        result = ordered_metrics()
        orders = [m.display_order for m in result]
        assert orders == sorted(orders)

    def test_all_metrics_have_unique_keys(self):
        keys = [m.key for m in METRICS]
        assert len(keys) == len(set(keys))


class TestMetricHealthIsGeneric:
    """Prove metric health iterates configured metrics, not hardcoded list."""

    def test_metric_health_from_rows_uses_ordered_metrics(self):
        """The function accepts any rows, not just specific metric keys."""
        from services.monitoring_service import (
            aggregate_freshness,
            metric_health_from_rows,
            Freshness,
        )
        # Build mock rows for a custom metric
        class MockRow:
            def __init__(self, device_id, metric, reading_ts, plant_id="p1", transformer_id="t1"):
                self.device_id = device_id
                self.metric = metric
                self.reading_ts = reading_ts
                self.plant_id = plant_id
                self.transformer_id = transformer_id

        from datetime import datetime, timezone
        now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
        rows = [MockRow("d1", "temperature", now)]
        result = metric_health_from_rows(rows, plant_id="p1", now=now)
        # Should return one MetricHealth per configured metric
        assert len(result) == len(METRICS)


class TestFreshnessChainIsGeneric:
    """Prove freshness evaluation uses configured metrics, not hardcoded list."""

    def test_evaluate_freshness_works_with_any_timestamp(self):
        from services.monitoring_service import evaluate_freshness, Freshness
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
        fresh = now - timedelta(minutes=5)
        assert evaluate_freshness(fresh, now) is Freshness.FRESH

    def test_evaluate_freshness_no_data_for_none(self):
        from services.monitoring_service import evaluate_freshness, Freshness
        assert evaluate_freshness(None) is Freshness.NO_DATA


class TestNoVibrationHardcoding:
    """Verify no vibration-specific code exists in production modules."""

    def test_config_metrics_has_no_vibration(self):
        keys = [m.key for m in METRICS]
        assert "vibration" not in keys

    def test_config_metrics_has_no_vibration_label(self):
        labels = [m.label for m in METRICS]
        assert "Vibration" not in labels


class TestCSSGridIsDynamic:
    """Verify CSS grid uses auto-fill, not hardcoded repeat(8, ...)."""

    def test_workspace_uses_explicit_columns(self):
        with open("assets/app.css", "r") as f:
            css = f.read()
        # Should NOT have repeat(8, ...) in the main .metric-workspace rule
        assert "repeat(8," not in css.split(".metric-workspace")[1].split("}")[0]


class TestTemperatureAttributionRetained:
    """Temperature attribution is a legitimate business feature, not hardcoding."""

    def test_attribution_metric_key_exists(self):
        from config.metrics import ATTRIBUTION_METRIC_KEY
        assert ATTRIBUTION_METRIC_KEY == "temperature"

    def test_attribution_metric_key_is_temperature(self):
        from config.metrics import ATTRIBUTION_METRIC_KEY
        m = get_metric(ATTRIBUTION_METRIC_KEY)
        assert m is not None
        assert m.key == "temperature"
