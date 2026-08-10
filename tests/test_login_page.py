"""Login page — control inventory, callback contracts and accessibility shape.

The login slice was a *visual* refinement, so the tests that matter are the ones
that catch a redesign quietly breaking authentication: a renamed id, a dropped
`n_submit=0`, a label that stopped pointing at its input.

Focus *rendering* is deliberately not asserted here. CSS source has twice passed
in this project while the browser computed something else (DEF-1's `:where()`
ring, `.dash-cell-value`'s inherited `text-overflow`), so the focus contract is
verified with getComputedStyle in a real browser. What this file guards is the
one thing source can prove: that the rule which used to double the indicator is
gone.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from dash import dcc, html

from components import equipment_selector as sel
from pages import login
from tests.dash_tree import find_by_exact_class, find_by_id, text_of, walk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_CSS = PROJECT_ROOT / "assets" / "app.css"

# The ids `callbacks/auth.py` binds. Renaming any of them silently detaches the
# login form from authentication: Dash raises nothing for an Input whose target
# is absent from the *page* layout, it simply never fires.
AUTH_CONTRACT_IDS = {
    "login-username",
    "login-password",
    "toggle-password-btn",
    "login-button",
    "login-error",
}


@pytest.fixture(scope="module")
def layout():
    return login.login_layout()


@pytest.fixture(scope="module")
def css() -> str:
    return APP_CSS.read_text(encoding="utf-8")


class TestCallbackContract:
    def test_every_auth_id_is_present(self, layout):
        ids = {getattr(n, "id", None) for n in walk(layout)}
        missing = AUTH_CONTRACT_IDS - ids
        assert not missing, f"auth callbacks would lose their targets: {missing}"

    def test_username_keeps_zero_n_submit(self, layout):
        """Not a default — `login_was_submitted` reads all-zero as 'not asked'.
        `None` instead of 0 is regression NEW-14."""
        assert find_by_id(layout, "login-username").n_submit == 0

    def test_password_keeps_zero_n_submit(self, layout):
        assert find_by_id(layout, "login-password").n_submit == 0

    def test_login_button_keeps_zero_n_clicks(self, layout):
        assert find_by_id(layout, "login-button").n_clicks == 0

    def test_toggle_keeps_zero_n_clicks(self, layout):
        assert find_by_id(layout, "toggle-password-btn").n_clicks == 0

    def test_inputs_are_dcc_inputs(self, layout):
        """The callback writes `type` onto login-password; it has to be a real
        dcc.Input, not an html.Input wrapper."""
        assert isinstance(find_by_id(layout, "login-username"), dcc.Input)
        assert isinstance(find_by_id(layout, "login-password"), dcc.Input)

    def test_password_starts_masked(self, layout):
        assert find_by_id(layout, "login-password").type == "password"

    def test_toggle_starts_showing_the_show_label(self, layout):
        """The callback owns this text, so the initial value must match the
        state it describes: masked field -> offer to Show."""
        assert text_of(find_by_id(layout, "toggle-password-btn")).strip() == "Show"

    def test_toggle_is_a_button(self, layout):
        """Keyboard reachability comes from the element, not from a tabindex."""
        assert isinstance(find_by_id(layout, "toggle-password-btn"), html.Button)

    def test_submit_is_a_button(self, layout):
        assert isinstance(find_by_id(layout, "login-button"), html.Button)


class TestRequiredControls:
    def test_form_panel_and_visual_panel_both_render(self, layout):
        assert find_by_exact_class(layout, "login-form-panel")
        assert find_by_exact_class(layout, "login-visual-panel")

    def test_shell_is_the_single_composition_root(self, layout):
        assert len(find_by_exact_class(layout, "login-shell")) == 1

    def test_error_region_exists(self, layout):
        assert find_by_id(layout, "login-error") is not None

    def test_error_region_starts_empty(self, layout):
        """Reserved space, no message. A non-empty default would trip the
        `:not(:empty)` styling and show an error nobody caused."""
        error = find_by_id(layout, "login-error")
        assert not text_of(error).strip()

    def test_no_consumer_login_affordances(self, layout):
        """No Remember me / Forgot password / Sign up / social login."""
        rendered = text_of(layout).lower()
        for banned in ("remember", "forgot", "sign up", "register", "google", "sso"):
            assert banned not in rendered, f"consumer affordance leaked in: {banned}"


class TestAccessibility:
    @pytest.mark.parametrize("field_id", ["login-username", "login-password"])
    def test_input_has_an_associated_label(self, layout, field_id):
        labels = [n for n in walk(layout) if isinstance(n, html.Label)]
        targets = {getattr(n, "htmlFor", None) for n in labels}
        assert field_id in targets, f"no <label for='{field_id}'>"

    @pytest.mark.parametrize("field_id", ["login-username", "login-password"])
    def test_label_carries_visible_text(self, layout, field_id):
        label = next(
            n for n in walk(layout)
            if isinstance(n, html.Label) and getattr(n, "htmlFor", None) == field_id
        )
        assert text_of(label).strip()

    def test_error_region_is_announced(self, layout):
        """role="alert" — the message appears without a page change, so nothing
        else would tell a screen reader it arrived."""
        assert find_by_id(layout, "login-error").role == "alert"

    def test_error_state_is_not_colour_alone(self, css):
        """A sentence carries the state; the marker is drawn, not coloured."""
        assert '.login-error:not(:empty)::before' in css
        assert 'content: "!";' in css

    def test_focus_ring_is_not_doubled_at_source(self, css):
        """The old `.login-input:focus { box-shadow: var(--focus-ring) }` stacked
        a halo on top of the global DEF-1 outline. Source can prove it is gone;
        the browser proves what replaced it."""
        block = css.split(".login-input:focus")[1].split("}")[0]
        assert "box-shadow" not in block
        assert "outline: none" not in block

    def test_global_focus_rule_still_covers_inputs_and_buttons(self, css):
        """The login block must not have quietly replaced the project treatment."""
        assert "input:focus-visible," in css
        assert "button:focus-visible," in css


class TestPasswordToggleIsInlineButUnchanged:
    """The control moved inside the field. What must not move with it is the
    callback contract: the button still owns its label, and the icon is derived
    from the field's `type` — the very property the callback writes — so the eye
    and the word can never disagree."""

    def test_icon_is_defined_for_both_states(self, css):
        assert '.login-input[type="password"] + .toggle-password-btn::before' in css
        assert '.login-input[type="text"] + .toggle-password-btn::before' in css

    def test_icon_is_keyed_on_the_callback_written_property(self, css):
        """`type` is what callbacks/auth.py writes. A state *class* would have to
        be toggled by something, and nothing does — that would be a contract
        change dressed up as styling."""
        # Every rule that supplies an icon image must be reached through the
        # field's type; the bare ::before rule carries geometry only.
        icon_rules = [
            block.split("{")[0].strip()
            for block in css.split("}")
            if ".toggle-password-btn::before" in block and "background-image" in block
        ]
        assert len(icon_rules) == 2, icon_rules
        for selector in icon_rules:
            assert selector.startswith('.login-input[type='), selector

        # No state class anywhere on the control — nothing would set it.
        assert ".toggle-password-btn." not in css

    def test_icon_uses_the_system_accent_not_a_new_colour(self, css):
        """A data: URI cannot inherit currentColor, so the hex is literal — it
        must be the --color-accent value, not a login-only colour."""
        accent = css.split("--color-accent:")[1].split(";")[0].strip()
        assert accent == "#2563eb"
        assert css.count("stroke='%232563eb'") == 2

    def test_field_reserves_space_for_the_control(self, css):
        """Without the reservation the value would run underneath the button."""
        assert ".login-password-row .login-input { padding-right: 88px; }" in css

    def test_control_is_still_a_focusable_button(self, layout):
        """Absolute positioning must not turn it into a decoration."""
        btn = find_by_id(layout, "toggle-password-btn")
        assert isinstance(btn, html.Button)
        assert text_of(btn).strip() == "Show"


class TestHeroAsset:
    def test_asset_exists_in_project(self):
        assert (PROJECT_ROOT / "assets" / login.HERO_ASSET).is_file()

    def test_css_references_the_project_asset(self, css):
        assert f'url("/assets/{login.HERO_ASSET}")' in css

    def test_no_sandbox_path_is_referenced(self, css):
        """/mnt/data is where the illustration was authored, never where it is
        served from."""
        assert "/mnt/data" not in css
        assert "/mnt/data" not in (PROJECT_ROOT / "pages" / "login.py").read_text(
            encoding="utf-8"
        )

    def test_overlay_copy_renders(self, layout):
        rendered = text_of(layout)
        assert login.HERO_HEADLINE in rendered
        assert login.HERO_SUPPORT in rendered

    def test_overlay_copy_states_no_operational_values(self, layout):
        """Restrained copy only — no fabricated readings, counts or states on an
        unauthenticated screen."""
        copy = f"{login.HERO_HEADLINE} {login.HERO_SUPPORT}"
        assert not any(ch.isdigit() for ch in copy)


class TestEquipmentSelectorStaysHidden:
    """Overlaps `test_equipment_selector.py` by design: that file guards the
    selector's architecture, this one guards it from *this* slice."""

    def test_selector_is_not_rendered_inside_the_login_layout(self, layout):
        ids = {getattr(n, "id", None) for n in walk(layout)}
        for component_id in (sel.SHELL_ID, sel.PLANT_ID, sel.TRANSFORMER_ID, sel.DEVICE_ID):
            assert component_id not in ids

    def test_no_selector_flash_before_authentication(self):
        """Hidden by construction, not by a callback that has to run first —
        which is what would show as a flash on the first paint."""
        from callbacks.equipment_selector import selector_visibility

        assert sel.equipment_selector_shell().style == {"display": "none"}
        assert selector_visibility(None) == {"display": "none"}
        assert selector_visibility({"authenticated": False}) == {"display": "none"}

    def test_login_reserves_no_space_for_the_selector(self, css):
        """`display: none`, not `visibility: hidden` — the latter would leave an
        empty bar above the login composition."""
        assert "display" in sel.HIDDEN_STYLE
        assert sel.HIDDEN_STYLE["display"] == "none"


class TestResponsiveContract:
    def test_desktop_split_is_45_55(self, css):
        assert "grid-template-columns: 45fr 55fr;" in css

    def test_shell_is_width_capped_not_fixed(self, css):
        """A rigid box was explicitly rejected; the shell tracks the viewport up
        to its cap."""
        assert "width: min(1320px, 100%);" in css

    def test_height_cannot_exceed_the_viewport(self, css):
        """1366x768 has to fit without vertical scrolling, with enough slack to
        survive browser chrome / OS scaling / a zoom step: 32 + 690 + 32 = 754
        against 768 is 14 px. 700 would leave 4 px, which measures clean and
        scrolls in the real world."""
        assert "height: min(690px, calc(100vh - 64px));" in css

    def test_vertical_clearance_has_a_safety_margin(self, css):
        """Guards the number above against being nudged back up."""
        import re
        cap = int(re.search(r"height: min\((\d+)px, calc\(100vh - (\d+)px\)\)", css).group(1))
        gutter = int(re.search(r"height: min\(\d+px, calc\(100vh - (\d+)px\)\)", css).group(1))
        assert 768 - (cap + gutter) >= 12, f"only {768 - (cap + gutter)}px clearance at 768"

    def test_visual_panel_collapses_on_narrow_viewports(self, css):
        narrow = css.split("@media (max-width: 899px)")[1]
        assert ".login-visual-panel { display: none; }" in narrow
