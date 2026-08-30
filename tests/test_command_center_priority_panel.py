"""Priority Investigation panel rendering (CC-1 Phase 10, ADR-009).

Structural assertions over the rendered Dash tree, matching
tests/test_command_center_recent_events_panel.py. What matters here is that
the panel renders what the service decided and re-derives nothing: no
sorting, no freshness evaluation, no age arithmetic of its own.
"""
from __future__ import annotations

import pytest
from dash import dcc, html

from components.command_center import priority as panel
from services import command_center_service as svc
from services.monitoring_service import Freshness


def _row(
    device_id="plant-01-t1-d1",
    *,
    device_label="29017",
    state=Freshness.NO_DATA,
    tone=svc.TONE_NO_DATA,
    badge_label="NO DATA",
    context_label="Three Gorges Dam / aa12",
    age_label=None,
    reason=svc.NO_DATA_EXPLANATION,
    asset_href="/devices/plant-01-t1-d1",
):
    return svc.PriorityRTL(
        device_id=device_id,
        device_label=device_label,
        state=state,
        tone=tone,
        badge_label=badge_label,
        context_label=context_label,
        age_label=age_label,
        reason=reason,
        asset_href=asset_href,
    )


def _stale_row(**kwargs):
    defaults = dict(
        device_id="plant-02-t1-d1",
        device_label="18442",
        state=Freshness.STALE,
        tone=svc.TONE_STALE,
        badge_label="STALE",
        context_label="Grand Coulee / tx07",
        age_label="3h 41m",
        reason="Oldest monitored metric last reported 3h 41m ago",
        asset_href="/devices/plant-02-t1-d1",
    )
    defaults.update(kwargs)
    return _row(**defaults)


class _Snapshot:
    def __init__(self, rows=(), *, total=None, monitored=120):
        self.priority_rtls = tuple(rows)
        self.priority_total = len(rows) if total is None else total
        self.monitored_device_count = monitored

    @property
    def has_monitored_devices(self):
        return self.monitored_device_count > 0


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
    return [n for n in _walk(node) if isinstance(n, (dcc.Link, html.A))]


class TestRowContent:
    def test_a_row_shows_its_device_badge_context_and_reason(self):
        card = panel.priority_investigation_card(_Snapshot([_row()]))
        texts = _texts(card)
        assert "29017" in texts
        assert "NO DATA" in texts
        assert "Three Gorges Dam / aa12" in texts
        assert svc.NO_DATA_EXPLANATION in texts

    def test_a_stale_row_shows_its_age_sentence(self):
        card = panel.priority_investigation_card(_Snapshot([_stale_row()]))
        assert "Oldest monitored metric last reported 3h 41m ago" in _texts(card)

    def test_every_coloured_badge_carries_its_word(self):
        """Colour never carries meaning alone (the Phase 9 rule, unchanged)."""
        for tone, label in ((svc.TONE_NO_DATA, "NO DATA"), (svc.TONE_STALE, "STALE")):
            card = panel.priority_investigation_card(
                _Snapshot([_row(tone=tone, badge_label=label)])
            )
            assert f"command-center__tone--{tone}" in _classes(card)
            assert label in _texts(card)

    def test_the_panel_renders_rows_in_the_order_given(self):
        """The service ranked them. The panel must not re-sort."""
        rows = [
            _row(device_id="a", device_label="AAA"),
            _stale_row(device_id="b", device_label="BBB"),
            _row(device_id="c", device_label="CCC"),
        ]
        texts = _texts(panel.priority_investigation_card(_Snapshot(rows)))
        assert texts.index("AAA") < texts.index("BBB") < texts.index("CCC")

    def test_a_row_without_a_context_label_still_renders(self):
        card = panel.priority_investigation_card(
            _Snapshot([_row(context_label=None, device_label="plant-01-t1-d1")])
        )
        assert "plant-01-t1-d1" in _texts(card)


class TestLinks:
    def test_every_row_offers_its_asset(self):
        card = panel.priority_investigation_card(
            _Snapshot([_row(), _stale_row()])
        )
        hrefs = [link.href for link in _links(card)]
        assert hrefs == ["/devices/plant-01-t1-d1", "/devices/plant-02-t1-d1"]

    def test_there_is_no_footer_link(self):
        """ADR-009 D5: /command-center/locations is the PLANT list. Linking
        it from an RTL panel would promise a population it does not show."""
        card = panel.priority_investigation_card(
            _Snapshot([_row()] * 8, total=23)
        )
        hrefs = [str(link.href) for link in _links(card)]
        assert all("/command-center" not in href for href in hrefs)

    def test_a_row_link_is_never_a_control(self):
        card = panel.priority_investigation_card(_Snapshot([_row()]))
        assert not [n for n in _walk(card) if isinstance(n, html.Button)]


class TestNoAlarmWorkflow:
    """ADR-001: none of these has a persisted workflow, so none may appear."""

    @pytest.mark.parametrize(
        "word",
        ["Acknowledge", "Resolve", "Clear", "Silence", "Escalate", "Assign", "Close"],
    )
    def test_no_alarm_action_is_offered(self, word):
        card = panel.priority_investigation_card(
            _Snapshot([_row(), _stale_row()])
        )
        assert word not in " ".join(_texts(card))

    @pytest.mark.parametrize("word", ["Critical", "CRITICAL", "Warning", "WARNING"])
    def test_the_event_vocabulary_never_appears(self, word):
        """Freshness is not severity. A blind RTL is not "Critical"."""
        card = panel.priority_investigation_card(
            _Snapshot([_row(), _stale_row()])
        )
        assert word not in " ".join(_texts(card))


class TestCounts:
    def test_it_states_how_many_it_is_showing_when_capped(self):
        card = panel.priority_investigation_card(_Snapshot([_row()] * 8, total=23))
        assert "Top 8 of 23 RTLs requiring attention" in _texts(card)

    def test_it_does_not_say_top_when_showing_everything(self):
        card = panel.priority_investigation_card(_Snapshot([_row()] * 3, total=3))
        joined = " ".join(_texts(card))
        assert "Top" not in joined
        assert "3 RTLs requiring attention" in joined

    def test_one_rtl_is_singular(self):
        card = panel.priority_investigation_card(_Snapshot([_row()], total=1))
        assert "1 RTL requiring attention" in " ".join(_texts(card))


class TestEmptyStates:
    def test_a_calm_fleet_says_so_without_claiming_health(self):
        card = panel.priority_investigation_card(_Snapshot([], total=0))
        joined = " ".join(_texts(card))
        assert panel.NOTHING_TO_INVESTIGATE in joined
        # Never an all-clear the freshness model cannot support.
        for forbidden in ("healthy", "Healthy", "No problems", "All clear", "OK"):
            assert forbidden not in joined

    def test_zero_monitored_is_a_different_sentence(self):
        """"Nothing to watch" and "nothing wrong" are different facts."""
        calm = panel.priority_investigation_card(_Snapshot([], total=0))
        empty = panel.priority_investigation_card(
            _Snapshot([], total=0, monitored=0)
        )
        assert panel.NOTHING_MONITORED in " ".join(_texts(empty))
        assert panel.NOTHING_MONITORED not in " ".join(_texts(calm))

    def test_neither_empty_state_offers_a_link(self):
        for snapshot in (_Snapshot([], total=0), _Snapshot([], total=0, monitored=0)):
            assert _links(panel.priority_investigation_card(snapshot)) == []


class TestTitle:
    def test_the_card_is_titled_priority_investigation(self):
        card = panel.priority_investigation_card(_Snapshot([_row()]))
        assert "Priority Investigation" in _texts(card)

    def test_the_subtitle_names_what_ranks_the_list(self):
        """The operator should not have to guess why this order is this order."""
        card = panel.priority_investigation_card(_Snapshot([_row()]))
        assert panel.SUBTITLE in _texts(card)


class TestThePanelInfersNothing:
    def test_the_component_never_names_a_metric(self):
        """ADR-009 D4: the service does not carry the lagging metric's
        identity, so the panel may not invent one. Asserted against the
        SOURCE, because a rendering test only catches the cases it fixtures."""
        import pathlib

        from config.metrics import METRIC_KEYS

        source = pathlib.Path(panel.__file__).read_text(encoding="utf-8")
        # Split off the docstring: the module comment legitimately discusses
        # metrics; the rendering code must not name one.
        body = source.split('"""', 2)[-1]
        for metric in METRIC_KEYS:
            assert f'"{metric}"' not in body
            assert f"'{metric}'" not in body

    def test_the_reason_is_rendered_verbatim(self):
        """Whatever the service decided, unedited — no reformatting, no
        appending, no second sentence assembled here."""
        card = panel.priority_investigation_card(
            _Snapshot([_stale_row(reason="ANYTHING THE SERVICE SAYS")])
        )
        assert "ANYTHING THE SERVICE SAYS" in _texts(card)
