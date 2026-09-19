"""CC-NEW-1: page layout ids and the populate callback's guard/failure paths."""
from __future__ import annotations

from datetime import datetime, timezone

from dash import no_update

from callbacks import command_center as cb
from components import theme
from pages import command_center as page
from services.attention_service import AttentionSnapshot


def _ids(node, out=None):
    out = set() if out is None else out
    if getattr(node, "id", None):
        out.add(node.id)
    children = getattr(node, "children", None)
    for child in children if isinstance(children, (list, tuple)) else ([children] if children is not None else []):
        _ids(child, out)
    return out


def test_layout_carries_every_slot_and_no_theme_controls_of_its_own():
    ids = _ids(page.layout())
    assert {page.SCOPE_ID, page.STATUS_SLOT_ID, page.PROBLEMS_ID, page.HOTTEST_ID,
            page.ACTIVITY_ID, page.TREND_ID, page.ERROR_ID, page.INTERVAL_ID,
            page.STORE_ID, page.REFRESH_STATUS_ID, page.REFRESH_NOW_ID} <= ids
    # ADR-025: the appearance is app-wide; its store and toggle live in the
    # shell, so the page must not mount duplicates of those ids.
    assert not ({theme.ROOT_ID, theme.STORE_ID, theme.TOGGLE_DARK_ID, theme.TOGGLE_LIGHT_ID} & ids)


def test_other_routes_do_nothing():
    out = cb.populate({"route": "overview"}, None, fetch=lambda *a, **k: 1 / 0)
    assert out == (no_update,) * 9


def test_success_renders_every_panel_and_records_success():
    snap = AttentionSnapshot(total_rtls=3, reporting_rtls=3, problems=(), hottest=(),
                             activity=(), daily_alarms=(), limits=None,
                             generated_at=datetime(2026, 9, 19, tzinfo=timezone.utc))
    out = cb.populate({"route": "command_center"}, None,
                      fetch=lambda scope, now: snap, scope_for=lambda: None,
                      identity=lambda: None)
    assert len(out) == 9 and out[6] is None
    assert out[8]["failed"] is False and out[8]["last_success_at"]


def test_failed_first_load_shows_error():
    out = cb.populate({"route": "command_center"}, None,
                      fetch=lambda *a, **k: 1 / 0, scope_for=lambda: None)
    assert out[6] is not None and out[8] == {"last_success_at": None, "failed": True}


def test_failed_refresh_keeps_last_good_panels():
    state = {"last_success_at": "2026-09-19T00:00:00+00:00", "failed": False}
    out = cb.populate({"route": "command_center"}, state,
                      fetch=lambda *a, **k: 1 / 0, scope_for=lambda: None)
    assert out[:7] == (no_update,) * 7
    assert out[8] == {"last_success_at": state["last_success_at"], "failed": True}


def test_page_root_carries_its_route_class_not_a_theme_class():
    root = page.layout()
    assert root.className == page.ROOT_CLASS
    assert "theme--" not in root.className
    assert root.children[0].className == "attention-page"


# --- CC-ACTIONS-1 -----------------------------------------------------------
from types import SimpleNamespace as NS

from callbacks import device_manage
from components import attention as ui
from services.attention_service import ProblemKind
from services.authorization import AuthorizationError


def test_layout_mounts_the_shared_manage_drawer():
    from components.device_manage_drawer import MANAGE_DRAWER_ID
    assert MANAGE_DRAWER_ID in _ids(page.layout())
    assert {page.ACTION_RESULT_ID, page.ACK_STORE_ID} <= _ids(page.layout())


def test_drawer_output_count_matches_the_other_openers():
    assert cb.DRAWER_OUTPUTS == device_manage._MANAGE_DRAWER_OUTPUTS


def test_permitted_devices_asks_the_policy_per_device_with_the_scope():
    problems = [NS(device_id="a"), NS(device_id="b")]
    seen = []

    def allow(user, action, *, device_id, scope):
        seen.append(scope)
        return device_id == "a"

    may_ack, may_manage = cb.permitted_devices(problems, "u", "SCOPE", allow=allow)
    assert may_ack == may_manage == frozenset({"a"})
    assert set(seen) == {"SCOPE"}


ACK = {"type": ui.ACK_BUTTON, "device": "d1", "kind": "power_down"}


class TestAcknowledgeOutputs:
    def test_rerender_is_not_a_click(self):
        assert cb.acknowledge_outputs(ACK, 0) == (no_update, no_update)
        assert cb.acknowledge_outputs(ACK, None) == (no_update, no_update)

    def test_click_acknowledges_and_refreshes(self):
        seen = {}

        def ack(user, scope, device, kind):
            seen.update(device=device, kind=kind)
            return 2

        notice, store = cb.acknowledge_outputs(ACK, 1, identity=lambda: "u",
                                               scope_for=lambda: "s", ack=ack)
        assert seen == {"device": "d1", "kind": ProblemKind.POWER_DOWN}
        assert "Acknowledged 2 alarms" in notice.children.children
        assert store and store["at"]

    def test_refusal_shows_notice_without_refresh(self):
        def ack(*a):
            raise AuthorizationError("no")

        notice, store = cb.acknowledge_outputs(ACK, 1, identity=lambda: "u",
                                               scope_for=lambda: "s", ack=ack)
        assert notice is not no_update and store is no_update

    def test_unknown_kind_is_ignored(self):
        bad = {**ACK, "kind": "nonsense"}
        assert cb.acknowledge_outputs(bad, 1) == (no_update, no_update)


MANAGE = {"type": ui.MANAGE_BUTTON, "device": "d1"}
PATH = NS(device_code="29001", transformer_code="t1", plant_name="Alpha")


class TestManageOutputs:
    def test_opens_drawer_with_server_resolved_labels(self):
        out = cb.manage_outputs(MANAGE, 1, identity=lambda: "u", scope_for=lambda: "s",
                                allow=lambda *a, **k: True, paths_for=lambda ids, scope: [PATH])
        assert len(out) == cb.DRAWER_OUTPUTS
        assert out[0] == {"display": "block"} and out[1] == "d1" and out[2] == "menu"
        assert out[3:6] == ("29001", "t1", "Alpha")

    def test_declined_without_permission(self):
        out = cb.manage_outputs(MANAGE, 1, identity=lambda: "u", scope_for=lambda: "s",
                                allow=lambda *a, **k: False, paths_for=lambda ids, scope: [PATH])
        assert out == (no_update,) * cb.DRAWER_OUTPUTS

    def test_declined_when_out_of_scope(self):
        out = cb.manage_outputs(MANAGE, 1, identity=lambda: "u", scope_for=lambda: "s",
                                allow=lambda *a, **k: True, paths_for=lambda ids, scope: [])
        assert out == (no_update,) * cb.DRAWER_OUTPUTS

    def test_rerender_is_not_a_click(self):
        assert cb.manage_outputs(MANAGE, 0) == (no_update,) * cb.DRAWER_OUTPUTS


def test_severity_selection_toggles_and_ignores_re_renders():
    from dash import no_update as nu
    t = {"type": "attention-severity", "tone": "critical", "part": "counter"}
    assert cb.severity_selection(t, 1, None) == "critical"
    assert cb.severity_selection(t, 2, "critical") is None
    assert cb.severity_selection({**t, "tone": "all"}, 1, "warning") is None
    assert cb.severity_selection(t, 0, None) is nu
