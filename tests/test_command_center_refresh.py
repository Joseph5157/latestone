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

Since SWITCH-OVER-1 the three distinctions are tested against the current
page's `populate` in tests/test_command_center_page.py; this file keeps the
cadence, the status copy, and the theme/poll separation (the theme is
app-wide since ADR-025; its callbacks are in callbacks/navigation.py).

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
from components import theme
from components.command_center import refresh
from config.settings import monitoring
from pages import command_center as page
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

    def clientside_callback(self, *args, **kwargs):
        pass


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
        assert _find(layout(), page.INTERVAL_ID) is not None

    def test_the_interval_is_page_owned_not_app_wide(self):
        """ADR-005: no global interval. It lives in the Command Center layout,
        so navigating away destroys it and Fleet Overview keeps having none."""
        interval = _find(layout(), page.INTERVAL_ID)
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


class TestThemeIsUntouched:
    def test_no_refresh_output_targets_the_theme(self, handlers):
        args, _ = handlers.specs["populate_attention"]
        outputs = [a for a in args if a.__class__.__name__ == "Output"]
        targets = [str(o.component_id) for o in outputs]
        assert theme.STORE_ID not in targets
        assert theme.ROOT_ID not in targets

    def test_the_theme_callback_does_not_listen_to_the_interval(self):
        from callbacks import navigation
        app = _CapturingApp()
        navigation.register(app)
        args, _ = app.specs["apply_theme"]
        inputs = [a for a in args if a.__class__.__name__ == "Input"]
        assert all(i.component_id != page.INTERVAL_ID for i in inputs)

    def test_polling_does_not_rerender_the_page_root(self, handlers):
        """The theme class lives on the root; the poll only replaces panel
        children, so the appearance cannot flicker on a tick."""
        args, _ = handlers.specs["populate_attention"]
        outputs = [a for a in args if a.__class__.__name__ == "Output"]
        assert all(o.component_id != theme.ROOT_ID for o in outputs)


