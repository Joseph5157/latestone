"""Inactive equipment: excluded from listings and counts, reachable by URL.

Regression tests for audit finding NEW-07.

Listings filtered to active equipment while `count_hierarchy_by_plant()` applied
no status filter, so once real data contains decommissioned kit an overview row
could claim 4 transformers and show 3 when opened.

Chosen policy: counts and listings agree (both exclude inactive), and a direct
URL still opens inactive equipment with a notice, so historical readings stay
inspectable. Administrative status only — never merged with freshness or
monitoring condition.
"""
from __future__ import annotations

import pytest

from components.status_panels import inactive_notice
from pages import device_dashboard, plant_detail, transformer_detail
from services import hierarchy_service

from tests.dash_tree import find_by_class, text_of


class _Rec:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class TestCountsMatchListings:
    def test_counts_exclude_inactive_by_default(self, monkeypatch):
        seen = {}

        def _count(include_inactive=False):
            seen["include_inactive"] = include_inactive
            return {}

        monkeypatch.setattr(hierarchy_service.repo, "count_hierarchy_by_plant", _count)
        hierarchy_service.get_plant_hierarchy_counts()
        assert seen["include_inactive"] is False

    def test_counts_can_still_include_inactive_explicitly(self, monkeypatch):
        seen = {}

        def _count(include_inactive=False):
            seen["include_inactive"] = include_inactive
            return {}

        monkeypatch.setattr(hierarchy_service.repo, "count_hierarchy_by_plant", _count)
        hierarchy_service.get_plant_hierarchy_counts(include_inactive=True)
        assert seen["include_inactive"] is True

    def test_listing_and_counting_share_one_default(self, monkeypatch):
        """The invariant the finding was about: same population, both ways."""
        transformers = [
            _Rec(transformer_id="t1", transformer_code="T1", status="active"),
            _Rec(transformer_id="t2", transformer_code="T2", status="inactive"),
        ]
        monkeypatch.setattr(hierarchy_service.repo, "list_transformers", lambda p: transformers)
        listed = hierarchy_service.list_transformers("plant-01")
        assert len(listed) == 1, "listing must exclude inactive by default"


class TestIsActive:
    def test_active_record(self):
        assert hierarchy_service.is_active(_Rec(status="active")) is True

    def test_inactive_record(self):
        assert hierarchy_service.is_active(_Rec(status="inactive")) is False

    def test_missing_status_is_treated_as_active(self):
        assert hierarchy_service.is_active(_Rec()) is True


class TestInactiveNotice:
    def test_names_the_entity(self):
        assert "device" in text_of(inactive_notice("device"))

    def test_says_the_data_is_historical(self):
        assert "historical" in text_of(inactive_notice("transformer")).lower()

    def test_is_not_an_error_panel(self):
        """Inactive is a normal state, not a failure."""
        notice = inactive_notice("plant")
        assert find_by_class(notice, "status-panel--inactive")
        assert not find_by_class(notice, "status-panel--error")


class TestPagesMarkInactiveEquipment:
    @pytest.mark.parametrize(
        "layout_fn,entity",
        [
            (lambda s: device_dashboard.layout(device_code="D1", device_status=s), "device"),
            (lambda s: plant_detail.layout("Plant", status=s), "plant"),
            (lambda s: transformer_detail.layout("Plant", "T1", "p1", status=s), "transformer"),
        ],
    )
    def test_notice_shown_when_inactive(self, layout_fn, entity):
        assert find_by_class(layout_fn("inactive"), "status-panel--inactive"), (
            f"{entity} page did not mark inactive equipment"
        )

    @pytest.mark.parametrize(
        "layout_fn",
        [
            lambda s: device_dashboard.layout(device_code="D1", device_status=s),
            lambda s: plant_detail.layout("Plant", status=s),
            lambda s: transformer_detail.layout("Plant", "T1", "p1", status=s),
        ],
    )
    def test_no_notice_when_active(self, layout_fn):
        assert not find_by_class(layout_fn("active"), "status-panel--inactive")

    @pytest.mark.parametrize(
        "layout_fn",
        [
            lambda: device_dashboard.layout(device_code="D1"),
            lambda: plant_detail.layout("Plant"),
            lambda: transformer_detail.layout("Plant", "T1", "p1"),
        ],
    )
    def test_no_notice_when_status_is_unknown(self, layout_fn):
        """A layout built before the record resolves must not accuse it."""
        assert not find_by_class(layout_fn(), "status-panel--inactive")
