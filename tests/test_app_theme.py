"""THEME-APP-1 (ADR-025): app-wide dark mode, Dark by default, remembered
per browser; the login page stays light. Replaces the Command Center-only
theme tests of ADR-006."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from dash import dcc, html, no_update

from callbacks import navigation
from components import theme
from components.app_sidebar import app_sidebar

CSS_PATH = Path(__file__).resolve().parent.parent / "assets" / "app.css"
DARK_SCOPE = ".app-root.theme--dark:not(:has(.login-page))"


@pytest.fixture(scope="module")
def css() -> str:
    return re.sub(r"/\*.*?\*/", "", CSS_PATH.read_text(encoding="utf-8"), flags=re.S)


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in children if isinstance(children, (list, tuple)) else [children]:
        yield from _walk(child)


def _by_id(node, component_id):
    return next(n for n in _walk(node) if getattr(n, "id", None) == component_id)


class TestTheChoice:
    def test_dark_is_the_default(self):
        assert theme.DEFAULT_THEME == theme.DARK
        assert theme.root_class_name(None) == "app-root theme--dark"

    @pytest.mark.parametrize("stored", ["purple", 7, {"theme": "sepia"}, {}])
    def test_unknown_stored_values_fall_back_to_dark(self, stored):
        assert theme.root_class_name(stored) == "app-root theme--dark"

    def test_stored_light_is_honoured_in_either_shape(self):
        assert theme.root_class_name({"theme": "light"}) == "app-root theme--light"
        assert theme.root_class_name("light") == "app-root theme--light"

    @pytest.mark.parametrize("stored", [None, {"theme": "light"}, {"theme": "dark"}])
    def test_exactly_one_appearance_class(self, stored):
        classes = theme.root_class_name(stored).split()
        assert sum(c.startswith("theme--") for c in classes) == 1


class TestTheShell:
    def test_the_app_root_carries_the_class_and_a_local_store(self):
        import app as app_module
        root = app_module.app.layout
        assert root.id == theme.ROOT_ID
        assert root.className == theme.root_class_name(None)
        store = _by_id(root, theme.STORE_ID)
        assert isinstance(store, dcc.Store)
        assert store.storage_type == "local"  # remembered across sign-outs
        assert getattr(store, "data", None) is None  # no value = Dark

    def test_the_toggle_is_in_the_sidebar_as_two_buttons(self):
        sidebar = app_sidebar()
        dark = _by_id(sidebar, theme.TOGGLE_DARK_ID)
        light = _by_id(sidebar, theme.TOGGLE_LIGHT_ID)
        assert isinstance(dark, html.Button) and isinstance(light, html.Button)
        assert dark.__dict__["aria-pressed"] == "true"   # default is Dark
        assert light.__dict__["aria-pressed"] == "false"


class TestTheCallbacks:
    def test_a_click_stores_the_choice(self):
        assert navigation.theme_choice(theme.TOGGLE_LIGHT_ID) == {"theme": "light"}
        assert navigation.theme_choice(theme.TOGGLE_DARK_ID) == {"theme": "dark"}
        assert navigation.theme_choice(None) is no_update

    def test_the_stored_choice_sets_root_and_both_buttons(self):
        root, dark_cls, light_cls, dark_pressed, light_pressed = navigation.theme_outputs({"theme": "light"})
        assert root == "app-root theme--light"
        assert "--active" in light_cls and "--active" not in dark_cls
        assert (dark_pressed, light_pressed) == ("false", "true")


class TestTheStylesheet:
    def test_the_dark_tokens_are_defined_on_the_app_root(self, css):
        block = re.search(re.escape(DARK_SCOPE) + r"\s*\{(.*?)\}", css, flags=re.S)
        assert block, "no app-wide dark token block"
        for token in ("--color-bg", "--color-surface", "--color-text", "--sev-critical"):
            assert token in block.group(1)

    def test_the_login_page_is_excluded_from_dark(self, css):
        assert ":not(:has(.login-page))" in DARK_SCOPE and DARK_SCOPE in css

    def test_no_route_scoped_theme_classes_remain(self, css):
        assert "cc-theme--" not in css

    def test_it_is_not_driven_by_the_operating_system(self, css):
        assert "prefers-color-scheme" not in css

    def test_the_shared_state_tokens_are_untouched_in_root(self, css):
        root = re.search(r":root\s*\{(.*?)\}", css, flags=re.S).group(1)
        assert "--state-none-text: #495057" in root
        assert "--state-stale-text: #713f12" in root

    def test_no_theme_rule_changes_the_font_family(self, css):
        for m in re.finditer(r"theme--dark[^{]*\{(.*?)\}", css, flags=re.S):
            assert "font-family" not in m.group(1)


class TestComponentsFollowTheTheme:
    """THEME-APP-1 step 2: components that paint their own colours."""

    @pytest.mark.parametrize("hook", [
        ".dash-spreadsheet-container .dash-spreadsheet-inner td",  # tables
        ".Select-control", ".Select-menu-outer",                   # dropdowns
        ".DateInput_input", ".CalendarDay__default",               # date pickers
        ".js-plotly-plot .main-svg",                               # charts
        ".header__brand",
    ])
    def test_dark_rule_exists(self, css, hook):
        assert f"{DARK_SCOPE} {hook}" in css

    def test_tables_take_their_cell_colours_from_tokens(self):
        from components.entity_table import entity_table
        table = next(n for n in _walk(entity_table(table_id="t", columns=[{"name": "A", "id": "a"}], rows=[]))
                     if getattr(n, "style_cell", None))
        assert table.style_cell["backgroundColor"] == "var(--color-surface)"
        assert table.style_cell["color"] == "var(--color-text)"

    def test_text_on_an_accent_fill_uses_the_on_accent_token(self, css):
        assert "color: #ffffff;\n}" not in css.split(".manage-drawer__btn--primary {")[1][:200]
        assert "--color-on-accent" in css


# --- THEME-APP-2: contrast of the dark states, native controls, leftovers ---

def _dark_tokens(css):
    block = re.search(re.escape(DARK_SCOPE) + r"\s*\{(.*?)\}", css, flags=re.S).group(1)
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", block))


def _contrast(a, b):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class TestDarkContrast:
    """WCAG 2.2: text 4.5:1; a form field's edge 3:1 (1.4.11); a selected
    or hovered row must visibly differ from its surroundings."""

    @pytest.mark.parametrize("token", ["--color-text", "--color-text-2", "--color-text-3",
                                       "--color-muted", "--color-accent", "--sev-critical",
                                       "--sev-warning", "--sev-nodata", "--sev-normal"])
    def test_text_tokens_read_on_every_ground(self, css, token):
        t = _dark_tokens(css)
        for ground in ("--color-bg", "--color-surface", "--color-subtle"):
            assert _contrast(t[token], t[ground]) >= 4.5, (token, ground)

    def test_the_highlight_is_visible_on_surface_page_and_sidebar(self, css):
        t = _dark_tokens(css)
        for ground in ("--color-surface", "--color-bg", "--color-brand"):
            assert _contrast(t["--color-accent-bg"], t[ground]) >= 1.4, ground
        assert _contrast(t["--color-text"], t["--color-accent-bg"]) >= 4.5

    def test_form_field_edges_reach_three_to_one(self, css):
        t = _dark_tokens(css)
        for ground in ("--color-surface", "--color-subtle", "--color-bg"):
            assert _contrast(t["--color-input-border"], t[ground]) >= 3, ground

    def test_cards_stand_off_the_canvas(self, css):
        t = _dark_tokens(css)
        assert _contrast(t["--color-surface"], t["--color-bg"]) >= 1.18

    def test_the_active_sidebar_link_has_an_accent_marker(self, css):
        rule = css.split(f"{DARK_SCOPE} .app-sidebar__link--active {{")[1].split("}")[0]
        assert "var(--color-accent)" in rule


class TestDarkLeftovers:
    def test_native_controls_render_dark(self, css):
        block = re.search(re.escape(DARK_SCOPE) + r"\s*\{(.*?)\}", css, flags=re.S).group(1)
        assert "color-scheme: dark" in block
        assert "accent-color: var(--color-accent)" in block

    @pytest.mark.parametrize("literal", ["#cbd2d9", "#aeb7c2"])
    def test_shared_border_literals_live_only_in_root(self, css, literal):
        root = re.search(r":root\s*\{(.*?)\}", css, flags=re.S).group(0)
        assert css.count(literal) == root.count(literal) == 1, literal

    @pytest.mark.parametrize("hook", [
        '.entity-table-wrapper--freshness-axis td[data-dash-column="freshness"]',
        ".detail-operational-summary .kpi-card",
        ".page--device-dashboard .equipment-context",
        ".admin-boundary-note",
        "input.dash-filter--case",
    ])
    def test_hard_coded_light_edges_have_a_dark_rule(self, css, hook):
        assert f"{DARK_SCOPE} {hook}" in css

    def test_disabled_secondary_buttons_get_a_dark_fill(self, css):
        rule = css.split(f'{DARK_SCOPE} button:disabled:not([class*="--primary"]) {{')[1].split("}")[0]
        assert "background" in rule


def test_every_sidebar_icon_has_a_drawing():
    """A sidebar icon without a mask rule paints as a solid square."""
    from components.app_sidebar import SIDEBAR_SECTIONS
    text = CSS_PATH.read_text(encoding="utf-8")
    for _title, items in SIDEBAR_SECTIONS:
        for _key, _label, _href, icon in items:
            assert re.search(rf"\.app-sidebar__icon--{re.escape(icon)}\s*\{{[^}}]*mask-image", text), icon
