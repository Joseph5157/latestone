"""ENT-5 — Operational Workflow Consistency verification checks.

These pin the tranche's frozen decisions:

- D1/D2  the Asset Assignment section and its mock state are gone;
- D3     assignment confirm renders its outcome (never a silent close);
- D4     no ``(Prototype)`` action-button suffixes;
- D5     refusals render the shared notice;
- D6     the Device Management drawer actually has fixed-overlay CSS,
         including narrow-viewport (390px-class) behaviour;
- D7     forwarding copy states per-account scope ("your account",
         "not specifically to this RTL");
- and nothing in this tranche introduced transport, scheduler or
  hierarchy-reassignment behaviour.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from callbacks import device_admin, device_assign, device_manage, user_admin
from components.assign_device_drawer import assign_device_drawer
from components.device_manage_drawer import device_manage_drawer
from components.user_form_drawer import user_form_drawer

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _source(module) -> str:
    return inspect.getsource(module)


def _ids(component) -> list[str]:
    ids = []

    def walk(node):
        if hasattr(node, "id") and node.id:
            ids.append(node.id)
        if hasattr(node, "children"):
            children = node.children
            if isinstance(children, list):
                for child in children:
                    walk(child)
            elif children is not None:
                walk(children)

    walk(component)
    return ids


class TestDeadAssetAssignmentIsGone:
    def test_mock_state_symbols_no_longer_exist(self):
        """ENT-5 D2: the in-memory prototype store and its accessors were
        deleted, not merely unused."""
        for symbol in (
            "_mock_assignments",
            "get_mock_assignment",
            "clear_mock_assignments",
        ):
            assert not hasattr(device_assign, symbol), symbol
            assert symbol not in _source(device_assign), symbol

    def test_asset_cascade_helpers_are_gone(self):
        for symbol in ("_plant_options", "_transformer_options"):
            assert not hasattr(device_assign, symbol), symbol

    def test_drawers_offer_no_hierarchy_reassignment(self):
        for drawer in (assign_device_drawer(), device_manage_drawer()):
            text = str(drawer)
            assert "assign-plant" not in text
            assert "assign-transformer" not in text
            assert "Asset Assignment" not in text


class TestAssignmentOutcomeGrammar:
    def test_confirm_renders_a_result_slot(self):
        """ENT-5 D3: success is visible in the drawer with an explicit
        Close action — never a silent close."""
        drawer = assign_device_drawer()
        ids = _ids(drawer)
        assert "assign-result" in ids
        assert "assign-close-btn" in ids
        # After a save the secondary action is relabelled "Close" so the
        # operator has an explicit way out of the drawer.
        source = _source(device_assign)
        assert 'Output(ASSIGN_CLOSE_BTN, "children"' in source
        assert '"Close"' in source

    def test_open_paths_clear_the_result_slot(self):
        """Stale feedback from a previous visit must not bleed into a
        freshly opened drawer."""
        source = _source(device_assign)
        assert "_open_outputs" in source
        assert source.count('Output(ASSIGN_RESULT_ID, "children"') >= 3

    def test_refusal_notice_is_wired_into_both_refusable_flows(self):
        """ENT-5 D5: assign and user-form confirms render the shared
        refusal notice instead of a silent no-op."""
        from components.status_panels import action_refused_notice

        assert "action_refused_notice" in _source(device_assign)
        assert "action_refused_notice" in _source(user_admin)


class TestNoPrototypeButtonSuffixes:
    def test_operational_verbs_without_prototype_suffix(self):
        assert "(Prototype)" not in str(assign_device_drawer())
        assert "(Prototype)" not in str(user_form_drawer())
        assert "(Prototype)" not in str(device_manage_drawer())
        assert "(Prototype)" not in _source(user_admin)


class TestManageDrawerHasRealStyles:
    def test_fixed_overlay_css_exists(self):
        css = (PROJECT_ROOT / "assets" / "app.css").read_text(encoding="utf-8")
        start = css.index(".manage-drawer {")
        body = css[start : css.index("}", start)]
        assert "position: fixed" in body
        assert "z-index" in body

    def test_overlay_and_panel_rules_exist(self):
        css = (PROJECT_ROOT / "assets" / "app.css").read_text(encoding="utf-8")
        assert ".manage-drawer__overlay {" in css
        panel_start = css.index(".manage-drawer__panel {")
        panel = css[panel_start : css.index("}", panel_start)]
        assert "position: absolute" in panel
        assert "overflow-y: auto" in panel

    def test_narrow_viewport_behaviour_for_390px_devices(self):
        css = (PROJECT_ROOT / "assets" / "app.css").read_text(encoding="utf-8")
        media_start = css.index("@media (max-width: 480px)")
        media = css[media_start:]
        assert ".manage-drawer__panel" in media
        assert ".manage-drawer__actions" in media


class TestForwardingPerUserWording:
    def test_menu_and_panel_state_the_account_scope(self):
        text = str(device_manage_drawer())
        assert "applies to your account, not specifically to this RTL" in text
        # Both the menu description and the panel description carry it.
        assert text.count("not specifically to this RTL") >= 2


class TestAccessibleCloseAffordances:
    def test_every_drawer_close_button_is_labelled(self):
        for drawer in (
            assign_device_drawer(),
            device_manage_drawer(),
            user_form_drawer(),
        ):
            text = str(drawer)
            assert "aria-label='Close" in text or 'aria-label="Close' in text


class TestNoForbiddenBehaviourCreptIn:
    def test_no_transport_or_scheduler_machinery(self):
        """No SMS/email transport, scheduler, or delivery pipeline was
        introduced by this consistency tranche."""
        banned = ("smtplib", "apscheduler", "celery", "requests.post", "twilio")
        for module in (device_assign, device_manage, device_admin):
            source = _source(module).lower()
            for marker in banned:
                assert marker not in source, f"{module.__name__}: {marker}"

    def test_assignment_callbacks_do_not_write_the_hierarchy(self):
        """Technician assignment must remain the only write this workflow
        performs — no devices.transformer_id reassignment here."""
        source = _source(device_assign)
        assert "transformer_id" not in source
        assert "hierarchy_service" not in source

    def test_dead_view_action_helper_is_gone(self):
        assert "_is_view_action" not in _source(device_admin)
