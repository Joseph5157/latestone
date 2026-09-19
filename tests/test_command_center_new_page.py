"""CC-NEW-1: page layout ids and the populate callback's guard/failure paths."""
from __future__ import annotations

from datetime import datetime, timezone

from dash import no_update

from callbacks import command_center_new as cb
from components.command_center import theme
from pages import command_center_new as page
from services.attention_service import AttentionSnapshot


def _ids(node, out=None):
    out = set() if out is None else out
    if getattr(node, "id", None):
        out.add(node.id)
    children = getattr(node, "children", None)
    for child in children if isinstance(children, (list, tuple)) else ([children] if children is not None else []):
        _ids(child, out)
    return out


def test_layout_carries_every_slot_and_the_shared_theme_ids():
    ids = _ids(page.layout())
    assert {page.SCOPE_ID, page.STATUS_SLOT_ID, page.PROBLEMS_ID, page.HOTTEST_ID,
            page.ACTIVITY_ID, page.TREND_ID, page.ERROR_ID, page.INTERVAL_ID,
            page.STORE_ID, page.REFRESH_STATUS_ID, page.REFRESH_NOW_ID} <= ids
    assert {theme.ROOT_ID, theme.STORE_ID, theme.TOGGLE_DARK_ID, theme.TOGGLE_LIGHT_ID} <= ids


def test_other_routes_do_nothing():
    out = cb.populate({"route": "overview"}, None, fetch=lambda *a, **k: 1 / 0)
    assert out == (no_update,) * 9


def test_success_renders_every_panel_and_records_success():
    snap = AttentionSnapshot(total_rtls=3, reporting_rtls=3, problems=(), hottest=(),
                             activity=(), daily_alarms=(), limits=None,
                             generated_at=datetime(2026, 9, 19, tzinfo=timezone.utc))
    out = cb.populate({"route": "command_center_new"}, None,
                      fetch=lambda scope, now: snap, scope_for=lambda: None)
    assert len(out) == 9 and out[6] is None
    assert out[8]["failed"] is False and out[8]["last_success_at"]


def test_failed_first_load_shows_error():
    out = cb.populate({"route": "command_center_new"}, None,
                      fetch=lambda *a, **k: 1 / 0, scope_for=lambda: None)
    assert out[6] is not None and out[8] == {"last_success_at": None, "failed": True}


def test_failed_refresh_keeps_last_good_panels():
    state = {"last_success_at": "2026-09-19T00:00:00+00:00", "failed": False}
    out = cb.populate({"route": "command_center_new"}, state,
                      fetch=lambda *a, **k: 1 / 0, scope_for=lambda: None)
    assert out[:7] == (no_update,) * 7
    assert out[8] == {"last_success_at": state["last_success_at"], "failed": True}


def test_page_class_survives_the_theme_callback():
    """apply_theme REPLACES the root className, so nothing of this page's
    own may live there — it would vanish on the first theme apply."""
    root = page.layout()
    assert root.className == theme.root_class_name(theme.DEFAULT_THEME)
    assert root.children[0].className == "attention-page"
