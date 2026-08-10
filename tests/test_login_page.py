"""Login page — control inventory, callback contracts and accessibility shape.

The login slice is a *visual* refinement, so the tests that matter are the ones
that catch a redesign quietly breaking authentication: a renamed id, a dropped
`n_submit=0`, a label that stopped pointing at its input. That held true across
the full-bleed rewrite too — none of the auth wiring below changed with it.

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
    def test_card_sits_inside_the_grid_stage(self, layout):
        """The card's position comes from a declared grid column, not a
        standalone flex-positioned element — `.login-stage` must be the card's
        parent, not a sibling or absent entirely."""
        assert len(find_by_exact_class(layout, "login-stage")) == 1
        assert len(find_by_exact_class(layout, "login-card")) == 1
        stage = find_by_exact_class(layout, "login-stage")[0]
        assert find_by_exact_class(stage, "login-card")

    def test_no_leftover_split_composition_classes(self, layout):
        """Guards against a half-finished revert: the old shell/panel classes
        must not still be in the tree alongside the new grid."""
        rendered_classes = {
            cls
            for n in walk(layout)
            for cls in str(getattr(n, "className", "") or "").split()
        }
        for stale in ("login-shell", "login-form-panel", "login-visual-panel"):
            assert stale not in rendered_classes

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

    def test_logo_mark_uses_the_system_accent(self, css):
        """The new shield mark is a decorative data: URI, not a raster asset —
        it must draw from the same --color-accent as the rest of the system
        rather than hard-coding an unrelated brand blue."""
        block = css.split(".login-logo-mark {")[1].split("}")[0]
        assert "stroke='%232563eb'" in block

    def test_card_is_opaque_so_contrast_never_depends_on_the_photo(self, css):
        """The solid-card variant was chosen over a translucent one specifically
        so text contrast can never depend on which part of the background photo
        sits behind it. Guards that the card background stays a flat token, not
        an rgba() or a backdrop-filter creeping back in."""
        block = css.split(".login-card {")[1].split("}")[0]
        assert "background: var(--color-surface);" in block
        assert "backdrop-filter" not in block
        assert "rgba(255, 255, 255" not in block


class TestPasswordToggleIsInlineButUnchanged:
    """The control moved inside the field in an earlier pass, and the full-bleed
    rewrite must not have disturbed it. The icon is derived from the field's
    `type` — the very property the callback writes — so the eye and the word
    can never disagree."""

    def test_icon_is_defined_for_both_states(self, css):
        assert '.login-input[type="password"] + .toggle-password-btn::before' in css
        assert '.login-input[type="text"] + .toggle-password-btn::before' in css

    def test_icon_is_keyed_on_the_callback_written_property(self, css):
        """`type` is what callbacks/auth.py writes. A state *class* would have to
        be toggled by something, and nothing does — that would be a contract
        change dressed up as styling."""
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
        must be the --color-accent value, not a login-only colour. Scoped to the
        toggle rules specifically: the logo mark also legitimately encodes the
        same accent in its own data: URI, so a whole-file count would conflate
        two different components sharing one design decision."""
        accent = css.split("--color-accent:")[1].split(";")[0].strip()
        assert accent == "#2563eb"
        toggle_block = css.split(".login-input[type=\"password\"] + .toggle-password-btn::before")[1]
        toggle_block = toggle_block.split(".login-button {")[0]
        assert toggle_block.count("stroke='%232563eb'") == 2

    def test_field_reserves_space_for_the_control(self, css):
        """Without the reservation the value would run underneath the button."""
        assert ".login-password-row .login-input { padding-right: 92px; }" in css

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
        """/mnt/data is where source images are authored, never where they are
        served from."""
        assert "/mnt/data" not in css
        assert "/mnt/data" not in (PROJECT_ROOT / "pages" / "login.py").read_text(
            encoding="utf-8"
        )

    def test_hero_is_the_page_background_not_a_panel(self, css):
        """Full-bleed rewrite: the photo belongs to .login-page (the whole
        viewport), not a dedicated hero panel — there is no panel left."""
        block = css.split(".login-page {")[1].split("}")[0]
        assert f'url("/assets/{login.HERO_ASSET}")' in block
        assert "background-size: cover;" in block

    def test_asset_is_a_compressed_photo_format(self):
        """PNG is lossless and roughly 9x larger than JPEG for this photo —
        the difference between the image starting to render in the
        low-tens-of-ms and it visibly popping in after the form. Guards
        against a future replacement quietly reverting to PNG."""
        assert login.HERO_ASSET.endswith((".jpg", ".jpeg", ".webp"))

    def test_hero_is_preloaded_so_it_does_not_lag_the_form(self):
        """The image is a CSS background-image on an element Dash renders
        client-side, so the browser doesn't discover it until after the JS
        bundle parses and paints `.login-page` — well after the form is
        already visible (measured: ~400ms lag without this). The preload tag
        lets fetching start in parallel with the JS bundle instead. Read from
        the live app object, not app.py source text, since the tag is built
        by a runtime .replace() rather than typed out literally in the file."""
        import app as app_module

        assert f'href="/assets/{login.HERO_ASSET}"' in app_module.app.index_string
        assert 'rel="preload" as="image"' in app_module.app.index_string

    def test_no_overlay_copy_on_the_photo(self, layout):
        """The reference design has no headline/support text on the image
        itself — only the card carries copy now."""
        rendered = text_of(layout)
        assert "Operational visibility" not in rendered
        assert "one workspace" not in rendered


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
    def test_card_is_width_capped_not_full_width_by_default(self, css):
        """A rigid box was rejected in the previous composition too; the card
        keeps that discipline — it tracks the viewport up to a cap rather than
        stretching edge to edge. Fixed on the card itself rather than left to
        the grid track's own minmax() resolution — verified in-browser to land
        at exactly 490px at both 1366 and 1920, which the track's theoretical
        420–500px range does not guarantee on its own. 490, not 460: measured
        directly off the reference composition's ~36% width-to-canvas ratio."""
        block = css.split(".login-card {")[1].split("}")[0]
        assert "max-width: 490px;" in block
        assert "width: 100%;" in block

    def test_position_comes_from_a_declared_grid_not_a_page_offset(self, css):
        """The card's position used to be `.login-page`'s own padding — a
        number with no relationship to anything else. It now comes from
        `.login-stage`'s grid track, and `.login-page` centres that stage
        rather than pushing the card directly."""
        page_block = css.split(".login-page {")[1].split("}")[0]
        assert "justify-content: center;" in page_block

        stage_block = css.split(".login-stage {")[1].split("}")[0]
        assert "display: grid;" in stage_block
        assert "grid-template-columns: minmax(420px, 500px) 1fr;" in stage_block
        assert "align-items: center;" in stage_block

    def test_card_is_truly_centred_not_nudged(self, css):
        """An earlier pass added `margin-top` to nudge the card down from dead
        centre. The grid replaces that entirely — verified in-browser as equal
        top/bottom gaps at both 1366 and 1920 — so the nudge must not have
        crept back into either rule."""
        card_block = css.split(".login-card {")[1].split("}")[0]
        assert "margin-top" not in card_block
        page_block = css.split(".login-page {")[1].split("}")[0]
        assert "margin-top" not in page_block

    def test_grid_collapses_to_one_centred_column_on_narrow_viewports(self, css):
        """No room for a two-column grid once the viewport is phone-width —
        falls back to a single column with the card centred in it, like any
        other small dialog."""
        narrow = css.split("@media (max-width: 899px)")[1]
        assert "grid-template-columns: 1fr;" in narrow
        assert "justify-items: center;" in narrow

    def test_hero_stays_full_bleed_at_every_width(self, css):
        """The photo is the page background, not a panel — it should never be
        toggled off in any media query, at this breakpoint or any other."""
        assert ".login-page { display: none" not in css
        for block in css.split("@media"):
            if "max-width" not in block.split("{")[0]:
                continue
            assert "background-image: none" not in block
