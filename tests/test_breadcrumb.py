"""The breadcrumb says where you are — to assistive technology as well.

It looked right and announced badly: two unnamed `<nav>` landmarks on every
page, a current item that was visually current but programmatically just
text, and a "›" read aloud between every pair of labels.

Structure carries the meaning. An ordered list is what conveys sequence and
position ("item 2 of 4"); a run of spans conveys nothing, and the other
fixes hang off getting that right.
"""
import pytest
from dash import dcc, html

from components.breadcrumb import breadcrumb
from tests.dash_tree import walk

@pytest.fixture(scope="module")
def css():
    from pathlib import Path
    import re

    text = (Path(__file__).resolve().parents[1] / "assets" / "app.css").read_text(
        encoding="utf-8"
    )
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rule(css, selector):
    import re

    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"Missing rule: {selector}"
    return match.group(1)


DEEPEST = [
    ("Fleet", "/plants"),
    ("Az Zour South CCGT", "/plants/plant-11"),
    ("ku01", "/plants/plant-11/plant-11-t1"),
    ("29044", None),
]


def items(trail):
    return [n for n in walk(breadcrumb(trail)) if isinstance(n, html.Li)]


class TestLandmark:
    def test_the_trail_is_a_named_navigation_landmark(self):
        """The app renders two `<nav>`s — this and the sidebar. Unnamed, they
        are announced identically."""
        nav = breadcrumb(DEEPEST)
        assert isinstance(nav, html.Nav)
        assert getattr(nav, "aria-label") == "Breadcrumb"

    def test_the_sidebar_names_itself_too(self):
        """A label here only disambiguates if the other landmark has one."""
        from components.app_sidebar import app_sidebar_shell

        navs = [n for n in walk(app_sidebar_shell()) if isinstance(n, html.Nav)]
        assert navs, "sidebar renders no nav landmark"
        assert all(getattr(n, "aria-label", None) for n in navs)


class TestListStructure:
    def test_the_trail_is_an_ordered_list(self):
        """Order is the whole meaning of a breadcrumb."""
        nav = breadcrumb(DEEPEST)
        assert any(isinstance(n, html.Ol) for n in walk(nav))

    def test_one_item_per_step(self):
        assert len(items(DEEPEST)) == 4

    def test_a_single_step_trail_is_still_a_list(self):
        """Most pages have one crumb; the structure should not change shape
        for them."""
        assert len(items([("Fleet", None)])) == 1


class TestCurrentPage:
    def test_the_current_page_is_marked_not_merely_styled(self):
        current = [
            n for n in walk(breadcrumb(DEEPEST))
            if getattr(n, "aria-current", None) == "page"
        ]
        assert len(current) == 1
        assert current[0].children == "29044"

    def test_the_current_page_is_not_a_link(self):
        """A link to the page you are on is a dead control."""
        nav = breadcrumb(DEEPEST)
        hrefs = [n.href for n in walk(nav) if isinstance(n, dcc.Link)]
        assert hrefs == ["/plants", "/plants/plant-11", "/plants/plant-11/plant-11-t1"]

    def test_earlier_steps_are_not_marked_current(self):
        marked = [n for n in walk(breadcrumb(DEEPEST)) if getattr(n, "aria-current", None)]
        assert len(marked) == 1


class TestSeparators:
    def test_separators_are_hidden_from_assistive_technology(self):
        """Otherwise the deepest trail announces three angle quotation marks
        between its four labels."""
        seps = [
            n for n in walk(breadcrumb(DEEPEST))
            if getattr(n, "className", None) == "breadcrumb__sep"
        ]
        assert len(seps) == 3
        assert all(getattr(s, "aria-hidden") == "true" for s in seps)

    def test_no_separator_before_the_first_step(self):
        seps = [
            n for n in walk(breadcrumb([("Fleet", None)]))
            if getattr(n, "className", None) == "breadcrumb__sep"
        ]
        assert seps == []


class TestLongLabels:
    """"Itaipu Binacional Dam (Paraguay part)" is a real plant name. The
    device page previously handled it with `word-break: break-word`, which
    breaks a name mid-word rather than truncating it.
    """

    def test_a_long_label_truncates_rather_than_breaking_mid_word(self, css):
        body = rule(css, ".breadcrumb__link, .breadcrumb__current")
        assert "text-overflow: ellipsis" in body
        assert "white-space: nowrap" in body
        assert "max-width" in body

    def test_no_breadcrumb_rule_breaks_words(self, css):
        """Scoped to breadcrumb selectors: `word-break: break-word` is still
        right elsewhere (the user-admin table wraps long usernames at narrow
        widths), so a file-wide assertion would fail on unrelated CSS."""
        import re

        for m in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
            if "breadcrumb" in m.group(1):
                assert "word-break" not in m.group(2), m.group(1).strip()

    def test_a_truncated_label_keeps_its_full_text_available(self):
        """Truncation must not lose the name — the title carries it."""
        long_name = "Itaipu Binacional Dam (Paraguay part)"
        nav = breadcrumb([("Fleet", "/plants"), (long_name, None)])
        current = next(
            n for n in walk(nav) if getattr(n, "aria-current", None) == "page"
        )
        assert current.title == long_name
