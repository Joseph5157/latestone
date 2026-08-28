"""One card surface, driven by one spacing variable.

Five surfaces implemented the same idea and disagreed on it: two radii
(8px/6px), one lone box-shadow at 3% alpha, and four padding combinations.
Border and background were the only properties they already shared. The
primitive fixes the surface in one place so a card cannot drift again by
being written a sixth time.

Anatomy follows the shadcn Card: a header carrying title, description and an
optional action pinned top-right, then the card's own content. The action
slot is the part Fleet Overview was missing — "View full fleet" lived inside
a bespoke summary row because there was nowhere for a card-level action to
go.
"""
from pathlib import Path
import re

import pytest
from dash import html

from components.card import card_header
from tests.dash_tree import find_by_exact_class, text_of, walk


@pytest.fixture(scope="module")
def css():
    text = (Path(__file__).resolve().parents[1] / "assets" / "app.css").read_text(
        encoding="utf-8"
    )
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rule(css, selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"Missing rule: {selector}"
    return match.group(1)


class TestSurface:
    def test_spacing_is_one_variable_not_a_padding_literal(self, css):
        body = rule(css, ".card")
        assert "--card-spacing:" in body
        assert "padding: var(--card-spacing)" in body

    def test_the_gap_between_sections_comes_from_the_same_variable(self, css):
        """Four padding combinations existed because padding and rhythm were
        set independently on every surface."""
        assert "gap: var(--card-spacing)" in rule(css, ".card")

    def test_the_small_variant_changes_only_the_spacing(self, css):
        body = rule(css, ".card--sm")
        assert "--card-spacing:" in body
        assert "border" not in body and "radius" not in body

    def test_the_surface_uses_tokens_rather_than_literals(self, css):
        body = rule(css, ".card")
        assert "border-radius: var(--radius)" in body
        assert "border: 1px solid var(--color-border)" in body
        assert "background: var(--color-surface)" in body

    def test_separation_is_the_border_not_elevation(self, css):
        """The one shadow in the old set was rgb(31 41 55 / 3%) — invisible,
        and inconsistent with the four surfaces that had none."""
        assert "box-shadow" not in rule(css, ".card")


class TestHeaderAnatomy:
    def test_the_action_sits_beside_the_title_not_below_it(self, css):
        assert "grid-template-columns: 1fr auto" in rule(css, ".card__header")

    def test_title_and_description_share_the_first_column(self, css):
        assert "grid-column: 1" in rule(css, ".card__title")
        assert "grid-column: 1" in rule(css, ".card__description")


class TestCardHeader:
    def test_renders_title_and_description(self):
        header = card_header("Fleet Condition", "Attention across the fleet")
        assert text_of(header) == "Fleet Condition Attention across the fleet"

    def test_description_is_optional(self):
        header = card_header("Fleet Condition")
        assert find_by_exact_class(header, "card__description") == []

    def test_action_is_optional(self):
        header = card_header("Fleet Condition", "x")
        assert find_by_exact_class(header, "card__action") == []

    def test_an_action_is_placed_in_its_own_slot(self):
        link = html.A("View full fleet", href="#fleet-plants")
        header = card_header("Needs attention", "3 affected RTLs", action=link)
        slot = find_by_exact_class(header, "card__action")
        assert len(slot) == 1
        assert link in list(walk(slot[0]))

    def test_heading_level_is_the_callers_choice(self):
        """A card inside a section is not automatically an h3; the page owns
        its outline."""
        header = card_header("Needs attention", heading=html.H2)
        assert isinstance(find_by_exact_class(header, "card__title")[0], html.H2)


class TestFleetOverviewMigration:
    def test_the_condition_card_uses_the_shared_surface(self):
        from components.fleet_condition import fleet_condition_summary
        from services.monitoring_service import Freshness

        section = fleet_condition_summary({Freshness.FRESH: 3, Freshness.STALE: 1})
        assert "card" in section.className.split()

    def test_needs_attention_uses_the_shared_surface(self):
        from components.needs_attention import needs_attention

        panel = needs_attention({"groups": [], "total_rtls": 0})
        assert "card" in panel.className.split()

    def test_view_full_fleet_moves_into_the_card_action_slot(self):
        """It was inside `needs-attention__summary-row`, a bespoke element
        that existed only because the card had no action slot.

        Built through `build_exception_queue` rather than a hand-written dict:
        the queue's shape is a real contract between builder and renderer, and
        a fake that satisfies neither proves nothing.
        """
        from callbacks.listings import build_exception_queue
        from components.needs_attention import needs_attention
        from tests.test_needs_attention import NOW, STALE_TS, _codes, _health, _Plant

        health = _health([("p1", "t1", "d1", STALE_TS)])
        queue = build_exception_queue([_Plant("p1", "Aaa")], health, NOW, **_codes())
        panel = needs_attention(queue)
        action = find_by_exact_class(panel, "card__action")
        assert len(action) == 1
        assert "View full fleet" in text_of(action[0])

    def test_the_migrated_surfaces_no_longer_set_their_own_geometry(self, css):
        """A surface that still declares radius or padding has not migrated —
        it has gained a class and kept its old rules to fight with."""
        for selector in (".fleet-condition__card", ".needs-attention"):
            body = rule(css, selector)
            assert "border-radius" not in body
            assert "box-shadow" not in body
            assert not re.search(r"(?<![-\w])padding\s*:", body)
