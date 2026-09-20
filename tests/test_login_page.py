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

from callbacks.auth import password_toggle_state
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
    "toggle-password-icon",
    "toggle-password-label",
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
    """The control moved inside the field in an earlier pass, and neither the
    full-bleed rewrite nor the local-icon swap must have disturbed it."""

    def test_field_reserves_space_for_the_control(self, css):
        """Without the reservation the value would run underneath the button."""
        assert ".login-password-row .login-input { padding-right: 92px; }" in css

    def test_control_is_still_a_focusable_button(self, layout):
        """Absolute positioning must not turn it into a decoration."""
        btn = find_by_id(layout, "toggle-password-btn")
        assert isinstance(btn, html.Button)
        assert text_of(btn).strip() == "Show"

    def test_no_leftover_css_only_icon(self, css):
        """The old data: URI eye/eye-off pseudo-elements (pre-dates even the
        Iconify pass) must be gone, not left behind alongside the local mask
        icon."""
        assert "toggle-password-btn::before" not in css
        assert "M1 12s4-8 11-8" not in css  # the old eye path data


class TestPasswordToggleIconIsLocal:
    """The eye glyph is a local SVG (assets/icons/eye[-off].svg) applied as a
    CSS mask on a plain <span>, not a remote Iconify request — the login
    control must render and toggle with zero network access. Both the glyph's
    className and the visible label derive from the same `showing` boolean in
    callbacks/auth.py so they cannot disagree."""

    ICON_DIR = PROJECT_ROOT / "assets" / "icons"

    def test_icon_assets_are_served_locally_from_the_repo(self):
        assert (self.ICON_DIR / "eye.svg").is_file()
        assert (self.ICON_DIR / "eye-off.svg").is_file()

    def test_css_references_the_local_assets_not_a_remote_host(self, css):
        assert 'url("/assets/icons/eye.svg")' in css
        assert 'url("/assets/icons/eye-off.svg")' in css
        assert "iconify" not in css.lower()
        assert "http://" not in css.split(".toggle-password-icon")[1].split(".login-button {")[0]
        assert "https://" not in css.split(".toggle-password-icon")[1].split(".login-button {")[0]

    def test_no_iconify_import_remains_in_the_login_slice(self):
        """Regression guard: nothing in the login page or its callback should
        re-introduce the CDN-dependent component."""
        login_src = (PROJECT_ROOT / "pages" / "login.py").read_text(encoding="utf-8")
        auth_src = (PROJECT_ROOT / "callbacks" / "auth.py").read_text(encoding="utf-8")
        assert "dash_iconify" not in login_src
        assert "dash_iconify" not in auth_src

    def test_icon_size_is_declared_in_css_not_a_component_prop(self, css):
        """Sizing used to be DashIconify's width/height props; now it has to
        live in CSS since the element is a plain span."""
        block = css.split(".toggle-password-icon {")[1].split("}")[0]
        assert "width: 17px;" in block
        assert "height: 17px;" in block

    def test_icon_inherits_currentcolor_not_a_hardcoded_accent(self, css):
        """The mask supplies shape only; `background-color: currentColor` is
        what lets it pick up `.toggle-password-btn { color: var(--color-accent) }`
        without a second, independent colour declaration."""
        block = css.split(".toggle-password-icon {")[1].split("}")[0]
        assert "background-color: currentColor;" in block
        assert "#2563eb" not in block
        assert "var(--color-accent)" not in block

    def test_icon_span_is_present_in_the_layout(self, layout):
        icon = find_by_id(layout, "toggle-password-icon")
        assert isinstance(icon, html.Span)

    def test_icon_lives_inside_the_toggle_button(self, layout):
        btn = find_by_id(layout, "toggle-password-btn")
        assert find_by_id(btn, "toggle-password-icon") is not None

    def test_icon_is_hidden_from_the_accessibility_tree(self, layout):
        """The button's accessible name comes from its own aria-label, not
        from flattened text — an unhidden icon span would otherwise risk a
        second, competing accessible object."""
        btn = find_by_id(layout, "toggle-password-btn")
        icon_wrapper = next(
            n for n in walk(btn)
            if isinstance(n, html.Span)
            and find_by_id(n, "toggle-password-icon") is not None
        )
        assert getattr(icon_wrapper, "aria-hidden") == "true"

    def test_hidden_state_shows_the_eye_and_offers_show(self):
        """n_clicks=0 (and every even count) is the masked state."""
        field_type, icon_class, label, aria_label = password_toggle_state(0)
        assert field_type == "password"
        assert icon_class == login.TOGGLE_ICON_SHOW_CLASS
        assert label == "Show"
        assert aria_label == "Show password"

    def test_visible_state_shows_the_eye_off_and_offers_hide(self):
        """An odd click count is the revealed state."""
        field_type, icon_class, label, aria_label = password_toggle_state(1)
        assert field_type == "text"
        assert icon_class == login.TOGGLE_ICON_HIDE_CLASS
        assert label == "Hide"
        assert aria_label == "Hide password"

    def test_toggle_is_reversible(self):
        """A second click must return exactly to the first state, not just to
        *a* different one."""
        assert password_toggle_state(2) == password_toggle_state(0)
        assert password_toggle_state(3) == password_toggle_state(1)

    def test_state_classes_both_carry_the_base_class(self):
        """The callback replaces `className` wholesale, so each state's value
        must still include the base class that carries the sizing/mask rules
        — losing it would silently shrink the icon to nothing."""
        assert login.TOGGLE_ICON_BASE_CLASS in login.TOGGLE_ICON_SHOW_CLASS.split()
        assert login.TOGGLE_ICON_BASE_CLASS in login.TOGGLE_ICON_HIDE_CLASS.split()

    def test_initial_layout_matches_the_hidden_state(self, layout):
        """The server-rendered layout must agree with what n_clicks=0 produces
        — nothing but the callback should ever set these props."""
        _, icon_class, label, aria_label = password_toggle_state(0)
        assert find_by_id(layout, "toggle-password-icon").className == icon_class
        assert text_of(find_by_id(layout, "toggle-password-label")) == label
        assert getattr(find_by_id(layout, "toggle-password-btn"), "aria-label") == aria_label

    def test_accessible_name_contains_the_visible_word(self):
        """WCAG 2.5.3 Label in Name: the aria-label must not diverge from the
        word a sighted user actually reads on the button."""
        for n_clicks in (0, 1):
            _, _, label, aria_label = password_toggle_state(n_clicks)
            assert label.lower() in aria_label.lower()


class TestBrandLogos:
    """Real client branding (Eskom), not a decorative mark — two placements on
    the login page (blue on the white card, white on the dark photo) plus the
    app header once authenticated. All three are meaningful images, not
    decoration, so each needs alt text rather than an empty string."""

    def test_both_login_assets_exist_in_project(self):
        assert (PROJECT_ROOT / "assets" / login.LOGO_BLUE_ASSET).is_file()
        assert (PROJECT_ROOT / "assets" / login.LOGO_WHITE_ASSET).is_file()

    def test_no_sandbox_or_local_path_leaks_into_the_layout(self, layout):
        """The source files were dropped in the repo root during authoring —
        the rendered <img src> must point at /assets/, never a local
        filesystem path or an upload-tool path like /mnt/data."""
        rendered = str(layout)
        assert "/mnt/data" not in rendered
        assert "C:\\" not in rendered and "C:/" not in rendered

    def test_card_logo_is_an_image_with_alt_text(self, layout):
        """Not a <div> background icon any more — a real logo needs a real
        <img> so screen readers and asset tooling both see it as content."""
        node = find_by_exact_class(layout, "login-logo-mark")
        assert len(node) == 1
        img = node[0]
        assert isinstance(img, html.Img)
        assert img.src == f"/assets/{login.LOGO_BLUE_ASSET}"
        assert img.alt.strip()

    def test_hero_panel_logo_is_an_image_with_alt_text(self, layout):
        node = find_by_exact_class(layout, "login-brand-mark")
        assert len(node) == 1
        img = node[0]
        assert isinstance(img, html.Img)
        assert img.src == f"/assets/{login.LOGO_WHITE_ASSET}"
        assert img.alt.strip()

    def test_card_and_hero_logos_use_different_assets(self):
        """Blue-on-white and white-on-dark are not interchangeable — using
        the same file in both spots would make one of them unreadable."""
        assert login.LOGO_BLUE_ASSET != login.LOGO_WHITE_ASSET

    def test_hero_logo_is_positioned_independently_of_the_grid(self, css):
        """Sits over the photo at a fixed corner of .login-page, not inside
        .login-stage — its position must not depend on how the grid's
        columns resolve."""
        block = css.split(".login-brand-mark {")[1].split("}")[0]
        assert "position: absolute;" in block
        page_block = css.split(".login-page {")[1].split("}")[0]
        assert "position: relative;" in page_block

    def test_neither_login_logo_is_forced_square(self, css):
        """Both source files are horizontal icon+wordmark lockups, not square
        glyphs — height is fixed and width must stay auto so the aspect ratio
        holds rather than being squashed into the old icon's square slot."""
        for selector in (".login-logo-mark {", ".login-brand-mark {"):
            block = css.split(selector)[1].split("}")[0]
            assert "width: auto;" in block

    def test_header_logo_exists_and_carries_alt_text(self):
        """Rendered after login, in the app header — same blue asset as the
        card, since the header background is white too."""
        from components.app_header import app_header

        header = app_header()
        imgs = [n for n in walk(header) if isinstance(n, html.Img)]
        assert len(imgs) == 1
        assert imgs[0].src == f"/assets/{login.LOGO_BLUE_ASSET}"
        assert imgs[0].alt.strip()

    def test_header_brand_text_is_unchanged(self):
        """The logo is additive — the brand text must still render alongside
        the mark. APP-NAME-1 renamed that text to "RTL Monitoring"; the point
        of this test is that the logo did not displace it."""
        from components.app_header import app_header

        header = app_header()
        assert "RTL Monitoring" in text_of(header)
        assert "Powerplant" not in text_of(header)


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
