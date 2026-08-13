"""Entity context component — static label/value pairs, presentation only."""
from __future__ import annotations

from components.entity_context import entity_context
from tests.dash_tree import find_by_exact_class, text_of


class TestOrderingAndContent:
    def test_renders_one_item_per_supplied_pair(self):
        card = entity_context([("Country", "Germany"), ("Primary fuel", "Gas")])
        assert len(find_by_exact_class(card, "entity-context__item")) == 2

    def test_preserves_supplied_order(self):
        card = entity_context([
            ("Country", "Germany"), ("Primary fuel", "Gas"), ("Capacity", "450 MW"),
        ])
        labels = [text_of(n) for n in find_by_exact_class(card, "entity-context__label")]
        assert labels == ["Country", "Primary fuel", "Capacity"]

    def test_renders_the_given_values(self):
        card = entity_context([("Country", "Germany")])
        assert "Germany" in text_of(card)


class TestMissingValues:
    def test_none_value_renders_as_an_em_dash(self):
        card = entity_context([("Capacity", None)])
        values = find_by_exact_class(card, "entity-context__value")
        assert values[0].children == "—"

    def test_empty_string_value_renders_as_an_em_dash(self):
        card = entity_context([("Capacity", "")])
        values = find_by_exact_class(card, "entity-context__value")
        assert values[0].children == "—"

    def test_zero_is_a_real_value_not_a_missing_one(self):
        """0 is a legitimate count (e.g. zero transformers) - only None/""
        fall back to the em dash, matching config.metrics.format_value's
        None-only convention."""
        card = entity_context([("Transformers", 0)])
        values = find_by_exact_class(card, "entity-context__value")
        assert values[0].children == 0
