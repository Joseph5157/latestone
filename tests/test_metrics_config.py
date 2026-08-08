"""Unit tests for config.metrics."""
from __future__ import annotations

from config.metrics import (
    METRIC_KEYS,
    METRICS,
    Aggregation,
    format_value,
    get_metric,
    ordered_metrics,
)


class TestRegistry:
    def test_defines_eight_metrics(self):
        assert len(METRICS) == 8

    def test_keys_match_spec(self):
        assert set(METRIC_KEYS) == {
            "temperature", "voltage", "current", "active_power",
            "reactive_power", "power_factor", "frequency", "energy",
        }

    def test_display_orders_are_unique_and_sequential(self):
        assert sorted(m.display_order for m in METRICS) == list(range(1, 9))

    def test_ordered_metrics_sorted_by_display_order(self):
        orders = [m.display_order for m in ordered_metrics()]
        assert orders == sorted(orders)

    def test_reactive_power_uses_mvar_casing(self):
        assert get_metric("reactive_power").unit == "MVAr"

    def test_power_factor_has_empty_unit(self):
        assert get_metric("power_factor").unit == ""

    def test_units_match_development_display_units(self):
        expected = {
            "temperature": "°C", "voltage": "kV", "current": "A",
            "active_power": "MW", "reactive_power": "MVAr",
            "power_factor": "", "frequency": "Hz", "energy": "MWh",
        }
        assert {m.key: m.unit for m in METRICS} == expected

    def test_all_charts_are_line_charts(self):
        assert {m.chart_type for m in METRICS} == {"line"}

    def test_no_threshold_fields_defined(self):
        """Guard: production thresholds are explicitly out of scope."""
        fields = set(vars(METRICS[0]))
        assert not any("threshold" in f or "warning" in f or "critical" in f for f in fields)


class TestAggregation:
    def test_energy_uses_delta(self):
        assert get_metric("energy").aggregation is Aggregation.DELTA

    def test_all_other_metrics_use_statistics(self):
        for metric in METRICS:
            if metric.key != "energy":
                assert metric.aggregation is Aggregation.STATISTICS, metric.key


class TestLookup:
    def test_returns_config_for_known_key(self):
        assert get_metric("voltage").label == "Voltage"

    def test_returns_none_for_unknown_key(self):
        assert get_metric("not-a-metric") is None

    def test_returns_none_for_empty_key(self):
        assert get_metric("") is None


class TestFormatValue:
    def test_applies_configured_precision(self):
        assert format_value(get_metric("voltage"), 11.0246) == "11.02 kV"

    def test_temperature_uses_one_decimal(self):
        assert format_value(get_metric("temperature"), 31.44) == "31.4 °C"

    def test_power_factor_omits_unit_suffix(self):
        assert format_value(get_metric("power_factor"), 0.9723) == "0.972"

    def test_none_renders_em_dash(self):
        assert format_value(get_metric("voltage"), None) == "—"
