"""The breadcrumb gets its own row, at every width — not just mobile.

`.app-header` was a flex row with `.header__brand`'s `margin-right: auto`
pushing everything else to the right edge. Breadcrumb, freshness and Logout
landed side by side there in DOM order, so the trail rendered as a single
word wedged beside Logout — the same size and colour as a header control,
2,100px from the page heading it describes.

A full-width breadcrumb row already existed, but only inside
`@media (max-width: 768px)`. This makes that the base layout at every width,
and narrows the mobile block to genuine size/spacing overrides rather than
positions duplicated wholesale.
"""
from pathlib import Path
import re

import pytest

from components.app_header import app_header
from services.monitoring_service import Freshness
from tests.dash_tree import find_by_exact_class, walk


@pytest.fixture(scope="module")
def css():
    text = (Path(__file__).resolve().parents[1] / "assets" / "app.css").read_text(
        encoding="utf-8"
    )
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def base_rule(css, selector):
    """The unscoped rule — the first match outside any @media block, found
    by requiring the selector to start a line (nothing inside a media query
    is indented that way in this file)."""
    match = re.search(r"^" + re.escape(selector) + r"\s*\{([^}]*)\}", css, re.M)
    assert match, f"Missing base rule: {selector}"
    return match.group(1)


class TestHeaderIsAGridAtEveryWidth:
    def test_the_header_is_a_grid_by_default_not_only_on_mobile(self, css):
        header = base_rule(css, ".app-header")
        assert "display: grid" in header
        assert "grid-template-columns: minmax(0, 1fr) auto" in header

    def test_the_breadcrumb_spans_the_full_row(self, css):
        breadcrumb = base_rule(css, ".header__breadcrumb")
        assert "grid-column: 1 / -1" in breadcrumb

    def test_the_breadcrumb_is_its_own_row_below_brand_and_logout(self, css):
        """Row 1 is brand + Logout; the breadcrumb is row 2, so it sits
        directly under the brand bar and above the page's own heading —
        not squeezed onto row 1 beside Logout."""
        brand = base_rule(css, ".header__brand")
        breadcrumb = base_rule(css, ".header__breadcrumb")
        logout = base_rule(css, ".header__logout-wrapper")
        assert "grid-row: 2" in breadcrumb
        assert "grid-row: 1" in logout
        # brand takes row 1 by grid auto-placement (no row set); it must not
        # have been pinned to the same row as the breadcrumb by mistake.
        assert "grid-row: 2" not in brand

    def test_freshness_does_not_share_a_row_with_the_breadcrumb(self, css):
        """Both are optional and independent; if a page renders both, they
        must not collide in the same grid cell."""
        breadcrumb_row = re.search(r"grid-row:\s*(\d+)", base_rule(css, ".header__breadcrumb"))
        freshness_row = re.search(r"grid-row:\s*(\d+)", base_rule(css, ".header__freshness"))
        assert breadcrumb_row and freshness_row
        assert breadcrumb_row.group(1) != freshness_row.group(1)

    def test_logout_stays_on_the_brand_row_not_pushed_down(self, css):
        logout = base_rule(css, ".header__logout-wrapper")
        assert "grid-row: 1" in logout
        assert "grid-column: 2" in logout


class TestMobileOverrideIsSizingOnly:
    """Positions now live in the base rule; the media query should not
    restate them — a duplicate that drifts from the base is worse than no
    override at all."""

    @pytest.fixture(scope="module")
    def mobile_block(self, css):
        """The header's rules inside `@media (max-width: 768px)`.

        That media query is one large shared block (header rules, then page
        padding, then the Asset Navigator's responsive layout, ...), so it
        cannot be isolated by matching to the block's closing brace. Bounded
        instead between the header comment and the next rule known to follow
        it directly in the same block.
        """
        match = re.search(
            r"@media \(max-width: 768px\) \{\n  \.app-header \{(.*?)\n  \.page,",
            css, re.S,
        )
        assert match, "Could not find the header's mobile media block"
        return match.group(1)

    def test_mobile_no_longer_redeclares_breadcrumb_position(self, mobile_block):
        assert re.search(r"\.header__breadcrumb\s*\{", mobile_block) is None

    def test_mobile_no_longer_redeclares_logout_position(self, mobile_block):
        assert re.search(r"\.header__logout-wrapper\s*\{", mobile_block) is None

    def test_mobile_no_longer_redeclares_freshness_position(self, mobile_block):
        """It previously pinned freshness to row 2 — the same row the
        breadcrumb now owns in the base rule, which would collide."""
        assert re.search(r"\.header__freshness\s*\{", mobile_block) is None


class TestRenderedStructureIsUnchanged:
    """Pure CSS change: the component tree and DOM order stay exactly as
    they were — order is what the grid rows above rely on."""

    def test_child_order_is_brand_breadcrumb_freshness_logout(self):
        header = app_header(breadcrumb_children="x", freshness=Freshness.FRESH)
        classes = [
            getattr(n, "className", None)
            for n in header.children
        ]
        assert classes == [
            "header__brand", "header__breadcrumb", "header__freshness",
            "header__logout-wrapper",
        ]

    def test_breadcrumb_slot_is_still_optional(self):
        header = app_header()
        assert find_by_exact_class(header, "header__breadcrumb") == []
