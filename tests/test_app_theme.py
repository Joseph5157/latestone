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
