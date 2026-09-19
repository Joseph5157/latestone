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
    assert {page.SCOPE_ID, page.STATUS_SLOT_ID, page.GLANCE_ID, page.PROBLEMS_ID, page.HOTTEST_ID,
            page.ACTIVITY_ID, page.TREND_ID, page.ERROR_ID, page.INTERVAL_ID,
            page.STORE_ID, page.REFRESH_STATUS_ID, page.REFRESH_NOW_ID} <= ids
    # ADR-025: the appearance is app-wide; its store and toggle live in the
    # shell, so the page must not mount duplicates of those ids.
    assert not ({theme.ROOT_ID, theme.STORE_ID, theme.TOGGLE_DARK_ID, theme.TOGGLE_LIGHT_ID} & ids)


def test_other_routes_do_nothing():
    out = cb.populate({"route": "overview"}, None, fetch=lambda *a, **k: 1 / 0)
    assert out == (no_update,) * (cb.PANEL_OUTPUTS + 3)


def test_success_renders_every_panel_and_records_success():
    snap = AttentionSnapshot(total_rtls=3, reporting_rtls=3, problems=(), hottest=(),
                             activity=(), daily_alarms=(), limits=None,
                             generated_at=datetime(2026, 9, 19, tzinfo=timezone.utc))
    out = cb.populate({"route": "command_center"}, None,
                      fetch=lambda scope, now: snap, scope_for=lambda: None,
                      identity=lambda: None)
    P = cb.PANEL_OUTPUTS
    assert len(out) == P + 3 and out[P] is None
    assert out[P + 2]["failed"] is False and out[P + 2]["last_success_at"]


def test_failed_first_load_shows_error():
    out = cb.populate({"route": "command_center"}, None,
                      fetch=lambda *a, **k: 1 / 0, scope_for=lambda: None)
    P = cb.PANEL_OUTPUTS
    assert out[P] is not None and out[P + 2] == {"last_success_at": None, "failed": True}


def test_failed_refresh_keeps_last_good_panels():
    state = {"last_success_at": "2026-09-19T00:00:00+00:00", "failed": False}
    out = cb.populate({"route": "command_center"}, state,
                      fetch=lambda *a, **k: 1 / 0, scope_for=lambda: None)
    P = cb.PANEL_OUTPUTS
    assert out[:P + 1] == (no_update,) * (P + 1)
    assert out[P + 2] == {"last_success_at": state["last_success_at"], "failed": True}


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


# --- PROBLEM-GROUPS-2 -------------------------------------------------------
def test_fold_selection_toggles_one_kind_and_ignores_rerenders():
    trig = {"type": ui.GROUP_TOGGLE, "kind": "power_down"}
    assert cb.fold_selection(trig, 1, []) == ["power_down"]
    assert cb.fold_selection(trig, 2, ["battery_low", "power_down"]) == ["battery_low"]
    assert cb.fold_selection(trig, 0, []) is no_update       # re-render
    assert cb.fold_selection(None, 1, []) is no_update


def test_populate_draws_folded_groups_closed():
    from services.attention_service import AttentionSnapshot, Problem, ProblemKind
    p = Problem(kind=ProblemKind.POWER_DOWN, device_id="d1", device_code="D1",
                plant_id="p1", plant_name="Alpha", transformer_code="T1", since=None, detail="x")
    snap = AttentionSnapshot(total_rtls=1, reporting_rtls=1, problems=(p,), hottest=(),
                             activity=(), daily_alarms=(), limits=None,
                             generated_at=datetime(2026, 9, 19, tzinfo=timezone.utc))
    out = cb.populate({"route": "command_center"}, None, None, ["power_down"],
                      fetch=lambda scope, now: snap, scope_for=lambda: None,
                      identity=lambda: None)
    groups = [n for n in _walk_all(out[2]) if "attention-group-details" in (getattr(n, "className", "") or "").split()]
    assert [g.open for g in groups] == [False]


def _walk_all(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in children if isinstance(children, (list, tuple)) else [children]:
        yield from _walk_all(child)


# --- CC-GAUGES-1 (ADR-028) ----------------------------------------------------


def test_the_glance_slot_sits_above_the_problem_list_in_the_main_column():
    main = next(n for n in _walk_nodes(page.layout())
                if getattr(n, "className", None) == "attention-grid__main")
    assert [c.id for c in main.children] == [page.GLANCE_ID, page.PROBLEMS_ID]


def _walk_nodes(node):
    yield node
    children = getattr(node, "children", None)
    for child in children if isinstance(children, (list, tuple)) else ([children] if children is not None else []):
        yield from _walk_nodes(child)


def test_populate_fills_the_glance_slot_in_callback_output_order():
    snap = AttentionSnapshot(total_rtls=3, reporting_rtls=2, problems=(), hottest=(),
                             activity=(), daily_alarms=(), limits=None,
                             generated_at=datetime(2026, 9, 19, tzinfo=timezone.utc))
    out = cb.populate({"route": "command_center"}, None, selected="warning",
                      fetch=lambda scope, now: snap, scope_for=lambda: None,
                      identity=lambda: None)
    outputs = [
        (o.component_id, o.component_property)
        for o in _populate_outputs()
    ]
    glance = out[outputs.index((page.GLANCE_ID, "children"))]
    assert "2 of 3" in str(_texts(glance))


def _texts(node):
    return [n for n in _walk_nodes(node) if isinstance(n, str)]


def _populate_outputs():
    from dash import Output

    class Capture:
        def __init__(self):
            self.specs = {}

        def callback(self, *args, **kwargs):
            def register(fn):
                self.specs[fn.__name__] = args
                return fn
            return register

    capture = Capture()
    cb.register(capture)
    return [a for a in capture.specs["populate_attention"] if isinstance(a, Output)]


def test_a_donut_label_selects_and_toggles_like_a_card():
    trigger = {"type": ui.SEVERITY_BUTTON, "tone": "warning", "part": "donut"}
    assert cb.severity_selection(trigger, 1, None) == "warning"
    assert cb.severity_selection(trigger, 1, "warning") is None


def test_gauge_rings_have_a_cut_out_hole_and_no_animation():
    from pathlib import Path
    css = Path("assets/app.css").read_text(encoding="utf-8")
    start = css.index("/* CC-GAUGES-1 (ADR-028)")
    block = css[start:css.index("/* ====", start)]
    assert "mask: radial-gradient(farthest-side, transparent" in block
    assert ".attention-arc__frame" in block and "overflow: hidden" in block
    assert "animation:" not in block and "transition:" not in block
