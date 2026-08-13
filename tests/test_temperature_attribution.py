"""Temperature attribution card — presentation only, no selection/threshold
math. The component receives an already-decided TemperatureAttribution and
only formats it.
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timezone

from components.temperature_attribution import temperature_attribution
from config.metrics import get_metric
from services.monitoring_service import Freshness, TemperatureAttribution
from tests.dash_tree import find_by_exact_class, text_of
from tests.test_component_architecture import (
    FORBIDDEN_SERVICE_SYMBOLS,
    _imported_symbols_from_services,
)

TEMP = get_metric("temperature")
TS = datetime(2026, 8, 9, 5, 43, tzinfo=timezone.utc)


def _view(**overrides):
    base = dict(
        metric=TEMP, value=37.5, reading_ts=TS, freshness=Freshness.FRESH,
        device_id="d1", device_code="29044", transformer_id="t1",
        transformer_code="ta01", reporting_count=7, total_devices=7, has_data=True,
    )
    base.update(overrides)
    return TemperatureAttribution(**base)


def _no_data_view(total_devices=8):
    return _view(
        value=None, reading_ts=None, freshness=Freshness.NO_DATA,
        device_id=None, device_code=None, transformer_id=None, transformer_code=None,
        reporting_count=0, total_devices=total_devices, has_data=False,
    )


class TestHasDataRendering:
    def test_renders_value_with_unit_and_precision(self):
        card = temperature_attribution(_view(value=37.5))
        assert "37.5 °C" in text_of(card)

    def test_renders_device_identity(self):
        card = temperature_attribution(_view())
        assert "29044" in text_of(card)

    def test_renders_transformer_identity_when_requested(self):
        card = temperature_attribution(_view(), show_transformer=True)
        assert "ta01" in text_of(card)

    def test_omits_transformer_identity_when_not_requested(self):
        """Transformer scope: the page header already names the transformer."""
        card = temperature_attribution(_view(), show_transformer=False)
        assert "ta01" not in text_of(card)

    def test_renders_freshness_badge(self):
        card = temperature_attribution(_view(freshness=Freshness.STALE))
        badges = find_by_exact_class(card, "freshness-badge")
        assert len(badges) == 1
        assert badges[0].children == "Stale"

    def test_stale_reading_renders_normally_not_dimmed(self):
        """A stale reading is last-known data, not no data - no empty
        modifier and no missing value."""
        card = temperature_attribution(_view(freshness=Freshness.STALE))
        assert "temperature-attribution--empty" not in card.className
        assert "37.5" in text_of(card)

    def test_renders_reporting_coverage(self):
        card = temperature_attribution(_view(reporting_count=7, total_devices=8))
        assert "7 of 8 devices reporting" in text_of(card)

    def test_renders_timestamp_using_the_existing_utc_convention(self):
        card = temperature_attribution(_view(reading_ts=TS))
        assert "09 Aug 2026 05:43 UTC" in text_of(card)

    def test_does_not_render_a_relative_age_it_was_not_given(self):
        """TemperatureAttribution carries no `age` field - proves the
        component did not compute one itself."""
        card = temperature_attribution(_view())
        assert "ago" not in text_of(card)


class TestNoDataState:
    def test_renders_intentional_no_data_message(self):
        card = temperature_attribution(_no_data_view())
        assert "No temperature data available" in text_of(card)
        assert "0 of 8 devices reporting" in text_of(card)

    def test_no_data_state_carries_the_empty_modifier_class(self):
        card = temperature_attribution(_no_data_view())
        assert "temperature-attribution--empty" in card.className

    def test_does_not_raise_when_identity_and_population_are_all_zero(self):
        temperature_attribution(_no_data_view(total_devices=0))  # must not raise


class TestWordingAvoidsThresholdLanguage:
    def test_no_forbidden_severity_words_anywhere(self):
        text = text_of(temperature_attribution(_view()))
        for forbidden in ("Warning", "Critical", "Alert", "Overheating", "High Temperature"):
            assert forbidden not in text


class TestArchitectureBoundary:
    def test_component_does_not_import_forbidden_service_functions(self):
        path = (
            pathlib.Path(__file__).resolve().parent.parent
            / "components" / "temperature_attribution.py"
        )
        hit = _imported_symbols_from_services(path) & FORBIDDEN_SERVICE_SYMBOLS
        assert not hit
