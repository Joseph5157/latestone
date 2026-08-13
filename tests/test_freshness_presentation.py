"""Contracts for the shared Freshness -> presentation mapping.

`freshness_badge` (a real DOM badge) and `entity_table` (DataTable cell
styling) each consume `FRESHNESS_PRESENTATION` for a different purpose. These
tests pin the one shared definition and that each renderer still reads its
own token from it correctly, rather than pinning the renderers to share a
DOM structure they cannot share.
"""
from __future__ import annotations

import pytest

from components.entity_table import freshness_style_rules
from components.freshness_badge import FRESHNESS_LABELS, freshness_badge
from components.freshness_presentation import FRESHNESS_PRESENTATION
from services.monitoring_service import Freshness


def test_presentation_mapping_covers_every_freshness_state_exactly():
    """A fourth state must be presented deliberately, not left to a KeyError
    at render time."""
    assert set(FRESHNESS_PRESENTATION) == set(Freshness)


@pytest.mark.parametrize("state", list(Freshness))
def test_badge_label_comes_from_the_shared_mapping(state):
    assert FRESHNESS_LABELS[state] == FRESHNESS_PRESENTATION[state].label


@pytest.mark.parametrize("state", list(Freshness))
def test_rendered_badge_text_matches_the_shared_label(state):
    badge = freshness_badge(state)
    assert badge.children == FRESHNESS_PRESENTATION[state].label


@pytest.mark.parametrize("state", list(Freshness))
def test_table_style_rule_colour_comes_from_the_shared_mapping(state):
    rules = {
        r["if"]["filter_query"]: r["color"] for r in freshness_style_rules("freshness")
    }
    token = FRESHNESS_PRESENTATION[state].text_token
    query = f'{{_state}} eq "{state.value}"'
    assert rules[query] == f"var(--state-{token}-text)"


def test_no_data_text_token_is_the_neutral_none_token_not_the_enum_value():
    """The one deliberate divergence: NO_DATA's CSS token is `none`, not
    `no_data`. Guards against a "helpful" simplification collapsing the two."""
    assert FRESHNESS_PRESENTATION[Freshness.NO_DATA].text_token == "none"
