from datetime import datetime
from decimal import Decimal

import pytest

from repositories.rtl_temperature_repository import RTLTemperatureReading, RTLTemperatureRepositoryError
from services import rtl_temperature_ui_service as service
from components.kpi_card import kpi_row


def test_explicit_uid_uses_rtl_latest_and_bounded_history(monkeypatch):
    seen = []
    class Reader:
        def get_latest_temperature(self, uid):
            seen.append(("latest", uid)); return RTLTemperatureReading(uid, datetime(2026, 9, 17, 3, 39), Decimal("16.00"))
        def get_temperature_range(self, uid, start, end):
            seen.append(("range", uid, start, end)); return [RTLTemperatureReading(uid, start, Decimal("15.00")), RTLTemperatureReading(uid, end, Decimal("16.00"))]
    monkeypatch.setattr(service, "RTLTemperatureRepository", Reader)
    view = service.get_temperature_view(29743, "24h")
    assert view.current == 16.0 and [r.value for r in view.series] == [15.0, 16.0]
    assert seen[0] == ("latest", 29743) and seen[1][1] == 29743
    assert seen[1][3] == datetime(2026, 9, 17, 3, 39)
    assert view.last_updated == datetime(2026, 9, 17, 3, 39)
    rendered = str(kpi_row(view, timestamp_timezone_label=None))
    assert "17 Sep 2026 03:39" in rendered
    assert "UTC" not in rendered


def test_rtl_failure_never_falls_back(monkeypatch):
    class Reader:
        def get_latest_temperature(self, uid): raise RTLTemperatureRepositoryError("down")
    monkeypatch.setattr(service, "RTLTemperatureRepository", Reader)
    with pytest.raises(service.RTLTemperatureUnavailable):
        service.get_temperature_view(29743, "24h")


def test_unknown_or_no_data_uid_is_an_empty_temperature_view(monkeypatch):
    class Reader:
        def get_latest_temperature(self, uid): return None
    monkeypatch.setattr(service, "RTLTemperatureRepository", Reader)
    assert service.get_temperature_view(999999, "24h").has_data is False
