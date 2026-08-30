"""Command Center auto-refresh (CC-1 Phase 12, ADR-005).

Polling, not a push feed — and the whole gate is really about what happens
when a poll FAILS. A refresh that blanks the cockpit is worse than no
refresh at all: the operator loses a screen full of true information because
one query timed out, and an empty Needs Attention card reads as "nothing is
wrong" rather than "we could not look".

So the tests below spend most of their effort on three distinctions the
implementation must keep structurally apart:

    a failed refresh          != No Data
    a failed FIRST load       != a failed refresh
    the time of a failure     != `Last updated`

Callbacks are captured with a fake app (the house pattern from
tests/test_action_guard_callbacks.py) rather than exercised through a live
Dash server.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from dash import dcc, html, no_update

from callbacks import command_center as cc
from components.command_center import refresh, theme
from config.settings import monitoring
from pages.command_center import layout

NOW = datetime(2026, 8, 30, 14, 31, 7, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(minutes=5)

ADMIN_SESSION = {
    "authenticated": True,
    "user_id": 1,
    "username": "admin",
    "full_name": "Admin",
    "role": "administrator",
}

CONTEXT = {"route": "command_center", "plant_id": None}


class _CapturingApp:
    """Collects callbacks by function name, keeping their Output/Input spec."""

    def __init__(self):
        self.functions = {}
        self.specs = {}

    def callback(self, *args, **kwargs):
        def decorator(fn):
            self.functions[fn.__name__] = fn
            self.specs[fn.__name__] = (args, kwargs)
            return fn

        return decorator


@pytest.fixture
def handlers():
    app = _CapturingApp()
    cc.register(app)
    return app


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        yield from _walk(child)


def _texts(node) -> list[str]:
    return [n for n in _walk(node) if isinstance(n, str)]


def _find(node, component_id):
    for n in _walk(node):
        if getattr(n, "id", None) == component_id:
            return n
    return None


def _fake_snapshot(**overrides):
    base = dict(
        monitored_device_count=120,
        fresh_rtls=120,
        stale_rtls=0,
        no_data_rtls=0,
        attention_rtls=0,
        attention_percent=0.0,
        no_data_percent=0.0,
        plant_count=30,
        transformer_count=71,
        no_data_affected_plants=0,
        electrical_conditions=(),
        affected_locations=(),
        selected_location=None,
        recent_events=(),
        recent_events_failed=False,
        priority_rtls=(),
        priority_total=0,
        has_monitored_devices=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------
class TestCadence:
    def test_the_interval_derives_from_the_setting(self):
        assert refresh.interval_ms() == monitoring.refresh_interval_seconds * 1000

    def test_the_cadence_is_never_hardcoded(self):
        """ADR-005 names ONE cadence source. A literal here would drift from
        `UI_REFRESH_INTERVAL_SECONDS` the first time an operator changed it."""
        import pathlib
        import re

        source = pathlib.Path(refresh.__file__).read_text(encoding="utf-8")
        body = source.split('"""', 2)[-1]
        assert "refresh_interval_seconds" in body
        # No bare millisecond literal masquerading as a cadence.
        assert not re.search(r"interval\s*=\s*\d{3,}", body)

    def test_the_page_mounts_the_interval(self):
        assert _find(layout(), refresh.INTERVAL_ID) is not None

    def test_the_interval_is_page_owned_not_app_wide(self):
        """ADR-005: no global interval. It lives in the Command Center layout,
        so navigating away destroys it and Fleet Overview keeps having none."""
        interval = _find(layout(), refresh.INTERVAL_ID)
        assert isinstance(interval, dcc.Interval)
        assert interval.interval == refresh.interval_ms()


class TestCopy:
    def test_it_says_polling_not_streaming(self):
        """"Live" implies a push guarantee this does not provide (ADR-005)."""
        status = refresh.refresh_status(NOW, failed=False)
        joined = " ".join(_texts(status)).lower()
        for forbidden in ("live", "streaming", "push", "websocket", "real-time", "realtime"):
            assert forbidden not in joined

    def test_it_states_auto_refresh_is_on(self):
        status = refresh.refresh_status(NOW, failed=False)
        assert refresh.AUTO_REFRESH_ON in " ".join(_texts(status))

    def test_it_shows_the_last_updated_time(self):
        status = refresh.refresh_status(NOW, failed=False)
        assert "14:31:07" in " ".join(_texts(status))

    def test_a_failure_is_named_as_a_refresh_failure(self):
        status = refresh.refresh_status(NOW, failed=True)
        joined = " ".join(_texts(status))
        assert refresh.REFRESH_FAILED in joined

    def test_a_failure_is_never_described_as_no_data(self):
        """The distinction the whole gate exists to hold: "we could not look"
        is not "there is nothing there" (ADR-002)."""
        status = refresh.refresh_status(NOW, failed=True)
        joined = " ".join(_texts(status)).lower()
        assert "no data" not in joined
        assert "no readings" not in joined

    def test_a_failure_still_shows_the_last_successful_time(self):
        """So the operator knows how old the data they are reading is."""
        status = refresh.refresh_status(NOW, failed=True)
        assert "14:31:07" in " ".join(_texts(status))

    def test_before_any_success_there_is_no_fabricated_timestamp(self):
        status = refresh.refresh_status(None, failed=False)
        joined = " ".join(_texts(status))
        assert "14:31" not in joined
        assert refresh.NEVER_UPDATED in joined


# --------------------------------------------------------------------------
class TestOneTickOneSnapshot:
    def test_a_tick_assembles_exactly_one_snapshot(self, handlers, monkeypatch):
        """ADR-008's call discipline survives polling: one tick is one
        assembly, not six panels each fetching their own."""
        calls = []
        monkeypatch.setattr(
            cc, "get_command_center_snapshot",
            lambda **kw: calls.append(kw) or _fake_snapshot(),
        )
        monkeypatch.setattr(cc, "scope_from_session", lambda a: "SCOPE")
        monkeypatch.setattr(cc, "from_session", lambda a: SimpleNamespace(role="administrator"))

        handlers.functions["populate_command_center"](CONTEXT, 1, 0, ADMIN_SESSION, None)
        assert len(calls) == 1

    def test_a_tick_on_another_route_does_nothing(self, handlers, monkeypatch):
        calls = []
        monkeypatch.setattr(
            cc, "get_command_center_snapshot",
            lambda **kw: calls.append(kw) or _fake_snapshot(),
        )
        result = handlers.functions["populate_command_center"](
            {"route": "plants"}, 1, 0, ADMIN_SESSION, None
        )
        assert calls == []
        assert all(r is no_update for r in result)


class TestSelectedPlantSurvives:
    """The selection lives in the URL (`?plant=`), parsed into page-context by
    callbacks/routing.py — so it survives a poll BY CONSTRUCTION, because no
    refresh callback owns or can clear it. These tests hold that property
    rather than re-implementing it."""

    def test_the_selection_is_passed_through_on_every_tick(self, handlers, monkeypatch):
        seen = []
        monkeypatch.setattr(
            cc, "get_command_center_snapshot",
            lambda **kw: seen.append(kw.get("selected_plant_id")) or _fake_snapshot(),
        )
        monkeypatch.setattr(cc, "scope_from_session", lambda a: "SCOPE")
        monkeypatch.setattr(cc, "from_session", lambda a: SimpleNamespace(role="administrator"))

        context = {"route": "command_center", "plant_id": "plant-11"}
        for tick in (1, 2, 3):
            handlers.functions["populate_command_center"](
                context, tick, 0, ADMIN_SESSION,
                {"last_success_at": EARLIER.isoformat()},
            )
        assert seen == ["plant-11", "plant-11", "plant-11"]

    def test_polling_never_writes_the_selection(self, handlers):
        """No Output of the refresh callback is the URL or a selection store —
        a poll that could rewrite the selection could also lose it."""
        args, _ = handlers.specs["populate_command_center"]
        outputs = [a for a in args if a.__class__.__name__ == "Output"]
        targets = [o.component_id for o in outputs]
        assert "url" not in targets
        assert not any("plant" in str(t) for t in targets)


class TestRefreshFailureRetainsTheLastGoodSnapshot:
    """The highest-risk behaviour in the gate."""

    def _fail(self, handlers, monkeypatch, store):
        def _boom(**kwargs):
            raise RuntimeError("snapshot read failed")

        monkeypatch.setattr(cc, "get_command_center_snapshot", _boom)
        monkeypatch.setattr(cc, "scope_from_session", lambda a: "SCOPE")
        monkeypatch.setattr(cc, "from_session", lambda a: SimpleNamespace(role="administrator"))
        return handlers.functions["populate_command_center"](
            CONTEXT, 5, 0, ADMIN_SESSION, store
        )

    def test_the_panels_are_left_untouched(self, handlers, monkeypatch):
        """`no_update` and not `[]` — the difference between keeping a screen
        of true data and blanking it because one query timed out."""
        store = {"last_success_at": EARLIER.isoformat(), "failed": False}
        result = self._fail(handlers, monkeypatch, store)
        panels = result[: cc.PANEL_OUTPUT_COUNT]
        assert all(p is no_update for p in panels)

    def test_it_does_not_replace_the_cards_with_zeros(self, handlers, monkeypatch):
        store = {"last_success_at": EARLIER.isoformat(), "failed": False}
        result = self._fail(handlers, monkeypatch, store)
        for panel in result[: cc.PANEL_OUTPUT_COUNT]:
            assert panel is not None
            assert panel != []

    def test_last_updated_keeps_the_last_SUCCESSFUL_time(self, handlers, monkeypatch):
        store = {"last_success_at": EARLIER.isoformat(), "failed": False}
        result = self._fail(handlers, monkeypatch, store)
        new_store = result[-1]
        assert new_store["last_success_at"] == EARLIER.isoformat()

    def test_the_failure_is_flagged(self, handlers, monkeypatch):
        store = {"last_success_at": EARLIER.isoformat(), "failed": False}
        result = self._fail(handlers, monkeypatch, store)
        assert result[-1]["failed"] is True

    def test_the_banner_says_it_is_showing_older_data(self, handlers, monkeypatch):
        store = {"last_success_at": EARLIER.isoformat(), "failed": False}
        result = self._fail(handlers, monkeypatch, store)
        status = result[-2]
        assert refresh.REFRESH_FAILED in " ".join(_texts(status))

    def test_a_later_success_clears_the_error(self, handlers, monkeypatch):
        monkeypatch.setattr(cc, "get_command_center_snapshot", lambda **kw: _fake_snapshot())
        monkeypatch.setattr(cc, "scope_from_session", lambda a: "SCOPE")
        monkeypatch.setattr(cc, "from_session", lambda a: SimpleNamespace(role="administrator"))

        failed_store = {"last_success_at": EARLIER.isoformat(), "failed": True}
        result = handlers.functions["populate_command_center"](
            CONTEXT, 6, 0, ADMIN_SESSION, failed_store
        )
        assert result[-1]["failed"] is False
        assert refresh.REFRESH_FAILED not in " ".join(_texts(result[-2]))

    def test_a_successful_refresh_advances_last_success_at(self, handlers, monkeypatch):
        monkeypatch.setattr(cc, "get_command_center_snapshot", lambda **kw: _fake_snapshot())
        monkeypatch.setattr(cc, "scope_from_session", lambda a: "SCOPE")
        monkeypatch.setattr(cc, "from_session", lambda a: SimpleNamespace(role="administrator"))

        store = {"last_success_at": EARLIER.isoformat(), "failed": False}
        result = handlers.functions["populate_command_center"](
            CONTEXT, 2, 0, ADMIN_SESSION, store
        )
        assert result[-1]["last_success_at"] != EARLIER.isoformat()


class TestFirstLoadFailureIsDifferent:
    """No "last good" exists, so there is nothing to retain and nothing to
    put a stale-data banner over."""

    def _fail(self, handlers, monkeypatch, store):
        def _boom(**kwargs):
            raise RuntimeError("first read failed")

        monkeypatch.setattr(cc, "get_command_center_snapshot", _boom)
        monkeypatch.setattr(cc, "scope_from_session", lambda a: "SCOPE")
        monkeypatch.setattr(cc, "from_session", lambda a: SimpleNamespace(role="administrator"))
        return handlers.functions["populate_command_center"](
            CONTEXT, 0, 0, ADMIN_SESSION, store
        )

    @pytest.mark.parametrize("store", [None, {}, {"last_success_at": None}])
    def test_it_renders_the_initial_error_state(self, handlers, monkeypatch, store):
        result = self._fail(handlers, monkeypatch, store)
        assert result[cc.ERROR_OUTPUT_INDEX] is not None
        assert result[cc.ERROR_OUTPUT_INDEX] is not no_update

    def test_it_does_not_retain_panels_it_never_had(self, handlers, monkeypatch):
        """Retaining `no_update` here would leave the "Loading…" placeholders
        on screen forever, which reads as a slow fleet rather than a failure."""
        result = self._fail(handlers, monkeypatch, None)
        panels = result[1 : cc.PANEL_OUTPUT_COUNT]
        assert all(p == [] for p in panels)

    def test_it_shows_no_stale_data_banner(self, handlers, monkeypatch):
        """There is no last-successful data to be showing."""
        result = self._fail(handlers, monkeypatch, None)
        assert refresh.REFRESH_FAILED not in " ".join(_texts(result[-2]))

    def test_it_records_no_success_time(self, handlers, monkeypatch):
        result = self._fail(handlers, monkeypatch, None)
        assert result[-1]["last_success_at"] is None

    def test_the_two_failures_are_structurally_distinguishable(
        self, handlers, monkeypatch
    ):
        first = self._fail(handlers, monkeypatch, None)
        later = self._fail(
            handlers, monkeypatch, {"last_success_at": EARLIER.isoformat()}
        )
        assert first[cc.ERROR_OUTPUT_INDEX] is not no_update
        assert later[cc.ERROR_OUTPUT_INDEX] is no_update


class TestThemeIsUntouched:
    def test_no_refresh_output_targets_the_theme(self, handlers):
        args, _ = handlers.specs["populate_command_center"]
        outputs = [a for a in args if a.__class__.__name__ == "Output"]
        targets = [str(o.component_id) for o in outputs]
        assert theme.STORE_ID not in targets
        assert theme.ROOT_ID not in targets

    def test_the_theme_callback_does_not_listen_to_the_interval(self, handlers):
        args, _ = handlers.specs["apply_theme"]
        inputs = [a for a in args if a.__class__.__name__ == "Input"]
        assert all(i.component_id != refresh.INTERVAL_ID for i in inputs)

    def test_polling_does_not_rerender_the_page_root(self, handlers):
        """The theme class lives on the root; the poll only replaces panel
        children, so the appearance cannot flicker on a tick."""
        args, _ = handlers.specs["populate_command_center"]
        outputs = [a for a in args if a.__class__.__name__ == "Output"]
        assert all(o.component_id != theme.ROOT_ID for o in outputs)


class TestSemanticsSurviveRefresh:
    def test_current_states_stay_unavailable(self, handlers, monkeypatch):
        """ADR-001 does not relax because the data was re-fetched."""
        from services.command_center_service import ELECTRICAL_CONDITIONS

        assert all(c.current_count is None for c in ELECTRICAL_CONDITIONS)

    def test_refresh_does_not_reclassify_events(self, handlers, monkeypatch):
        """The callback passes the snapshot through; it owns no event logic."""
        import pathlib

        source = pathlib.Path(cc.__file__).read_text(encoding="utf-8")
        for word in ("power_down", "battery_low", "severity", "reclassif"):
            assert word not in source
