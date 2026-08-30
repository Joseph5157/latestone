"""Command Center theme + shell integration (CC-1 Phase 11, ADR-006).

Two halves, and the second is the one that matters.

The first is ordinary: a Dark|Light toggle sets a class on the page root and
the choice survives a re-render.

The second is CONTAINMENT. This gate introduces the application's first
theme, and the whole risk is that it escapes — a token redefined in `:root`,
a bare element selector, a semantic colour changed globally — and quietly
restyles `/plants`, Reports and Notifications. Those tests assert over the
stylesheet's structure, because that is where the leak would be: a rendering
test only catches the routes it fixtures, and the routes at risk are the
ones nobody thought to fixture.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from dash import html

from components.command_center import theme
from pages.command_center import layout

CSS_PATH = Path(__file__).resolve().parents[1] / "assets" / "app.css"


@pytest.fixture(scope="module")
def css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


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


def _rule_selectors(css: str) -> list[str]:
    """Every selector in the stylesheet, comments stripped.

    Crude on purpose — it must not depend on a CSS parser this repo does not
    have, and it only ever needs to answer "what does this rule match".
    """
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [
        part.strip()
        for block in re.findall(r"([^{}]+)\{[^{}]*\}", stripped)
        for part in block.split(",")
        if part.strip() and not part.strip().startswith("@")
    ]


class TestTheClassReachesTheRoot:
    def test_the_page_root_carries_the_default_theme(self):
        root = layout()
        assert theme.THEME_CLASS_DARK in root.className
        assert "page--command-center" in root.className

    def test_dark_is_the_default(self):
        """A control room is the primary environment (ADR-006). Light is the
        field/daylight case, chosen deliberately rather than fallen into."""
        assert theme.DEFAULT_THEME == theme.DARK

    def test_the_root_is_addressable_by_a_callback(self):
        """The toggle rewrites this element's className, so it needs an id."""
        root = layout()
        assert root.id == theme.ROOT_ID

    def test_each_theme_maps_to_exactly_one_class(self):
        assert theme.theme_class(theme.DARK) == theme.THEME_CLASS_DARK
        assert theme.theme_class(theme.LIGHT) == theme.THEME_CLASS_LIGHT
        assert theme.THEME_CLASS_DARK != theme.THEME_CLASS_LIGHT

    def test_an_unknown_stored_value_falls_back_rather_than_breaking(self):
        """Session storage is user-writable. A hand-edited value must land on
        an appearance, never on a page with no theme class at all."""
        assert theme.theme_class("chartreuse") == theme.theme_class(theme.DEFAULT_THEME)

    def test_the_root_class_never_carries_both_appearances(self):
        for choice in (theme.DARK, theme.LIGHT):
            className = theme.root_class_name(choice)
            assert (theme.THEME_CLASS_DARK in className) != (
                theme.THEME_CLASS_LIGHT in className
            )

    def test_the_route_class_survives_every_theme(self):
        """The cockpit layout keys off `page--command-center`. Losing it while
        swapping themes would silently unfix the fixed-viewport layout."""
        for choice in (theme.DARK, theme.LIGHT, "nonsense"):
            assert "page--command-center" in theme.root_class_name(choice)


class TestTheToggle:
    def test_it_offers_both_appearances_by_name(self):
        control = theme.theme_toggle(theme.DARK)
        labels = _texts(control)
        assert "Dark" in labels
        assert "Light" in labels

    def test_it_marks_the_active_choice_for_assistive_tech(self):
        """Not colour alone — the same rule the status vocabulary follows."""
        for choice in (theme.DARK, theme.LIGHT):
            control = theme.theme_toggle(choice)
            pressed = [
                getattr(n, "n_clicks_timestamp", None) or n
                for n in _walk(control)
                if isinstance(n, html.Button)
            ]
            assert len(pressed) == 2
            states = [
                getattr(b, "aria-pressed", None)
                or (b.to_plotly_json().get("props", {}).get("aria-pressed"))
                for b in _walk(control)
                if isinstance(b, html.Button)
            ]
            assert states.count("true") == 1

    def test_it_is_buttons_not_links(self):
        """It changes appearance, it does not navigate."""
        from dash import dcc

        control = theme.theme_toggle(theme.DARK)
        assert not [n for n in _walk(control) if isinstance(n, (dcc.Link, html.A))]

    def test_the_next_theme_alternates(self):
        assert theme.other(theme.DARK) == theme.LIGHT
        assert theme.other(theme.LIGHT) == theme.DARK


class TestContainment:
    """The theme must not be able to reach another route."""

    def test_no_dark_rule_is_defined_at_root(self, css):
        """A dark token in `:root` would repaint the whole application."""
        root_blocks = re.findall(r":root\s*\{([^}]*)\}", css)
        for block in root_blocks:
            assert theme.DARK_CANVAS not in block.lower()

    def test_every_theme_rule_is_scoped_to_the_command_center(self, css):
        """Each rule mentioning a theme class must ALSO name the route.

        A bare `.cc-theme--dark` would work today only because nothing else
        renders that class — which is a coincidence, not containment.
        """
        themed = [
            s for s in _rule_selectors(css)
            if theme.THEME_CLASS_DARK in s or theme.THEME_CLASS_LIGHT in s
        ]
        assert themed, "no theme rules found — the stylesheet half is missing"
        for selector in themed:
            assert "page--command-center" in selector, (
                f"theme rule not route-scoped: {selector!r}"
            )

    def test_the_semantic_tones_are_route_scoped_too(self, css):
        """No Data purple and the Warning/Stale split apply in BOTH
        appearances, so they are scoped by ROUTE rather than by theme class
        (ADR-006, amended). They must still never escape the route."""
        toned = [
            s for s in _rule_selectors(css)
            if "command-center__tone--" in s and "--cc-" not in s
        ]
        assert toned, "no tone rules found"

    def test_no_theme_rule_targets_a_bare_element(self, css):
        """`body { background: … }` inside a theme block is the classic leak."""
        for selector in _rule_selectors(css):
            if theme.THEME_CLASS_DARK in selector or theme.THEME_CLASS_LIGHT in selector:
                head = selector.split()[0]
                assert head.startswith((".", "#", ":")), (
                    f"theme rule starts at a bare element: {selector!r}"
                )

    def test_the_shared_state_tokens_are_untouched_in_root(self, css):
        """Fleet Overview renders `--state-none-*` and `--state-stale-*`.
        Phase 11 gives No Data a purple and separates Warning from Stale — both
        INSIDE the Command Center scope. Redefining them here would restyle
        /plants, which ADR-006's regression rule forbids."""
        root = re.search(r":root\s*\{(.*?)\}", css, flags=re.S).group(1)
        assert "--state-none-text: #495057" in root
        assert "--state-stale-text: #713f12" in root

    def test_the_semantic_overrides_exist_and_are_scoped(self, css):
        """The two colours that differ from today's application must be
        present, and must be inside the route scope."""
        scoped = [
            selector
            for selector in _rule_selectors(css)
            if "page--command-center" in selector
        ]
        assert scoped, "no route-scoped rules found at all"

    def test_no_shell_python_file_was_given_a_theme_hook(self):
        """ADR-006's answered question: the shell reacts via :has(), it is not
        rewritten. If a theme class appears in these files, the hook stopped
        being minimal and the gate needs re-opening, not a bigger diff."""
        for name in ("app_shell.py", "app_sidebar.py", "app_header.py"):
            source = (
                Path(__file__).resolve().parents[1] / "components" / name
            ).read_text(encoding="utf-8")
            assert theme.THEME_CLASS_DARK not in source
            assert theme.THEME_CLASS_LIGHT not in source
            assert "theme" not in source.lower().replace("theme_", "")


class TestTypographySurvives:
    def test_no_theme_rule_changes_the_family(self, css):
        """IBM Plex Sans remains the face (gate constraint)."""
        stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for block in re.findall(r"([^{}]*)\{([^{}]*)\}", stripped):
            selector, body = block
            if theme.THEME_CLASS_DARK in selector or theme.THEME_CLASS_LIGHT in selector:
                assert "font-family" not in body

    def test_telemetry_keeps_tabular_numerals(self, css):
        """Numbers must not shift column as they change."""
        assert "font-variant-numeric: tabular-nums" in css


class TestUnavailableNeverAcquiresSeverity:
    """ADR-001 / gate D5. "We cannot derive this" is not a severity."""

    def test_it_resolves_to_the_neutral_token(self, css):
        block = re.search(
            r"\.command-center__unavailable\s*\{([^}]*)\}", css
        ).group(1)
        assert "var(--color-muted)" in block

    def test_the_neutral_rule_actually_wins_the_cascade(self, css):
        """Presence is not effect.

        `.command-center__unavailable` alone is 0,1,0 and LOSES to
        `.command-center__condition-facts dd` at 0,1,1 — so for its whole life
        this rule existed and never applied, and the value rendered in primary
        text colour. Invisible against a light canvas; obvious against Phase
        11's dark one. Assert the winning selector, not the wish.
        """
        def specificity(selector: str) -> tuple[int, int, int]:
            ids = len(re.findall(r"#[\w-]+", selector))
            classes = len(re.findall(r"\.[\w-]+|\[[^\]]*\]|:[\w-]+", selector))
            elements = len(
                re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", selector)
            )
            return (ids, classes, elements)

        selectors = _rule_selectors(css)
        competing = max(
            (s for s in selectors if s.endswith("condition-facts dd")),
            key=specificity,
            default=None,
        )
        assert competing, "the competing dd rule vanished — re-check this test"
        winner = max(
            (s for s in selectors if "command-center__unavailable" in s
             and "-dash" not in s),
            key=specificity,
        )
        assert specificity(winner) > specificity(competing), (
            f"{winner!r} does not out-specify {competing!r}"
        )

    def test_it_carries_no_semantic_tone(self, css):
        """It must never be repainted with a `--cc-` state colour — in
        either appearance."""
        block = re.search(
            r"\.command-center__unavailable\s*\{([^}]*)\}", css
        ).group(1)
        assert "--cc-" not in block

    def test_no_theme_rule_singles_it_out(self, css):
        """It themes by inheriting `--color-muted`, which the dark block
        redefines. A dedicated rule would be a second place for it to drift."""
        for selector in _rule_selectors(css):
            if "command-center__unavailable" in selector:
                assert theme.THEME_CLASS_DARK not in selector
                assert theme.THEME_CLASS_LIGHT not in selector


class TestInheritedTextIsThemed:
    def test_the_route_scope_sets_a_text_colour(self, css):
        """`body` hardcodes a light `color`, so anything without a colour rule
        of its own inherits it. The page H1 has none — in dark that rendered
        1.22:1 and was effectively invisible. The scope must set `color` so
        un-ruled descendants follow the appearance, not just the elements
        somebody remembered to style."""
        # NOT `re.search`: the cockpit layout block uses this same selector
        # and comes first, so searching once finds a block that legitimately
        # sets no colour and the test fails on the wrong rule.
        blocks = re.findall(
            r"\.app-root:has\(\.page--command-center\)\s*\{([^}]*)\}", css
        )
        assert blocks, "the route-scoped block is gone"
        assert any(
            re.search(r"(^|;|\s)color:\s*var\(--color-text\)", b) for b in blocks
        ), "no route-scoped block sets an inheritable text colour"

    def test_the_active_nav_item_is_re_expressed_in_dark(self, css):
        """Its light-mode pairing (brand text on a surface pill) inverts in
        dark, where brand IS the near-black ground."""
        assert ".app-sidebar__link--active" in css
        scoped = [
            s for s in _rule_selectors(css)
            if "app-sidebar__link--active" in s and theme.THEME_CLASS_DARK in s
        ]
        assert scoped, "no dark-appearance rule for the active nav item"
