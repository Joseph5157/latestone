"""Recent Operational Events panel rendering (CC-1 Phase 9).

Structural assertions over the rendered Dash tree, not repr() comparisons:
what matters is that a Critical row carries its label beside its colour, that
an unregistered UID carries no link, and that no acknowledge control exists —
none of which a string comparison states clearly enough to survive a
refactor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from dash import dcc, html

from components.command_center import recent_events as panel
from services import command_center_service as svc

NOW = datetime(2026, 8, 29, 14, 30, tzinfo=timezone.utc)


def _row(
    event_id=1,
    *,
    display_label="Power Down",
    tone="critical",
    tone_label="Critical",
    asset_label="29017",
    context_label="Kariba North / aa12",
    detail=None,
    asset_href="/devices/plant-01-t1-d1",
    time_label="14:02",
):
    return svc.RecentEvent(
        event_id=event_id,
        occurred_at=NOW,
        event_type="power_down",
        display_label=display_label,
        tone=tone,
        tone_label=tone_label,
        asset_label=asset_label,
        context_label=context_label,
        detail=detail,
        asset_href=asset_href,
        time_label=time_label,
        time_title="2026-08-29 14:02 UTC",
    )


def _snapshot(rows=(), *, failed=False):
    return SimpleNamespace(
        recent_events=tuple(rows), recent_events_failed=failed
    )


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


def _classes(node) -> list[str]:
    return [
        c
        for n in _walk(node)
        for c in str(getattr(n, "className", "") or "").split()
    ]


def _links(node) -> list:
    return [
        n
        for n in _walk(node)
        if isinstance(n, (dcc.Link, html.A))
    ]


class TestRowContent:
    def test_a_row_shows_its_time_label_and_asset(self):
        card = panel.recent_events_card(_snapshot([_row()]))
        texts = _texts(card)
        assert "14:02" in texts
        assert "Power Down" in texts
        assert "29017" in texts
        assert "Kariba North / aa12" in texts

    def test_every_coloured_marker_has_a_text_label_beside_it(self):
        """Colour never carries meaning alone. A red dot with no word is
        unreadable to a colour-blind operator and to a greyscale printout."""
        for tone, label in (
            ("critical", "Critical"),
            ("warning", "Warning"),
            (svc.TONE_EVENT, "Event"),
        ):
            card = panel.recent_events_card(
                _snapshot([_row(tone=tone, tone_label=label)])
            )
            assert f"command-center__tone--{tone}" in _classes(card)
            assert label in _texts(card)

    def test_detail_payload_is_rendered_when_present(self):
        card = panel.recent_events_card(
            _snapshot([_row(detail="Battery voltage · 3.58 V")])
        )
        assert "Battery voltage · 3.58 V" in _texts(card)

    def test_no_detail_element_is_emitted_when_there_is_none(self):
        """An empty detail line would reserve space for a value that does
        not exist, which reads as a failed load."""
        card = panel.recent_events_card(_snapshot([_row(detail=None)]))
        assert "command-center__event-detail" not in _classes(card)


class TestAssetAction:
    def test_a_resolved_asset_gets_an_open_action(self):
        card = panel.recent_events_card(_snapshot([_row()]))
        hrefs = [getattr(link, "href", None) for link in _links(card)]
        assert "/devices/plant-01-t1-d1" in hrefs

    def test_an_unresolved_asset_gets_no_link_at_all(self):
        """Not a disabled-looking one. A greyed control still says the asset
        exists; plain text says only what is known."""
        card = panel.recent_events_card(
            _snapshot(
                [_row(asset_href=None, asset_label="UID 29841",
                      context_label="Unregistered UID")]
            )
        )
        hrefs = [getattr(link, "href", None) for link in _links(card)]
        assert "/devices/29841" not in hrefs
        assert not [h for h in hrefs if h and h.startswith("/devices/")]
        assert "UID 29841" in _texts(card)
        assert "Unregistered UID" in _texts(card)

    def test_the_asset_link_is_in_app_navigation(self):
        """dcc.Link, not html.A: an html.A reloads the whole Dash app and
        loses the operator's place."""
        card = panel.recent_events_card(_snapshot([_row()]))
        asset_links = [
            link
            for link in _links(card)
            if getattr(link, "href", "") == "/devices/plant-01-t1-d1"
        ]
        assert asset_links and all(
            isinstance(link, dcc.Link) for link in asset_links
        )


class TestNoAlarmWorkflow:
    @pytest.mark.parametrize(
        "word",
        ["acknowledge", "resolve", "clear", "silence", "escalate", "dismiss",
         "assign alarm", "close incident"],
    )
    def test_no_event_workflow_control_is_rendered(self, word):
        """None of these have a persisted workflow behind them. A button
        that looks like it acknowledges an alarm and does nothing is worse
        than no button (ADR-001 — events have no closure contract)."""
        card = panel.recent_events_card(
            _snapshot([_row(), _row(2, tone="warning", tone_label="Warning")])
        )
        rendered = " ".join(_texts(card)).lower()
        assert word not in rendered

    def test_the_panel_renders_no_buttons(self):
        card = panel.recent_events_card(_snapshot([_row()]))
        assert not [n for n in _walk(card) if isinstance(n, html.Button)]


class TestEmptyAndErrorStates:
    def test_the_empty_state_says_only_what_the_database_supports(self):
        card = panel.recent_events_card(_snapshot([]))
        rendered = " ".join(_texts(card))
        assert panel.EMPTY_TEXT in rendered
        for forbidden in ("No problems", "System healthy", "All clear"):
            assert forbidden not in rendered

    def test_a_read_failure_is_not_rendered_as_an_empty_list(self):
        """The distinction the snapshot flag exists to carry: 'nothing
        happened' and 'we could not look' must not render the same."""
        failed = panel.recent_events_card(_snapshot([], failed=True))
        empty = panel.recent_events_card(_snapshot([]))
        assert panel.ERROR_TEXT in " ".join(_texts(failed))
        assert panel.EMPTY_TEXT not in " ".join(_texts(failed))
        assert panel.ERROR_TEXT not in " ".join(_texts(empty))

    def test_the_error_state_does_not_offer_a_view_all_link(self):
        """A link into the full list promises content this panel just
        failed to read."""
        card = panel.recent_events_card(_snapshot([], failed=True))
        assert "/notifications" not in [
            getattr(link, "href", None) for link in _links(card)
        ]


class TestFooterAndScroll:
    def test_rows_link_on_to_the_full_notification_center(self):
        card = panel.recent_events_card(_snapshot([_row()]))
        assert panel.NOTIFICATIONS_PATH in [
            getattr(link, "href", None) for link in _links(card)
        ]

    def test_a_short_list_is_not_wrapped_in_a_scroll_region(self):
        """A focus stop that scrolls nothing is noise in the tab order."""
        card = panel.recent_events_card(
            _snapshot([_row(i) for i in range(panel.SCROLL_AFTER_ROWS)])
        )
        assert "command-center__event-scroll" not in _classes(card)

    def test_a_long_list_scrolls_and_stays_keyboard_reachable(self):
        card = panel.recent_events_card(
            _snapshot([_row(i) for i in range(panel.SCROLL_AFTER_ROWS + 1)])
        )
        region = [
            n
            for n in _walk(card)
            if "command-center__event-scroll"
            in str(getattr(n, "className", "") or "")
        ]
        assert region, "the list must become a scroll region past the cap"
        # WCAG 2.1.1: a scroll container that cannot take focus leaves its
        # lower rows visually present and functionally unreachable.
        assert region[0].tabIndex == "0"
        assert getattr(region[0], "role", None) == "region"

    def test_no_row_is_hidden_by_the_cap(self):
        """The cap bounds HEIGHT, not DATA — same rule as Affected
        Locations. Dropping rows would remove the recent activity the panel
        exists to show."""
        rows = [_row(i, asset_label=f"asset-{i}") for i in range(20)]
        rendered = " ".join(_texts(panel.recent_events_card(_snapshot(rows))))
        for i in range(20):
            assert f"asset-{i}" in rendered
